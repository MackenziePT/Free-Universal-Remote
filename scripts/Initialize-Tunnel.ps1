[CmdletBinding()]
param([string]$TunnelId)
. (Join-Path $PSScriptRoot 'PowerShell-Security.ps1')

function Get-UniversalTunnelKeyError {
    param([AllowNull()][AllowEmptyString()][string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return 'Cole a chave completa para continuar.' }
    $Candidate = $Value.Trim()
    if ($Candidate.Length -gt 4096) { return 'O texto colado e demasiado longo para uma chave.' }
    if ($Candidate -notmatch '\Ask-[A-Za-z0-9_-]+\z') {
        return 'Cole apenas o codigo secreto completo da API, sem aspas, espacos ou linhas adicionais.'
    }
    return ''
}

function ConvertTo-UniversalTunnelKey {
    param([AllowNull()][AllowEmptyString()][string]$Value,
          [ScriptBlock]$Validator = ${function:Get-UniversalTunnelKeyError})
    $Problem = & $Validator $Value
    if ($Problem) { throw [ArgumentException]::new($Problem) }
    $Result = ConvertTo-SecureString -String $Value.Trim() -AsPlainText -Force
    $Result.MakeReadOnly()
    return $Result
}

function New-UniversalTunnelKeyDialog {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $ValidateKey = ${function:Get-UniversalTunnelKeyError}
    $ConvertKey = ${function:ConvertTo-UniversalTunnelKey}
    $Form = [Windows.Forms.Form]::new()
    $Form.Text = 'Universal Remote MCP - chave do tunel'
    $Form.ClientSize = [Drawing.Size]::new(660, 270)
    $Form.FormBorderStyle = [Windows.Forms.FormBorderStyle]::FixedDialog
    $Form.StartPosition = [Windows.Forms.FormStartPosition]::CenterScreen
    $Form.MaximizeBox = $false
    $Form.MinimizeBox = $false
    $Form.AutoScaleMode = [Windows.Forms.AutoScaleMode]::Font
    $Form.Font = [Drawing.Font]::new('Segoe UI', 10)

    $Instruction = [Windows.Forms.Label]::new()
    $Instruction.Text = "Cole a chave API completa com Ctrl+V ou com o botao Colar.`r`nO codigo fica visivel neste campo. Pode ocultar abaixo."
    $Instruction.SetBounds(20, 16, 620, 48)
    $InputBox = [Windows.Forms.TextBox]::new()
    $InputBox.SetBounds(20, 76, 620, 28)
    $InputBox.MaxLength = 4096
    $InputBox.ShortcutsEnabled = $true
    $InputBox.UseSystemPasswordChar = $false
    $InputBox.TabIndex = 0
    $Paste = [Windows.Forms.Button]::new()
    $Paste.Text = 'Colar'
    $Paste.SetBounds(20, 116, 105, 32)
    $Paste.TabIndex = 1
    $Visible = [Windows.Forms.CheckBox]::new()
    $Visible.Text = 'Mostrar chave'
    $Visible.Checked = $true
    $Visible.SetBounds(145, 119, 180, 28)
    $Visible.TabIndex = 2
    $Status = [Windows.Forms.Label]::new()
    $Status.SetBounds(20, 160, 620, 44)
    $Status.ForeColor = [Drawing.Color]::DarkRed
    $Submit = [Windows.Forms.Button]::new()
    $Submit.Text = 'Continuar'
    $Submit.SetBounds(410, 218, 110, 32)
    $Submit.TabIndex = 3
    $Cancel = [Windows.Forms.Button]::new()
    $Cancel.Text = 'Cancelar'
    $Cancel.SetBounds(530, 218, 110, 32)
    $Cancel.TabIndex = 4
    $Cancel.DialogResult = [Windows.Forms.DialogResult]::Cancel
    $Form.AcceptButton = $Submit
    $Form.CancelButton = $Cancel
    $Form.Controls.AddRange(@($Instruction, $InputBox, $Paste, $Visible, $Status, $Submit, $Cancel))

    # Clipboard access occurs only after Paste/Ctrl+V, never on form creation.
    # All paste routes validate the entire clipboard text before putting it in
    # the single-line control (which would otherwise truncate at a newline).
    $Paste.add_Click({
        $Raw = $null; $Candidate = $null
        try {
            $Raw = [Windows.Forms.Clipboard]::GetText()
            $Problem = & $ValidateKey $Raw
            if ($Problem) { $Status.Text = $Problem; return }
            $Candidate = $Raw.Trim()
            $InputBox.Text = $Candidate
            $InputBox.SelectionStart = $InputBox.TextLength
            $InputBox.SelectionLength = 0
            $Status.Text = ''
            $InputBox.Focus() | Out-Null
        } catch {
            $Status.Text = 'Nao foi possivel colar. Copie a chave novamente e clique em Colar.'
        } finally { $Raw = $null; $Candidate = $null }
    }.GetNewClosure())
    $InputBox.add_KeyDown({
        param($Sender, $Event)
        if (($Event.Control -and $Event.KeyCode -eq [Windows.Forms.Keys]::V) -or
            ($Event.Shift -and $Event.KeyCode -eq [Windows.Forms.Keys]::Insert)) {
            $Event.Handled = $true
            $Event.SuppressKeyPress = $true
            $Paste.PerformClick()
        }
    }.GetNewClosure())
    $Menu = [Windows.Forms.ContextMenuStrip]::new()
    $MenuPaste = $Menu.Items.Add('Colar chave completa')
    $MenuPaste.add_Click({ $Paste.PerformClick() }.GetNewClosure())
    $InputBox.ContextMenuStrip = $Menu
    $Visible.add_CheckedChanged({
        $InputBox.UseSystemPasswordChar = -not $Visible.Checked
    }.GetNewClosure())
    $Submit.add_Click({
        try {
            $Form.Tag = & $ConvertKey -Value $InputBox.Text -Validator $ValidateKey
            $Form.DialogResult = [Windows.Forms.DialogResult]::OK
            $Form.Close()
        } catch {
            $Problem = & $ValidateKey $InputBox.Text
            if ($Problem) { $Status.Text = $Problem }
            else { $Status.Text = 'Nao foi possivel preparar a chave. Tente novamente.' }
        }
    }.GetNewClosure())
    $Form.add_Shown({ $InputBox.Focus() | Out-Null }.GetNewClosure())
    # Only controls are returned. The secret is returned as SecureString by Read.
    return @{Form=$Form; Input=$InputBox; Paste=$Paste; Visible=$Visible; Submit=$Submit; Cancel=$Cancel; Menu=$Menu}
}

function Read-UniversalTunnelKey {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'A janela da chave deve ser aberta no Windows.'
    }
    if ([Threading.Thread]::CurrentThread.GetApartmentState() -ne [Threading.ApartmentState]::STA) {
        # Windows Forms clipboard requires STA. Keep the result in memory;
        # no temporary secret file, command-line token or console echo.
        $Runspace = [Management.Automation.Runspaces.RunspaceFactory]::CreateRunspace()
        $Runspace.ApartmentState = [Threading.ApartmentState]::STA
        $Runspace.ThreadOptions = [Management.Automation.Runspaces.PSThreadOptions]::ReuseThread
        $PowerShell = [Management.Automation.PowerShell]::Create()
        try {
            $Runspace.Open()
            $PowerShell.Runspace = $Runspace
            $null = $PowerShell.AddScript('. $args[0]; Read-UniversalTunnelKey').AddArgument($PSCommandPath)
            $Results = $PowerShell.Invoke()
            if ($PowerShell.HadErrors -or $Results.Count -ne 1 -or
                $Results[0].PSObject.BaseObject -isnot [Security.SecureString]) {
                throw 'Entrada da chave cancelada ou indisponivel. Nenhuma credencial foi guardada.'
            }
            return $Results[0].PSObject.BaseObject
        } finally { $PowerShell.Dispose(); $Runspace.Dispose() }
    }
    $Dialog = New-UniversalTunnelKeyDialog
    try {
        if ($Dialog.Form.ShowDialog() -ne [Windows.Forms.DialogResult]::OK -or
            $Dialog.Form.Tag -isnot [Security.SecureString]) {
            throw [OperationCanceledException]::new('Entrada da chave cancelada. Nenhuma credencial foi guardada.')
        }
        $Secret = $Dialog.Form.Tag
        $Dialog.Form.Tag = $null
        return $Secret
    } finally {
        $Dialog.Input.Clear()
        $Dialog.Input.ClearUndo()
        if ($Dialog.Form.Tag -is [Security.SecureString]) { $Dialog.Form.Tag.Dispose() }
        $Dialog.Form.Tag = $null
        $Dialog.Menu.Dispose()
        $Dialog.Form.Dispose()
    }
}

function Invoke-UniversalTunnelInitialization {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][ValidatePattern('^tunnel_[0-9a-f]{32}$')][string]$TunnelId)
    $ErrorActionPreference = 'Stop'
    $Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
    $Client = Join-Path $Root 'bin\tunnel-client.exe'
    $Python = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $Client)) { throw "Copy tunnel-client.exe into $Root\bin first (official OpenAI release)" }
    if (-not (Test-Path -LiteralPath $Python)) { throw 'Run scripts\Install.ps1 first' }
    $StateRoot = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
    New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
    $SecretPath = Join-Path $StateRoot 'tunnel-key.dpapi'
    Write-Host 'Cole a chave na janela Universal Remote MCP. Ctrl+V e o botao Colar estao disponiveis.'
    $SecureKey = Read-UniversalTunnelKey
    if ($SecureKey -isnot [Security.SecureString]) { throw 'No key supplied. Nothing was initialized.' }
    # DPAPI binds this ciphertext to the currently logged-in Windows account.
    try {
        $BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
        try { $env:CONTROL_PLANE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR) }
        & $Python (Join-Path $Root 'initialize_tunnel.py') --tunnel-id $TunnelId
        if ($LASTEXITCODE -ne 0) { throw 'Tunnel initialization failed' }
        & $Client doctor --profile harmony-remote --explain
        if ($LASTEXITCODE -ne 0) { throw 'Tunnel doctor did not pass. Fix the diagnosis before starting.' }
        # Persist only after BOTH initialization and doctor succeed.
        $SecureKey | ConvertFrom-SecureString | Set-Content -LiteralPath $SecretPath -Encoding UTF8
        Write-Host 'Tunnel initialized. Use scripts\Start-Tunnel.ps1 to connect.' -ForegroundColor Green
    } finally {
        Remove-Item Env:\CONTROL_PLANE_API_KEY -ErrorAction SilentlyContinue
        $SecureKey.Dispose()
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    if (-not $TunnelId) { throw 'Supply -TunnelId with your private tunnel ID.' }
    Invoke-UniversalTunnelInitialization -TunnelId $TunnelId
}
