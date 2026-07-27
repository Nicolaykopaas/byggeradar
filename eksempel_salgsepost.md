# Eksempel: salgs-e-post fra Byggeradar

Dette er et konkret eksempel på hvordan en autonom salgs-e-post ser ut. Den
**representerer selskapet Byggeradar**, aldri en privatperson, og følger
markedsføringsloven §15 (kun upersonlige adresser, tydelig avmelding).

Eksemplet er bygget på et **ekte, ferskt lead** fra pilotdataene (Bergen),
anonymisert til postnummer – ingen personopplysninger deles.

---

## Slik ser e-posten ut

```
Fra:    Byggeradar <post@byggeradar.no>
Til:    post@eksempel-tomrer.no
Emne:   Ny byggejobb i 5230: Nybygg villa

Hei,

Det kom nettopp inn en ny byggesak i deres område som kan passe dere godt:

  • Type:      Nybygg villa
  • Område:    postnr 5230 (Paradis-området), Bergen
  • Fag:       tømrer, tak, elektro, gulv/flis
  • Status:    privat tiltakshaver – ingen entreprenør registrert ennå

Et nybygg med privat tiltakshaver betyr at de nesten helt sikkert skal hyre
inn håndverkere. Typisk arbeid: grunn og fundament, reisverk, tak, yttervegg
og kledning, vinduer, elektro, rør og innvendig arbeid.

Dette er en gratis smakebit fra Byggeradar. Vi leser hver nye byggetillatelse
og varsler deg om de som passer ditt fag og område – med lenke rett til saken
hos kommunen, så du kan være først ute.

Se ferske saker i ditt område gratis:
https://byggeradar.no

Ønsker dere ikke slike tips? Svar «nei takk», så hører dere ikke fra oss igjen.

Mvh
Byggeradar
```

---

## Hvorfor dette er en god e-post

- **Representerer selskapet, aldri deg** – avsender og signatur er «Byggeradar».
  Ditt personnavn står ingen steder.
- **Konkret og ærlig** – nevner et ekte, ferskt lead og hva jobben faktisk
  innebærer, uten å love en garantert jobb. Vi selger «vær først», ikke «dette
  er din kunde».
- **§15-trygg** – går kun til en upersonlig adresse (`post@…`), og har en enkel
  avmelding i hver e-post. Samme bedrift kontaktes aldri to ganger.
- **Kort** – én skjermhøyde, ett tydelig neste steg (lenken til verktøyet).
- **Riktig lead-type** – «nybygg + privat søker» er den mest lovende saken:
  de skal helt sikkert hyre inn.

## Slik genereres og sendes den

```bash
python generate_email_drafts.py --utboks   # lager e-postene i data/utboks/
python approve_and_send.py --dry-run       # se hva som ville blitt sendt
python approve_and_send.py --maks 10        # send (maks 10/uke, som selskapet)
```

Utsendingen krever at din egen sendekonto er satt i `.env` (SMTP). Uten den
sendes ingenting. Se README for full oppsett.
