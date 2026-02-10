import os
import sys
import uvicorn
import socket

import threading
import time
import datetime

# Try to import resource for memory usage (Linux/Mac)
try:
    import resource
except ImportError:
    resource = None

# OPTIMIZATION: Reduce thread overhead for single-core environments
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

def start():
    try:
        print("🔍 [STARTUP] Initializing server...", flush=True)
        
        # 1. Get PORT from environment (Railway sets this)
        port_env = os.environ.get("PORT")
        print(f"🔍 [STARTUP] Detected PORT env var: {port_env}", flush=True)
        
        # 2. Default to 8080 if not set (local dev)
        # Note: Railway sets PORT, but sometimes it might be missing in docker runs.
        port = int(port_env) if port_env else 8080
        host = "0.0.0.0"
        
        print(f"🚀 [STARTUP] Configured to listen on: {host}:{port}", flush=True)

        # 3. Import app (this loads the lifespan, etc.)
        print("🔍 [STARTUP] Importing FastAPI app...", flush=True)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app.main import app
        print("✅ [STARTUP] App imported successfully.", flush=True)

        # ===============================
        # DIAGNOSTICS: HEARTBEAT THREAD
        # ===============================
        def heartbeat():
            """Background thread to log memory usage and aliveness."""
            print("💓 [HEARTBEAT] Thread starting...", flush=True)
            while True:
                try:
                    timestamp = datetime.datetime.now().isoformat()
                    mem_str = "N/A"
                    
                    # Linux resource usage (in KB)
                    if resource:
                        mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        # On Linux, ru_maxrss is in KB. On Mac, bytes. Assume Linux (Railway).
                        mem_mb = mem_kb / 1024
                        mem_str = f"{mem_mb:.1f} MB"
                    
                    print(f"💓 [HEARTBEAT] {timestamp} | RAM: {mem_str} | Status: ALIVE", flush=True)
                except Exception as hb_e:
                    print(f"⚠️ [HEARTBEAT] Error: {hb_e}", flush=True)
                
                time.sleep(2)

        hb_thread = threading.Thread(target=heartbeat, daemon=True)
        hb_thread.start()
        # ===============================

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
        
    except BaseException as e:
        print(f"❌ [FATAL] Server crashed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    start()
