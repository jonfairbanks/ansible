"""Local tests use synthetic tokens and never contact a Kubernetes API."""
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('refresh', Path(__file__).parents[1] / 'files/refresh-credentials.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


def token(expiry):
    payload = base64.urlsafe_b64encode(json.dumps({'exp': expiry}).encode()).decode().rstrip('=')
    return 'synthetic.' + payload + '.signature'


class CredentialsTest(unittest.TestCase):
    def test_expiry_comes_from_issued_token(self):
        value = refresh.credential(token(int(time.time()) + 3600))
        self.assertEqual(value['kind'], 'ExecCredential')
        self.assertTrue(value['status']['expirationTimestamp'].endswith('Z'))
        self.assertIn('synthetic.', value['status']['token'])

    def test_short_lifetime_is_rejected(self):
        with self.assertRaises(ValueError):
            refresh.credential(token(int(time.time()) + 60))

    def test_atomic_replace_permissions_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'credential.json'
            path.write_text('old')
            with patch.object(refresh.os, 'fchown') as chown:
                refresh.atomic_write(path, {'test': 'new'}, 123)
            chown.assert_called_once()
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            self.assertEqual(json.loads(path.read_text()), {'test': 'new'})
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_failed_replace_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'credential.json'
            path.write_text('old')
            with patch.object(refresh.os, 'fchown'), patch.object(refresh.os, 'replace', side_effect=OSError):
                with self.assertRaises(OSError):
                    refresh.atomic_write(path, {'test': 'new'}, 123)
            self.assertEqual(path.read_text(), 'old')
            self.assertEqual(list(Path(directory).iterdir()), [path])


if __name__ == '__main__':
    unittest.main()
