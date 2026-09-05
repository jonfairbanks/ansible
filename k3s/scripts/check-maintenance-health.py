#!/usr/bin/env python3
"""Read-only maintenance gate. Run on the K3s server; never read Secrets."""

import json
import subprocess
import sys


def failures(nodes, workloads, volumes, jobs, target):
    problems = []
    if not any(obj['kind'] == 'StatefulSet' and obj['metadata']['namespace'] == 'vault-system'
               and obj['metadata']['name'] == 'vault' for obj in workloads):
        problems.append('The required vault-system/vault StatefulSet is absent')
    if target not in {n['metadata']['name'] for n in nodes}:
        problems.append(f'Kubernetes node {target} is absent; check k3s_node_name')
    for node in nodes:
        name = node['metadata']['name']
        conditions = {c['type']: c['status'] for c in node.get('status', {}).get('conditions', [])}
        if conditions.get('Ready') != 'True' or node.get('spec', {}).get('unschedulable', False):
            problems.append(f'Node {name} is not Ready and schedulable')
        if any(conditions.get(c) != 'False' for c in ('MemoryPressure', 'DiskPressure', 'PIDPressure')):
            problems.append(f'Node {name} has pressure or missing pressure conditions')
    for obj in workloads:
        status, spec, meta = obj.get('status', {}), obj.get('spec', {}), obj['metadata']
        name = f"{obj['kind']} {meta['namespace']}/{meta['name']}"
        if status.get('observedGeneration', 0) < meta.get('generation', 1):
            problems.append(f'{name} has an unobserved generation')
        if obj['kind'] == 'DaemonSet':
            desired = status.get('desiredNumberScheduled', 0)
            ready = status.get('numberAvailable', 0)
        else:
            desired = spec.get('replicas', 1)
            ready = status.get('availableReplicas' if obj['kind'] == 'Deployment' else 'readyReplicas', 0)
        if ready < desired:
            problems.append(f'{name} has {ready}/{desired} replicas available')
    for volume in volumes:
        status = volume.get('status', {})
        if status.get('state') != 'detached' and (
            status.get('state') != 'attached' or status.get('robustness') != 'healthy'
        ):
            problems.append(f"Longhorn volume {volume['metadata']['name']} is not healthy")
    for job in jobs:
        if job.get('status', {}).get('active', 0):
            problems.append(f"k6 job {job['metadata']['name']} is active; wait for completion")
    return problems


def get(*args):
    result = subprocess.run(
        ['/usr/local/bin/k3s', 'kubectl', '--request-timeout=20s', 'get', *args, '-o', 'json'],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout)['items']


def main():
    try:
        problems = failures(
            get('nodes'), get('deployments,statefulsets,daemonsets', '-A'),
            get('volumes.longhorn.io', '-n', 'longhorn-system'),
            get('jobs', '-n', 'k6-tests'), sys.argv[1],
        )
    except (subprocess.SubprocessError, ValueError, KeyError, IndexError) as exc:
        print(f'Cannot establish maintenance readiness: {exc}', file=sys.stderr)
        return 1
    if problems:
        print('\n'.join(problems), file=sys.stderr)
        return 1
    print('Nodes, workloads, and Longhorn are healthy; no active k6 jobs.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
