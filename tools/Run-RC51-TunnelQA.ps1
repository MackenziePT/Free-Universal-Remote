# Private RC5.1 comprehensive build and E2E acceptance. Never installs on live RC5.0.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$qa=Join-Path $root 'evidence\qa'
$py=Join-Path $qa 'patched-app-venv\Scripts\python.exe'
$iscc=Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'
Set-Location -LiteralPath $root
if(-not(Test-Path $py)-or -not(Test-Path $iscc)){throw 'Python QA / Inno missing'}
$env:URM_CI_HEADLESS='1'

function Run-Step {
    param([string]$Name,[string]$Log,[scriptblock]$Action)
    Write-Output ('BEGIN '+$Name)
    & $Action *> (Join-Path $qa $Log)
    $exitCode=$LASTEXITCODE
    if($null -eq $exitCode){$exitCode=0}
    if($exitCode -ne 0){
        Write-Output ('FAILED '+$Name+' exit='+$exitCode)
        Get-Content -LiteralPath (Join-Path $qa $Log) -Tail 28
        exit $exitCode
    }
    Write-Output ('PASS '+$Name)
}

Run-Step 'FULL_UNIT_REGRESSION' 'RC51-TUNNEL-FULL-REGRESSION.log' {
    & $py -m unittest discover -s tests -p 'test_*.py' -q
}
Get-Content -LiteralPath (Join-Path $qa 'RC51-TUNNEL-FULL-REGRESSION.log') -Tail 4
Run-Step 'BUILD_FOUR_STANDALONE_COMPONENTS' 'RC51-TUNNEL-PORTABLE-BUILD.log' {
    & $py tools\build_public_prototype.py
}
Get-Content -LiteralPath (Join-Path $qa 'RC51-TUNNEL-PORTABLE-BUILD.log') -Tail 6
Run-Step 'FROZEN_ALL_COMPONENTS_WINDOWS_TEMP' 'RC51-TUNNEL-FROZEN-COMPONENTS.log' {
    & $py tools\qa_frozen_all_temp.py
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
Get-Content -LiteralPath (Join-Path $qa 'RC51-TUNNEL-ZIP-CHECK.log') -Tail 1
& $py tools\public_release_gate.py *> (Join-Path $qa 'RC51-TUNNEL-PUBLIC-RELEASE-GATE.log')
if($LASTEXITCODE -ne 3){throw 'Public release gate must fail closed, pending certificate and external QA'}
Write-Output 'PASS PUBLIC_RELEASE_NO_GO_AS_EXPECTED'
Write-Output 'RC51_TUNNEL_PRIVATE_ACCEPTANCE_PASS'
