"""Gjør en byggesakstittel om til konkret arbeid: hvilke oppgaver tillatelsen innebærer.

Kilden (Bergen) publiserer arbeidet KUN i sakstittelen (f.eks. "tilbygg og
fasadeendring mm") - detaljerte saksdokumenter er blokkert av robots.txt. Dette
laget oversetter de gjenkjennelige tiltakene i tittelen til en klar liste over
typiske arbeidsoppgaver + relevante fag, så håndverkeren vet hva jobben går ut på.

Rent regelbasert på offentlig tittel - ingen personopplysninger, ingen scraping av
blokkerte endepunkt. Oppgavene er "typisk innhold", ikke garantert omfang.
"""
import re

# Hvert tiltak: nøkkelord (regex, \b-grense) -> beskrivelse + typiske oppgaver + fag.
# Rekkefølge = prioritet ved visning (mest spesifikke først).
TILTAK = [
    ("nybygg", r"\b(nytt bygg|nybygg|oppføring|boligblokk|leilighet|næringsbygg|enebolig|villa|rekkehus|tomannsbolig|flermannsbolig)",
     "Nybygg / oppføring av bygg",
     ["Grunn- og fundamentarbeid", "Betong/støp", "Reisverk og bæring (tømrer)", "Tak og tekking",
      "Yttervegg, isolasjon og kledning", "Vinduer og dører", "Elektro", "Rør og sanitær",
      "Ventilasjon", "Gulv og flis", "Innvendig snekring og maling"],
     ["Snekkerarbeid/tømrer", "Takarbeid", "Elektroinstallasjon", "VVS og rørlegger", "Gulvlegging/flislegging", "Malerarbeid"]),

    ("tilbygg", r"\b(tilbygg|påbygg|utvidelse)",
     "Tilbygg/påbygg – utvidelse av bygget",
     ["Grunn/fundament for tilbygget", "Reisverk og bæring", "Tak på tilbygget",
      "Isolasjon og fasade/kledning", "Vinduer og dører", "Elektro og rør hvis nytt oppholdsrom", "Maling"],
     ["Snekkerarbeid/tømrer", "Takarbeid", "Elektroinstallasjon", "VVS og rørlegger", "Malerarbeid"]),

    ("fasade", r"\b(fasadeendring|fasade|kledning|ny inngang|vindu)",
     "Fasadeendring – ytre endringer",
     ["Ny kledning/panel", "Nye vinduer og dører", "Beslag", "Maling/overflate"],
     ["Snekkerarbeid/tømrer", "Malerarbeid"]),

    ("tak", r"\b(tak|takomlegging|omtekking|takvindu|takopplett|ark)",
     "Takarbeid – nytt tak eller takendring",
     ["Riving av gammelt tak", "Undertak og lekter", "Taktekking", "Beslag, renner og nedløp", "Evt. takvinduer"],
     ["Takarbeid", "Snekkerarbeid/tømrer"]),

    ("vatrom", r"\b(våtrom|bad|dusj|vaskerom)",
     "Våtrom – nytt eller oppgradert bad",
     ["Riving", "Membran og tetting", "Flislegging", "Rør, sluk og sanitær", "Ventilasjon", "Elektro (varmekabel/punkt)"],
     ["VVS og rørlegger", "Gulvlegging/flislegging", "Elektroinstallasjon"]),

    ("bruksendring", r"\b(bruksendring|innredning|innreder|loft til|kjeller til|tilleggsdel)",
     "Bruksendring – tar i bruk areal til nytt formål",
     ["Isolasjon og brannskille", "Rømningsvei/vindu", "Elektro", "Rør hvis våtrom/kjøkken", "Gulv", "Maling"],
     ["Snekkerarbeid/tømrer", "Elektroinstallasjon", "VVS og rørlegger", "Gulvlegging/flislegging", "Malerarbeid"]),

    ("garasje", r"\b(garasje|carport|uthus|bod|anneks|naust)",
     "Frittstående bygg – garasje/uthus e.l.",
     ["Grunn og støp", "Reisverk (tømrer)", "Tak", "Kledning", "Port/dør", "Evt. elektro"],
     ["Snekkerarbeid/tømrer", "Takarbeid", "Elektroinstallasjon"]),

    ("terrasse", r"\b(terrasse|veranda|balkong|platting|uteplass)",
     "Terrasse/veranda – uteplass",
     ["Fundamenter", "Bæring og bjelkelag", "Terrassebord/dekke", "Rekkverk"],
     ["Snekkerarbeid/tømrer"]),

    ("riving", r"\b(riving|rive|sanering)",
     "Riving",
     ["Riving av bygg/konstruksjon", "Sanering og avfallshåndtering", "Rydding av tomt"],
     ["Snekkerarbeid/tømrer"]),

    ("mur", r"\b(mur|forstøtning|støttemur|natursten)",
     "Murarbeid / forstøtningsmur",
     ["Grunnarbeid", "Muring/betong", "Drenering"],
     ["Snekkerarbeid/tømrer"]),

    ("pipe", r"\b(pipe|skorstein|ildsted|peis|ovn)",
     "Pipe/ildsted",
     ["Pipeelement eller stålpipe", "Gjennomføring i tak", "Beslag", "Montering av ildsted"],
     ["Takarbeid"]),

    ("solcelle", r"\b(solcelle|solpanel|solenergi)",
     "Solcelleanlegg",
     ["Montasje på tak", "Elektro og vekselretter", "Nettilknytning"],
     ["Takarbeid", "Elektroinstallasjon"]),

    ("terreng", r"\b(terrenginngrep|vei|avkjørsel|mur og fylling|graving|drenering|va-anlegg|vann og avløp)",
     "Terreng/utomhus – vei, graving, VA",
     ["Graving og masseflytting", "Vei/avkjørsel", "Drenering", "Vann og avløp"],
     ["VVS og rørlegger", "Snekkerarbeid/tømrer"]),
]

# Rene papir-/administrasjonssaker uten fysisk arbeid.
ADMIN = re.compile(r"\b(seksjoner|deling av|grensejustering|dispensasjon|forhåndskonferanse|matrikkel|utgår|klage)", re.I)


def analyser_arbeid(sakstype: str) -> list[dict]:
    """Returnerer liste av gjenkjente tiltak: {navn, oppgaver, fag}. Kan være tom."""
    t = (sakstype or "").lower()
    treff = []
    for _, mønster, navn, oppgaver, fag in TILTAK:
        if re.search(mønster, t):
            treff.append({"navn": navn, "oppgaver": oppgaver, "fag": fag})
    return treff


def arbeidssammendrag(sakstype: str) -> dict:
    """Samlet, visningsklar beskrivelse av arbeidet i én sak."""
    treff = analyser_arbeid(sakstype)
    if not treff:
        if ADMIN.search(sakstype or ""):
            return {"overskrift": "Administrativ sak (trolig lite/ikke fysisk arbeid)",
                    "oppgaver": [], "fag": []}
        return {"overskrift": "Byggetiltak", "oppgaver": [], "fag": []}

    # Slå sammen oppgaver/fag på tvers av tiltak, behold rekkefølge, fjern duplikater
    oppgaver, fag = [], []
    for tr in treff:
        for o in tr["oppgaver"]:
            if o not in oppgaver:
                oppgaver.append(o)
        for f in tr["fag"]:
            if f not in fag:
                fag.append(f)
    overskrift = " + ".join(tr["navn"] for tr in treff)
    return {"overskrift": overskrift, "oppgaver": oppgaver, "fag": fag}
