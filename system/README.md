# System Management

- `reboot.yaml`: Reboot K3s worker hosts in the `k3s_workers` inventory group
  by default; accepts an explicit target override.
- `set-static-ip.yaml`: Configure a static IPv4 address on Ubuntu through
  Netplan.
- `set-timezone.yaml`: Set all targeted hosts to `America/Los_Angeles`.
- `shutdown.yaml`: Shut down K3s worker hosts in the `k3s_workers` inventory group.
- `system-info.yaml`: Display the Ubuntu system-information summary for selected hosts.
- `ulimit.yaml`: Configure process and file-descriptor limits on `managed_hosts`.
- `uptime.yaml`: Display the uptime of selected managed hosts.
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

The playbook schedules power-off one minute later by default, allowing Ansible
to confirm the request before SSH closes. Change the delay when needed:

```sh
ansible-playbook system/shutdown.yaml \
  -e 'target_hosts=control_plane shutdown_delay_minutes=5'
```

To cancel a scheduled shutdown on the host before it runs:

```sh
sudo shutdown -c
```

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

## Show Uptime

`uptime.yaml` is read-only and targets `managed_hosts` by default.

```sh
ansible-playbook system/uptime.yaml --limit <host-alias>
```

To select a host or group explicitly:

```sh
ansible-playbook system/uptime.yaml -e 'target_hosts=<host-alias-or-group>'
```

## Show System Information

`system-info.yaml` displays the Ubuntu system summary, including load,
temperature, disk, process, memory, swap, logged-in user, and default-interface
IPv4 information. It is read-only, runs in parallel by default, and targets
`managed_hosts` by default.

```sh
ansible-playbook system/system-info.yaml --limit <host-alias>
```

It requires the `landscape-sysinfo` utility supplied by Ubuntu's
`landscape-common` package. To select a host or group explicitly:

```sh
ansible-playbook system/system-info.yaml \
  -e 'target_hosts=<host-alias-or-group>'
```

## Apply Updates

`updates.yaml` applies Debian-family package upgrades to `managed_hosts` one
host at a time and stops the play on failure. It reports a required reboot but
does not reboot by default.

```sh
ansible-playbook system/updates.yaml --limit <host-alias>
```

To target a host or group outside `managed_hosts`, override `target_hosts`:

```sh
ansible-playbook system/updates.yaml -e 'target_hosts=<host-alias-or-group>'
```

To update a larger batch at a time, override `update_batch_size`:

```sh
ansible-playbook system/updates.yaml -e 'update_batch_size=2'
```

To apply updates and reboot the selected host when required:

```sh
ansible-playbook system/updates.yaml --limit <host-alias> \
  -e 'reboot_if_required=true'
```

With automatic reboots enabled, every host in the active batch can reboot at
the same time. Keep the default batch size of one for a rolling reboot.
