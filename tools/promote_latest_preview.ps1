$ErrorActionPreference='Stop'
$project=Split-Path -Parent $PSScriptRoot
$root=Split-Path -Parent $project
$dest=Join-Path $root 'Universal-Remote-Preview-v1.0.0-rc5.1'
$qa=Join-Path $project 'evidence\qa'
$installer=Join-Path $qa 'installer-build\UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe'
$zip=Join-Path $qa 'portable-release-latest\UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED-LATEST.zip'
$matrix=Join-Path $qa 'certification-gates.md'
$policy=Join-Path $project 'docs\POWERSHELL_LATEST_POLICY.md'
$evidence=Join-Path $qa 'portable-release-latest\RELEASE-EVIDENCE.json'
function HashHex([string]$file) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try {
        $st=[IO.File]::OpenRead($file)
        try {return ([BitConverter]::ToString($sha.ComputeHash($st))).Replace('-','').ToLowerInvariant()}
        finally {$st.Dispose()}
    } finally {$sha.Dispose()}
}
$expectedExe='9842d94e902cf5bc0182ffc1ac13f9751a3301f8c248eeafa6a5a6e116b89df4'
$expectedZip='bf1d51fb762c13d8f182698306ac978a5eb231032187a3aa20524077785bf995'
if(-not(Test-Path -LiteralPath $dest -PathType Container)){throw 'Delivery folder unavailable'}
foreach($item in @($installer,$zip,$matrix,$policy,$evidence)){
    if(-not(Test-Path -LiteralPath $item -PathType Leaf)){throw ('Missing '+$item)}
}
if((HashHex $installer) -cne $expectedExe -or (HashHex $zip) -cne $expectedZip){
    throw 'Source hash mismatched; delivery aborted'
}
$outExe=Join-Path $dest (Split-Path -Leaf $installer)
$outZip=Join-Path $dest (Split-Path -Leaf $zip)
if(Test-Path $outExe){
    $known=HashHex $outExe
    if($known -notin @($expectedExe,'2fa0e9ef7672e7c989f530cebaf59bcccc562746a32e9231a7c19beb3725adee')){
        throw 'Installed preview file was modified; do not overwrite'
    }
}
if(Test-Path $outZip){
    if((HashHex $outZip) -cne $expectedZip){throw 'Target ZIP exists with unknown hash'}
}
Copy-Item -LiteralPath $installer -Destination $outExe -Force
Copy-Item -LiteralPath $zip -Destination $outZip -Force
Copy-Item -LiteralPath $matrix -Destination (Join-Path $dest 'certification-gates.md') -Force
Copy-Item -LiteralPath $policy -Destination (Join-Path $dest 'POWERSHELL_LATEST_POLICY.md') -Force
Copy-Item -LiteralPath $evidence -Destination (Join-Path $dest 'RELEASE-EVIDENCE.json') -Force
$oldZip=Join-Path $dest 'UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED-AUTO.zip'
if(Test-Path $oldZip){
    if((HashHex $oldZip) -ceq '9b47fc89b2a848e31bf7b95111439a2ae316414ef35a1874abe0b9c8c19c02c7'){
        Remove-Item -LiteralPath $oldZip -Force
    } else {Write-Warning 'Old ZIP modified: preserved for manual review'}
}
$readme=@'
# Universal Remote RC5.1 — pré-visualização Windows x64

**Versão de teste não assinada, ainda não certificada para publicação pública.**

Instalação: executar o ficheiro .exe desta pasta. Seguir as cinco etapas da configuração inicial. Python, pip, Git e runtimes C++ não exigem qualquer instalação manual.

PowerShell: no primeiro arranque, a opção de verificar a versão estável mais recente publicada pela Microsoft vem selecionada; pode ser desmarcada. A aplicação consulta a versão nesse momento, suporta versões principais futuras, reutiliza instalações iguais ou superiores, e não altera o PowerShell global do Windows.

Sem instalação: extrair o ZIP LATEST e abrir GUI\UniversalRemote-Preview.exe.

MCP local: 27 ferramentas, com operações privilegiadas desligadas por defeito. A preview NÃO inclui um sistema público de emparelhamento remoto pela Internet.

Consultar SHA256SUMS.txt para hashes e POWERSHELL_LATEST_POLICY.md para a política de versões. Ainda faltam assinatura digital de editor, testes Windows/ARM64 noutros PCs, acessibilidade e auditoria independente.

A RC5.0 instalada no ASUS não é alterada.
'@
[IO.File]::WriteAllText((Join-Path $dest 'LEIA-PRIMEIRO.md'),$readme,[Text.UTF8Encoding]::new($false))
$sum=($expectedExe+'  '+(Split-Path -Leaf $installer)+[Environment]::NewLine+$expectedZip+'  '+(Split-Path -Leaf $zip)+[Environment]::NewLine)
[IO.File]::WriteAllText((Join-Path $dest 'SHA256SUMS.txt'),$sum,[Text.UTF8Encoding]::new($false))
if((HashHex $outExe) -cne $expectedExe -or (HashHex $outZip) -cne $expectedZip){
    throw 'Delivery integrity verification failed'
}
Write-Output ('PREVIEW_UPDATED='+$dest)
Write-Output ('INSTALLER_SHA256='+$expectedExe)
Write-Output ('PORTABLE_SHA256='+$expectedZip)
Write-Output ('FILE_COUNT='+@(Get-ChildItem -LiteralPath $dest -File).Count)
