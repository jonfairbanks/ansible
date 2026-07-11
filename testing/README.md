# Testing

`stress-test.yaml` installs `sysbench`, runs a five-minute CPU test, and then
collects cluster temperatures. It targets the `k3s_cluster` inventory group and
installs the Raspberry Pi temperature script when it is missing.

Run it with:

```sh
ansible-playbook testing/stress-test.yaml
```
