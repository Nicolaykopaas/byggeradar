# Byggesaksradar

Lead-gen for håndverksbedrifter: varsler om nye byggetillatelser i deres område og bransje,
matchet mot håndverkere fra Brreg. Se [CLAUDE.md](CLAUDE.md) for arkitektur og regler.

## Status
Pilot: datakilde for byggesaker under research.

- eInnsyns offisielle API (api.einnsyn.no) er en push-API for at kommuner skal *levere* data inn,
  ikke en åpen lese-API for tredjeparter — krever Maskinporten/Altinn-tilgang.
- Trondheim (`trondheim.innsynsportal.no`) og Oslo PBE (`innsyn.pbe.oslo.kommune.no`) har begge
  `robots.txt: Disallow: /` og er derfor UTELUKKET som kilde (se regel om robots.txt i CLAUDE.md).
- Leter etter en kommune med åpen postliste/RSS for byggesaker der robots.txt tillater henting.

## Kom i gang
```bash
pip install -r requirements.txt

python brreg_fetch.py 5001        # hent håndverkere i Trondheim (kommunenr 5001)
python byggesak_fetch.py 5001     # hent nye byggesaker
python compute_scores.py          # match saker mot bedrifter
python generate_email_drafts.py   # lag e-postutkast for topp-matcher

streamlit run app.py              # dashbord
```

## Pipeline
1. `brreg_fetch.py` — håndverkerbedrifter fra Brreg Enhetsregisteret (NACE 43.x)
2. `byggesak_fetch.py` — nye byggesaker fra kommunen
3. `compute_scores.py` — matchscore sak↔bedrift
4. `generate_email_drafts.py` — e-postutkast (sendes manuelt, aldri automatisk)
5. `app.py` — Streamlit-dashbord for gjennomgang og oppfølging
