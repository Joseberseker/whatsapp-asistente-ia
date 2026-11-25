"""Módulos de negocio enchufables.

Cada módulo expone:
- TOOLS: declaraciones de función (JSON Schema) que el agente le ofrece a la IA.
- HANDLERS: {nombre: fn(wa_id, **args) -> str} que ejecuta esa tool.
Agregar un módulo = crear el archivo y sumarlo a MODULES.
"""

from . import reminders

MODULES = [reminders]

TOOLS = [t for m in MODULES for t in m.TOOLS]
HANDLERS = {name: fn for m in MODULES for name, fn in m.HANDLERS.items()}
