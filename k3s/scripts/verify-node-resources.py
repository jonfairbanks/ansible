#!/usr/bin/env python3
"""Read-only preflight and verification for the managed kubelet resource profile."""

import json
import re
import subprocess
import sys
from decimal import Decimal


def quantity(value):
    match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)([a-zA-Z]*)', str(value))
    if not match:
        raise ValueError(f'Unsupported resource quantity: {value}')
    factors = {'': 1, 'n': Decimal('1e-9'), 'u': Decimal('1e-6'), 'm': Decimal('.001')}
    factors.update({suffix: 1024**i for i, suffix in enumerate(['Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei'], 1)})
    factors.update({suffix: 1000**i for i, suffix in enumerate(['k', 'M', 'G', 'T', 'P', 'E'], 1)})
    return Decimal(match[1]) * factors[match[2]]


def pod_request(pod, resource):
    """Scheduler request including init containers, native sidecars, and overhead."""
    spec = pod['spec']
    def request(container):
        return quantity(container.get('resources', {}).get('requests', {}).get(resource, 0))
    apps = sum(request(c) for c in spec.get('containers', []))
    sidecars = peak = Decimal(0)
    for container in spec.get('initContainers', []):
        value = request(container)
        if container.get('restartPolicy') == 'Always':
            sidecars += value
            peak = max(peak, sidecars)
        else:
            peak = max(peak, sidecars + value)
    request_value = max(apps + sidecars, peak)
    pod_level = spec.get('resources', {}).get('requests', {})
    if resource in pod_level:
        request_value = quantity(pod_level[resource])
    return request_value + quantity(spec.get('overhead', {}).get(resource, 0))


def projected_allocatable(node, config):
    for section in ('systemReserved', 'kubeReserved'):
        if set(config[section]) != {'cpu', 'memory'}:
            raise ValueError(f'{section} must contain CPU and memory only')
        if any(quantity(value) <= 0 for value in config[section].values()):
            raise ValueError('Reservation quantities must be positive')
    if set(config) != {'apiVersion', 'kind', 'systemReserved', 'kubeReserved', 'evictionHard', 'enforceNodeAllocatable'}:
        raise ValueError('Only the managed reservation and eviction fields are allowed')
    if config['enforceNodeAllocatable'] != ['pods']:
        raise ValueError('System daemon cgroup enforcement is not supported by this rollout')
    thresholds = config['evictionHard']
    if set(thresholds) != {'memory.available', 'nodefs.available', 'imagefs.available', 'nodefs.inodesFree', 'imagefs.inodesFree'}:
        raise ValueError('Specify the complete memory, disk, and inode eviction map')
    if quantity(thresholds['memory.available']) < quantity('100Mi'):
        raise ValueError('The memory eviction buffer must be at least 100Mi')
    for name, value in thresholds.items():
        if name != 'memory.available' and not (
            re.fullmatch(r'[0-9]+(?:\.[0-9]+)?%', str(value)) and 0 < Decimal(str(value)[:-1]) < 100
        ):
            raise ValueError(f'{name} must be a percentage between 0 and 100')
    result = {}
    for resource in ('cpu', 'memory'):
        capacity = quantity(node['status']['capacity'][resource])
        reserved = sum(quantity(config[s][resource]) for s in ('systemReserved', 'kubeReserved'))
        eviction = quantity(thresholds['memory.available']) if resource == 'memory' else 0
        result[resource] = capacity - reserved - eviction
        if result[resource] <= 0:
            raise ValueError(f'Reservations leave no allocatable {resource}')
    return result


def require_ready(nodes):
    for node in nodes:
        conditions = {c['type']: c['status'] for c in node.get('status', {}).get('conditions', [])}
        if conditions.get('Ready') != 'True' or node.get('spec', {}).get('unschedulable', False):
            raise ValueError(f"Node {node['metadata']['name']} is not Ready and schedulable")
        if any(conditions.get(c) != 'False' for c in ('MemoryPressure', 'DiskPressure', 'PIDPressure')):
            raise ValueError(f"Node {node['metadata']['name']} has pressure or missing conditions")


def preflight(node, config, pods, stats):
    projected = projected_allocatable(node, config)
    scheduled = [p for p in pods if p['spec'].get('nodeName') == node['metadata']['name']
                 and p.get('status', {}).get('phase') not in ('Succeeded', 'Failed')]
    for resource in projected:
        requested = sum(pod_request(p, resource) for p in scheduled)
        if requested > projected[resource]:
            raise ValueError(f'Current pod {resource} requests exceed projected allocatable')
    pod_stats = next(c for c in stats['node']['systemContainers'] if c['name'] == 'pods')
    if pod_stats['memory']['workingSetBytes'] > projected['memory']:
        raise ValueError('Current pod memory usage exceeds projected allocatable')
    if stats['node']['memory']['availableBytes'] <= quantity(config['evictionHard']['memory.available']):
        raise ValueError('Current available memory is below the proposed eviction buffer')
    for prefix, fs in [('nodefs', stats['node']['fs']), ('imagefs', stats['node']['runtime']['imageFs'])]:
        for signal, available, capacity in [('available', 'availableBytes', 'capacityBytes'),
                                            ('inodesFree', 'inodesFree', 'inodes')]:
            threshold = Decimal(config['evictionHard'][f'{prefix}.{signal}'][:-1]) / 100
            if fs[available] <= Decimal(fs[capacity]) * threshold:
                raise ValueError(f'{prefix}.{signal} is below the proposed eviction threshold')
    return projected


def verify(node, config, effective):
    projected = projected_allocatable(node, config)
    for field in ('systemReserved', 'kubeReserved', 'evictionHard', 'enforceNodeAllocatable'):
        if effective.get(field) != config[field]:
            raise ValueError(f'Effective {field} differs; inspect K3s CLI flags and later drop-ins')
    for resource, expected in projected.items():
        if quantity(node['status']['allocatable'][resource]) != expected:
            raise ValueError(f'Node allocatable {resource} has not converged to the profile')
    return projected


def kubectl(*args):
    result = subprocess.run(
        ['/usr/local/bin/k3s', 'kubectl', '--request-timeout=20s', *args],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout)


def main():
    try:
        mode, name, encoded = sys.argv[1:]
        config = json.loads(encoded)
        nodes = kubectl('get', 'nodes', '-o', 'json')['items']
        require_ready(nodes)
        node = next(n for n in nodes if n['metadata']['name'] == name)
        if mode == 'preflight':
            projected = preflight(
                node, config,
                kubectl('get', 'pods', '-A', '-o', 'json')['items'],
                kubectl('get', '--raw', f'/api/v1/nodes/{name}/proxy/stats/summary'),
            )
        elif mode == 'verify':
            effective = kubectl('get', '--raw', f'/api/v1/nodes/{name}/proxy/configz')['kubeletconfig']
            projected = verify(node, config, effective)
        else:
            raise ValueError('Mode must be preflight or verify')
        print(f"{name}: {mode} passed; allocatable CPU={projected['cpu']}, memory={projected['memory']} bytes")
        return 0
    except (subprocess.SubprocessError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(f'Node resource check failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
