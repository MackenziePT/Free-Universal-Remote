"""Measure actual first-run page size against a laptop-sized window under DPI scaling."""
import json,os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from public_gui import Onboarding
with tempfile.TemporaryDirectory(prefix="urm-ux-dpi-") as tmp:
    os.environ["LOCALAPPDATA"]=tmp
    app=Onboarding()
    app.withdraw()
    report=[]
    try:
        for dpi in (1.0,1.333,1.5,2.0):
            app.tk.call("tk","scaling",dpi)
            for i in range(5):
                app.step=i; app._render(); app.update_idletasks()
                frame_heights=[widget.winfo_reqheight() for widget in app.winfo_children()]
                required=sum(frame_heights)
                report.append({
                    "tk_scaling":dpi,"step":i+1,
                    "content_req_px":frame_heights,
                    "total_req_px":required,
                    "configured_window_px":605,
                    "clipped_at_default_height":required>605,
                })
    finally:app.destroy()
print("UX_DPI_LAYOUT_REPORT",json.dumps(report,ensure_ascii=False))
print("CLIPPED_CASES",sum(x["clipped_at_default_height"] for x in report))
