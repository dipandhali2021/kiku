"""FastAPI application entry point.

One service. Tokenisation, dictionary lookup, LLM glossing, storage, and auth
verification all live here. See docs/decisions.md for why this is a single
Python service rather than a Kotlin or JVM backend beside it.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.session import init_db
from app.llm.client import get_llm_client
from app.nlp.dictionary import get_dictionary
from app.nlp.tokenizer import get_tokenizer
from app.routers import lessons, reviews, words
from app.schemas import HealthOut

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("kiku")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm the expensive singletons at startup.

    The tokeniser loads a large dictionary on first use. Doing that here means
    the cost lands on container start, not on a user's first lesson.
    """
    init_db()
    tokenizer = get_tokenizer()
    dictionary = get_dictionary()
    logger.info(
        "kiku %s ready: tokenizer=%s dictionary=%d entries llm=%s env=%s",
        settings.version,
        tokenizer.name,
        len(dictionary),
        get_llm_client().name,
        settings.environment,
    )
    if settings.dev_auth_allowed:
        logger.warning("AUTH_DEV_MODE is on: 'Bearer dev:<uid>' tokens are accepted")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    summary="Turn Japanese video clips into lessons.",
    lifespan=lifespan,
)

# The Android client does not need CORS; this is for the web demo and docs.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else ["https://kiku.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lessons.router)
app.include_router(words.router)
app.include_router(reviews.router)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    """Domain errors are client errors, not 500s."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/health", response_model=HealthOut, tags=["meta"])
def health() -> HealthOut:
    """Liveness probe. Reports which engines actually loaded.

    This is the endpoint to check after a deploy: if `tokenizer` says
    `longest-match` in production, MeCab did not load and lesson quality is
    silently degraded.
    """
    return HealthOut(
        status="ok",
        version=settings.version,
        environment=settings.environment,
        tokenizer=get_tokenizer().name,
        llm=get_llm_client().name,
        dictionary_entries=len(get_dictionary()),
    )
