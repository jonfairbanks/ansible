# Raspberry Pi

`temps.yaml` collects temperatures from the `k3s_cluster` inventory group. It
installs [`pi-temps.sh`](https://github.com/jonfairbanks/scripts/blob/master/pi-temps/pi-temps.sh)
to `/usr/local/bin/pi-temps.sh` when the script is missing, then runs that copy.

Run it with:

```sh
ansible-playbook raspberry-pi/temps.yaml
```
