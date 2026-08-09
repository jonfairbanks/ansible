# Bootstrap

`first10seconds.yaml` provisions Debian-family hosts in parallel by default. It
updates packages, installs baseline tools, Docker, kubectl, NVM with the current
Node LTS, Fail2ban, and UFW. It supports x86_64 and aarch64 hosts. SSH key setup
remains an inventory prerequisite. NVM is installed through its pinned official
install/update script, then installs and selects the latest Node.js LTS release.

Install the required Ansible collections once:

```sh
ansible-galaxy collection install -r requirements.yml
```

Run it against one host:

```sh
ansible-playbook bootstrap/first10seconds.yaml --limit <host-alias>
```

For a rolling bootstrap, process one host at a time:

```sh
ansible-playbook bootstrap/first10seconds.yaml -e 'bootstrap_batch_size=1'
```

To reboot the selected host when package updates require it:

```sh
ansible-playbook bootstrap/first10seconds.yaml --limit <host-alias> \
  -e 'reboot_if_required=true'
```

With automatic reboots enabled, every host in the active batch can reboot at
the same time. Use `bootstrap_batch_size=1` for a rolling reboot.

The playbook targets `managed_hosts` by default and accepts a `target_hosts`
override. It allows rate-limited SSH plus TCP ports 80 and 443 through UFW.
Docker-published ports are managed by the Docker workload configuration rather
than additional Docker-specific firewall rules.
