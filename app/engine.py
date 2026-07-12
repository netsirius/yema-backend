"""Motor de veredictos — port 1:1 del mock de la app (MockDb.evaluate).

Agregación fail-safe: gana el peor riesgo activo, y un atributo desconocido
bajo `if_unknown: assume_worst` cuenta como el caso de riesgo.
La suite de tests fija la equivalencia con el motor del cliente.
"""
from __future__ import annotations

SEVERITY = {"avoid": 3, "caution": 2, "caffeine": 2, "safe": 1}

DEFAULT_SAFE = {
    "verdict": "safe",
    "explanation": {
        "es": "Sin riesgos conocidos en el embarazo.",
        "en": "No known risks during pregnancy.",
    },
    "source_org": "AESAN",
    "source_url": "https://www.aesan.gob.es/AECOSAN/web/para_el_consumidor/ampliacion/embarazadas.htm",
}


def evaluate(rules: list[dict], category: str | None, attributes: dict) -> dict:
    """Devuelve el payload de la regla ganadora + mg de cafeína interpolados."""
    worst: dict | None = None

    for rule in rules:
        if not rule.get("active", True):
            continue
        targets_category = rule["target_type"] == "category" and rule["target_id"] == category
        targets_attribute = rule["target_type"] == "attribute"
        if not (targets_category or targets_attribute):
            continue

        cond = rule.get("condition")
        if cond is None:
            matches = targets_category
        else:
            value = attributes.get(cond["attribute"])
            if value is None:
                # Núcleo fail-safe: atributo desconocido = caso de riesgo.
                matches = targets_category and cond.get("if_unknown") == "assume_worst"
            else:
                matches = value == cond["value"]
        if not matches:
            continue

        if worst is None or SEVERITY[rule["verdict"]] > SEVERITY[worst["verdict"]]:
            worst = rule

    if worst is None:
        return dict(DEFAULT_SAFE)

    result = {
        "verdict": worst["verdict"],
        "explanation": worst["explanation"],
        "caution_note": worst.get("caution_note"),
        "factor_label": worst.get("factor_label"),
        "safe_alternatives": worst.get("safe_alternatives"),
        "education": worst.get("education"),
        "source_org": worst["source_org"],
        "source_url": worst["source_url"],
        "rule_id": worst["id"],
        "rule_version": worst.get("version", 1),  # trazabilidad clínica
    }
    if worst["verdict"] == "caffeine":
        mg = int(attributes.get("cafeina_mg") or 0)
        result["caffeine_mg"] = mg
        result["explanation"] = {
            lang: text.replace("{mg}", str(mg))
            for lang, text in worst["explanation"].items()
        }
    return result
