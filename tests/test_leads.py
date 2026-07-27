"""Enhetstester for de personvern/juss-kritiske rene funksjonene i leads.py.

Kun stdlib (unittest). Kjør med: python tests/test_leads.py
Disse funksjonene håndhever markedsføringsloven §15 (e-postfilter) og
personvern-regelen i CLAUDE.md (aldri eksponer privatpersoners adresse), så
dekningen er bevisst grundig - feil her har juridiske konsekvenser.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leads import er_upersonlig_epost, anonymiser_adresse, rensk_sakstype


class TestErUpersonligEpost(unittest.TestCase):
    """§15: kun generelle rolleadresser (post@, info@ ...) skal godkjennes."""

    def test_upersonlige_prefikser_godkjennes(self):
        for epost in [
            "post@firma.no",
            "firmapost@firma.no",
            "kontakt@firma.no",
            "info@firma.no",
            "post.bergen@firma.no",  # sammensatt lokaldel med upersonlig bit
        ]:
            with self.subTest(epost=epost):
                self.assertTrue(er_upersonlig_epost(epost))

    def test_personlige_avvises(self):
        for epost in [
            "ola.nordmann@firma.no",
            "ola@firma.no",
        ]:
            with self.subTest(epost=epost):
                self.assertFalse(er_upersonlig_epost(epost))

    def test_tom_none_og_ugyldig_avvises(self):
        # Tom streng, None, manglende @ og dobbel @ skal alle gi False.
        self.assertFalse(er_upersonlig_epost(""))
        self.assertFalse(er_upersonlig_epost(None))
        self.assertFalse(er_upersonlig_epost("postfirma.no"))       # ingen @
        self.assertFalse(er_upersonlig_epost("post@@firma.no"))      # to @
        self.assertFalse(er_upersonlig_epost("post@a@firma.no"))     # to @

    def test_store_bokstaver_og_mellomrom(self):
        # Skal normalisere case og trimme omkringliggende mellomrom.
        self.assertTrue(er_upersonlig_epost("POST@FIRMA.NO"))
        self.assertTrue(er_upersonlig_epost("  Post@Firma.no  "))
        self.assertTrue(er_upersonlig_epost("Kontakt@Firma.no"))
        # Personlig skal fortsatt avvises selv med rar case.
        self.assertFalse(er_upersonlig_epost("Ola.Nordmann@Firma.no"))

    def test_ikke_streng_type_avvises(self):
        # Ikke-str input (f.eks. NaN/float fra pandas) skal gi False, ikke krasje.
        self.assertFalse(er_upersonlig_epost(123))
        self.assertFalse(er_upersonlig_epost(float("nan")))


class TestAnonymiserAdresse(unittest.TestCase):
    """Husnummer må fjernes så eksakt privatadresse ikke publiseres."""

    def test_fjerner_husnummer_med_bokstav(self):
        self.assertEqual(anonymiser_adresse("Paradisleitet 12B"), "Paradisleitet")

    def test_fjerner_husnummer_uten_bokstav(self):
        self.assertEqual(anonymiser_adresse("Storgata 5"), "Storgata")

    def test_beholder_gatenavn_uten_husnummer(self):
        # Ingen husnummer å fjerne - gatenavnet skal beholdes uendret.
        self.assertEqual(anonymiser_adresse("Torgallmenningen"), "Torgallmenningen")

    def test_none_og_tom_gir_fallback(self):
        fallback = "et område i kommunen"
        self.assertEqual(anonymiser_adresse(None), fallback)
        self.assertEqual(anonymiser_adresse(""), fallback)
        self.assertEqual(anonymiser_adresse("   "), fallback)

    def test_husnummer_ikke_i_output(self):
        # Personvern: selve husnummeret skal aldri overleve anonymiseringen.
        resultat = anonymiser_adresse("Paradisleitet 12B")
        self.assertNotIn("12", resultat)
        self.assertNotIn("B", resultat)


class TestRenskSakstype(unittest.TestCase):
    """Matrikkel OG adresse (med husnummer) må fjernes fra sakstittelen."""

    def test_full_bergen_tittel(self):
        tittel = "82/233/0/0 Vallaheiane 141, tilbygg og fasadeendring mm"
        self.assertEqual(rensk_sakstype(tittel), "Tilbygg og fasadeendring mm")

    def test_personvern_ingen_adresse_eller_husnummer_lekker(self):
        # KRITISK: verken husnummeret (141) eller gatenavnet (Vallaheiane) skal
        # være igjen i resultatet - ellers lekker privatadressen ut i emnefelt.
        tittel = "82/233/0/0 Vallaheiane 141, tilbygg og fasadeendring mm"
        resultat = rensk_sakstype(tittel)
        self.assertNotIn("141", resultat)
        self.assertNotIn("Vallaheiane", resultat)
        self.assertNotIn("82/233", resultat)

    def test_none_og_tom_gir_byggesak(self):
        self.assertEqual(rensk_sakstype(None), "Byggesak")
        self.assertEqual(rensk_sakstype(""), "Byggesak")
        self.assertEqual(rensk_sakstype("   "), "Byggesak")

    def test_tittel_uten_komma(self):
        # Uten komma finnes ingen adressedel; matrikkel strippes, resten står.
        self.assertEqual(rensk_sakstype("nybygg enebolig"), "Nybygg enebolig")

    def test_forste_bokstav_stor(self):
        self.assertTrue(rensk_sakstype("riving av garasje")[0].isupper())


if __name__ == "__main__":
    unittest.main()
