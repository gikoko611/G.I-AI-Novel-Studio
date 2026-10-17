import httpx
from .config import (
    AI_PROVIDER, AI_BASE_URL, AI_MODEL, AI_API_KEY,
    GEMINI_API_KEY, GEMINI_MODEL
)

class ProviderError(Exception):
    def __init__(self, message, quota=False, retryable=False):
        super().__init__(message)
        self.quota = quota
        self.retryable = retryable

def _quota_error(status, body):
    text = (body or "").lower()
    return status in (402, 429) or any(x in text for x in (
        "quota exceeded", "insufficient_quota", "resource_exhausted",
        "billing hard limit", "rate limit reached"
    ))

async def generate_text(prompt: str) -> str:
    provider = AI_PROVIDER
    if provider == "gemini":
        if not GEMINI_API_KEY:
            raise ProviderError("GEMINI_API_KEY မသတ်မှတ်ရသေးပါ။")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(
                    url, params={"key": GEMINI_API_KEY},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"temperature": 0.8}}
                )
        except httpx.HTTPError as e:
            raise ProviderError(f"Gemini network error: {e}", retryable=True) from e
        if r.status_code >= 400:
            body = r.text[:1000]
            raise ProviderError(f"Gemini HTTP {r.status_code}: {body}",
                                quota=_quota_error(r.status_code, body),
                                retryable=r.status_code >= 500)
        data = r.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            raise ProviderError("Gemini မှ စာသားမရရှိပါ။ Response structure ကိုစစ်ပါ။")

    if provider != "openai_compatible":
        raise ProviderError("AI_PROVIDER သည် openai_compatible သို့မဟုတ် gemini ဖြစ်ရပါမည်။")
    if not AI_API_KEY:
        raise ProviderError("AI_API_KEY မသတ်မှတ်ရသေးပါ။")
    url = f"{AI_BASE_URL}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {AI_API_KEY}"},
                json={
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": (
                            "You are a professional novelist. Write original, coherent Burmese prose. "
                            "Follow the chapter brief, maintain continuity, and output only the chapter "
                            "title on the first line followed by the chapter text. Do not summarize."
                        )},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.8
                }
            )
    except httpx.HTTPError as e:
        raise ProviderError(f"AI network error: {e}", retryable=True) from e
    if r.status_code >= 400:
        body = r.text[:1000]
        raise ProviderError(f"AI HTTP {r.status_code}: {body}",
                            quota=_quota_error(r.status_code, body),
                            retryable=r.status_code >= 500)
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise ProviderError("AI provider မှ စာသားမရရှိပါ။ Response structure ကိုစစ်ပါ။")
