
# 🦚 Peacock: Multi-Threaded Remote Command & Analysis Daemon

Peacock is a low latency, non-intrusive desktop capture system paired with a mobile-first management dashboard. Peacock interfaces directly with the Windows OS subsystem to achieve true background invisibility. It allows users to stream GPU framebuffer contexts to remote devices for real-time multi-modal AI analysis without disrupting foreground interactions, breaking application focus, or alerting native window event loops.

### Intended Use & Fair Use Policy

Peacock is an advanced productivity and accessibility tool engineered for high-performance note-taking, live context summarization, and programmatic multi-modal workflows.

* **Approved Fair Use:** Real-time data synthesis during technical webinars, automated action-item extraction from rapid corporate streams, and programmatic OCR harvesting from legacy environments lacking copy-paste clipboards.
* **Prohibited Use:** Academic dishonesty, unauthorized programmatic data exfiltration, DRM circumvention, or covert host monitoring.

---

## Table of Contents

1. [System Topology](#system-topology)
2. [Core Systems Architecture](#core-systems-architecture)
3. [Deep Dive: Windows Subsystem Overrides (Ring 3 Native Interface)](#deep-dive-windows-subsystem-overrides-ring-3-native-interface)
4. [Asynchronous Actor Model & Thread Isolation](#asynchronous-actor-model--thread-isolation)
5. [Network Topology: Ephemeral Mesh Networks](#network-topology-ephemeral-mesh-networks)
6. [State Persistence & Compiling](#state-persistence--compiling)
7. [System Requirements & Deployment](#system-requirements--deployment)

---

## System Topology

| Subsystem | Technology Stack | Operational Responsibility |
| :--- | :--- | :--- |
| **Host Kernel Wrapper** | `ctypes` + Win32 Native API | Mutates OS Window Styles; manages focus-rejection and capture-evasion. |
| **Ingestion Engine** | `mss` (Direct Framebuffer Intercept) | Executes fast, hardware-level VRAM blitting to extract pixel matrices. |
| **Concurrency Daemon** | `FastAPI` + `uvicorn` + `threading` | Asymmetric thread manager decoupling HTTP/WS states from GUI operations. |
| **Persistence Layer** | Local JSON Document Store | Intercepts Tkinter geometry states via window-manager hooks for zero-config cold boots. |
| **Client Interface** | Vanilla ES6 JavaScript (WebSocket Client) | Decoupled State/UI layer handling multi-modal scheduling and hardware-simulation triggers. |

---

## Core Systems Architecture

```text
       [ Remote Client Device ]
                 │
      (Encrypted WireGuard Mesh)
                 │
                 ▼  [Port: 58432]
     ┌──────────────────────────────────────────────┐
     │             PEACOCK HOST DAEMON              │
     │                                              │
     │  ┌──────────────────┐  Thread-Safe Queue     │
     │  │  Uvicorn Server  ├─────────────────────┐  │
     │  │ (Async/WS Thread)│                     │  │
     │  └──────────────────┘                     ▼  │
     │                                ┌───────────────────┐
     │                                │  Tkinter Engine   │
     │                                │   (Main Thread)   │
     │                                └─────────┬─────────┘
     │                                         │
     │  ┌──────────────────┐                   │
     │  │ Win32 Subsystem  │◄──────────────────┘
     │  │ (WS_EX_NOACTIVATE)│ (ctypes Ring 3 Manipulation)
     │  └──────────────────┘
     └──────────────────────────────────────────────────────┘

```

---

## Deep Dive: Windows Subsystem Overrides (Ring 3 Native Interface)

Standard desktop windows are designed to explicitly interact with user space: clicking a window shifts OS focus parameters, changing window hierarchies, and modifying window manager visibility. Peacock bypasses these native behaviors by directly manipulating the Windows OS User Space subsystem (`Ring 3`) via the Python `ctypes` foreign function interface, targeting the **Desktop Window Manager (DWM)** memory blocks.

### Focus Rejection (`WS_EX_NOACTIVATE`)

To ensure that interacting with the teleprompter overlay never steals focus away from your active IDE, terminal, or browser, the daemon mutates the window's Extended Window Styles flag in the kernel memory table:

* It reads the current style allocation via `GetWindowLongW`.
* It performs a bitwise `OR` assignment to append the `WS_EX_NOACTIVATE` hex mask.
* It writes the state back using `SetWindowLongW`. This instructs the OS window manager to entirely ignore hardware-level mouse clicks relative to focus state modification.

### Overlay Seclusion (`WS_EX_TOOLWINDOW`)

To achieve complete structural minimalism, Peacock strips its taskbar presence and drops out of the native `Alt+Tab` application rotation array. This is completed by injecting the `WS_EX_TOOLWINDOW` flag into the DWM configuration matrix, making the engine functionally invisible to OS task monitoring layouts.

### Capture Evasion (`WDA_EXCLUDEFROMCAPTURE`)

To allow the screen-capture engine to see "through" the overlay and read the code or presentation underneath it, the window calls `SetWindowDisplayAffinity` passing the `WDA_EXCLUDEFROMCAPTURE` parameter. The Windows GPU compositor safely renders the overlay to your monitor but explicitly drops its memory buffer when generating screen capture arrays via standard API hooks.

---

## Asynchronous Actor Model & Thread Isolation

Python's **Global Interpreter Lock (GIL)** guarantees that only one native thread executes bytecode at any given moment. This presents a critical failure state when combining a real-time web server (Uvicorn) with an infinite graphic user interface loop (`Tkinter.mainloop()`). If spawned symmetrically, the UI render thread entirely starves the web server network socket loop.

```text
[Main Thread] ───► Tkinter Loop (Rendering UI) ──► Polling Queue ──► Update GUI
                                                        ▲
                                            (Thread-Safe Buffer)
                                                        │
[Daemon Thread] ─► Uvicorn WS Connection ────────────────┘

```

Peacock mitigates this via a decoupled **Asynchronous Actor Model**:

1. **The Core UI Anchor:** The Tkinter GUI sits strictly on the host's **Main OS Thread**, satisfying the internal requirement of Windows window managers that pixel operations originate from the starting thread.
2. **The Server Background Daemon:** The FastAPI app/Uvicorn server is isolated inside a secondary background thread explicitly configured with `daemon=True`. This keeps network pipelines alive asynchronously and ensures the server shuts down cleanly when the parent process exits.
3. **Thread-Safe Memory Interleaving:** To share state payloads safely across thread bounds without risking memory access collisions or race conditions, communication relies on a synchronized `queue.Queue()`. The background web worker reads remote websocket instructions and commits them to the queue. The Main GUI thread executes a non-blocking poll every 50ms via the window loop's `.after()` handler to ingest and render payloads.

---

## Network Topology: Ephemeral Mesh Networks

Peacock abandons traditional public-facing routing conventions (like insecure port forwarding or cloud middle-man relay APIs) to maintain local performance parity and strict structural security.

```text
[Phone Workspace App] ───► [Tailscale Virtual Interface] ───► [Host Engine Daemon]
                             (WireGuard Mesh Tunnel)           (Port: 58432)

```

### Port Obfuscation

The host server avoids identifiable, predictable application ports (e.g., `80`, `8080`, `8000`), instead binding directly to port `58432`. This port sits in the **IANA Ephemeral Port Range**, effectively camouflaging all inbound and outbound teleprompter instructions amid routine background operating system network pings.

### Zero-Trust Mesh Integration

Instead of exposing unencrypted framebuffers to broader subnets or public routing arrays, Peacock leverages **Tailscale (WireGuard engine core)**. This wraps the network interface in a private virtual mesh. The mobile device connects directly to the host machine using its private `100.x.x.x` overlay IP address. All payloads are wrapped in end-to-end ChaCha20-Poly1305 encryption at the network boundary, bypassing router firewall tables entirely.

---

## State Persistence & Compiling

### Lightweight JSON Document Store

Peacock enforces zero-configuration execution. When a user dynamically resizes or drags the transparent interface across their screen space, the underlying Python layer intercepts the native geometry modifications (`<B1-Motion>` and `<Configure>`). It extracts the window spatial strings and serializes them in real-time to a local `peacock_state.json` file. On cold boot, the system parses this document store to restore spatial orientation offline before the network loop even initializes.

### Binary Compilation & `_MEIPASS` Routine

To facilitate zero-dependency deployment, the multi-file application is frozen into a standalone machine-code binary using PyInstaller with the `--noconsole` directive to sever `sys.stdout` runtime constraints.

Because PyInstaller unpacks embedded resources (like HTML, CSS, and JS web components) into a volatile, random OS temporary directory at run time, path resolution uses an absolute mapping layout:

```python
def get_asset_path(relative_path):
    import sys, os
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

```

This enables the FastAPI static asset director to reliably locate web components regardless of where the OS unpacks the application binary execution context.

---

## System Requirements & Deployment

### Hardware & Software Prerequisites

* **Operating System:** Windows 10/11 (Required for native Win32/DWM API overrides).
* **Runtime Environment:** Python 3.14+ (If running uncompiled scripts).
* **Package Management:** `uv` (Fast Python Package Installer) or `pip`.

### Dependency Installation

To spin up the core environment from source:

```bash
# Using 'uv' package orchestrator
uv add fastapi uvicorn pillow mss google-genai python-dotenv qrcode pydantic pyautogui pyperclip

# Using standard Python pip infrastructure
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

```

### Initializing the Daemon

Execute the parent application directly to spin up the local server loops:

```bash
uv run main.py

```

Upon execution, a localized QR code will generate in the active terminal environment. Scan this with your network-linked device to connect the orchestration dashboard immediately.

```
