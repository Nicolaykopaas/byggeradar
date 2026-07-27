"""Bygger feed/index.html - en statisk "Finn-for-byggetillatelser"-side du kan åpne.

Kjør:  python build_feed_html.py   (åpner seg selv i nettleseren)

Selvstendig HTML (all CSS inline), postnr-anonymisert. Full adresse vises ALDRI -
"Lås opp"-knappen er en prototype-CTA. Data hentes fra data/saker.csv + data/matches.csv.
"""
import html
import os
import webbrowser
from datetime import date

from config import BASE_DIR
from feed import bygg_feed_rader, ferskhet_etikett

UT = os.path.join(BASE_DIR, "feed", "index.html")

BRANSJE_FARGE = {
    "Snekkerarbeid/tømrer": "#b45309", "Elektroinstallasjon": "#1d4ed8",
    "Takarbeid": "#0f766e", "Gulvlegging/flislegging": "#7c3aed",
    "VVS og rørlegger": "#0891b2", "Malerarbeid": "#be185d",
}


def _kort(rad: dict) -> str:
    tags = "".join(
        f'<span class="tag" style="--f:{BRANSJE_FARGE.get(b, "#475569")}">{html.escape(b)}</span>'
        for b in rad["bransjer"][:4]
    )
    fersk = ferskhet_etikett(rad["dager_siden"])
    fersk_html = f'<span class="fersk">{html.escape(fersk)}</span>' if fersk else ""
    return f"""
    <article class="kort">
      <div class="kort-topp">
        <span class="score" title="Matchscore 0-100">{rad['score']}</span>
        {fersk_html}
      </div>
      <h3>{html.escape(rad['sakstype'])}</h3>
      <div class="omrade">🔒 Område: <strong>{html.escape(rad['omrade'])}</strong> <span class="skjult">· eksakt adresse skjult</span></div>
      <div class="tags">{tags}</div>
      <button class="laas" onclick="alert('Prototype: her ville full adresse + lenke til saken låses opp for 100 kr, eller inngå i abonnementet ditt.')">Lås opp full adresse – 100 kr</button>
    </article>"""


def bygg() -> str:
    rader = bygg_feed_rader()
    kort = "\n".join(_kort(r) for r in rader) if rader else \
        '<p class="tom">Ingen saker enda. Kjør <code>python run_pipeline.py</code> for å hente data.</p>'

    doc = f"""<!doctype html>
<html lang="nb"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Byggeradar – nye byggetillatelser i Bergen</title>
<style>
  :root {{ --bla:#1d4ed8; --tekst:#0f172a; --grå:#64748b; --kant:#e2e8f0; --bg:#f1f5f9; --kort:#fff; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; color:var(--tekst); background:var(--bg); line-height:1.5; }}
  header {{ background:linear-gradient(135deg,#1d4ed8,#1e3a8a); color:#fff; padding:32px 20px; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:0 20px; }}
  header h1 {{ font-size:1.7rem; }}
  header p {{ opacity:.92; margin-top:6px; max-width:620px; }}
  .banner {{ background:#fef9c3; border:1px solid #fde047; color:#713f12; border-radius:10px; padding:12px 16px; margin:20px auto; font-size:.92rem; max-width:1100px; }}
  .antall {{ color:var(--grå); font-size:.9rem; margin:18px 0 10px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:16px; padding-bottom:48px; }}
  .kort {{ background:var(--kort); border:1px solid var(--kant); border-radius:12px; padding:16px; display:flex; flex-direction:column; gap:10px; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
  .kort-topp {{ display:flex; align-items:center; gap:8px; }}
  .score {{ background:#dbeafe; color:var(--bla); font-weight:700; border-radius:8px; padding:2px 10px; font-size:.9rem; }}
  .fersk {{ color:var(--grå); font-size:.8rem; }}
  .kort h3 {{ font-size:1.02rem; line-height:1.3; }}
  .omrade {{ font-size:.9rem; color:#334155; }}
  .omrade .skjult {{ color:var(--grå); font-size:.82rem; }}
  .tags {{ display:flex; flex-wrap:wrap; gap:6px; }}
  .tag {{ font-size:.75rem; font-weight:600; color:#fff; background:var(--f); border-radius:999px; padding:2px 9px; }}
  .laas {{ margin-top:auto; background:var(--bla); color:#fff; border:0; border-radius:8px; padding:10px; font-weight:600; font-size:.9rem; cursor:pointer; }}
  .laas:hover {{ background:#1e40af; }}
  .tom {{ padding:40px; text-align:center; color:var(--grå); }}
  footer {{ color:var(--grå); font-size:.82rem; padding:24px 20px 40px; text-align:center; }}
  @media (prefers-color-scheme:dark) {{
    :root {{ --tekst:#e2e8f0; --bg:#0f172a; --kort:#1e293b; --kant:#334155; --grå:#94a3b8; }}
    .banner {{ background:#422006; border-color:#854d0e; color:#fde68a; }}
    .score {{ background:#1e3a8a; color:#bfdbfe; }}
    .omrade {{ color:#cbd5e1; }}
  }}
</style></head>
<body>
  <header><div class="wrap">
    <h1>Byggeradar</h1>
    <p>Nye byggetillatelser i Bergen – oppdatert daglig fra kommunens saksinnsyn. Se hva som skjer i ditt nabolag før konkurrentene.</p>
  </div></header>
  <div class="banner"><strong>Prototype.</strong> Adresser er anonymisert til postnummer. «Lås opp» er kun en demo – ingen betaling skjer. Formål: teste om håndverkere synes dette er verdt 100 kr.</div>
  <main class="wrap">
    <div class="antall">{len(rader)} ferske saker · sortert nyest først · generert {date.today().isoformat()}</div>
    <div class="grid">
      {kort}
    </div>
  </main>
  <footer>Byggeradar-prototype · data fra Bergen kommunes saksinnsyn + Brreg · ingen personopplysninger vises</footer>
</body></html>"""

    os.makedirs(os.path.dirname(UT), exist_ok=True)
    with open(UT, "w", encoding="utf-8") as f:
        f.write(doc)
    return UT


if __name__ == "__main__":
    sti = bygg()
    print(f"Bygget feed-side: {sti}")
    webbrowser.open("file:///" + sti.replace("\\", "/"))
