"""Liten CLI for aa administrere betalende kunder manuelt (data/kunder.csv).

    python sett_kunde.py legg-til --epost x@y.no --kommune 4601 --postnr 50 \
        --bransjer "Snekkerarbeid/tomrer" --minscore 60 --navn "Firma AS"
    python sett_kunde.py deaktiver --epost x@y.no
    python sett_kunde.py liste

Kun standardbiblioteket (argparse) + pandas via kunder.py. Norsk output.
"""
import argparse
import sys

from kunder import aktive_kunder, deaktiver_kunde, legg_til_kunde, les_kunder


def _cmd_legg_til(args) -> int:
    legg_til_kunde(
        epost=args.epost,
        kommunenummer=args.kommune,
        postnummer_prefiks=args.postnr,
        bransjer=args.bransjer,
        min_score=args.minscore,
        navn=args.navn,
        aktiv="ja",
    )
    print(f"OK: kunde {args.epost} lagt til / oppdatert.")
    _skriv_ut_kunde(args.epost)
    return 0


def _cmd_deaktiver(args) -> int:
    if deaktiver_kunde(args.epost):
        print(f"OK: kunde {args.epost} er deaktivert (aktiv=nei).")
        return 0
    print(f"Fant ingen kunde med e-post {args.epost}.")
    return 1


def _cmd_liste(_args) -> int:
    df = les_kunder()
    if df.empty:
        print("Ingen kunder registrert enna. Legg til med: python sett_kunde.py legg-til ...")
        return 0
    aktive = aktive_kunder()
    print(f"{len(df)} kunde(r) totalt, {len(aktive)} aktiv(e):\n")
    for _, r in df.iterrows():
        status = "AKTIV" if r["epost"] in set(aktive["epost"]) else "inaktiv"
        bransjer = r["bransjer"] or "(alle bransjer)"
        postnr = r["postnummer_prefiks"] or "(hele kommunen)"
        print(f"  [{status:7}] {r['epost']}  {r['navn']}")
        print(f"            kommune={r['kommunenummer'] or '-'}  postnr-prefiks={postnr}  "
              f"minscore={r['min_score'] or '0'}")
        print(f"            bransjer={bransjer}")
    return 0


def _skriv_ut_kunde(epost: str):
    df = les_kunder()
    rad = df[df["epost"].str.strip().str.lower() == (epost or "").strip().lower()]
    if not rad.empty:
        r = rad.iloc[0]
        print(f"    -> kommune={r['kommunenummer'] or '-'}, postnr-prefiks="
              f"{r['postnummer_prefiks'] or '(hele kommunen)'}, "
              f"bransjer={r['bransjer'] or '(alle)'}, minscore={r['min_score'] or '0'}")


def _bygg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Administrer betalende kunder for Byggesaksradar-leveransen.")
    under = parser.add_subparsers(dest="kommando", required=True)

    p_legg = under.add_parser("legg-til", help="Legg til eller oppdater en kunde")
    p_legg.add_argument("--epost", required=True, help="Kundens e-postadresse (unik nokkel)")
    p_legg.add_argument("--kommune", default="", help="Kommunenummer, f.eks. 4601")
    p_legg.add_argument("--postnr", default="",
                        help="Postnummer-prefiks, f.eks. 50 (tom = hele kommunen)")
    p_legg.add_argument("--bransjer", default="",
                        help='Semikolon-separert, f.eks. "Snekkerarbeid/tomrer;Takarbeid" '
                             "(tom = alle bransjer)")
    p_legg.add_argument("--minscore", default="0", help="Lavest tillatte matchscore 0-100")
    p_legg.add_argument("--navn", default="", help="Navn/firma for hilsen (valgfritt)")
    p_legg.set_defaults(func=_cmd_legg_til)

    p_de = under.add_parser("deaktiver", help="Deaktiver en kunde (aktiv=nei)")
    p_de.add_argument("--epost", required=True, help="Kundens e-postadresse")
    p_de.set_defaults(func=_cmd_deaktiver)

    p_liste = under.add_parser("liste", help="List opp alle kunder")
    p_liste.set_defaults(func=_cmd_liste)

    return parser


def main(argv=None) -> int:
    parser = _bygg_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
