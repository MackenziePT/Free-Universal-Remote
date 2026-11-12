"""On-device pairing administrator for preview/read-only enrollment.

Privileged scopes remain disabled until independent Windows Hello presence
verification is implemented. Remote MCP exposes no admin approval endpoints.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import messagebox, simpledialog
from pathlib import Path
from device_pairing import PairingRegistry,PairingError

BG="#0A0F1D"
PANEL="#151F32"
FG="#EAF0FA"
MUTED="#9FB0C8"
ACCENT="#75D9FF"


def show_pairing_window(parent, state_dir: Path):
    registry = PairingRegistry(state_dir)
    window=tk.Toplevel(parent)
    window.title("Universal Remote — Dispositivos emparelhados")
    window.geometry("810x580")
    window.minsize(690,490)
    window.configure(bg=BG)
    window.transient(parent)
    tk.Label(window,text="Emparelhamento de dispositivos",
             bg=BG,fg=FG,font=("Segoe UI Semibold",17)).pack(anchor="w",padx=24,pady=(20,8))
    tk.Label(window,text=("Confirma a identidade do outro dispositivo antes de autorizar. "
                          "Nesta preview, novas ligações recebem apenas leitura. "
                          "As permissões de escrita/terminal/ecrã exigirão verificação "
                          "independente do proprietário (Windows Hello)."),
             bg=BG,fg=MUTED,justify="left",wraplength=745,
             font=("Segoe UI",10)).pack(anchor="w",padx=24,pady=(0,14))
    body=tk.Frame(window,bg=BG)
    body.pack(fill="both",expand=True,padx=24)
    pending_box=tk.Frame(body,bg=PANEL,padx=12,pady=12)
    pending_box.pack(fill="both",expand=True,pady=(0,10))
    tk.Label(pending_box,text="Pedidos pendentes (prova de chave confirmada)",
             bg=PANEL,fg=ACCENT,font=("Segoe UI",11,"bold")).pack(anchor="w")
    requests=tk.Listbox(pending_box,bg="#0A1222",fg=FG,selectbackground="#245070",
                        height=6,exportselection=False,font=("Consolas",10))
    requests.pack(fill="both",expand=True,pady=(8,9))
    devices_box=tk.Frame(body,bg=PANEL,padx=12,pady=12)
    devices_box.pack(fill="both",expand=True)
    tk.Label(devices_box,text="Dispositivos aprovados",
             bg=PANEL,fg=ACCENT,font=("Segoe UI",11,"bold")).pack(anchor="w")
    devices=tk.Listbox(devices_box,bg="#0A1222",fg=FG,selectbackground="#245070",
                       height=5,exportselection=False,font=("Consolas",10))
    devices.pack(fill="both",expand=True,pady=(8,9))
    controls=tk.Frame(window,bg=BG)
    controls.pack(fill="x",padx=24,pady=16)
    current_pending=[]
    current_devices=[]

    def refresh():
        nonlocal current_pending,current_devices
        current_pending=[item for item in registry.list_pending_local() if item["proved"]]
        current_devices=registry.list_devices_local()
        requests.delete(0,tk.END)
        for item in current_pending:
            requests.insert(tk.END,f'{item["label"][:24]:24}  chave: {item["fingerprint"]}')
        devices.delete(0,tk.END)
        for item in current_devices:
            state="REVOGADO" if item["revoked"] is not None else "ATIVO"
            devices.insert(tk.END,
               f'{item["label"][:20]:20} {state:8}  {item["fingerprint"]}  {",".join(item["scopes"])}')

    def approve():
        chosen=requests.curselection()
        if not chosen:
            messagebox.showinfo("Emparelhamento","Seleciona primeiro um pedido.",parent=window)
            return
        req=current_pending[chosen[0]]
        fingerprint=req["fingerprint"]
        confirm=simpledialog.askstring("Confirmação de identidade",
               ("Confirma presencialmente o identificador de chave no outro dispositivo.\n"
                "Escreve os últimos 8 caracteres deste identificador:\n"
                f"{fingerprint}"),parent=window)
        if confirm != fingerprint[-8:]:
            messagebox.showwarning("Não aprovado","O identificador não foi confirmado.",
                                   parent=window)
            return
        if not messagebox.askyesno("Aprovação de dispositivo",
          "Aprovar apenas leitura para este dispositivo?\n\n"
          "Nenhum comando, alteração ou captura será autorizado nesta fase.",
          parent=window):
            return
        try:
            registry.approve_local(req["request_id"],{"read"},presence_confirmed=True)
        except (PairingError,OSError) as ex:
            messagebox.showerror("Aprovação recusada",str(ex),parent=window)
        refresh()

    def revoke():
        selection=devices.curselection()
        if not selection:
            return
        item=current_devices[selection[0]]
        if not messagebox.askyesno("Revogar dispositivo",
                    f'Revogar acesso de {item["label"]}?\nA revogação é imediata para novos pedidos.',
                    parent=window):
            return
        try:
            registry.revoke_local(item["client_id"])
        except (PairingError,OSError) as ex:
            messagebox.showerror("Falha na revogação",str(ex),parent=window)
        refresh()

    def btn(label,callback):
        tk.Button(controls,text=label,command=callback,bg="#233C56",fg=FG,
                  activebackground="#315E7A",relief="flat",padx=14,pady=9,
                  font=("Segoe UI",10)).pack(side="left",padx=(0,9))
    btn("Atualizar lista",refresh)
    btn("Aprovar leitura",approve)
    btn("Revogar selecionado",revoke)
    btn("Fechar",window.destroy)
    refresh()
    return window
