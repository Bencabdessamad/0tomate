(function () {
  "use strict";

  var h = window.React.createElement;
  var html = window.htm.bind(h);
  var useState = window.React.useState;
  var useEffect = window.React.useEffect;
  var useRef = window.React.useRef;

  var PROCESS_OPTIONS = [
    { value: "", label: "Sélectionnez un process…" },
    { value: "factures", label: "Traitement des factures" },
    { value: "bons_commande", label: "Bons de commande" },
    { value: "validations", label: "Validations & approbations" },
    { value: "support_interne", label: "Support interne (questions, procédures)" },
    { value: "autre", label: "Autre" },
  ];

  // ---------------------------------------------------------------------
  // Storage: window.storage.set / window.storage.list, with a safe
  // in-memory fallback so the page still works if the host doesn't inject it.
  // ---------------------------------------------------------------------
  var memoryStore = {};
  function getStorage() {
    if (window.storage && typeof window.storage.set === "function" && typeof window.storage.list === "function") {
      return window.storage;
    }
    return {
      set: function (key, value) {
        memoryStore[key] = value;
        return Promise.resolve();
      },
      list: function () {
        return Promise.resolve(Object.keys(memoryStore).map(function (k) {
          return { key: k, value: memoryStore[k] };
        }));
      },
    };
  }

  function extractKey(entry) {
    if (typeof entry === "string") return entry;
    if (entry && typeof entry === "object") return entry.key || entry.name || entry.id || "";
    return "";
  }

  function countWaitlist() {
    var store = getStorage();
    return store.list().then(function (res) {
      var items = Array.isArray(res) ? res : (res && (res.keys || res.items || res.entries)) || [];
      return items.filter(function (it) {
        return extractKey(it).indexOf("waitlist:") === 0;
      }).length;
    });
  }

  // ---------------------------------------------------------------------
  // Hero pipeline canvas — small ambient animation showing a document
  // flowing through the automated steps. Freezes under reduced-motion.
  // ---------------------------------------------------------------------
  function PipelineCanvas() {
    var ref = useRef(null);

    useEffect(function () {
      var canvas = ref.current;
      if (!canvas) return;
      var ctx = canvas.getContext("2d");
      var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      var raf = null;
      var dpr = Math.min(window.devicePixelRatio || 1, 2);

      var nodes = [
        { label: "Reçu" },
        { label: "Extrait" },
        { label: "Vérifié" },
        { label: "Validé" },
      ];

      function layout() {
        var rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        return { w: rect.width, h: rect.height };
      }

      var size = layout();

      function points(w, h) {
        var margin = w * 0.09;
        var y = h * 0.42;
        var span = w - margin * 2;
        return nodes.map(function (n, i) {
          return { x: margin + (span * i) / (nodes.length - 1), y: y, label: n.label };
        });
      }

      function draw(t) {
        var w = size.w, hgt = size.h;
        ctx.clearRect(0, 0, w, hgt);
        var pts = points(w, hgt);

        // connecting rail
        ctx.strokeStyle = "#3c3524";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        ctx.lineTo(pts[pts.length - 1].x, pts[pts.length - 1].y);
        ctx.stroke();

        // nodes
        pts.forEach(function (p, i) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
          ctx.fillStyle = "#16140f";
          ctx.fill();
          ctx.lineWidth = 1.5;
          ctx.strokeStyle = "#8a7f68";
          ctx.stroke();

          ctx.fillStyle = "#b4a88e";
          ctx.font = "500 11px 'IBM Plex Mono', monospace";
          ctx.textAlign = "center";
          ctx.fillText(p.label, p.x, p.y + 26);
        });

        // traveling pulse
        var duration = 5200;
        var cycle = (t % duration) / duration; // 0..1
        var seg = cycle * (pts.length - 1);
        var i0 = Math.min(Math.floor(seg), pts.length - 2);
        var localT = seg - i0;
        var ease = localT < 0.5 ? 2 * localT * localT : 1 - Math.pow(-2 * localT + 2, 2) / 2;
        var a = pts[i0], b = pts[i0 + 1];
        var px = a.x + (b.x - a.x) * ease;
        var py = a.y + (b.y - a.y) * ease;

        var grad = ctx.createRadialGradient(px, py, 0, px, py, 9);
        grad.addColorStop(0, "rgba(232,163,61,0.9)");
        grad.addColorStop(1, "rgba(232,163,61,0)");
        ctx.beginPath();
        ctx.arc(px, py, 9, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(px, py, 3.4, 0, Math.PI * 2);
        ctx.fillStyle = "#f4b756";
        ctx.fill();

        // lit-up nodes behind the pulse
        for (var k = 0; k <= i0; k++) {
          ctx.beginPath();
          ctx.arc(pts[k].x, pts[k].y, 4.5, 0, Math.PI * 2);
          ctx.fillStyle = "#e8a33d";
          ctx.fill();
        }
      }

      if (reduceMotion) {
        draw(0);
      } else {
        var start = null;
        function frame(ts) {
          if (start === null) start = ts;
          draw(ts - start);
          raf = window.requestAnimationFrame(frame);
        }
        raf = window.requestAnimationFrame(frame);
      }

      function onResize() {
        size = layout();
        if (reduceMotion) draw(0);
      }
      window.addEventListener("resize", onResize);

      return function () {
        if (raf) window.cancelAnimationFrame(raf);
        window.removeEventListener("resize", onResize);
      };
    }, []);

    return html`<canvas ref=${ref} aria-hidden="true"></canvas>`;
  }

  function Header() {
    return html`
      <header class="site-header">
        <div class="wrap">
          <a class="logo" href="#top">OTOMAT<span class="dot">.</span><span class="logo-mark">RABAT</span></a>
          <a class="stamp-btn ghost header-cta" href="#waitlist">Rejoindre la liste d'attente</a>
        </div>
      </header>
    `;
  }

  function Hero(props) {
    return html`
      <section class="hero" id="top">
        <div class="wrap">
          <div class="hero-copy">
            <span class="hero-eyebrow eyebrow">Automatisation de process · PME francophones</span>
            <h1>Vos équipes passent <span class="accent">40h par mois</span> à ressaisir des documents. Reprenez-les.</h1>
            <p class="hero-sub">
              Otomat automatise le traitement de vos factures, bons de commande et validations
              internes. Résultat : moins de saisie, moins d'erreurs, des décisions qui ne
              traînent plus dans une boîte mail.
            </p>
            <div class="hero-actions">
              <a class="stamp-btn" href="#waitlist">Rejoindre la liste d'attente</a>
              <span class="hero-count tabular">
                ${props.count !== null
                  ? html`<strong>${String(props.count).padStart(3, "0")}</strong> entreprises déjà inscrites`
                  : "Places limitées pour la première cohorte"}
              </span>
            </div>
          </div>
          <div class="hero-visual">
            <div class="hero-visual-label">
              <span>Flux · Bon de commande #4821</span>
              <span>Auto</span>
            </div>
            <${PipelineCanvas} />
            <p class="hero-visual-caption">Réception → extraction → vérification → validation, sans intervention manuelle.</p>
          </div>
        </div>
      </section>
    `;
  }

  var PAIN_POINTS = [
    {
      title: "La saisie manuelle qui grignote vos journées",
      body: "Vos équipes recopient à la main des factures, bons de commande et relevés. Chaque document, c'est 8 à 12 minutes perdues — répétées des centaines de fois par mois.",
      figure: "8-12 min",
      unit: "par document",
    },
    {
      title: "Les erreurs qui finissent en litige",
      body: "Un montant mal recopié, une référence oubliée : ça part en relance client, en écart de compta, en heures passées à corriger plutôt qu'à produire.",
      figure: "2-4 %",
      unit: "taux d'erreur de saisie",
    },
    {
      title: "Les validations qui traînent dans une boîte mail",
      body: "Un bon de commande attend la signature du bon manager pendant des jours. Pendant ce temps, les fournisseurs patientent et les projets stagnent.",
      figure: "3-5 j",
      unit: "délai moyen d'approbation",
    },
  ];

  function Problem() {
    return html`
      <section class="section" id="probleme">
        <div class="wrap">
          <div class="section-head">
            <span class="eyebrow">Le constat</span>
            <h2 class="section-title">Le problème n'est pas vos équipes. C'est le travail qu'on leur laisse faire.</h2>
          </div>
          <div class="ledger">
            ${PAIN_POINTS.map(function (p, i) {
              return html`
                <div class="ledger-row" key=${i}>
                  <span class="ledger-index tabular">0${i + 1}</span>
                  <div class="ledger-body">
                    <h3>${p.title}</h3>
                    <p>${p.body}</p>
                  </div>
                  <div class="ledger-figure tabular">
                    ${p.figure}
                    <small>${p.unit}</small>
                  </div>
                </div>
              `;
            })}
          </div>
        </div>
      </section>
    `;
  }

  var SOLUTIONS = [
    {
      tag: "Documents",
      title: "Traitement documentaire IA",
      body: "Factures et bons de commande lus, extraits et intégrés automatiquement dans votre ERP ou votre logiciel de compta. Zéro copier-coller.",
      num: "-80 %",
      unit: "de temps de saisie",
    },
    {
      tag: "Assistant",
      title: "Assistant IA interne",
      body: "Un assistant branché sur vos documents et procédures internes, qui répond aux questions de vos équipes sans passer par un collègue.",
      num: "<30 s",
      unit: "temps de réponse, 24/7",
    },
    {
      tag: "Workflows",
      title: "Workflows d'approbation automatisés",
      body: "Routage automatique vers le bon validateur, relances programmées, traçabilité complète. Plus de bon de commande perdu dans une boîte mail.",
      num: "÷4",
      unit: "délai de validation moyen",
    },
  ];

  function Solutions() {
    return html`
      <section class="section" id="solutions">
        <div class="wrap">
          <div class="section-head">
            <span class="eyebrow">Nos solutions</span>
            <h2 class="section-title">Trois automatisations, un seul objectif : libérer du temps.</h2>
            <p class="section-lede">On construit sur mesure, mais on part toujours des mêmes briques éprouvées.</p>
          </div>
          <div class="solutions-grid">
            ${SOLUTIONS.map(function (s, i) {
              return html`
                <div class="solution-card" key=${i}>
                  <span class="eyebrow muted">${s.tag}</span>
                  <h3>${s.title}</h3>
                  <p>${s.body}</p>
                  <div class="solution-stat">
                    <span class="num">${s.num}</span>
                    <span class="unit">${s.unit}</span>
                  </div>
                </div>
              `;
            })}
          </div>
        </div>
      </section>
    `;
  }

  var STEPS = [
    {
      title: "Audit gratuit",
      time: "Semaine 1",
      body: "On cartographie vos process actuels et on chiffre le gain potentiel. Sans engagement, ni jargon.",
    },
    {
      title: "Développement",
      time: "4 semaines",
      body: "On construit et on teste l'automatisation sur vos vrais documents, en itérant avec vos équipes.",
    },
    {
      title: "Supervision continue",
      time: "En continu",
      body: "On surveille le système en production, on ajuste, on le fait évoluer avec votre activité.",
    },
  ];

  function HowItWorks() {
    return html`
      <section class="section" id="comment">
        <div class="wrap">
          <div class="section-head">
            <span class="eyebrow">Comment ça marche</span>
            <h2 class="section-title">De l'audit à la mise en production, en cinq semaines.</h2>
          </div>
          <div class="steps">
            ${STEPS.map(function (s, i) {
              return html`
                <div class="step" key=${i}>
                  <span class="step-num">${i + 1}</span>
                  <span class="step-time">${s.time}</span>
                  <h3>${s.title}</h3>
                  <p>${s.body}</p>
                </div>
              `;
            })}
          </div>
        </div>
      </section>
    `;
  }

  function Credibility() {
    return html`
      <section class="section" id="credibilite">
        <div class="wrap">
          <div class="plaque">
            <p class="plaque-text">
              <strong>2 ans+</strong> d'automatisation de processus métier (BPM) sur des projets internationaux, dont un grand groupe international. <strong>3 applications métier</strong> conçues, développées et livrées en autonomie.
            </p>
            <div class="plaque-meta">
              <div class="plaque-stat">
                <div class="num tabular">2+</div>
                <div class="label">Ans d'expérience BPM</div>
              </div>
              <div class="plaque-stat">
                <div class="num tabular">3</div>
                <div class="label">Apps métier livrées</div>
              </div>
            </div>
          </div>
        </div>
      </section>
    `;
  }

  function Waitlist(props) {
    var count = props.count;
    var onSubmitted = props.onSubmitted;
    var _s = useState({ email: "", nom: "", entreprise: "", process: "" });
    var form = _s[0], setForm = _s[1];
    var _e = useState(null);
    var error = _e[0], setError = _e[1];
    var _sub = useState(false);
    var submitting = _sub[0], setSubmitting = _sub[1];
    var _done = useState(false);
    var submitted = _done[0], setSubmitted = _done[1];

    function update(field) {
      return function (ev) {
        setForm(Object.assign({}, form, { [field]: ev.target.value }));
      };
    }

    function handleSubmit(ev) {
      ev.preventDefault();
      setError(null);

      if (!form.email || !form.nom || !form.entreprise || !form.process) {
        setError("Merci de remplir tous les champs avant d'envoyer.");
        return;
      }
      var emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email);
      if (!emailOk) {
        setError("Cette adresse email ne semble pas valide.");
        return;
      }

      setSubmitting(true);
      var store = getStorage();
      var record = {
        email: form.email,
        nom: form.nom,
        entreprise: form.entreprise,
        process: form.process,
        createdAt: new Date().toISOString(),
      };

      store
        .set("waitlist:" + Date.now(), JSON.stringify(record))
        .then(function () {
          setSubmitted(true);
          if (onSubmitted) onSubmitted();
        })
        .catch(function () {
          setError("Une erreur est survenue pendant l'inscription. Réessayez dans un instant.");
        })
        .finally(function () {
          setSubmitting(false);
        });
    }

    return html`
      <section class="section waitlist" id="waitlist">
        <div class="wrap">
          <div class="waitlist-panel">
            <div class="waitlist-intro">
              <span class="eyebrow">Liste d'attente</span>
              <h2>Soyez prévenu à l'ouverture des premières places.</h2>
              <p>
                On travaille avec un nombre limité de PME par cohorte pour garantir un
                déploiement soigné. Laissez vos coordonnées, on vous recontacte pour l'audit
                gratuit.
              </p>
              <div class="waitlist-count">
                <span class="num tabular">${count !== null ? String(count).padStart(3, "0") : "—"}</span>
                <span class="label">entreprises inscrites</span>
              </div>
            </div>

            ${submitted
              ? html`
                  <div class="confirm">
                    <span class="confirm-mark">✓</span>
                    <h3>Inscription enregistrée.</h3>
                    <p>Merci ${form.nom.split(" ")[0]}. On revient vers vous à ${form.email} pour caler l'audit gratuit de ${form.entreprise}.</p>
                    <span class="ref tabular">Référence : ${new Date().toISOString().slice(0, 10)}</span>
                  </div>
                `
              : html`
                  <form onSubmit=${handleSubmit}>
                    <div class="field-grid two">
                      <div class="field">
                        <label for="f-nom">Nom complet</label>
                        <input id="f-nom" type="text" placeholder="Nadia El Amrani" value=${form.nom} onInput=${update("nom")} />
                      </div>
                      <div class="field">
                        <label for="f-email">Email professionnel</label>
                        <input id="f-email" type="email" placeholder="nadia@entreprise.ma" value=${form.email} onInput=${update("email")} />
                      </div>
                    </div>
                    <div class="field-grid two" style=${{ marginTop: "1.1rem" }}>
                      <div class="field">
                        <label for="f-entreprise">Entreprise</label>
                        <input id="f-entreprise" type="text" placeholder="Nom de votre PME" value=${form.entreprise} onInput=${update("entreprise")} />
                      </div>
                      <div class="field">
                        <label for="f-process">Process le plus coûteux en temps</label>
                        <select id="f-process" value=${form.process} onChange=${update("process")}>
                          ${PROCESS_OPTIONS.map(function (o) {
                            return html`<option value=${o.value} key=${o.value}>${o.label}</option>`;
                          })}
                        </select>
                      </div>
                    </div>

                    ${error ? html`<p class="form-error" style=${{ marginTop: "1rem" }}>${error}</p>` : null}

                    <div style=${{ marginTop: "1.4rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      <button type="submit" class="stamp-btn block" disabled=${submitting}>
                        ${submitting ? "Envoi…" : "Rejoindre la liste d'attente"}
                      </button>
                      <span class="form-note">Pas de spam. Vos données servent uniquement à préparer votre audit.</span>
                    </div>
                  </form>
                `}
          </div>
        </div>
      </section>
    `;
  }

  function Footer() {
    return html`
      <footer class="site-footer">
        <div class="wrap">
          <div class="footer-brand">
            <span class="logo">OTOMAT<span class="dot">.</span></span>
            <p>Automatisation de process pour PME francophones. Rabat, Maroc.</p>
          </div>
          <nav class="footer-nav">
            <a href="#probleme">Le problème</a>
            <a href="#solutions">Solutions</a>
            <a href="#comment">Méthode</a>
            <a href="#waitlist">Liste d'attente</a>
          </nav>
        </div>
      </footer>
    `;
  }

  function App() {
    var _c = useState(null);
    var count = _c[0], setCount = _c[1];

    function refresh() {
      countWaitlist()
        .then(setCount)
        .catch(function () {
          setCount(null);
        });
    }

    useEffect(function () {
      refresh();
    }, []);

    return html`
      <div>
        <${Header} />
        <main>
          <${Hero} count=${count} />
          <${Problem} />
          <${Solutions} />
          <${HowItWorks} />
          <${Credibility} />
          <${Waitlist} count=${count} onSubmitted=${refresh} />
        </main>
        <${Footer} />
      </div>
    `;
  }

  var root = window.ReactDOM.createRoot(document.getElementById("root"));
  root.render(h(App));
})();
