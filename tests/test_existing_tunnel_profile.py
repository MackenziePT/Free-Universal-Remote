"""No accidental profile replacement or extra user prompts on a repeat setup."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
import initialize_tunnel

TUNNEL = 'tunnel_' + 'a' * 32
OTHER = 'tunnel_' + 'b' * 32

class ExistingTunnelProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.profile = self.home/'.config'/'tunnel-client'/'harmony-remote.yaml'
        self.profile.parent.mkdir(parents=True)

    def write_profile(self, tunnel=TUNNEL, *, key_ref='env:CONTROL_PLANE_API_KEY'):
        content = (f'config_version: 1\ncontrol_plane:\n  tunnel_id: "{tunnel}"\n'
                   f'  api_key: "{key_ref}"\nmcp:\n  commands:\n'
                   '    - channel: main\n      command: "launch_server.py"\n')
        self.profile.write_text(content, encoding='utf-8')

    def test_matching_profile_is_reused_without_running_init(self):
        self.write_profile()
        with patch.object(initialize_tunnel.Path, 'home', return_value=self.home), \
             patch.object(initialize_tunnel.subprocess, 'run') as run, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(initialize_tunnel.main(['--tunnel-id', TUNNEL]), 0)
        run.assert_not_called()

    def test_other_tunnel_is_refused_without_overwrite(self):
        self.write_profile(OTHER)
        before = self.profile.read_bytes()
        with patch.object(initialize_tunnel.Path, 'home', return_value=self.home), \
             patch.object(initialize_tunnel.subprocess, 'run') as run:
            with self.assertRaises(SystemExit):
                initialize_tunnel.main(['--tunnel-id', TUNNEL])
        self.assertEqual(before, self.profile.read_bytes())
        run.assert_not_called()

    def test_plaintext_key_profile_is_refused(self):
        self.write_profile(key_ref='sk-PRIVATE-KEY')
        with patch.object(initialize_tunnel.Path, 'home', return_value=self.home), \
             patch.object(initialize_tunnel.subprocess, 'run') as run:
            with self.assertRaises(SystemExit):
                initialize_tunnel.main(['--tunnel-id', TUNNEL])
        run.assert_not_called()
