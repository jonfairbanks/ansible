# Docker Workloads

- `factorio-install.yaml`: Install Docker and run a Factorio server.
- `factorio-update.yaml`: Recreate the Factorio container.
- `rancher-install.yaml`: Install Docker and run Rancher.

All Docker playbooks target `managed_hosts` by default and accept a
`target_hosts` override. They check for Docker first and run Docker's official
convenience installer only when the engine is missing. Existing Docker engines
are not upgraded by these playbooks.

The shared setup adds the configured Ansible user to the `docker` group. Open a
new SSH session before using Docker directly without `sudo`.

Install the required Ansible collections before running Docker playbooks:

```sh
ansible-galaxy collection install -r requirements.yml
```

Docker-published ports can require workload-specific firewall handling; the
bootstrap UFW baseline does not add Docker-specific filtering rules.

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
