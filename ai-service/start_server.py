import os
import sys
import uvicorn
import socket

def start():
    try:
        print("🔍 [STARTUP] Initializing server...", flush=True)
        
        # 1. Get PORT from environment (Railway sets this)
        port_env = os.environ.get("PORT")
        print(f"🔍 [STARTUP] Detected PORT env var: {port_env}", flush=True)
        
        # 2. Default to 8080 if not set (local dev)
        # Note: Railway sets PORT, but sometimes it might be missing in local docker runs.
        port = int(port_env) if port_env else 8080
        host = "0.0.0.0"
        
        print(f"🚀 [STARTUP] Configured to listen on: {host}:{port}", flush=True)

        # 3. Import app (this loads the lifespan, etc.)
        print("🔍 [STARTUP] Importing FastAPI app...", flush=True)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app.main import app
        print("✅ [STARTUP] App imported successfully.", flush=True)

        # 4. Start Uvicorn
        print(f"🚀 [STARTUP] Starting Uvicorn now on {host}:{port}...", flush=True)
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            proxy_headers=True,
            forwarded_allow_ips="*"
        )
        
    except Exception as e:
        print(f"❌ [FATAL] Server startup failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    start()
