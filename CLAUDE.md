# Byggesaksradar

Lead-gen: skraper kommunale byggesaker og matcher mot håndverkere fra Brreg.
Spin-off av anbudsradar-konseptet — samme mønster: gratis smakebit-lead på e-post, abonnement for løpende varsler.

## Arkitektur
- `byggesak_fetch.py` — henter nye byggetillatelser fra Bergen kommunes åpne saksinnsyn-API (`/innsynplanogbyggesak/api/saker`). Output: `data/saker.csv`
- `brreg_fetch.py` — henter håndverkerbedrifter fra Brreg Enhetsregisteret API. Filtrer NACE 43.x + kommune/fylke. Output: `data/bedrifter.csv`
- `compute_scores.py` — matchscore 0-100 per sak-bedrift-par: bransjematch (sakstype→NACE via tabell), geografisk nærhet, bedriftsstørrelse. Output: `data/matches.csv`
- `generate_email_drafts.py` — ett utkast per topp-match. Kort, konkret, nevner adresse og sakstype. Output: `data/email_drafts/`
- `app.py` — Streamlit-dashbord: filtrer, se score, marker som kontaktet
- `data/kontaktet.csv` — logg. Aldri kontakt samme bedrift to ganger

## Regler
- Alt skal være gratis å drifte. Ingen betalte API-er eller hosting
- Kun pandas + streamlit + requests. Ingen database, CSV er nok
- ALDRI lagre personopplysninger fra byggesaker (tiltakshavers navn/adresse som privatperson). Kun bedriftsdata fra Brreg
- Utsending er manuell — scriptet lager utkast, sender aldri selv
- Rate-limit alle kall mot kommunale sider, respekter robots.txt
- Norsk i all output mot bruker (e-poster, dashbord)

## Status
Pilot kjører mot Bergen kommune (kommunenr 4601). Se README.md for detaljer om datakilde og robots.txt-vurdering.
