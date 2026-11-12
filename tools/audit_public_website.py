"""Static site readiness checks. Local preview, no deployment or public download."""
from __future__ import annotations
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

SITE=Path(__file__).resolve().parents[1]/"site"/"index.html"
class Site(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.links=[]
        self.external=[]
        self.scripts=0
        self.forms=0
        self.lang=None
        self.meta=set()
    def handle_starttag(self,tag,attrs):
        data=dict(attrs)
        if data.get("id"):self.ids.append(data["id"])
        if tag=="a":
            self.links.append(data.get("href",""))
            href=data.get("href","")
            if urlparse(href).scheme or href.startswith("//"):self.external.append(href)
        if tag=="script":self.scripts+=1
        if tag=="form":self.forms+=1
        if tag=="html":self.lang=data.get("lang")
        if tag=="meta" and data.get("name"):self.meta.add(data["name"])
parser=Site()
html=SITE.read_text(encoding="utf-8")
parser.feed(html)
assert parser.lang=="pt-PT"
assert {"viewport","description"} <= parser.meta
assert len(parser.ids)==len(set(parser.ids)), "Duplicate anchors"
for link in parser.links:
    assert link.startswith("#"),"Unexpected external link: "+link
    assert link[1:] in parser.ids,"Broken navigation anchor: "+link
assert parser.scripts==0 and parser.forms==0
assert not parser.external
assert "Saltar para o conteúdo principal" in html
assert "não inclui" in html.lower() or "ainda não" in html.lower()
assert "versão estável mais recente" in html
assert "Python" in html and "SHA-256" in html
assert "Ainda não existe download público certificado" in html
assert "href=\"http" not in html
print("PUBLIC_SITE_STATIC_UX_PASS",{
    "navigation_links":len(parser.links),"anchors":len(parser.ids),
    "external_urls":0,"scripts":0,"forms":0,
    "state":"Local preview, no public downloads"
})
