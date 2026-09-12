# Deploying the Kiku API on Render's free plan

What you get for free: a public HTTPS URL, auto-deploy on push to `main`,
0.1 CPU and 512 MB RAM, and 750 instance-hours per month per workspace.

Two limits shape every decision below:

1. **The service sleeps.** Render spins down a free web service after 15
   minutes with no traffic. The next request pays a cold start of roughly
   30-60 seconds while the container boots and loads the dictionary.
2. **Free Render Postgres expires 30 days after creation** (then a 14-day
   grace period, then deletion). So we use a **Neon** free database instead,
   which has no expiry.

## 1. Create the database (Neon, 3 minutes)

1. Sign up at neon.com and create a project named `kiku`.
2. Copy the **connection string** from the dashboard. It looks like:

   ```
   postgresql://user:password@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```

3. Change the scheme to the driver this project uses:

   ```
   postgresql+psycopg://user:password@ep-xxx.../neondb?sslmode=require
   ```

   Keep `?sslmode=require`. Neon rejects unencrypted connections, and
   `pool_recycle` in `app/db/session.py` is already tuned for a proxy that
   closes idle connections.

## 2. Deploy the service

The repo contains `render.yaml`, so use a Blueprint rather than clicking
through the form:

1. Push the repo to GitHub.
2. In Render: **New > Blueprint**, select the repo, and confirm.
3. Render reads `render.yaml` and asks for the three secret values:

   | Variable | Value |
   | --- | --- |
   | `DATABASE_URL` | the Neon string from step 1 |
   | `FIREBASE_PROJECT_ID` | your Firebase project id (e.g. `kiku-app`) |
   | `LLM_API_KEY` | your OpenAI key, or leave blank to use stub glosses |

4. Click **Apply**. The first build takes 5-10 minutes because the image
   compiles the MeCab wrapper.

If you prefer the manual route: **New > Web Service**, connect the repo, set
runtime **Docker**, root directory `backend`, health check path `/health`,
plan **Free**, then add the same environment variables by hand.

## 3. Verify

```bash
curl https://kiku-api.onrender.com/health
```

Expect something like:

```json
{
  "status": "ok",
  "tokenizer": "fugashi",
  "dictionary_entries": 55,
  "llm": "openai"
}
```

`"tokenizer": "longest-match"` means MeCab did not load and word splitting
is running on the fallback. Check the build logs for a `fugashi` error before
shipping the app against it.

Then build a real lesson:

```bash
curl -X POST https://kiku-api.onrender.com/lessons \
  -H "Authorization: Bearer <firebase-id-token>" \
  -H "Content-Type: application/json" \
  -d "{\"subtitles\": $(jq -Rs . < backend/sample/cafe.srt)}"
```

## 4. Point the app at it

In `android/local.properties`:

```properties
API_BASE_URL=https://kiku-api.onrender.com/
```

The trailing slash is required; Retrofit silently misbuilds URLs without it.
For release builds, set `API_BASE_URL` as a GitHub secret so `release.yml`
picks it up.

## 5. Living with the free plan

**Cold starts.** The OkHttp client already allows 90 seconds, so a cold start
won't throw. But a spinner for a minute feels broken, so the Today screen
should say something honest while importing. Two options if it annoys you:

- A GitHub Actions cron hitting `/health` every 10 minutes keeps the service
  warm — but it burns instance hours (750/month is only ~31 days of one
  service running nonstop, so a warm service uses nearly the whole budget).
- Pay $7/month for the Starter plan, which never sleeps. This is the honest
  answer once you have real users.

**Memory.** 512 MB is the real constraint. `unidic-lite` (~50 MB) is used
deliberately instead of full UniDic (~500 MB), which would be OOM-killed on
this plan. `render.yaml` also caps lessons at 60 lines and subtitles at
256 KB for the same reason. If the service restarts mid-import, that is the
OOM killer, not a bug in the code.

**Migrations** run automatically: the container's start command is
`alembic upgrade head && uvicorn ...`. A failed migration fails the deploy
rather than serving a broken schema.

**Cost ceiling.** No credit card is required, and a free service cannot
incur charges — it just stops when the monthly hours run out.
