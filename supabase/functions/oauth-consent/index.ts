/* Public Supabase OAuth consent UI, no service role or private key. */
const HTML = [
  "<!doctype html><html lang='pt-PT'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Universal Remote — Autorização</title>",
  "<style nonce='__NONCE__'>:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#101719;color:#eaf4f0}body{min-height:100vh;display:grid;place-items:center;margin:0;padding:1rem;box-sizing:border-box}main{width:min(100%,520px);background:#1a2527;border:1px solid #3a6256;border-radius:15px;padding:1.8rem}p{line-height:1.5}label{display:block;margin-top:.75rem}input{width:100%;box-sizing:border-box;padding:.7rem;border:1px solid #638d7d;border-radius:7px;background:#0c1718;color:white}button{margin:.6rem .4rem 0 0;padding:.8rem;border:1px solid #478f73;background:#226a50;color:white;border-radius:8px;cursor:pointer}button.secondary{background:#333e43}button:disabled{opacity:.5}section[hidden]{display:none}#status{color:#f7d48a;min-height:2.5rem}small{color:#bad0c7}</style></head><body>",
  "<main><h1>Universal Remote Free Unlimited</h1><p>Identifica-te e aprova apenas as aplicações que conheces. O controlo de PowerShell, ecrã, teclado e rato exige sempre autorização separada no teu Windows.</p>",
  "<p id='status' role='status' aria-live='polite'>A verificar a autorização...</p>",
  "<section id='account' hidden><h2>Entrar na conta</h2><label for='email'>Email</label><input id='email' type='email' autocomplete='email'><label for='password'>Palavra-passe</label><input id='password' type='password' autocomplete='current-password' minlength='8'>",
  "<button type='button' id='signin'>Entrar</button><button type='button' class='secondary' id='signup'>Criar conta</button><p><small>É possível que tenhas de confirmar o email antes de entrares.</small></p></section>",
  "<section id='consent' hidden><h2>Autorizar aplicação</h2><p>Aplicação: <strong id='client-name'></strong></p><p>Endereço de retorno: <strong id='redirect-uri'></strong></p><p>Âmbitos solicitados:</p><ul id='scopes'></ul>",
  "<button type='button' id='allow' disabled>Autorizar</button><button type='button' id='deny' class='secondary' disabled>Recusar</button></section></main>",
  "<script type='module' nonce='__NONCE__'>",
  "import {createClient} from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.0/+esm';",
  "const sb=createClient('https://hsztpgfgwlmnocealhcm.supabase.co','sb_publishable_EBRAjPDfSpTOPq2C2oc78Q_4rn8si8a',{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:false}});",
  "const el=id=>document.getElementById(id),msg=t=>{el('status').textContent=t;};",
  "const aid=new URL(location.href).searchParams.get('authorization_id');",
  "async function refresh(){try{const {data:{user},error}=await sb.auth.getUser();if(error||!user){el('account').hidden=false;msg('Inicia sessão para veres o pedido.');return;}",
  "el('account').hidden=true;const result=await sb.auth.oauth.getAuthorizationDetails(aid);if(result.error||!result.data)throw new Error('Pedido de autorização inválido ou expirado.');const d=result.data;",
  "if(!('authorization_id' in d)){if(d.redirect_url){location.assign(d.redirect_url);return;}throw new Error('Resposta inválida.');}",
  "el('client-name').textContent=String(d.client?.name||'Aplicação desconhecida');el('redirect-uri').textContent=String(d.redirect_uri||'Não indicado');const list=el('scopes');list.replaceChildren();",
  "for(const scope of String(d.scope||'').split(' ').filter(Boolean)){const item=document.createElement('li');item.textContent=scope;list.appendChild(item);}if(!list.children.length){const item=document.createElement('li');item.textContent='Identificação básica';list.appendChild(item);}",
  "el('consent').hidden=false;el('allow').disabled=false;el('deny').disabled=false;msg('Confirma o destinatário e os âmbitos antes de autorizar.');}catch(e){msg(e?.message||'Não foi possível validar o pedido.');}}",
  "async function decide(ok){el('allow').disabled=true;el('deny').disabled=true;msg('A registar a tua decisão...');try{const r=ok?await sb.auth.oauth.approveAuthorization(aid):await sb.auth.oauth.denyAuthorization(aid);if(r.error||!r.data?.redirect_url)throw new Error('Falha ao confirmar a decisão.');location.assign(r.data.redirect_url);}catch(e){msg(e?.message||'Não foi possível concluir.');el('allow').disabled=false;el('deny').disabled=false;}}",
  "async function signin(create){const email=el('email').value.trim(),password=el('password').value;if(!email.includes('@')||password.length<8){msg('Indica um email válido e uma palavra-passe de pelo menos 8 caracteres.');return;}el('signin').disabled=true;el('signup').disabled=true;",
  "try{const r=create?await sb.auth.signUp({email,password}):await sb.auth.signInWithPassword({email,password});if(r.error)throw new Error(r.error.message);if(!r.data?.session){msg('Confirma o email enviado pelo Supabase e volta a entrar.');return;}await refresh();}catch(e){msg(e?.message||'Falha de autenticação.');}finally{el('signin').disabled=false;el('signup').disabled=false;}}",
  "el('allow').addEventListener('click',()=>decide(true));el('deny').addEventListener('click',()=>decide(false));el('signin').addEventListener('click',()=>signin(false));el('signup').addEventListener('click',()=>signin(true));",
  "if(!aid||!(/^[A-Za-z0-9_-]{8,256}$/).test(aid))msg('Identificador de autorização em falta ou inválido.');else void refresh();",
  "</script></body></html>"
].join("\n");
Deno.serve((request:Request)=>{
  if(request.method!=="GET")return new Response("Method not allowed",{status:405,headers:{Allow:"GET"}});
  if(!new URL(request.url).pathname.endsWith("/oauth-consent"))return new Response("Not found",{status:404});
  const nonce=crypto.randomUUID().replaceAll("-","");
  const csp="default-src 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'none'; "+
    "style-src 'nonce-"+nonce+"'; script-src 'nonce-"+nonce+"' https://cdn.jsdelivr.net; "+
    "connect-src https://hsztpgfgwlmnocealhcm.supabase.co https://cdn.jsdelivr.net; img-src 'none'";
  return new Response(HTML.replaceAll("__NONCE__",nonce),{status:200,headers:{
    "Content-Type":"text/html; charset=utf-8","Cache-Control":"no-store",
    "Referrer-Policy":"no-referrer","X-Frame-Options":"DENY",
    "X-Content-Type-Options":"nosniff","Content-Security-Policy":csp,
    "Permissions-Policy":"camera=(), microphone=(), geolocation=()"
  }});
});
