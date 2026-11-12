"""UI scale 100%-200%: first-run steps must scroll without hiding navigation."""
import os
import tempfile
import unittest
from unittest.mock import patch
import tkinter as tk

from public_gui import Onboarding

@unittest.skipUnless(os.name=="nt","Interactive Tk Windows desktop required")
@unittest.skipIf(os.environ.get("URM_CI_HEADLESS")=="1","Needs interactive desktop")
class OnboardingScaleTests(unittest.TestCase):
    def test_nav_visible_and_body_scrolls_at_large_dpi(self):
        with tempfile.TemporaryDirectory(prefix="urm-dpi-first-run-") as temp:
            with patch.dict(os.environ,{"LOCALAPPDATA":temp}):
                app=Onboarding()
                try:
                    app.geometry("760x605+25000+25000")
                    app.attributes("-alpha",0.0)
                    app.update()
                    app.tk.call("tk","scaling",2.0)
                    for step in range(5):
                        app.step=step;app._render();app.update()
                        self.assertTrue(hasattr(app,"_scroll_canvas"))
                        viewport=app._scroll_canvas
                        navigation=app.winfo_children()[-1]
                        self.assertGreater(navigation.winfo_height(),30)
                        self.assertLessEqual(
                            navigation.winfo_y()+navigation.winfo_height(),610,
                            f"Navigation inaccessible on step {step+1}")
                        extent=viewport.bbox("all")
                        self.assertIsNotNone(extent)
                        self.assertGreater(extent[3]-extent[1],0)
                        if extent[3]-extent[1] > viewport.winfo_height():
                            viewport.yview_moveto(1)
                            app.update_idletasks()
                            self.assertGreater(viewport.yview()[0],0,
                                               f"No scrolling available for step {step+1}")
                finally:
                    app.destroy()

if __name__=="__main__":unittest.main()
