"""
StockAI Launcher
Detects LAN IP address, starts FastAPI server, and launches browser.
"""
import socket
import sys
import webbrowser
import uvicorn

# Configure UTF-8 encoding for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")



def get_local_ip():
    """Retrieve machine's LAN IP address for phone connection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000

    print("=" * 65)
    print("      🚀 STOCKAI - 15m PATTERN & NEWS SENTIMENT BOT")
    print("=" * 65)
    print(f"[*] Local PC URL:      http://localhost:{port}")
    print(f"[*] Android Phone URL: http://{local_ip}:{port}")
    print("=" * 65)
    print("Tip: Open the Android Phone URL in Chrome on your phone")
    print("     and tap 'Add to Home Screen' to use it as an Android App!")
    print("=" * 65)
    print("[*] Starting backend engine & WebSocket server...\n")

    # Automatically launch browser on PC
    webbrowser.open(f"http://localhost:{port}")

    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)
