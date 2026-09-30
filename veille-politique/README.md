# Veille politique Maroc

Outil de veille de la communication politique marocaine : collecte les articles
récents de sites de presse (arabe et français), repère les acteurs et partis
suivis, traduit l'arabe en français et produit un **Excel prêt à filtrer**
(table filtrable, tableau de bord, graphiques).

```
veille-politique/
├── veille.py            # point d'entrée (CLI)
├── sites.yaml           # sources : ajouter un site = éditer ce fichier
├── keywords.yaml        # acteurs / partis et leurs variantes ar/fr
├── collectors/          # REST WordPress -> RSS -> HTML
├── core/                # normalisation, mots-clés, dédoublonnage, SQLite,
│                        # traduction, tonalité, exports Excel/CSV
├── tests/               # pytest + faux sites locaux (tests/mock_sites.py)
├── lancer_veille.sh     # lancement planifié (cron)
└── lancer_veille.bat    # lancement planifié (Windows)
```

## Installation

Python 3.10 ou plus récent.

```bash
cd veille-politique
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Clé API Anthropic (traduction et tonalité)

La traduction arabe → français et la tonalité utilisent le modèle
`claude-haiku-4-5-20251001`, par lots, avec un cache SQLite (un même texte
n'est jamais traduit ni classé deux fois). Seuls les articles **retenus après
filtrage par mots-clés** sont envoyés, et les articles déjà en français ne sont
pas traduits.

```bash
export ANTHROPIC_API_KEY=sk-ant-...                 # Linux / macOS
setx ANTHROPIC_API_KEY "sk-ant-..."                 # Windows (nouvelle console ensuite)
```

Sans clé :

- la traduction se rabat sur `deep-translator` (Google Traduction, gratuit, sans clé) ;
- la colonne `tonalité` reste vide (vous pouvez la remplir à la main : elle a une liste déroulante).

Pour changer de modèle : variable d'environnement `VEILLE_MODELE`.

## Utilisation

```bash
python veille.py                                    # 24 dernières heures, tous les sites, tous les acteurs
python veille.py --heures 24 --sites hespress,al3omk --acteurs PAM,RNI \
                 --langue fr --traduire --sortie excel
python veille.py --depuis 2026-09-01 --sortie csv   # depuis une date
python veille.py --no-traduire --no-tonalite -v     # sans appel API, journal détaillé
```

| Option | Rôle |
|---|---|
| `--heures N` | fenêtre glissante de N heures (défaut 24) |
| `--depuis YYYY-MM-DD` | début de la fenêtre (prioritaire sur `--heures`) |
| `--sites a,b` | clés de `sites.yaml` ; un préfixe marche (`hespress` = `hespress_ar` + `hespress_fr`) |
| `--acteurs PAM,RNI` | `id` de `keywords.yaml` (défaut : tous les actifs) |
| `--langue fr` | langue cible de la traduction (colonnes `titre_fr`, `paragraphe_fr`) |
| `--langues-source ar,fr` | langues d'articles à conserver |
| `--traduire` / `--no-traduire` | traduction (activée par défaut) |
| `--tonalite` / `--no-tonalite` | tonalité via Claude (activée par défaut si clé) |
| `--sortie excel\|csv` | format (CSV : UTF-8 BOM, séparateur `;`) |
| `--config sites.yaml` | autre fichier de sites |
| `--keywords keywords.yaml` | autre fichier de mots-clés |
| `--dossier-sortie`, `--base` | dossier des fichiers, base SQLite |
| `--tous` | exporter aussi les articles sans mot-clé (diagnostic) |
| `--verbose` | journal détaillé |

Les fichiers sont écrits dans `sorties/` : `veille_YYYYMMDD_HHMM.xlsx`, plus un
journal par exécution dans `sorties/logs/`. Toutes les dates sont en heure du
Maroc (`Africa/Casablanca`, y compris le passage à UTC+0 pendant le Ramadan).

### Ce que fait une exécution

1. **Collecte** de chaque site dans l'ordre REST WordPress → RSS → HTML (la
   `methode_preferee` passe en premier). Les sites sont collectés en parallèle ;
   un site en panne n'arrête pas les autres.
2. **Base SQLite** (`veille.db`) : les articles vus y sont conservés. Une
   nouvelle exécution ne re-télécharge pas les pages HTML déjà connues, et
   l'Excel inclut aussi les articles de la fenêtre collectés précédemment (si un
   site tombe aujourd'hui, ceux d'hier restent visibles).
3. **Filtrage par mots-clés** sur titre + premier paragraphe.
4. **Dédoublonnage** par URL canonique (sans `utm_`, `/amp`, `www`…) puis par
   titre normalisé ou quasi identique (ratio ≥ 0,9). La première publication est
   gardée ; les autres sources sont listées dans `reprises_par`.
5. **Traduction** et **tonalité** des articles retenus.
6. **Export** Excel ou CSV.

### Politesse et limites

- User-Agent explicite, respect de `robots.txt`, 1 à 2 s entre deux requêtes
  sur un même site, délai d'expiration de 20 s, 3 nouvelles tentatives avec
  attente croissante sur les erreurs 429 et 5xx.
- Lecture publique et légère uniquement : pas de connexion, pas de
  contournement de protection anti-robot. Un site qui renvoie 403 ou dont le
  `robots.txt` interdit l'accès est marqué **BLOQUÉ** dans la feuille Sources.

## Le fichier Excel

**Articles** : Table Excel avec filtres automatiques, en-tête et 4 premières
colonnes figés, retour à la ligne, texte arabe aligné à droite (sens RTL), liens
cliquables.

- Colonnes : `date`, `heure`, `source`, `langue`, `titre_original`, `titre_fr`,
  `paragraphe_original`, `paragraphe_fr`, `lien`, `acteurs_détectés`,
  `nb_acteurs`, une colonne 0/1 par acteur (Mansouri, PAM, RNI, PI, Benkirane,
  PJD, Benabdellah, PPS), `mots_clés_trouvés`, `tonalité`, `statut` (liste
  déroulante *à traiter* / *traité*), `commentaire`, `reprises_par`.
- Mise en forme conditionnelle : chaque colonne d'acteur prend la couleur de
  son parti, `acteurs_détectés` aussi. Les articles citant au moins 2 acteurs
  sont surlignés en orange clair. Tonalité en vert ou rouge, lignes *traité* grisées.

**Tableau de bord** : menus déroulants *Période* (Tout, Aujourd'hui, 24 h,
7 jours, 30 jours, fenêtre de collecte) et *Acteur*. Les compteurs utilisent
`COUNTIFS` : articles par source, par acteur, par jour, par tonalité, et
multi-acteurs. Quatre graphiques en dépendent. La *date de référence*
(cellule B6) est l'heure de génération : remplacez-la par `=MAINTENANT()` pour
des périodes glissantes.

**Mots-clés** : la liste utilisée (traçabilité). **Sources** : état de la
collecte par site (méthode utilisée, résultat REST/RSS/HTML, trouvés,
nouveaux, retenus, erreurs, durée) et paramètres de l'exécution.

### Segments (slicers)

openpyxl ne sait pas créer de segments. Comme la feuille Articles est une vraie
Table Excel, vous pouvez les ajouter en deux clics : cliquer dans la table,
puis **Création de tableau → Insérer un segment**, et cocher *source*,
*langue*, *tonalité*, *statut* ou les colonnes d'acteurs. Les segments sont
conservés tant que vous travaillez dans ce fichier. En attendant, les menus du
tableau de bord et les filtres de la table offrent le même filtrage.

## Ajouter un site

Éditez uniquement `sites.yaml` :

```yaml
sites:
  lesiteinfo:
    nom: Le Site Info
    url: https://www.lesiteinfo.com
    langue: fr
    methode_preferee: rest          # rest | rss | html
    rss: [https://www.lesiteinfo.com/feed/]            # optionnel
    rubriques: [https://www.lesiteinfo.com/politique/] # pour le repli HTML
    selecteurs:                     # optionnel, repli HTML uniquement
      liens: "h2.entry-title a"
      titre: "h1"
      date: "time[datetime]"
      contenu: ".entry-content"
```

Pour tester un site seul : `python veille.py --sites lesiteinfo -v`, puis
consultez la feuille **Sources**. Sans sélecteurs, des heuristiques génériques
sont utilisées (OpenGraph, JSON-LD, `<time>`, `.entry-content`, `<article>`).

## Ajouter ou modifier un acteur

Éditez `keywords.yaml`. Chaque bloc a un `id`, qui devient le nom de la colonne
0/1, et des `termes`. Écrivez les variantes naturellement : la normalisation
gère les harakat, le tatweel, أ/إ/آ, ى/ي, ة/ه, les accents, la casse et les
préfixes arabes (و ف ب ل ك, et للـ pour الـ). Les mots ambigus (بركة,
الاستقلال, الأحرار, Baraka…) vont dans `termes_faibles` : ils ne comptent que
si un terme sûr ou un mot de `contexte` est présent. Les sigles (PAM, RNI…)
vont dans `sensible_casse` et sont cherchés en mots entiers.

## Tâche planifiée quotidienne

**Linux / macOS (cron)**, tous les jours à 7 h 50 :

```bash
crontab -e
50 7 * * * /chemin/vers/veille-politique/lancer_veille.sh
```

Mettez la clé dans `~/.veille_env` (`export ANTHROPIC_API_KEY=...`), que le script lit.

**Windows (Planificateur de tâches)** :

1. Ouvrir le *Planificateur de tâches* → *Créer une tâche de base*.
2. Déclencheur : *Tous les jours*, 07:50.
3. Action : *Démarrer un programme* → `C:\chemin\veille-politique\lancer_veille.bat`
   (champ *Commencer dans* : le dossier `veille-politique`).
4. Définir `ANTHROPIC_API_KEY` comme variable d'environnement utilisateur (`setx`).

Ou en une ligne :
`schtasks /Create /SC DAILY /ST 07:50 /TN "Veille politique" /TR "C:\chemin\veille-politique\lancer_veille.bat"`

## Tests

```bash
python -m pytest -q
```

Ils couvrent la normalisation arabe, la détection des mots-clés (préfixes,
faux positifs, termes faibles), le dédoublonnage, l'extraction du premier
paragraphe (légendes, pubs, « lire aussi ») et le cache de traduction. Un test
de bout en bout fait aussi tourner la chaîne complète contre des faux sites
locaux qui simulent REST, RSS, HTML, 403, 500 et `robots.txt`.

Démonstration hors ligne : `python -m tests.mock_sites` produit un Excel dans
`sorties/demo/`, avec des articles fictifs.
