"""Chaîne complète contre les faux sites locaux (tests/mock_sites.py)."""
from pathlib import Path

import pytest
from openpyxl import load_workbook

import veille
from tests import mock_sites

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    work = tmp_path_factory.mktemp("veille")
    urls = mock_sites.start_servers(port0=18180)
    cfg = mock_sites.write_config(urls, ROOT / "sites.yaml", work / "sites.yaml", work / "v.db", work)
    import yaml
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    data["defaults"]["delai"] = [0.05, 0.1]          # tests rapides
    cfg.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    import os
    os.environ.pop("ANTHROPIC_API_KEY", None)
    rc = veille.main(["--config", str(cfg), "--no-traduire"])
    files = sorted(work.glob("veille_*.xlsx"))
    return rc, work, files, cfg


def test_code_retour_et_fichier(run):
    rc, work, files, _ = run
    assert rc == 0 and len(files) == 1


def test_sources_et_methodes(run):
    wb = load_workbook(run[2][0])
    rows = {r[0]: r for r in wb["Sources"].iter_rows(min_row=2, max_row=9, values_only=True)}
    assert rows["hespress_ar"][7] == "rest"
    assert rows["hespress_fr"][7] == "rss"          # REST 404 -> RSS
    assert rows["al3omk"][7] == "html"              # anti-robot + pas de RSS -> HTML
    assert rows["madar21"][7] == "rss"              # méthode préférée
    assert rows["thevoice"][4] == "BLOQUÉ"          # 403
    assert rows["alaoual"][4] == "BLOQUÉ"           # robots.txt
    assert rows["hibapress"][4] == "ÉCHEC"          # 500


def test_articles_filtres_et_dedoublonnes(run):
    wb = load_workbook(run[2][0])
    ws = wb["Articles"]
    head = [c.value for c in ws[1]]
    data = [dict(zip(head, r)) for r in ws.iter_rows(min_row=2, values_only=True) if r[0]]
    titres = [d["titre_original"] for d in data]
    assert len(data) == 8
    assert not any("Pampers" in t or "الطقس" in t or "عيد الاستقلال" in t or "بركة الله" in t for t in titres)
    mans = [d for d in data if d["Mansouri"] == 1]
    assert len(mans) == 1 and mans[0]["reprises_par"] == "Lakome2"     # doublon fusionné
    assert all(d["nb_acteurs"] == sum(d[a] for a in ("Mansouri", "PAM", "RNI", "PI", "Benkirane",
                                                      "PJD", "Benabdellah", "PPS")) for d in data)


def test_mise_en_forme_excel(run):
    wb = load_workbook(run[2][0])
    ws = wb["Articles"]
    assert "tblArticles" in ws.tables and ws.freeze_panes == "E2"
    head = [c.value for c in ws[1]]
    lien = head.index("lien") + 1
    ar_row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head.index("langue") + 1).value == "ar")
    assert ws.cell(ar_row, head.index("titre_original") + 1).alignment.horizontal == "right"
    assert ws.cell(ar_row, head.index("titre_original") + 1).alignment.readingOrder == 2
    assert ws.cell(2, lien).hyperlink.target.startswith("http")
    assert len(ws.data_validations.dataValidation) >= 2
    assert wb["Tableau de bord"]["B10"].value.startswith("=COUNTIFS(")
    assert len(wb["Tableau de bord"]._charts) == 4


def test_execution_incrementale(run):
    rc, work, _, cfg = run
    import sqlite3
    n1 = sqlite3.connect(work / "v.db").execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    assert veille.main(["--config", str(cfg), "--no-traduire", "--sortie", "csv"]) == 0
    n2 = sqlite3.connect(work / "v.db").execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    assert n1 == n2 == 15
    csv_file = sorted(work.glob("veille_*.csv"))[0]
    assert csv_file.read_text(encoding="utf-8-sig").count("\n") == 9   # en-tête + 8
