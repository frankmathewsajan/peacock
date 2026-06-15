import io
import socket
import json
import sys
import time
import random
import asyncio
import re
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

from chat_agent import analyze_screen

load_dotenv()
pyautogui.FAILSAFE = False

# Evaluate the OS modifier constraint exactly once at module load
MODIFIER_KEY = "command" if sys.platform == "darwin" else "ctrl"


def clean_code(text_data: str) -> tuple[str, bool]:
    """
    Replaces the blunt AST parser with targeted regex string manipulation.
    Strips Python comments while strictly preserving exact whitespace and structure.
    """
    is_python = "def " in text_data or "import " in text_data or "class " in text_data
    if is_python:
        # Strip comments but preserve the indentation skeleton
        text_data = re.sub(r"#.*", "", text_data)
        # Filter out lines that became completely empty
        lines = [line for line in text_data.split("\n") if line.strip() != ""]
        return "\n".join(lines), True
    return text_data, False


class PeripheralActor:
    """
    Event-driven Actor Model for managing hardware-bound tasks.
    Isolates typing simulations from the web server's concurrency model.
    """

    def __init__(self):
        self.queue = asyncio.Queue()
        self.typing_task: asyncio.Task | None = None
        self.is_paused = False

    async def run_loop(self):
        while True:
            command, payload = await self.queue.get()

            if command == "TYPE":
                if self.typing_task and not self.typing_task.done():
                    self.typing_task.cancel()
                self.is_paused = False
                self.typing_task = asyncio.create_task(self._async_type(payload))

            elif command == "PAUSE_TYPE":
                self.is_paused = True

            elif command == "RESUME_TYPE":
                self.is_paused = False

            elif command == "STOP_TYPE":
                if self.typing_task:
                    self.typing_task.cancel()

    async def _async_type(self, text_data: str):
        """
        Executes human-like typing cooperatively. Yields control back to the
        ASGI event loop via asyncio.sleep() rather than blocking the main thread.
        """
        try:
            cleaned_text, is_python = clean_code(text_data)
            lines = cleaned_text.split("\n")
            prev_indent = 0

            for line in lines:
                while self.is_paused:
                    await asyncio.sleep(0.1)

                curr_indent = len(line) - len(line.lstrip(" "))

                if is_python and curr_indent < prev_indent:
                    levels_to_drop = (prev_indent - curr_indent) // 4
                    for _ in range(levels_to_drop):
                        pyautogui.press("backspace")
                        await asyncio.sleep(0.05)

                line = line.lstrip(" ")
                prev_indent = curr_indent

                for char in line:
                    while self.is_paused:
                        await asyncio.sleep(0.1)

                    typo_chance = 0.01 if is_python else 0.05
                    if random.random() < typo_chance and char.isalpha():
                        wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                        pyautogui.write(wrong_char)
                        await asyncio.sleep(random.uniform(0.04, 0.12))
                        pyautogui.press("backspace")
                        await asyncio.sleep(random.uniform(0.04, 0.12))

                    pyautogui.write(char)
                    # Yield execution back to the server loop
                    await asyncio.sleep(random.uniform(0.01, 0.06))

                pyautogui.press("enter")
                await asyncio.sleep(random.uniform(0.1, 0.3))

        except asyncio.CancelledError:
            # Task was intercepted and killed by the Actor gracefully
            pass


# --- Pydantic Data Contracts ---
class ChatRequest(BaseModel):
    message: str
    model_tier: str = "fast"


class StreamEvent(BaseModel):
    action: Literal[
        "CAPTURE",
        "EXTRACT_TEXT",
        "TYPE",
        "PAUSE_TYPE",
        "RESUME_TYPE",
        "STOP_TYPE",
        "PASTE",
    ]
    text: str = ""


# --- Application State Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initializes dependent services scoped cleanly to the server lifecycle.
    """
    app.state.actor = PeripheralActor()
    app.state.actor_task = asyncio.create_task(app.state.actor.run_loop())
    app.state.session_images = []
    app.state.total_tokens = 0
    yield
    # Clean teardown
    app.state.actor_task.cancel()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Synchronous Offload Functions ---
def _sync_capture() -> io.BytesIO:
    """Isolates the blocking C-extension MSS call."""
    with mss.MSS() as sct:
        sct_img = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return img, buffer


def _sync_extract_text() -> str:
    """Isolates the blocking clipboard and hotkey operations."""
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


# --- Endpoints ---
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
            "response": "System Error: Prompt or capture context required.",
            "total_tokens": state.total_tokens,
        }

    answer, tokens_used = analyze_screen(
        request_data.message, state.session_images, request_data.model_tier
    )

    state.total_tokens += tokens_used
    state.session_images.clear()

    return {
        "response": answer,
        "total_tokens": state.total_tokens,
    }


@app.websocket("/stream")
async def capture_on_demand(websocket: WebSocket):
    await websocket.accept()
    actor: PeripheralActor = websocket.app.state.actor

    try:
        while True:
            raw_message = await websocket.receive_text()

            try:
                event = StreamEvent.model_validate_json(raw_message)
            except ValidationError:
                # Fallback for simple string commands
                event = StreamEvent(action=raw_message)

            if event.action == "CAPTURE":
                # Offload to prevent blocking the websocket loop
                img, buffer = await asyncio.to_thread(_sync_capture)
                websocket.app.state.session_images.append(img)
                await websocket.send_bytes(buffer.getvalue())

            elif event.action == "EXTRACT_TEXT":
                extracted = await asyncio.to_thread(_sync_extract_text)
                await websocket.send_text(
                    json.dumps({"type": "extracted_text", "content": extracted})
                )

            elif event.action in ["TYPE", "PAUSE_TYPE", "RESUME_TYPE", "STOP_TYPE"]:
                await actor.queue.put((event.action, event.text))

            elif event.action == "PASTE":
                cleaned_text, _ = clean_code(event.text)
                await asyncio.to_thread(_sync_paste, cleaned_text)

    except WebSocketDisconnect:
        await actor.queue.put(("STOP_TYPE", ""))
    except Exception as e:
        print(f"Stream interface degraded: {e}")
        await actor.queue.put(("STOP_TYPE", ""))
        try:
            await websocket.close()
        except RuntimeError:
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
