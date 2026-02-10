import os
import sys
import uvicorn
import socket

if __name__ == "__main__":
    try:
        print("🔍 [RUN] Starting initialization...")
        
        # 1. Print Environment Info
        port_env = os.environ.get("PORT")
        print(f"🔍 [RUN] Env PORT: {port_env}")
        
        # 2. Determine Port
        port = int(port_env) if port_env else 8080
        print(f"🚀 [RUN] Selected Port: {port}")

        # 3. Check Binding ability
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('0.0.0.0', port))
        if result == 0:
            print(f"⚠️ [RUN] WARNING: Port {port} seems to be in use already!")
        sock.close()

        # 4. Explicit Import Test
        print("🔍 [RUN] Attempting to import app.main...")
        from app.main import app
        print("✅ [RUN] Successfully imported app.main")

        # 5. Start Uvicorn
        print(f"🚀 [RUN] Starting Uvicorn on 0.0.0.0:{port}...")
        uvicorn.run(
            app,  # Pass app object directly
            host="0.0.0.0", 
            port=port, 
            log_level="info",
            proxy_headers=True,
            forwarded_allow_ips="*"
        )
        
    except Exception as e:
        print(f"❌ [FATAL] Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
