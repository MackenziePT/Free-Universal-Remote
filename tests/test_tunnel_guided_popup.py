import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from tunnel_setup_ui import show_tunnel_setup

@unittest.skipUnless(os.name=="nt" and os.environ.get("URM_CI_HEADLESS")!="1",
                      "Requires interactive Windows Tk")
class TunnelGuidedPopupTests(unittest.TestCase):
    def test_setup_window_is_scrollable_without_contacting_platform(self):
        with tempfile.TemporaryDirectory(prefix="urm-popup-") as temp:
            root=tk.Tk()
            root.withdraw()
            try:
                popup=show_tunnel_setup(
                    root,state=Path(temp)/"state",
                    agent=Path(temp)/"UniversalRemoteAgent-Preview.exe",
                    client=Path(temp)/"tunnel-client.exe",
                    sidecar=Path(temp)/"UniversalRemoteTunnel-Preview.exe")
                root.update_idletasks()
                self.assertIn("ChatGPT",popup.title())
                self.assertTrue(any(isinstance(x,tk.Canvas) for x in popup.winfo_children()))
                self.assertTrue(popup.winfo_exists())
                popup.destroy()
            finally:
                root.destroy()
