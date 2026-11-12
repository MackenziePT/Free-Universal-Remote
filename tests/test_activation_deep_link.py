import unittest
from public_gui import activation_destination

class ActivationTests(unittest.TestCase):
    def test_one_paste_starts_guided_connection(self):
        self.assertEqual(activation_destination(["universal-remote://connect"]),"Conexões")
        self.assertEqual(activation_destination(["universal-remote://open"]),"Início")

    def test_default_entrypoint(self):
        self.assertEqual(activation_destination([]),"Início")

    def test_reject_untrusted_deep_link_arguments(self):
        invalid=(["universal-remote://connect?grant=all"],
                 ["universal-remote://connect/shell"],
                 ["universal-remote://other"],
                 ["https://somewhere.example/path"],
                 ["universal-remote://connect","extra"],
                 ["--no-consent"])
        for args in invalid:
            with self.subTest(args=args),self.assertRaises(ValueError):
                activation_destination(args)

if __name__=="__main__":
    unittest.main()
