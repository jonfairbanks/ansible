"""Regression cases for the maintenance safety gate; no cluster writes."""

import copy
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'k3s/scripts/check-maintenance-health.py'
spec = importlib.util.spec_from_file_location('maintenance_health', path)
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class MaintenanceHealthTests(unittest.TestCase):
    def setUp(self):
        self.nodes = [{'metadata': {'name': 'worker'}, 'spec': {}, 'status': {'conditions': [
            {'type': 'Ready', 'status': 'True'},
            *({'type': c, 'status': 'False'} for c in ('MemoryPressure', 'DiskPressure', 'PIDPressure')),
        ]}}]
        self.workloads = [{'kind': 'StatefulSet', 'metadata': {'namespace': 'vault-system', 'name': 'vault', 'generation': 2},
                           'spec': {'replicas': 3}, 'status': {'readyReplicas': 3, 'observedGeneration': 2}}]
        self.volumes = [{'metadata': {'name': 'data'}, 'status': {'state': 'attached', 'robustness': 'healthy'}}]

    def check(self, jobs=None, target='worker'):
        return health.failures(self.nodes, self.workloads, self.volumes, jobs or [], target)

    def test_healthy_cluster(self):
        self.assertEqual(self.check(), [])

    def test_wrong_inventory_name(self):
        self.assertTrue(self.check(target='wrong-alias'))

    def test_cordoned_or_unready_node(self):
        self.nodes[0]['spec']['unschedulable'] = True
        self.assertTrue(self.check())
        self.nodes[0]['spec'].clear()
        self.nodes[0]['status']['conditions'][0]['status'] = 'False'
        self.assertTrue(self.check())

    def test_pressure_or_unknown_conditions(self):
        self.nodes[0]['status']['conditions'][1]['status'] = 'True'
        self.assertTrue(self.check())
        self.nodes[0]['status']['conditions'] = []
        self.assertTrue(self.check())

    def test_vault_replica_not_recovered(self):
        self.workloads[0]['status']['readyReplicas'] = 2
        self.assertTrue(self.check())

    def test_missing_vault_cannot_look_healthy(self):
        self.workloads = []
        self.assertTrue(self.check())

    def test_controller_has_not_observed_change(self):
        self.workloads[0]['status']['observedGeneration'] = 1
        self.assertTrue(self.check())

    def test_daemonset_not_available(self):
        ds = copy.deepcopy(self.workloads[0])
        ds['kind'] = 'DaemonSet'
        ds['status'].update(desiredNumberScheduled=4, numberAvailable=3)
        self.workloads.append(ds)
        self.assertTrue(self.check())

    def test_scaled_to_zero_deployment(self):
        deployment = copy.deepcopy(self.workloads[0])
        deployment.update(kind='Deployment', spec={'replicas': 0})
        self.workloads.append(deployment)
        self.assertEqual(self.check(), [])

    def test_longhorn_degraded_or_rebuilding(self):
        for state, robustness in [('attached', 'degraded'), ('attaching', 'unknown'), ('attached', 'faulted')]:
            self.volumes[0]['status'].update(state=state, robustness=robustness)
            self.assertTrue(self.check())

    def test_detached_volume_does_not_require_attachment(self):
        self.volumes[0]['status'].update(state='detached', robustness='unknown')
        self.assertEqual(self.check(), [])

    def test_active_k6_job_blocks_but_terminal_history_does_not(self):
        self.assertTrue(self.check([{'metadata': {'name': 'load'}, 'status': {'active': 1}}]))
        self.assertEqual(self.check([{'metadata': {'name': 'old-load'}, 'status': {'failed': 1}}]), [])


if __name__ == '__main__':
    unittest.main()
