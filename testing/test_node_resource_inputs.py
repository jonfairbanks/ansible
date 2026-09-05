"""Exercise the real Ansible input guard locally; no host-changing tasks run."""

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Requires ansible-playbook')
class OperatorInputTests(unittest.TestCase):
    def setUp(self):
        self.profile = {'systemReserved': {'cpu': '100m', 'memory': '128Mi'},
                        'kubeReserved': {'cpu': '200m', 'memory': '256Mi'}}
        self.evictions = {'memory.available': '5%', 'nodefs.available': '2Gi',
                          'imagefs.available': '10%', 'nodefs.inodesFree': '1000', 'imagefs.inodesFree': '5%'}
        self.inventory = {'all': {'children': {
            'k3s_master': {'hosts': {'server_a': {}}},
            'k3s_workers': {'hosts': {'worker_a': {}}},
        }, 'vars': {'k3s_node_resource_profile': self.profile, 'k3s_node_eviction_hard': self.evictions}}}

    def run_guard(self, extra_args):
        repo = Path(__file__).resolve().parents[1]
        guard = repo / 'k3s/tasks/validate-node-resource-inputs.yaml'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'inventory.json').write_text(json.dumps(self.inventory))
            (root / 'ansible.cfg').write_text('[defaults]\n')
            (root / 'guard.yaml').write_text(
                '- hosts: k3s_workers:k3s_master\n'
                '  gather_facts: false\n'
                '  any_errors_fatal: true\n'
                '  tasks:\n'
                f'    - ansible.builtin.import_tasks: {json.dumps(str(guard))}\n'
                '    - ansible.builtin.debug:\n'
                '        msg: "INPUT {{ inventory_hostname }} {{ k3s_node_resource_profile.systemReserved.cpu }}"\n'
            )
            env = dict(os.environ, ANSIBLE_CONFIG=str(root / 'ansible.cfg'),
                       ANSIBLE_LOCAL_TEMP=str(root / 'ansible-tmp'), ANSIBLE_NOCOLOR='1')
            return subprocess.run(
                ['ansible-playbook', str(root / 'guard.yaml'), '-i', str(root / 'inventory.json'), *extra_args],
                capture_output=True, text=True, env=env, timeout=30,
            )

    def canary(self, host='worker_a'):
        return ['--limit', host, '-e', f'k3s_node_resources_canary_host={host}']

    def test_missing_profile_has_no_implicit_default(self):
        del self.inventory['all']['vars']['k3s_node_resource_profile']
        result = self.run_guard(self.canary())
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('There are no built-in resource sizes or thresholds', result.stdout)

    def test_missing_evictions_has_no_implicit_default(self):
        del self.inventory['all']['vars']['k3s_node_eviction_hard']
        result = self.run_guard(self.canary())
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_null_template_and_incomplete_maps_are_rejected(self):
        self.profile['systemReserved']['cpu'] = None
        self.assertNotEqual(self.run_guard(self.canary()).returncode, 0)
        self.profile['systemReserved']['cpu'] = '100m'
        del self.evictions['imagefs.inodesFree']
        self.assertNotEqual(self.run_guard(self.canary()).returncode, 0)

    def test_server_only_canary_does_not_require_a_worker(self):
        self.inventory['all']['children']['k3s_workers']['hosts'] = {}
        result = self.run_guard(self.canary('server_a'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('INPUT server_a 100m', result.stdout)

    def test_multiple_servers_and_different_host_budgets(self):
        alternate = copy.deepcopy(self.profile)
        alternate['systemReserved']['cpu'] = '600m'
        self.inventory['all']['children']['k3s_master']['hosts']['server_b'] = {
            'k3s_node_resource_profile': alternate}
        result = self.run_guard(['-e', 'k3s_node_resources_canary_verified=true'])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('INPUT server_a 100m', result.stdout)
        self.assertIn('INPUT server_b 600m', result.stdout)

    def test_broad_rollout_requires_verified_canary(self):
        result = self.run_guard([])
        self.assertNotEqual(result.returncode, 0, result.stdout)


if __name__ == '__main__':
    unittest.main()
