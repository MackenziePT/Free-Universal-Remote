"""Red-green checks for at-most-once dispatch of powerful remote actions."""
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
import remote_core as core


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'allowed'
        root.mkdir()
        state = Path(self.tmp.name) / 'state'
        state.mkdir()
        self.cfg = core.Config(allowed_roots=(root,), enable_shell=True, enable_input=True,
                               grants_path=state / 'grants.json')
        self.cfg.grants_path.write_text(json.dumps({'expires_at':core.time.time()+600,
                                                    'capabilities':['shell','input']}))

    def test_shell_same_operation_never_executes_twice(self):
        ident = str(uuid.uuid4())
        with patch.object(core, '_powershell', return_value={'exit_code':0}) as execute:
            result = core.powershell(self.cfg, 'Write-Output works', operation_id=ident)
            self.assertEqual(result['exit_code'], 0)
            with self.assertRaises(core.PolicyError):
                core.powershell(self.cfg, 'Write-Output works', operation_id=ident)
            execute.assert_called_once()
        status = core.operation_status(self.cfg, ident)
        self.assertEqual(status['state'], 'completed')
        self.assertNotIn('Write-Output', json.dumps(status))

    def test_different_command_cannot_reuse_operation_id(self):
        ident = str(uuid.uuid4())
        with patch.object(core, '_powershell', return_value={'exit_code':0}) as execute:
            core.powershell(self.cfg, '1', operation_id=ident)
            with self.assertRaises(core.PolicyError):
                core.powershell(self.cfg, '2', operation_id=ident)
            execute.assert_called_once()

    def test_crash_after_claim_does_not_execute_again(self):
        ident = str(uuid.uuid4())
        with patch.object(core, '_powershell', side_effect=RuntimeError('crash')) as execute:
            with self.assertRaises(RuntimeError):
                core.powershell(self.cfg, '1', operation_id=ident)
            with self.assertRaises(core.PolicyError):
                core.powershell(self.cfg, '1', operation_id=ident)
            execute.assert_called_once()
        self.assertEqual(core.operation_status(self.cfg, ident)['state'], 'uncertain')

    def test_invalid_operation_id_prevents_execution(self):
        with patch.object(core, '_powershell') as execute:
            for value in ('', '../danger', '1234', 'not-a-uuid'):
                with self.assertRaises(core.PolicyError):
                    core.powershell(self.cfg, '1', operation_id=value)
            execute.assert_not_called()

    def test_untrusted_operation_ids_cannot_escape_state(self):
        with self.assertRaises(core.PolicyError):
            core.operation_status(self.cfg, '../outside')

if __name__ == '__main__': unittest.main()
