"""Add an allowlisted universal-remote:// deep link, without requiring a console.
The installer claims an unused HKCU protocol only; never overwrites a foreign handler.
"""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
entry=root/"public_gui.py"
iss=root/"packaging"/"UniversalRemote-Preview.iss"
tests=root/"tests"/"test_activation_deep_link.py"
src=entry.read_text(encoding="utf-8")
setup=iss.read_text(encoding="utf-8-sig")
def replace(text,old,new,label):
    count=text.count(old)
    if count!=1: raise RuntimeError(f"{label}: expected exactly once got {count}")
    return text.replace(old,new,1)

# Only literal allowlisted URI values. Refuse any parameters, arbitrary URLs or commands.
src=replace(src,'def main()->int:\n    policy=config_path()',
'''def activation_destination(arguments: list[str]) -> str:
    """Accept only documented, non-privileged entrypoints."""
    if not arguments:
        return "Início"
    if arguments == ["universal-remote://connect"]:
        return "Conexões"
    if arguments == ["universal-remote://open"]:
        return "Início"
    raise ValueError("Ligação de abertura inválida")

def main()->int:
    policy=config_path()''',"activation")
src=replace(src,'''        return 0
    prepare_powershell=False
    first_run=False''','''        return 0
    try:
        destination=activation_destination(sys.argv[1:])
    except ValueError:
        return 2
    prepare_powershell=False
    first_run=False''',"argument validation")
src=replace(src,
    '    app=ui.UniversalRemoteApp(start_page="Guia" if first_run else "Início")',
    '''    app=ui.UniversalRemoteApp(start_page=("Guia" if first_run and destination=="Início"
                                           else destination))
    if destination=="Conexões":
        # Deliberate click/activation opens the guide, never grants a remote session.
        app.after(450,app._open_tunnel_setup)''',
    "guided opening")

# Register URI as current-user handler only if not already assigned to an app.
setup=replace(setup,
'''function InitializeSetup(): Boolean;
begin
  Result := True;
end;''',
'''var
  InstallURProtocol: Boolean;

function InitializeSetup(): Boolean;
var
  Key, Existing, Expected: String;
begin
  Key := 'Software\\Classes\\universal-remote';
  Expected := '"' + ExpandConstant('{app}\\GUI\\UniversalRemote-Preview.exe') + '" "%1"';
  InstallURProtocol := not RegKeyExists(HKCU, Key);
  if not InstallURProtocol then
  begin
    { Existing registration is kept unless it points to this exact installation. }
    if RegQueryStringValue(HKCU, Key + '\\shell\\open\\command', '', Existing) then
      InstallURProtocol := CompareText(Existing, Expected) = 0;
  end;
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Key, Command: String;
begin
  if (CurStep = ssPostInstall) and InstallURProtocol then
  begin
    Key := 'Software\\Classes\\universal-remote';
    Command := '"' + ExpandConstant('{app}\\GUI\\UniversalRemote-Preview.exe') + '" "%1"';
    RegWriteStringValue(HKCU, Key, '', 'URL:Universal Remote');
    RegWriteStringValue(HKCU, Key, 'URL Protocol', '');
    RegWriteStringValue(HKCU, Key + '\\shell\\open\\command', '', Command);
  end;
end;''',"Inno protocol setup")
setup=replace(setup,
'''  if CurUninstallStep = usUninstall then
  begin
    Sidecar := ExpandConstant('{app}\\Tunnel\\UniversalRemoteTunnel-Preview.exe');''',
'''  if CurUninstallStep = usUninstall then
  begin
    { Never revoke someone else's protocol registration. }
    if RegQueryStringValue(HKCU,
         'Software\\Classes\\universal-remote\\shell\\open\\command',
         '', CurrentValue) then
    begin
      ExpectedValue := '"' + ExpandConstant('{app}\\GUI\\UniversalRemote-Preview.exe') + '" "%1"';
      if CompareText(CurrentValue, ExpectedValue) = 0 then
        RegDeleteKeyIncludingSubkeys(HKCU, 'Software\\Classes\\universal-remote');
    end;
    Sidecar := ExpandConstant('{app}\\Tunnel\\UniversalRemoteTunnel-Preview.exe');''',"Inno uninstall ownership")

test='''import unittest
from public_gui import activation_destination

class ActivationTests(unittest.TestCase):
    def test_one_paste_starts_guided_connection(self):
        self.assertEqual(activation_destination(["universal-remote://connect"]),"Conexões")
        self.assertEqual(activation_destination(["universal-remote://open"]),"Início")

    def test_default_entrypoint(self):
        self.assertEqual(activation_destination([]),"Início")

    def test_reject_untrusted_deep_link_arguments(self):
        invalid=(["universal-remote://connect?grant=all"],
                 ["universal-remote://connect/shell"],
                 ["universal-remote://other"],
                 ["https://somewhere.example/path"],
                 ["universal-remote://connect","extra"],
                 ["--no-consent"])
        for args in invalid:
            with self.subTest(args=args),self.assertRaises(ValueError):
                activation_destination(args)

if __name__=="__main__":
    unittest.main()
'''
# All source anchors must match before writing anything.
entry.write_text(src,encoding="utf-8")
iss.write_text(setup,encoding="utf-8-sig")
tests.write_text(test,encoding="utf-8")
print("SAFE_ONE_LINK_ACTIVATION_PATCH_APPLIED")
