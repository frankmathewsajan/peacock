
# Peacock: Remote Collaboration & Analysis Engine

Peacock is a zero-latency, non-intrusive desktop capture tool paired with a mobile-first dashboard. Engineered for live webinars, remote team meetings, and digital collaboration, it allows you to pull multi-modal AI analysis from your PC's active display directly to your smartphone, without disrupting your primary screen.

### Intended Use & Fair Use Policy

Peacock is strictly designed as an accessibility and productivity aid for note-taking and content summarization.

**Approved Fair Use Examples:**

* **Live Lecture Summarization:** Capturing complex slides during a webinar to generate simplified study notes in real-time.
* **Meeting Action Items:** Extracting action items or tasks from a fast-paced virtual meeting presentation without breaking focus from the speaker.
* **Non-Selectable Data Extraction:** Pulling text or code snippets from video tutorials or protected presentations where standard copy-paste is unavailable.

**Prohibited Use:**
This software is not intended for, and must not be used for, academic dishonesty (e.g., live exam cheating), unauthorized data exfiltration, bypassing DRM protections, or any malicious surveillance.

---

## Table of Contents

1. [Core Architecture](#core-architecture)
2. [System Requirements](#system-requirements)
3. [Setup & Deployment](#setup--deployment)
4. [Feature Guide](#feature-guide)
5. [Architectural Deep Dive: Under the Hood](#architectural-deep-dive-under-the-hood)
6. [Security Notice](#security-notice)

---

## Core Architecture

* **Direct Frame-Buffer Access:** Bypasses application-layer hooks by reading directly from the OS GPU via the `mss` library.
* **Event-Driven Actor Model:** Hardware simulations (like remote typing) are decoupled from the web server using asynchronous task queues, ensuring zero latency or server freezing.
* **Strict Data Contracts:** WebSocket communications are validated using Pydantic schemas, ensuring robust data handling.
* **Modular Frontend:** A clean, decoupled JavaScript architecture (State, Network, UI logic) served natively by FastAPI, persisting user history locally via IndexedDB.

---

## System Requirements

* Python 3.14+
* `uv` (Fast Python Package Installer) or standard `pip`
* A valid Google Gemini API Key
* Both host machine and mobile device must reside on the same Local Area Network (LAN/Wi-Fi).

---

## Setup & Deployment

1. **Install Core Dependencies**

  Option A (Using `uv`):

```bash
uv add fastapi uvicorn pillow mss google-genai python-dotenv qrcode pydantic pyautogui pyperclip

```

  Option B (Using Python `pip`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

```

2. **Configure Host Authentication**

Create a `.env` file in the root project directory and securely store your API key. Obtain this key from Google AI Studio.

```bash
GEMINI_API_KEY="your_api_key_here"

```

3. **Verify Directory Structure**

Ensure your project matches this modular layout:

```text
.env
main.py
chat_agent.py
static/
  index.html
  styles.css
  js/
    app.js
    network.js
    state.js
    ui.js

```

4. **Initialize the Server**

Boot the backend engine on your host PC:

```bash
uv run main.py

```

---

## Feature Guide

### Local Network Pairing

Peacock requires your host PC and your mobile dashboard to be on the same physical network (Wi-Fi or Ethernet subnet). Because Peacock transmits unencrypted framebuffer data, routing it exclusively over your local router ensures high speed and prevents exposure to the public internet. When you start the server, a QR code will render in your terminal. Scan this with your smartphone camera to instantly open the dashboard.

### Model Tiers (Fast vs. Deep)

The engine provides two distinct reasoning tracks to balance speed against analytical depth.

* **Fast (Gemini 3.5 Flash):** Optimized for near-instant execution. Best for simple summarization, OCR text extraction, or quick translations.
* **Deep (Gemini 3.1 Pro):** Optimized for complex logic. Best for analyzing architectural diagrams, solving advanced logic problems, or comparing multiple screens of code.

### Capture Modes (Single vs. Batch)

Depending on your workflow, you can analyze a single moment in time or a sequence of events.

* **Single Mode:** Tapping the capture button immediately grabs the current screen state and sends it to the AI alongside your prompt.
* **Batch Mode:** Tapping capture adds a frame to your local "Draft Gallery." You can capture multiple sequential slides, code changes, or application states over a few minutes. Once ready, you submit the entire batch as a single, multi-modal context window to the AI.

### Preset Shortcuts

To prevent typing repetitive prompts on your mobile device during live meetings, Peacock includes four configurable Preset Shortcuts. You can customize these via the Engine Configuration menu. Common examples include "Summarize this slide," "Extract raw text," or "Provide action items." Tapping a preset instantly executes a capture with that specific instruction.

### Remote Input Injection

Peacock allows you to push text from your mobile device directly onto your host PC's screen.

* **Remote Paste:** Instantly pastes the staged payload directly into your PC's active cursor location using the system clipboard.
* **Human-Simulation Typing:** The engine natively simulates human keystrokes. It parses Python syntax to automatically handle IDE auto-indentation, includes micro-delays between keys, and introduces a calculated typo/backspace rate to bypass behavioral analysis tracking.
* **Active Controls:** While the engine is typing, you can pause or completely abort the execution in real-time from your phone.

---

## Architectural Deep Dive: Under the Hood

Peacock is designed using modern software engineering paradigms to ensure stability, concurrency, and performance. Understanding these underlying concepts highlights why the application is structured the way it is.

### 1. Operating Systems & The Framebuffer

Traditional screen recording software relies on application-level hooks or OS-provided Window Manager APIs. These can be slow, resource-heavy, or blocked by specific applications. Peacock uses `mss` to access the **framebuffer**—a dedicated block of memory (VRAM/RAM) where the operating system stores the exact pixel data currently being sent to your monitor. By performing a direct memory copy of this grid of Red, Green, and Blue values, Peacock achieves millisecond-level capture speeds entirely independent of what applications are running on screen.

### 2. Concurrency & The Actor Model

Python's standard execution is synchronous, meaning it does one thing at a time. To handle a web server (FastAPI) and hardware simulations simultaneously, Peacock utilizes an Asynchronous Server Gateway Interface (ASGI) event loop.

However, `async` does not magically prevent blocking. System calls like manipulating the clipboard or reading the framebuffer are executed via C-extensions that seize the Python Global Interpreter Lock (GIL). If run directly in the web server's loop, the entire API would freeze during a screenshot.

To solve this, Peacock implements an **Event-Driven Actor Model**. Hardware inputs (like typing simulations) and system calls are completely decoupled from the web server. The web server merely pushes instructions into an `asyncio.Queue`. A separate, isolated background worker (the Actor) consumes these tasks cooperatively using `asyncio.to_thread()`, ensuring the main web server remains 100% responsive to incoming mobile requests.

### 3. Local Subnet Routing & WebSockets

Peacock does not route its traffic through a central cloud server. When the Python script boots, it binds a Uvicorn server to `0.0.0.0` (all available network interfaces) and broadcasts its local IPv4 address via the QR code.

When your phone scans the code, it establishes a direct, peer-to-peer TCP connection over your router's subnet.

To handle real-time commands (like pausing a typing simulation), Peacock upgrades the standard HTTP connection to a **WebSocket**. Unlike HTTP requests, which require opening and closing a connection for every single message, WebSockets maintain a persistent, bidirectional pipeline. This allows the mobile dashboard to stream raw binary image data and receive status updates instantly.

### 4. Pydantic Data Contracts

In distributed systems, unpredictable data payloads cause silent failures. Peacock enforces strict data contracts over its WebSocket interface using Pydantic. Instead of writing volatile `if/else` logic to parse incoming JSON strings, the application validates every incoming network event against a predefined schema. If the mobile app sends an improperly formatted command, the schema rejects it at the network boundary, ensuring the core application logic is never poisoned by bad data.

---

## Security Notice

This architecture transmits unencrypted JSON payloads and image byte streams over local HTTP. It relies strictly on the inherent WPA2/WPA3 security of your physical Wi-Fi network. **Do not deploy this tool on public Wi-Fi (e.g., coffee shops, airports, or untrusted corporate guest networks)** if you are processing sensitive personal, corporate, or financial data on-screen.