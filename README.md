# Peacock 🦚
**Remote Collaboration & Analysis Engine**

Peacock is a zero-latency, non-intrusive desktop capture tool paired with a mobile-first dashboard. Engineered for live webinars, remote team meetings, and digital collaboration, it allows you to pull multi-modal AI analysis from your PC's active display directly to your smartphone, without disrupting your primary screen.

## Core Architecture
* **Direct Frame-Buffer Access:** Bypasses application-layer hooks (like Zoom or Teams) by reading directly from the OS GPU via the `mss` library.
* **Dual-Engine Processing:** Seamlessly toggle between Gemini 3.5 Flash (for high-speed standard queries) and Gemini 3.1 Pro (for deep analytical reasoning).
* **Decoupled Client-Server Pipeline:** The frontend is a clean, split JavaScript/HTML/CSS architecture served natively by FastAPI, ensuring easy scalability.
* **Token Telemetry Engine:** Built-in mobile dashboard actively tracks and calculates your usage against the 1M token limit, keeping costs predictable.
* **Offline Persistence:** All analysis logs, prompts, and configurations are saved locally on your phone utilizing IndexedDB via LocalForage.

## System Requirements
* Python 3.14+
* `uv` (Fast Python Package Installer), or `pip`
* A valid Google Gemini API Key

## Setup & Deployment

1. **Install Core Dependencies**

   Option A: use `uv`:
   ```bash
   uv add fastapi uvicorn pillow mss google-genai python-dotenv qrcode
   ```

   Option B: use Python and `pip` with a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
   Or on macOS/Linux:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

2. **Configure Host Authentication**

   Create a `.env` file in the root project directory and securely store your API key:
   ```bash
   GEMINI_API_KEY="your_api_key_here"
   ```

   Obtain your Gemini API key from Google AI Studio:
   `https://aistudio.google.com/api-keys`

3. **Verify Directory Structure**
   Ensure your project is structured as follows:
   ```text
   .env
   main.py
   chat_agent.py
   static/
     index.html
     styles.css
     app.js
   ```

4. **Initialize the Server**
   Boot the backend engine on your host PC:
   ```bash
   uv run main.py
   ```

5. **Connect the Remote Dashboard**
   Upon boot, your terminal will generate a scannable ASCII QR code. Point your smartphone's camera at the terminal to open the remote dashboard.

   > Crucial: Your mobile device and host PC must be on the same local subnet/Wi-Fi.

## Security Notice
This architecture transmits payloads over local HTTP. It relies strictly on the inherent WPA2/WPA3 security of your physical network. Do not deploy this tool on public or untrusted networks if you are processing sensitive corporate or financial data on-screen.
