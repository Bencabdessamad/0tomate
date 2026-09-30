#!/usr/bin/env python3
"""Veille de communication politique au Maroc.

Collecte les articles récents des sites configurés (sites.yaml) par API REST
WordPress, flux RSS ou, en dernier recours, scraping HTML léger ; filtre par
acteurs/partis (keywords.yaml) ; traduit l'arabe en français ; exporte un
Excel prêt à filtrer (ou un CSV).

Exemple :
    python veille.py --heures 24 --sites hespress_ar,al3omk --acteurs PAM,RNI \
                     --langue fr --traduire --sortie excel
"""
from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

from collectors import SiteConfig, collect_site
from core import dates, tonality
from core.dedup import deduplicate
from core.keywords import KeywordMatcher
from core.storage import Storage
from core.translate import Translator

HERE = Path(__file__).resolve().parent
log = logging.getLogger("veille")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Veille presse politique Maroc -> Excel",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--heures", type=float, default=24, help="fenêtre en heures (défaut 24)")
    p.add_argument("--depuis", help="date de début YYYY-MM-DD (prioritaire sur --heures)")
    p.add_argument("--sites", help="clés de sites séparées par des virgules (défaut : tous les actifs)")
    p.add_argument("--acteurs", help="acteurs à retenir, ex. PAM,RNI (défaut : tous les actifs)")
    p.add_argument("--langue", default="fr", help="langue de traduction / des colonnes *_fr (défaut fr)")
    p.add_argument("--langues-source", default="ar,fr",
                   help="langues d'articles à garder (défaut ar,fr)")
    p.add_argument("--traduire", dest="traduire", action="store_true", default=True,
                   help="traduire les articles non français (défaut)")
    p.add_argument("--no-traduire", dest="traduire", action="store_false")
    p.add_argument("--tonalite", dest="tonalite", action="store_true", default=True,
                   help="classer la tonalité via Claude si une clé est disponible (défaut)")
    p.add_argument("--no-tonalite", dest="tonalite", action="store_false")
    p.add_argument("--sortie", choices=["excel", "csv"], default="excel")
    p.add_argument("--dossier-sortie", help="dossier des fichiers produits (défaut : sites.yaml)")
    p.add_argument("--config", default=str(HERE / "sites.yaml"), help="fichier sites.yaml")
    p.add_argument("--keywords", default=str(HERE / "keywords.yaml"), help="fichier keywords.yaml")
    p.add_argument("--base", help="fichier SQLite (défaut : sites.yaml)")
    p.add_argument("--tous", action="store_true",
                   help="exporter aussi les articles sans mot-clé (diagnostic)")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args(argv)


def load_sites(path: str) -> tuple[dict, list[SiteConfig]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    defaults = data.get("defaults", {}) or {}
    sites = []
    for key, raw in (data.get("sites") or {}).items():
        raw = dict(raw or {})
        fields = SiteConfig.__dataclass_fields__
        kw = {k: v for k, v in raw.items() if k in fields}
        for k in ("rss", "rubriques"):
            if isinstance(kw.get(k), str):
                kw[k] = [kw[k]]
        kw.setdefault("nom", key)
        sites.append(SiteConfig(cle=key, **kw))
    return defaults, sites


def setup_logging(verbose: bool, logfile: Path):
    logfile.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s : %(message)s", "%H:%M:%S")
    fmt.converter = lambda ts: dates.datetime.fromtimestamp(ts, dates.TZ).timetuple()   # heure marocaine
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.DEBUG if verbose else logging.INFO)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.handlers = [sh, fh]
    for noisy in ("urllib3", "httpx", "httpx2", "anthropic", "charset_normalizer"):
        logging.getLogger(noisy).setLevel(logging.ERROR)


def resolve(path_value: str, base: Path) -> Path:
    p = Path(path_value)
    return p if p.is_absolute() else base / p


def free_path(path: Path) -> Path:
    """Évite d'écraser un fichier existant (ou ouvert dans Excel) : ajoute _2, _3…"""
    n, candidate = 2, path
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_{n}{path.suffix}")
        n += 1
    return candidate


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg_path = Path(args.config).resolve()
    defaults, all_sites = load_sites(str(cfg_path))
    out_dir = resolve(args.dossier_sortie or defaults.get("dossier_sortie", "sorties"), cfg_path.parent)
    started = dates.now()
    stamp = started.strftime("%Y%m%d_%H%M")
    setup_logging(args.verbose, out_dir / "logs" / f"veille_{stamp}.log")

    # -- sélection des sites ------------------------------------------------
    sites = [s for s in all_sites if s.actif]
    if args.sites:
        wanted = [x.strip() for x in args.sites.split(",") if x.strip()]
        sites, unknown = [], []
        for w in wanted:
            # clé exacte, sinon préfixe : "hespress" = hespress_ar + hespress_fr
            match = [s for s in all_sites if s.cle == w] or \
                    [s for s in all_sites if s.cle.startswith(w + "_")]
            if not match:
                unknown.append(w)
            sites += [s for s in match if s not in sites]
        if unknown:
            log.error("Site(s) inconnu(s) : %s. Disponibles : %s", ", ".join(unknown),
                      ", ".join(s.cle for s in all_sites))
            return 2
    if not sites:
        log.error("Aucun site sélectionné")
        return 2

    try:
        matcher = KeywordMatcher.from_yaml(args.keywords, only=args.acteurs.split(",") if args.acteurs else None)
    except ValueError as e:
        log.error("%s", e)
        return 2
    start, end = dates.window(args.heures, args.depuis)
    langs = {x.strip() for x in args.langues_source.split(",") if x.strip()}
    log.info("Fenêtre : %s -> %s (Africa/Casablanca) · %d site(s) · acteurs : %s",
             start.strftime("%d/%m/%Y %H:%M"), end.strftime("%d/%m/%Y %H:%M"), len(sites),
             ", ".join(matcher.actor_ids))

    storage = Storage(resolve(args.base or defaults.get("base", "veille.db"), cfg_path.parent))

    # -- collecte (un fil par site, un site en panne n'arrête pas les autres)
    reports = {}
    collected = []
    with ThreadPoolExecutor(max_workers=int(defaults.get("sites_en_parallele", 4))) as pool:
        futures = {pool.submit(collect_site, s, start, end, defaults, storage): s for s in sites}
        for fut in as_completed(futures):
            s = futures[fut]
            try:
                arts, rep = fut.result()
            except Exception as e:           # ne devrait pas arriver (collect_site est protégé)
                log.exception("[%s] plantage : %s", s.cle, e)
                continue
            rep.nouveaux = storage.upsert_articles(arts)
            reports[s.cle] = rep
            collected += arts
            log.info("[%s] %s · méthode=%s · trouvés=%d · nouveaux=%d · erreurs=%d · %.1fs",
                     s.cle, rep.etat, rep.methode_utilisee or "-", rep.trouves, rep.nouveaux,
                     len(rep.erreurs), rep.duree)
    reports = [reports[s.cle] for s in sites if s.cle in reports]

    # -- articles de la fenêtre (collecte du jour + historique SQLite) -------
    pool_articles = storage.articles_between(start, end, [s.cle for s in sites])
    pool_articles = [a for a in pool_articles if a.langue in langs]
    retained = []
    for a in pool_articles:
        m = matcher.find(f"{a.titre}\n{a.paragraphe}")
        a.acteurs, a.mots_cles = m.actor_ids, m.terms
        if m.actor_ids or args.tous:
            retained.append(a)
    new_urls = {a.url for a in collected if a.nouveau}
    for a in retained:
        a.nouveau = a.url in new_urls
    retained, dups = deduplicate(retained)
    retained.sort(key=lambda a: a.date, reverse=True)
    for rep in reports:
        rep.retenus = sum(1 for a in retained if a.source == rep.cle)
    log.info("Filtrage : %d article(s) dans la fenêtre, %d retenu(s) après mots-clés, %d doublon(s) fusionné(s)",
             len(pool_articles), len(retained), dups)

    # -- traduction / tonalité (uniquement les articles retenus) -------------
    if args.traduire and retained:
        Translator(storage, target=args.langue).translate_articles(retained)
    if args.tonalite and retained:
        tonality.classify(retained, storage)

    # -- export --------------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)
    params = {"fenêtre": f"{start:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M}",
              "sites": ",".join(s.cle for s in sites), "acteurs": ",".join(matcher.actor_ids),
              "langue": args.langue, "traduire": args.traduire, "tonalité": args.tonalite,
              "langues_source": ",".join(sorted(langs))}
    if args.sortie == "excel":
        from core.export_excel import write_excel
        path = write_excel(free_path(out_dir / f"veille_{stamp}.xlsx"), retained, matcher.actors, reports, start, end,
                           started, lang=args.langue, params=params, all_actors=matcher.all_actors)
    else:
        from core.export_csv import write_csv
        path = write_csv(free_path(out_dir / f"veille_{stamp}.csv"), retained, matcher.actor_ids, lang=args.langue)
    storage.log_run(started, params, {r.cle: {"etat": r.etat, "methode": r.methode_utilisee,
                                               "trouves": r.trouves, "retenus": r.retenus,
                                               "erreurs": r.erreurs} for r in reports})
    storage.close()

    # -- résumé --------------------------------------------------------------
    log.info("%-14s %-8s %-6s %8s %8s %8s", "site", "état", "méth.", "trouvés", "nouveaux", "retenus")
    for r in reports:
        log.info("%-14s %-8s %-6s %8d %8d %8d", r.cle, r.etat, r.methode_utilisee or "-",
                 r.trouves, r.nouveaux, r.retenus)
    log.info("Fichier produit : %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
