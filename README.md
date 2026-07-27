# Byggesaksradar

Lead-gen for håndverksbedrifter: varsler om nye byggetillatelser i deres område og bransje,
matchet mot håndverkere fra Brreg. Produktet selges som abonnement (99 kr/mnd) på ukentlige
leads. Se [CLAUDE.md](CLAUDE.md) for arkitektur og regler.

**Mål:** ~500 kr/mnd = 6 betalende kunder, med minst mulig manuelt arbeid.

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

Registrer nye betalende kunder i `data/kunder.csv` (kolonner: `epost,omrade,bransje,aktiv`),
eller la helsesjekken lese antallet direkte fra Stripe hvis `STRIPE_SECRET_KEY` er satt.

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
