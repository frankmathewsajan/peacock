import os
import subprocess
import socket
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

# --- WINDOWS KERNEL FLAGS FOR STEALTH EXECUTION ---
DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000


def get_local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"


def is_peacock_running() -> bool:
    """Checks the Windows task list silently to see if the daemon is active."""
    try:
        output = subprocess.check_output(
            'tasklist /FI "IMAGENAME eq peacock.exe"',
            shell=True,
            creationflags=CREATE_NO_WINDOW,
        ).decode()
        return "peacock.exe" in output
    except Exception:
        return False


# --- SHADCN-STYLE FRONTEND HTML ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Peacock Overseer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        body { background-color: #f8fafc; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
        .shadcn-card { background: white; border: 1px solid #e2e8f0; border-radius: 0.75rem; box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1); }
        .btn { transition: all 0.2s; display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; font-weight: 500; font-size: 0.875rem; padding: 0.5rem 1rem; border-radius: 0.375rem; outline: none; }
        .btn:active { transform: scale(0.98); }
        .btn-primary { background-color: #0f172a; color: white; }
        .btn-primary:hover { background-color: #1e293b; }
        .btn-destructive { background-color: #ef4444; color: white; }
        .btn-destructive:hover { background-color: #dc2626; }
        .btn-disabled { background-color: #cbd5e1; color: #64748b; cursor: not-allowed; pointer-events: none; }
    </style>
</head>
<body class="min-h-screen flex items-center justify-center p-4">

    <div class="shadcn-card w-full max-w-sm p-6">
        <div class="flex items-center justify-between mb-6">
            <div>
                <h1 class="text-xl font-semibold tracking-tight text-slate-900">Peacock Overseer</h1>
                <p class="text-sm text-slate-500 mt-1">Companion Mode Daemon</p>
            </div>
            <div class="p-2 bg-slate-100 rounded-full">
                <i data-lucide="cpu" class="w-5 h-5 text-slate-600"></i>
            </div>
        </div>

        <div class="flex items-center justify-between p-4 mb-6 border border-slate-100 rounded-lg bg-slate-50">
            <span class="text-sm font-medium text-slate-700">System Status</span>
            <div id="status-badge" class="flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-200 text-slate-600">
                <span id="status-dot" class="w-2 h-2 rounded-full bg-slate-400"></span>
                <span id="status-text">Checking...</span>
            </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
            <button id="btn-start" class="btn btn-primary btn-disabled" onclick="sendCommand('start')">
                <i data-lucide="play" class="w-4 h-4"></i> Start HUD
            </button>
            <button id="btn-stop" class="btn btn-destructive btn-disabled" onclick="sendCommand('stop')">
                <i data-lucide="square" class="w-4 h-4 fill-current"></i> Kill Process
            </button>
        </div>
    </div>

    <script>
        lucide.createIcons();
        let isRunning = false;

        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateUI(data.running);
            } catch (error) {
                console.error("Connection lost");
                updateUI(null);
            }
        }

        function updateUI(running) {
            const badge = document.getElementById('status-badge');
            const dot = document.getElementById('status-dot');
            const text = document.getElementById('status-text');
            const btnStart = document.getElementById('btn-start');
            const btnStop = document.getElementById('btn-stop');

            if (running === true) {
                badge.className = "flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200";
                dot.className = "w-2 h-2 rounded-full bg-emerald-500 animate-pulse";
                text.innerText = "Online";
                
                btnStart.classList.add('btn-disabled');
                btnStop.classList.remove('btn-disabled');
            } else if (running === false) {
                badge.className = "flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200";
                dot.className = "w-2 h-2 rounded-full bg-slate-400";
                text.innerText = "Offline";

                btnStart.classList.remove('btn-disabled');
                btnStop.classList.add('btn-disabled');
            } else {
                badge.className = "flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200";
                dot.className = "w-2 h-2 rounded-full bg-red-500";
                text.innerText = "Disconnected";
            }
        }

        async function sendCommand(action) {
            const btn = action === 'start' ? document.getElementById('btn-start') : document.getElementById('btn-stop');
            const originalHTML = btn.innerHTML;
            btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Executing...`;
            lucide.createIcons();
            
            try {
                await fetch(`/api/${action}`, { method: 'POST' });
                setTimeout(fetchStatus, 500); // Poll status immediately after command
            } catch (e) {
                console.error(e);
            } finally {
                btn.innerHTML = originalHTML;
                lucide.createIcons();
            }
        }

        // Poll the server every 2 seconds to keep the UI perfectly synced
        setInterval(fetchStatus, 2000);
        fetchStatus();
    </script>
</body>
</html>
"""

# --- API ENDPOINTS ---


@app.get("/")
def serve_ui():
    return HTMLResponse(content=HTML_TEMPLATE)


@app.get("/api/status")
def get_status():
    return {"running": is_peacock_running()}


@app.post("/api/start")
def start_peacock():
    if not is_peacock_running():
        # Spawn the binary silently without attaching it to the current console or desktop focus
        subprocess.Popen(
            ["peacock.exe"], creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW
        )
    return {"status": "started"}


@app.post("/api/stop")
def stop_peacock():
    if is_peacock_running():
        # Force kill the executable and all its child threads
        subprocess.run(
            ["taskkill", "/IM", "peacock.exe", "/F"], creationflags=CREATE_NO_WINDOW
        )
    return {"status": "stopped"}


if __name__ == "__main__":
    port = 58433
    local_ip = get_local_ip()
    print(f"\n[OVERSEER] Booting Control Node")
    print(f"[OVERSEER] Dashboard URL: http://{local_ip}:{port}\n")
    # Log config is None to prevent stdout crashes when compiled windowless
    uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)
