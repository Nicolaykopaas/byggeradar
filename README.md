# Byggeradar

Kuratert, landsdekkende oversikt over nye byggetillatelser i norske kommuner, matchet mot
håndverksfag fra Brreg. Én kilde-adapter per kommune (`kilder/`), så flere kommuner legges til
uten å endre resten. Pilot kjører mot Bergen; grensesnittet er allerede flerkommune/landsdekkende.
Se [CLAUDE.md](CLAUDE.md) for arkitektur og regler.

## Produktdreining (viktig)

Første versjon prøvde å selge kalde «leads» (en offentlig adresse) for 99–100 kr. Testing viste
at det ikke skaper verdi: kilden har **ingen kontaktinfo vi lovlig kan gi videre** (tiltakshaver er
en privatperson, §/GDPR), jobben er ofte allerede kontrahert, og bare 6 % av bedriftene er lovlig
e-postbare. Vi solgte i praksis en betalingsmur foran offentlig info.

**Ny retning:** et *gratis, kuraterende verktøy* i stedet for en betalingsmur. Kjernen er
[radar.py](radar.py): den leser hver nye byggesak i hele Norge, kaster bort støyen, og løfter fram
de få prosjektene som er verdt tiden din – rangert på **mulighet** (ferskt + stort + treffer ditt
fag), med et **ærlig, lovlig handlingstips** per prosjekt. Store prosjekter merkes «kontaktbart
foretak» (der ansvarlig søkerforetak – en bedrift, ikke en privatperson – er offentlig i
saksdokumentene).

Åpne den:
```bash
python build_feed_html.py     # bygger + åpner feed/index.html (statisk, dobbeltklikkbar)
streamlit run finn_feed.py    # interaktiv «Din radar» med filtre på fag/geografi
```

### Filtre og lenke (begge visningene)

Både den statiske siden og Streamlit-appen har de samme filtrene, og alle filtrerer det faktiske
datasettet (ingen «døde» kontroller – dekket av `test_feed_filtre.py`):

- **Fag** – bare prosjekter som treffer ditt håndverksfag.
- **Fylke** og **Kommune** – geografi, «Hele Norge» som standard. Kommune-listen kaskaderer på valgt
  fylke. Filtrering skjer på `kommunenummer`/`fylke`; kommunenavn/fylke slås opp via
  `kilder.kommune_info()`, så datasettet trenger ikke egne navnekolonner.
- **Postnr**, **Kun trolig ledige** (privat søker), **Kun store prosjekter**, **Skjul tidlige/tatte**.

Hvert prosjektkort har en klikkbar **🔗 Se saken hos kommunen** som åpner kommunens egen offentlige
saksside (`kilde_url`, ny fane). Vår egen visning er postnr-anonymisert – full gateadresse skrives
aldri ut – men lenken til kommunens side er offentlig og alltid med.

Test at filtrene og lenken virker:
```bash
python test_feed_filtre.py    # 12 tester: hvert filter, ekte http(s)-lenke, ingen adresse-lekkasje
```

Monetisering kommer *etter* at verktøyet er nyttig nok til at folk bruker det: en billig
«vær først»-varsling (abonnement), ikke stykkpris. Valider først med 10 telefoner (34 % av
bedriftene har telefon i Brreg). Abonnement-/salgsmaskineriet under er beholdt, men er sekundært.

---

## Legacy: abonnement/salg (beholdt, men nedprioritert)

Lead-gen som abonnement (99 kr/mnd) på ukentlige leads. **Mål:** ~500 kr/mnd = 6 kunder.

---

## TL;DR – det eneste du MÅ gjøre selv

Alt det tekniske går av seg selv når det er satt opp. Du trenger bare å:

1. **Engangs (30 min):** legg inn nøkler i `.env`, hosт landingssiden, registrer den planlagte oppgaven. Se [Førstegangsoppsett](#førstegangsoppsett).
2. **Ukentlig (~10 min):** godkjenn og send salgs-e-postene. Se [Ukentlig rutine](#ukentlig-rutine-10-min).
3. **Ved varsel:** hvis du får en feilmelding (e-post/Windows-varsel), fiks det som står der.

Resten – skraping, matching, scoring, helsesjekk – er automatisk.

---

## Hva som går automatisk

| Når | Hva | Script |
|-----|-----|--------|
| Daglig 07:15 | Henter byggesaker + (ukentlig) bedrifter, matcher, scorer, lager utkast | `run_pipeline.py` |
| Daglig 07:15 | Selvtest – varsler deg på e-post/Windows hvis noe feilet | `selftest.py` |
| Mandag 08:00 | Helsesjekk – tester skraperne, teller leads/kunder, sender rapport | `helsesjekk.py` |

Feil logges til `logs/`. Ved feil får du varsel (hvis SMTP er satt opp i `.env`).

## De 2 tingene du gjør manuelt hver uke

1. **Godkjenn utsending** av salgs-e-poster (§15 gjør at *sending* alltid skal være en bevisst handling).
2. **Følg opp svar** fra bedrifter som er interessert, og registrer nye kunder.

---

## Førstegangsoppsett

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell: .venv\Scripts\Activate.ps1)
pip install -r requirements.txt
copy .env.example .env            # fyll inn dine verdier
```

### 1. Sett opp betaling (Stripe)
- Lag en gratis Stripe-konto. Enten:
  - lim `STRIPE_SECRET_KEY=sk_live_...` inn i `.env` og kjør `python stripe_setup.py`, **eller**
  - lag en Payment Link manuelt i Stripe-dashbordet (produkt 99 kr/mnd, gjentakende) og lim
    `STRIPE_PAYMENT_LINK=https://buy.stripe.com/...` inn i `.env`.

### 2. Publiser landingssiden (gratis)
```bash
python build_landing.py           # lager landing/index.html med lenke + eksempel-lead
```
Last `landing/index.html` opp gratis på f.eks.:
- **GitHub Pages** – legg fila i et repo, skru på Pages, eller
- **Netlify Drop** – dra og slipp `landing/`-mappa på app.netlify.com/drop.

Lim den ferdige URL-en inn som `LANDINGSSIDE_URL` i `.env` (brukes i salgs-e-postene).

### 3. Sett opp e-post (Gmail anbefalt)
Skru på 2-faktor på Gmail og lag et **app-passord** (16 tegn). Legg SMTP-verdiene i `.env`
(se `.env.example`). Dette gir både feilvarsler og utsending av salgs-e-poster.

### 4. Registrer den daglige jobben (Windows)
```powershell
powershell -ExecutionPolicy Bypass -File scheduler\register_task.ps1
```
Dette lager to planlagte oppgaver: daglig pipeline (07:15) og ukentlig helsesjekk (mandag 08:00).
Test med `Start-ScheduledTask -TaskName "Byggesaksradar"`.

*Linux/macOS:* bruk `scheduler/cron.txt` i stedet.

---

## Ukentlig rutine (~10 min)

```bash
python generate_email_drafts.py --utboks   # 1. lag ferske salgs-e-poster i data/utboks/
python approve_and_send.py --dry-run       # 2. les gjennom hva som vil bli sendt
python approve_and_send.py                 # 3. godkjenn og send (logger til kontaktet.csv)
```
- Kun **upersonlige** mottakere (`post@`, `firmapost@`, `kontakt@` …) tas med – personlige
  adresser filtreres bort automatisk (markedsføringsloven §15).
- Ingen bedrift kontaktes to ganger (`data/kontaktet.csv`).
- Sendte e-poster arkiveres i `data/sendt/`.

## Kunder og levering (produktet)

En betalende kunde får ukens nye, relevante byggesaker levert på e-post. Administrer kunder:
```bash
python sett_kunde.py legg-til --epost post@firma.no --kommune 4601 --bransjer "Snekkerarbeid/tømrer" --minscore 55
python sett_kunde.py liste
python sett_kunde.py deaktiver --epost post@firma.no
```
`data/kunder.csv`-skjema: `epost, navn, kommunenummer, postnummer_prefiks, bransjer, min_score, aktiv, opprettet`.
`bransjer` = semikolon-separert (tom = alle fag), `postnummer_prefiks` = f.eks. `52` (tom = hele kommunen —
anbefalt, siden mange saker mangler postnummer). Har du `STRIPE_SECRET_KEY` satt, beriker helsesjekken
kundetallet fra aktive Stripe-abonnement i tillegg.

Levering (schedulerbar, kjører automatisk mandag 08:30, eller manuelt):
```bash
python send_kunde_leads.py --dry-run   # skriv e-postene til data/kunde_utboks/ (send ingenting)
python send_kunde_leads.py             # send ukens leads, logg til data/kunde_sendt.csv
```
Ingen kunde får samme sak to ganger. Tomme uker hoppes over (ingen tom e-post). Dette er en samtykket
leveranse til betalende abonnenter, så full adresse er med (i motsetning til de kalde salgs-e-postene).

## Dashbord
```bash
streamlit run app.py
```

---

## Pipeline
1. `brreg_fetch.py` — håndverkerbedrifter fra Brreg Enhetsregisteret (NACE 43.x)
2. `byggesak_fetch.py` — nye byggesaker fra Bergen kommunes saksinnsyn-API
3. `compute_scores.py` — matchscore sak↔bedrift
4. `generate_email_drafts.py` — e-postutkast (`--utboks` for salgs-e-poster)
5. `approve_and_send.py` — sender godkjente salgs-e-poster via SMTP
6. `app.py` — Streamlit-dashbord

Orkestreres av `run_pipeline.py`; overvåkes av `selftest.py` og `helsesjekk.py`.

## Datakilde og robots.txt
- `www.bergen.kommune.no/innsynplanogbyggesak/api/saker` er et åpent JSON-API bak kommunens
  søkeside. robots.txt blokkerer kun `/api/fil/*` og `/api/saksgang` – søke-API-et er lovlig å hente.
- Trondheim (`trondheim.innsynsportal.no`) og Oslo PBE (`innsyn.pbe.oslo.kommune.no`) har begge
  `robots.txt: Disallow: /` og er UTELUKKET som kilde.
- API-et returnerer `tiltakshaver` (søkerens navn) – dette feltet leses ALDRI ut. Sakstitler som
  inneholder eksakt adresse anonymiseres før de brukes i e-post/landingsside (se `leads.py`).

## Personvern og lov
- Kun bedriftsdata fra Brreg lagres. Ingen personopplysninger fra byggesaker.
- Markedsføring kun til upersonlige virksomhetsadresser, med enkel avmelding i hver e-post (§15).
- Utsending skjer aldri automatisk – alltid via din godkjenning i `approve_and_send.py`.
