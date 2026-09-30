"""Base SQLite : articles vus (historique, exécutions incrémentales),
caches de traduction et de tonalité, journal des exécutions."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .dates import TZ, now
from .dedup import canonical_url
from .models import Article

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    url_canon   TEXT PRIMARY KEY,
    url         TEXT NOT NULL,
    source      TEXT NOT NULL,
    source_nom  TEXT,
    langue      TEXT,
    titre       TEXT,
    paragraphe  TEXT,
    date_pub    TEXT NOT NULL,      -- ISO 8601 en UTC
    methode     TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date_pub);
CREATE TABLE IF NOT EXISTS traductions (
    cle         TEXT PRIMARY KEY,
    langue      TEXT,
    source      TEXT,
    traduction  TEXT,
    moteur      TEXT,
    cree_le     TEXT
);
CREATE TABLE IF NOT EXISTS tonalites (
    cle         TEXT PRIMARY KEY,
    tonalite    TEXT,
    moteur      TEXT,
    cree_le     TEXT
);
CREATE TABLE IF NOT EXISTS executions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    debut       TEXT,
    fin         TEXT,
    parametres  TEXT,
    resume      TEXT
);
"""


class Storage:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    # -- articles ------------------------------------------------------------
    def get_article(self, url: str) -> Article | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM articles WHERE url_canon=?",
                                    (canonical_url(url),)).fetchone()
        return self._row_to_article(row) if row else None

    def upsert_articles(self, articles: list[Article]) -> int:
        """Insère / met à jour ; retourne le nombre d'articles nouveaux."""
        ts = now().isoformat()
        new = 0
        with self.lock, self.conn:
            for a in articles:
                cu = canonical_url(a.url)
                exists = self.conn.execute("SELECT 1 FROM articles WHERE url_canon=?", (cu,)).fetchone()
                if exists:
                    a.nouveau = False
                    self.conn.execute(
                        "UPDATE articles SET titre=?, paragraphe=?, last_seen=? WHERE url_canon=?",
                        (a.titre, a.paragraphe, ts, cu))
                else:
                    new += 1
                    a.nouveau = True
                    self.conn.execute(
                        "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (cu, a.url, a.source, a.source_nom, a.langue, a.titre, a.paragraphe,
                         a.date.astimezone(timezone.utc).isoformat(), a.methode, ts, ts))
        return new

    def articles_between(self, start: datetime, end: datetime, sources: list[str]) -> list[Article]:
        q = ("SELECT * FROM articles WHERE date_pub >= ? AND date_pub <= ? AND source IN (%s)"
             % ",".join("?" * len(sources)))
        # date_pub est stockée en ISO UTC : la comparaison lexicale est exacte
        utc = lambda d: d.astimezone(timezone.utc).isoformat()
        with self.lock:
            rows = self.conn.execute(q, (utc(start), utc(end), *sources)).fetchall()
        return [self._row_to_article(r) for r in rows]

    def _row_to_article(self, row) -> Article:
        return Article(url=row["url"], source=row["source"], source_nom=row["source_nom"],
                       langue=row["langue"], titre=row["titre"], paragraphe=row["paragraphe"],
                       date=datetime.fromisoformat(row["date_pub"]).astimezone(TZ),
                       methode=row["methode"], nouveau=False)

    # -- caches --------------------------------------------------------------
    def get_translation(self, cle: str) -> str | None:
        with self.lock:
            row = self.conn.execute("SELECT traduction FROM traductions WHERE cle=?", (cle,)).fetchone()
        return row[0] if row else None

    def put_translation(self, cle: str, langue: str, source: str, traduction: str, moteur: str):
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO traductions VALUES (?,?,?,?,?,?)",
                              (cle, langue, source, traduction, moteur, now().isoformat()))

    def get_tonality(self, cle: str) -> str | None:
        with self.lock:
            row = self.conn.execute("SELECT tonalite FROM tonalites WHERE cle=?", (cle,)).fetchone()
        return row[0] if row else None

    def put_tonality(self, cle: str, tonalite: str, moteur: str):
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO tonalites VALUES (?,?,?,?)",
                              (cle, tonalite, moteur, now().isoformat()))

    # -- journal -------------------------------------------------------------
    def log_run(self, debut: datetime, params: dict, resume: dict):
        with self.lock, self.conn:
            self.conn.execute("INSERT INTO executions (debut, fin, parametres, resume) VALUES (?,?,?,?)",
                              (debut.isoformat(), now().isoformat(),
                               json.dumps(params, ensure_ascii=False, default=str),
                               json.dumps(resume, ensure_ascii=False, default=str)))

    def close(self):
        self.conn.close()
