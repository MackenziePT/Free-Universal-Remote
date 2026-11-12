import json
import tempfile
import unittest
from pathlib import Path
from remote_core import PolicyError, load_config

class ConfigurationBoundaryTests(unittest.TestCase):
    def test_reject_scalar_roots_instead_of_array(self):
        with tempfile.TemporaryDirectory() as td:
            config=Path(td)/'config.json'
            config.write_text(json.dumps({'allowed_roots':td}))
            with self.assertRaises(PolicyError):
                load_config(config)

    def test_reject_relative_root_to_prevent_cwd_dependent_authority(self):
        with tempfile.TemporaryDirectory() as td:
            config=Path(td)/'config.json'
            config.write_text(json.dumps({'allowed_roots':['../projects']}))
            with self.assertRaises(PolicyError):
                load_config(config)

    def test_reject_empty_root_entry(self):
        with tempfile.TemporaryDirectory() as td:
            config=Path(td)/'config.json'
            config.write_text(json.dumps({'allowed_roots':['']}))
            with self.assertRaises(PolicyError):
                load_config(config)

if __name__ == '__main__':
    unittest.main()
