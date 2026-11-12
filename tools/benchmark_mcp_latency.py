"""Measure actual MCP stdio latency, throughput, payload throughput, startup time.

This is a nonprivileged isolated benchmark with disposable config and read-only calls.
No writes are performed through the agent, no OS settings altered.
"""
from __future__ import annotations
import asyncio
from datetime import timedelta
import json,os,statistics,sys,tempfile,time
from pathlib import Path

from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FROZEN="--frozen" in sys.argv
OUT=ROOT/"evidence"/"qa"/("mcp-latency-frozen.json" if FROZEN else "mcp-latency-source.json")

def stats(values):
    values=sorted(values)
    if not values:return {}
    return {
        "n":len(values),
        "p50_ms":round(statistics.median(values)*1000,3),
        "p95_ms":round(values[min(len(values)-1,int(len(values)*.95))]*1000,3),
        "max_ms":round(values[-1]*1000,3)
    }

async def once(client,name,args):
    start=time.perf_counter()
    result=await client.call_tool(name,args)
    if result.isError:raise RuntimeError("Bench call failed "+name)
    return time.perf_counter()-start,result

async def main():
    with tempfile.TemporaryDirectory(prefix="urm-stdio-perf-") as temp:
        home=Path(temp)
        root=home/"work";root.mkdir()
        sample=root/"sample.txt"
        sample.write_text("ABCDEFá🌿012345\n"*2600,encoding="utf-8")
        cfg=home/"config.json"
        cfg.write_text(json.dumps({
            "allowed_roots":[str(root)],
            "backup_root":str(home/"backups"),
            "grants_path":str(home/"grants.json"),
            "enable_shell":False,"enable_writes":False,
            "enable_screen":False,"enable_input":False
        }),encoding="utf-8")
        if FROZEN:
            from unittest.mock import patch
            from public_paths import write_initial_config
            with patch.dict(os.environ,{"LOCALAPPDATA":str(home)}):
                write_initial_config(root)
            binary=ROOT/"evidence"/"qa"/"public-portable-prototype"/"UniversalRemoteAgent-Preview"/"UniversalRemoteAgent-Preview.exe"
            if not binary.is_file():
                raise RuntimeError("Frozen agent missing: rebuild first")
            env={"LOCALAPPDATA":str(home),"PATH":os.path.join(os.environ["SystemRoot"],"System32")}
            params=StdioServerParameters(command=str(binary),args=[],env=env)
        else:
            env={"HARMONY_MCP_CONFIG":str(cfg),"LOCALAPPDATA":str(home)}
            params=StdioServerParameters(command=sys.executable,
                                        args=[str(ROOT/"launch_server.py")],env=env)
        startup=time.perf_counter()
        async with stdio_client(params) as (reader,writer):
            async with ClientSession(reader,writer,
                             read_timeout_seconds=timedelta(seconds=50)) as client:
                await client.initialize()
                t_ready=time.perf_counter()
                # Isolate server hot request path from startup and first-request effects.
                for _ in range(10):await once(client,"ping",{})
                latency=[]
                for _ in range(120):
                    elapsed,_=await once(client,"ping",{})
                    latency.append(elapsed)
                concurrency=8
                semaphore=asyncio.Semaphore(concurrency)
                async def worker(index):
                    async with semaphore:
                        elapsed,_=await once(client,"ping",{})
                        return elapsed
                start=time.perf_counter()
                burst=await asyncio.gather(*(worker(i) for i in range(180)))
                wall=time.perf_counter()-start
                byte_calls=[]
                payload_bytes=0
                read_wall_start=time.perf_counter()
                for _ in range(70):
                    elapsed,result=await once(client,"read_text_file",{
                        "path":str(sample),"offset":0,"max_bytes":16384})
                    body=json.loads(next(c.text for c in result.content if c.type=="text"))
                    payload_bytes+=body["returned_bytes"]
                    byte_calls.append(elapsed)
                read_wall=time.perf_counter()-read_wall_start
                report={
                    "scope":"Local MCP stdio disposable read-only benchmark on ASUS; not cross-platform",
                    "deployment":"frozen executable" if FROZEN else "Python source",
                    "startup_ms":round((t_ready-startup)*1000,2),
                    "ping_sequential":stats(latency),
                    "ping_burst_concurrency":concurrency,
                    "ping_burst_requests":len(burst),
                    "ping_burst":stats(burst),
                    "ping_burst_wall_s":round(wall,4),
                    "ping_burst_throughput_ops_s":round(len(burst)/wall,1),
                    "read_text_16KiB":stats(byte_calls),
                    "read_text_returned_mib":round(payload_bytes/(1024*1024),2),
                    "read_text_payload_mib_s":round(payload_bytes/(1024*1024)/read_wall,2),
                }
                OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
                print("MCP_ISOLATED_BENCHMARK",json.dumps(report,ensure_ascii=False),flush=True)

if __name__=="__main__":
    asyncio.run(main())
