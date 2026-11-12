import unittest
from universal_remote_ui import UniversalRemoteApp

class TunnelGuiIntegrationTests(unittest.TestCase):
    def test_connections_offers_guided_secure_tunnel_setup(self):
        self.assertTrue(callable(getattr(UniversalRemoteApp,"_open_tunnel_setup",None)),
                        "Connections view must expose a guided local setup window")

if __name__=="__main__":
    unittest.main()
