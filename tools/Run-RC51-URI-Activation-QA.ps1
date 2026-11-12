# RC5.1: deep-link one-paste activation QA. No changes to live RC5.0.
$ErrorActionPreference='Stop'
$root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$qa=Join-Path $root 'evidence\qa'
$py=Join-Path $qa 'patched-app-venv\Scripts\python.exe'
$iscc=Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'
Set-Location -LiteralPath $root
$env:URM_CI_HEADLESS='1'
function Step([string]$name,[string]$file,[scriptblock]$action){
    Write-Output ("BEGIN "+$name)
    & $action *> (Join-Path $qa $file)
    $code=$LASTEXITCODE
    if($code -ne 0){
        Write-Output ("FAILED "+$name+" exit="+$code)
        Get-Content -LiteralPath (Join-Path $qa $file) -Tail 25
        exit $code
    }
    Write-Output ("PASS "+$name)
}
Step 'SIGNED_TEMPLATE_PARITY' 'RC51-URI-SIGNED-PARITY.log' {
    & $py tools\sync_activation_signed_candidate.py
}
Step 'FULL_REGRESSION' 'RC51-URI-ALL-UNIT.log' {
    & $py -m unittest discover -s tests -p 'test_*.py' -q
}
Get-Content -LiteralPath (Join-Path $qa 'RC51-URI-ALL-UNIT.log') -Tail 4
Step 'GUI_BUILD' 'RC51-URI-GUI-BUILD.log' {
    & $py -m PyInstaller --noconfirm --clean --noupx --onedir --windowed --name UniversalRemote-Preview --distpath (Join-Path $qa 'public-portable-prototype') --workpath (Join-Path $qa 'pyinstaller-work') --specpath (Join-Path $qa 'pyinstaller-spec') --paths $root --hidden-import pairing_management_ui --hidden-import device_pairing --hidden-import help_center --hidden-import guided_steps --hidden-import connection_doctor --hidden-import tunnel_setup_ui --hidden-import tunnel_manager --hidden-import cryptography.hazmat.primitives.asymmetric.ed25519 (Join-Path $root 'public_gui.py')
}
$runtime=Join-Path $qa 'public-portable-prototype'
$from=Join-Path $runtime 'UniversalRemoteAgent-Preview\_internal\zlib1.dll'
$to=Join-Path $runtime 'UniversalRemote-Preview\_internal\zlib1.dll'
if(-not(Test-Path $to) -and (Test-Path $from)) {Copy-Item -LiteralPath $from -Destination $to -ErrorAction Stop}
Step 'GUI_FROZEN_SELFTEST' 'RC51-URI-GUI-SELFTEST.log' {
    & $py tools\qa_frozen_all_temp.py
}
Step 'INSTALLER_BUILD' 'RC51-URI-INNO.log' {
    & $iscc '/Qp' (Join-Path $root 'packaging\UniversalRemote-Preview.iss')
}
Step 'INSTALLER_DEEP_LINK_AND_E2E' 'RC51-URI-INSTALL-E2E.log' {
    & $py tools\qa_installer_e2e.py
}
Get-Content -LiteralPath (Join-Path $qa 'RC51-URI-INSTALL-E2E.log') -Tail 3
Step 'PACK_PRIVATE_QA' 'RC51-URI-ZIP-BUILD.log' {
    & $py tools\build_independent_qa_kit.py
}
Step 'VERIFY_PRIVATE_QA' 'RC51-URI-ZIP-VERIFY.log' {
    & $py tools\qa_verify_archive.py
}
Get-Content -LiteralPath (Join-Path $qa 'RC51-URI-ZIP-VERIFY.log') -Tail 2
& $py tools\public_release_gate.py *> (Join-Path $qa 'RC51-URI-PUBLIC-NO-GO.log')
if($LASTEXITCODE -ne 3){throw 'Expected public release gate NO-GO'}
Write-Output 'RC51_ONE_PASTE_ACTIVATION_PRIVATE_QA_PASS'
