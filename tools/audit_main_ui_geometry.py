"""Offscreen Tk geometry audit, all six pages at 200% DPI, no screenshots."""
from __future__ import annotations
import json,os,sys,tempfile,tkinter as tk
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from universal_remote_ui import UniversalRemoteApp

def children(root):
    for item in root.winfo_children():
        yield item
        yield from children(item)

with tempfile.TemporaryDirectory(prefix="urm-mainui-visual-") as temp:
    root=Path(temp)
    work=root/"work";work.mkdir()
    config=root/"config.json"
    config.write_text(json.dumps({
        "allowed_roots":[str(work)],
        "backup_root":str(root/"backups"),
        "grants_path":str(root/"grants.json"),
    }),encoding="utf-8")
    with patch.dict(os.environ,{"HARMONY_MCP_CONFIG":str(config),"LOCALAPPDATA":temp}),\
         patch("universal_remote_ui.STATE",root/"UniversalRemote"),\
         patch("native_windows.window_list",return_value=[]):
        app=UniversalRemoteApp()
        try:
            app.geometry("1040x690+25000+25000")
            app.attributes("-alpha",0)
            app.tk.call("tk","scaling",2.0)
            app.update()
            report=[]
            for page in ("Início","Conexões","Acesso","Tarefas","Janelas","Atividade"):
                app.show(page);app.update()
                viewport=app.content_host
                left=viewport.winfo_rootx();top=viewport.winfo_rooty()
                right=left+viewport.winfo_width();bottom=top+viewport.winfo_height()
                controls=[]
                for w in children(viewport):
                    if isinstance(w,tk.Button):
                        x=w.winfo_rootx();y=w.winfo_rooty()
                        controls.append({
                            "label":w.cget("text")[:38],
                            "x":x-left,"y":y-top,"w":w.winfo_width(),"h":w.winfo_height(),
                            "inside_viewport":(
                                left<=x and x+w.winfo_width()<=right and
                                top<=y and y+w.winfo_height()<=bottom)
                        })
                report.append({"page":page,"viewport_px":[viewport.winfo_width(),viewport.winfo_height()],
                    "scrollable":app._content_canvas is not None,
                    "controls":controls})
            print("MAIN_UI_200PCT_GEOMETRY",json.dumps(report,ensure_ascii=False))
        finally:
            app.jobs.close()
            app.destroy()
