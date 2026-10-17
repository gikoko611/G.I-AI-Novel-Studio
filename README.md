# G.I AI Novel Studio — FastAPI Backend

Termux-friendly starter backend: FastAPI + SQLite, chapter checkpoints, quota pause, resume, idempotency keys, partial PDF and optional MP3 export.

## Important notes

- API keys stay in backend environment variables. Do not put keys in browser JavaScript or commit `.env`.
- SQLite persists in `data/novel_studio.db`. Back up the `data/` folder.
- Quota handling depends on the provider's returned HTTP code/message. Some providers report billing exhaustion as 400/403; inspect the `last_error` and adjust `app/providers.py` if necessary.
- MP3 uses `edge-tts` and internet access. The configured Burmese voice may not be available in every region/service version.
- ReportLab's built-in fonts may not render Myanmar script correctly. Set `MYANMAR_FONT_PATH` and add font registration if you need embedded Myanmar font PDF output. The endpoint currently produces the PDF layout but Myanmar glyph support must be validated with a real Myanmar TTF.
- This starter does not include authentication. Do not expose it publicly with unrestricted access; add auth and exact CORS origins before public use.
- For production multi-worker deployment, use a job queue/worker and database-backed locking. The starter's unique chapter constraint and idempotency keys protect common retries but are not a distributed job queue.

## 1. Termux setup

```bash
pkg update
pkg install python git
mkdir -p ~/projects
cd ~/projects
# Put/unzip this folder here, then:
cd GI-AI-Novel-Studio-Backend
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with a terminal-friendly method, or set variables in the shell before running. Never paste real API keys into public chat or GitHub.

Example for Groq-compatible API:
```bash
export AI_PROVIDER=openai_compatible
export AI_BASE_URL=https://api.groq.com/openai/v1
export AI_MODEL=openai/gpt-oss-120b
export AI_API_KEY='YOUR_KEY_HERE'
```

Example Gemini:
```bash
export AI_PROVIDER=gemini
export GEMINI_MODEL=gemini-2.5-flash
export GEMINI_API_KEY='YOUR_KEY_HERE'
```

## 2. Start server

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open on the phone: `http://127.0.0.1:8000/docs`
Health: `http://127.0.0.1:8000/api/health`

## 3. Test workflow

Create a novel:
```bash
curl -sS -X POST http://127.0.0.1:8000/api/novels \
  -H 'Content-Type: application/json' \
  -d '{"title":"ညအမှောင်ထဲကအသံ","idea":"မြို့ငယ်တစ်ခုတွင် ပျောက်ဆုံးမှုများကို စုံထောက်တစ်ဦး စုံစမ်းသည်","genre":"mystery","target_chapters":8}'
```
Copy the returned `id`.

Generate one chapter (use the same idempotency key if retrying the same request):
```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/novels/PASTE_ID/generate' \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: novel-1-chapter-1-attempt-1' \
  -d '{"chapters":1}'
```

Check progress:
```bash
curl -sS http://127.0.0.1:8000/api/novels/PASTE_ID
```

Continue after quota reset:
```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/novels/PASTE_ID/resume' \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: novel-1-resume-attempt-2' \
  -d '{"chapters":1}'
```

Partial PDF:
`http://127.0.0.1:8000/api/novels/PASTE_ID/export/pdf`

Partial MP3:
`http://127.0.0.1:8000/api/novels/PASTE_ID/export/mp3`

## 4. Deploying

Use a persistent disk/storage for `data/` on the hosting platform. If the host's filesystem is ephemeral, SQLite data may be lost on redeploy/restart. For Render, attach a persistent disk and set `DATABASE_PATH` and `OUTPUT_DIR` to paths on that disk. Add provider keys in the service Environment page. Restrict `CORS_ORIGINS` and add authentication before public production use.

## API summary

- `GET /api/health`
- `GET /api/config`
- `POST /api/novels`
- `GET /api/novels`
- `GET /api/novels/{id}`
- `POST /api/novels/{id}/generate`
- `POST /api/novels/{id}/resume`
- `GET /api/novels/{id}/chapters/{chapter_no}`
- `GET /api/novels/{id}/export/pdf`
- `GET /api/novels/{id}/export/mp3`
- `DELETE /api/novels/{id}`

Use `/docs` to test interactively.
