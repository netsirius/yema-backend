"""Aplica el esquema y siembra reglas/alimentos/contenido desde los mocks
de la app (única fuente de verdad hasta que exista el panel clínico).

    python3 seed.py            # usa deploy/.env de yema-pipelines o DATABASE_URL
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import psycopg

HERE = pathlib.Path(__file__).parent
MOCKS = HERE.parent / "yema" / "assets" / "mock"


def database_url() -> str:
    if url := os.environ.get("DATABASE_URL"):
        return url
    env = HERE.parent / "yema-pipelines" / "deploy" / ".env"
    if env.exists():
        vals = dict(line.strip().split("=", 1) for line in env.read_text().splitlines() if "=" in line)
        return (f"postgresql://{vals['PGUSER']}:{vals['PGPASSWORD']}"
                f"@{vals['PGHOST']}:{vals['PGPORT']}/{vals['PGDATABASE']}")
    sys.exit("Define DATABASE_URL o crea yema-pipelines/deploy/.env")


def load(name: str):
    return json.loads((MOCKS / f"{name}.json").read_text())


def main() -> None:
    with psycopg.connect(database_url()) as conn:
        conn.execute((HERE / "schema.sql").read_text())

        rules = load("risk_rules")
        for r in rules:
            conn.execute(
                """INSERT INTO risk_rules (id, version, active, payload)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET version=excluded.version,
                     active=excluded.active, payload=excluded.payload,
                     updated_at=now()""",
                (r["id"], r.get("version", 1), r.get("active", True), json.dumps(r)))

        for f in load("foods"):
            conn.execute(
                """INSERT INTO foods (id, payload) VALUES (%s, %s)
                   ON CONFLICT (id) DO UPDATE SET payload=excluded.payload, updated_at=now()""",
                (f["id"], json.dumps(f)))

        conn.execute("DELETE FROM restaurant_guide")
        for g in load("restaurant_guide"):
            conn.execute("INSERT INTO restaurant_guide (payload) VALUES (%s)", (json.dumps(g),))

        for w in load("weekly_content"):
            conn.execute(
                """INSERT INTO weekly_content (week, payload, reviewed_by, version)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (week) DO UPDATE SET payload=excluded.payload,
                     reviewed_by=excluded.reviewed_by, version=excluded.version,
                     updated_at=now()""",
                (w["week"], json.dumps(w), w.get("reviewed_by"), w.get("version", 1)))

        # Los productos curados del demo también entran al catálogo real.
        for p in load("products"):
            conn.execute(
                """INSERT INTO products (ean, name, brand, category, ingredients_raw,
                     attributes, source, confidence, product_type, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (ean) DO UPDATE SET name=excluded.name,
                     brand=excluded.brand, category=excluded.category,
                     ingredients_raw=excluded.ingredients_raw,
                     attributes=excluded.attributes, source=excluded.source,
                     confidence=excluded.confidence,
                     product_type=excluded.product_type,
                     updated_at=excluded.updated_at""",
                (p["ean"], p["name"], p.get("brand"), p.get("category"),
                 p.get("ingredients_raw"), json.dumps(p.get("attributes", {})),
                 p["source"], p["confidence"], p.get("product_type", "food"),
                 p["updated_at"]))

        counts = {}
        for table in ("risk_rules", "foods", "restaurant_guide", "weekly_content", "products"):
            counts[table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print("Seed OK:", counts)


if __name__ == "__main__":
    main()
