"""Resource arithmetic, unsafe-profile rejection, and effective-config checks."""

import copy
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'k3s/scripts/verify-node-resources.py'
spec = importlib.util.spec_from_file_location('node_resources', path)
resources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resources)


class NodeResourceTests(unittest.TestCase):
    def setUp(self):
        self.node = {'metadata': {'name': 'worker'}, 'spec': {}, 'status': {
            'capacity': {'cpu': '4', 'memory': '8Gi'},
            'allocatable': {'cpu': '3', 'memory': '5632Mi'},
            'conditions': [{'type': 'Ready', 'status': 'True'},
                           *({'type': c, 'status': 'False'} for c in ('MemoryPressure', 'DiskPressure', 'PIDPressure'))],
        }}
        self.config = {
            'apiVersion': 'kubelet.config.k8s.io/v1beta1', 'kind': 'KubeletConfiguration',
            'systemReserved': {'cpu': '250m', 'memory': '512Mi'},
            'kubeReserved': {'cpu': '750m', 'memory': '1536Mi'},
            'enforceNodeAllocatable': ['pods'],
            'evictionHard': {'memory.available': '512Mi', 'nodefs.available': '10%', 'imagefs.available': '15%',
                             'nodefs.inodesFree': '5%', 'imagefs.inodesFree': '5%'},
        }
        fs = {'availableBytes': 1000, 'capacityBytes': 2000, 'inodesFree': 100, 'inodes': 200}
        self.stats = {'node': {'systemContainers': [{'name': 'pods', 'memory': {'workingSetBytes': 1024**3}}],
                               'memory': {'availableBytes': 2 * 1024**3}, 'fs': fs, 'runtime': {'imageFs': fs}}}

    def test_quantity_equivalence(self):
        self.assertEqual(resources.quantity('1Gi'), resources.quantity('1024Mi'))
        self.assertEqual(resources.quantity('1500m'), resources.quantity('1.5'))

    def test_valid_preflight_and_verified_allocatable(self):
        result = resources.preflight(self.node, self.config, [], self.stats)
        self.assertEqual(result['cpu'], 3)
        self.assertEqual(result['memory'], resources.quantity('5632Mi'))
        self.assertEqual(resources.verify(self.node, self.config, self.config), result)

    def test_oversized_reservation(self):
        self.config['kubeReserved']['memory'] = '8Gi'
        with self.assertRaises(ValueError): resources.projected_allocatable(self.node, self.config)

    def test_partial_eviction_map_and_daemon_enforcement_rejected(self):
        del self.config['evictionHard']['imagefs.inodesFree']
        with self.assertRaises(ValueError): resources.projected_allocatable(self.node, self.config)
        self.setUp()
        self.config['enforceNodeAllocatable'].append('system-reserved')
        with self.assertRaises(ValueError): resources.projected_allocatable(self.node, self.config)

    def test_effective_cli_override_and_old_allocatable_rejected(self):
        effective = copy.deepcopy(self.config)
        effective['evictionHard']['memory.available'] = '100Mi'
        with self.assertRaises(ValueError): resources.verify(self.node, self.config, effective)
        self.node['status']['allocatable']['cpu'] = '4'
        with self.assertRaises(ValueError): resources.verify(self.node, self.config, self.config)

    def test_pod_request_counts_init_sidecars_and_overhead(self):
        container = lambda cpu, **kw: {'resources': {'requests': {'cpu': cpu}}, **kw}
        pod = {'spec': {'containers': [container('500m')], 'initContainers': [
            container('200m', restartPolicy='Always'), container('1500m')], 'overhead': {'cpu': '100m'}}}
        self.assertEqual(resources.pod_request(pod, 'cpu'), resources.quantity('1800m'))
        pod['spec']['resources'] = {'requests': {'cpu': '2'}}
        self.assertEqual(resources.pod_request(pod, 'cpu'), resources.quantity('2100m'))

    def test_excessive_requests_block_but_finished_pods_do_not(self):
        pod = {'spec': {'nodeName': 'worker', 'containers': [{'resources': {'requests': {'cpu': '4'}}}]},
               'status': {'phase': 'Running'}}
        with self.assertRaises(ValueError): resources.preflight(self.node, self.config, [pod], self.stats)
        pod['status']['phase'] = 'Succeeded'
        resources.preflight(self.node, self.config, [pod], self.stats)

    def test_memory_working_set_and_disk_headroom(self):
        self.stats['node']['systemContainers'][0]['memory']['workingSetBytes'] = 6 * 1024**3
        with self.assertRaises(ValueError): resources.preflight(self.node, self.config, [], self.stats)
        self.setUp()
        self.stats['node']['fs']['availableBytes'] = 100
        with self.assertRaises(ValueError): resources.preflight(self.node, self.config, [], self.stats)

    def test_unready_or_cordoned_node_rejected(self):
        resources.require_ready([self.node])
        self.node['spec']['unschedulable'] = True
        with self.assertRaises(ValueError): resources.require_ready([self.node])


if __name__ == '__main__':
    unittest.main()
