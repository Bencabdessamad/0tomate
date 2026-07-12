"""Assembles index.html from src/ — a self-contained page with fonts and
React/ReactDOM/htm inlined (no CDN/runtime network requests). Run from the
repo root: python3 build.py
"""
import base64
import pathlib

root = pathlib.Path(__file__).parent
src = root / "src"

def b64(path):
    return base64.b64encode(path.read_bytes()).decode("ascii")

big_shoulders = b64(src / "fonts" / "big-shoulders.woff2")
public_sans = b64(src / "fonts" / "public-sans.woff2")
plex_400 = b64(src / "fonts" / "ibm-plex-mono-400.woff2")
plex_500 = b64(src / "fonts" / "ibm-plex-mono-500.woff2")

react_js = (src / "vendor" / "react.production.min.js").read_text()
reactdom_js = (src / "vendor" / "react-dom.production.min.js").read_text()
htm_js = (src / "vendor" / "htm.umd.js").read_text()

app_css = (src / "app.css").read_text()
app_js = (src / "app.js").read_text()

font_faces = f"""
@font-face {{
  font-family: 'Big Shoulders';
  font-style: normal;
  font-weight: 700 800;
  font-display: swap;
  src: url(data:font/woff2;base64,{big_shoulders}) format('woff2');
}}
@font-face {{
  font-family: 'Public Sans';
  font-style: normal;
  font-weight: 400 700;
  font-display: swap;
  src: url(data:font/woff2;base64,{public_sans}) format('woff2');
}}
@font-face {{
  font-family: 'IBM Plex Mono';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url(data:font/woff2;base64,{plex_400}) format('woff2');
}}
@font-face {{
  font-family: 'IBM Plex Mono';
  font-style: normal;
  font-weight: 500;
  font-display: swap;
  src: url(data:font/woff2;base64,{plex_500}) format('woff2');
}}
""".strip()

css_final = app_css.replace(
    "/* ===== Fonts injected by build.py: @font-face Big Shoulders / Public Sans / IBM Plex Mono ===== */",
    font_faces,
)

html_out = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Otomat — Automatisation de process pour PME</title>
<meta name="description" content="Otomat automatise le traitement de vos factures, bons de commande et validations internes. Rejoignez la liste d'attente." />
<style>
{css_final}
</style>
</head>
<body>
<div id="root"></div>

<script>
{react_js}
</script>
<script>
{reactdom_js}
</script>
<script>
{htm_js}
</script>
<script>
{app_js}
</script>
</body>
</html>
"""

out_path = root / "index.html"
out_path.write_text(html_out)
print("wrote", out_path, len(html_out), "bytes")
