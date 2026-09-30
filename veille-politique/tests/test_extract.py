from core.extract import first_paragraph

LONG_AR = "قال نزار بركة، الأمين العام لحزب الاستقلال، إن الحكومة ماضية في تنفيذ التزاماتها الاجتماعية."
LONG_FR = "Le bureau politique du PAM s'est réuni mardi à Rabat pour évaluer le bilan de la majorité."


def test_ignore_legende_figure():
    html = f"<figure><img src=x><figcaption>Photo : archives, réunion du bureau politique à Rabat</figcaption></figure><p>{LONG_FR}</p>"
    assert first_paragraph(html) == LONG_FR


def test_ignore_pub_par_classe():
    html = (f"<div class='code-block ads'><p>Publicité publicité publicité publicité publicité publicité</p></div>"
            f"<p class='wp-caption-text'>Légende d'une photo assez longue pour passer le seuil</p><p>{LONG_AR}</p>")
    assert first_paragraph(html) == LONG_AR


def test_ignore_lire_aussi_et_liens_seuls():
    html = ("<p><strong>اقرأ أيضا:</strong> <a href='/x'>البام يعقد دورة مجلسه الوطني في الرباط</a></p>"
            "<p><a href='/y'>Un autre article lié dont le titre est suffisamment long ici</a></p>"
            f"<p>Lire aussi : un article sans rapport avec le sujet principal du jour</p><p>{LONG_FR}</p>")
    assert first_paragraph(html) == LONG_FR


def test_ignore_paragraphes_trop_courts_et_credit():
    html = f"<p>MAP</p><p>&nbsp;</p><p>Photo : Hespress / Archives de la rédaction 2026</p><p>{LONG_FR}</p>"
    assert first_paragraph(html) == LONG_FR


def test_scripts_et_entites():
    html = f"<script>var a='<p>faux paragraphe très long mais dans un script ignoré</p>'</script><p>{LONG_FR.replace(chr(39), '&#8217;')}</p>"
    assert first_paragraph(html) == LONG_FR.replace("'", "’")


def test_texte_brut_et_vide():
    assert first_paragraph("") == ""
    assert first_paragraph("Texte brut sans balise") == "Texte brut sans balise"
    assert first_paragraph("<div>Contenu sans paragraphe mais avec du texte</div>") == \
        "Contenu sans paragraphe mais avec du texte"
