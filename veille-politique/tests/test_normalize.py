from core.normalize import detect_language, normalize_arabic, normalize_text, title_key


def test_tashkeel_et_tatweel_retires():
    assert normalize_arabic("الأَصَالَةُ") == "الاصاله"
    assert normalize_arabic("المعـــاصرة") == "المعاصره"


def test_alef_ya_ta_marbuta():
    assert normalize_arabic("أإآٱ") == "اااا"
    assert normalize_arabic("مصطفى") == "مصطفي"
    assert normalize_arabic("حكومة") == "حكومه"


def test_francais_casse_et_accents():
    assert normalize_text("Authenticité et MODERNITÉ") == "authenticite et modernite"
    assert normalize_text("l’Istiqlal") == "l'istiqlal"


def test_texte_mixte_et_espaces():
    assert normalize_text("  Le  PAM   والبامّ ") == "le pam والبام"


def test_ligature_lam_alef():
    assert normalize_text("ﻻ") == "لا"


def test_title_key_ignore_ponctuation():
    assert title_key("« Le PAM » : réunion — demain !") == title_key("Le PAM, réunion demain")
    assert title_key("المنصوري: البام متمسك") == title_key("المنصوري : البامُ متمسك!")


def test_detection_langue():
    assert detect_language("بنكيران يهاجم الحكومة") == "ar"
    assert detect_language("Benkirane attaque le gouvernement", default="ar") == "fr"
