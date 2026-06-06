# Peacock 🦚
**Remote Collaboration & Analysis Engine**

Peacock is a zero-latency, non-intrusive desktop capture tool paired with a mobile-first dashboard. Engineered for live webinars, remote team meetings, and digital collaboration, it allows you to pull multi-modal AI analysis from your PC's active display directly to your smartphone, without disrupting your primary screen.

## Core Architecture
* **Direct Frame-Buffer Access:** Bypasses application-layer hooks (like Zoom or Teams) by reading directly from the OS GPU via the `mss` library.
* **Dual-Engine Processing:** Seamlessly toggle between Gemini 3.5 Flash (for high-speed standard queries) and Gemini 3.1 Pro (for deep analytical reasoning).
* **Auto-Fire Mode:** Designed for live-action environments. When enabled, capturing a frame instantly bypasses the drafting phase and executes a predefined system prompt against the `Fast` model to minimize friction.
* **Token Telemetry Engine:** Built-in mobile dashboard actively tracks and calculates your usage against the 1M token limit, keeping costs predictable.
* **Decoupled Edge Networking:** Heavy image processing stays on the host PC's hardware. Only ultra-compressed thumbnail indicators and text payloads are transmitted across your local network to the smartphone.
* **Offline Persistence:** All analysis logs, prompts, and configurations are saved locally on your phone utilizing IndexedDB via LocalForage.

## System Requirements
* Python 3.10+
* `uv` (Fast Python Package Installer)
* A valid Google Gemini API Key

## Setup & Deployment

1. **Install Core Dependencies**
Initialize your Python environment and pull the required packages:
```bash
uv add fastapi uvicorn pillow mss google-genai python-dotenv