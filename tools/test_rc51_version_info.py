"""Check all five PE VERSIONINFO metadata resources before a future rebuild."""
from pathlib import Path
from tempfile import TemporaryDirectory
from PyInstaller.utils.win32.versioninfo import load_version_info_from_text_file
from rc51_windows_version import COMPONENTS, generate_version_file

def main():
    with TemporaryDirectory(prefix="urm-version-qa-") as tmp:
        for name in COMPONENTS:
            path = generate_version_file(name, Path(tmp) / (name + ".txt"))
            result = load_version_info_from_text_file(str(path))
            assert result is not None, name
            print("VERSIONINFO_PARSE_PASS", name)
if __name__ == "__main__":
    main()
