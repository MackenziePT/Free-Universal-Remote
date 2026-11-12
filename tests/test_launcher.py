import os
import unittest
from unittest.mock import patch
import launch_server


class LauncherTests(unittest.TestCase):
    def test_control_plane_api_key_not_inherited_by_mcp(self):
        with patch.dict(os.environ, {"CONTROL_PLANE_API_KEY": "dummy-not-a-real-key"}):
            with patch.object(launch_server.subprocess, "call", return_value=0) as call:
                self.assertEqual(launch_server.main(), 0)
                self.assertNotIn("CONTROL_PLANE_API_KEY", call.call_args.kwargs["env"])
                self.assertEqual(os.environ["CONTROL_PLANE_API_KEY"], "dummy-not-a-real-key")


if __name__ == '__main__':
    unittest.main()
