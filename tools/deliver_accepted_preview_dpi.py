"""Promote only acceptance-tested unsigned previews into a single delivery folder."""
from __future__ import annotations
import hashlib, json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"evidence"/"qa"
DEST=ROOT.parent/"Universal-Remote-Preview-v1.0.0-rc5.1"
EXE=QA/"installer-build"/"UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe"
ZIP=QA/"portable-release-dpi"/"UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED-LATEST.zip"
ACCEPTANCE=QA/"installer-e2e-results.json"
EVIDENCE=QA/"portable-release-dpi"/"RELEASE-EVIDENCE.json"
KNOWN_OLD_INSTALLER={"2fa0e9ef7672e7c989f530cebaf59bcccc562746a32e9231a7c19beb3725adee","9842d94e902cf5bc0182ffc1ac13f9751a3301f8c248eeafa6a5a6e116b89df4","2cfefefb69572462c72d521f7f222068adf82db82299cdee698c6267d7973f74"}
KNOWN_OLD_ZIP={"9b47fc89b2a848e31bf7b95111439a2ae316414ef35a1874abe0b9c8c19c02c7","bf1d51fb762c13d8f182698306ac978a5eb231032187a3aa20524077785bf995","25cdf34fc11a62a860664551f1981fb8784e1a53f93f384e93c767cd560a3c45"}
def sha(path:Path)->str:
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def main():
    assert DEST.is_dir(),"Existing delivery folder unavailable"
    report=json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    proof=json.loads(EVIDENCE.read_text(encoding="utf-8"))
    mandatory=[
        report.get("installed_files_present"),report.get("unconfigured_denied"),
        report.get("gui_six_pages"),report.get("agent_stdio_tools")==27,
        report.get("repair_preserved_personal_config"),report.get("uninstaller_exit")==0,
        report.get("uninstaller_removed_exe"),
        report.get("user_private_state_preserved_on_uninstall"),
    ]
    assert all(mandatory),"Installer acceptance has not passed"
    assert sha(EXE)==report["package_sha256"]==proof["installer_sha256"],"Installer hash mismatch"
    assert sha(ZIP)==proof["portable_zip_sha256"],"Portable ZIP hash mismatch"
    for src,oldhashes in ((EXE,KNOWN_OLD_INSTALLER),(ZIP,KNOWN_OLD_ZIP)):
        target=DEST/src.name
        if target.exists() and sha(target)!=sha(src) and sha(target) not in oldhashes:
            raise RuntimeError("Existing file modified: "+str(target))
    for src in (EXE,ZIP):
        dest=DEST/src.name
        shutil.copy2(src,dest)
        assert sha(dest)==sha(src),"Copied file mismatch"
    for src,dest in (
        (QA/"certification-gates.md",DEST/"certification-gates.md"),
        (ROOT/"docs"/"POWERSHELL_LATEST_POLICY.md",DEST/"POWERSHELL_LATEST_POLICY.md"),
        (EVIDENCE,DEST/"RELEASE-EVIDENCE.json")
    ):
        assert src.is_file(),src
        shutil.copy2(src,dest)
    obsolete=DEST/"UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED-AUTO.zip"
    if obsolete.exists():
        if sha(obsolete) in KNOWN_OLD_ZIP:obsolete.unlink()
        else:print("OLD_ZIP_PRESERVED_UNEXPECTED_HASH",str(obsolete))
    readme=(
        "# Universal Remote RC5.1 - Windows x64 (pré-visualização)\n\n"
        "**Este instalador ainda não tem assinatura de editor nem certificação pública.**\n\n"
        "Para instalar, abre o ficheiro EXE desta pasta e segue os cinco passos. "
        "Não precisas de instalar Python, pip, Git ou Visual C++.\n\n"
        "A opção de verificar a versão estável mais recente do PowerShell vem "
        "selecionada, mas pode ser desmarcada. A aplicação consulta a versão oficial "
        "nesse momento, incluindo futuras versões principais. Só descarrega quando "
        "é necessário, verificando SHA-256 e assinatura Microsoft, sem alterar "
        "o PowerShell global do Windows.\n\n"
        "Para a versão portátil, extrai o ZIP com o sufixo LATEST e executa "
        "GUI\\UniversalRemote-Preview.exe.\n\n"
        "As 27 ferramentas MCP funcionam localmente. O emparelhamento remoto "
        "público ainda não está incluído e as operações privilegiadas começam "
        "desativadas. A RC5.0 instalada no ASUS não é modificada.\n\n"
        "Consultar POWERSHELL_LATEST_POLICY.md, certification-gates.md e "
        "SHA256SUMS.txt para verificações e limitações.\n"
    )
    (DEST/"LEIA-PRIMEIRO.md").write_text(readme,encoding="utf-8")
    hashes="\n".join(sha(f)+"  "+f.name for f in (EXE,ZIP))+"\n"
    (DEST/"SHA256SUMS.txt").write_text(hashes,encoding="utf-8")
    assert "pré-visualização" in (DEST/"LEIA-PRIMEIRO.md").read_text(encoding="utf-8")
    assert sha(DEST/EXE.name)==sha(EXE) and sha(DEST/ZIP.name)==sha(ZIP)
    print("FINAL_DELIVERY_VERIFIED",json.dumps({
        "installer":str(DEST/EXE.name),"installer_sha256":sha(EXE),
        "portable":str(DEST/ZIP.name),"portable_sha256":sha(ZIP),
        "readme_utf8":True,"installer_e2e":True,
        "status":"UNSIGNED PRIVATE PREVIEW, NOT PUBLIC RELEASE"
    },ensure_ascii=False))

if __name__=="__main__": main()
