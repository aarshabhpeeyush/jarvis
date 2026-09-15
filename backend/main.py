"""J.A.R.V.I.S. Backend — FastAPI server orchestrating Claude, ElevenLabs, and HAL Bridge."""
import os
import json
import base64
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from jarvis_brain import think, reset_conversation, get_history
from voice_pipeline import synthesize_stream, synthesize_full
from hal_bridge import hal
from goal_compiler import compile_goal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("jarvis.main")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("J.A.R.V.I.S. systems initialising...")
    await hal.connect()
    logger.info("All systems nominal. Good evening, Sir.")
    yield
    logger.info("J.A.R.V.I.S. shutting down.")


app = FastAPI(title="J.A.R.V.I.S.", lifespan=lifespan)

# Serve frontend static files
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ─── REST Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "online", "identity": "J.A.R.V.I.S.", "version": "1.0.0"}


@app.post("/api/reset")
async def reset():
    reset_conversation()
    return {"message": "Memory wiped. A clean slate, Sir."}


@app.get("/api/history")
async def history():
    return {"history": get_history()}


@app.get("/api/hal/tools")
async def hal_tools():
    return hal.list_tools()


@app.post("/api/hal/dispatch")
async def hal_dispatch(payload: dict):
    action = payload.get("action", "")
    target = payload.get("target", "")
    params = payload.get("params", {})
    result = await hal.dispatch(action, target, params)
    return result


@app.post("/api/goal/compile")
async def compile_goal_endpoint(payload: dict):
    objective = payload.get("objective", "")
    if not objective:
        raise HTTPException(status_code=400, detail="objective is required")
    goal_block = await compile_goal(objective)
    return {"goal": goal_block}


# ─── WebSocket — main real-time channel ──────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws) if hasattr(self.active, "discard") else None
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(ws)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    await ws.send_json({"type": "connected", "message": "J.A.R.V.I.S. online. Good evening, Sir."})
    logger.info("WebSocket client connected")

    try:
        while True:
            raw = await ws.receive_text()
            message = json.loads(raw)
            msg_type = message.get("type", "chat")

            if msg_type == "chat":
                user_text = message.get("text", "").strip()
                if not user_text:
                    continue

                # Log to HUD
                await ws.send_json({
                    "type": "hud_log",
                    "level": "input",
                    "message": f"INPUT: {user_text[:80]}",
                })

                # Detect goal compilation trigger
                lower = user_text.lower()
                if lower.startswith("generate a goal") or lower.startswith("generate goal"):
                    objective = user_text.split("goal", 1)[-1].strip().lstrip(":")
                    await ws.send_json({"type": "hud_log", "level": "system", "message": "GOAL COMPILER: Engaging..."})
                    goal_block = await compile_goal(objective)

                    await ws.send_json({"type": "goal_block", "content": goal_block})
                    await ws.send_json({"type": "hud_log", "level": "success", "message": "GOAL COMPILER: Block generated."})

                    # Have JARVIS explain it
                    explanation_prompt = f"I've compiled the goal block. Now explain the architecture and execution plan for this objective in your J.A.R.V.I.S. style:\n\nObjective: {objective}"
                    await _stream_jarvis_response(ws, explanation_prompt)
                else:
                    await _stream_jarvis_response(ws, user_text)

            elif msg_type == "hal_command":
                action = message.get("action", "")
                target = message.get("target", "")
                params = message.get("params", {})
                await ws.send_json({"type": "hud_log", "level": "hal", "message": f"HAL: Dispatching {action} → {target}"})
                result = await hal.dispatch(action, target, params)
                await ws.send_json({"type": "hal_result", "result": result})

            elif msg_type == "reset":
                reset_conversation()
                await ws.send_json({"type": "system", "message": "Memory wiped. A clean slate, Sir."})

    except WebSocketDisconnect:
        manager.disconnect(ws)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(ws)


async def _stream_jarvis_response(ws: WebSocket, user_text: str):
    """Stream JARVIS tokens, then synthesize and send audio."""
    await ws.send_json({"type": "jarvis_start"})
    await ws.send_json({"type": "hud_log", "level": "process", "message": "BRAIN: Processing query via Claude Opus 5..."})

    full_text = ""
    token_count = 0

    async for token in think(user_text):
        full_text += token
        token_count += 1
        await ws.send_json({"type": "jarvis_token", "token": token})

    await ws.send_json({"type": "jarvis_end", "full_text": full_text})
    await ws.send_json({"type": "hud_log", "level": "success", "message": f"BRAIN: Response generated ({token_count} tokens)."})

    # Voice synthesis
    if os.getenv("ELEVENLABS_API_KEY"):
        await ws.send_json({"type": "hud_log", "level": "process", "message": "VOICE: Synthesising audio stream..."})
        audio_chunks = []
        async for chunk in synthesize_stream(full_text):
            audio_chunks.append(chunk)

        if audio_chunks:
            full_audio = b"".join(audio_chunks)
            audio_b64 = base64.b64encode(full_audio).decode()
            await ws.send_json({"type": "audio", "data": audio_b64, "format": "mp3"})
            await ws.send_json({"type": "hud_log", "level": "success", "message": f"VOICE: Audio ready ({len(full_audio)} bytes)."})
    else:
        await ws.send_json({"type": "hud_log", "level": "warning", "message": "VOICE: ElevenLabs key not configured — using browser TTS."})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
