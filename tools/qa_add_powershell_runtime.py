"""Wire public runtime (no global PowerShell installer) to public product."""
from pathlib import Path
r=Path(__file__).resolve().parents[1]
def patch(path,old,new):
 p=r/path
 s=p.read_text(encoding="utf-8")
 assert old in s,(path,old[:115])
 p.write_text(s.replace(old,new),encoding="utf-8",newline="\n")
 print("PATCH",path)
patch("scripts/Resolve-PowerShell.ps1",r"HarmonyRemoteMCP\runtime\powershell",r"UniversalRemote\runtime\powershell")
patch("scripts/Resolve-PowerShell.ps1","param([switch]$NoDownload, [version]$MinimumVersion",
      "param([switch]$NoDownload, [switch]$PreferLatest, [version]$MinimumVersion")
patch("scripts/Resolve-PowerShell.ps1",'''    if ($BestPath) { return $BestPath }
    if ($NoDownload) { throw 'PowerShell 7+ não encontrado; descarregamento desativado neste teste' }
    return Install-UniversalPortablePowerShell -MinimumVersion $MinimumVersion''',
'''    if ($BestPath -and (-not $PreferLatest -or $NoDownload)) { return $BestPath }
    if ($NoDownload) { throw 'PowerShell 7+ não encontrado; descarregamento desativado neste teste' }
    try {
        return Install-UniversalPortablePowerShell -MinimumVersion $MinimumVersion
    } catch {
        if ($BestPath) {
            Write-Warning 'Não foi possível obter a versão mais recente; foi conservada a instalação atual verificada'
            return $BestPath
        }
        throw
    }''')
patch("remote_core.py",r'"HarmonyRemoteMCP" / "runtime" / "powershell"',
      r'"UniversalRemote" / "runtime" / "powershell"')
patch("tests/test_public_readiness.py",
      'path=Path(tmp)/"HarmonyRemoteMCP"/"runtime"/"powershell"/"7.6.9-x64"',
      'path=Path(tmp)/"UniversalRemote"/"runtime"/"powershell"/"7.6.9-x64"')
patch("universal_remote_ui.py",'''import json
import os
import sys''','''import json
import os
import sys
import queue
import threading''')
patch("universal_remote_ui.py",'''from native_jobs import TaskManager
from remote_core import grant_allowed, load_config''','''from native_jobs import TaskManager
from remote_core import grant_allowed, load_config
from public_runtime import get_private_powershell_setup_path, install_private_powershell''')
patch("universal_remote_ui.py",
'''        self.nav_buttons = {}
        self.page = ""''',
'''        self.nav_buttons = {}
        self._pwsh_results = queue.Queue()
        self._pwsh_worker = None
        self.page = ""''')
needle='''        self._label(box, "Para serviços de IA remotos é necessário um transporte autenticado "
                    "compatível. Não se expõem portas do computador à Internet.",
                    10, MUTED, wraplength=630).pack(anchor="w", pady=(16, 0))

    def _copy_config(self):'''
change='''        self._label(box, "Para serviços de IA remotos é necessário um transporte autenticado "
                    "compatível. Não se expõem portas do computador à Internet.",
                    10, MUTED, wraplength=630).pack(anchor="w", pady=(16, 0))
        extra = self._card()
        extra.pack(fill="x", pady=(14,0))
        self._label(extra, "PowerShell 7  ·  Motor de diagnósticos", 13, TEXT, bold=True).pack(anchor="w")
        self._label(extra, "A aplicação funciona sem PowerShell pré-instalado. "
                    "Para ferramentas de diagnóstico e terminal PowerShell, podes obter "
                    "automaticamente a versão estável mais recente da Microsoft. "
                    "A cópia fica privada na aplicação; não altera o PowerShell do Windows.",
                    10, MUTED, wraplength=630).pack(anchor="w", pady=(7, 11))
        self._button(extra, "Obter ou atualizar PowerShell 7", self._prepare_powershell).pack(anchor="w")
        self._pwsh_status = self._label(extra, "", 9, MUTED)
        self._pwsh_status.pack(anchor="w", pady=(8,0))

    def _prepare_powershell(self):
        if self._pwsh_worker is not None and self._pwsh_worker.is_alive():
            return
        if not messagebox.askyesno("PowerShell da Microsoft",
              "Queres descarregar e verificar a versão estável mais recente do PowerShell 7?\\n\\n"
              "O download é feito do repositório oficial Microsoft e a assinatura e SHA-256 "
              "são verificadas. Não altera o PowerShell instalado globalmente."):
            return
        if hasattr(self, "_pwsh_status") and self._pwsh_status.winfo_exists():
            self._pwsh_status.configure(text="A descarregar e verificar a assinatura Microsoft...")
        def background():
            try:
                location = install_private_powershell()
                self._pwsh_results.put(("ok",str(location)))
            except Exception as ex:
                self._pwsh_results.put(("error",str(ex)))
        self._pwsh_worker=threading.Thread(target=background,daemon=True,name="urm-pwsh-provision")
        self._pwsh_worker.start()
        self.after(400,self._poll_powershell)

    def _poll_powershell(self):
        try:
            state,detail=self._pwsh_results.get_nowait()
        except queue.Empty:
            if self.winfo_exists():
                self.after(400,self._poll_powershell)
            return
        if state=="ok":
            messagebox.showinfo("PowerShell pronto",
                                "PowerShell verificado e disponível para o Universal Remote.\\n"+detail)
        else:
            messagebox.showerror("Não foi possível preparar",detail)
        if self.winfo_exists() and self.page=="Conexões":
            self.show("Conexões")

    def _copy_config(self):'''
patch("universal_remote_ui.py",needle,change)
patch("packaging/UniversalRemote-Preview.iss",
      '''Source: "..\\docs\\INSTALLER_AND_UX_SPEC.md"; DestDir: "{app}\\docs"; Flags: ignoreversion''',
      '''Source: "..\\scripts\\Resolve-PowerShell.ps1"; DestDir: "{app}\\scripts"; Flags: ignoreversion
Source: "..\\scripts\\Prepare-PowerShell.ps1"; DestDir: "{app}\\scripts"; Flags: ignoreversion
Source: "..\\docs\\INSTALLER_AND_UX_SPEC.md"; DestDir: "{app}\\docs"; Flags: ignoreversion''')
patch("packaging/UniversalRemote-Preview.iss","WizardResizable=yes\n","")
print("PUBLIC_RUNTIME_CONNECTIONS_DONE")
