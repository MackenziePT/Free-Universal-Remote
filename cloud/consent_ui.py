# HTML OAuth consent is served only over the existing secure gateway.
from __future__ import annotations
from pathlib import Path
import secrets
from fastapi.responses import HTMLResponse

def consent_html_response():
    nonce=secrets.token_urlsafe(24)
    html=Path(__file__).with_name("consent.html").read_text(encoding="utf-8")
    if "__NONCE__" not in html:
        raise RuntimeError("Consent template nonce missing")
    html=html.replace("__NONCE__",nonce)
    csp=("default-src 'none'; base-uri 'none'; object-src 'none'; "+
         "frame-ancestors 'none'; form-action 'none'; "+
         "style-src 'nonce-"+nonce+"'; "+
         "script-src 'nonce-"+nonce+"' https://cdn.jsdelivr.net; "+
         "connect-src https://hsztpgfgwlmnocealhcm.supabase.co https://cdn.jsdelivr.net")
    return HTMLResponse(html,headers={
        "Cache-Control":"no-store",
        "Referrer-Policy":"no-referrer",
        "X-Frame-Options":"DENY",
        "X-Content-Type-Options":"nosniff",
        "Content-Security-Policy":csp,
        "Permissions-Policy":"camera=(), microphone=(), geolocation=()",
    })
