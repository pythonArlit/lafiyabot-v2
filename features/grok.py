# features/grok.py
import httpx
from config import GROK_KEY

async def ask_grok(question: str, lang: str) -> str:
    if not GROK_KEY:
        return fallback_answer(lang)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROK_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-2",
                    "messages": [
                        {
                            "role": "system",
                            "content": f"Answer health questions in simple {lang}."
                        },
                        {"role": "user", "content": question},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return fallback_answer(lang)

def fallback_answer(lang: str) -> str:
    if lang == "ha":
        return "Na fahimci tambayarka. Ga amsa mai sauƙi."
    if lang == "en":
        return "I understand your question. Here is a simple answer."
    return "J’ai compris ta question. Voici une réponse simple."
