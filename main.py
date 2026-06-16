import io
import socket
import json
import sys
import os
import time
import asyncio
import queue
import threading
from typing import Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
import uvicorn
import mss
import qrcode
import pyautogui
import pyperclip
from PIL import Image
from dotenv import load_dotenv

import tkinter as tk
from chat_agent import analyze_screen
from teleprompter import StealthTeleprompter

load_dotenv()
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0
MODIFIER_KEY = "command" if sys.platform == "darwin" else "ctrl"
LOCAL_PRESET_FILE = "presets.json"


def get_asset_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class StreamEvent(BaseModel):
    action: Literal[
        "CAPTURE",
        "EXTRACT_TEXT",
        "PASTE",
        "SET_CONFIG",
        "PROMPTER_SYNC",
        "PROMPTER_CLEAR",
        "PROMPTER_HIDE",
        "PROMPTER_SHOW",
        "PROMPTER_LOCK",
        "PROMPTER_UNLOCK",
        "PROMPTER_THEME",
    ]
    text: str = ""


class ChatRequest(BaseModel):
    message: str
    model_tier: str = "fast"


def load_local_config():
    default_config = {
        "auto_prompt": "Analyze this screen and provide key takeaways.",
        "presets": [
            {"emoji": "🦚", "text": "Summarize this slide concisely"},
            {"emoji": "🌿", "text": "Extract all text exactly as written"},
            {"emoji": "🦉", "text": "Explain the core concept"},
            {"emoji": "🦊", "text": "Provide the primary action item."},
        ],
    }
    if os.path.exists(LOCAL_PRESET_FILE):
        try:
            with open(LOCAL_PRESET_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config["auto_prompt"] = data.get(
                    "auto_prompt", default_config["auto_prompt"]
                )
                default_config["presets"] = data.get(
                    "presets", default_config["presets"]
                )
        except Exception:
            pass
    return default_config


# --- GLOBAL STATE ---
global_queue = queue.Queue()
global_config = load_local_config()
session_images = []
total_tokens = 0

app = FastAPI()
app.mount("/static", StaticFiles(directory=get_asset_path("static")), name="static")


@app.get("/")
async def serve_index():
    return FileResponse(get_asset_path("static/index.html"))


@app.get("/tokens")
async def get_tokens():
    return {"total_used": total_tokens}


@app.post("/chat")
async def process_chat(request_data: ChatRequest):
    global total_tokens, session_images
    if not session_images and not request_data.message:
        return {
            "response": "System Error: Prompt or context required.",
            "total_tokens": total_tokens,
        }

    answer, tokens_used = analyze_screen(
        request_data.message, session_images, request_data.model_tier
    )
    total_tokens += tokens_used
    session_images.clear()
    return {"response": answer, "total_tokens": total_tokens}


def _sync_capture() -> tuple[Image.Image, io.BytesIO]:
    with mss.MSS() as sct:
        sct_img = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        # --- LOCAL BOTTLENECK OPTIMIZATION ---

        # 1. Downscale High-DPI Framebuffers
        # Shrinks the pixel matrix to save memory before transmission to Google
        max_width = 1280
        if img.width > max_width:
            aspect_ratio = img.height / img.width
            new_height = int(max_width * aspect_ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # 2. In-Memory Byte Buffering & JPEG Compression
        # 80% quality drops the payload size by ~85% with zero OCR degradation
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80, optimize=True)

        return img, buffer


def _sync_extract_text() -> str:
    old_clipboard = pyperclip.paste()
    pyautogui.hotkey(MODIFIER_KEY, "a")
    time.sleep(0.1)
    pyautogui.hotkey(MODIFIER_KEY, "c")
    time.sleep(0.1)
    extracted = pyperclip.paste()
    pyperclip.copy(old_clipboard)
    return extracted


def _sync_paste(text: str):
    pyperclip.copy(text)
    pyautogui.hotkey(MODIFIER_KEY, "v")


@app.websocket("/stream")
async def capture_on_demand(websocket: WebSocket):
    global global_config
    await websocket.accept()

    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                event = StreamEvent.model_validate_json(raw_message)
            except ValidationError:
                continue

            if event.action == "SET_CONFIG":
                try:
                    new_config = json.loads(event.text)
                    with open(LOCAL_PRESET_FILE, "w", encoding="utf-8") as f:
                        json.dump(new_config, f)
                    global_config.update(new_config)
                    global_queue.put(
                        {"action": "PROMPTER_CONFIG", "config": new_config}
                    )
                except Exception as e:
                    pass

            elif event.action == "CAPTURE":
                img, buffer = await asyncio.to_thread(_sync_capture)
                session_images.append(img)
                # Now sending a highly optimized, compressed JPEG via WebSocket
                await websocket.send_bytes(buffer.getvalue())

            elif event.action == "EXTRACT_TEXT":
                extracted = await asyncio.to_thread(_sync_extract_text)
                await websocket.send_text(
                    json.dumps({"type": "extracted_text", "content": extracted})
                )

            elif event.action == "PASTE":
                await asyncio.to_thread(_sync_paste, event.text)

            elif event.action.startswith("PROMPTER_"):
                global_queue.put({"action": event.action, "text": event.text})

    except WebSocketDisconnect:
        pass


# --- DISPOSABLE SERVER MANAGER ---
class UvicornManager:
    """Safely spawns and slaughters the ASGI server to free system ports."""

    def __init__(self, target_port):
        self.port = target_port
        self.server = None
        self.thread = None

    def start(self):
        if self.server is None:
            log_config = None if sys.stdout is None else uvicorn.config.LOGGING_CONFIG
            config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=self.port,
                log_config=log_config,
                loop="asyncio",
            )
            self.server = uvicorn.Server(config)
            self.thread = threading.Thread(target=self.server.run, daemon=True)
            self.thread.start()

    def stop(self):
        if self.server:
            self.server.should_exit = True
            self.server = None


def get_local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    port = 58432
    api_manager = UvicornManager(port)
    api_manager.start()

    if sys.stdout is not None:
        local_ip = get_local_ip()
        target_url = f"http://{local_ip}:{port}"
        print("\n[SYSTEM] Peacock Engine Initialized")
        print(f"\nDashboard URL: {target_url}\n")
        qr = qrcode.QRCode(version=1, box_size=1, border=2)
        qr.add_data(target_url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)

    # --- TELEPROMPTER LOGIC ---
    local_image_buffer = []

    def handle_capture():
        try:
            img, _ = _sync_capture()
            local_image_buffer.append(img)
            global_queue.put(
                {"action": "PROMPTER_BUFFER_UPDATE", "count": len(local_image_buffer)}
            )
        except Exception:
            pass

    def handle_analyze(prompt_text, model_tier):
        global_queue.put(
            {
                "action": "PROMPTER_SYNC",
                "text": f"[ Processing with {model_tier.upper()} mode... ]",
            }
        )
        try:
            images_to_analyze = []
            if len(local_image_buffer) > 0:
                images_to_analyze = list(local_image_buffer)
                local_image_buffer.clear()
                global_queue.put({"action": "PROMPTER_BUFFER_UPDATE", "count": 0})
            else:
                img, _ = _sync_capture()
                images_to_analyze = [img]

            answer, tokens = analyze_screen(prompt_text, images_to_analyze, model_tier)
            global_queue.put({"action": "PROMPTER_SYNC", "text": answer})
        except Exception as e:
            global_queue.put(
                {"action": "PROMPTER_SYNC", "text": f"[ Analysis Failed: {str(e)} ]"}
            )

    def handle_network_toggle(is_online: bool):
        if is_online:
            api_manager.start()
            global_queue.put(
                {"action": "PROMPTER_SYNC", "text": "[ Local Network Socket: OPEN ]"}
            )
        else:
            api_manager.stop()
            global_queue.put(
                {"action": "PROMPTER_SYNC", "text": "[ Local Network Socket: CLOSED ]"}
            )

    root = tk.Tk()
    app_ui = StealthTeleprompter(
        root,
        global_queue,
        global_config,
        on_analyze_callback=handle_analyze,
        on_capture_callback=handle_capture,
        on_network_toggle=handle_network_toggle,
    )

    root.mainloop()
