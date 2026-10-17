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


async def generate_text(
    prompt: str,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> str:
    provider = (provider or AI_PROVIDER).strip().lower()

    if provider == "gemini":
        key = gemini_api_key or api_key or GEMINI_API_KEY
        chosen_model = model or GEMINI_MODEL
        if not key:
            raise ProviderError("Gemini API Key မသတ်မှတ်ရသေးပါ။")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{chosen_model}:generateContent"
        )
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(
                    url,
                    params={"key": key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.8},
                    },
                )
        except httpx.HTTPError as e:
            raise ProviderError(
                f"Gemini network error: {e}", retryable=True
            ) from e

        if r.status_code >= 400:
            body = r.text[:1000]
            raise ProviderError(
                f"Gemini HTTP {r.status_code}: {body}",
                quota=_quota_error(r.status_code, body),
                retryable=r.status_code >= 500,
            )

        try:
            data = r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            raise ProviderError(
                "Gemini မှ စာသားမရရှိပါ။ Response structure ကိုစစ်ပါ။"
            )

    if provider != "openai_compatible":
        raise ProviderError(
            "Provider သည် openai_compatible သို့မဟုတ် gemini ဖြစ်ရပါမည်။"
        )

    key = api_key or AI_API_KEY
    chosen_model = model or AI_MODEL
    chosen_base_url = (base_url or AI_BASE_URL).strip().rstrip("/")

    if not key:
        raise ProviderError("AI API Key မသတ်မှတ်ရသေးပါ။")
    if not chosen_base_url.startswith("https://"):
        raise ProviderError("API Base URL သည် HTTPS ဖြစ်ရပါမည်။")

    url = f"{chosen_base_url}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": chosen_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an experienced Burmese-language novelist and careful prose editor. "
                                "Write original fiction in clear, natural, idiomatic Burmese. "
                                "Avoid translated-sounding sentences, repetition, filler, and confusing phrasing. "
                                "Show scenes through believable actions, dialogue, and emotions rather than summaries. "
                                "Keep character voices, motivations, facts, and chronology consistent. "
                                "Follow the requested genre and chapter brief, and make each scene advance the story. "
                                "Output only the chapter heading on the first line followed by the Burmese novel text. "
                                "Do not explain your process or summarize the chapter."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 1,
                },
            )
    except httpx.HTTPError as e:
        raise ProviderError(
            f"AI network error: {e}", retryable=True
        ) from e

    if r.status_code >= 400:
        body = r.text[:1000]
        raise ProviderError(
            f"AI HTTP {r.status_code}: {body}",
            quota=_quota_error(r.status_code, body),
            retryable=r.status_code >= 500,
        )

    try:
        return r.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise ProviderError(
            "AI provider မှ စာသားမရရှိပါ။ Response structure ကိုစစ်ပါ။"
        )
