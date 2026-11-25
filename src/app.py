import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response

from . import agent, config, store, whatsapp
from .modules import reminders

log = logging.getLogger("asistente")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(reminders.loop())
    yield
    task.cancel()


app = FastAPI(title="WhatsApp Asistente IA", lifespan=lifespan)


@app.get("/webhook")
def verify(request: Request):
    """Handshake que hace Meta al configurar el webhook."""
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and config.WHATSAPP_VERIFY_TOKEN and q.get("hub.verify_token") == config.WHATSAPP_VERIFY_TOKEN:
        return Response(q.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(403)


def reply(wa_id: str, text: str) -> None:
    whatsapp.send_text(wa_id, text)
    store.record_outbound(wa_id, text)


def handle_message(msg: dict) -> None:
    if not store.first_time(msg["id"]):
        return
    store.record_inbound(msg["from"], msg["name"], msg["text"] or f"[{msg['type']}]")
    if msg["text"] is None:
        reply(msg["from"], "Por ahora solo entiendo mensajes de texto 🙂")
        return
    reply(msg["from"], agent.reply(msg["from"]))


def _safe_handle(msg: dict) -> None:
    try:
        handle_message(msg)
    except Exception:
        log.exception("Error procesando mensaje %s", msg["id"])


@app.post("/webhook")
async def receive(request: Request, background: BackgroundTasks):
    body = await request.body()
    if not whatsapp.valid_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(401)
    # Responder 200 rápido: Meta reintenta si tardamos, el trabajo va en segundo plano.
    for msg in whatsapp.parse_messages(json.loads(body)):
        background.add_task(_safe_handle, msg)
    return {"ok": True}
