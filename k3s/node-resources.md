# Kubelet host reservations

`node-resources.yaml` owns one K3s kubelet drop-in:
`/var/lib/rancher/k3s/agent/etc/kubelet.conf.d/20-ansible-node-resources.conf`.
It is separate from installation, tokens, and generated systemd arguments.
K3s 1.32+ supports this configuration directory on both servers and agents.
The current pin is 1.36.3. See the [K3s configuration guide](https://docs.k3s.io/installation/configuration#kubelet-configuration-files).

This is a reviewed-source rollout path, not an automatic deployment on merge.
It uses only built-in Ansible modules and Python's standard library.

## Proposed profiles

| Role | OS CPU / memory | K3s CPU / memory | Memory eviction buffer | Pod allocatable on current nodes |
| --- | --- | --- | --- | --- |
| Server | 250m / 512Mi | 1750m / 3072Mi | 512Mi | 2 CPU / approximately 2.70Gi |
| Worker | 250m / 512Mi | 750m / 1536Mi | 512Mi | 3 CPU / approximately 4.20Gi |

These reduce advertised scheduling capacity. `enforceNodeAllocatable: [pods]`
retains pod-level enforcement; it does not impose hard cgroup limits on K3s,
containerd, or system daemons. Longhorn and Alloy remain pods with their own
requests. CPU can still burst; these are not CPU affinity assignments.

The complete eviction map includes memory available at 512Mi, root disk
available at 10%, image filesystem available at 15%, and both inode-free
thresholds at 5%. The September 5 live config had only two 5% disk thresholds
and no memory threshold. Defining the whole map avoids silently dropping
defaults when overriding one entry. See [Kubernetes reservations](https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/)
and [node-pressure eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/).

## Measurement basis and limitations

Read-only Grafana queries on September 5, 2026 used the preceding seven days,
sampled at five-minute resolution. The non-pod memory estimate was node working
set minus the sum of pod-container working sets. Server p99/max were about
3087/3183Mi; worker p99 values ranged from 1483–1666Mi and maxima from
1528–1718Mi. Proposed combined reservations round above these observations:
3584Mi on the server and 2048Mi on workers, before the eviction buffer.

CPU used non-idle, non-iowait, non-steal host CPU minus pod-container CPU, both
over five-minute rates. Server p99/max were 1.51/2.03 cores; worker p99 values
were 0.81–0.87 and maxima 1.07–1.71. Combined CPU reservations are 2 cores on
the server and 1 on workers, with bursting available.

These are conservative aggregate estimates, not exact per-daemon profiles.
They include accounting differences and omit peaks between samples. The
window spans scheduled k6 and backup periods, but does not prove every scrape
or every workload was observed. Grafana aggregates the process metric's node
label, so it cannot establish the historical OS/K3s split. The 512Mi/250m OS
share is a budgeting choice within each measured combined reservation. A live
kubelet summary corroborated greater K3s memory demand on the server, but is
only a snapshot. Revisit these budgets after K3s or workload changes.

Reproduce the estimates using `max_over_time` and `quantile_over_time(0.99, …)`
with `[7d:5m]` subqueries around:

```promql
max by (node) (node_memory_working_set_bytes{job="integrations/kubernetes/resources"})
- sum by (node) (container_memory_working_set_bytes{job="integrations/kubernetes/cadvisor",container!=""})
```

```promql
label_replace(
  sum by (instance) (rate(node_cpu_seconds_total{job="integrations/node_exporter",mode!~"idle|iowait|steal"}[5m])),
  "node", "$1", "instance", "(.*)"
)
- on (node) sum by (node) (rate(container_cpu_usage_seconds_total{job="integrations/kubernetes/cadvisor",container!=""}[5m]))
```

## Review and rollout

Review the profile file in Git. A host-specific `k3s_node_resource_profile`
can replace its role's `systemReserved` and `kubeReserved` maps; supply both
CPU and memory. Keep real host mappings in the ignored inventory. Only the
reservation fields are accepted. Set `k3s_node_name` where the Kubernetes name
differs from the system hostname.

After merge and approval for an Ansible maintenance execution, begin with a
single worker, using `--limit <worker-alias>` with `k3s/node-resources.yaml`.
Observe a complete scheduled k6 run, a backup, pod evictions, and node pressure
before approving the remaining workers and finally the server. Passing the
immediate checks alone does not establish long-term sizing. The single server
restart briefly interrupts API access.

The first execution is limited to one worker unless
`k3s_node_resources_canary_verified=true` is explicitly supplied. Set that
variable for subsequent batches only after the canary observation is complete.

The playbook refuses a profile that leaves no allocatable resources, exceeds
current pod requests or working-set memory, or crosses a current memory/disk/
inode threshold. It requires all nodes Ready, schedulable, and free of pressure.
Check the proposed values against other concurrent changes before running;
the preflight is a snapshot, not a scheduler lock. Use a quiet maintenance
window between load tests and backups.

On a changed drop-in, Ansible restarts only that host's K3s service. This is
not a node reboot or an application drain. It then checks the effective
`configz` values and the exact CPU/memory allocatable before continuing.
Unchanged files do not restart K3s. If the runtime fails to converge, the run
stops; later nodes are untouched. Inspect command-line overrides or later
drop-ins rather than bypassing verification. `--check` is refused because it
cannot verify the effective post-restart configuration.

Offline checks:

```sh
ansible-playbook k3s/node-resources.yaml -i inventory/hosts.example.ini --syntax-check
ansible-playbook k3s/node-resources.yaml -i inventory/hosts.example.ini --list-hosts
python3 -m unittest discover -s testing -p 'test_node_resources.py'
git diff --check
```

Rollback requires an approved maintenance execution: restore the previous
drop-in (Ansible creates a backup when replacing it), or remove this one file
if this was its initial installation, then restart that node's K3s service and
verify Ready and `configz`. A Git revert alone does not remove an already
installed file. Do not edit `00-k3s-defaults.conf` or remove unrelated drop-ins.
