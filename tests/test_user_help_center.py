import unittest
from dataclasses import dataclass

from help_center import (MESSAGES, diagnose, friendly_text, guidance,
                         issue_for_exception, safe_diagnostic_report)

@dataclass
class Check:
    key: str
    ok: bool

class HelpCenterTests(unittest.TestCase):
    def test_missing_runtime_explains_repair_without_security_bypass(self):
        r = diagnose([Check("runtime", False),Check("agent", True),Check("config", True)],True)
        self.assertEqual(r[0].code,"INSTALL_INCOMPLETE")
        self.assertIn("Reparar",friendly_text(r[0]))

    def test_missing_agent_has_concrete_steps(self):
        r=diagnose([Check("runtime",True),Check("agent",False),Check("config",True)],False)
        self.assertEqual(r[0].code,"AGENT_MISSING")

    def test_no_configuration_guides_onboarding(self):
        r=diagnose([Check("runtime",True),Check("agent",True),Check("config",False)],True)
        self.assertEqual(r[0].code,"SETUP_INCOMPLETE")

    def test_local_ready_does_not_claim_remote_connected(self):
        r=diagnose([Check("runtime",True),Check("agent",True),Check("config",True)],True)
        self.assertEqual(tuple(x.code for x in r),("LOCAL_OK","REMOTE_UNVERIFIED"))
        self.assertIn("não significa",friendly_text(r[1]))

    def test_all_catalog_messages_have_actionable_steps(self):
        for item in MESSAGES.values():
            with self.subTest(code=item.code):
                self.assertGreaterEqual(len(item.steps),2)
                self.assertIn("O que fazer",friendly_text(item))
                self.assertIn(item.severity,("error","warning","info"))

    def test_exceptions_are_sanitized(self):
        private="C:\\Users\\alice\\Desktop\\secret-key.pem token=123"
        error=RuntimeError(private)
        item=issue_for_exception(error)
        output=friendly_text(item)+safe_diagnostic_report([item])
        self.assertNotIn("alice",output)
        self.assertNotIn("secret-key",output)
        self.assertNotIn("123",output)

    def test_context_specific_guidance(self):
        for context,code in (("startup","STARTUP_FAILED"),("powershell","OPTIONAL_POWERSHELL"),
                             ("pairing","PAIRING_FAILED"),("task","TASK_FAILED"),
                             ("update","UPDATE_FAILED")):
            with self.subTest(context=context):
                self.assertEqual(issue_for_exception(Exception("untrusted"),context=context).code,code)

    def test_permissions_do_not_advise_disabling_protection(self):
        item=issue_for_exception(PermissionError("deny"))
        self.assertEqual(item.code,"PERMISSION_DENIED")
        self.assertIn("Não desatives",friendly_text(item))

if __name__=="__main__":
    unittest.main()
