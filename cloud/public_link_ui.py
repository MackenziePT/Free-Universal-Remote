"""Owner-guided public pairing UI; no privileged action without native grants."""
from __future__ import annotations
import os, sys, queue, threading, subprocess
from pathlib import Path
import tkinter as tk
from .public_link import LinkConfig,LinkError,connect_windows,current_link_status
from .public_link_cli import configure_startup

BG="#101827"; PANEL="#172337"; FG="#eef4ff"; MUTED="#b9c6da"; RED="#e85353"

def start_agent():
    if getattr(sys,"frozen",False):cmd=[sys.executable,"--public-serve"]
    else:cmd=[sys.executable,"-m","cloud.public_link_cli","serve"]
    flags=(subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP) if sys.platform=="win32" else 0
    subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,creationflags=flags,close_fds=True,
                     cwd=str(Path(sys.executable).resolve().parent) if getattr(sys,"frozen",False)
                         else str(Path(__file__).resolve().parent.parent))

def show_public_link_window(parent):
    from .windows_identity import default_identity_path
    win=tk.Toplevel(parent)
    win.title("Universal Remote Free Unlimited — ligação pública")
    win.geometry("585x335")
    win.resizable(False,False)
    win.configure(bg=BG)
    q=queue.Queue()
    tk.Label(win,text="Ligar este PC ao ChatGPT",fg=FG,bg=BG,
             font=("Segoe UI",16,"bold")).pack(anchor="w",padx=23,pady=(21,10))
    tk.Label(win,text="Usa o navegador para confirmar a tua conta. A ligação é feita apenas "
              "de saída e as permissões do Windows continuam independentes.",
             justify="left",wraplength=510,bg=BG,fg=MUTED).pack(anchor="w",padx=23,pady=(0,12))
    msg=tk.StringVar(value="A verificar a configuração…")
    tk.Label(win,textvariable=msg,justify="left",wraplength=500,bg=PANEL,fg=FG,
             padx=12,pady=14).pack(fill="x",padx=23,pady=(0,14))
    auto=tk.BooleanVar(value=False)
    if getattr(sys,"frozen",False):
        tk.Checkbutton(win,text="Manter ligado quando iniciar sessão no Windows",
                       variable=auto,bg=BG,fg=FG,selectcolor=PANEL,
                       activebackground=BG,activeforeground=FG).pack(anchor="w",padx=23)
    buttons=tk.Frame(win,bg=BG);buttons.pack(anchor="w",padx=23,pady=(16,10))
    def launch():
        try:
            if auto.get():configure_startup(True,agreed=True)
            start_agent()
            msg.set("Agente iniciado. Pedidos remotos continuam sujeitos às autorizações locais.")
        except (OSError,LinkError):
            msg.set("Não foi possível iniciar o agente. Consulta a ajuda da aplicação.")
    def worker(config):
        try:
            label=(os.environ.get("COMPUTERNAME") or "Windows PC")[:48]
            device=connect_windows(config,label,note=lambda x:q.put(("note",x)))
            q.put(("paired",device))
        except (OSError,ValueError,LinkError) as ex:
            q.put(("error",str(ex)))
    def connect(config):
        btn.config(state="disabled")
        msg.set("Abre o navegador, introduz o código e confirma a ligação…")
        threading.Thread(target=worker,args=(config,),daemon=True,
                         name="universal-remote-public-pair").start()
    try:
        cfg=LinkConfig.from_env()
        if current_link_status(default_identity_path())["paired"]:
            msg.set("Este Windows já tem uma identidade emparelhada.")
            btn=tk.Button(buttons,text="Iniciar ligação",command=launch,
                          fg="white",bg=RED)
        else:
            msg.set("Pronto para autenticar e emparelhar o teu PC.")
            btn=tk.Button(buttons,text="Ligar ao ChatGPT",fg="white",bg=RED,
                          command=lambda:connect(cfg))
    except (OSError,LinkError):
        msg.set("A autenticação pública ainda não foi configurada pelo editor. "
                "O servidor está online, mas não pode aceitar emparelhamentos.")
        btn=tk.Button(buttons,text="Ligação pública indisponível",state="disabled")
    btn.pack(side="left",padx=(0,12))
    tk.Button(buttons,text="Fechar",fg=FG,bg=PANEL,command=win.destroy).pack(side="left")
    def updates():
        if not win.winfo_exists():return
        try:
            while True:
                kind,data=q.get_nowait()
                if kind=="note":msg.set(data)
                elif kind=="error":
                    msg.set("Falha de emparelhamento: "+data)
                    btn.config(state="normal")
                elif kind=="paired":
                    msg.set("Dispositivo emparelhado; a iniciar ligação segura…")
                    btn.config(state="normal",text="Iniciar ligação",command=launch)
                    launch()
        except queue.Empty:pass
        win.after(180,updates)
    win.after(180,updates)
    return win
