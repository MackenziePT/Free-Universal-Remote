"""PowerShell transport must avoid command line quoting and emit UTF-8 output."""
import base64
import unittest
from unittest.mock import patch
import remote_core

class PowerShellTransportTests(unittest.TestCase):
    def test_windows_powershell_encodes_unicode_and_quotes(self):
        sample = 'Write-Output "á✅ \' exemplo"'
        with patch.object(remote_core.os, 'name', 'nt'), \
             patch('remote_core.shutil.which', return_value='pwsh.exe'), \
             patch('remote_core.run_limited_process', return_value={'exit_code': 0}) as run:
            remote_core._powershell(sample, 9)
        cmd=run.call_args.args[0]
        self.assertIn('-EncodedCommand',cmd)
        script=base64.b64decode(cmd[cmd.index('-EncodedCommand')+1]).decode('utf-16-le')
        self.assertIn(sample,script)
        self.assertIn('OutputEncoding',script)
        self.assertIn("'Stop'",script)

if __name__=='__main__': unittest.main()
