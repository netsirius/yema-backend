"""Guardián de fuente única de verdad.

Las reglas viven en `yema/assets/mock/risk_rules.json` (la app las usa como
motor offline). El backend las sirve tras `seed.py` y las testea contra una
copia en `tests/fixtures/`. Este test falla si ambas divergen — evita que el
motor del servidor y el del cliente se desincronicen sin que nadie lo note.

Si falla: copia el fichero de la app al fixture y re-siembra.
    cp ../yema/assets/mock/risk_rules.json tests/fixtures/risk_rules.json
    python3 seed.py
"""
import json
import pathlib
import unittest

HERE = pathlib.Path(__file__).parent
APP = HERE.parent.parent / "yema" / "assets" / "mock" / "risk_rules.json"
FIXTURE = HERE / "fixtures" / "risk_rules.json"


class RulesSyncTests(unittest.TestCase):
    def test_fixture_matches_app_source_of_truth(self):
        if not APP.exists():
            self.skipTest("app source not present (CI checks out backend only)")
        self.assertEqual(
            json.loads(APP.read_text()),
            json.loads(FIXTURE.read_text()),
            "Las reglas de la app y el fixture del backend han divergido. "
            "Copia el fichero de la app al fixture y re-siembra (ver docstring).",
        )

    def test_rule_ids_unique(self):
        rules = json.loads(FIXTURE.read_text())
        ids = [r["id"] for r in rules]
        self.assertEqual(len(ids), len(set(ids)), "IDs de regla duplicados")

    def test_every_rule_has_source(self):
        # Trazabilidad clínica: ninguna regla sin fuente citada.
        for r in json.loads(FIXTURE.read_text()):
            self.assertTrue(r.get("source_org"), f"regla {r['id']} sin source_org")
            self.assertTrue(
                str(r.get("source_url", "")).startswith("https://"),
                f"regla {r['id']} sin source_url válida")


if __name__ == "__main__":
    unittest.main()
