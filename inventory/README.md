# Inventory

`hosts.ini` is intentionally ignored because it contains local infrastructure
details. Create it from the committed placeholder inventory:

```sh
cp inventory/hosts.example.ini inventory/hosts.ini
```

The `managed_hosts` group contains all managed systems. The template separates
that broader set from K3s cluster membership:

- `k3s_cluster` includes control-plane and worker hosts.
- `k3s_master` and `k3s_workers` select K3s installation roles; `k3s_workers`
  contains worker hosts only.

Ansible's implicit `all` group includes every host.

The repository's `ansible.cfg` selects this inventory automatically. Run a
playbook with the appropriate SSH user:

```sh
ansible-playbook system/updates.yaml
```

The example uses `StrictHostKeyChecking=accept-new`: SSH records a new host
key automatically, but still rejects a changed key.

## Passwordless Sudo

For a trusted automation account, configure passwordless sudo on each managed
host. On the managed host, edit a dedicated sudoers file:

```sh
sudo visudo -f /etc/sudoers.d/90-ansible-<ssh-user>
```

Add the following rule, substituting the SSH user:

```sudoers
<ssh-user> ALL=(ALL) NOPASSWD: ALL
```

Verify that sudo does not prompt for a password:

```sh
ssh <ssh-user>@<host-address> 'sudo -n true'
```

Afterward, playbooks that use privilege escalation do not need `-K`:

```sh
ansible-playbook system/set-timezone.yaml --limit <host-alias>
```

This grants the account full root access without a sudo prompt. Use it only
for a trusted account protected by SSH key authentication.

## SSH Key Authentication

Use an SSH key instead of storing a login password in the inventory. Create a
key only when one does not already exist:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519
```

Install its public key on a managed host using the existing login password:

```sh
ssh-copy-id -i ~/.ssh/id_ed25519.pub <ssh-user>@<host-address>
```

Verify that password authentication is no longer needed:

```sh
ssh -o PasswordAuthentication=no -i ~/.ssh/id_ed25519 <ssh-user>@<host-address>
```

Set `ansible_user` in the local ignored inventory. With the default
`~/.ssh/id_ed25519` key, Ansible discovers the key automatically:

```sh
ansible-playbook system/set-timezone.yaml --limit <host-alias>
```
