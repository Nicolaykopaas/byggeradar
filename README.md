# Byggesaksradar

Lead-gen for håndverksbedrifter: varsler om nye byggetillatelser i deres område og bransje,
matchet mot håndverkere fra Brreg. Se [CLAUDE.md](CLAUDE.md) for arkitektur og regler.

## Status
Pilot: **Bergen kommune** (kommunenr 4601). Datakilde er verifisert og i bruk:

- `www.bergen.kommune.no/innsynplanogbyggesak/api/saker` er et åpent JSON-API som ligger til
  grunn for kommunens egen søkeside. robots.txt blokkerer kun `/api/fil/*` og `/api/saksgang` -
  selve søke-API-et er ikke omfattet og hentes derfor lovlig.
- Trondheim (`trondheim.innsynsportal.no`) og Oslo PBE (`innsyn.pbe.oslo.kommune.no`) har begge
  `robots.txt: Disallow: /` og er UTELUKKET som kilde (se regel om robots.txt i CLAUDE.md).
- eInnsyns offisielle API (api.einnsyn.no) er en push-API for at kommuner skal *levere* data inn,
  ikke en åpen lese-API for tredjeparter — krever Maskinporten/Altinn-tilgang. Vurderes for
  nasjonal skalering senere.
- API-et returnerer `tiltakshaver` (søkerens navn) - dette feltet leses ALDRI ut, se CLAUDE.md.

## Kom i gang
```bash
pip install -r requirements.txt

python brreg_fetch.py 4601        # hent håndverkere i Bergen (kommunenr 4601)
python byggesak_fetch.py 100      # hent de 100 sist innkomne byggesakene i Bergen
python compute_scores.py          # match saker mot bedrifter
python generate_email_drafts.py   # lag e-postutkast for topp-matcher

streamlit run app.py              # dashbord
```

## Pipeline
1. `brreg_fetch.py` — håndverkerbedrifter fra Brreg Enhetsregisteret (NACE 43.x)
2. `byggesak_fetch.py` — nye byggesaker fra Bergen kommunes saksinnsyn-API
3. `compute_scores.py` — matchscore sak↔bedrift
4. `generate_email_drafts.py` — e-postutkast (sendes manuelt, aldri automatisk)
5. `app.py` — Streamlit-dashbord for gjennomgang og oppfølging
