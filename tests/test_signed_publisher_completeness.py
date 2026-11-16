"""Static release gates: every app EXE must be CA-signed and packaged.
This test runs on Linux CI too; no certificates or private keys are required.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
COMPONENTS=(
 "UniversalRemote-Preview",
 "UniversalRemoteAgent-Preview",
 "UniversalRemoteBridge-Preview",
 "UniversalRemoteUpdater-Preview",
 "UniversalRemoteTunnel-Preview",
)
class PublisherReleaseGateTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.sign=(ROOT/"tools"/"Invoke-IVReleaseSigning.ps1").read_text("utf-8-sig")
  cls.verify=(ROOT/"tools"/"Test-PublisherSignature.ps1").read_text("utf-8-sig")
  cls.iss=(ROOT/"packaging"/"UniversalRemote-SIGNED-CANDIDATE.iss").read_text("utf-8-sig")

 def test_all_five_executables_signed(self):
  match=re.search(r"\$names=@\((.*?)\)",self.sign,re.S)
  self.assertIsNotNone(match,"Sign script component inventory missing")
  self.assertEqual(set(re.findall(r"'(UniversalRemote[^']*-Preview)'",match.group(1))),set(COMPONENTS))
  self.assertIn("foreach($name in $names)",self.sign)

 def test_all_five_executables_verified(self):
  for name in COMPONENTS:
   self.assertIn(name+"\\",self.verify)
   self.assertIn(name+".exe",self.verify)
  self.assertIn("Get-AuthenticodeSignature",self.verify)
  self.assertIn("PUBLISHER_SIGNATURE_GATE_PASS",self.verify)
  self.assertIn("TimeStamperCertificate",self.verify)
  self.assertIn("SignerCertificate",self.verify)

 def test_signed_installer_includes_all_components(self):
  found=re.findall(r'^Source:\s*"\{#PackageRoot\}\\(UniversalRemote[^\\"]*-Preview)\\\*"',self.iss,re.M)
  self.assertEqual(set(found),set(COMPONENTS))
  self.assertEqual(len(found),len(COMPONENTS))
  self.assertIn("SignTool=URPublisher",self.iss)
  self.assertIn("SignedUninstaller=yes",self.iss)

 def test_ca_identity_is_mandatory_for_public_signing(self):
  self.assertIn("CA_ISSUED_IV_CERTIFICATE_MISSING",self.sign)
  self.assertIn("ConfirmIdentityValidated",self.sign)
  self.assertIn("ConfirmSecureKeyProvider",self.sign)
  self.assertIn("HasPrivateKey",self.sign)
  self.assertIn("X509Chain",self.sign)
  self.assertIn("PRODUCTION",self.sign)
  self.assertIn("embedded_keys",self.sign)
  self.assertIn("/fd SHA256",self.sign)
  self.assertIn("/td SHA256",self.sign)
  self.assertIn("Compression=zip/1",self.iss)
  self.assertIn("SolidCompression=no",self.iss)

if __name__=="__main__":
 unittest.main()
