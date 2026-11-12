"""Build a self-contained key-paste repair using the verified atomic repair flow."""
import argparse
import base64
import hashlib
from pathlib import Path
import re
from build_connection_repair import BODY, HEADER

ROOT = Path(__file__).resolve().parents[1]
OLD_HASHES = [
    '53a78232c1fbff6615caabde94614c4a92d2a2eeffee449e9e9252cb265d88c1',
    'eb9fcb9749c65c21570e45d0dd6da7d111fe359d6505fa3b8a2677679fa55d52',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tunnel-id', default='')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.tunnel_id and not re.fullmatch(r'tunnel_[0-9a-f]{32}', args.tunnel_id):
        parser.error('Invalid tunnel ID')
    fixed = (ROOT/'scripts/Initialize-Tunnel.ps1').read_bytes()
    payload = base64.b64encode(fixed).decode('ascii')
    # Short lines keep the CMD artifact safely below the cmd.exe line limit.
    payload = "' +\n        '".join(payload[i:i+120] for i in range(0, len(payload), 120))
    body = BODY.replace('build_connection_repair.py', 'build_key_input_repair.py')
    body = body.replace('Invoke-UniversalVerifierRepair', 'Invoke-UniversalKeyInputRepair')
    body = body.replace('Verify-Windows.ps1', 'Initialize-Tunnel.ps1')
    body = body.replace('verify-cwd-20261022', 'key-paste-20261022')
    body = body.replace('verifier', 'key input').replace('Verifier', 'Key input')
    body = body.replace('Key input corrected. All regression and MCP checks remain enabled.',
                        'Key input corrected: visible field, Ctrl+V, Paste button and optional masking.')
    body = body.replace('__OLD_HASHES__', ','.join(repr(x) for x in OLD_HASHES))
    body = body.replace('__FIXED_BYTES__', payload)
    body = body.replace('__FIXED_HASH__', hashlib.sha256(fixed).hexdigest())
    header = HEADER.replace('reparar e ligar', 'colar chave e ligar')
    header = header.replace('reparacao do verificador', 'entrada normal da chave com Colar')
    header = header.replace('A chave, se necessaria, sera pedida apenas na janela protegida.',
                            'A chave sera pedida numa janela propria com campo normal e botao Colar.')
    header = header.replace('-NoLogo -NoProfile', '-NoLogo -NoProfile -STA')
    (ROOT/'scripts/Repair-KeyInput.ps1').write_text(body.replace('__TUNNEL_ID__', ''), encoding='ascii', newline='\n')
    out = args.output or ROOT/'COLAR-CHAVE-E-LIGAR.cmd'
    out.write_bytes((header+body.replace('__TUNNEL_ID__', args.tunnel_id)).replace('\r\n', '\n').replace('\n', '\r\n').encode('ascii'))
    print(out)


if __name__ == '__main__':
    main()
