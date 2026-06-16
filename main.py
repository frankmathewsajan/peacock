import io
import socket
import json
import sys
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
from teleprompter import StealthTeleprompter  # Decoupled Teleprompter Logic

load_dotenv()
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

MODIFIER_KEY = "command" if sys.platform == "darwin" else "ctrl"


class StreamEvent(BaseModel):
    action: Literal[
        "CAPTURE",
        "EXTRACT_TEXT",
        "PASTE",
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


def _launch_teleprompter(q: queue.Queue):
    """Spawns Tkinter in a daemon thread so it doesn't block FastAPI."""
    root = tk.Tk()
    app = StealthTeleprompter(root, q)
    root.mainloop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Boot up the Teleprompter Thread
    app.state.prompter_queue = queue.Queue()
    tk_thread = threading.Thread(
        target=_launch_teleprompter, args=(app.state.prompter_queue,), daemon=True
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

    # FIX: We must retrieve the queue from the app state before using it!
    p_queue: queue.Queue = websocket.app.state.prompter_queue

    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                event = StreamEvent.model_validate_json(raw_message)
            except ValidationError:
                continue

            if event.action == "CAPTURE":
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

            # --- ROUTING ENDPOINTS ---
            elif event.action.startswith("PROMPTER_"):
                # Dynamically route any teleprompter command to the Tkinter Thread Queue
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
