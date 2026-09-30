"""Export Excel "prêt à l'emploi" (openpyxl).

Feuilles : Articles (Table filtrable), Tableau de bord (COUNTIFS + graphiques
+ menus déroulants), Mots-clés, Sources, Listes (masquée, pour les menus)."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.series import DataPoint
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(name=FONT, bold=True, color="FFFFFF")
BASE_FONT = Font(name=FONT, size=10)
LINK_FONT = Font(name=FONT, size=10, color="0563C1", underline="single")
TITLE_FONT = Font(name=FONT, size=14, bold=True, color="1F3864")
BOLD = Font(name=FONT, size=10, bold=True)
THIN = Side(style="thin", color="BFBFBF")
RTL = Alignment(horizontal="right", vertical="top", wrap_text=True, readingOrder=2)
LTR = Alignment(horizontal="left", vertical="top", wrap_text=True, readingOrder=1)
CENTER = Alignment(horizontal="center", vertical="top")

PERIODES = ["Tout", "Aujourd'hui", "24 dernières heures", "7 derniers jours",
            "30 derniers jours", "Fenêtre de collecte"]
TONALITES = ["positive", "neutre", "négative"]
STATUTS = ["à traiter", "traité"]
MULTI_FILL = "FCE4D6"


def _cols(actor_ids, lang):
    """Colonnes de la feuille Articles : (nom, largeur)."""
    base = [("date", 11), ("heure", 7), ("source", 16), ("langue", 7),
            ("titre_original", 45), (f"titre_{lang}", 45),
            ("paragraphe_original", 70), (f"paragraphe_{lang}", 70),
            ("lien", 38), ("acteurs_détectés", 22), ("nb_acteurs", 11)]
    base += [(a, max(7, len(a) + 3)) for a in actor_ids]
    base += [("mots_clés_trouvés", 30), ("tonalité", 11), ("statut", 11),
             ("commentaire", 30), ("reprises_par", 20), ("horodatage", 17)]
    return base


def _row_height(texts_widths) -> float:
    lines = 1
    for text, width in texts_widths:
        if text:
            lines = max(lines, math.ceil(len(text) / max(width * 1.05, 1)))
    return min(lines, 6) * 13.5 + 3


def build_workbook(articles, actors, reports, start, end, generated_at, lang="fr", params=None,
                   all_actors=None):
    wb = Workbook()
    actor_ids = [a.id for a in actors]
    cols = _cols(actor_ids, lang)
    idx = {name: i + 1 for i, (name, _) in enumerate(cols)}
    C = {name: L(i) for name, i in idx.items()}          # lettres de colonnes
    n = max(len(articles), 1)
    last_row = n + 1

    # ======================= Feuille Articles ==============================
    ws = wb.active
    ws.title = "Articles"
    for name, width in cols:
        c = ws.cell(row=1, column=idx[name], value=name)
        c.font, c.fill = HEAD_FONT, HEAD_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[L(idx[name])].width = width
    ws.row_dimensions[1].height = 30

    for r, a in enumerate(articles, start=2):
        loc = a.date.replace(tzinfo=None)
        is_ar = a.langue == "ar"
        values = {
            "date": loc.date(), "heure": loc.time().replace(second=0, microsecond=0),
            "source": a.source_nom, "langue": a.langue,
            "titre_original": a.titre, f"titre_{lang}": a.titre_trad if a.langue != lang else a.titre,
            "paragraphe_original": a.paragraphe,
            f"paragraphe_{lang}": a.paragraphe_trad if a.langue != lang else a.paragraphe,
            "lien": a.url, "acteurs_détectés": ", ".join(a.acteurs), "nb_acteurs": len(a.acteurs),
            "mots_clés_trouvés": ", ".join(a.mots_cles), "tonalité": a.tonalite or None,
            "statut": "à traiter", "commentaire": None,
            "reprises_par": ", ".join(a.reprises) or None, "horodatage": loc,
        }
        for aid in actor_ids:
            values[aid] = 1 if aid in a.acteurs else 0
        for name, v in values.items():
            c = ws.cell(row=r, column=idx[name], value=v)
            c.font = BASE_FONT
            c.alignment = LTR
        for name in ("titre_original", "paragraphe_original"):
            ws.cell(row=r, column=idx[name]).alignment = RTL if is_ar else LTR
        for name in ["date", "heure", "langue", "nb_acteurs", "tonalité", "statut", *actor_ids]:
            ws.cell(row=r, column=idx[name]).alignment = CENTER
        ws.cell(row=r, column=idx["date"]).number_format = "DD/MM/YYYY"
        ws.cell(row=r, column=idx["heure"]).number_format = "HH:MM"
        ws.cell(row=r, column=idx["horodatage"]).number_format = "DD/MM/YYYY HH:MM"
        link = ws.cell(row=r, column=idx["lien"])
        link.hyperlink = a.url
        link.font = LINK_FONT
        link.alignment = Alignment(vertical="top", wrap_text=False)
        for name in ("titre_original", f"titre_{lang}"):
            ws.cell(row=r, column=idx[name]).font = Font(name=FONT, size=10, bold=True)
        ws.row_dimensions[r].height = _row_height([
            (a.titre, 45), (a.paragraphe, 70), (a.paragraphe_trad, 70)])
    if not articles:
        ws.cell(row=2, column=idx["titre_original"], value="(aucun article retenu sur la période)")

    last_col = L(len(cols))
    table = Table(displayName="tblArticles", ref=f"A1:{last_col}{last_row}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
    ws.add_table(table)
    ws.freeze_panes = "E2"
    ws.column_dimensions[C["horodatage"]].hidden = True
    ws.cell(row=1, column=idx["horodatage"]).comment = Comment(
        "Colonne technique (date + heure) utilisée par le Tableau de bord.", "veille")
    ws.cell(row=1, column=idx["nb_acteurs"]).comment = Comment(
        "Nombre d'acteurs cités. Filtrer >= 2 pour les articles multi-acteurs.", "veille")

    # listes déroulantes (plages étendues pour les lignes ajoutées à la main)
    dv_rows = f"{last_row + 500}"
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUTS) + '"', allow_blank=True)
    dv.add(f"{C['statut']}2:{C['statut']}{dv_rows}")
    dv_t = DataValidation(type="list", formula1='"' + ",".join(TONALITES) + '"', allow_blank=True)
    dv_t.add(f"{C['tonalité']}2:{C['tonalité']}{dv_rows}")
    ws.add_data_validation(dv)
    ws.add_data_validation(dv_t)

    # mise en forme conditionnelle ------------------------------------------
    rng = lambda col: f"{C[col]}2:{C[col]}{last_row}"
    full = f"A2:{last_col}{last_row}"
    for act in actors:
        fill = PatternFill("solid", fgColor=act.couleur, bgColor=act.couleur)
        ws.conditional_formatting.add(rng(act.id), CellIsRule(operator="equal", formula=["1"], fill=fill,
                                                              font=Font(bold=True)))
        ws.conditional_formatting.add(rng(act.id), CellIsRule(operator="equal", formula=["0"],
                                                              font=Font(color="BFBFBF")))
    # couleur du parti du premier acteur détecté sur la colonne acteurs_détectés et source
    for act in actors:
        fill = PatternFill("solid", fgColor=act.couleur, bgColor=act.couleur)
        ws.conditional_formatting.add(
            f"{C['acteurs_détectés']}2:{C['acteurs_détectés']}{last_row}",
            FormulaRule(formula=[f"${C[act.id]}2=1"], fill=fill, stopIfTrue=True))
    # articles multi-acteurs : ligne surlignée
    ws.conditional_formatting.add(full, FormulaRule(
        formula=[f"${C['nb_acteurs']}2>=2"],
        fill=PatternFill("solid", fgColor=MULTI_FILL, bgColor=MULTI_FILL),
        border=Border(top=Side(style="thin", color="C65911"), bottom=Side(style="thin", color="C65911"))))
    ws.conditional_formatting.add(rng("tonalité"), CellIsRule(operator="equal", formula=['"positive"'],
                                                              font=Font(color="006100", bold=True)))
    ws.conditional_formatting.add(rng("tonalité"), CellIsRule(operator="equal", formula=['"négative"'],
                                                              font=Font(color="9C0006", bold=True)))
    ws.conditional_formatting.add(rng("statut"), CellIsRule(
        operator="equal", formula=['"traité"'], font=Font(color="808080"),
        fill=PatternFill("solid", fgColor="EDEDED", bgColor="EDEDED")))

    # ======================= Feuille Listes (masquée) =======================
    wl = wb.create_sheet("Listes")
    wl["A1"] = "Tous"
    for i, aid in enumerate(actor_ids, start=2):
        wl.cell(row=i, column=1, value=aid)
    for i, p in enumerate(PERIODES, start=1):
        wl.cell(row=i, column=2, value=p)
    wl["C1"], wl["C2"] = "Début fenêtre", start.replace(tzinfo=None)
    wl["C2"].number_format = "DD/MM/YYYY HH:MM"
    wl.sheet_state = "hidden"
    wb.defined_names["ListeActeurs"] = DefinedName("ListeActeurs", attr_text=f"Listes!$A$1:$A${len(actor_ids) + 1}")
    wb.defined_names["ListePeriodes"] = DefinedName("ListePeriodes", attr_text=f"Listes!$B$1:$B${len(PERIODES)}")

    # ======================= Tableau de bord =================================
    wd = wb.create_sheet("Tableau de bord", 0)
    wd.sheet_view.showGridLines = False
    wd["A1"] = "Veille politique Maroc : tableau de bord"
    wd["A1"].font = TITLE_FONT
    wd["A2"] = (f"Collecte du {start:%d/%m/%Y %H:%M} au {end:%d/%m/%Y %H:%M} (Africa/Casablanca) · "
                f"{len(articles)} article(s) retenu(s)")
    wd["A2"].font = Font(name=FONT, size=10, italic=True, color="595959")

    label = lambda cell, text: (wd.__setitem__(cell, text), setattr(wd[cell], "font", BOLD))
    label("A4", "Période")
    label("A5", "Acteur")
    label("A6", "Date de référence")
    label("A7", "Début de période")
    wd["B4"], wd["B5"] = "Fenêtre de collecte", "Tous"
    wd["B6"] = generated_at.replace(tzinfo=None, microsecond=0)
    wd["B6"].number_format = "DD/MM/YYYY HH:MM"
    wd["B6"].comment = Comment("Heure de génération du fichier. Remplacer par =MAINTENANT() "
                               "(=NOW()) pour des périodes glissantes.", "veille")
    wd["B7"] = ('=IF(B4="Tout",0,IF(B4="Aujourd\'hui",INT(B6),IF(B4="24 dernières heures",B6-1,'
                'IF(B4="7 derniers jours",INT(B6)-6,IF(B4="30 derniers jours",INT(B6)-29,Listes!$C$2)))))')
    wd["B7"].number_format = "DD/MM/YYYY HH:MM"
    wd["B8"] = "=MATCH(B5,ListeActeurs,0)"       # colonne technique
    wd["A8"] = "(index acteur)"
    wd["A8"].font = Font(name=FONT, size=8, color="A6A6A6")
    wd["B8"].font = Font(name=FONT, size=8, color="A6A6A6")
    input_fill = PatternFill("solid", fgColor="FFF2CC")
    for cell in ("B4", "B5", "B6"):
        wd[cell].fill = input_fill
        wd[cell].border = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
    wd["C4"] = "◄ menus déroulants (cellules jaunes)"
    wd["C4"].font = Font(name=FONT, size=9, italic=True, color="7F7F7F")
    dvp = DataValidation(type="list", formula1="=ListePeriodes", allow_blank=False)
    dva = DataValidation(type="list", formula1="=ListeActeurs", allow_blank=False)
    wd.add_data_validation(dvp)
    wd.add_data_validation(dva)
    dvp.add("B4")
    dva.add("B5")

    # critères communs : période + acteur choisi
    # plages bornées (marge pour les lignes ajoutées à la main) : plus rapide que
    # des colonnes entières, notamment avec INDEX(…;0;n)
    R = max(last_row + 1000, 2000)
    col = lambda name: f"Articles!${C[name]}$2:${C[name]}${R}"
    H = col("horodatage")
    first_act, last_act = C["nb_acteurs"], C[actor_ids[-1]] if actor_ids else C["nb_acteurs"]
    ACTS = f"Articles!${first_act}$2:${last_act}${R}"
    ACT = f"INDEX({ACTS},0,$B$8)"
    common = f'{H},">="&$B$7,{ACT},">=1"'

    label("A10", "Articles (période + acteur)")
    wd["B10"] = f"=COUNTIFS({common})"
    label("A11", "dont multi-acteurs")
    wd["B11"] = f'=COUNTIFS({common},{col("nb_acteurs")},">=2")'
    for c in ("B10", "B11"):
        wd[c].font = Font(name=FONT, size=12, bold=True, color="1F3864")

    def block(col, row, title, header, items, formula_for):
        c0 = wd.cell(row=row, column=col, value=title)
        c0.font = Font(name=FONT, size=11, bold=True, color="1F3864")
        for j, h in enumerate(header):
            c = wd.cell(row=row + 1, column=col + j, value=h)
            c.font, c.fill = HEAD_FONT, HEAD_FILL
        for i, item in enumerate(items):
            r = row + 2 + i
            c = wd.cell(row=r, column=col, value=item)
            c.font = BASE_FONT
            c.border = Border(bottom=THIN)
            f = wd.cell(row=r, column=col + 1, value=formula_for(f"{L(col)}{r}", item))
            f.font = BASE_FONT
            f.border = Border(bottom=THIN)
        return row + 1, row + 1 + len(items)

    top = 13
    sources = [rep.nom for rep in reports]
    src_hdr, src_end = block(1, top, "Par source", ["Source", "Articles"], sources,
                             lambda ref, _: f"=COUNTIFS({col('source')},{ref},{common})")
    act_hdr, act_end = block(4, top, "Par acteur (période)", ["Acteur", "Articles"], actor_ids,
                             lambda ref, _: f'=COUNTIFS({H},">="&$B$7,INDEX({ACTS},0,'
                                         f'MATCH({ref},ListeActeurs,0)),1)')
    ton_items = TONALITES + ["non classé"]

    def ton_formula(ref, item):
        if item == "non classé":     # = total - classés (COUNTIFS sur "" compterait les lignes vides)
            return None
        return f"=COUNTIFS({col('tonalité')},{ref},{common})"
    ton_hdr, ton_end = block(7, top, "Par tonalité", ["Tonalité", "Articles"], ton_items, ton_formula)
    wd.cell(row=ton_end, column=8, value=f"=$B$10-SUM(H{ton_hdr + 1}:H{ton_end - 1})").font = BASE_FONT

    days = []
    d = start.date()
    while d <= end.date():
        days.append(d)
        d += timedelta(days=1)
    days = days[-62:]
    day_hdr, day_end = block(10, top, "Par jour", ["Jour", "Articles"], days,
                             lambda ref, _: f"=COUNTIFS({col('date')},{ref},{common})")
    for r in range(day_hdr + 1, day_end + 1):
        wd.cell(row=r, column=10).number_format = "DD/MM/YYYY"

    for col, w in zip("ABCDEFGHIJK", (26, 22, 3, 16, 10, 3, 13, 10, 3, 12, 10)):
        wd.column_dimensions[col].width = w

    # graphiques --------------------------------------------------------------
    chart_row = max(src_end, act_end, ton_end, day_end) + 3

    def bar(title, col, hdr, end_row, anchor, horizontal=True):
        ch = BarChart()
        ch.type = "bar" if horizontal else "col"
        ch.title, ch.legend, ch.style = title, None, 10
        ch.add_data(Reference(wd, min_col=col + 1, min_row=hdr, max_row=end_row), titles_from_data=True)
        ch.set_categories(Reference(wd, min_col=col, min_row=hdr + 1, max_row=end_row))
        ch.height, ch.width = 7.5, 13
        wd.add_chart(ch, anchor)

    bar("Articles par source", 1, src_hdr, src_end, f"A{chart_row}")
    bar("Articles par acteur", 4, act_hdr, act_end, f"G{chart_row}")
    days_chart = BarChart()
    days_chart.type, days_chart.title, days_chart.legend, days_chart.style = "col", "Articles par jour", None, 10
    days_chart.add_data(Reference(wd, min_col=11, min_row=day_hdr, max_row=day_end), titles_from_data=True)
    days_chart.set_categories(Reference(wd, min_col=10, min_row=day_hdr + 1, max_row=day_end))
    days_chart.height, days_chart.width = 7.5, 13
    wd.add_chart(days_chart, f"A{chart_row + 16}")
    pie = PieChart()
    pie.title = "Tonalité"
    pie.add_data(Reference(wd, min_col=8, min_row=ton_hdr, max_row=ton_end), titles_from_data=True)
    pie.set_categories(Reference(wd, min_col=7, min_row=ton_hdr + 1, max_row=ton_end))
    for i, color in enumerate(("70AD47", "A5A5A5", "C00000", "DDEBF7")):
        pt = DataPoint(idx=i)
        pt.graphicalProperties.solidFill = color
        pie.series[0].dPt.append(pt)
    pie.height, pie.width = 7.5, 13
    wd.add_chart(pie, f"G{chart_row + 16}")

    note_row = chart_row + 32
    wd.cell(row=note_row, column=1, value="Segments (slicers)").font = BOLD
    wd.cell(row=note_row + 1, column=1, value=(
        "La feuille Articles est une Table Excel : pour ajouter des segments, cliquer dans la table puis "
        "Création de tableau > Insérer un segment (source, langue, tonalité, statut, acteurs…). "
        "Ils ne peuvent pas être générés automatiquement par openpyxl ; les menus ci-dessus et les "
        "filtres de la table offrent le même filtrage.")).font = Font(name=FONT, size=9, color="595959")

    # ======================= Mots-clés ======================================
    wk = wb.create_sheet("Mots-clés")
    hdr = ["id", "libellé", "type", "parti", "actif", "termes", "termes_faibles", "contexte",
           "sensible_casse", "couleur"]
    for j, h in enumerate(hdr, 1):
        c = wk.cell(row=1, column=j, value=h)
        c.font, c.fill = HEAD_FONT, HEAD_FILL
    for i, a in enumerate((all_actors or actors), start=2):
        vals = [a.id, a.libelle, a.type, a.parti, "oui" if a.actif else "non (à confirmer)",
                " | ".join(a.termes), " | ".join(a.termes_faibles), " | ".join(a.contexte),
                " | ".join(a.sensible_casse), a.couleur]
        for j, v in enumerate(vals, 1):
            c = wk.cell(row=i, column=j, value=v)
            c.font, c.alignment = BASE_FONT, LTR
        wk.cell(row=i, column=10).fill = PatternFill("solid", fgColor=a.couleur)
    for col, w in zip("ABCDEFGHIJ", (13, 34, 10, 10, 16, 60, 30, 40, 14, 10)):
        wk.column_dimensions[col].width = w
    wk.freeze_panes = "B2"
    r = len((all_actors or actors)) + 3
    wk.cell(row=r, column=1, value="Normalisation : arabe sans tashkeel/tatweel, أ/إ/آ→ا, ى→ي, ة→ه ; "
            "français insensible à la casse et aux accents ; mots entiers ; préfixes arabes و ف ب ل ك gérés. "
            "Un terme faible ne compte que si un terme sûr ou un mot de contexte est présent.").font = \
        Font(name=FONT, size=9, italic=True)

    # ======================= Sources ========================================
    wsrc = wb.create_sheet("Sources")
    hdr = ["clé", "source", "url", "langue", "état", "à confirmer", "méthode préférée", "méthode utilisée",
           "REST", "RSS", "HTML", "trouvés (fenêtre)", "nouveaux", "retenus", "requêtes", "durée (s)", "erreurs"]
    for j, h in enumerate(hdr, 1):
        c = wsrc.cell(row=1, column=j, value=h)
        c.font, c.fill = HEAD_FONT, HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for i, rep in enumerate(reports, start=2):
        vals = [rep.cle, rep.nom, rep.url, rep.langue, rep.etat, "oui" if rep.a_confirmer else "",
                rep.methode_preferee, rep.methode_utilisee or "-", rep.statuts.get("rest", ""),
                rep.statuts.get("rss", ""), rep.statuts.get("html", ""), rep.trouves, rep.nouveaux,
                rep.retenus, rep.requetes, rep.duree, " || ".join(rep.erreurs)]
        for j, v in enumerate(vals, 1):
            c = wsrc.cell(row=i, column=j, value=v)
            c.font, c.alignment = BASE_FONT, LTR
        wsrc.cell(row=i, column=3).hyperlink = rep.url
        wsrc.cell(row=i, column=3).font = LINK_FONT
        color = {"OK": "C6EFCE", "BLOQUÉ": "FFC7CE", "ÉCHEC": "FFEB9C"}[rep.etat]
        wsrc.cell(row=i, column=5).fill = PatternFill("solid", fgColor=color)
    tr = len(reports) + 2
    wsrc.cell(row=tr, column=2, value="Total").font = BOLD
    for j in (12, 13, 14, 15):
        wsrc.cell(row=tr, column=j, value=f"=SUM({L(j)}2:{L(j)}{tr - 1})").font = BOLD
    for col, w in zip("ABCDEFGHIJKLMNOPQ", (12, 18, 26, 7, 9, 9, 10, 10, 26, 26, 26, 10, 10, 9, 9, 9, 60)):
        wsrc.column_dimensions[col].width = w
    wsrc.freeze_panes = "C2"
    if params:
        pr = tr + 2
        wsrc.cell(row=pr, column=2, value="Paramètres").font = BOLD
        for k, (key, v) in enumerate(params.items(), start=1):
            wsrc.cell(row=pr + k, column=2, value=key).font = BASE_FONT
            wsrc.cell(row=pr + k, column=3, value=str(v)).font = BASE_FONT

    wb.calculation.fullCalcOnLoad = True
    return wb


def write_excel(path, *args, **kwargs) -> str:
    wb = build_workbook(*args, **kwargs)
    wb.save(path)
    return str(path)
