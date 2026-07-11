# Docker Workloads

- `factorio-install.yaml`: Install Docker and run a Factorio server.
- `factorio-update.yaml`: Recreate the Factorio container.
- `rancher-install.yaml`: Install Docker and run Rancher.

All current Docker playbooks target the `managed_hosts` inventory group.

## `factorio-install.yaml`

```sh
ansible-playbook docker/factorio-install.yaml --limit <host-alias>
```

## `factorio-update.yaml`

```sh
ansible-playbook docker/factorio-update.yaml --limit <host-alias>
```

## `rancher-install.yaml`

```sh
ansible-playbook docker/rancher-install.yaml --limit <host-alias>
```
