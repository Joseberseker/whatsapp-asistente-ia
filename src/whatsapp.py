"""Cliente mínimo de la WhatsApp Cloud API: firma del webhook, parseo y envío."""

import hashlib
import hmac

import httpx

from . import config


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
    r.raise_for_status()
    return r.json()


def send_text(to: str, body: str) -> dict:
    return _post({"to": to, "type": "text", "text": {"body": body}})


def send_template(to: str, name: str, lang: str, params: list[str] | None = None) -> dict:
    template = {"name": name, "language": {"code": lang}}
    if params:
        template["components"] = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]
    return _post({"to": to, "type": "template", "template": template})
