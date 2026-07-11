# System Management

- `reboot.yaml`: Reboot K3s worker hosts in the `k3s_workers` inventory group
  by default; accepts an explicit target override.
- `set-static-ip.yaml`: Configure a static IPv4 address on Ubuntu through
  Netplan.
- `set-timezone.yaml`: Set all targeted hosts to `America/Los_Angeles`.
- `shutdown.yaml`: Shut down K3s worker hosts in the `k3s_workers` inventory group.
- `ulimit.yaml`: Configure process and file-descriptor limits on `managed_hosts`.
- `updates.yaml`: Apply Ubuntu package upgrades and reboot when required.

## Reboot Hosts

By default, `reboot.yaml` reboots the `k3s_workers` group only. This excludes
control-plane hosts:

```sh
ansible-playbook system/reboot.yaml
```

To reboot a specific host outside that group intentionally, override
`target_hosts`:

```sh
ansible-playbook system/reboot.yaml -e 'target_hosts=control_plane'
```

The playbook waits for each selected host to return, then reports its uptime.

## Shut Down Hosts

By default, `shutdown.yaml` shuts down the `k3s_workers` group only. To shut
down a specific host outside that group intentionally, override `target_hosts`:

```sh
ansible-playbook system/shutdown.yaml -e 'target_hosts=control_plane'
```

The playbook returns after it dispatches the non-blocking power-off request;
the host is expected to become unavailable afterward.

## Static IP Address

To set a static IPv4 address:

```sh
ansible-playbook system/set-static-ip.yaml \
  --limit <host-alias> \
  -e 'static_ip_address=192.0.2.50'
```

`set-static-ip.yaml` changes the active network connection. It discovers the
Ethernet interface carrying the host's current default IPv4 route; use console
access when changing the address of a remote machine. It applies a `/24`
network prefix and uses the gateway and DNS settings defined in the playbook.

## Set Timezone

`set-timezone.yaml` sets selected hosts to `America/Los_Angeles`.

```sh
ansible-playbook system/set-timezone.yaml --limit <host-alias>
```

## Configure Limits

`ulimit.yaml` configures process and file-descriptor limits on managed hosts.

```sh
ansible-playbook system/ulimit.yaml --limit <host-alias>
```

## Apply Updates

`updates.yaml` applies Ubuntu package upgrades and reboots when required.

```sh
ansible-playbook system/updates.yaml --limit <host-alias>
```
