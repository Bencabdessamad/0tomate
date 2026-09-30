"""Faux sites locaux pour tester la chaîne complète hors ligne.

Chaque "site" tourne sur son propre port et simule un comportement réel :
REST OK, REST absent -> RSS, anti-robot -> HTML, 500, 403, robots.txt fermé…

    python -m tests.mock_sites            # lance les serveurs + veille.py
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import timedelta, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.dates import now  # noqa: E402

NOW = now()
H = lambda h: NOW - timedelta(hours=h)

AR_PARA_PAM = ("<figure class='wp-block-image'><img src='x.jpg'><figcaption>صورة : أرشيف - اجتماع "
               "المكتب السياسي للحزب بالرباط</figcaption></figure>"
               "<div class='code-block ads'><p>إعلان إعلان إعلان إعلان إعلان إعلان إعلان إعلان إعلان</p></div>"
               "<p><strong>اقرأ أيضا:</strong> <a href='/x'>البام يعقد دورة مجلسه الوطني في الرباط الأسبوع المقبل</a></p>"
               "<p>ترأست فاطمة الزهراء المنصوري، منسقة القيادة الجماعية لحزب الأصالة والمعاصرة، اجتماعاً "
               "للمكتب السياسي خُصص لتقييم حصيلة الأغلبية الحكومية مع حزب التجمع الوطني للأحرار.</p>"
               "<p>وأكدت المنصوري أن الحزب متمسك بالتحالف الحكومي.</p>")

SITES = {
    "hespress_ar": {"behavior": "rest", "lang": "ar", "posts": [
        dict(t="المنصوري: البام متمسك بالتحالف مع الأحرار", c=AR_PARA_PAM, h=2),
        dict(t="بنكيران يهاجم الحكومة ويدعو إلى انتخابات نزيهة",
             c="<p>انتقد عبد الإله بنكيران، الأمين العام لحزب العدالة والتنمية، أداء الحكومة الحالية "
               "في مهرجان خطابي بمدينة سلا.</p>", h=5),
        dict(t="الطقس: أمطار رعدية مرتقبة بعدد من المناطق",
             c="<p>تتوقع المديرية العامة للأرصاد الجوية أمطارا رعدية قوية بعدد من أقاليم المملكة يوم غد.</p>", h=3),
        dict(t="احتفالات بذكرى عيد الاستقلال في مختلف المدن",
             c="<p>تخلد المملكة ذكرى عيد الاستقلال بتنظيم أنشطة ثقافية ورياضية في مختلف المدن والجهات.</p>", h=4),
        dict(t="نزار بركة: حزب الاستقلال سيقدم مقترحات لإصلاح مدونة الانتخابات",
             c="<p>قال نزار بركة، الأمين العام لحزب الاستقلال، إن الحزب سيقدم مذكرة مفصلة حول إصلاح "
               "المنظومة الانتخابية قبل نهاية الشهر.</p>", h=8),
        dict(t="بنعبد الله ينتقد تدبير ملف الماء",
             c="<p>انتقد نبيل بنعبد الله، الأمين العام لحزب التقدم والاشتراكية، ما وصفه بالتأخر في "
               "تدبير أزمة الماء في عدد من الجهات.</p>", h=30),   # hors fenêtre 24 h
    ]},
    "hespress_fr": {"behavior": "rss", "lang": "fr", "posts": [
        dict(t="Le RNI et le PAM affichent leur unité au Parlement",
             c="<p>Les groupes parlementaires du Rassemblement national des indépendants et du PAM ont "
               "présenté mardi une position commune sur le projet de loi de finances.</p>", h=1),
        dict(t="Benkirane appelle à un sursaut du PJD",
             c="<p>Abdelilah Benkirane a appelé les militants du Parti de la justice et du développement "
               "à se mobiliser en vue des prochaines échéances électorales.</p>", h=6),
        dict(t="Coupe du monde 2030 : le chantier du grand stade avance",
             c="<p>Les travaux du grand stade de Benslimane progressent selon le calendrier prévu par les "
               "autorités, a-t-on appris auprès du comité d'organisation.</p>", h=7),
        dict(t="Pampers et Pampa : une campagne publicitaire fait sourire",
             c="<p>Une campagne mêlant les deux marques amuse les internautes marocains depuis ce week-end, "
               "sans aucun lien avec la politique.</p>", h=2),
    ]},
    "al3omk": {"behavior": "html", "lang": "ar", "posts": [
        dict(t="شوكي: التجمع الوطني للأحرار منفتح على كل الفرقاء",
             c="<p>قال محمد شوكي، رئيس حزب التجمع الوطني للأحرار، إن الحزب منفتح على الحوار مع كل الفرقاء "
               "السياسيين في أفق الاستحقاقات المقبلة.</p>", h=3),
        dict(t="المعارضة تنتقد الحكومة بسبب غلاء الأسعار",
             c="<p>انتقدت فرق المعارضة بمجلس النواب، ومنها فريق التقدم والاشتراكية، ما وصفته بعجز الحكومة "
               "عن مواجهة موجة الغلاء.</p>", h=9),
        dict(t="افتتاح معرض الكتاب بالرباط",
             c="<p>افتتحت الدورة الجديدة للمعرض الدولي للنشر والكتاب بالرباط بمشاركة مئات العارضين.</p>", h=10),
    ]},
    "lakome2": {"behavior": "rest", "lang": "ar", "posts": [
        # reprise quasi identique de la dépêche hespress_ar (dédoublonnage)
        dict(t="المنصوري : البام متمسك بالتحالف مع الأحرار!", c=AR_PARA_PAM, h=1.5),
        dict(t="بركة الله في الجهود التطوعية بالقرى",
             c="<p>أشاد فاعلون جمعويون بالجهود التطوعية التي تقوم بها الجمعيات في القرى الجبلية خلال فصل الشتاء.</p>",
             h=4),
    ]},
    "hibapress": {"behavior": "500", "lang": "ar", "posts": []},
    "thevoice": {"behavior": "403", "lang": "fr", "posts": []},
    "alaoual": {"behavior": "robots", "lang": "ar", "posts": []},
    "madar21": {"behavior": "rss", "lang": "ar", "posts": [
        dict(t="الأصالة والمعاصرة تعقد دورة مجلسها الوطني",
             c="<p>يعقد حزب الأصالة والمعاصرة دورة عادية لمجلسه الوطني نهاية الأسبوع لانتخاب هياكل جديدة.</p>",
             h=12),
    ]},
}


def _posts(key, base):
    out = []
    for i, p in enumerate(SITES[key]["posts"], start=1):
        d = H(p["h"])
        out.append({"id": i, "date": d.replace(tzinfo=None).isoformat(timespec="seconds"),
                    "date_gmt": d.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
                    "link": f"{base}/{key}/article-{i}/?utm_source=rss",
                    "title": {"rendered": p["t"]}, "content": {"rendered": p["c"]},
                    "excerpt": {"rendered": ""}, "_date": d})
    return out


def _rss(key, base):
    items = "".join(
        f"<item><title>{p['title']['rendered']}</title><link>{p['link']}</link>"
        f"<pubDate>{format_datetime(p['_date'])}</pubDate>"
        f"<description><![CDATA[{p['content']['rendered']}]]></description></item>"
        for p in _posts(key, base))
    return f"<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel><title>{key}</title>{items}</channel></rss>"


def make_handler(key):
    cfg = SITES[key]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="text/html; charset=utf-8", headers=None):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            base = f"http://{self.headers['Host']}"
            path = urlsplit(self.path).path
            b = cfg["behavior"]
            if path == "/robots.txt":
                if b == "robots":
                    return self.send(200, "User-agent: *\nDisallow: /\n", "text/plain")
                return self.send(200, "User-agent: *\nDisallow: /wp-admin/\n", "text/plain")
            if b == "500":
                return self.send(500, "Internal Server Error")
            if b == "403":
                return self.send(403, "Forbidden")
            if path.startswith("/wp-json/wp/v2/posts"):
                if b == "rest":
                    posts = [{k: v for k, v in p.items() if k != "_date"} for p in _posts(key, base)]
                    return self.send(200, json.dumps(posts, ensure_ascii=False), "application/json",
                                     {"X-WP-TotalPages": "1"})
                if b == "html":   # anti-robot : page HTML à la place du JSON
                    return self.send(200, "<html><body>Checking your browser…</body></html>")
                return self.send(404, "<html>404</html>")
            if path in ("/feed/", "/feed", "/rss"):
                if b in ("rss", "rest"):
                    return self.send(200, _rss(key, base), "application/rss+xml; charset=utf-8")
                return self.send(404, "not found")
            if path.rstrip("/") == "/category/politique":
                links = "".join(
                    f"<article><h3 class='entry-title'><a href='/{key}/article-{p['id']}/'>{p['title']['rendered']}</a></h3></article>"
                    for p in _posts(key, base))
                return self.send(200, f"<html><body><a href='/category/sport/'>رياضة</a>{links}"
                                      f"<a href='/tag/x/'>وسم</a></body></html>")
            for p in _posts(key, base):
                if path.rstrip("/") == f"/{key}/article-{p['id']}":
                    return self.send(200, (
                        f"<html><head><meta property='og:title' content='{p['title']['rendered']}'>"
                        f"<meta property='article:published_time' content='{p['_date'].isoformat()}'></head>"
                        f"<body><h1>{p['title']['rendered']}</h1><div class='share'><p>شارك المقال على فيسبوك وتويتر وواتساب الآن</p></div>"
                        f"<div class='entry-content'>{p['content']['rendered']}</div></body></html>"))
            return self.send(404, "not found")

    return Handler


def start_servers(port0=18080) -> dict[str, str]:
    urls = {}
    for i, key in enumerate(SITES):
        srv = ThreadingHTTPServer(("127.0.0.1", port0 + i), make_handler(key))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        urls[key] = f"http://127.0.0.1:{port0 + i}"
    return urls


def write_config(urls: dict, real_config: Path, out: Path, db: Path, out_dir: Path) -> Path:
    cfg = yaml.safe_load(real_config.read_text(encoding="utf-8"))
    cfg["defaults"].update({"retries": 1, "base": str(db), "dossier_sortie": str(out_dir)})
    for key, site in cfg["sites"].items():
        site["url"] = urls[key]
        site.pop("rss", None)
        site.pop("selecteurs", None)
        site["rubriques"] = [urls[key] + "/category/politique"]
        site["methode_preferee"] = "rss" if key == "madar21" else "rest"
    out.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    work = (Path(sys.argv[1]) if len(sys.argv) > 1 else root / "sorties" / "demo").resolve()
    work.mkdir(parents=True, exist_ok=True)
    urls = start_servers()
    cfg = write_config(urls, root / "sites.yaml", work / "sites_mock.yaml", work / "veille_demo.db", work)
    import veille
    sys.exit(veille.main(["--config", str(cfg), *sys.argv[2:]]))
