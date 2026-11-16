"""Standalone universal_remote_agent.exe entrypoint. Stdio only, no network listener."""
from __future__ import annotations
import os
import sys
from pathlib import Path

def main() -> int:
    # The owner-approved private tunnel signs per-device requests locally.
    # Normal local stdio and individually paired entrypoints remain unchanged.
    if sys.argv[1:] == ["--bridge-health-probe"]:
        from private_tunnel_bridge import configure_signed_private_tunnel
        print("UNIVERSAL_REMOTE_AGENT_PRIVATE_BRIDGE_HEALTH_OK")
        return 0
    if sys.argv[1:] in (["--bridge-enroll"], ["--tunnel-bridge"]):
        import private_tunnel_bridge as private_bridge
        sys.argv = [sys.argv[0]] + (["--enroll"] if sys.argv[1] == "--bridge-enroll" else [])
        return private_bridge.main()
    if sys.argv[1:] == ["--health-probe"]:
        # Sidecar update health only: no private state, no MCP permissions.
        import mcp
        import cryptography
        from secure_gateway import attach_secure_gateway
        print("UNIVERSAL_REMOTE_AGENT_HEALTH_OK")
        return 0
    from public_paths import product_home,config_path
    state=product_home()
    policy=config_path()
    if not policy.is_file():
        print("Universal Remote is not configured. Open the desktop app first.",file=sys.stderr)
        return 12
    os.environ["HARMONY_MCP_CONFIG"]=str(policy)
    os.environ["UNIVERSAL_REMOTE_DATA_HOME"]=str(state)
    os.environ.pop("CONTROL_PLANE_API_KEY",None)
    from server import mcp
    if sys.argv[1:] == ["--version"]:
        from server import ping
        print(ping())
        return 0
    if sys.argv[1:] == ["--paired"]:
        # Remote / multi-client entry point: all non-public tools require signed
        # per-device requests. Local stdio compatibility remains unchanged.
        from secure_gateway import attach_secure_gateway
        attach_secure_gateway(mcp, state / "security")
    elif len(sys.argv)>1:
        print("Unsupported argument",file=sys.stderr)
        return 2
    mcp.run(transport="stdio")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
