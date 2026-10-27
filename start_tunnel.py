"""
StockAI 1-Click Mobile Live Tunnel Assistant
Automatically starts backend (if not running) and launches Cloudflare secure tunnel.
"""
import os
import sys
import time
import socket
import subprocess
import re

PORT = 8000
BACKEND_URL = f"http://127.0.0.1:{PORT}"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLOUDFLARED_EXE = os.path.join(SCRIPT_DIR, "cloudflared.exe")

def is_backend_running():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1.0):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def copy_to_clipboard(text):
    try:
        proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
        proc.communicate(text.encode("utf-8"))
    except Exception:
        pass

def main():
    print("=" * 65)
    print("           StockAI - 1-Click Mobile Live Assistant")
    print("=" * 65)
    print()

    # 1. Check / Start Backend
    if is_backend_running():
        print(f"[*] StockAI Python Backend is already running on port {PORT}.")
    else:
        print("[*] Starting StockAI Python Backend server...")
        py_exe = sys.executable
        run_app_path = os.path.join(SCRIPT_DIR, "run_app.py")
        subprocess.Popen(
            [py_exe, run_app_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        )
        print("[*] Waiting for backend to initialize...", end="", flush=True)
        for _ in range(15):
            time.sleep(1)
            if is_backend_running():
                print(" Ready!")
                break
            print(".", end="", flush=True)
        else:
            print("\n[!] Warning: Backend initialization timed out. Proceeding with tunnel...")

    # 2. Check cloudflared.exe
    if not os.path.isfile(CLOUDFLARED_EXE):
        print(f"[!] Error: cloudflared.exe not found at {CLOUDFLARED_EXE}")
        input("Press Enter to exit...")
        return

    # 3. Launch Cloudflare Tunnel
    print("[*] Connecting to Cloudflare global secure network...")
    cmd = [CLOUDFLARED_EXE, "tunnel", "--url", BACKEND_URL]
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    tunnel_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")

    for line in proc.stdout:
        match = url_pattern.search(line)
        if match:
            tunnel_url = match.group(0)
            break
        if "ERR" in line or "error" in line.lower():
            if "failed" in line.lower():
                print(f"[!] Tunnel Notice: {line.strip()}")

    if tunnel_url:
        copy_to_clipboard(tunnel_url)
        print()
        print("+" + "-" * 63 + "+")
        print("|  SUCCESS! Your 24/7 Mobile Cloud Link is LIVE (SSL Encrypted) |")
        print("+" + "-" * 63 + "+")
        print()
        print(f"  >>>  {tunnel_url}  <<<")
        print()
        print("  [Copied to Clipboard automatically! / క్లిప్‌బోర్డ్‌కి కాపీ అయింది!]")
        print()
        print("  1. Mee Phone lo 'StockAI-bot.apk' open cheyyandi.")
        print("  2. Kindha 'Settings' tab meeda click cheyyandi.")
        print("  3. 'Bot Backend Connection' lo ee URL paste chesi 'Save' nokkandi!")
        print()
        print("  (Also works directly in any Phone Browser like Chrome!)")
        print("+" + "-" * 63 + "+")
        print()
        print("[*] Tunnel active. Keep this window open. Press Ctrl+C to stop.")
    else:
        print("[!] Could not parse tunnel URL. Cloudflare logs:")

    try:
        for line in proc.stdout:
            # Silence repetitive metrics logs, print important notices
            if "metrics" not in line.lower() and "retrying" not in line.lower():
                pass
    except KeyboardInterrupt:
        print("\n[*] Stopping Cloudflare tunnel...")
        proc.terminate()

if __name__ == "__main__":
    main()
