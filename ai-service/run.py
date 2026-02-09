import os
import uvicorn
import sys

if __name__ == "__main__":
    try:
        # Get PORT from environment, default to 8000
        port = int(os.environ.get("PORT", 8000))
        print(f"🚀 Starting AI Service on port {port}...")
        
        # Start uvicorn
        uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)
