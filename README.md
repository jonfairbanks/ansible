# Ansible Playbooks

## Playbooks

- [Bootstrap](bootstrap/README.md)
- [Docker workloads](docker/README.md)
- [Examples](examples/README.md)
- [Inventory setup](inventory/README.md)
- [K3s cluster setup](k3s/README.md)
- [Raspberry Pi](raspberry-pi/README.md)
- [System management](system/README.md)
- [Testing](testing/README.md)

## Usage

The repository selects the local, ignored `inventory/hosts.ini` through
`ansible.cfg`. Create it from `inventory/hosts.example.ini`, then set host
addresses, group membership, and `ansible_user` locally.

Run a playbook:

```sh
ansible-playbook examples/hello-world.yaml --limit <host-alias>
```

To target one host explicitly:

```sh
ansible-playbook examples/hello-world.yaml --limit <host-alias>
```

## Passwordless SSH

Use SSH keys for managed hosts rather than storing login passwords in the
inventory. Create a key only when one does not already exist:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519
```

Install the public key using the existing host password:

```sh
ssh-copy-id -i ~/.ssh/id_ed25519.pub <ssh-user>@<host-address>
```

Verify key-only access before using Ansible:

```sh
ssh -o PasswordAuthentication=no -i ~/.ssh/id_ed25519 <ssh-user>@<host-address>
ansible <host-alias> -m ping
```

The full inventory, SSH host-key, and passwordless-sudo guidance is in the
[inventory setup guide](inventory/README.md).

Run a command ad-hoc

```
ansible all -m shell -a 'echo $TERM'
```

Install an app as a particular user:

```
ansible managed_hosts -m apt -a "name=apache2-utils state=present" --become
```
