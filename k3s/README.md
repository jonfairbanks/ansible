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

### Version pinning and upgrades

The server and every worker use the exact release in `k3s/versions.yaml`:

```yaml
k3s_version: v1.36.3+k3s1
```

The playbook passes this value to the official installer as
`INSTALL_K3S_VERSION`, verifies the installed binary afterward, and only reruns
the installer when a node does not match the pin. To upgrade, review the K3s
release notes and Kubernetes version-skew requirements, change this single
value in a pull request, and then run the playbook after it merges. The server
is reconciled first; workers are upgraded and verified Ready one at a time.

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

## Traefik Dashboard

`k3s.yaml` can expose a Basic Auth-protected Traefik dashboard at
`http://traefik.home.arpa/dashboard/`, but the route is disabled by default.
K3s's bundled Traefik chart already enables the internal dashboard; when
enabled, the playbook creates the route and a credential Secret only when one
does not already exist, so reruns do not replace the password. On Debian or
Ubuntu K3s nodes, the opt-in path installs `apache2-utils` to create the bcrypt
password hash.

Enable it explicitly:

```sh
ansible-playbook k3s/k3s.yaml \
  -e 'traefik_dashboard_enabled=true'
```

To display the generated password during a trusted interactive bootstrap, opt
in explicitly. Do not use this option in CI or retained logs.

```sh
ansible-playbook k3s/k3s.yaml \
  -e 'traefik_dashboard_enabled=true' \
  -e 'traefik_dashboard_display_initial_credentials=true'
```

Set a known initial password instead of generating one:

```sh
ansible-playbook k3s/k3s.yaml \
  -e 'traefik_dashboard_enabled=true' \
  -e 'traefik_dashboard_password=replace-with-a-strong-password'
```

Change the hostname or skip dashboard bootstrap when needed:

```sh
ansible-playbook k3s/k3s.yaml \
  -e 'traefik_dashboard_hostname=traefik.example.internal'

ansible-playbook k3s/k3s.yaml \
  -e 'traefik_dashboard_enabled=false'
```

Setting `traefik_dashboard_enabled=false` does not delete a route that was
previously created; remove that route explicitly if you no longer want to
expose the dashboard.

The route uses the HTTP `web` entry point to match the existing local ingress
pattern. Basic Auth protects access but does not encrypt the password in
transit; move it to HTTPS before using it beyond a trusted local network.

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
server. It uses K3s's bundled `kubectl`, pins the Argo CD release, creates a
Traefik Ingress for `argocd.home.arpa`, and waits for the API server and
application controller to be ready.

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

Override the published hostname for a different local DNS name:

```sh
ansible-playbook k3s/argocd.yaml \
  -e 'argocd_hostname=argocd.example.internal'
```

The Ingress follows the existing homelab HTTP pattern and uses HTTPS for its
connection to Argo CD. Argo CD's upstream self-signed backend certificate is
accepted only by Traefik for that in-cluster connection. For a temporary
local-only session instead, use:

```sh
sudo k3s kubectl -n argocd port-forward service/argocd-server 8080:443
```

The initial username is `admin`. To display the generated initial password at
the end of a trusted interactive playbook run, opt in explicitly. This writes
the password to the Ansible output, so do not use it in CI or retained logs.

```sh
ansible-playbook k3s/argocd.yaml \
  -e 'argocd_display_initial_credentials=true'
```

The initial-password Secret may be removed after the first successful login.
To retrieve it directly before then, use a trusted terminal:

```sh
sudo k3s kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 --decode; echo
```

## `longhorn.yaml`

`longhorn.yaml` installs the host prerequisites on every Debian-family K3s node.
The Longhorn Argo CD Application and its Helm values live in the separate
`cluster-state` repository, which is the source of truth for cluster workloads.

Install the host prerequisites before merging the Longhorn `cluster-state` PR:

```sh
ansible-playbook k3s/longhorn.yaml
```

Do not add Longhorn manifests to this repository or apply them directly: Argo CD
reconciles them from `cluster-state`. Longhorn's UI remains unexposed until an
authenticated ingress design is added.
