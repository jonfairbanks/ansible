# Examples

## `hello-world.yaml`

`hello-world.yaml` is a safe first-run playbook. It connects to the selected
host, runs Ansible's `ping` module, and prints a confirmation without changing
the remote system.

Run it against one host:

```sh
ansible-playbook examples/hello-world.yaml --limit <host-alias>
```
