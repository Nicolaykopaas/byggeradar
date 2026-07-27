"""Bygger feed/index.html - Byggeradar: et selvbetjent verktøy en håndverker kan åpne.

Kjør:  python build_feed_html.py   (åpner seg selv i nettleseren)

Håndverkeren velger sitt fag og område og ser umiddelbart om det er relevant arbeid.
Alt filtreres i nettleseren (vanilla JS) - ingen server, ingen innlogging. Ren statisk
fil som kan hostes gratis (GitHub Pages/Netlify) og deles med en lenke.

Postnr-anonymisert; full adresse vises aldri. Data fra data/saker.csv + data/matches.csv.
"""
import json
import os
import webbrowser
from datetime import date

from config import BASE_DIR
from feed import ferskhet_etikett
from radar import bygg_radar, ukesammendrag

UT = os.path.join(BASE_DIR, "feed", "index.html")


def _json_for_html(data) -> str:
    # Trygt å bygge inn i <script>: hindre at "</script>" bryter ut.
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def bygg() -> str:
    rader = bygg_radar()
    s = ukesammendrag(rader)

    # Slank JSON til klienten - kun det kortet trenger, alt postnr-anonymisert
    data = [{
        "sakstype": r["sakstype"], "omrade": r["omrade"], "bransjer": r["bransjer"],
        "skala": r["skala"], "skala_etikett": r["skala_etikett"],
        "naering": r["naeringsvennlig"], "mulighet": r["mulighet"],
        "status": r.get("status") or "", "fersk": ferskhet_etikett(r["dager_siden"]),
        "arbeid": r["arbeid"]["overskrift"], "oppgaver": r["arbeid"]["oppgaver"],
        "tilg_niva": r["tilgjengelighet"]["niva"],
        "tilg_etikett": r["tilgjengelighet"]["etikett"],
        "tilg_forklaring": r["tilgjengelighet"]["forklaring"],
        "tips": r["tips"],
    } for r in rader]

    fag = sorted({b for r in rader for b in r["bransjer"]})
    postnr = sorted({r["omrade"] for r in rader})

    doc = f"""<!doctype html>
<html lang="nb"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Byggeradar – finn relevant byggearbeid i Bergen</title>
<style>
  :root {{ --bla:#1d4ed8; --tekst:#0f172a; --grå:#64748b; --kant:#e2e8f0; --bg:#f1f5f9; --kort:#fff; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; color:var(--tekst); background:var(--bg); line-height:1.5; }}
  header {{ background:linear-gradient(135deg,#1d4ed8,#1e3a8a); color:#fff; padding:34px 20px 26px; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:0 20px; }}
  header h1 {{ font-size:1.9rem; }}
  header p {{ opacity:.95; margin-top:8px; max-width:640px; font-size:1.05rem; }}
  .filter {{ position:sticky; top:0; z-index:5; background:var(--kort); border-bottom:1px solid var(--kant);
             box-shadow:0 1px 4px rgba(0,0,0,.05); padding:14px 0; }}
  .filter .row {{ display:flex; flex-wrap:wrap; gap:12px; align-items:end; }}
  .felt {{ display:flex; flex-direction:column; gap:4px; }}
  .felt label {{ font-size:.78rem; color:var(--grå); font-weight:600; }}
  select, .sok {{ font-size:.95rem; padding:9px 12px; border:1px solid var(--kant); border-radius:9px;
                  background:var(--bg); color:var(--tekst); min-width:190px; }}
  .sjekk {{ display:flex; align-items:center; gap:6px; font-size:.9rem; color:#334155; padding-bottom:9px; }}
  .teller {{ margin-left:auto; font-weight:600; color:var(--bla); padding-bottom:9px; }}
  .forklar {{ color:var(--grå); font-size:.86rem; margin:14px 0 4px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; padding:14px 0 40px; }}
  .kort {{ background:var(--kort); border:1px solid var(--kant); border-radius:12px; padding:16px; display:flex; flex-direction:column; gap:10px; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
  .kort-topp {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
  .mulighet {{ background:#dbeafe; color:var(--bla); font-weight:700; border-radius:8px; padding:2px 10px; }}
  .skala {{ color:#fff; font-size:.74rem; font-weight:600; border-radius:999px; padding:2px 9px; }}
  .skala.stor {{ background:#166534; }} .skala.middels {{ background:#475569; }} .skala.liten {{ background:#94a3b8; }}
  .fersk {{ color:var(--grå); font-size:.8rem; margin-left:auto; }}
  .kort h3 {{ font-size:1.05rem; line-height:1.3; }}
  .meta {{ font-size:.9rem; color:#334155; }}
  .tags {{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; }}
  .tag {{ font-size:.74rem; font-weight:600; color:#fff; background:#475569; border-radius:999px; padding:2px 9px; }}
  .naering {{ font-size:.74rem; font-weight:600; color:#166534; background:#dcfce7; border-radius:999px; padding:2px 9px; }}
  .arbeid {{ font-size:.85rem; }}
  .arbeid-t {{ color:#334155; margin-bottom:4px; }}
  .arbeid ul {{ margin:0; padding-left:18px; color:var(--grå); columns:2; column-gap:16px; }}
  .arbeid li {{ font-size:.8rem; }}
  .tilg {{ font-size:.83rem; border-radius:8px; padding:8px 10px; margin-top:auto; }}
  .tilg-uavklart {{ background:#eff6ff; color:#1e3a8a; }}
  .tilg-tidlig {{ background:#fef9c3; color:#713f12; }}
  .tilg-tatt {{ background:#fee2e2; color:#7f1d1d; }}
  .tips {{ font-size:.86rem; color:#475569; background:#f8fafc; border-left:3px solid var(--bla); border-radius:0 6px 6px 0; padding:8px 10px; }}
  .tom {{ padding:48px 20px; text-align:center; color:var(--grå); }}
  footer {{ color:var(--grå); font-size:.82rem; padding:24px 20px 40px; text-align:center; }}
  @media (prefers-color-scheme:dark) {{
    :root {{ --tekst:#e2e8f0; --bg:#0f172a; --kort:#1e293b; --kant:#334155; --grå:#94a3b8; }}
    .mulighet {{ background:#1e3a8a; color:#bfdbfe; }} .meta {{ color:#cbd5e1; }}
    .arbeid-t {{ color:#cbd5e1; }}
    .tilg-uavklart {{ background:#0f2544; color:#bfdbfe; }}
    .tilg-tidlig {{ background:#422006; color:#fde68a; }}
    .tilg-tatt {{ background:#450a0a; color:#fecaca; }}
    .tips {{ background:#0f172a; color:#cbd5e1; }} .naering {{ background:#14532d; color:#bbf7d0; }}
  }}
</style></head>
<body>
  <header><div class="wrap">
    <h1>Byggeradar</h1>
    <p>Er det byggearbeid for deg i Bergen akkurat nå? Velg faget ditt, så ser du med én gang.
       Oppdateres daglig fra kommunens saksinnsyn.</p>
  </div></header>

  <div class="filter"><div class="wrap"><div class="row">
    <div class="felt"><label for="fag">Jeg jobber med</label>
      <select id="fag"><option value="">Alle fag</option>{"".join(f'<option>{f}</option>' for f in fag)}</select></div>
    <div class="felt"><label for="omrade">Område (postnr)</label>
      <select id="omrade"><option value="">Hele Bergen</option>{"".join(f'<option>{p}</option>' for p in postnr)}</select></div>
    <label class="sjekk"><input type="checkbox" id="kunStore"/> Kun store prosjekter</label>
    <label class="sjekk"><input type="checkbox" id="kunNaering"/> Kun kontaktbart foretak</label>
    <label class="sjekk"><input type="checkbox" id="skjulTatt" checked/> Skjul tidlige/trolig tatte</label>
    <span class="teller" id="teller"></span>
  </div></div></div>

  <main class="wrap">
    <div class="forklar">Høy «mulighet» = ferskt, stort og treffer ditt fag. Adresser er anonymisert til postnummer.
       <b>Ærlig om «ledig vs tatt»:</b> offentlig data kan ikke bekrefte om en jobb allerede har entreprenør –
       det står i saksdokumenter kommunen ikke gjør søkbare. Vi skjuler de vi <i>kan</i> se er tidlige eller
       ferdige, og merker resten «uavklart – sjekk saken». Vi lover aldri at en jobb er ledig.</div>
    <div class="grid" id="grid"></div>
    <div class="tom" id="tom" style="display:none"></div>
  </main>
  <footer>Byggeradar · data fra Bergen kommunes saksinnsyn + Brreg · generert {date.today().isoformat()} · ingen personopplysninger</footer>

<script>
const DATA = {_json_for_html(data)};
const esc = s => String(s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
const $ = id => document.getElementById(id);

function kort(r) {{
  const tags = r.bransjer.slice(0,4).map(b => `<span class="tag">${{esc(b)}}</span>`).join(" ");
  const naering = r.naering ? `<span class="naering">✓ Kontaktbart foretak</span>` : "";
  const status = r.status ? ` · ${{esc(r.status)}}` : "";
  const oppgaver = (r.oppgaver && r.oppgaver.length)
    ? `<div class="arbeid"><div class="arbeid-t">🛠️ Arbeid som inngår: <b>${{esc(r.arbeid)}}</b></div>
         <ul>${{r.oppgaver.map(o => `<li>${{esc(o)}}</li>`).join("")}}</ul></div>`
    : `<div class="arbeid"><div class="arbeid-t">${{esc(r.arbeid)}}</div></div>`;
  const tilg = `<div class="tilg tilg-${{r.tilg_niva}}"><b>${{esc(r.tilg_etikett)}}</b><br>${{esc(r.tilg_forklaring)}}</div>`;
  const tips = (r.tilg_niva === "uavklart") ? `<div class="tips">💡 ${{esc(r.tips)}}</div>` : "";
  return `<article class="kort">
    <div class="kort-topp">
      <span class="mulighet" title="Hvor verdt det er å følge opp (0-100)">${{r.mulighet}}</span>
      <span class="skala ${{r.skala}}">${{esc(r.skala_etikett)}}</span>
      <span class="fersk">${{esc(r.fersk)}}</span>
    </div>
    <h3>${{esc(r.sakstype)}}</h3>
    <div class="meta">📍 Postnr <strong>${{esc(r.omrade)}}</strong>${{status}}</div>
    <div class="tags">${{tags}} ${{naering}}</div>
    ${{oppgaver}}
    ${{tilg}}
    ${{tips}}
  </article>`;
}}

function tegn() {{
  const fag = $("fag").value, omrade = $("omrade").value;
  const kunStore = $("kunStore").checked, kunNaering = $("kunNaering").checked;
  const skjulTatt = $("skjulTatt").checked;
  const treff = DATA.filter(r =>
    (!fag || r.bransjer.includes(fag)) &&
    (!omrade || r.omrade === omrade) &&
    (!kunStore || r.skala === "stor") &&
    (!kunNaering || r.naering) &&
    (!skjulTatt || r.tilg_niva === "uavklart"));
  $("grid").innerHTML = treff.map(kort).join("");
  $("teller").textContent = treff.length + (treff.length === 1 ? " treff" : " treff");
  const tom = $("tom");
  if (treff.length === 0) {{
    tom.style.display = "block";
    tom.innerHTML = "Ingen relevante prosjekter" + (fag ? ` for <b>${{esc(fag)}}</b>` : "") +
      (omrade ? ` i postnr <b>${{esc(omrade)}}</b>` : "") +
      " akkurat nå.<br>Prøv et større område, eller kom tilbake i morgen – lista oppdateres daglig.";
  }} else {{ tom.style.display = "none"; }}
}}
["fag","omrade","kunStore","kunNaering","skjulTatt"].forEach(id => $(id).addEventListener("input", tegn));
tegn();
</script>
</body></html>"""

    os.makedirs(os.path.dirname(UT), exist_ok=True)
    with open(UT, "w", encoding="utf-8") as f:
        f.write(doc)
    return UT


if __name__ == "__main__":
    sti = bygg()
    print(f"Bygget Byggeradar-side: {sti}")
    webbrowser.open("file:///" + sti.replace("\\", "/"))
