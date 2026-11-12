"""Main application: scroll-heavy panels stay accessible at 200% DPI.

No real desktop input; private ephemeral state, UI runs off-screen.
"""
from __future__ import annotations
import json,os,tempfile,tkinter as tk,unittest
from pathlib import Path
from unittest.mock import patch

from universal_remote_ui import UniversalRemoteApp

@unittest.skipUnless(os.name=="nt","Interactive Windows Tk")
@unittest.skipIf(os.environ.get("URM_CI_HEADLESS")=="1","Needs an interactive desktop")
class MainUiDpiTests(unittest.TestCase):
    def test_static_pages_remain_scrollable_at_200pct_and_native_panels_work(self):
        with tempfile.TemporaryDirectory(prefix="urm-mainui-dpi-") as temp:
            work=Path(temp)/"workspace";work.mkdir()
            cfg=Path(temp)/"config.json"
            cfg.write_text(json.dumps({
                "allowed_roots":[str(work)],
                "backup_root":str(Path(temp)/"backups"),
                "grants_path":str(Path(temp)/"grants.json")
            }),encoding="utf-8")
            with patch.dict(os.environ,{"HARMONY_MCP_CONFIG":str(cfg),"LOCALAPPDATA":temp}),\
                 patch("universal_remote_ui.STATE",Path(temp)/"UniversalRemote"):
                app=UniversalRemoteApp()
                try:
                    app.geometry("1040x690+25000+25000")
                    app.attributes("-alpha",0)
                    app.update()
                    app.tk.call("tk","scaling",2.0)
                    for page in ("Início","Conexões","Acesso"):
                        app.show(page)
                        app.update()
                        with self.subTest(page=page):
                            self.assertIsNotNone(app._content_canvas,
                                    "Static panel must scroll at high DPI")
                            viewport=app._content_canvas
                            self.assertGreater(viewport.winfo_height(),60)
                            bounds=viewport.bbox("all")
                            self.assertIsNotNone(bounds)
                            height=bounds[3]-bounds[1]
                            if height>viewport.winfo_height():
                                viewport.yview_moveto(1)
                                app.update_idletasks()
                                self.assertGreater(viewport.yview()[0],0)
                            self.assertGreater(app.nav_buttons["Conexões"].winfo_width(),75)
                    app.tk.call("tk","scaling",2.0)
                    for page in ("Tarefas","Janelas","Atividade"):
                        app.show(page)
                        app.update()
                        self.assertIsNone(app._content_canvas)
                        if page=="Atividade":
                            def descendants(widget):
                                for child in widget.winfo_children():
                                    yield child
                                    yield from descendants(child)
                            controls=[w for w in descendants(app.content_host)
                                      if isinstance(w,tk.Button) and w.cget("text")=="Atualizar"]
                            self.assertEqual(len(controls),1)
                            button=controls[0]
                            self.assertGreater(button.winfo_width(),55,
                                "Refresh button collapsed to an unusable width")
                            limit=app.content_host.winfo_rooty()+app.content_host.winfo_height()
                            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),limit,
                                "Refresh button must remain visible at 200% DPI")
                finally:
                    app.jobs.close()
                    app.destroy()

if __name__=="__main__":unittest.main()
