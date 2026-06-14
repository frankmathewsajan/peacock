import io
import socket
import json
import sys
import time
import random
import threading
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import mss
import qrcode
import pyautogui
import pyperclip
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
from chat_agent import analyze_screen

pyautogui.FAILSAFE = False

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

SESSION_IMAGES: list[Image.Image] = []
TOTAL_TOKENS_USED = 0


# --- NEW: Asynchronous Typing State Machine ---
class TypingState:
    def __init__(self):
        self.is_active = False
        self.is_paused = False
        self.current_text = ""
        self.thread = None

    def stop(self):
        self.is_active = False
        self.is_paused = False

    def pause(self):
        if self.is_active:
            self.is_paused = True

    def resume(self):
        if self.is_active:
            self.is_paused = False


typing_state = TypingState()


def background_typing_task(text_data, state: TypingState):
    """
    Runs in a separate thread. Checks the state flag before EVERY keystroke.
    """
    for char in text_data:
        # Check for absolute stop command
        if not state.is_active:
            break

        # Check for pause loop
        while state.is_paused:
            if not state.is_active:  # Allow stopping while paused
                return
            time.sleep(0.1)

        # 5% chance to simulate a typo on alphabetic characters
        if random.random() < 0.05 and char.isalpha():
            wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
            pyautogui.write(wrong_char)
            time.sleep(random.uniform(0.05, 0.15))
            pyautogui.press("backspace")
            time.sleep(random.uniform(0.05, 0.15))

        if char == "\n":
            pyautogui.press("enter")
        else:
            pyautogui.write(char)

        time.sleep(random.uniform(0.01, 0.08))

    state.is_active = False  # Reset state when fully done natively


class ChatRequest(BaseModel):
    message: str
    model_tier: str = "fast"


@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")


@app.get("/tokens")
async def get_tokens():
    return {"total_used": TOTAL_TOKENS_USED}


@app.post("/chat")
async def process_chat(request: ChatRequest):
    global SESSION_IMAGES, TOTAL_TOKENS_USED

    if not SESSION_IMAGES and not request.message:
        return {
            "response": "System Error: Prompt or capture context required.",
            "total_tokens": TOTAL_TOKENS_USED,
        }

    answer, tokens_used = analyze_screen(
        request.message, SESSION_IMAGES, request.model_tier
    )

    TOTAL_TOKENS_USED += tokens_used
    SESSION_IMAGES.clear()

    return {
        "response": answer,
        "total_tokens": TOTAL_TOKENS_USED,
    }


@app.websocket("/stream")
async def capture_on_demand(websocket: WebSocket):
    global SESSION_IMAGES, typing_state
    await websocket.accept()

    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        try:
            while True:
                raw_message = await websocket.receive_text()

                try:
                    payload = json.loads(raw_message)
                    action = payload.get("action")
                    text_data = payload.get("text", "")
                except json.JSONDecodeError:
                    action = raw_message

                if action == "CAPTURE":
                    sct_img = sct.grab(monitor)
                    img = Image.frombytes(
                        "RGB", sct_img.size, sct_img.bgra, "raw", "BGRX"
                    )
                    SESSION_IMAGES.append(img)

                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    await websocket.send_bytes(buffer.getvalue())

                elif action == "EXTRACT_TEXT":
                    old_clipboard = pyperclip.paste()

                    if sys.platform == "darwin":
                        pyautogui.hotkey("command", "a")
                        time.sleep(0.1)
                        pyautogui.hotkey("command", "c")
                    else:
                        pyautogui.hotkey("ctrl", "a")
                        time.sleep(0.1)
                        pyautogui.hotkey("ctrl", "c")

                    time.sleep(0.1)
                    extracted = pyperclip.paste()

                    await websocket.send_text(
                        json.dumps({"type": "extracted_text", "content": extracted})
                    )

                    pyperclip.copy(old_clipboard)

                elif action == "TYPE":
                    # Spawns a new independent thread for typing
                    typing_state.stop()  # Kill any existing thread
                    typing_state.is_active = True
                    typing_state.is_paused = False
                    typing_state.thread = threading.Thread(
                        target=background_typing_task, args=(text_data, typing_state)
                    )
                    typing_state.thread.start()

                # --- NEW STEALTH MACRO CONTROLS ---
                elif action == "PAUSE_TYPE":
                    typing_state.pause()

                elif action == "RESUME_TYPE":
                    typing_state.resume()

                elif action == "STOP_TYPE":
                    typing_state.stop()

                elif action == "PASTE":
                    pyperclip.copy(text_data)
                    if sys.platform == "darwin":
                        pyautogui.hotkey("command", "v")
                    else:
                        pyautogui.hotkey("ctrl", "v")

        except WebSocketDisconnect:
            typing_state.stop()  # Failsafe
        except Exception as e:
            print(f"Stream error: {e}")
            typing_state.stop()
            try:
                await websocket.close()
            except RuntimeError:
                pass


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


if __name__ == "__main__":
    port = 8000
    local_ip = get_local_ip()
    target_url = f"http://{local_ip}:{port}"

    print("\nPeacock Engine initialized.")
    print("Ensure both devices are on the same local network.")
    print(f"\nDashboard URL: {target_url}\n")

    qr = qrcode.QRCode(version=1, box_size=1, border=2)
    qr.add_data(target_url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)

    print("\nStarting server...\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
