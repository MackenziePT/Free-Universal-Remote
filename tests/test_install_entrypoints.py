"""Version gate and tunnel command fidelity without a key or network access."""
from contextlib import redirect_stderr, redirect_stdout
import io
import shlex
import unittest
from unittest.mock import patch

import initialize_tunnel
import install_check


class InstallEntrypointTests(unittest.TestCase):
    def test_unsupported_python_returns_error_without_importing_dependencies(self):
        with patch.object(install_check.sys, 'version_info', (3, 10)), \
                patch.object(install_check.importlib, 'import_module') as imports, \
                redirect_stderr(io.StringIO()):
            self.assertEqual(install_check.main(['--version-only']), 2)
            imports.assert_not_called()

    def test_version_gate_runs_without_installed_dependencies(self):
        with patch.object(install_check.importlib, 'import_module') as imports, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(install_check.main(['--version-only']), 0)
            imports.assert_not_called()

    def test_windows_paths_survive_tunnel_shell_style_parser(self):
        paths = [r"C:\Users\O'Neil\AppData\Local\HarmonyRemoteMCP\app\.venv\Scripts\python.exe",
                 r"C:\Users\O'Neil\Remote MCP (new)\launch_server.py"]
        self.assertEqual(shlex.split(initialize_tunnel.mcp_command(*paths)), paths)

    def test_invalid_id_never_launches_client(self):
        with patch.object(initialize_tunnel.subprocess, 'run') as run, \
                redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                initialize_tunnel.main(['--tunnel-id', 'invalid'])
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
