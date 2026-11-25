"""Cliente mínimo de la WhatsApp Cloud API: firma del webhook, parseo y envío."""

import hashlib
import hmac

import logging

import httpx

from . import config

log = logging.getLogger("asistente.whatsapp")


def valid_signature(body: bytes, header: str | None) -> bool:
    """Meta firma cada POST con HMAC-SHA256 del App Secret (header X-Hub-Signature-256)."""
    if not config.WHATSAPP_APP_SECRET or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(config.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def parse_messages(payload: dict) -> list[dict]:
    """Extrae los mensajes entrantes. Ignora los status (sent/delivered/read)."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c["wa_id"]: c.get("profile", {}).get("name", "") for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                text = m["text"]["body"] if m.get("type") == "text" else None
                out.append({"id": m["id"], "from": m["from"], "name": names.get(m["from"], ""),
                            "type": m.get("type"), "text": text})
    return out


def _post(payload: dict) -> dict:
    r = httpx.post(
        f"{config.GRAPH_API_URL}/{config.WHATSAPP_PHONE_NUMBER_ID}/messages",
        headers={"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"},
        json={"messaging_product": "whatsapp", **payload},
        timeout=15,
    )
    if r.is_error:
        # Meta explica el motivo en el cuerpo (token, número no autorizado, plantilla...)
        log.error("Graph API %s → %s", r.status_code, r.text)
    r.raise_for_status()
    return r.json()


def send_text(to: str, body: str) -> dict:
    log.info("→ %s texto: %s", to, body[:120])
    return _post({"to": to, "type": "text", "text": {"body": body}})


def mark_read_typing(message_id: str) -> None:
    """Marca el mensaje como leído y muestra "escribiendo…" hasta que respondamos (máx. 25 s)."""
    _post({"status": "read", "message_id": message_id, "typing_indicator": {"type": "text"}})


def send_template(to: str, name: str, lang: str, params: list[str] | None = None) -> dict:
    log.info("→ %s plantilla %s/%s %s", to, name, lang, params)
    template = {"name": name, "language": {"code": lang}}
    if params:
        template["components"] = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]
    return _post({"to": to, "type": "template", "template": template})
