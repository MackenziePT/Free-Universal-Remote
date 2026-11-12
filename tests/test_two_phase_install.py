"""The Windows source publish process must not execute the staged Python itself."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class TwoPhaseContract(unittest.TestCase):
    def test_installer_preparation_is_out_of_process(self):
        s=(ROOT/'scripts'/'Install.ps1').read_text()
        self.assertIn('Start-Process -FilePath $HostExe',s)
        self.assertIn('-PassThru -Wait',s)
        self.assertIn(r"'scripts\Prepare-Stage.ps1'",s)
        self.assertLess(s.index('Start-Process -FilePath $HostExe'),s.index('Move-AtomicDirectory -From $Stage -To $Destination'))
    def test_staging_has_all_three_gates(self):
        s=(ROOT/'scripts'/'Prepare-Stage.ps1').read_text()
        for text in ('-m pip install','-m unittest discover','smoke_test.py','install_check.py'):
            self.assertIn(text,s)
