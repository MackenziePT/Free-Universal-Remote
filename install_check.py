"""Installer preflight, executed as a file to support Windows PowerShell 5.1.

Do not embed Python source in native ``-c`` arguments: the legacy PowerShell
argument binder removes embedded quote characters.
"""
import argparse
import importlib
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version-only', action='store_true')
    options = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        print('Python 3.11+ required', file=sys.stderr)
        return 2
    if options.version_only:
        print('Python version OK (' + sys.version.split()[0] + ')')
        return 0
    for name in ('mcp', 'psutil', 'mss', 'PIL', 'pyautogui'):
        importlib.import_module(name)
    from remote_core import load_config
    load_config()
    print('Policy and imports OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
