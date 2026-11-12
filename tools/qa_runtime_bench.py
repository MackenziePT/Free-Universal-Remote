"""Disposable single-host stress and GUI responsiveness evidence (NOT universal performance certificate)."""
from __future__ import annotations
import json, os, sys, tempfile, time
from pathlib import Path
import psutil

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"evidence"/"qa"
QA.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT))
from native_jobs import TaskManager

results={}
with tempfile.TemporaryDirectory(prefix="urm-qa-stress-",dir=str(QA)) as temp:
    folder=Path(temp)
    workspace=folder/"workspace"
    workspace.mkdir()
    jobs=TaskManager(folder/"jobs",max_running=3)
    started=time.perf_counter()
    ids=[]
    try:
        for i in range(20):
            rec=jobs.start(sys.executable,["-c",f"print('TEST_PASS_{i}',flush=True)"],
                           str(workspace),label="QA disposable")
            ids.append((rec["job_id"],i))
            deadline=time.monotonic()+12
            while time.monotonic()<deadline:
                state=jobs.status(rec["job_id"])
                if state["state"] in ("exited","exited_unobserved","stopped"):break
                time.sleep(0.025)
            assert state["state"]=="exited" and state["exit_code"]==0, (i,state)
            output=jobs.output(rec["job_id"],0,4096)
            assert f"TEST_PASS_{i}" in output["text"],i
        results["task_stress"]={"jobs":len(ids),"success":len(ids),
                                 "duration_s":round(time.perf_counter()-started,3)}
    finally:
        for job_id,_ in ids:
            try:jobs.stop(job_id)
            except (OSError,KeyError):pass
        jobs.close()
    # This interpreter runs under a disposable LOCALAPPDATA and synthetic policy.
    state=folder/"private-state"
    state.mkdir()
    os.environ["LOCALAPPDATA"]=str(state)
    config=folder/"config.json"
    config.write_text(json.dumps({"allowed_roots":[str(workspace)],
                                  "grants_path":str(folder/"grants.json"),
                                  "backup_root":str(folder/"backups"),
                                  "enable_writes":False,"enable_shell":False,
                                  "enable_screen":False,"enable_input":False}),encoding="utf-8")
    os.environ["HARMONY_MCP_CONFIG"]=str(config)
    import universal_remote_ui as ui
    ui.STATE=state/"HarmonyRemoteMCP"
    start=time.perf_counter()
    app=ui.UniversalRemoteApp()
    try:
        app.withdraw()
        pages=("Início","Conexões","Acesso","Tarefas","Janelas","Atividade")
        for page in pages:
            app.show(page)
            app.update()
        duration=time.perf_counter()-start
        proc=psutil.Process(os.getpid())
        memory=proc.memory_info().rss / (1024*1024)
        cpu_before=proc.cpu_times()
        t0=time.monotonic()
        while time.monotonic()-t0<3:
            app.update()
            time.sleep(0.025)
        cpu_after=proc.cpu_times()
        cpu_s=(cpu_after.user+cpu_after.system)-(cpu_before.user+cpu_before.system)
        results["gui"]={"pages_tested":len(pages),
                        "first_window_plus_6_pages_s":round(duration,3),
                        "process_rss_mb":round(memory,2),
                        "cpu_seconds_during_3sec_idle":round(cpu_s,3)}
    finally:
        app.jobs.close()
        app.destroy()

(QA/"runtime-performance-local.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
print("STRESS_AND_LOCAL_PERFORMANCE_PASS",json.dumps(results))
