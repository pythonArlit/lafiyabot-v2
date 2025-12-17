import httpx
import os
async def ask_grok(text: str, langue: str = "fr") -> str:
    try:
        r = await httpx.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('GROK_KEY')}", "Content-Type": "application/json"},
            json={"model": "grok-3", "messages": [{"role": "system", "content": "Réponds clair et poli."}, {"role": "user", "content": text}], "temperature": 0.7}
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except:
        return "Je n’ai pas pu répondre pour le moment."
