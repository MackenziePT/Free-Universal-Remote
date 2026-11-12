"""Static, offline site audit (not a substitute for visual/accessibility testing)."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import re

ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/"site"/"index.html"

class SiteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=set()
        self.hrefs=[]
        self.external=[]
        self.scripts=[]
        self.images=[]
        self.lang=None
        self.meta=set()

    def handle_starttag(self,tag,attrs):
        props=dict(attrs)
        if tag=="html": self.lang=props.get("lang")
        if props.get("id"): self.ids.add(props["id"])
        if tag=="a": self.hrefs.append(props.get("href",""))
        if tag=="script": self.scripts.append(props.get("src"))
        if tag in {"img","iframe"}: self.images.append(props.get("src"))
        if tag=="meta": self.meta.add(props.get("name",""))
        if tag in {"link","script","img","iframe"}:
            url=props.get("href",props.get("src",""))
            if url and urlparse(url).scheme in {"http","https"}: self.external.append(url)

text=HTML.read_text(encoding="utf-8")
p=SiteParser();p.feed(text);p.close()
issues=[]
if p.lang!="pt-PT":issues.append("missing PT-PT lang")
if "viewport" not in p.meta:issues.append("missing viewport")
if "description" not in p.meta:issues.append("missing description")
if not all(h.startswith("#") and h[1:] in p.ids for h in p.hrefs):
    issues.append("dead or external navigation targets")
if p.external or p.scripts or p.images:issues.append("unexpected third-party asset or active scripting")
if "prefers-reduced-motion" not in text:issues.append("missing reduced-motion CSS")
if "font-size" not in text:issues.append("missing scalable typography")
if "Download" in text or "Descarregar" in text:
    print("SITE_NOTE: download references are informational only; no live download")
print("SITE_TAG_IDS",len(p.ids),"NAVIGATION_LINKS",len(p.hrefs),"THIRD_PARTY_ASSETS",len(p.external))
if issues:
    for issue in issues: print("FAIL",issue)
    raise SystemExit(1)
print("SITE_STATIC_AUDIT_PASS")
