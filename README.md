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

The repository inventory at `inventory/hosts.ini` includes the managed target
`192.168.4.18` and is selected by `ansible.cfg` when running from this
repository. Provide its SSH user with `-u` when running a playbook.

Run a playbook:

```
ansible-playbook testing/stress-test.yaml -K
```

For example, target the managed host with:

```sh
ansible-playbook testing/stress-test.yaml -u <ssh-user> -K
```

Run a command ad-hoc

```
ansible all -m shell -a 'echo $TERM'
```

Install an app as a particular user:

```
ansible all -m apt -a "name=apache2-utils state=present" -u $USER --become -K
```
