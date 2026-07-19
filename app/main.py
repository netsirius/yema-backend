"""API de Yema — catálogo + motor de veredictos servidos desde Postgres.

    uvicorn app.main:app --reload

Contrato = el de la capa mock de la app Flutter: mismos campos, mismos
significados. La app cambia MockDb por HTTP y nada más se toca.
"""
from __future__ import annotations

import hmac
import json
import os
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from . import engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://yema:yema@localhost:5433/yema")
# ponytail: API key compartida — sube el listón contra bots/scraping; la
# protección "solo la app genuina" real llega con App Attest/Play Integrity.
# Acepta VARIAS claves separadas por comas para rotar sin romper las apps
# ya instaladas: API_KEY="nueva,antigua" durante la ventana de rotación.
API_KEYS = [k.strip() for k in os.environ.get("API_KEY", "").split(",") if k.strip()]


def _valid_key(provided: str) -> bool:
    return any(hmac.compare_digest(provided, k) for k in API_KEYS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = AsyncConnectionPool(DATABASE_URL, min_size=1, max_size=8, open=False)
    await app.state.pool.open()
    yield
    await app.state.pool.close()


app = FastAPI(title="Yema API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    # /health queda abierto para monitorización.
    if API_KEYS and request.url.path != "/health":
        if not _valid_key(request.headers.get("x-api-key", "")):
            return JSONResponse({"detail": "invalid_api_key"}, status_code=401)
    return await call_next(request)


async def _rules(pool) -> list[dict]:
    # ponytail: las reglas son pocas y cambian poco — query directa; cache
    # en memoria con TTL cuando haya tráfico real.
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        rows = await (await conn.execute(
            "SELECT id, version, active, payload FROM risk_rules WHERE active")).fetchall()
    return [{**r["payload"], "id": r["id"], "version": r["version"], "active": r["active"]}
            for r in rows]


@app.get("/health")
async def health():
    async with app.state.pool.connection() as conn:
        await conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/products/{ean}/verdict")
async def product_verdict(ean: str):
    async with app.state.pool.connection() as conn:
        conn.row_factory = dict_row
        row = await (await conn.execute(
            "SELECT * FROM products WHERE ean = %s", (ean,))).fetchone()
    if row is None:
        raise HTTPException(404, "product_not_found")
    attributes = row["attributes"] or {}
    verdict = engine.evaluate(await _rules(app.state.pool), row["category"], attributes)
    return {
        "product": {
            "ean": row["ean"], "name": row["name"], "brand": row["brand"],
            "category": row["category"], "product_type": row["product_type"],
            "confidence": row["confidence"], "image_url": row.get("image_url"),
        },
        "verdict": verdict,
    }


@app.get("/foods/search")
async def food_search(q: str = Query("", max_length=80), lang: str = "es"):
    async with app.state.pool.connection() as conn:
        conn.row_factory = dict_row
        rows = await (await conn.execute("SELECT id, payload FROM foods")).fetchall()
    rules = await _rules(app.state.pool)
    needle = q.strip().lower()
    results = []
    for row in rows:
        food = row["payload"]
        name = food["name"].get(lang) or food["name"]["es"]
        if needle and needle not in name.lower():
            continue
        results.append({
            "id": row["id"],
            "name": food["name"],
            "category": food.get("category"),
            "verdict": engine.evaluate(rules, food.get("category"), food.get("attributes") or {}),
        })
    return {"results": results}


@app.get("/weekly/{week}")
async def weekly(week: int):
    async with app.state.pool.connection() as conn:
        conn.row_factory = dict_row
        # Semana editorial más cercana (el CMS cubrirá 1..42).
        row = await (await conn.execute(
            "SELECT week, payload FROM weekly_content ORDER BY abs(week - %s) LIMIT 1",
            (week,))).fetchone()
    if row is None:
        raise HTTPException(404, "no_content")
    return {"week": row["week"], **row["payload"]}


@app.get("/restaurant")
async def restaurant():
    async with app.state.pool.connection() as conn:
        conn.row_factory = dict_row
        rows = await (await conn.execute(
            "SELECT payload FROM restaurant_guide ORDER BY id")).fetchall()
    rules = await _rules(app.state.pool)
    guide = []
    for row in rows:
        cuisine = row["payload"]
        guide.append({
            "cuisine": cuisine["cuisine"],
            "dishes": [
                {**dish,
                 "verdict": engine.evaluate(rules, dish.get("category"), dish.get("attributes") or {})}
                for dish in cuisine["dishes"]
            ],
        })
    return {"cuisines": guide}
