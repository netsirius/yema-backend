# yema-backend

API de Yema: catálogo + **motor de veredictos server-side** (el activo
defendible vive aquí, no en el cliente) sobre el Postgres del VPS.

```
GET /health
GET /products/{ean}/verdict     → {product, verdict}
GET /foods/search?q=&lang=      → resultados evaluados
GET /weekly/{week}              → contenido editorial (semana más cercana)
GET /restaurant                 → guía por cocinas, platos evaluados
```

El contrato replica la capa mock de la app Flutter (`lib/mockdb.dart`):
mismos campos y semántica; el motor (`app/engine.py`) es un port 1:1 de
`MockDb.evaluate` con su agregación fail-safe, y cada veredicto incluye
`rule_id`/`rule_version` (trazabilidad clínica).

## Desarrollo

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DATABASE_URL=postgresql://yema:...@76.13.37.201:5433/yema \
  .venv/bin/uvicorn app.main:app --reload
python3 -m unittest discover tests        # motor (equivalencia con el cliente)
python3 seed.py                            # esquema + reglas/contenido desde los mocks de la app
```

## Despliegue en el VPS (fase 2)

1. `docker build -t ghcr.io/<usuario>/yema-api . && docker push ...`
2. Añadir el servicio `api` al proyecto Docker `yema` (ver
   `yema-pipelines/deploy/docker-compose.yml`, bloque comentado) con labels
   de Traefik para `api.<dominio>` — Traefik ya corre en el VPS.
