"""Prepare an Inno Setup candidate that MUST use a genuine signing provider.

Does not sign, issue certificates, publish, or alter unsigned preview inputs.
The Inno SignTool integration is required so uninstallers and internal setup
copies also receive Authenticode signatures.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/"packaging"/"UniversalRemote-Preview.iss"
output=ROOT/"packaging"/"UniversalRemote-SIGNED-CANDIDATE.iss"
data=source.read_text(encoding="utf-8-sig")

patches={
    '#define Product "Universal Remote"':
      '#define Product "Universal Remote"\n#ifndef PublisherLegalName\n#error PublisherLegalName must be supplied by validated publisher identity\n#endif',
    'AppPublisher=Universal Remote Project (pré-visualização)':
      'AppPublisher={#PublisherLegalName}',
    'AppComments=Versão interna de desenvolvimento; não certificada para distribuição pública':
      'AppComments=Candidato assinado; nao publicar antes da certificacao externa',
    'OutputBaseFilename=UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED':
      'OutputBaseFilename=UniversalRemote-1.0.0-rc5.1-x64-SIGNED-CANDIDATE',
    'VersionInfoDescription=Universal Remote - Preview sem assinatura':
      'VersionInfoDescription=Universal Remote - Publisher signed candidate',
    'VersionInfoProductName=Universal Remote Preview':
      'VersionInfoProductName=Universal Remote',
    'Compression=lzma2/ultra64':
      'Compression=lzma2/ultra64\nSignTool=URPublisher\nSignedUninstaller=yes',
}
for old,new in patches.items():
    if data.count(old)!=1:
        raise RuntimeError("Ambiguous or missing candidate template marker: "+old)
    data=data.replace(old,new)
if "PREVIEW-UNSIGNED.exe" in data:
    raise RuntimeError("Signed candidate contains misleading unsigned target")
output.write_text(data,encoding="utf-8-sig")
print("SIGNED_CANDIDATE_TEMPLATE_CREATED",str(output))
print("REQUIRES verified CA publisher, ISCC -dPublisherLegalName and -sURPublisher.")
