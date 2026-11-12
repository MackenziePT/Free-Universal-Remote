import unittest
from dataclasses import dataclass
from guided_steps import build_steps, next_action, completed_local_count

@dataclass
class Check:
    key: str
    ok: bool

class GuidedStepsTests(unittest.TestCase):
    def checks(self, runtime=True,agent=True,config=True):
        return [Check("runtime",runtime),Check("agent",agent),Check("config",config)]

    def test_healthy_local_never_claims_remote_connected(self):
        stages=build_steps(self.checks(),True,engine_health="READY")
        self.assertEqual([s.state for s in stages],["done","done","pending","pending"])
        self.assertEqual(next_action(stages).number,3)
        self.assertEqual(completed_local_count(stages),2)

    def test_missing_binary_recommends_safe_help(self):
        stages=build_steps(self.checks(runtime=False),True,engine_health="READY")
        self.assertEqual(next_action(stages).destination,"Ajuda")
        self.assertEqual(completed_local_count(stages),1)

    def test_missing_configuration_prioritized_after_runtime(self):
        stages=build_steps(self.checks(config=False),True,engine_health="READY")
        self.assertEqual(next_action(stages).number,2)

    def test_missing_agent_is_not_ready(self):
        stages=build_steps(self.checks(),False,engine_health="READY")
        self.assertEqual(stages[0].state,"action")

    def test_all_guidance_has_simple_next_action(self):
        stages=build_steps(self.checks(),True,engine_health="READY")
        self.assertEqual(len(stages),4)
        for item in stages:
            self.assertTrue(item.title and item.summary and item.button)
            self.assertIn(item.destination,{"Ajuda","Conexões","Acesso"})
            self.assertNotIn(item.state,{"connected","remote_verified"})

    def test_no_unverified_local_health_is_ever_marked_ready(self):
        stages=build_steps(self.checks(),True)
        self.assertEqual(stages[0].state,"pending")
        self.assertEqual(completed_local_count(stages),1)
        self.assertEqual(next_action(stages).number,1)

    def test_runtime_failure_comes_before_remote_connection(self):
        stages=build_steps(self.checks(),True,engine_health="BLOCKED")
        self.assertEqual(stages[0].state,"action")
        self.assertEqual(next_action(stages).number,1)

    def test_no_optional_power_shell_dependency(self):
        stages=build_steps(self.checks(),True,engine_health="READY")
        self.assertEqual(stages[0].state,"done")
        self.assertNotIn("PowerShell",next_action(stages).summary)

if __name__=="__main__":
    unittest.main()
