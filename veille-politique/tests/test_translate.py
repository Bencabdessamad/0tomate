from core.storage import Storage
from core.translate import Translator
from tests.helpers import make_article


class FakeTranslator(Translator):
    def __init__(self, storage):
        super().__init__(storage, engine="claude", batch_size=3)
        self.calls = []

    def _claude(self, texts):
        self.calls.append(list(texts))
        return [f"FR:{t}" for t in texts]


def test_cache_evite_toute_retraduction(tmp_path):
    st = Storage(tmp_path / "t.db")
    tr = FakeTranslator(st)
    arts = [make_article("https://a.ma/1", "عنوان أول", "فقرة أولى"),
            make_article("https://a.ma/2", "عنوان ثان", "فقرة ثانية"),
            make_article("https://a.ma/3", "Titre français", "Paragraphe", langue="fr")]
    tr.translate_articles(arts)
    assert arts[0].titre_trad == "FR:عنوان أول" and arts[1].paragraphe_trad == "FR:فقرة ثانية"
    assert arts[2].titre_trad == ""                 # déjà en français : pas traduit
    assert sum(len(c) for c in tr.calls) == 4      # 4 textes arabes, par lots de 3
    assert len(tr.calls) == 2

    tr2 = FakeTranslator(st)                       # nouvelle exécution, même base
    again = [make_article("https://a.ma/1", "عنوان أوّل", "فقرة أولى")]  # harakat : même clé
    tr2.translate_articles(again)
    assert tr2.calls == [] and again[0].titre_trad == "FR:عنوان أول"
    assert tr2.stats["cache"] == 2


def test_textes_identiques_traduits_une_fois(tmp_path):
    tr = FakeTranslator(Storage(tmp_path / "t.db"))
    out = tr.translate_texts(["نفس النص", "نفس النص", ""])
    assert out == ["FR:نفس النص", "FR:نفس النص", ""]
    assert tr.calls == [["نفس النص"]]


def test_sans_moteur_colonnes_vides(tmp_path):
    tr = Translator(Storage(tmp_path / "t.db"), engine="aucun")
    tr.engine = None
    arts = [make_article("https://a.ma/1", "عنوان", "فقرة")]
    tr.translate_articles(arts)
    assert arts[0].titre_trad == ""
