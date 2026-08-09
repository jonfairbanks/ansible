# K3s Cluster Setup

`k3s.yaml` installs a single K3s master and joins one or more worker nodes.
It requires one host in the `k3s_master` group and any number of hosts in the
`k3s_workers` group.

## Prepare the inventory

The repository uses the top-level local inventory. From the repository root,
copy the safe template:

```sh
cp inventory/hosts.example.ini inventory/hosts.ini
```

Replace the example addresses, set the SSH user as appropriate, define the
`k3s_master` and `k3s_workers` roles, and keep `k3s_server_url` pointed at the
server's reachable Kubernetes API address. The local inventory is ignored by
Git. The host running Ansible must be able to reach every node over SSH, and
worker nodes must be able to reach the server on TCP port 6443.

## Cluster Token

On first installation, the playbook generates a random K3s token and K3s
persists its authoritative node token at
`/var/lib/rancher/k3s/server/node-token` on the server. The token is never
written to the controller inventory or documentation.

When adding a worker later, add it to the local `k3s_workers` inventory group and
rerun `k3s.yaml`. The playbook reads the server token in memory and uses it to
join the new worker.

## Kubeconfig Output

After the master API is ready, `k3s.yaml` writes its admin kubeconfig to
`~/.kube/config` on the Ansible controller. It replaces the master loopback
endpoint with `k3s_server_url`, sets mode `0600`, and creates a backup before
overwriting an existing config.

The exported file grants cluster-admin access. Keep it private and use it with:

```sh
kubectl get nodes
```

## `k3s.yaml`

```sh
ansible-playbook k3s/k3s.yaml
```

After an agent joins, the playbook applies the standard
`node-role.kubernetes.io/worker` label so `kubectl get nodes` displays its
`worker` role. By default, it uses the worker's system hostname. Set
`k3s_node_name` for a worker when its Kubernetes node name differs.

The playbook also configures the bundled Traefik controller as a DaemonSet and
uses `externalTrafficPolicy: Local`. This preserves client source addresses for
Ingress workloads while ensuring every K3s node receiving ServiceLB traffic has
a local Traefik endpoint.

To label existing workers without rerunning installation tasks:

```sh
ansible-playbook k3s/k3s.yaml --tags node-labels
```

For an additional API certificate name, such as a load balancer DNS name, pass
it when installing the server:

```sh
ansible-playbook k3s/k3s.yaml \
  -e 'k3s_server_extra_args=--tls-san=k3s.example.internal'
```

## `firewall.yaml`

`firewall.yaml` adds the K3s inter-node UFW rules without enabling UFW or
changing its default policy. Run the bootstrap playbook first when the host
needs the baseline UFW policy.

```sh
ansible-playbook k3s/firewall.yaml
```

The default `vxlan` backend allows TCP 6443 to servers, TCP 10250 between
nodes, and UDP 8472 between nodes. For a WireGuard-native Flannel backend:

```sh
ansible-playbook k3s/firewall.yaml \
  -e 'k3s_flannel_backend=wireguard-native'
```

To permit `kubectl` access from the Ansible controller or another trusted
client network, define `k3s_api_allowed_sources` in the ignored local
inventory, then rerun the firewall playbook:

```ini
[k3s:vars]
k3s_api_allowed_sources=["192.0.2.0/24"]
```

Replace the example subnet with the trusted client's LAN subnet. Keep local
network addresses out of the committed example inventory.

## `argocd.yaml`

`argocd.yaml` installs the official multi-tenant Argo CD manifest on the K3s
server. It uses K3s's bundled `kubectl`, pins the Argo CD release, and waits
for the API server and application controller to be ready.

```sh
ansible-playbook k3s/argocd.yaml
```

The default `standard` profile is the upstream non-HA manifest. For a cluster
with the capacity for the upstream HA deployment, select it explicitly:

```sh
ansible-playbook k3s/argocd.yaml \
  -e 'argocd_install_profile=ha'
```

The default release is `v3.4.2`. Keep releases pinned and pass a supported
patch release when upgrading:

```sh
ansible-playbook k3s/argocd.yaml \
  -e 'argocd_version=v3.4.2'
```

The service remains cluster-internal by default. To open the UI locally from
the K3s server, use:

```sh
sudo k3s kubectl -n argocd port-forward service/argocd-server 8080:443
```

Retrieve the initial `admin` password only from a trusted terminal:

```sh
sudo k3s kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 --decode; echo
```
