"""Agente conversacional: Gemini + historial + function calling sobre las tools de los módulos."""

import logging
import time
from datetime import datetime

from google import genai
from google.genai import types

from . import config, modules, store

log = logging.getLogger("asistente.agent")
MAX_TOOL_ROUNDS = 4

SYSTEM = """Eres un asistente por WhatsApp, cordial y breve (máximo 3-4 líneas, sin markdown pesado).
Responde en el idioma del usuario. Ahora es {now} (zona horaria {tz}).
Usa las herramientas disponibles cuando el usuario pida algo que ellas resuelven; no inventes resultados.
Si algo no lo puedes hacer, dilo claramente."""

_client = None


def _generate(contents, system: str, tools: list[dict]) -> types.GenerateContentResponse:
    global _client
    _client = _client or genai.Client(api_key=config.GEMINI_API_KEY)
    decls = [types.FunctionDeclaration(name=t["name"], description=t["description"],
                                       parameters_json_schema=t["parameters"]) for t in tools]
    return _client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=decls)] if decls else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )


def _run_tool(wa_id: str, call: types.FunctionCall) -> str:
    fn = modules.HANDLERS.get(call.name)
    if fn is None:
        return f"Error: la herramienta {call.name} no existe."
    try:
        result = fn(wa_id, **(call.args or {}))
        log.info("Tool %s(%s) → %s", call.name, call.args, result)
        return result
    except Exception as e:  # el error vuelve a la IA para que se lo explique al usuario
        log.exception("Tool %s falló", call.name)
        return f"Error: {e}"


def reply(wa_id: str) -> str:
    """Genera la respuesta al último mensaje (ya guardado en store) de este contacto."""
    contents = [types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
                for m in store.history(wa_id)]
    system = SYSTEM.format(now=datetime.now(config.TZ).strftime("%A %Y-%m-%d %H:%M"), tz=config.TZ.key)
    for _ in range(MAX_TOOL_ROUNDS):
        t0 = time.monotonic()
        resp = _generate(contents, system, modules.TOOLS)
        log.info("Gemini respondió en %.1fs%s", time.monotonic() - t0,
                 f" con tools {[c.name for c in resp.function_calls]}" if resp.function_calls else "")
        if not resp.function_calls:
            return (resp.text or "").strip() or "Perdón, no entendí. ¿Me lo repites?"
        contents.append(resp.candidates[0].content)
        contents.append(types.Content(role="user", parts=[
            # el id enlaza cada resultado con su llamada (los modelos Gemini 3 lo exigen)
            types.Part(function_response=types.FunctionResponse(id=c.id, name=c.name, response={"result": _run_tool(wa_id, c)}))
            for c in resp.function_calls
        ]))
    return "Perdón, me enredé con esa solicitud. ¿Puedes intentarlo de otra forma?"
