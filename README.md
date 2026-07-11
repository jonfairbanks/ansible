# Ansible Playbooks

## Playbooks

- [Bootstrap](bootstrap/README.md)
- [Docker workloads](docker/README.md)
- [Inventory](inventory/README.md)
- [K3s cluster setup](k3s/README.md)
- [Raspberry Pi](raspberry-pi/README.md)
- [System management](system/README.md)
- [Testing](testing/README.md)

## Usage

The repository selects the local, ignored `inventory/hosts.ini` through
`ansible.cfg`. Create it from `inventory/hosts.example.ini` and provide its SSH
user with `-u` when running a playbook.

Run a playbook:

```
ansible-playbook testing/stress-test.yaml
```

For example, target the managed host with:

```sh
ansible-playbook testing/stress-test.yaml
```

Run a command ad-hoc

```
ansible all -m shell -a 'echo $TERM'
```

Install an app as a particular user:

```
ansible managed_hosts -m apt -a "name=apache2-utils state=present" --become
```
