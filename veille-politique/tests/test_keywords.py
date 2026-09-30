from pathlib import Path

import pytest

from core.keywords import Actor, KeywordMatcher

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def m():
    return KeywordMatcher.from_yaml(ROOT / "keywords.yaml")


def ids(m, text):
    return set(m.find(text).actor_ids)


def test_arabe_avec_prefixes(m):
    assert ids(m, "اجتماع لحزب الأصالة والمعاصرة") == {"PAM"}
    assert ids(m, "والبام يرد") == {"PAM"}
    assert ids(m, "وقال للمنصوري") == {"Mansouri"}


def test_arabe_avec_harakat_et_hamza(m):
    assert ids(m, "حِزْبُ الإستقلال") == {"PI"}           # إ normalisé en ا
    assert ids(m, "التجمّع الوطنيّ للأحرار") == {"RNI"}


def test_francais_insensible_casse_accents(m):
    assert ids(m, "le parti AUTHENTICITE ET MODERNITE") == {"PAM"}
    assert ids(m, "Fatima-Zahra El Mansouri s'exprime") == {"Mansouri"}
    assert ids(m, "BENKIRANE et le pjd") == {"Benkirane"}   # sigle PJD sensible à la casse


def test_sigles_mots_entiers(m):
    assert ids(m, "PAMPERS et Pampa") == set()
    assert ids(m, "Le PAM, le RNI et le PPS") == {"PAM", "RNI", "PPS"}
    assert ids(m, "la pam du jour") == set()            # "pam" minuscule ≠ sigle


def test_termes_faibles_exigent_contexte(m):
    assert ids(m, "احتفالات عيد الاستقلال") == set()
    assert ids(m, "بركة الله فيكم") == set()
    assert ids(m, "اجتماع للأحرار") == set()
    assert ids(m, "بركة يترأس اجتماع حزب الاستقلال") == {"PI"}
    assert ids(m, "قيادة حزب الأحرار") == {"RNI"}


def test_mots_cles_trouves(m):
    r = m.find("قال نزار بركة إن حزب الاستقلال")
    assert "نزار بركة" in r.terms and "حزب الاستقلال" in r.terms


def test_placeholder_inactif(m):
    assert "A_CONFIRMER" not in m.actor_ids
    assert ids(m, "الاتحاد الاشتراكي") == set()


def test_filtre_acteurs():
    m2 = KeywordMatcher.from_yaml(ROOT / "keywords.yaml", only=["pam", "RNI"])
    assert m2.actor_ids == ["PAM", "RNI"]
    with pytest.raises(ValueError):
        KeywordMatcher.from_yaml(ROOT / "keywords.yaml", only=["XYZ"])


def test_acteur_personnalise():
    m2 = KeywordMatcher([Actor(id="X", libelle="X", termes=["أخنوش", "Akhannouch"])])
    assert m2.find("رئيس الحكومة عزيز أخنوش").actor_ids == ["X"]
    assert m2.find("Aziz AKHANNOUCH").actor_ids == ["X"]
