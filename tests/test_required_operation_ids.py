"""Protocol contract: privileged MCP tools advertise operation_id as required."""
import ast
import unittest
from pathlib import Path

class OperationIdSchemaTests(unittest.TestCase):
    def test_operation_id_is_required_at_tool_schema_level(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'server.py').read_text())
        functions={n.name:n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for name in ('write_text_file','run_powershell','desktop_action'):
            with self.subTest(name=name):
                fn=functions[name]
                args=fn.args.posonlyargs + fn.args.args
                required=len(args)-len(fn.args.defaults)
                id_pos=next(i for i,a in enumerate(args) if a.arg=='operation_id')
                self.assertLess(id_pos,required,'operation_id must not be an optional tool argument')

if __name__=='__main__': unittest.main()
