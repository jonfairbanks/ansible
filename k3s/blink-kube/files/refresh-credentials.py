#!/usr/bin/python3
"""Mint a short-lived node-reader credential without exposing admin credentials."""
import base64
import datetime
import grp
import json
import os
from pathlib import Path
import subprocess
import tempfile

DIRECTORY = Path('/etc/blink-kube')
KUBECTL = ['/usr/local/bin/k3s', 'kubectl', '--kubeconfig=/etc/rancher/k3s/k3s.yaml']


def atomic_write(path, value, gid):
    fd, temporary = tempfile.mkstemp(prefix='.refresh-', dir=path.parent)
    try:
        os.fchmod(fd, 0o640)
        os.fchown(fd, 0, gid)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def credential(token):
    payload = token.split('.')[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
    expiry = datetime.datetime.fromtimestamp(claims['exp'], datetime.timezone.utc)
    if expiry <= datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=25):
        raise ValueError('Token lifetime is too short for the refresh interval')
    return {'apiVersion': 'client.authentication.k8s.io/v1beta1', 'kind': 'ExecCredential',
            'status': {'token': token, 'expirationTimestamp': expiry.isoformat().replace('+00:00', 'Z')}}


def main():
    gid = grp.getgrnam('blink-kube').gr_gid
    # Keep subprocess output captured. Never print token or admin kubeconfig data.
    admin = json.loads(subprocess.check_output(KUBECTL + ['config', 'view', '--raw', '--minify', '-o', 'json'], timeout=30))
    cluster = admin['clusters'][0]['cluster']
    ca = cluster['certificate-authority-data']
    server = cluster['server']
    token = subprocess.check_output(KUBECTL + ['-n', 'blink-kube', 'create', 'token', 'blink-kube', '--duration=1h'], text=True, timeout=30).strip()
    config = {'apiVersion': 'v1', 'kind': 'Config', 'current-context': 'blink-kube',
              'clusters': [{'name': 'k3s', 'cluster': {'server': server, 'certificate-authority-data': ca}}],
              'contexts': [{'name': 'blink-kube', 'context': {'cluster': 'k3s', 'user': 'blink-kube'}}],
              'users': [{'name': 'blink-kube', 'user': {'exec': {'apiVersion': 'client.authentication.k8s.io/v1beta1',
                         'command': '/usr/bin/cat', 'args': [str(DIRECTORY / 'credential.json')], 'interactiveMode': 'Never'}}}]}
    atomic_write(DIRECTORY / 'credential.json', credential(token), gid)
    atomic_write(DIRECTORY / 'kubeconfig', config, gid)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Blink credential refresh failed; check K3s and the blink-kube service account') from None
