import tempfile
import unittest
from pathlib import Path
from remote_core import Config, PolicyError, read_text


class TextFidelityTests(unittest.TestCase):
    def test_split_utf8_codepoint_is_rejected_not_silently_corrupted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            file = root/'utf8.txt'
            file.write_text('áB', encoding='utf-8')
            cfg = Config(allowed_roots=(root.resolve(),))
            with self.assertRaises(PolicyError):
                read_text(cfg, str(file), offset=0, max_bytes=1)
            self.assertEqual(read_text(cfg, str(file), offset=0, max_bytes=2)['text'], 'á')

    def test_invalid_utf8_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            file = root/'ansi.txt'
            file.write_bytes(b'\xff')
            cfg = Config(allowed_roots=(root.resolve(),))
            with self.assertRaises(PolicyError):
                read_text(cfg, str(file))

if __name__ == '__main__':
    unittest.main()
