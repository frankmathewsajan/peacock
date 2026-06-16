import io
import socket
import json
import sys
import os
import time
import asyncio
import queue
import threading
from contextlib import asynccontextmanager
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
    """Loads presets from disk for autonomous operation."""
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


def _launch_teleprompter(q: queue.Queue, config: dict):
    """Spawns Tkinter in a daemon thread."""
    local_image_buffer = []

    def handle_capture():
        """Batch capture logic: stores images silently."""
        try:
            img, _ = _sync_capture()
            local_image_buffer.append(img)
            q.put(
                {"action": "PROMPTER_BUFFER_UPDATE", "count": len(local_image_buffer)}
            )
        except Exception:
            pass

    def handle_analyze(prompt_text, model_tier):
        """Processes either the batched images or a single fresh screenshot."""
        q.put(
            {
                "action": "PROMPTER_SYNC",
                "text": f"[ Processing with {model_tier.upper()} mode... ]",
            }
        )
        try:
            images_to_analyze = []

            # If batch buffer has images, use them and clear it.
            if len(local_image_buffer) > 0:
                images_to_analyze = list(local_image_buffer)
                local_image_buffer.clear()
                q.put({"action": "PROMPTER_BUFFER_UPDATE", "count": 0})
            else:
                # Fallback to single instant screenshot
                img, _ = _sync_capture()
                images_to_analyze = [img]

            answer, tokens = analyze_screen(prompt_text, images_to_analyze, model_tier)
            q.put({"action": "PROMPTER_SYNC", "text": answer})
        except Exception as e:
            q.put({"action": "PROMPTER_SYNC", "text": f"[ Analysis Failed: {str(e)} ]"})

    root = tk.Tk()
    app = StealthTeleprompter(
        root,
        q,
        config,
        on_analyze_callback=handle_analyze,
        on_capture_callback=handle_capture,
    )
    root.mainloop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.prompter_queue = queue.Queue()
    app.state.shared_config = load_local_config()

    tk_thread = threading.Thread(
        target=_launch_teleprompter,
        args=(app.state.prompter_queue, app.state.shared_config),
        daemon=True,
    )
    tk_thread.start()

    app.state.session_images = []
    app.state.total_tokens = 0
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


def _sync_capture() -> io.BytesIO:
    with mss.MSS() as sct:
        sct_img = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
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


@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")


@app.get("/tokens")
async def get_tokens(request: Request):
    return {"total_used": request.app.state.total_tokens}


@app.post("/chat")
async def process_chat(request_data: ChatRequest, request: Request):
    state = request.app.state
    if not state.session_images and not request_data.message:
        return {
            "response": "System Error: Prompt or context required.",
            "total_tokens": state.total_tokens,
        }

    answer, tokens_used = analyze_screen(
        request_data.message, state.session_images, request_data.model_tier
    )
    state.total_tokens += tokens_used
    state.session_images.clear()
    return {"response": answer, "total_tokens": state.total_tokens}


@app.websocket("/stream")
async def capture_on_demand(websocket: WebSocket):
    await websocket.accept()
    p_queue: queue.Queue = websocket.app.state.prompter_queue
    config: dict = websocket.app.state.shared_config

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

                    config.update(new_config)
                    p_queue.put({"action": "PROMPTER_CONFIG", "config": new_config})
                except Exception as e:
                    print("Config Save Failed:", e)

            elif event.action == "CAPTURE":
                img, buffer = await asyncio.to_thread(_sync_capture)
                websocket.app.state.session_images.append(img)
                await websocket.send_bytes(buffer.getvalue())

            elif event.action == "EXTRACT_TEXT":
                extracted = await asyncio.to_thread(_sync_extract_text)
                await websocket.send_text(
                    json.dumps({"type": "extracted_text", "content": extracted})
                )

            elif event.action == "PASTE":
                await asyncio.to_thread(_sync_paste, event.text)

            elif event.action.startswith("PROMPTER_"):
                p_queue.put({"action": event.action, "text": event.text})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Stream Interface Degraded: {e}")
        pass


def get_local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"


if __name__ == "__main__":
    port = 8000
    local_ip = get_local_ip()
    target_url = f"http://{local_ip}:{port}"

    print("\n[SYSTEM] Peacock Engine Initialized")
    print(f"\nDashboard URL: {target_url}\n")
    qr = qrcode.QRCode(version=1, box_size=1, border=2)
    qr.add_data(target_url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    print("\nStarting Uvicorn ASGI Server...\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
