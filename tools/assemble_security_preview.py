"""Deliver a new *unsigned* self-contained internal security preview without overwriting the live agent."""
from __future__ import annotations

from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent
QA=ROOT/"evidence"/"qa"
BUNDLE=QA/"public-portable-prototype"
INSTALLER=QA/"installer-build"/"UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe"
ACCEPT=QA/"installer-e2e-results.json"
OUTPUT=BASE/"Universal-Remote-Preview-RC5.1-Security-20261111"
NAME="UniversalRemote-RC5.1-SECURITY-TEST-UNSIGNED"
FOLDER=OUTPUT/NAME
ZIP=OUTPUT/(NAME+".zip")
SETUP=OUTPUT/(NAME+".exe")


def sha(path:Path)->str:
    with path.open("rb") as fd:
        return hashlib.file_digest(fd,"sha256").hexdigest()


def main():
    if not INSTALLER.is_file():
        raise FileNotFoundError("Installer build missing")
    acceptance=json.loads(ACCEPT.read_text(encoding="utf-8"))
    if (not acceptance.get("security_updater_present")
        or acceptance.get("uninstaller_exit")!=0
        or not acceptance.get("user_private_state_preserved_on_uninstall")
        or acceptance.get("agent_stdio_tools")!=27
        or acceptance.get("package_sha256")!=sha(INSTALLER)):
        raise RuntimeError("Installer E2E acceptance is not current/complete")
    if OUTPUT.exists():
        raise FileExistsError("Refusing to overwrite previous deliverable")
    OUTPUT.mkdir()
    try:
        FOLDER.mkdir()
        for source,dest in (
            ("UniversalRemote-Preview","GUI"),
            ("UniversalRemoteAgent-Preview","Agent"),
            ("UniversalRemoteUpdater-Preview","Updater")
        ):
            b=BUNDLE/source
            if not (b/(source+".exe")).is_file():
                raise FileNotFoundError("Missing build: "+source)
            shutil.copytree(b,FOLDER/dest)
        scripts=FOLDER/"scripts"
        scripts.mkdir()
        for name in ("Test-Independent-PC.ps1","Resolve-PowerShell.ps1","Prepare-PowerShell.ps1"):
            shutil.copy2(ROOT/"scripts"/name,scripts/name)
        docs=FOLDER/"docs"
        docs.mkdir()
        for name in ("RC51_SECURITY_HARDENING_2026-11-11.md","PUBLIC_RELEASE_GATES.md",
                     "PUBLIC_SECURITY_MODEL.md"):
            shutil.copy2(ROOT/"docs"/name,docs/name)
        note=(
            "# Universal Remote — RC5.1 Security Preview (11/11/2026)\n\n"
            "**Só para testes privados. Este EXE NÃO está assinado por um editor "
            "e NÃO é uma release pública certificada.**\n\n"
            "Instalador: abre o ficheiro EXE nesta pasta e segue o assistente. "
            "Não é necessário Python pré-instalado.\n\n"
            "Portátil: extrai o ZIP completo, executa GUI\\UniversalRemote-Preview.exe. "
            "Para o teste de outro PC, abre PowerShell na pasta extraída e executa "
            "scripts\\Test-Independent-PC.ps1 (não concede permissões).\n\n"
            "Agente MCP local por defeito: 27 ferramentas. Modo de emparelhamento "
            "individual com assinatura e revogação: Agent\\UniversalRemoteAgent-Preview.exe "
            "--paired, requer configuração local e confirmação de dispositivos. "
            "Não configura automaticamente nenhum túnel, porta ou conta remota.\n\n"
            "O atualizador está em Updater\\UniversalRemoteUpdater-Preview.exe e "
            "verifica manifestos Ed25519 de um editor previamente confiado. "
            "Nenhuma chave de editor de produção é fornecida nesta preview; "
            "não executar atualizações desconhecidas.\n\n"
            "A RC5.0 instalada e ligada ao ChatGPT permanece intocada. "
            "Para teste público ainda faltam Authenticode, consentimento forte "
            "(Windows Hello), outros PCs e revisão de segurança independente.\n"
        )
        (FOLDER/"LEIA-PRIMEIRO.md").write_text(note,encoding="utf-8")
        files=sorted(f for f in FOLDER.rglob("*") if f.is_file())
        checks=[{"name":f.relative_to(FOLDER).as_posix(),"sha256":sha(f),"bytes":f.stat().st_size}
                for f in files]
        (FOLDER/"SHA256SUMS.txt").write_text(
            "\n".join(f'{f["sha256"]}  {f["name"]}' for f in checks)+"\n",encoding="utf-8")
        with zipfile.ZipFile(ZIP,"x",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for file in sorted(FOLDER.rglob("*")):
                if file.is_file():
                    z.write(file, NAME+"/"+file.relative_to(FOLDER).as_posix())
        with zipfile.ZipFile(ZIP) as z:
            if z.testzip() is not None:
                raise RuntimeError("CRC failure")
            if not any(s.endswith("/Updater/UniversalRemoteUpdater-Preview.exe") for s in z.namelist()):
                raise RuntimeError("Updater omitted from portable package")
        shutil.copy2(INSTALLER,SETUP)
        result={
            "kind":"internal-unsigned-test-preview",
            "created_at_utc":datetime.now(timezone.utc).isoformat(),
            "installer_sha256":sha(SETUP),
            "zip_sha256":sha(ZIP),
            "zip_bytes":ZIP.stat().st_size,
            "installer_bytes":SETUP.stat().st_size,
            "portable_files":len(checks),
            "local_installer_e2e":True,
            "publisher_signature":False,
            "external_pc_tests":False,
            "live_new_pairing_test":False,
            "do_not_publish":True}
        (OUTPUT/"RELEASE-EVIDENCE.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        (OUTPUT/"LEIA-PRIMEIRO.md").write_text(note,encoding="utf-8")
        (OUTPUT/"SHA256SUMS.txt").write_text(
            sha(SETUP)+"  "+SETUP.name+"\n"+sha(ZIP)+"  "+ZIP.name+"\n",encoding="utf-8")
        print("SECURITY_PREVIEW_DELIVERED",json.dumps(result,ensure_ascii=False),flush=True)
        print("PREVIEW_FOLDER",str(OUTPUT),flush=True)
    except BaseException:
        shutil.rmtree(OUTPUT,ignore_errors=True)
        raise


if __name__=="__main__":
    main()
