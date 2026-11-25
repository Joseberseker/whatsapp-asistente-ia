"""Dashboard de operación: métricas, conversaciones y recordatorios. Protegido con HTTP Basic."""

import secrets
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from .. import config, store
from ..modules import reminders

security = HTTPBasic()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def auth(creds: HTTPBasicCredentials = Depends(security)) -> None:
    # Sin contraseña configurada no se abre: el dashboard queda expuesto por el mismo túnel que el webhook.
    ok = bool(config.DASHBOARD_PASSWORD) and secrets.compare_digest(creds.username, config.DASHBOARD_USER) \
        and secrets.compare_digest(creds.password, config.DASHBOARD_PASSWORD)
    if not ok:
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})


router = APIRouter(prefix="/dashboard", dependencies=[Depends(auth)])


def _local(iso: str | None) -> str:
    if not iso:
        return "—"
    return datetime.fromisoformat(iso).astimezone(config.TZ).strftime("%d/%m %H:%M")


templates.env.filters["local"] = _local


def _data() -> dict:
    since_24h = (store.now() - timedelta(hours=24)).isoformat()
    with store.connect() as c:
        c.executescript(reminders._SCHEMA)
        status = dict(c.execute("SELECT status, COUNT(*) FROM reminders GROUP BY status").fetchall())
        per_day = c.execute(
            "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n FROM messages GROUP BY day ORDER BY day DESC LIMIT 7"
        ).fetchall()
        contacts = c.execute(
            "SELECT c.wa_id, c.name, c.last_inbound_at, "
            "(SELECT content FROM messages m WHERE m.wa_id = c.wa_id ORDER BY id DESC LIMIT 1) AS last "
            "FROM contacts c ORDER BY c.last_inbound_at DESC"
        ).fetchall()
        rems = c.execute("SELECT * FROM reminders ORDER BY due_at DESC LIMIT 50").fetchall()
        active = c.execute("SELECT COUNT(*) FROM contacts WHERE last_inbound_at >= ?", (since_24h,)).fetchone()[0]
        total_msgs = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    per_day = list(reversed(per_day))
    peak = max((r["n"] for r in per_day), default=1)
    return {
        "metrics": {"Mensajes totales": total_msgs, "Contactos activos (24 h)": active,
                    "Recordatorios pendientes": status.get("pending", 0), "Recordatorios enviados": status.get("sent", 0),
                    "Envíos fallidos": status.get("failed", 0)},
        "per_day": [{"day": r["day"][5:], "n": r["n"], "pct": round(100 * r["n"] / peak)} for r in per_day],
        "contacts": contacts, "reminders": rems,
    }


@router.get("")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", _data())


@router.get("/parcial")
def partial(request: Request):
    return templates.TemplateResponse(request, "_panel.html", _data())


@router.get("/chat/{wa_id}")
def chat(request: Request, wa_id: str):
    with store.connect() as c:
        contact = c.execute("SELECT * FROM contacts WHERE wa_id = ?", (wa_id,)).fetchone()
        msgs = c.execute("SELECT role, content, created_at FROM messages WHERE wa_id = ? ORDER BY id DESC LIMIT 100",
                         (wa_id,)).fetchall()
    if contact is None:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "chat.html", {"contact": contact, "messages": list(reversed(msgs)),
                                                             "in_window": store.in_window(wa_id)})
