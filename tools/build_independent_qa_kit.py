"""Private unsigned QA kit for an owner-authorized second Windows computer.

Does NOT publish, install anything, disable security software or include
credentials, source checkout, personal logs, signing keys or machine IDs.
"""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"evidence"/"qa"
installer=QA/"installer-build"/"UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe"
script=ROOT/"tools"/"Check-Independent-Windows-PC.ps1"
destination=ROOT.parent/"Universal-Remote-Preview-v1.0.0-rc5.1"
if not destination.exists() or not destination.is_dir():
    raise FileNotFoundError("Existing preview folder is not present; no new top-level folders created")
if not installer.is_file() or not script.is_file():
    raise FileNotFoundError("Required QA artifact missing")
with installer.open("rb") as fd:
    digest=hashlib.file_digest(fd,"sha256").hexdigest()
readme=f"""UNIVERSAL REMOTE RC5.1 - INTERNAL WINDOWS x64 QA ONLY

ATENCAO: ESTA PREVIEW NAO TEM ASSINATURA AUTHENTICODE DE EDITOR.
NÃO DESTINADA A DISTRIBUICAO PUBLICA. NUNCA DESATIVAR O ANTIVIRUS OU SMARTSCREEN.
Nao carregar credenciais, arquivos privados nem dados pessoais nos relatórios.

INSTALADOR: {installer.name}
SHA256 ESPERADO: {digest}

1) Copia este ZIP apenas para outro PC Windows x64 sob a autorizacao do seu dono.
2) Extrai-o para uma pasta tua de teste. Verifica a origem e hash acima por canal separado.
3) Antes de instalar, abre PowerShell normal no diretorio extraido e executa:
   .\\Check-Independent-Windows-PC.ps1 -Installer .\\{installer.name} -ExpectedSHA256 '{digest}'
   Se a tua politica de execucao impedir executar o script, NAO a desatives.
4) Verifica manualmente o nome, a origem e o aviso de 'editor desconhecido'.
   O utilizador decide se autoriza esta preview privada ou termina o teste.
5) Se autorizares, executa o instalador manualmente e completa o assistente.
   Não concedas permissoes de shell, input ou ecrã por defeito.
6) Executa de novo o mesmo script adicionando:
   -InstallDir "$env:LOCALAPPDATA\\Programs\\UniversalRemote"
   (ou o caminho de instalacao escolhido)
7) Verifica o resultado em Independent-PC-QA-Result.json.
   Envia apenas esse JSON revisto pelo utilizador, sem arquivos privados.
8) Testa reparacao e desinstalacao manualmente e anota qualquer bloqueio.
   Nao uses Windows ARM64 para declarar compatibilidade ARM nativa: o ZIP e x64.

ESTADO: executavel nao assinado; piloto interno, nao certificado.
Faltam assinatura de editor legitima, instalacao em segundo PC, Windows App Certification
Kit adequado, verificacoes de seguranca e a matriz Windows x64/ARM64.
""";
summary={
 "product":"Universal Remote",
 "version":"1.0.0-rc5.1-dev",
 "scope":"PRIVATE_WINDOWS_X64_QA",
 "signed":False,
 "publisher_verified":False,
 "certified":False,
 "installer":installer.name,
 "installer_sha256":digest,
 "installer_bytes":installer.stat().st_size,
 "tested_on_other_PCs":False
}
out=destination/"UniversalRemote-rc5.1-x64-PRIVATE-QA-UNSIGNED.zip"
with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
    z.write(installer,installer.name)
    z.write(script,script.name)
    z.writestr("LEIA-PRIMEIRO-QA-EXTERNO.txt",readme)
    z.writestr("QA-MANIFEST.json",json.dumps(summary,indent=2,ensure_ascii=False))
    z.writestr("SHA256SUMS.txt",f"{digest}  {installer.name}\n")
with out.open("rb") as f:
    zhash=hashlib.file_digest(f,"sha256").hexdigest()
print(json.dumps({"qa_zip":str(out),"qa_zip_bytes":out.stat().st_size,
                  "qa_zip_sha256":zhash,"installer_sha256":digest,
                  "signature":"unsigned","certified":False},indent=2,ensure_ascii=False))
