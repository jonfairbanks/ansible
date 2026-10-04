# BlinkStick K3s Monitor

Optional host service for a BlinkStick Nano connected to a K3s server. The
playbook targets `k3s_master` and defaults to `blink_kube_enabled: false`.
A disabled run makes no host changes. It does not stop an existing installation.

## Install

Reconcile the `blink-kube` namespace, service account, and node-list RBAC from
cluster-state first. Then run from the Ansible repository on the selected host:

```sh
ansible-playbook k3s/blink-kube.yaml --limit k0 -e blink_kube_enabled=true
```

Blink source is pinned to `4da82087127661ffc1751a2931bf1c2d6157dbda`.
`blink_kube_revision`, `blink_kube_uv_version` (0.11.16), and
`blink_kube_python_version` (3.13) can be changed explicitly. uv installs managed
Python and `uv sync --locked --no-dev` installs the repository's locked dependencies.
The host needs internet access to GitHub, PyPI, and Python release downloads.
No enclosure files are installed.

## Access and Credentials

The `blink-kube` user has no login shell. Its root-owned code and runtime live
under `/opt/blink-kube`. A udev rule grants its group access only to USB devices
with VID `20a0` and PID `41e5`; it does not grant general USB access.
The monitor's systemd device filter permits USB bus devices while filesystem
permissions narrow access to the matching device.

A root-only helper uses the existing K3s admin kubeconfig to mint a one-hour
service-account token every 20 minutes. It atomically writes group-readable
credential files under `/etc/blink-kube`, with the JWT's actual expiry. The
monitor receives only the API endpoint, CA, and a node-reader credential.
It cannot read the admin kubeconfig or modify its credentials or executable.
No permanent service-account token Secret is created.

The Kubernetes Python client loads the kubeconfig's ExecCredential via
`/usr/bin/cat`. Its expiry hook reruns that command when the cached token nears
expiry, so rotation does not require a monitor restart. See the
[client's loader and refresh hook](https://github.com/kubernetes-client/python/blob/v36.0.3/kubernetes/base/config/kube_config.py).
`PrivateTmp` provides writable storage for the client's temporary CA file.
If refresh fails for long enough, the monitor reports API failure until recovery.

## Verify and Roll Back

```sh
sudo systemctl status blink-kube.service blink-kube-credentials.timer
sudo journalctl -u blink-kube.service -u blink-kube-credentials.service --since '10 minutes ago'
```

Verify the LED, USB reconnect recovery, and a successful refresh after the timer
fires. Avoid printing `/etc/blink-kube/credential.json` or the admin kubeconfig.
To stop the installation, disable both units explicitly:

```sh
sudo systemctl disable --now blink-kube.service blink-kube-credentials.timer
```

This leaves files and the dedicated account available for a later restart.
Removing GitOps RBAC revokes the monitor's node access.
