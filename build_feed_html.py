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

from config import BASE_DIR, env
from feed import ferskhet_etikett
from radar import bygg_radar, ukesammendrag

UT = os.path.join(BASE_DIR, "feed", "index.html")


def _json_for_html(data) -> str:
    # Trygt å bygge inn i <script>: hindre at "</script>" bryter ut.
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def bygg() -> str:
    rader = bygg_radar()
    s = ukesammendrag(rader)

    # Slank JSON til klienten - kun det kortet trenger, vår visning postnr-anonymisert.
    # kilde_url er kommunens egen OFFENTLIGE saksside og er trygg å eksponere.
    def _url(u):
        u = str(u or "")
        return u if u.startswith("http://") or u.startswith("https://") else ""

    data = [{
        "sakstype": r["sakstype"], "omrade": r["omrade"], "bransjer": r["bransjer"],
        "kommunenummer": r.get("kommunenummer") or "", "kommunenavn": r.get("kommunenavn") or "",
        "fylke": r.get("fylke") or "", "postnummer": r.get("postnummer") or "",
        "skala": r["skala"], "skala_etikett": r["skala_etikett"],
        "naering": r["naeringsvennlig"], "mulighet": r["mulighet"],
        "status": r.get("status") or "", "fersk": ferskhet_etikett(r["dager_siden"]),
        "arbeid": r["arbeid"]["overskrift"], "oppgaver": r["arbeid"]["oppgaver"],
        "tilg_niva": r["tilgjengelighet"]["niva"],
        "tilg_etikett": r["tilgjengelighet"]["etikett"],
        "tilg_forklaring": r["tilgjengelighet"]["forklaring"],
        "trolig_ledig": r.get("profesjonell_soker") is False,
        "kilde_url": _url(r.get("kilde_url")),
        "tips": r["tips"],
    } for r in rader]

    fag = sorted({b for r in rader for b in r["bransjer"]})
    postnr = sorted({r.get("postnummer") for r in rader if r.get("postnummer")})
    fylker = sorted({r.get("fylke") for r in rader if r.get("fylke")})
    # Kommuner som (nummer, navn, fylke) - navn vises, nummer er verdien vi filtrerer på
    kommuner = sorted(
        {(r.get("kommunenummer"), r.get("kommunenavn"), r.get("fylke"))
         for r in rader if r.get("kommunenummer") and r.get("kommunenavn")},
        key=lambda t: (t[2] or "", t[1] or ""),
    )
    kommuner_json = [{"nr": k[0], "navn": k[1], "fylke": k[2]} for k in kommuner]
    kontakt = env("KONTAKT_EPOST") or env("VARSEL_TIL") or env("SMTP_FRA") or "din-epost@eksempel.no"

    doc = f"""<!doctype html>
<html lang="nb"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Byggeradar – nye byggetillatelser i hele Norge</title>
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
  .naering {{ font-size:.74rem; font-weight:600; color:#475569; background:#e2e8f0; border-radius:999px; padding:2px 9px; }}
  .ledig {{ font-size:.74rem; font-weight:700; color:#166534; background:#dcfce7; border-radius:999px; padding:2px 9px; }}
  .arbeid {{ font-size:.85rem; }}
  .arbeid-t {{ color:#334155; margin-bottom:4px; }}
  .arbeid ul {{ margin:0; padding-left:18px; color:var(--grå); columns:2; column-gap:16px; }}
  .arbeid li {{ font-size:.8rem; }}
  .tilg {{ font-size:.83rem; border-radius:8px; padding:8px 10px; margin-top:auto; }}
  .tilg-uavklart {{ background:#eff6ff; color:#1e3a8a; }}
  .tilg-tidlig {{ background:#fef9c3; color:#713f12; }}
  .tilg-tatt {{ background:#fee2e2; color:#7f1d1d; }}
  .tips {{ font-size:.86rem; color:#475569; background:#f8fafc; border-left:3px solid var(--bla); border-radius:0 6px 6px 0; padding:8px 10px; }}
  .lenke {{ display:inline-flex; align-items:center; gap:6px; font-size:.88rem; font-weight:600; color:var(--bla);
            text-decoration:none; background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:8px 12px; align-self:flex-start; }}
  .lenke:hover {{ background:#dbeafe; }}
  .cta {{ background:#0f172a; color:#fff; border-radius:14px; padding:26px; margin:12px 0 40px; text-align:center; }}
  .cta h2 {{ font-size:1.3rem; }} .cta p {{ opacity:.85; margin:8px 0 16px; }}
  .knapp {{ display:inline-block; background:var(--bla); color:#fff; text-decoration:none; font-weight:600; padding:12px 28px; border-radius:9px; }}
  .knapp:hover {{ background:#1e40af; }}
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
    .lenke {{ background:#0f2544; border-color:#1e3a8a; color:#bfdbfe; }}
    .lenke:hover {{ background:#12326b; }}
  }}
</style></head>
<body>
  <header><div class="wrap">
    <h1>Byggeradar</h1>
    <p>Nye byggetillatelser i hele Norge – samlet på ett sted. Velg faget ditt og hvor du
       jobber, så ser du med én gang om det er relevant arbeid. Hvert kort lenker rett til
       saken hos kommunen. Oppdateres daglig fra kommunenes saksinnsyn.</p>
  </div></header>

  <div class="filter"><div class="wrap"><div class="row">
    <div class="felt"><label for="fag">Jeg jobber med</label>
      <select id="fag"><option value="">Alle fag</option>{"".join(f'<option>{f}</option>' for f in fag)}</select></div>
    <div class="felt"><label for="fylke">Fylke</label>
      <select id="fylke"><option value="">Hele Norge</option>{"".join(f'<option>{f}</option>' for f in fylker)}</select></div>
    <div class="felt"><label for="kommune">Kommune</label>
      <select id="kommune"><option value="">Alle kommuner</option></select></div>
    <div class="felt"><label for="postnr">Postnr</label>
      <select id="postnr"><option value="">Alle postnr</option>{"".join(f'<option>{p}</option>' for p in postnr)}</select></div>
    <label class="sjekk"><input type="checkbox" id="kunLedig"/> Kun trolig ledige (privat søker)</label>
    <label class="sjekk"><input type="checkbox" id="kunStore"/> Kun store prosjekter</label>
    <label class="sjekk"><input type="checkbox" id="skjulTatt" checked/> Skjul tidlige/trolig tatte</label>
    <span class="teller" id="teller"></span>
  </div></div></div>

  <main class="wrap">
    <div class="forklar">Høy «mulighet» = ferskt, stort og treffer ditt fag. Vår visning er anonymisert til postnummer –
       men hvert kort lenker rett til saken hos kommunen, der du ser alt det offentlige.
       <b>Ærlig om «ledig vs tatt»:</b> offentlig data kan ikke bekrefte om en jobb allerede har entreprenør –
       det står i saksdokumenter kommunen ikke gjør søkbare. Vi skjuler de vi <i>kan</i> se er tidlige eller
       ferdige, og merker resten «uavklart – sjekk saken». Vi lover aldri at en jobb er ledig.</div>
    <div class="grid" id="grid"></div>
    <div class="tom" id="tom" style="display:none"></div>

    <div class="cta">
      <h2>Vil du ha disse rett i innboksen hver mandag?</h2>
      <p>Gratis å komme i gang. Velg faget ditt over, så tar vi det med i påmeldingen.</p>
      <a id="paameld" class="knapp" href="mailto:{kontakt}?subject=Byggeradar%20varsel">Meld meg på varsel</a>
    </div>
  </main>
  <footer>Byggeradar · data fra norske kommuners saksinnsyn + Brreg · generert {date.today().isoformat()} · ingen personopplysninger</footer>

<script>
const DATA = {_json_for_html(data)};
const KOMMUNER = {_json_for_html(kommuner_json)};
const KONTAKT = {_json_for_html(kontakt)};
const esc = s => String(s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
const $ = id => document.getElementById(id);

function kort(r) {{
  const tags = r.bransjer.slice(0,4).map(b => `<span class="tag">${{esc(b)}}</span>`).join(" ");
  // Vis ledig/proff-merket KUN når tilgjengelighet er "uavklart", så merket aldri
  // motsier tilgjengelighets-boksen (tatt/tidlig får ikke ledig-merke).
  const badge = (r.tilg_niva === "uavklart")
    ? (r.trolig_ledig ? `<span class="ledig">👤 Trolig ledig – privat søker</span>`
                      : (r.naering ? `<span class="naering">🏢 Proff søker inne</span>` : ""))
    : "";
  const status = r.status ? ` · ${{esc(r.status)}}` : "";
  const sted = r.kommunenavn ? `${{esc(r.kommunenavn)}} · Postnr <strong>${{esc(r.omrade)}}</strong>`
                             : `Postnr <strong>${{esc(r.omrade)}}</strong>`;
  const oppgaver = (r.oppgaver && r.oppgaver.length)
    ? `<div class="arbeid"><div class="arbeid-t">🛠️ Arbeid som inngår: <b>${{esc(r.arbeid)}}</b></div>
         <ul>${{r.oppgaver.map(o => `<li>${{esc(o)}}</li>`).join("")}}</ul></div>`
    : `<div class="arbeid"><div class="arbeid-t">${{esc(r.arbeid)}}</div></div>`;
  const tilg = `<div class="tilg tilg-${{r.tilg_niva}}"><b>${{esc(r.tilg_etikett)}}</b><br>${{esc(r.tilg_forklaring)}}</div>`;
  const tips = (r.tilg_niva === "uavklart") ? `<div class="tips">💡 ${{esc(r.tips)}}</div>` : "";
  const lenke = r.kilde_url
    ? `<a class="lenke" href="${{esc(r.kilde_url)}}" target="_blank" rel="noopener">🔗 Se saken hos kommunen</a>`
    : "";
  return `<article class="kort">
    <div class="kort-topp">
      <span class="mulighet" title="Hvor verdt det er å følge opp (0-100)">${{r.mulighet}}</span>
      <span class="skala ${{r.skala}}">${{esc(r.skala_etikett)}}</span>
      <span class="fersk">${{esc(r.fersk)}}</span>
    </div>
    <h3>${{esc(r.sakstype)}}</h3>
    <div class="meta">📍 ${{sted}}${{status}}</div>
    <div class="tags">${{tags}} ${{badge}}</div>
    ${{oppgaver}}
    ${{tilg}}
    ${{tips}}
    ${{lenke}}
  </article>`;
}}

// Kommune-nedtrekket kaskaderer på valgt fylke (viser bare kommuner i fylket).
function fyllKommuner() {{
  const fylke = $("fylke").value;
  const valgt = $("kommune").value;
  const rel = KOMMUNER.filter(k => !fylke || k.fylke === fylke);
  const finnes = rel.some(k => k.nr === valgt);
  $("kommune").innerHTML = `<option value="">Alle kommuner</option>` +
    rel.map(k => `<option value="${{esc(k.nr)}}"${{k.nr === valgt && finnes ? " selected" : ""}}>${{esc(k.navn)}}</option>`).join("");
  if (!finnes) $("kommune").value = "";
}}

function tegn() {{
  const fag = $("fag").value, fylke = $("fylke").value;
  const kommune = $("kommune").value, postnr = $("postnr").value;
  const kunStore = $("kunStore").checked, kunLedig = $("kunLedig").checked;
  const skjulTatt = $("skjulTatt").checked;
  const treff = DATA.filter(r =>
    (!fag || r.bransjer.includes(fag)) &&
    (!fylke || r.fylke === fylke) &&
    (!kommune || r.kommunenummer === kommune) &&
    (!postnr || r.postnummer === postnr) &&
    (!kunStore || r.skala === "stor") &&
    (!kunLedig || r.trolig_ledig) &&
    (!skjulTatt || r.tilg_niva === "uavklart"));
  $("grid").innerHTML = treff.map(kort).join("");
  $("teller").textContent = treff.length + " treff";
  const tom = $("tom");
  const komNavn = kommune ? (KOMMUNER.find(k => k.nr === kommune) || {{}}).navn : "";
  const sted = komNavn || fylke || "hele Norge";
  if (treff.length === 0) {{
    tom.style.display = "block";
    tom.innerHTML = "Ingen relevante prosjekter" + (fag ? ` for <b>${{esc(fag)}}</b>` : "") +
      ` i <b>${{esc(sted)}}</b>` + (postnr ? ` (postnr ${{esc(postnr)}})` : "") +
      " akkurat nå.<br>Prøv et større område, eller kom tilbake i morgen – lista oppdateres daglig.";
  }} else {{ tom.style.display = "none"; }}

  // Prefyll påmeldings-mailen med valgt fag/område
  const fagTekst = fag || "alle fag";
  const omr = " i " + sted + (postnr ? (", postnr " + postnr) : "");
  const emne = encodeURIComponent("Byggeradar varsel: " + fagTekst);
  const body = encodeURIComponent("Hei! Jeg vil ha ukentlig varsel om nye byggesaker for "
    + fagTekst + omr + ".\\n\\nBedrift/navn:\\nTelefon:");
  $("paameld").href = `mailto:${{KONTAKT}}?subject=${{emne}}&body=${{body}}`;
}}

$("fylke").addEventListener("input", () => {{ fyllKommuner(); tegn(); }});
["fag","kommune","postnr","kunStore","kunLedig","skjulTatt"].forEach(id => $(id).addEventListener("input", tegn));
fyllKommuner();
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
