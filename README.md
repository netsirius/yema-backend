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

## API key: dónde vive y cómo rotarla

La clave (`x-api-key`) vive en: el binario de la app (inyectada con
`--dart-define=YEMA_API_KEY=…`), el env del contenedor `api` en el VPS, y
`yema-pipelines/deploy/.env` (copia local, gitignoreada). Es una clave
compartida: frena bots y scraping, no a un atacante que descompile el APK —
para eso, App Attest / Play Integrity (producción).

**Rotación sin romper apps instaladas** (el backend acepta varias claves
separadas por comas):

1. Genera nueva: `openssl rand -hex 20` → `yk_<hex>`.
2. VPS: redespliega el proyecto `yema` con `API_KEY=nueva,antigua`.
3. App: publica build con `--dart-define=YEMA_API_KEY=yk_nueva`.
4. Cuando la flota esté actualizada: redespliega con `API_KEY=nueva` sola.
5. Actualiza `deploy/.env` local.

Rotar YA (clave comprometida): salta el paso de convivencia — las apps
antiguas caerán al motor offline hasta actualizarse (degradación elegante).

## Despliegue en el VPS (fase 2)

1. `docker build -t ghcr.io/<usuario>/yema-api . && docker push ...`
2. Añadir el servicio `api` al proyecto Docker `yema` (ver
   `yema-pipelines/deploy/docker-compose.yml`, bloque comentado) con labels
   de Traefik para `api.<dominio>` — Traefik ya corre en el VPS.
