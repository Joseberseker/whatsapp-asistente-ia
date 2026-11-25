# WhatsApp Asistente IA

Asistente de WhatsApp con IA sobre la **WhatsApp Cloud API oficial de Meta**: un **núcleo genérico** (webhook seguro, memoria, agente con function calling) al que se le **enchufan módulos de negocio**, más un **dashboard** para operarlo. Corre con costo $0 usando el número de prueba de Meta, la capa gratuita de Gemini y un túnel de ngrok.

> Primer módulo: **recordatorios**. Le escribes "recuérdame pagar la luz mañana a las 9" y a esa hora te llega el mensaje.

## Arquitectura

```
 WhatsApp ──► Meta Cloud API ──► POST /webhook ─┐  (firma HMAC + dedupe, 200 inmediato)
                                                ▼
                                   store (SQLite: contactos, mensajes, ventana 24 h)
                                                ▼
                                   agent (Gemini + historial + function calling)
                                                ▼
                                   modules/ ── reminders ── (citas, FAQ RAG, tienda… →)
                                                │
          ◄── send_text / send_template ◄───────┘   loop asyncio: envía recordatorios vencidos
                                                    (texto libre en ventana, plantilla fuera)
 Navegador ──► /dashboard (FastAPI + Jinja + HTMX, HTTP Basic)
```

| Archivo | Rol |
|---|---|
| `src/whatsapp.py` | Firma del webhook, parseo del payload, envío de texto y plantillas |
| `src/store.py` | SQLite: contactos, historial, deduplicación y regla de las 24 h |
| `src/agent.py` | Gemini con historial y bucle de function calling sobre las tools de los módulos |
| `src/modules/` | Módulos de negocio (`TOOLS` + `HANDLERS`) |
| `src/dashboard/` | Panel de operación en tiempo real |

## Decisiones de diseño
- **Ventana de 24 h de WhatsApp**: el núcleo sabe si puede enviar texto libre o si tiene que usar una plantilla aprobada. Es la regla que más proyectos de WhatsApp pasan por alto.
- **Webhook robusto**: valida `X-Hub-Signature-256`, responde 200 de inmediato (Meta reintenta si tardas) y deduplica por `message.id`.
- **Function calling manual**: los errores de una tool vuelven al modelo como texto, así el usuario recibe una explicación y no un silencio. Máximo 4 rondas.
- **Sin infraestructura extra**: el programador de envíos es un loop asyncio sobre SQLite; no hace falta Celery, Redis ni APScheduler para esta escala.
- **Dashboard cerrado por defecto**: queda expuesto por el mismo túnel que el webhook, así que sin `DASHBOARD_PASSWORD` no se abre.

## Cómo correrlo
1. Configura Meta, ngrok y Gemini siguiendo [`docs/setup-meta.md`](docs/setup-meta.md) y copia `.env.example` a `.env`.
2. Levanta la app:
   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   .venv/bin/uvicorn src.app:app --port 8000
   ```
   o con `docker compose up -d --build`.
3. Expón el webhook con `ngrok http --url=<tu-dominio> 8000`.
4. Escríbele al número de prueba y abre `http://localhost:8000/dashboard`.

Tests: `.venv/bin/pytest` (Gemini y la Graph API van simulados, no hace falta ninguna credencial).

## Cómo agregar un módulo
```python
# src/modules/mi_modulo.py
def consultar_stock(wa_id: str, producto: str) -> str:
    return f"Quedan 3 unidades de {producto}."

TOOLS = [{"name": "consultar_stock", "description": "Stock disponible de un producto.",
          "parameters": {"type": "object", "properties": {"producto": {"type": "string"}}, "required": ["producto"]}}]
HANDLERS = {"consultar_stock": consultar_stock}
```
Después lo sumas en `src/modules/__init__.py` → `MODULES = [reminders, mi_modulo]`. El agente ya lo ofrece a la IA.

## Limitaciones conocidas
- El número de prueba solo envía a **5 números verificados**. Para producción hace falta un número propio y la verificación del negocio en Meta.
- Fuera de la ventana de 24 h, los recordatorios dependen de que la plantilla `recordatorio` esté aprobada.
- Solo entiende texto (por ahora no procesa audios, imágenes ni ubicaciones).
- SQLite y un solo proceso: pensado para demo o pyme, no para alta concurrencia.

## Roadmap de módulos
- [x] Recordatorios
- [ ] **Citas**: agendar, consultar y cancelar contra Supabase, con recordatorio automático para reducir inasistencias
- [ ] **FAQ con RAG**: reutilizar el núcleo de [rag-faq-telegram](https://github.com/Joseberseker/rag-faq-telegram)
- [ ] **Traspaso a humano**: el operador toma la conversación desde el dashboard
- [ ] **Tienda/pedidos**: catálogo, pedido, estado y dashboard de ventas
- [ ] **Campañas y encuestas NPS** con plantillas

## Stack
Python 3.12 · FastAPI · WhatsApp Cloud API · Google Gemini (`google-genai`) · SQLite · Jinja2 + HTMX · Docker · pytest

Licencia MIT.
