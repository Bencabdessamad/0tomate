from datetime import datetime

from core.dates import TZ
from core.models import Article


def make_article(url, titre, para, langue="ar", source="s", minutes=0):
    return Article(url=url, source=source, source_nom=source, langue=langue, titre=titre, paragraphe=para,
                   date=datetime(2026, 9, 30, 10, minutes, tzinfo=TZ))
