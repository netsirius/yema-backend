-- Yema · esquema v0 (plan técnico §5 + anexo T.1).
-- Mismo shape que los mocks de la app y que el pipeline: conectar = no migrar.

CREATE TABLE IF NOT EXISTS products (
  ean             TEXT PRIMARY KEY,
  name            TEXT,
  brand           TEXT,
  category        TEXT,
  ingredients_raw TEXT,
  attributes      JSONB NOT NULL DEFAULT '{}',
  source          TEXT NOT NULL,              -- 'off' | 'crowd' | 'brand'
  confidence      REAL NOT NULL,
  product_type    TEXT NOT NULL DEFAULT 'food', -- 'food' | 'cosmetic'
  updated_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON products USING gin (to_tsvector('spanish', coalesce(name,'')));

-- Reglas como datos, versionadas (trazabilidad clínica). El payload JSONB
-- replica exactamente el formato de assets/mock/risk_rules.json.
CREATE TABLE IF NOT EXISTS risk_rules (
  id          INT PRIMARY KEY,
  version     INT NOT NULL DEFAULT 1,
  active      BOOLEAN NOT NULL DEFAULT true,
  payload     JSONB NOT NULL,
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Alimentos genéricos sin código de barras (búsqueda) y guía restaurante.
CREATE TABLE IF NOT EXISTS foods (
  id         TEXT PRIMARY KEY,
  payload    JSONB NOT NULL,                  -- {name:{es,en}, category, attributes}
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS restaurant_guide (
  id         SERIAL PRIMARY KEY,
  payload    JSONB NOT NULL,                  -- {cuisine:{es,en}, dishes:[...]}
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Contenido semanal editorial (anexo T.1), editable sin publicar app.
CREATE TABLE IF NOT EXISTS weekly_content (
  week       INT PRIMARY KEY,
  payload    JSONB NOT NULL,
  reviewed_by TEXT,
  version    INT NOT NULL DEFAULT 1,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
