#!/usr/bin/env python3
"""Read-only preflight and verification for the managed kubelet resource profile."""

import json
import re
import struct
import subprocess
import sys
from decimal import Decimal, ROUND_CEILING


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
        return resource_value(container.get('resources', {}).get('requests', {}).get(resource, 0), resource)
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
        request_value = resource_value(pod_level[resource], resource)
    return request_value + resource_value(spec.get('overhead', {}).get(resource, 0), resource)


def resource_value(value, resource):
    scale = 1000 if resource == 'cpu' else 1
    return (quantity(value) * scale).to_integral_value(rounding=ROUND_CEILING) / scale


def threshold_value(value, capacity):
    """Resolve a positive absolute or percentage threshold against its resource."""
    if str(value).endswith('%'):
        if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?%', str(value)):
            raise ValueError('Invalid percentage threshold')
        percent = Decimal(str(value)[:-1])
        if not 0 < percent < 100:
            raise ValueError('Percentage thresholds must be between 0 and 100')
        # Match kubelet's float32 percentage parsing/division and byte truncation.
        f32 = lambda number: struct.unpack('f', struct.pack('f', number))[0]
        fraction = f32(f32(float(percent)) / 100)
        result = Decimal(int(float(capacity) * fraction))
    else:
        result = quantity(value).to_integral_value(rounding=ROUND_CEILING)
    if result <= 0:
        raise ValueError('Eviction thresholds must be positive')
    return result


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
    result = {}
    for resource in ('cpu', 'memory'):
        capacity = resource_value(node['status']['capacity'][resource], resource)
        reserved = sum(resource_value(config[s][resource], resource) for s in ('systemReserved', 'kubeReserved'))
        eviction = threshold_value(thresholds['memory.available'], capacity) if resource == 'memory' else 0
        result[resource] = capacity - reserved - eviction
        if result[resource] <= 0:
            raise ValueError(f'Reservations leave no allocatable {resource}')
    return result


def require_ready(nodes):
    for node in nodes:
        conditions = {c['type']: c['status'] for c in node.get('status', {}).get('conditions', [])}
        if conditions.get('Ready') != 'True':
            raise ValueError(f"Node {node['metadata']['name']} is not Ready")
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
    memory_buffer = threshold_value(config['evictionHard']['memory.available'], quantity(node['status']['capacity']['memory']))
    if stats['node']['memory']['availableBytes'] <= memory_buffer:
        raise ValueError('Current available memory is below the proposed eviction buffer')
    for prefix, fs in [('nodefs', stats['node']['fs']), ('imagefs', stats['node']['runtime']['imageFs'])]:
        for signal, available, capacity in [('available', 'availableBytes', 'capacityBytes'),
                                            ('inodesFree', 'inodesFree', 'inodes')]:
            threshold = threshold_value(config['evictionHard'][f'{prefix}.{signal}'], fs[capacity])
            if fs[available] <= threshold:
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
