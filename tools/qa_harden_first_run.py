"""Fix pre-public Windows path validation and atomic first-run publish."""
from pathlib import Path
r=Path(__file__).resolve().parents[1]
p=r/"public_paths.py"
s=p.read_text(encoding="utf-8")
s=s.replace("import os\nfrom pathlib import Path","import os\nimport re\nfrom pathlib import Path")
s=s.replace('''    from remote_core import PolicyError, _is_link_or_junction''','''    from remote_core import PolicyError, _is_link_or_junction, validate_windows_path''')
old='''    original=Path(folder).expanduser()
    if not original.is_absolute():
        raise ValueError("The permitted folder must be absolute")
    if str(original).startswith(("\\\\\\\\","//")):
        raise ValueError("Network shares are not enabled in this preview")
    directory=original.resolve()
    if str(directory)==directory.anchor:
        raise ValueError("The entire Windows drive cannot be shared")
    home=product_home()
    if home == directory or home.is_relative_to(directory):
        raise ValueError("The permitted root must not contain Universal Remote private state")
    current=directory
    while current != current.parent:
        if current.exists() and _is_link_or_junction(current):
            raise PolicyError("Links and junctions in selected folders are unsupported")
        current=current.parent'''
new='''    original=Path(folder).expanduser()
    if not original.is_absolute():
        raise ValueError("A pasta tem de ter um caminho absoluto.")
    if str(original).startswith(("\\\\\\\\","//")):
        raise ValueError("Esta versão não permite partilhar pastas de rede.")
    if os.name == "nt":
        # Validate the original lexical path BEFORE resolve() can hide a reparse
        # point or strip an invalid Windows suffix/reserved DOS name.
        validate_windows_path(str(original))
    current=original
    while True:
        if current.exists() and _is_link_or_junction(current):
            raise PolicyError("Não é permitido selecionar pastas com atalhos NTFS ou junctions.")
        if current==current.parent:
            break
        current=current.parent
    directory=original.resolve()
    if str(directory)==directory.anchor:
        raise ValueError("Não é permitido partilhar o disco inteiro.")
    home=product_home()
    if home == directory or home.is_relative_to(directory):
        raise ValueError("A pasta de trabalho não pode conter os dados privados da aplicação.")'''
assert old in s, "Source config segment changed"
s=s.replace(old,new)
start=s.index('    created=False\n    try:')
end=s.index('    return target',start)
replacement='''    try:
        # Validate the staging file BEFORE making anything visible. The same-
        # volume NTFS hardlink is an atomic no-clobber publish; open("x") would
        # expose a partially written config to a competing application.
        load_config(candidate)
        os.link(candidate,target)
    finally:
        candidate.unlink(missing_ok=True)
'''
s=s[:start]+replacement+s[end:]
p.write_text(s,encoding="utf-8",newline="\n")
q=r/"tests"/"test_public_distribution.py"
t=q.read_text(encoding="utf-8")
old='''        original_open=Path.open
        competitor=b"R"*len(contents.encode("utf-8"))
        def concurrent_create(path,*args,**kwargs):
            if path==target and args and args[0]=="x":
                target.write_bytes(competitor)
                raise FileExistsError("Concurrent configuration was created")
            return original_open(path,*args,**kwargs)
        with patch.object(Path,"open",new=concurrent_create):'''
new='''        competitor=b"R"*len(contents.encode("utf-8"))
        def concurrent_create(src,dst,*args,**kwargs):
            if Path(dst)==target:
                target.write_bytes(competitor)
                raise FileExistsError("Concurrent configuration was created")
            raise AssertionError("Unexpected hardlink operation")
        with patch("public_paths.os.link",side_effect=concurrent_create):'''
assert old in t
q.write_text(t.replace(old,new),encoding="utf-8",newline="\n")
print("FIRST_RUN_ATOMIC_AND_PATH_VALIDATION_PATCHED")
