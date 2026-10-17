import asyncio
import re
import logging
import uuid
from pathlib import Path
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import (
    AI_PROVIDER, AI_MODEL, GEMINI_MODEL, OUTPUT_DIR, MAX_CHAPTERS_PER_REQUEST
)
from .db import init_db, connect, now, rowdict, novel_with_chapters
from .providers import generate_text, ProviderError

logger = logging.getLogger(__name__)

app = FastAPI(title="G.I AI Novel Studio API", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"]
)
# For public deployment, replace "*" with the exact frontend origin(s).

@app.on_event("startup")
def startup():
    init_db()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class NovelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    idea: str = Field(min_length=5, max_length=10000)
    genre: str = Field(default="mystery", max_length=80)
    target_chapters: int = Field(default=10, ge=1, le=200)
    provider: Literal["openai_compatible", "gemini"] | None = None
    model: str | None = None

class GenerateRequest(BaseModel):
    chapters: int = Field(default=1, ge=1, le=10)

def selected_provider(novel):
    provider = novel["provider"]
    model = novel["model"]
    return provider, model

def chapter_prompt(novel, chapter_no, previous):
    prior = ""
    if previous:
        last = previous[-1]
        prior = (
            f"\nယခင်အခန်း၏ နောက်ဆုံးအပိုင်း (အဆက်အစပ်အတွက်သာ):\n"
            f"{last['content'][-2500:]}\n"
        )

    return f"""
သင်သည် မြန်မာဘာသာဖြင့် ဖတ်ရှုရလွယ်ကူပြီး သဘာဝကျသော ဝတ္ထုရေးသားသူဖြစ်သည်။

ဝတ္ထုအမည်: {novel['title']}
အမျိုးအစား: {novel['genre']}
အဓိကဇာတ်လမ်းအကြောင်းအရာ: {novel['idea']}
ရေးသားရမည့်အခန်း: {chapter_no}

အောက်ပါစည်းမျဉ်းများကို တိကျစွာ လိုက်နာပါ။

၁။ သဘာဝကျပြီး အဓိပ္ပာယ်ရှင်းလင်းသော မြန်မာစကားပြေကို သုံးပါ။ ဘာသာပြန်စက်ဆန်သော
ဝါကျများ၊ အဓိပ္ပာယ်မရှင်းသော စကားစုများနှင့် အကြောင်းမဲ့ စကားလုံးထပ်ခြင်းကို ရှောင်ပါ။
၂။ ဝါကျတိုနှင့် ဝါကျအလတ်များကို သင့်လျော်စွာ ရောနှောသုံးပါ။ စာပိုဒ်တစ်ပိုဒ်စီသည်
အတွေးတစ်ခု၊ လုပ်ဆောင်ချက်တစ်ခု သို့မဟုတ် ခံစားချက်တစ်ခုကို ရှင်းလင်းစွာ ဖော်ပြပါ။
၃။ ဇာတ်ကောင်များ၏ အမည်၊ ရည်ရွယ်ချက်၊ ဆက်ဆံရေး၊ အချိန်အစဉ်နှင့် ဖြစ်ရပ်အချက်အလက်များ
ကို တစ်သမတ်တည်း ထိန်းသိမ်းပါ။
၄။ ဇာတ်လမ်းကို အကျဉ်းချုပ်သက်သက် မရေးပါနှင့်။ မြင်ကွင်းများကို လုပ်ဆောင်ချက်၊
သဘာဝကျသော စကားပြောခန်း၊ ပတ်ဝန်းကျင်နှင့် ယုံကြည်လက်ခံနိုင်သော ခံစားချက်များဖြင့် ဖော်ပြပါ။
၅။ ဇာတ်ကောင်တစ်ဦးစီ၏ စကားပြောပုံကို ၎င်းတို့၏ စရိုက်၊ အခြေအနေနှင့် ဆက်ဆံရေးအလိုက်
ကွဲပြားစေပါ။ ဇာတ်ကောင်အားလုံးကို တူညီသောပုံစံဖြင့် မပြောစေပါနှင့်။
၆။ အကြောင်းမရှိဘဲ ဖြစ်ရပ်များ ရုတ်တရက် မပြောင်းစေရ။ အရေးကြီးသော ဆုံးဖြတ်ချက်များနှင့်
ဇာတ်လမ်းအလှည့်အပြောင်းများတွင် ယုတ္တိရှိသော အကြောင်းပြချက် ရှိရမည်။
၇။ ယခင်အခန်းမှ စာပိုဒ်များနှင့် ဖြစ်ရပ်များကို ထပ်မကူးပါနှင့်။ ဇာတ်လမ်းကို ရှေ့ဆက်တိုးတက်စေပါ။
၈။ ရွေးချယ်ထားသော အမျိုးအစားနှင့် ကိုက်ညီပါစေ။ စုံထောက်ဝတ္ထုတွင် သဲလွန်စနှင့် ယုတ္တိကို
ထိန်းသိမ်းပါ။ သရဲဝတ္ထုတွင် တဖြည်းဖြည်းတင်းမာမှု တည်ဆောက်ပါ။ အချစ်ဝတ္ထုတွင်
ခံစားချက်နှင့် ဆက်ဆံရေးတိုးတက်မှုကို ယုံကြည်လက်ခံနိုင်အောင် ဖော်ပြပါ။
၉။ အခန်းတစ်ခန်းတွင် အစ၊ အလယ်၊ အဆုံး ရှိရမည်။ အဆုံးတွင် နောက်အခန်းကို ဆက်ဖတ်ချင်စေမည့်
သဘာဝကျသော ပြဿနာ သို့မဟုတ် မေးခွန်းတစ်ခု ချန်ထားပါ။
၁၀။ အဓိပ္ပာယ်မရှိသော စကားများဖြင့် စာရှည်အောင် မလုပ်ပါနှင့်။ ဇာတ်လမ်းအတွက် အရေးမပါသော
အကြောင်းအရာများ၊ ထပ်နေသော ရှင်းလင်းချက်များနှင့် အလွန်အကျွံ ကဗျာဆန်သော အသုံးအနှုန်းများကို ရှောင်ပါ။
၁၁။ မြန်မာဘာသာဖြင့်သာ ရေးပါ။ AI အကြောင်း၊ ရေးသားပုံအကြောင်း ရှင်းလင်းချက်၊
အခန်းအကျဉ်းချုပ် သို့မဟုတ် စာဖတ်သူထံသို့ မှတ်ချက် မထည့်ပါနှင့်။
၁၂။ ပထမစာကြောင်းကို "အခန်း {chapter_no}" ဖြင့် စတင်သော အခန်းခေါင်းစဉ်အဖြစ် ရေးပါ။
၁၃။ ဖြစ်နိုင်လျှင် အခန်းတစ်ခန်းလျှင် မြန်မာစကားလုံး ၉၀၀ မှ ၁၄၀၀ ခန့် ရေးပါ။
အရည်အသွေးနှင့် ဇာတ်လမ်းအဆက်အစပ်ကို စကားလုံးအရေအတွက်ထက် ဦးစားပေးပါ။

{prior}
ယခုအခန်းကို တိုက်ရိုက်ရေးသားပါ။ ခေါင်းစဉ်ပြီးနောက် ဝတ္ထုစာသားကိုသာ ထုတ်ပါ။
""".strip()


@app.get("/api/health")
def health():
    return {"ok": True, "service": "G.I AI Novel Studio API", "version": "1.0.0"}

@app.get("/api/config")
def config():
    # Never return API keys.
    return {"provider": AI_PROVIDER, "model": AI_MODEL if AI_PROVIDER == "openai_compatible" else GEMINI_MODEL,
            "max_chapters_per_request": MAX_CHAPTERS_PER_REQUEST}

@app.post("/api/novels", status_code=201)
def create_novel(payload: NovelCreate):
    novel_id = str(uuid.uuid4())
    provider = payload.provider or AI_PROVIDER
    model = payload.model or (GEMINI_MODEL if provider == "gemini" else AI_MODEL)
    timestamp = now()
    with connect() as con:
        con.execute("""
            INSERT INTO novels(id,title,idea,genre,target_chapters,provider,model,status,next_chapter,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,'draft',1,?,?)
        """, (novel_id, payload.title.strip(), payload.idea.strip(), payload.genre,
              payload.target_chapters, provider, model, timestamp, timestamp))
    return novel_with_chapters(novel_id)

@app.get("/api/novels")
def list_novels():
    with connect() as con:
        rows = con.execute("""
            SELECT n.*,
              (SELECT COUNT(*) FROM chapters c WHERE c.novel_id=n.id) AS completed_chapters
            FROM novels n ORDER BY n.updated_at DESC
        """).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/novels/{novel_id}")
def get_novel(novel_id: str):
    novel = novel_with_chapters(novel_id)
    if not novel:
        raise HTTPException(404, "Novel မတွေ့ပါ။")
    return novel

@app.post("/api/novels/{novel_id}/generate")
async def generate_chapters(
    novel_id: str,
    payload: GenerateRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    api_key: Optional[str] = Header(default=None, alias="X-AI-API-Key"),
    gemini_api_key: Optional[str] = Header(default=None, alias="X-Gemini-API-Key"),
    ai_base_url: Optional[str] = Header(default=None, alias="X-AI-Base-URL"),
):
    # One request generates sequentially; default is one chapter to limit spend.
    requested = min(payload.chapters, MAX_CHAPTERS_PER_REQUEST)
    novel = novel_with_chapters(novel_id)
    if not novel:
        raise HTTPException(404, "Novel မတွေ့ပါ။")
    if novel["status"] == "paused_quota":
        raise HTTPException(409, "Credit limit ကြောင့် pause ဖြစ်နေသည်။ Credit ပြန်ရပြီး /resume ကိုခေါ်ပါ။")

    # SQLite unique request key blocks accidental duplicate POSTs from a client retry.
    key = idempotency_key or f"{novel_id}:{novel['next_chapter']}:{uuid.uuid4()}"
    with connect() as con:
        existing = con.execute("SELECT * FROM requests WHERE idempotency_key=?", (key,)).fetchone()
        if existing:
            if existing["status"] == "completed":
                return novel_with_chapters(novel_id)
            if existing["status"] == "running":
                raise HTTPException(409, "ဤ generation request သည် လုပ်ဆောင်နေဆဲဖြစ်သည်။")
            # Failed keys are deliberately not replayed; use a new key after inspecting status.
            if existing["status"] == "failed":
                raise HTTPException(409, "ဤ request key ဖြင့် ယခင်က fail ဖြစ်ထားသည်။ Key အသစ်သုံးပါ။")
        con.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,?)",
                    (key, novel_id, novel["next_chapter"], "running", now(), now(), None))
        con.execute("UPDATE novels SET status='generating',last_error=NULL,updated_at=? WHERE id=?",
                    (now(), novel_id))

    try:
        for _ in range(requested):
            novel = novel_with_chapters(novel_id)
            chapter_no = novel["next_chapter"]
            if chapter_no > novel["target_chapters"]:
                with connect() as con:
                    con.execute("UPDATE novels SET status='completed',updated_at=? WHERE id=?", (now(), novel_id))
                break

            # Recheck before calling provider; UNIQUE(novel_id, chapter_no) prevents duplicate checkpoints.
            with connect() as con:
                exists = con.execute("SELECT 1 FROM chapters WHERE novel_id=? AND chapter_no=?",
                                     (novel_id, chapter_no)).fetchone()
            if exists:
                with connect() as con:
                    con.execute("UPDATE novels SET next_chapter=?,updated_at=? WHERE id=?",
                                (chapter_no + 1, now(), novel_id))
                continue

            try:
                text = await generate_text(
                    chapter_prompt(novel, chapter_no, novel["chapters"]),
                    provider=novel["provider"],
                    model=novel["model"],
                    base_url=ai_base_url,
                    api_key=api_key,
                    gemini_api_key=gemini_api_key,
                )
            except ProviderError as e:
                status = "paused_quota" if e.quota else "paused_error"
                with connect() as con:
                    con.execute("UPDATE novels SET status=?,last_error=?,updated_at=? WHERE id=?",
                                (status, str(e)[:1500], now(), novel_id))
                    con.execute("UPDATE requests SET status='failed',error=?,updated_at=? WHERE idempotency_key=?",
                                (str(e)[:1500], now(), key))
                if e.quota:
                    raise HTTPException(429, {
                        "status": "paused_quota",
                        "message": "AI quota/credit limit ဖြစ်နေသည်။ ရေးပြီးသားအခန်းများ သိမ်းပြီးဖြစ်သည်။",
                        "detail": str(e)[:500],
                        "resume_endpoint": f"/api/novels/{novel_id}/resume"
                    })
                raise HTTPException(502, {"status": status, "message": str(e)[:500],
                                          "saved_chapters": novel["completed_chapters"]})

            lines = text.splitlines()
            chapter_title = lines[0].strip()[:250] if lines else f"အခန်း {chapter_no}"
            if len(lines) > 1:
                body = "\n".join(lines[1:]).strip()
            else:
                body = text
            if not body:
                body = text
            # Checkpoint commit: chapter content and next_chapter update in one transaction.
            with connect() as con:
                con.execute("""
                    INSERT OR IGNORE INTO chapters(novel_id,chapter_no,title,content,status,created_at)
                    VALUES(?,?,?,?, 'completed', ?)
                """, (novel_id, chapter_no, chapter_title or f"အခန်း {chapter_no}", body, now()))
                con.execute("UPDATE novels SET next_chapter=?,status=?,last_error=NULL,updated_at=? WHERE id=?",
                            (chapter_no + 1,
                             "completed" if chapter_no >= novel["target_chapters"] else "ready",
                             now(), novel_id))

        with connect() as con:
            con.execute("UPDATE requests SET status='completed',updated_at=? WHERE idempotency_key=?",
                        (now(), key))
        return novel_with_chapters(novel_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected generation error for novel_id=%s", novel_id)
        with connect() as con:
            con.execute("UPDATE novels SET status='paused_error',last_error=?,updated_at=? WHERE id=?",
                        (str(e)[:1500], now(), novel_id))
            con.execute("UPDATE requests SET status='failed',error=?,updated_at=? WHERE idempotency_key=?",
                        (str(e)[:1500], now(), key))
        raise HTTPException(500, "Generation error ဖြစ်သွားသည်။ သိမ်းပြီးသားအခန်းများ မဖျက်ပါ။")

@app.post("/api/novels/{novel_id}/resume")
async def resume_novel(
    novel_id: str,
    payload: GenerateRequest = GenerateRequest(),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    api_key: Optional[str] = Header(default=None, alias="X-AI-API-Key"),
    gemini_api_key: Optional[str] = Header(default=None, alias="X-Gemini-API-Key"),
    ai_base_url: Optional[str] = Header(default=None, alias="X-AI-Base-URL"),
):
    novel = novel_with_chapters(novel_id)
    if not novel:
        raise HTTPException(404, "Novel မတွေ့ပါ။")
    if novel["next_chapter"] > novel["target_chapters"]:
        with connect() as con:
            con.execute("UPDATE novels SET status='completed',updated_at=? WHERE id=?", (now(), novel_id))
        return novel_with_chapters(novel_id)
    # Resume simply re-enters the same checkpoint-aware generator.
    with connect() as con:
        con.execute("UPDATE novels SET status='ready',last_error=NULL,updated_at=? WHERE id=?", (now(), novel_id))
    return await generate_chapters(
        novel_id, payload, idempotency_key, api_key, gemini_api_key, ai_base_url
    )

@app.get("/api/novels/{novel_id}/chapters/{chapter_no}")
def get_chapter(novel_id: str, chapter_no: int):
    with connect() as con:
        row = con.execute("SELECT * FROM chapters WHERE novel_id=? AND chapter_no=?",
                          (novel_id, chapter_no)).fetchone()
    if not row:
        raise HTTPException(404, "အခန်း မတွေ့ပါ။")
    return dict(row)

def pdf_escape(text):
    # Escape ReportLab markup while retaining readable line breaks.
    return escape(text).replace("\n", "<br/>")

@app.get("/api/novels/{novel_id}/export/pdf")
def export_pdf(novel_id: str):
    raise HTTPException(
        status_code=501,
        detail="PDF export ကို ယာယီပိတ်ထားသည်။ ReportLab မတပ်ဆင်ထားပါ။"
    )

@app.get("/api/novels/{novel_id}/export/mp3")
async def export_mp3(novel_id: str, voice: str = "my-MM-NilarNeural"):
    novel = novel_with_chapters(novel_id)
    if not novel:
        raise HTTPException(404, "Novel မတွေ့ပါ။")
    if not novel["chapters"]:
        raise HTTPException(400, "MP3 ထုတ်ရန် သိမ်းထားသောအခန်း မရှိသေးပါ။")
    try:
        import edge_tts
    except ImportError:
        raise HTTPException(501, "edge-tts မတပ်ဆင်ရသေးပါ။ requirements.txt ကို install လုပ်ပါ။")
    # Edge TTS requires internet; availability of a Burmese voice depends on the TTS service.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{novel_id}-partial.mp3"
    text = "\n\n".join(f"{c['title']}\n{c['content']}" for c in novel["chapters"])
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(path))
    except Exception as e:
        raise HTTPException(502, f"TTS export မအောင်မြင်ပါ။ Voice availability/network ကိုစစ်ပါ။ {str(e)[:300]}")
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type="audio/mpeg", filename=f"{novel['title']}-partial.mp3")

@app.delete("/api/novels/{novel_id}")
def delete_novel(novel_id: str):
    with connect() as con:
        result = con.execute("DELETE FROM novels WHERE id=?", (novel_id,))
        if result.rowcount == 0:
            raise HTTPException(404, "Novel မတွေ့ပါ။")
    return {"ok": True, "deleted": novel_id}


# Serve the static frontend only after registering all API routes.
from fastapi.staticfiles import StaticFiles

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
