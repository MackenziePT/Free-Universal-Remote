"""Generate Windows VERSIONINFO for unsigned development EXEs.

CompanyName follows AppPublisher in packaging/UniversalRemote-Preview.iss.
No signature or verified publisher identity is implied.
"""
from pathlib import Path

COMPANY = "Universal Remote Project (pré-visualização)"
VERSION = "1.0.0-rc5.1-dev"
FILE_VERSION = (1, 0, 0, 51)
COMPONENTS = {
    "UniversalRemote-Preview": "Universal Remote desktop interface",
    "UniversalRemoteAgent-Preview": "Universal Remote MCP agent",
    "UniversalRemoteBridge-Preview": "Universal Remote private tunnel bridge",
    "UniversalRemoteTunnel-Preview": "Universal Remote tunnel manager",
    "UniversalRemoteUpdater-Preview": "Universal Remote verified update worker",
}


def generate_version_file(name: str, destination: Path) -> Path:
    if name not in COMPONENTS:
        raise ValueError("Unknown version resource component")
    # repr() creates safe, quoted Python literals for PyInstaller's parser.
    strings = {
        "CompanyName": COMPANY,
        "FileDescription": COMPONENTS[name] + " (unsigned internal preview)",
        "FileVersion": VERSION,
        "InternalName": name,
        "OriginalFilename": name + ".exe",
        "ProductName": "Universal Remote",
        "ProductVersion": VERSION,
        "LegalCopyright": "Copyright 2026 Universal Remote Project",
    }
    text = (
        "# Auto-generated for PyInstaller; internal preview, not Authenticode.\n"
        "VSVersionInfo(\n"
        "ffi=FixedFileInfo(filevers=(1,0,0,51), prodvers=(1,0,0,51), "
        "mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)),\n"
        "kids=[StringFileInfo([StringTable('040904B0', [\n"
        + "".join(f"StringStruct({key!r}, {value!r}),\n" for key, value in strings.items())
        + "])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]\n"
        ")\n"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return destination
