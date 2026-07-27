"""Tester for compute_scores: sakstype->NACE-mapping og differensierende score.

Kjør med:  python tests/test_scoring.py
Kun stdlib (unittest) + pandas. Ingen pytest / nye avhengigheter.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

import pandas as pd

from compute_scores import (
    gjett_nace_fra_sakstype,
    gjett_nace_sett_fra_sakstype,
    bransjescore,
    geografiscore,
    ferskhetscore,
    compute_scores,
    SAKSTYPE_TIL_NACE_SETT,
)


class TestNaceMapping(unittest.TestCase):
    def test_mange_sakstyper_mapper(self):
        """Et bredt utvalg reelle Bergen-sakstyper skal nå treffe en bransje."""
        titler = [
            "82/233/0/0 Vallaheiane 141, tilbygg og fasadeendring mm",
            "166/182/0/0 Fjellveien 121, nytt bygg - Boligformål",
            "162/719/0/0 Gimleveien 41A, innvending ombygging av eksisterende bolig",
            "167/261/0/0 Løytnant Bjelkes gate 2, bruksendring bolig",
            "186/570/0/0 Tertnesveien 138, tilbygg bolig",
            "159/459/0/0 Inndalsveien 7C, riving av eksisterende bolighus",
            "1/1/0/0 Ein veg, mur mot vei",
            "2/2/0/0 Eit tak, takomlegging",
        ]
        mapper = sum(1 for t in titler if gjett_nace_sett_fra_sakstype(t))
        self.assertEqual(mapper, len(titler),
                         "Alle disse reelle sakstypene skal mappe til minst én bransje")

    def test_fler_bransje_mapping(self):
        """Ett tiltak kan berøre flere fag -> flere NACE-koder i settet."""
        sett = gjett_nace_sett_fra_sakstype("tilbygg og fasadeendring")
        self.assertGreater(len(sett), 1, "Tilbygg + fasade skal treffe flere bransjer")
        self.assertIn("43.320", sett)  # tømrer
        self.assertIn("43.910", sett)  # tak (fra tilbygg)
        self.assertIn("43.341", sett)  # maler (fra fasade)

    def test_presis_sak_ett_fag(self):
        """En presis sak skal peke på nøyaktig én bransje."""
        sett = gjett_nace_sett_fra_sakstype("takomlegging")
        self.assertEqual(sett, {"43.910"})

    def test_ordgrense_unngar_falske_treff(self):
        """\\b-trikset: 'mal' skal ikke treffe inni 'normal', 'tak' ikke i 'kontakt'."""
        self.assertEqual(gjett_nace_sett_fra_sakstype("helt normal kontakt sak"), set())

    def test_bakoverkompatibel_enkeltfunksjon(self):
        """gjett_nace_fra_sakstype skal fortsatt returnere ÉN kode (eller None)."""
        nace = gjett_nace_fra_sakstype("takomlegging")
        self.assertEqual(nace, "43.910")
        self.assertIsNone(gjett_nace_fra_sakstype("søknad om dispensasjon"))


class TestDelscorer(unittest.TestCase):
    def test_bransjescore_faerre_fag_hoyere(self):
        """Færre/mer spesifikke bransjetreff skal gi høyere bransjescore."""
        self.assertGreater(bransjescore(1), bransjescore(2))
        self.assertGreater(bransjescore(2), bransjescore(4))

    def test_geografi_gradert(self):
        """3-siffers postnr-nærhet > 2-siffer > bare samme kommune > ingenting."""
        tre = geografiscore("5227", "5229", "4601", "4601")
        to = geografiscore("5227", "5290", "4601", "4601")
        kommune = geografiscore("5227", "9010", "4601", "4601")
        ingen = geografiscore("5227", "9010", "4601", "5001")
        self.assertGreater(tre, to)
        self.assertGreater(to, kommune)
        self.assertGreater(kommune, ingen)
        self.assertEqual(ingen, 0.0)

    def test_ferskhet_nyere_hoyere(self):
        from datetime import date
        ref = date(2026, 7, 27)
        fersk = ferskhetscore("2026-07-27", ref)
        halv = ferskhetscore("2026-07-12", ref)
        gammel = ferskhetscore("2026-05-01", ref)
        self.assertGreater(fersk, halv)
        self.assertGreater(halv, gammel)
        self.assertEqual(gammel, 0.0)


class TestComputeScoresEndeTilEnde(unittest.TestCase):
    def _saker(self):
        return pd.DataFrame([
            # Presis, fersk, nær sak
            {"sak_id": "A", "kommunenummer": "4601", "postnummer": "5227",
             "adresse": "Nærgata 1", "saksdato": "2026-07-27", "sakstype": "takomlegging"},
            # Generisk, eldre, uten postnr (fjernere)
            {"sak_id": "B", "kommunenummer": "4601", "postnummer": "",
             "adresse": "Fjerngata 9", "saksdato": "2026-06-01", "sakstype": "bruksendring bolig"},
        ])

    def _bedrifter(self):
        return pd.DataFrame([
            # Takfirma nær sak A (samme 3-siffer postnr), liten bedrift
            {"organisasjonsnummer": "1", "navn": "Tak AS", "nace_kode": "43.910",
             "bransje": "Takarbeid", "kommunenummer": "4601", "postnummer": "5229",
             "epost": "post@tak.no", "telefon": "1", "antall_ansatte": 5.0},
            # Tømrerfirma langt unna, ukjent størrelse (kandidat for sak B)
            {"organisasjonsnummer": "2", "navn": "Tømrer AS", "nace_kode": "43.320",
             "bransje": "Snekkerarbeid/tømrer", "kommunenummer": "4601", "postnummer": "5299",
             "epost": "post@tom.no", "telefon": "2", "antall_ansatte": None},
        ])

    def test_presis_naer_slaar_generisk_fjern(self):
        matches = compute_scores(self._saker(), self._bedrifter())
        self.assertFalse(matches.empty)
        beste_a = matches[matches["sak_id"] == "A"]["score"].max()
        beste_b = matches[matches["sak_id"] == "B"]["score"].max()
        self.assertGreater(beste_a, beste_b,
                           "Presis/fersk/nær lead skal score høyere enn generisk/fjern")

    def test_kjernekolonner_bevart(self):
        """app.py m.fl. leser disse kolonnene - de skal ikke forsvinne."""
        matches = compute_scores(self._saker(), self._bedrifter())
        for kol in ["sak_id", "sak_adresse", "sakstype", "saksdato",
                    "organisasjonsnummer", "bedrift_navn", "bransje",
                    "epost", "telefon", "score"]:
            self.assertIn(kol, matches.columns)

    def test_flere_bransjer_gir_matcher_i_flere_fag(self):
        """En fler-bransje-sak skal kunne matche bedrifter i ulike fag."""
        matches = compute_scores(self._saker(), self._bedrifter())
        bransjer_b = set(matches[matches["sak_id"] == "B"]["bransje"])
        self.assertIn("Snekkerarbeid/tømrer", bransjer_b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
