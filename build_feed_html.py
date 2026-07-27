"""Bygger feed/index.html - Byggeradar: en kuratert, ærlig oversikt du kan åpne.

Kjør:  python build_feed_html.py   (åpner seg selv i nettleseren)

Selvstendig HTML (all CSS inline). Viser IKKE en betalingsmur foran offentlig info -
i stedet kuraterer den bort støyen og sier ærlig hvordan du kan følge opp lovlig.
Postnr-anonymisert; full adresse vises aldri. Data fra data/saker.csv + data/matches.csv.
"""
import html
import os
import webbrowser
from datetime import date

from config import BASE_DIR
from feed import ferskhet_etikett
from radar import bygg_radar, ukesammendrag

UT = os.path.join(BASE_DIR, "feed", "index.html")

BRANSJE_FARGE = {
    "Snekkerarbeid/tømrer": "#b45309", "Elektroinstallasjon": "#1d4ed8",
    "Takarbeid": "#0f766e", "Gulvlegging/flislegging": "#7c3aed",
    "VVS og rørlegger": "#0891b2", "Malerarbeid": "#be185d",
}
SKALA_FARGE = {"stor": "#166534", "middels": "#475569", "liten": "#94a3b8"}


def _kort(r: dict) -> str:
    tags = "".join(
        f'<span class="tag" style="--f:{BRANSJE_FARGE.get(b, "#475569")}">{html.escape(b)}</span>'
        for b in r["bransjer"][:4]
    )
    fersk = ferskhet_etikett(r["dager_siden"])
    status = html.escape(r["status"]) if r.get("status") else ""
    naering = ('<span class="naering">✓ Kontaktbart foretak</span>' if r["naeringsvennlig"] else "")
    return f"""
    <article class="kort">
      <div class="kort-topp">
        <span class="mulighet" title="Hvor verdt det er å følge opp (0-100)">{r['mulighet']}</span>
        <span class="skala" style="--s:{SKALA_FARGE[r['skala']]}">{html.escape(r['skala_etikett'])}</span>
        <span class="fersk">{html.escape(fersk)}</span>
      </div>
      <h3>{html.escape(r['sakstype'])}</h3>
      <div class="meta">📍 Postnr <strong>{html.escape(r['omrade'])}</strong>{f' · {status}' if status else ''}</div>
      <div class="tags">{tags} {naering}</div>
      <div class="tips">💡 {html.escape(r['tips'])}</div>
    </article>"""


def bygg() -> str:
    rader = bygg_radar()
    s = ukesammendrag(rader)
    kort = "\n".join(_kort(r) for r in rader) if rader else \
        '<p class="tom">Ingen prosjekter enda. Kjør <code>python run_pipeline.py</code> for å hente data.</p>'

    doc = f"""<!doctype html>
<html lang="nb"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Byggeradar – hvor det bygges i Bergen</title>
<style>
  :root {{ --bla:#1d4ed8; --tekst:#0f172a; --grå:#64748b; --kant:#e2e8f0; --bg:#f1f5f9; --kort:#fff; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; color:var(--tekst); background:var(--bg); line-height:1.5; }}
  header {{ background:linear-gradient(135deg,#1d4ed8,#1e3a8a); color:#fff; padding:36px 20px; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:0 20px; }}
  header h1 {{ font-size:1.9rem; }}
  header p {{ opacity:.95; margin-top:8px; max-width:640px; font-size:1.05rem; }}
  .stats {{ display:flex; flex-wrap:wrap; gap:14px; max-width:1100px; margin:22px auto 6px; }}
  .stat {{ background:var(--kort); border:1px solid var(--kant); border-radius:12px; padding:12px 18px; flex:1; min-width:130px; }}
  .stat .n {{ font-size:1.6rem; font-weight:700; color:var(--bla); }}
  .stat .l {{ font-size:.82rem; color:var(--grå); }}
  .forklar {{ color:var(--grå); font-size:.9rem; margin:16px 0 10px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; padding-bottom:40px; }}
  .kort {{ background:var(--kort); border:1px solid var(--kant); border-radius:12px; padding:16px; display:flex; flex-direction:column; gap:10px; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
  .kort-topp {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
  .mulighet {{ background:#dbeafe; color:var(--bla); font-weight:700; border-radius:8px; padding:2px 10px; }}
  .skala {{ color:#fff; background:var(--s); font-size:.74rem; font-weight:600; border-radius:999px; padding:2px 9px; }}
  .fersk {{ color:var(--grå); font-size:.8rem; margin-left:auto; }}
  .kort h3 {{ font-size:1.05rem; line-height:1.3; }}
  .meta {{ font-size:.9rem; color:#334155; }}
  .tags {{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; }}
  .tag {{ font-size:.74rem; font-weight:600; color:#fff; background:var(--f); border-radius:999px; padding:2px 9px; }}
  .naering {{ font-size:.74rem; font-weight:600; color:#166534; background:#dcfce7; border-radius:999px; padding:2px 9px; }}
  .tips {{ font-size:.86rem; color:#475569; background:#f8fafc; border-left:3px solid var(--bla); border-radius:0 6px 6px 0; padding:8px 10px; margin-top:auto; }}
  .cta {{ background:#0f172a; color:#fff; border-radius:14px; padding:24px; margin:8px auto 40px; text-align:center; }}
  .cta h2 {{ font-size:1.3rem; }} .cta p {{ opacity:.85; margin:8px 0 0; }}
  .tom {{ padding:40px; text-align:center; color:var(--grå); }}
  footer {{ color:var(--grå); font-size:.82rem; padding:24px 20px 40px; text-align:center; }}
  @media (prefers-color-scheme:dark) {{
    :root {{ --tekst:#e2e8f0; --bg:#0f172a; --kort:#1e293b; --kant:#334155; --grå:#94a3b8; }}
    .mulighet {{ background:#1e3a8a; color:#bfdbfe; }} .meta {{ color:#cbd5e1; }}
    .tips {{ background:#0f172a; color:#cbd5e1; }} .naering {{ background:#14532d; color:#bbf7d0; }}
  }}
</style></head>
<body>
  <header><div class="wrap">
    <h1>Byggeradar</h1>
    <p>Vi leser hver nye byggesak i Bergen så du slipper. Her er prosjektene som faktisk er verdt tiden din –
       sortert etter mulighet, med et ærlig tips om hvordan du følger opp lovlig.</p>
  </div></header>

  <div class="wrap">
    <div class="stats">
      <div class="stat"><div class="n">{s['totalt']}</div><div class="l">aktuelle prosjekter</div></div>
      <div class="stat"><div class="n">{s['ferske_7d']}</div><div class="l">nye siste 7 dager</div></div>
      <div class="stat"><div class="n">{s['store']}</div><div class="l">store prosjekter</div></div>
      <div class="stat"><div class="n">{s['naeringsvennlige']}</div><div class="l">med kontaktbart foretak</div></div>
    </div>
    <div class="forklar">Høy «mulighet» = ferskt, stort og treffer ditt fag. Adresser er anonymisert til
       postnummer; ingen personopplysninger vises. Grønn merkelapp = større prosjekt der ansvarlig foretak
       (en bedrift) er offentlig i saksdokumentene og lovlig å kontakte.</div>

    <div class="grid">
      {kort}
    </div>

    <div class="cta">
      <h2>Vil du ha din radar hver mandag?</h2>
      <p>Velg fag og område, så sender vi deg ukens nye prosjekter – gratis å komme i gang.</p>
    </div>
  </div>
  <footer>Byggeradar · data fra Bergen kommunes saksinnsyn + Brreg · generert {date.today().isoformat()} · ingen personopplysninger</footer>
</body></html>"""

    os.makedirs(os.path.dirname(UT), exist_ok=True)
    with open(UT, "w", encoding="utf-8") as f:
        f.write(doc)
    return UT


if __name__ == "__main__":
    sti = bygg()
    print(f"Bygget Byggeradar-side: {sti}")
    webbrowser.open("file:///" + sti.replace("\\", "/"))
