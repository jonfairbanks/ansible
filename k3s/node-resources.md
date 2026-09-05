# Kubelet host reservations

`node-resources.yaml` applies operator-supplied CPU/memory reservations and
memory/disk/inode eviction thresholds to existing K3s nodes. It ships **no
resource sizes or eviction thresholds**. Every selected host must receive
explicit values from its inventory's host or group variables.

The playbook owns only
`/var/lib/rancher/k3s/agent/etc/kubelet.conf.d/20-ansible-node-resources.conf`.
It does not change installation arguments, tokens, or other kubelet drop-ins.
K3s 1.32+ supports this directory on servers and agents with an enabled kubelet.
See the [K3s configuration guide](https://docs.k3s.io/installation/configuration#kubelet-configuration-files).

## Supply values for your environment

Use [the unfilled template](examples/node-resources.example.yaml) as a schema.
It is never loaded automatically; its null values deliberately fail validation.
Copy the fields into your inventory's `group_vars` or `host_vars`, and replace
every null before use. Use separate group profiles for different node classes,
and host overrides for nodes with different capacity or workloads. No role
inherits an automatically selected profile.

Required variables:

| Variable | Required contents |
| --- | --- |
| `k3s_node_resource_profile` | `systemReserved` and `kubeReserved`, each containing explicit `cpu` and `memory` quantities |
| `k3s_node_eviction_hard` | `memory.available`, `nodefs.available`, `imagefs.available`, `nodefs.inodesFree`, and `imagefs.inodesFree` |

Quote all values as strings. Reservations use positive Kubernetes quantities: CPU cores or millicores,
and memory bytes or units such as Mi/Gi. Eviction thresholds accept positive
absolute quantities or percentages below 100%; percentages are evaluated against
the corresponding resource's actual capacity. Inode absolute thresholds are
counts. These are accepted formats, not recommended sizes.

The complete eviction map avoids silently losing a threshold when overriding
another one. The playbook retains `enforceNodeAllocatable: [pods]`; it does not
apply hard cgroup limits to host daemons or assign dedicated CPU cores. System
components running as pods still need their own requests. See
[Kubernetes reservations](https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/)
and [node-pressure eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/).

## Choose and validate your budgets

Measure each node class across representative workload peaks and background
maintenance. Account for OS/kernel demand in `systemReserved`, and host-level
Kubernetes/runtime demand in `kubeReserved`. Leave enough pod capacity for
normal work and the failure scenarios your cluster must tolerate.

A node-minus-pod usage estimate can inform the combined budget, but is not an
exact per-daemon measurement. Check scrape coverage, accounting differences,
and spikes between samples. Choose eviction buffers based on your own node
capacity, storage layout, workload growth, and recovery requirements. This
playbook does not infer sizing from the repository author's cluster, a Grafana
installation, or a particular application.

## Inventory and canary

Use the repository's `k3s_workers` and `k3s_master` inventory groups; keep them
disjoint. One or more servers are supported. A cluster without separate workers
can use a server as its canary. Set `k3s_node_name` if the Kubernetes node name
differs from the host's system hostname.

The API checks run on a K3s server over SSH. By default a server other than the
current target is preferred, falling back to the target for a single-server
cluster. Set `k3s_node_resources_api_host` to select a suitable inventory server
explicitly. All selected nodes need Python 3; the delegate needs K3s kubectl
and its administrative kubeconfig. No Secrets are read or printed by the checks.

After merge and approval for an Ansible maintenance execution, select one
representative node with `--limit <node-alias>` and set
`k3s_node_resources_canary_host=<node-alias>`. The canary may be a worker or a
server. Observe representative peak load and background jobs for your environment
before explicitly setting `k3s_node_resources_canary_verified=true` for a broader
rollout. An immediate successful check does not establish long-term sizing.

Workers are processed first, then servers, one at a time. Failure stops later
hosts and phases. On a single-server cluster, restarting the server briefly
interrupts API access. In a multi-server cluster, plan the maintenance window
around your control-plane and datastore availability requirements.

## Execution and verification

A controller-side input pass checks every selected host for missing profiles,
incomplete maps, and unfilled placeholders before any host-changing tasks.
Per-node read-only preflight then rejects reservations that leave no pod
capacity, exceed current pod requests or memory usage, or cross current
memory/disk/inode thresholds. Nodes must be Ready and free of pressure;
existing cordons are preserved. These are snapshot checks, not a scheduler lock.

A changed drop-in restarts only that host's K3s service. This is not a reboot
or a drain. Unchanged files do not trigger a restart. Effective `configz` fields
and CPU/memory allocatable must then match the supplied profile before the next
node starts. A mismatch stops the run; inspect command-line overrides and later
drop-ins instead of bypassing verification. Merge alone does not deploy anything.

Offline checks:

```sh
ansible-playbook k3s/node-resources.yaml -i inventory/hosts.example.ini --syntax-check
ansible-playbook k3s/node-resources.yaml -i inventory/hosts.example.ini --list-hosts
python3 -m unittest discover -s testing -p 'test_node_resource*.py'
git diff --check
```

`--check` is refused because it cannot verify effective settings after restart.
The placeholder inventory is sufficient for syntax and host-selection checks;
a real execution additionally requires the operator-supplied variables.

Rollback requires an approved maintenance execution: restore the previous
managed drop-in (Ansible backs up replacements), or remove this one file if
this was its first installation, then restart that node's K3s service and verify
Ready and `configz`. A Git revert alone does not remove an installed file.
Do not edit `00-k3s-defaults.conf` or remove unrelated drop-ins.
