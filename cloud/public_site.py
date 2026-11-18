"""Public listing and notices served by the existing HTTPS MCP gateway.

Pre-release information; the verified publisher must approve final legal
language and contacts before submitting the plugin for official review.
"""
from __future__ import annotations
from html import escape
import secrets
from fastapi.responses import HTMLResponse

PROJECT="https://github.com/MackenziePT/Free-Universal-Remote"
PAGES={
 "about":("Universal Remote Free Unlimited",[
  ("Sobre o projeto","Ligação protegida entre ChatGPT e computadores Windows emparelhados. Esta versão é uma pré-publicação técnica: o instalador assinado e a aprovação oficial ainda estão pendentes."),
  ("Como funciona","Cada computador usa uma chave Ed25519 própria, protegida pelo Windows. A autenticação OAuth utiliza Supabase e o gateway HTTPS está alojado no Railway. O emparelhamento não autoriza automaticamente PowerShell, ficheiros, ecrã ou rato."),
  ("Limitações","Free Unlimited não elimina quotas, custos ou limites dos prestadores externos. Não uses builds de teste como se fossem instaladores certificados.")
 ]),
 "privacy":("Privacidade — Universal Remote Free Unlimited",[
  ("Autenticação e identidade","O Supabase processa o email e as sessões de autenticação. O Railway armazena identificadores pseudonimizados de conta, nomes de dispositivos e chaves públicas. A chave privada Ed25519 permanece no Windows, protegida com DPAPI."),
  ("Dados e operações","Se forem autorizadas, operações podem incluir comandos, caminhos, resultados e conteúdos sensíveis. A fila de operações do Railway cifra argumentos e resultados em repouso."),
  ("Retenção","As operações têm prazo de cinco minutos. O histórico é elegível para limpeza 24 horas após a expiração, com remoção progressiva. Os prestadores de alojamento podem reter logs de infraestrutura segundo políticas próprias."),
  ("Direitos e revogação","A revogação de um dispositivo invalida a sua chave e operações associadas, mas não elimina automaticamente a conta Supabase. Para pedidos relativos a dados, usa o suporte para solicitar um contacto privado; não publiques palavras-passe, tokens ou outros dados pessoais em issues abertas.")
 ]),
 "terms":("Condições — Universal Remote Free Unlimited",[
  ("Autorização","Utiliza a aplicação apenas em computadores próprios ou com consentimento explícito do titular. Nunca partilhes credenciais ou identidades privadas de dispositivos."),
  ("Estado do produto","O software encontra-se em testes. O gateway público e os instaladores de ensaio não representam certificação pela OpenAI, Microsoft ou terceiros."),
  ("Riscos","PowerShell, alterações de ficheiros e ações de ecrã podem mudar o computador. Confirma sempre as autorizações locais e mantém cópias de segurança. A disponibilidade e os limites dos serviços de terceiros continuam a aplicar-se."),
  ("Revisão","O editor deve validar e aprovar as condições definitivas antes da distribuição pública geral.")
 ]),
 "support":("Suporte — Universal Remote Free Unlimited",[
  ("Primeira ligação","Inicia sessão no Supabase, associa o teu próprio Windows e verifica a ligação de saída HTTPS. Um dispositivo emparelhado precisa de uma comunicação assinada recente para estar online."),
  ("Email confirmado","Se o link do email expirar mas a conta estiver confirmada, abre um pedido OAuth novo e escolhe Entrar, não Criar conta."),
  ("Permissões","O servidor pode aceitar o login e o emparelhamento mantendo comandos remotos bloqueados até conclusão dos ensaios de segurança."),
  ("Contacto","Usa as issues do repositório GitHub para suporte público. Para incidentes de segurança ou privacidade, solicita primeiro um canal privado e nunca publiques tokens, palavras-passe ou capturas privadas.")
 ])
}

def public_page(name: str) -> HTMLResponse:
    if name not in PAGES:
        raise ValueError("Unknown listing page")
    title,sections=PAGES[name]
    nonce=secrets.token_urlsafe(24)
    links=" · ".join(f'<a href="/{name_}">{escape(label)}</a>' for name_,label in
                   (("about","Início"),("privacy","Privacidade"),("terms","Condições"),("support","Suporte")))
    body="".join(f'<section><h2>{escape(head)}</h2><p>{escape(text)}</p></section>'
                 for head,text in sections)
    source=f"""<!doctype html>
<html lang="pt-PT"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style nonce="{nonce}">
:root{{color-scheme:dark;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#101719;color:#ebf3ef}}
body{{margin:0;padding:1.5rem;min-height:100vh;box-sizing:border-box}}
main{{max-width:760px;margin:2rem auto;background:#1b2729;border:1px solid #36574e;border-radius:18px;padding:2rem}}
nav{{line-height:2}}h1{{font-size:1.75rem}}h2{{font-size:1.17rem;margin-top:1.7rem}}
p{{line-height:1.65}}a{{color:#a1e7c5}}small{{color:#bbcbc3}}
</style></head><body><main><nav aria-label="Navegação">{links}</nav>
<h1>{escape(title)}</h1><p><small>Informação de pré-lançamento.</small></p>
{body}<p><a href="{PROJECT}">Projeto no GitHub</a> · <a href="{PROJECT}/issues">Suporte</a></p>
</main></body></html>"""
    csp=("default-src 'none'; base-uri 'none'; object-src 'none'; "
         "frame-ancestors 'none'; form-action 'none'; connect-src 'none'; "
         "script-src 'none'; style-src 'nonce-"+nonce+"'")
    return HTMLResponse(source,headers={
      "Cache-Control":"no-store","Referrer-Policy":"no-referrer",
      "X-Frame-Options":"DENY","X-Content-Type-Options":"nosniff",
      "Content-Security-Policy":csp,
      "Permissions-Policy":"camera=(), microphone=(), geolocation=()"})
