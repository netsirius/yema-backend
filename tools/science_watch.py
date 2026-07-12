"""Vigilancia científica: novedades de PubMed y EFSA relevantes para las
reglas de Yema. Corre semanalmente (GitHub Actions) y abre un Issue con el
digest para revisión humana — nunca cambia reglas por sí solo.

    python3 tools/science_watch.py --days 7            # digest a stdout
    python3 tools/science_watch.py --days 7 --summarize # + análisis LLM
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).parent.parent
RULES_PATH = HERE.parent / "yema" / "assets" / "mock" / "risk_rules.json"
FIXTURE = HERE / "tests" / "fixtures" / "risk_rules.json"

PUBMED_QUERY = (
    '(pregnancy[Title/Abstract]) AND '
    '(listeria OR toxoplasmosis OR "food safety" OR methylmercury OR '
    'caffeine OR retinoid OR "vitamin A" OR salmonella OR anisakis)'
)
EFSA_RSS = "https://www.efsa.europa.eu/en/all/rss"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "yema-science-watch/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def pubmed(days: int) -> list[dict]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    q = urllib.parse.urlencode({
        "db": "pubmed", "term": PUBMED_QUERY, "reldate": days,
        "datetype": "pdat", "retmax": 25, "retmode": "json", "sort": "date",
    })
    ids = json.loads(_get(f"{base}/esearch.fcgi?{q}"))["esearchresult"]["idlist"]
    if not ids:
        return []
    q = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
    summaries = json.loads(_get(f"{base}/esummary.fcgi?{q}"))["result"]
    return [{
        "title": summaries[i]["title"],
        "journal": summaries[i].get("fulljournalname", ""),
        "date": summaries[i].get("pubdate", ""),
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{i}/",
    } for i in ids]


def efsa(days: int) -> list[dict]:
    try:
        root = ET.fromstring(_get(EFSA_RSS))
    except Exception:  # noqa: BLE001 — el RSS a veces se cae; el digest sigue
        return []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    items = []
    for item in root.iter("item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        pub = item.findtext("pubDate") or ""
        try:
            when = datetime.datetime.strptime(pub[:25].strip(), "%a, %d %b %Y %H:%M:%S")
            if when.replace(tzinfo=datetime.timezone.utc) < cutoff:
                continue
        except ValueError:
            pass
        items.append({"title": title, "url": link, "date": pub})
    return items[:15]


def digest(days: int) -> str:
    pm, ef = pubmed(days), efsa(days)
    lines = [f"# Vigilancia científica Yema · últimos {days} días",
             f"_Generado {datetime.date.today()}_", ""]
    lines += [f"## PubMed ({len(pm)})", ""]
    lines += [f"- [{a['title']}]({a['url']}) — {a['journal']}, {a['date']}" for a in pm] or ["(sin resultados)"]
    lines += ["", f"## EFSA ({len(ef)})", ""]
    lines += [f"- [{a['title']}]({a['url']}) — {a['date']}" for a in ef] or ["(sin resultados)"]
    return "\n".join(lines)


def summarize(text: str) -> str:
    import os
    import subprocess
    rules_path = RULES_PATH if RULES_PATH.exists() else FIXTURE
    rules = json.loads(rules_path.read_text())
    themes = sorted({r["target_id"] for r in rules})
    prompt = (
        "Eres el asistente del panel clínico de Yema (seguridad alimentaria en "
        "el embarazo). Del siguiente digest de publicaciones, señala SOLO lo "
        "que podría afectar a nuestras reglas (temas actuales: "
        f"{', '.join(themes)}). Para cada hallazgo relevante: qué regla podría "
        "cambiar y por qué, en 1-2 frases. Si nada es relevante, dilo sin "
        "rodeos. NUNCA propongas relajar una regla sin señalar que requiere "
        "revisión del panel.\n\n" + text)
    if key := os.environ.get("ANTHROPIC_API_KEY"):
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            data=json.dumps({"model": "claude-sonnet-5", "max_tokens": 2000,
                             "messages": [{"role": "user", "content": prompt}]}).encode())
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.load(resp)["content"][0]["text"]
    out = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=600)
    return out.stdout if out.returncode == 0 else "(análisis LLM no disponible)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--summarize", action="store_true")
    args = ap.parse_args()

    text = digest(args.days)
    if args.summarize:
        text += "\n\n## Análisis de relevancia (IA — requiere revisión del panel)\n\n"
        text += summarize(text)
    print(text)


if __name__ == "__main__":
    main()
