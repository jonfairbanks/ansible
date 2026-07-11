# Raspberry Pi

`temps.yaml` collects temperatures from the `cluster` inventory group. It
expects `/home/jonfairbanks/scripts/temp.sh` to be available on each target.

Run it with:

```sh
ansible-playbook raspberry-pi/temps.yaml -K
```
