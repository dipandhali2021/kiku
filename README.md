# Kiku

Turn any Japanese video clip into a lesson. Point Kiku at a subtitle file and
it returns the dialogue line by line with romaji, natural English, and a note
on every word explaining the form that actually appears on screen.

The video never leaves your phone. Only the subtitle text is sent to the API.

## What works today

The language pipeline is pure standard library, so it runs with no
dependencies and no network:

```bash
cd backend
python3 -m app.cli sample/cafe.srt
```

Output for the bundled cafe scene:

```
もう / 行かなきゃ。        mou ikanakya.        I have to go.
ちょっと / 待って / くれない   chotto matte kurenai?  Could you wait a sec?
```

`python3 -m tests.test_nlp` and `python3 -m tests.test_srs` run the same way:
32 assertions covering romanisation, subtitle parsing, tokenisation, lesson
building, and spaced repetition.

## Architecture

```
android/   Kotlin + Compose (Material 3), Media3 player, Room cache
backend/   FastAPI + SQLAlchemy, MeCab/UniDic tokenizer, FSRS-style scheduler
shared/    lesson.schema.json, the contract between the two
```

The backend is deliberately one service. Tokenisation needs a 100 MB+
dictionary resident in memory, which rules out serverless platforms such as
Vercel; the image is built to run on Render or Cloud Run with Postgres. See
`docs/deploy-render.md` for the free-tier deploy.

Tokenisation degrades rather than fails: if MeCab is unavailable the API falls
back to a longest-match tokenizer and reports which engine is live at
`GET /health`, so a misconfigured deploy is visible instead of silent.

## Running the API locally

```bash
cd backend
cp .env.example .env
uv sync --group dev          # or: pip install -e ".[nlp]"
uv run uvicorn app.main:app --reload --port 8080
```

With `AUTH_DEV_MODE=true` you can authenticate as anyone:

```bash
curl -X POST localhost:8080/lessons \
  -H "Authorization: Bearer dev:me" \
  -H "Content-Type: application/json" \
  -d "{\"subtitles\": $(jq -Rs . < sample/cafe.srt)}"
```

| Endpoint | Purpose |
| --- | --- |
| `POST /lessons` | Build a lesson from subtitle text (cached by content hash) |
| `GET /lessons/{clip_id}` | Fetch a built lesson |
| `POST /words` | Save a word for review |
| `GET /reviews` | Due queue, hardest first |
| `POST /reviews` | Grade a card (0 again, 1 hard, 2 good, 3 easy) |
| `GET /progress` | Saved words, due count, streak |
| `GET /health` | Status plus active tokenizer and dictionary size |

## Running the app

```bash
cd android
gradle wrapper --gradle-version 8.11   # first time only
./gradlew assembleDebug
```

Debug builds point at `http://10.0.2.2:8080/` (the host machine from an
emulator) and use dev auth, so Firebase is optional until you ship. Override
with `API_BASE_URL` in `local.properties`.

## CI and releases

| Workflow | Trigger | Result |
| --- | --- | --- |
| `backend-ci.yml` | changes under `backend/` | ruff, mypy, pytest, stdlib smoke test, Docker image to GHCR |
| `android-ci.yml` | changes under `android/` | unit tests, debug APK artifact, Compose UI tests on main |
| `release.yml` | pushing a `v*` tag | signed APK + AAB with checksums on a GitHub Release, tagged backend image |

Release secrets: `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`,
`KEY_PASSWORD`, `GOOGLE_SERVICES_JSON`, `API_BASE_URL`. Generate the keystore
once and keep it forever — losing it means you can never update the app
under the same listing.

```bash
keytool -genkeypair -v -keystore kiku-release.jks -keyalg RSA \
  -keysize 4096 -validity 10000 -alias kiku
base64 -w0 kiku-release.jks   # paste into the KEYSTORE_BASE64 secret
```

## MVP scope

In: import subtitles, line-by-line lesson with tappable words, save words,
spaced review, offline replay of imported lessons, anonymous sign-in.

Out for now: speaking practice, clip library, social features, iOS.
