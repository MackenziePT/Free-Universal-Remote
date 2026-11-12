$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$qa=Join-Path $root 'evidence\qa'
$py=Join-Path $qa 'patched-app-venv\Scripts\python.exe'
$iscc=Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'
Set-Location -LiteralPath $root
function Run-Step([string]$name,[string]$log,[scriptblock]$job){
    Write-Output ('BEGIN '+$name)
    & $job *> (Join-Path $qa $log)
    $exitCode=$LASTEXITCODE
    if($exitCode -ne 0){
        Write-Output ('FAILED '+$name+' exit='+$exitCode)
        Get-Content -LiteralPath (Join-Path $qa $log) -Tail 24
        exit $exitCode
    }
    Write-Output ('PASS '+$name)
}
Run-Step 'AUDIT_ALL_FOUR_BUNDLES' 'RC51-4BUNDLE-AUDIT.log' {
    & $py tools\audit_bundled_runtime.py
}
Run-Step 'INNO_RC51_INSTALLER_BUILD' 'RC51-TUNNEL-INNO-BUILD.log' {
    & $iscc '/Qp' 'packaging\UniversalRemote-Preview.iss'
}
Run-Step 'INNO_INSTALL_REPAIR_UNINSTALL' 'RC51-TUNNEL-INSTALLER-E2E.log' {
    & $py tools\qa_installer_e2e.py
}
Get-Content -LiteralPath (Join-Path $qa 'RC51-TUNNEL-INSTALLER-E2E.log') -Tail 2
Run-Step 'SIGNED_TEST_UPDATE_AND_ROLLBACK' 'RC51-TUNNEL-SIGNED-UPDATER-E2E.log' {
    & $py tools\qa_signed_updater_e2e.py
}
Get-Content -LiteralPath (Join-Path $qa 'RC51-TUNNEL-SIGNED-UPDATER-E2E.log') -Tail 2
Run-Step 'REFRESH_PRIVATE_QA_ZIP' 'RC51-TUNNEL-ZIP-BUILD.log' {
    & $py tools\build_independent_qa_kit.py
}
Run-Step 'VERIFY_PRIVATE_QA_ZIP' 'RC51-TUNNEL-ZIP-CHECK.log' {
    & $py tools\qa_verify_archive.py
}
Get-Content -LiteralPath (Join-Path $qa 'RC51-TUNNEL-ZIP-CHECK.log') -Tail 2
& $py tools\public_release_gate.py *> (Join-Path $qa 'RC51-TUNNEL-PUBLIC-RELEASE-GATE.log')
if($LASTEXITCODE -ne 3){throw 'Public release gate must refuse because CA and external QA are not complete'}
Write-Output 'PASS PUBLIC_RELEASE_NO_GO_EXPECTED'
Write-Output 'RC51_TUNNEL_PRIVATE_ACCEPTANCE_PASS'
