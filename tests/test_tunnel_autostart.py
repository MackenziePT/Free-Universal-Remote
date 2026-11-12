import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import winreg
import tunnel_manager as module

class _RegistryKey:
    def __enter__(self):return self
    def __exit__(self,*a):return False

@unittest.skipUnless(os.name=="nt","Windows-only registry")
class StartupPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="ur-startup-preference-")
        self.addCleanup(self.tmp.cleanup)
        self.exe=Path(self.tmp.name)/"UniversalRemoteTunnel-Preview.exe"
        self.exe.write_bytes(b"test-only fake executable")

    def test_explicit_enable_writes_only_hkcu(self):
        with patch.object(winreg,"CreateKeyEx",return_value=_RegistryKey()) as open_key, \
             patch.object(winreg,"QueryValueEx",side_effect=FileNotFoundError), \
             patch.object(winreg,"SetValueEx") as set_value, \
             patch.object(winreg,"DeleteValue") as delete:
            module.set_autostart(self.exe,True)
        open_key.assert_called_once()
        self.assertEqual(open_key.call_args.args[0],winreg.HKEY_CURRENT_USER)
        self.assertEqual(set_value.call_args.args[1],module.RUN_ENTRY)
        self.assertIn(str(self.exe),set_value.call_args.args[-1])
        delete.assert_not_called()

    def test_mismatched_existing_run_entry_never_overwritten(self):
        with patch.object(winreg,"CreateKeyEx",return_value=_RegistryKey()), \
             patch.object(winreg,"QueryValueEx",return_value=('"unrelated.exe" run',winreg.REG_SZ)), \
             patch.object(winreg,"SetValueEx") as set_value:
            with self.assertRaises(module.TunnelConfigError):
                module.set_autostart(self.exe,True)
        set_value.assert_not_called()

    def test_disabled_without_existing_value_makes_no_changes(self):
        with patch.object(winreg,"CreateKeyEx",return_value=_RegistryKey()), \
             patch.object(winreg,"QueryValueEx",side_effect=FileNotFoundError), \
             patch.object(winreg,"SetValueEx") as set_value, \
             patch.object(winreg,"DeleteValue") as delete:
            module.set_autostart(self.exe,False)
        set_value.assert_not_called()
        delete.assert_not_called()
