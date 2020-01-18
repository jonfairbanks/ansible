# Ansible Playbooks

Setup host groups:
```
(sudo) vi /etc/ansible/hosts
```

Run a playbook:
```
ansible-playbook /ansible/stress-test.yaml -K
```

Run a command ad-hoc
```
ansible all -m shell -a 'echo $TERM'
```

Install an app as a particular user:
```
ansible all -m apt -a "name=apache2-utils state=present" -u $USER --become -K
```