"""Export CSV (UTF-8 avec BOM, séparateur ';' : s'ouvre directement dans Excel FR)."""
from __future__ import annotations

import csv


def write_csv(path, articles, actor_ids, lang="fr") -> str:
    cols = ["date", "heure", "source", "langue", "titre_original", f"titre_{lang}",
            "paragraphe_original", f"paragraphe_{lang}", "lien", "acteurs_détectés", "nb_acteurs",
            *actor_ids, "mots_clés_trouvés", "tonalité", "statut", "commentaire", "reprises_par"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cols)
        for a in articles:
            same = a.langue == lang
            w.writerow([a.date.strftime("%Y-%m-%d"), a.date.strftime("%H:%M"), a.source_nom, a.langue,
                        a.titre, a.titre if same else a.titre_trad, a.paragraphe,
                        a.paragraphe if same else a.paragraphe_trad, a.url, ", ".join(a.acteurs),
                        len(a.acteurs), *[1 if x in a.acteurs else 0 for x in actor_ids],
                        ", ".join(a.mots_cles), a.tonalite, "à traiter", "", ", ".join(a.reprises)])
    return str(path)
