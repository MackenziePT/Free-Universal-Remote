"""Guided setup for the private tunnel; no terminal or key on command line."""
from __future__ import annotations
from pathlib import Path
import socket
import threading
import tkinter as tk
from tkinter import messagebox
import webbrowser

from tunnel_manager import (
    TunnelConfigError, autostart_enabled, is_provisioned, profile_path, provision_profile,
    read_status, request_stop, set_autostart, spawn_supervisor
)

BG="#0A0F1D"
PANEL="#151F32"
FG="#EAF0FA"
MUTED="#9FB0C8"
ACCENT="#75D9FF"

def _local_port_occupied(port=8080)->bool:
    """Prevent conflict with a previous active tunnel client; never kill it."""
    try:
        with socket.create_connection(("127.0.0.1",port),timeout=0.45):
            return True
    except OSError:
        return False

def show_tunnel_setup(parent, *, state:Path, agent:Path, client:Path, sidecar:Path):
    window=tk.Toplevel(parent)
    window.title("Universal Remote — Ligar ao ChatGPT")
    window.geometry("720x680")
    window.minsize(650,600)
    window.configure(bg=BG)
    window.transient(parent)
    # Scrollable content also works on small laptop screens and high DPI.
    canvas=tk.Canvas(window,bg=BG,highlightthickness=0)
    scrollbar=tk.Scrollbar(window,orient="vertical",command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right",fill="y")
    canvas.pack(side="left",fill="both",expand=True)
    content=tk.Frame(canvas,bg=BG)
    content_window=canvas.create_window((0,0),window=content,anchor="nw")
    content.bind("<Configure>",lambda event:canvas.configure(
        scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>",lambda event:canvas.itemconfigure(
        content_window,width=event.width))
    state=Path(state)
    busy={"value":False}
    is_active={"value":True}

    def label(text,*,size=10,color=FG,weight="normal"):
        widget=tk.Label(content,text=text,bg=BG,fg=color,
                        font=("Segoe UI",size,weight),wraplength=655,justify="left")
        widget.pack(anchor="w",padx=22,pady=(4,6))
        return widget

    def button(text,func,*,enabled=True):
        b=tk.Button(content,text=text,command=func,
                    bg="#24455F",fg=FG,activebackground="#356D89",
                    relief="flat",font=("Segoe UI",10),padx=12,pady=7,
                    state="normal" if enabled else "disabled")
        b.pack(anchor="w",padx=22,pady=(3,6))
        return b

    label("Ligar ao ChatGPT — configuração guiada",size=17,weight="bold")
    label("É necessária uma associação oficial no ChatGPT. O Universal Remote trata "
          "do funcionamento local e da reconexão; nunca recebe a tua palavra-passe do ChatGPT.",
          color=MUTED)
    label("1. Obtém o identificador do túnel e uma chave de utilização na plataforma OpenAI.",
          weight="bold")

    def open_tunnels():
        webbrowser.open("https://platform.openai.com/settings/organization/tunnels")
    def open_keys():
        webbrowser.open("https://platform.openai.com/settings/organization/api-keys")
    def open_chatgpt():
        webbrowser.open("https://chatgpt.com/")
    button("Abrir os meus túneis na OpenAI",open_tunnels)
    button("Abrir as minhas chaves na OpenAI",open_keys)
    label("2. Cola os dados abaixo uma única vez. A chave é protegida pelo Windows e "
          "não fica no ficheiro de configuração do túnel.",weight="bold")
    field=tk.Frame(content,bg=BG)
    field.pack(fill="x",padx=22,pady=(4,6))
    tk.Label(field,text="Identificador do túnel",bg=BG,fg=MUTED,
             font=("Segoe UI",10)).pack(anchor="w")
    tunnel=tk.StringVar()
    receipt=state/"tunnel-profile.json"
    if receipt.is_file():
        try:
            import json
            saved=json.loads(receipt.read_text(encoding="utf-8"))
            if isinstance(saved.get("tunnel_id"),str):
                tunnel.set(saved["tunnel_id"])
        except (ValueError,OSError):
            pass
    tk.Entry(field,textvariable=tunnel,fg=FG,bg="#101D30",insertbackground=FG,
             relief="flat",font=("Consolas",10)).pack(fill="x",ipady=7,pady=(2,8))
    tk.Label(field,text="Chave privada de utilização",bg=BG,fg=MUTED,
             font=("Segoe UI",10)).pack(anchor="w")
    password=tk.StringVar()
    secret_field=tk.Entry(field,textvariable=password,show="•",fg=FG,bg="#101D30",
                          insertbackground=FG,relief="flat",font=("Segoe UI",10))
    secret_field.pack(fill="x",ipady=7,pady=(2,6))
    visible=tk.BooleanVar(value=False)
    tk.Checkbutton(field,text="Mostrar a chave enquanto colo",
                   variable=visible,command=lambda:secret_field.configure(
                       show="" if visible.get() else "•"),
                   bg=BG,fg=MUTED,selectcolor="#101D30",activebackground=BG,
                   activeforeground=FG).pack(anchor="w")
    autostart=tk.BooleanVar(value=autostart_enabled(sidecar))
    tk.Checkbutton(content,text="Manter a ligação disponível após iniciar o Windows (opcional)",
                   variable=autostart,bg=BG,fg=MUTED,selectcolor="#101D30",
                   activebackground=BG,activeforeground=FG,
                   font=("Segoe UI",10)).pack(anchor="w",padx=22,pady=(3,7))
    consent=tk.BooleanVar(value=False)
    tk.Checkbutton(content,text="Autorizo a guardar esta chave na minha conta Windows "
                               "e a iniciar uma ligação privada de saída",
                   variable=consent,bg=BG,fg=FG,selectcolor="#101D30",
                   activebackground=BG,activeforeground=FG,
                   font=("Segoe UI",10)).pack(anchor="w",padx=22,pady=(5,9))
    status=label("Estado: ainda não ligado. A RC5.0 existente não será interrompida.",
                 size=10,color=ACCENT)
    def update():
        if not is_active["value"] or not window.winfo_exists():return
        result=read_status(state)
        if is_provisioned(state):
            msg=result["detail"]
            if result["code"]=="UNKNOWN":
                msg="Túnel configurado, sem ligação local confirmada. Podes iniciá-lo."
            status.configure(text="Estado: "+msg)
        window.after(2500,update)

    def start():
        if _local_port_occupied():
            messagebox.showwarning("Outra ligação em execução",
                "Já existe uma ligação a utilizar a porta local do cliente. "
                "Não vou interrompê-la nem abrir outra em paralelo. "
                "Podes continuar a utilizar a ligação atual.",parent=window)
            return
        try:
            spawn_supervisor(sidecar)
            status.configure(text="A iniciar o túnel em segundo plano...")
        except (TunnelConfigError,OSError):
            messagebox.showerror("Não foi possível iniciar",
                "Verifica se o Universal Remote está corretamente instalado. "
                "Não precisas de desativar o antivírus.",parent=window)

    def configure():
        if busy["value"]:return
        if not consent.get():
            messagebox.showinfo("Confirmação necessária",
                  "Para continuar, confirma que pretendes guardar a chave e iniciar "
                  "esta ligação privada.",parent=window)
            return
        tid=tunnel.get().strip()
        value=password.get().strip()
        busy["value"]=True
        connect_btn.configure(state="disabled")
        status.configure(text="A configurar de forma segura...")
        def worker():
            try:
                provision_profile(tid,value,state,agent,client)
                outcome=None
            except (TunnelConfigError,OSError,ValueError):
                outcome="Não foi possível configurar a ligação. Confirma o identificador "
                outcome+="e a chave na plataforma OpenAI. Nenhuma permissão foi concedida."
            def complete():
                if not is_active["value"] or not window.winfo_exists():return
                password.set("")
                busy["value"]=False
                connect_btn.configure(state="normal")
                if outcome:
                    status.configure(text=outcome)
                else:
                    try:
                        set_autostart(sidecar,autostart.get())
                        status.configure(text="Chave guardada de forma protegida. "
                                            "A preferência de arranque foi guardada.")
                    except (TunnelConfigError,OSError):
                        status.configure(text="Chave guardada. Não foi possível aplicar "
                                            "a preferência de arranque do Windows.")
                    start()
            window.after(0,complete)
        threading.Thread(target=worker,daemon=True,name="urm-tunnel-configure").start()

    label("3. Depois de iniciares o túnel, abre ChatGPT → Plugins → + → "
          "Adicionar servidor MCP personalizado → Túnel. "
          "Confirma a ligação e as permissões na própria conta ChatGPT.",weight="bold")
    connect_btn=button("Guardar e iniciar ligação",configure)
    button("Iniciar ligação já configurada",start)
    def stop():
        if not messagebox.askyesno("Parar ligação",
                  "Parar apenas o túnel desta instalação Universal Remote?",
                  parent=window):return
        request_stop(state)
        status.configure(text="Pedido de paragem enviado. O processo terminará com segurança.")
    button("Parar esta ligação",stop)
    button("Abrir ChatGPT para concluir associação",open_chatgpt)
    window.protocol("WM_DELETE_WINDOW",lambda:(is_active.update(value=False),window.destroy()))
    update()
    return window
