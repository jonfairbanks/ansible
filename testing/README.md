# Testing

`stress-test.yaml` installs `sysbench`, runs a five-minute CPU test, and then
collects cluster temperatures. It targets the `k3s_cluster` inventory group and
expects `/home/jonfairbanks/scripts/temp.sh` to be available on each target.

Run it with:

```sh
ansible-playbook testing/stress-test.yaml
```
