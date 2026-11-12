"""Select newest usable global/private pwsh using signed install policy + Windows version metadata."""
from pathlib import Path
r=Path(__file__).resolve().parents[1]
p=r/"remote_core.py"
s=p.read_text(encoding="utf-8")
start=s.index("def _powershell(command: str, timeout: int) -> dict[str, Any]:")
end=s.index("\n\ndef diagnostic(",start)
code=r'''def _windows_executable_version(executable: str | Path) -> tuple[int, int, int] | None:
    """Read Windows FileVersionInfo without spawning a shell or downloading anything."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        version = ctypes.WinDLL("version", use_last_error=True)
        version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
        version.GetFileVersionInfoW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
        version.GetFileVersionInfoW.restype = wintypes.BOOL
        version.VerQueryValueW.argtypes = [
            ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.UINT)]
        version.VerQueryValueW.restype = wintypes.BOOL
        handle = wintypes.DWORD()
        size = version.GetFileVersionInfoSizeW(str(executable), ctypes.byref(handle))
        if size <= 0:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(str(executable), 0, size, buffer):
            return None
        block, length = ctypes.c_void_p(), wintypes.UINT()
        if not version.VerQueryValueW(buffer, "\\", ctypes.byref(block), ctypes.byref(length)):
            return None
        if length.value < 16:
            return None
        fixed = ctypes.cast(block, ctypes.POINTER(wintypes.DWORD))
        if fixed[0] != 0xFEEF04BD:
            return None
        major, minor, patch = fixed[2] >> 16, fixed[2] & 0xFFFF, fixed[3] >> 16
        return int(major), int(minor), int(patch)
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def _powershell(command: str, timeout: int) -> dict[str, Any]:
    if os.name != "nt":
        raise OSError("PowerShell diagnostics are Windows-only")

    # The updater validates Microsoft's signature/digest before installing private
    # runtimes. Prefer the highest version, rather than a stale global PATH entry.
    choices: list[tuple[tuple[int, int, int], str]] = []
    global_shell = shutil.which("pwsh.exe")
    if global_shell:
        global_version = _windows_executable_version(global_shell)
        if global_version is not None and global_version[0] >= 7:
            choices.append((global_version, global_shell))
        else:
            # Retain legacy behavior for a user-provided shell with no version
            # metadata, but never rank it above a verified private installation.
            choices.append(((0, 0, 0), global_shell))

    programs = os.environ.get("ProgramFiles", "")
    if programs:
        standard = Path(programs) / "PowerShell" / "7" / "pwsh.exe"
        if standard.is_file() and not _is_link_or_junction(standard):
            found = _windows_executable_version(standard)
            if found and found[0] >= 7:
                choices.append((found, str(standard)))

    state = Path(os.environ.get("LOCALAPPDATA", "")) / "UniversalRemote" / "runtime" / "powershell"
    if state.is_dir() and not _is_link_or_junction(state):
        for folder in state.iterdir():
            candidate = folder / "pwsh.exe"
            if not (folder.is_dir() and not _is_link_or_junction(folder)
                    and candidate.is_file() and not _is_link_or_junction(candidate)):
                continue
            try:
                version_parts = tuple(int(x) for x in folder.name.split("-", 1)[0].split("."))
                if len(version_parts) != 3 or version_parts[0] < 7:
                    continue
                file_version = _windows_executable_version(candidate)
                if file_version is not None and file_version != version_parts:
                    continue
                choices.append((version_parts, str(candidate)))
            except (ValueError, OSError):
                continue

    if not choices:
        raise FileNotFoundError(
            "PowerShell moderno indisponível. Abre Conexões para obter a versão estável mais recente.")
    executable = max(choices)[1]
    return run_limited_process(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive",
         "-EncodedCommand", powershell_encoded_command(command)], timeout)
'''
p.write_text(s[:start]+code+s[end:],encoding="utf-8",newline="\n")
print("POWER_SHELL_ENGINE_SELECTS_NEWEST_USABLE_RUNTIME")
