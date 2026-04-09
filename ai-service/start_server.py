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
        print("🔍 [STARTUP] Initializing server script...", flush=True)
        
        # 1. Get PORT from environment (Railway sets this)
        port_env = os.environ.get("PORT")
        print(f"🔍 [STARTUP] Environment PORT: '{port_env}'", flush=True)
        
        # 2. Default to 8000 if not set
        if not port_env or not port_env.strip():
            print("⚠️ [STARTUP] PORT env var is empty or missing. Defaulting to 8000.", flush=True)
            port = 8000
        else:
            try:
                port = int(port_env)
            except ValueError:
                print(f"❌ [STARTUP] PORT env var is not a number: '{port_env}'. Defaulting to 8000.", flush=True)
                port = 8000
                
        host = "0.0.0.0"
        workers_env = os.environ.get("UVICORN_WORKERS", "1")
        try:
            workers = max(1, int(workers_env))
        except ValueError:
            print(f"⚠️ [STARTUP] UVICORN_WORKERS is invalid: '{workers_env}'. Defaulting to 1.", flush=True)
            workers = 1

        print(f"🚀 [STARTUP] Configured listener: {host}:{port}", flush=True)
        print(f"🚀 [STARTUP] Configured workers: {workers}", flush=True)

        # 3. Check if we can bind to this port (Diagnostic)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.close()
            print(f"✅ [STARTUP] Port {port} is available for binding.", flush=True)
        except Exception as bind_e:
            print(f"⚠️ [STARTUP] Potential port conflict or bind issue on {port}: {bind_e}", flush=True)

        # 4. Import app (this loads the lifespan, etc.)
        print("🔍 [STARTUP] Importing FastAPI app from app/main.py...", flush=True)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            from app.main import app
            print(f"✅ [STARTUP] App object loaded: {id(app)}", flush=True)
        except Exception as imp_e:
            print(f"❌ [STARTUP] Failed to import app: {imp_e}", flush=True)
            raise imp_e

        # ===============================
        # DIAGNOSTICS: HEARTBEAT THREAD
        # ===============================
        def heartbeat():
            """Background thread to log memory usage and aliveness."""
            print("💓 [HEARTBEAT] Diagnostic thread started.", flush=True)
            while True:
                try:
                    timestamp = datetime.datetime.now().isoformat()
                    mem_str = "N/A"
                    if resource:
                        mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        mem_str = f"{mem_kb / 1024:.1f} MB"
                    
                    # Also log if startup error is set
                    try:
                        from app.core import startup
                        ready = startup.index is not None and startup.session is not None
                        err = getattr(startup, 'LOADING_ERROR', None)
                        status = "READY" if ready else ("ERROR" if err else "LOADING")
                    except:
                        status = "UNKNOWN"

                    print(f"💓 [HEARTBEAT] {timestamp} | RAM: {mem_str} | Status: {status} | Host: {host}:{port}", flush=True)
                except Exception as hb_e:
                    print(f"⚠️ [HEARTBEAT] Diagnostic error: {hb_e}", flush=True)
                
                time.sleep(5) # 5s is plenty

        hb_thread = threading.Thread(target=heartbeat, daemon=True)
        hb_thread.start()
        # ===============================

        # 5. Start Uvicorn
        print(f"🚀 [STARTUP] Launching Uvicorn on {host}:{port}...", flush=True)
        # Using string import to allow uvicorn to handle the import chain better if needed
        # but here we already have the app object.
        app_target = "app.main:app" if workers > 1 else app

        uvicorn.run(
            app_target,
            host=host,
            port=port,
            log_level="info",
            proxy_headers=True,
            forwarded_allow_ips="*",
            timeout_keep_alive=30,
            access_log=True, # Ensure access logs are ON
            workers=workers
        )
        
    except BaseException as e:
        print(f"❌ [FATAL] Server startup failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    start()
