import io
import socket
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import mss
import qrcode
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
from chat_agent import analyze_screen

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

SESSION_IMAGES: list[Image.Image] = []


class ChatRequest(BaseModel):
    message: str
    model_tier: str = "fast"


@app.get("/")
async def get():
    with open("./static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


TOTAL_TOKENS_USED = 0


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
    global SESSION_IMAGES
    await websocket.accept()

    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        try:
            while True:
                command = await websocket.receive_text()

                if command == "CAPTURE":
                    sct_img = sct.grab(monitor)
                    img = Image.frombytes(
                        "RGB", sct_img.size, sct_img.bgra, "raw", "BGRX"
                    )

                    SESSION_IMAGES.append(img)

                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    await websocket.send_bytes(buffer.getvalue())

        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"Stream error: {e}")
            try:
                await websocket.close()
            except RuntimeError:
                pass


def get_local_ip():
    """
    Creates a dummy socket connection to resolve the preferred local IP address.
    """
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

    print("Ensure both devices are on the same local network.")
    print(f"\nDashboard URL: {target_url}\n")

    qr = qrcode.QRCode(version=1, box_size=1, border=2)
    qr.add_data(target_url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)

    print("\nStarting server...\n")

    uvicorn.run(app, host="0.0.0.0", port=port)
