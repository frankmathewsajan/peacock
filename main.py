import io
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles  # NEW IMPORT
from pydantic import BaseModel
import uvicorn
import mss
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
from chat_agent import analyze_screen

app = FastAPI()

# NEW: Mount the static directory to serve JS and CSS files
app.mount("/static", StaticFiles(directory="static"), name="static")

SESSION_IMAGES: list[Image.Image] = []


class ChatRequest(BaseModel):
    message: str
    model_tier: str = "fast"


@app.get("/")
async def get():
    with open("./static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/chat")
async def process_chat(request: ChatRequest):
    global SESSION_IMAGES

    if not SESSION_IMAGES and not request.message:
        return {
            "response": "System Error: Prompt or capture context required.",
            "tokens": 0,
        }

    # Pass the model tier to the agent router
    answer, tokens_used = analyze_screen(
        request.message, SESSION_IMAGES, request.model_tier
    )

    SESSION_IMAGES.clear()

    return {"response": answer, "tokens": tokens_used}


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
            print("WebSocket connection dropped by client.")
        except Exception as e:
            print(f"WebSocket Error: {e}")
            try:
                await websocket.close()
            except RuntimeError:
                pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
