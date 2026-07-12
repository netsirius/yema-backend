"""Propone reglas de riesgo con IA — para revisión humana, NUNCA directo a
producción. Gobernanza del plan: la IA redacta, el panel clínico firma.

    python3 tools/propose_rules.py                # categorías sin regla
    python3 tools/propose_rules.py --topic "edulcorantes"
    python3 tools/propose_rules.py --dry-run      # solo muestra el prompt

Salida: proposals/rules_YYYY-MM-DD.json (validadas contra el motor).
Tras revisión humana: añadirlas a assets/mock/risk_rules.json de la app
(fuente de verdad) con reviewed_by, y ejecutar seed.py.

LLM: usa ANTHROPIC_API_KEY si existe; si no, la CLI `claude -p` local.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import urllib.request

HERE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(HERE))
from app import engine  # noqa: E402

RULES_PATH = HERE.parent / "yema" / "assets" / "mock" / "risk_rules.json"
TAXONOMY_PATH = HERE.parent / "yema-pipelines" / "yema_pipelines" / "categories.json"

PROMPT = """Eres el asistente de redacción del panel clínico de Yema, una app \
de seguridad alimentaria para embarazadas (España). Redacta REGLAS DE RIESGO \
en JSON para las categorías indicadas, con estas normas INNEGOCIABLES:

1. SOLO conocimiento establecido de fuentes oficiales: AESAN, EFSA, OMS, ACOG, \
AEMPS. Cada regla lleva source_org y source_url REAL de esa organización. Si no \
hay guía oficial clara para una categoría, NO inventes: devuélvela en la lista \
"sin_evidencia" con una frase de por qué.
2. Principio fail-safe: ante incertidumbre, el veredicto más prudente. Usa \
"condition" con "if_unknown": "assume_worst" cuando un atributo (p. ej. \
pasteurizado) cambia el veredicto.
3. Tono del microcopy (es la marca): sereno, segunda persona, sin alarmismo, \
frases cortas. El "evitar" nunca grita: "Mejor déjalo para después — …". \
Incluye siempre alternativas constructivas cuando el veredicto sea avoid.
4. Campo "education": 2-3 frases didácticas explicando el MECANISMO del riesgo \
en lenguaje llano (qué es, por qué, qué lo neutraliza).
5. Todo bilingüe es/en. IDs a partir de {next_id}. verdict ∈ safe|caution|avoid|caffeine.

ESQUEMA EXACTO (copia la estructura de estos ejemplos reales):
{examples}

CATEGORÍAS A CUBRIR:
{targets}

Responde SOLO con JSON válido: {{"rules": [...], "sin_evidencia": [{{"category": "...", "motivo": "..."}}]}}"""


def llm(prompt: str) -> str:
    if key := os.environ.get("ANTHROPIC_API_KEY"):
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            data=json.dumps({
                "model": "claude-sonnet-5",
                "max_tokens": 8000,
                "messages": [{"role": "user", "content": prompt}],
            }).encode())
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.load(resp)["content"][0]["text"]
    # Fallback: CLI local autenticada.
    out = subprocess.run(["claude", "-p", prompt], capture_output=True,
                         text=True, timeout=600)
    if out.returncode != 0:
        sys.exit(f"claude CLI falló: {out.stderr[:400]}")
    return out.stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", help="tema libre en vez de categorías sin regla")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rules = json.loads(RULES_PATH.read_text())
    covered = {r["target_id"] for r in rules if r["target_type"] == "category"}
    taxonomy = {v for k, v in json.loads(TAXONOMY_PATH.read_text()).items()
                if not k.startswith("_")}
    gaps = sorted(taxonomy - covered)

    targets = args.topic or "\n".join(f"- {g}" for g in gaps)
    if not args.topic and not gaps:
        sys.exit("No hay categorías sin regla. Usa --topic para un tema libre.")

    examples = json.dumps([r for r in rules if r["id"] in (1001, 1021, 1068)],
                          ensure_ascii=False, indent=1)
    next_id = max(r["id"] for r in rules) + 1
    prompt = PROMPT.format(next_id=next_id, examples=examples, targets=targets)

    if args.dry_run:
        print(prompt)
        return

    raw = llm(prompt)
    # El modelo puede envolver el JSON en ```; lo extraemos.
    raw = raw[raw.find("{"):raw.rfind("}") + 1]
    data = json.loads(raw)

    # Validación: esquema mínimo + el motor las evalúa sin explotar.
    valid, errors = [], []
    for r in data.get("rules", []):
        try:
            assert r["verdict"] in ("safe", "caution", "avoid", "caffeine")
            assert r["explanation"]["es"] and r["explanation"]["en"]
            assert r["source_url"].startswith("https://")
            engine.evaluate([{**r, "active": True}], r["target_id"], {})
            valid.append({**r, "active": False, "_status": "pending_review"})
        except Exception as e:  # noqa: BLE001
            errors.append({"rule": r.get("id"), "error": str(e)})

    outdir = HERE / "proposals"
    outdir.mkdir(exist_ok=True)
    out = outdir / f"rules_{datetime.date.today()}.json"
    out.write_text(json.dumps({
        "proposals": valid,
        "sin_evidencia": data.get("sin_evidencia", []),
        "validation_errors": errors,
    }, ensure_ascii=False, indent=2))
    print(f"{len(valid)} propuestas válidas → {out}")
    print(f"{len(data.get('sin_evidencia', []))} sin evidencia · {len(errors)} con errores")
    print("\nSiguiente paso: REVISIÓN HUMANA. Las aprobadas se copian a "
          "yema/assets/mock/risk_rules.json con active=true y reviewed_by, "
          "y se publica con seed.py.")


if __name__ == "__main__":
    main()
