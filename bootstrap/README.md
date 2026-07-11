# Bootstrap

`first10seconds.yaml` performs initial Ubuntu host provisioning. It configures
an SSH key, installs common packages, Docker, Kubernetes tooling, firewall
rules, and then reboots if required.

Run it with:

```sh
ansible-playbook bootstrap/first10seconds.yaml -K
```
