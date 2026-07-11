# System Management

- `reboot.yaml`: Reboot hosts in the `cluster_nodes` inventory group.
- `set-static-ip.yaml`: Configure a static IPv4 address on Ubuntu through
  Netplan.
- `set-timezone.yaml`: Set all targeted hosts to `America/Los_Angeles`.
- `shutdown.yaml`: Shut down hosts in the `cluster_nodes` inventory group.
- `ulimit.yaml`: Configure process and file-descriptor limits on `testers`.
- `updates.yaml`: Apply Ubuntu package upgrades and reboot when required.

To set a static IPv4 address:

```sh
ansible-playbook system/set-static-ip.yaml -K \
  -e 'static_ip_address=192.168.4.50'
```

`set-static-ip.yaml` changes the active network connection. It discovers the
Ethernet interface carrying the host's current default IPv4 route; use console
access when changing the address of a remote machine. It uses `192.168.4.1` as
both the default gateway and DNS server, and applies a `/24` network prefix.
