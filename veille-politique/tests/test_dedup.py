from datetime import datetime, timedelta

from core.dates import TZ
from core.dedup import canonical_url, deduplicate
from core.models import Article

T0 = datetime(2026, 9, 30, 10, 0, tzinfo=TZ)


def art(url, titre, src="A", minutes=0):
    return Article(url=url, source=src, source_nom=src, langue="ar", titre=titre, paragraphe="",
                   date=T0 + timedelta(minutes=minutes))


def test_canonical_url():
    assert canonical_url("http://www.site.ma/a/b/?utm_source=fb#x") == "https://site.ma/a/b"
    assert canonical_url("https://site.ma/a/b/amp/") == "https://site.ma/a/b"
    assert canonical_url("https://site.ma/?p=12&utm_medium=x") == "https://site.ma/?p=12"


def test_doublon_par_url():
    arts = [art("https://site.ma/a/", "Titre un"), art("http://www.site.ma/a?utm_source=x", "Titre un bis")]
    kept, removed = deduplicate(arts)
    assert len(kept) == 1 and removed == 1


def test_doublon_par_titre_normalise_multi_sources():
    arts = [art("https://b.ma/2", "المنصوري : البام متمسك بالتحالف مع الأحرار!", "B", minutes=30),
            art("https://a.ma/1", "المنصوري: البامُ متمسك بالتحالف مع الأحرار", "A", minutes=0)]
    kept, removed = deduplicate(arts)
    assert removed == 1
    assert kept[0].source == "A"            # la première publication est gardée
    assert kept[0].reprises == ["B"]


def test_titres_proches_mais_differents_conserves():
    arts = [art("https://a.ma/1", "Benkirane attaque le gouvernement sur les prix"),
            art("https://a.ma/2", "Benabdallah attaque le gouvernement sur l'eau potable")]
    kept, _ = deduplicate(arts)
    assert len(kept) == 2


def test_quasi_doublon_leger_ecart():
    arts = [art("https://a.ma/1", "Le RNI et le PAM affichent leur unité au Parlement", "A"),
            art("https://b.ma/9", "Le RNI et le PAM affichent leur unité au parlement.", "B", 5)]
    kept, removed = deduplicate(arts)
    assert len(kept) == 1 and removed == 1
