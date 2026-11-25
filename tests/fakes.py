from google.genai import types


def text(t):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=t)]))])


def call(name, **args):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))]))])


def scripted(monkeypatch, *responses):
    """Reemplaza a Gemini por respuestas guionadas; devuelve los contents que recibió en cada llamada."""
    from src import agent
    queue, seen = list(responses), []

    def fake(contents, system, tools):
        seen.append(list(contents))
        return queue.pop(0)

    monkeypatch.setattr(agent, "_generate", fake)
    return seen
