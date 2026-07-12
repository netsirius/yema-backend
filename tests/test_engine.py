"""Equivalencia con el motor del cliente (test/verdict_engine_test.dart)."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from app import engine

# En CI se usa la fixture local; en desarrollo, la fuente viva de la app.
_fixture = pathlib.Path(__file__).parent / "fixtures" / "risk_rules.json"
_app_mocks = (pathlib.Path(__file__).parent.parent.parent / "yema" / "assets" /
              "mock" / "risk_rules.json")
RULES = json.loads((_app_mocks if _app_mocks.exists() else _fixture).read_text())


class EngineTests(unittest.TestCase):
    def test_pasteurized_dairy_safe(self):
        r = engine.evaluate(RULES, "lacteos", {"pasteurizado": True})
        self.assertEqual(r["verdict"], "safe")
        self.assertEqual(r["source_org"], "AESAN")

    def test_fail_safe_unknown_pasteurization(self):
        r = engine.evaluate(RULES, "quesos_pasta_blanda", {})
        self.assertEqual(r["verdict"], "avoid")
        self.assertIsNotNone(r["caution_note"])
        self.assertIsNotNone(r["safe_alternatives"])
        self.assertIn("rule_id", r)  # trazabilidad: qué regla decidió

    def test_worst_risk_aggregation(self):
        r = engine.evaluate(RULES, "lacteos",
                            {"pasteurizado": True, "contiene_alcohol": True})
        self.assertEqual(r["verdict"], "avoid")

    def test_caffeine_interpolation(self):
        r = engine.evaluate(RULES, "bebidas_cafeina",
                            {"contiene_cafeina": True, "cafeina_mg": 80})
        self.assertEqual(r["verdict"], "caffeine")
        self.assertEqual(r["caffeine_mg"], 80)
        self.assertIn("80 mg", r["explanation"]["es"])

    def test_cosmetics(self):
        self.assertEqual(
            engine.evaluate(RULES, "cosmetica", {"contiene_retinol": True})["verdict"],
            "avoid")
        self.assertEqual(
            engine.evaluate(RULES, "cosmetica", {"filtro_mineral": True})["verdict"],
            "safe")

    def test_default_safe(self):
        self.assertEqual(engine.evaluate(RULES, None, {})["verdict"], "safe")


if __name__ == "__main__":
    unittest.main()
