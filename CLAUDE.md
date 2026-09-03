# Byggesaksradar

Lead-gen: skraper kommunale byggesaker og matcher mot håndverkere fra Brreg.
Spin-off av anbudsradar-konseptet, samme mønster: gratis smakebit-lead på e-post, abonnement for løpende varsler.

## Arkitektur
- `byggesak_fetch.py`, henter nye byggetillatelser fra Bergen kommunes åpne saksinnsyn-API (`/innsynplanogbyggesak/api/saker`). Output: `data/saker.csv`
- `brreg_fetch.py`, henter håndverkerbedrifter fra Brreg Enhetsregisteret API. Filtrer NACE 43.x + kommune/fylke. Output: `data/bedrifter.csv`
- `compute_scores.py`, matchscore 0-100 per sak-bedrift-par: bransjematch (sakstype→NACE via tabell), geografisk nærhet, bedriftsstørrelse. Output: `data/matches.csv`
- `generate_email_drafts.py`, ett utkast per topp-match. Kort, konkret, nevner adresse og sakstype. Output: `data/email_drafts/`
- `app.py`, Streamlit-dashbord: filtrer, se score, marker som kontaktet
- `data/kontaktet.csv`, logg. Aldri kontakt samme bedrift to ganger

### Drift, salg og vedlikehold
- `run_pipeline.py`, orkestrerer hele pipelinen (Brreg→saker→scoring→utkast). Kjøres daglig av Task Scheduler (`scheduler/`). Skriver `data/pipeline_status.json`.
- `selftest.py`, verifiserer siste kjøring og varsler ved feil (`varsling.py`: e-post + Windows-notif).
- `stripe_setup.py`, lager Stripe Payment Link (99 kr/mnd) via `requests`. `build_landing.py` + `landing/`, statisk landingsside.
- `generate_email_drafts.py --utboks`, skreddersydde salgs-e-poster til `data/utboks/`, kun upersonlige adresser (§15). `approve_and_send.py`, godkjenn+send via SMTP.
- `helsesjekk.py`, ukentlig: tester skraperne, teller leads/kunder, rapporterer. `config.py`/`logg.py`/`leads.py`, felles hjelpere.
- `kunder.py` + `sett_kunde.py`, kunderegister (`data/kunder.csv`, valgfri Stripe-sync). `send_kunde_leads.py`, ukentlig levering av leads til betalende kunder (område/fag/score-filtrert, dedupe via `data/kunde_sendt.csv`). Schedulert mandag 08:30.
- Matching: `compute_scores.py` mapper sakstype→NACE (fler-bransje), score vekter bransje-spesifisitet/geografi/ferskhet/størrelse. `byggesak_fetch.py`/`brreg_fetch.py` har retry m/backoff. Kun ekte `BYGG-`-saker beholdes. Tester i `tests/`.
- **Produktdreining (Byggeradar):** `feed.py` (postnr-anonymiserte rader) + `radar.py` (kuratering: prosjektskala, mulighetsscore, ærlig §15-tips, «kontaktbart foretak» for store prosjekter). Vises via `build_feed_html.py` (statisk feed/index.html) og `finn_feed.py` (Streamlit «Din radar»). Verdi = kuratering + timing + ærlighet, IKKE en betalingsmur. radar.py leser aldri tiltakshaver - skala utledes kun fra offentlig arbeidsbeskrivelse. Se README «Produktdreining».

## Regler
- Alt skal være gratis å drifte. Ingen betalte API-er eller hosting
- Kun pandas + streamlit + requests. Ingen database, CSV er nok
- ALDRI lagre personopplysninger fra byggesaker (tiltakshavers navn/adresse som privatperson). Kun bedriftsdata fra Brreg
- Utsending er manuell, scriptet lager utkast, sender aldri selv
- Rate-limit alle kall mot kommunale sider, respekter robots.txt
- Norsk i all output mot bruker (e-poster, dashbord)

## Status
Pilot kjører mot Bergen kommune (kommunenr 4601). Se README.md for detaljer om datakilde og robots.txt-vurdering.
