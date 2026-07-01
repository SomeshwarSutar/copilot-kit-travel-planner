"""
FastAPI entry-point — serves both the CopilotKit runtime and the Vite SPA.

Architecture
------------
  /api/copilotkit  — CopilotKit Python SDK runtime (wraps the LangGraph graph).
                     The Vite frontend connects here; no Node.js proxy needed.
  /assets/*        — Vite build output (JS/CSS bundles), mounted after build.
  /*               — SPA fallback: returns index.html for all unknown routes.

Development flow
----------------
  1. Start this server:   python main.py
  2. Start Vite dev:       npm run dev  (in ui/)
     Vite proxies /api → http://localhost:8123 so CORS is transparent.

Production flow
---------------
  1. Build the frontend:  npm run build  (in ui/)
  2. Start this server:   python main.py
     FastAPI serves the built static files directly.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

# Load .env BEFORE importing agent.py — ChatOpenAI is instantiated at
# import time and reads OPENAI_API_KEY from the environment.
for _env in (Path(__file__).parent / ".env", Path(".env")):
    if _env.is_file():
        load_dotenv(_env)
        break
else:
    load_dotenv()

import uvicorn
from copilotkit import LangGraphAGUIAgent
from ag_ui.core import RunAgentInput
from ag_ui.encoder import EventEncoder
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agent import graph

app = FastAPI(title="Travel Planner — CopilotKit + LangGraph")

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Vite dev server (port 5173) and any other origin during development.
# Restrict origins in production by reading from an env var.
_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ── AG-UI / CopilotKit runtime ───────────────────────────────────────────────
# Single unified POST /api/copilotkit endpoint that handles the CopilotKit JS
# SDK "single-endpoint" transport protocol:
#   • {"method": "info"}        — capabilities discovery
#   • {"method": "agent/stop"} — abort a running agent
#   • RunAgentInput body        — actually run the LangGraph agent (AG-UI SSE)
_agent = LangGraphAGUIAgent(
    name="travel_planner",
    description=(
        "AI travel planning assistant. "
        "Uses LangGraph subgraphs to search flights, hotels, and experiences."
    ),
    graph=graph,
)


@app.post("/api/copilotkit", response_model=None)
async def copilotkit_endpoint(request: Request):
    body = await request.json()

    # ── Info / capabilities discovery ─────────────────────────────────────────
    if isinstance(body, dict) and body.get("method") == "info":
        return JSONResponse({
            "sdkVersion": "0.0.0",
            "actions": {},
            "agents": {
                _agent.name: {
                    "description": _agent.description or "",
                    "capabilities": {},
                }
            },
        })

    # ── Agent stop / connect (fire-and-forget) ───────────────────────────────
    if isinstance(body, dict) and body.get("method") in ("agent/stop", "agent/connect"):
        return JSONResponse({"ok": True})

    # ── Single-endpoint agent run: {method:"agent/run", body: RunAgentInput} ─
    if isinstance(body, dict) and body.get("method") == "agent/run":
        run_body = body.get("body", {})
        input_data = RunAgentInput.model_validate(run_body)
        accept = request.headers.get("accept")
        encoder = EventEncoder(accept=accept)
        agent_instance = _agent.clone()

        async def event_stream_run():
            async for event in agent_instance.run(input_data):
                yield encoder.encode(event)

        return StreamingResponse(event_stream_run(), media_type=encoder.get_content_type())

    # ── AG-UI agent run (RunAgentInput) ───────────────────────────────────────
    input_data = RunAgentInput.model_validate(body)
    accept = request.headers.get("accept")
    encoder = EventEncoder(accept=accept)
    agent_instance = _agent.clone()

    async def event_stream():
        async for event in agent_instance.run(input_data):
            yield encoder.encode(event)

    return StreamingResponse(event_stream(), media_type=encoder.get_content_type())

# ── Vite static SPA (only active after `npm run build` in ui/) ────────────────
_STATIC_DIR = Path(__file__).parent.parent / "ui" / "dist"

if _STATIC_DIR.exists():
    _assets = _STATIC_DIR / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="vite-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:  # noqa: RUF029
        """Serve the Vite SPA; fall back to index.html for client-side routes."""
        target = _STATIC_DIR / full_path
        if target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(_STATIC_DIR / "index.html"))


def main() -> None:
    port = int(os.getenv("PORT", "8123"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_dirs=[str(Path(__file__).parent)],
    )


warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

if __name__ == "__main__":
    main()
