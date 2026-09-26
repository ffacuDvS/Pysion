import unittest

from pysion.rules import PhoneticRules, check
from pysion.scoring import harmony_score

RULES = PhoneticRules()


class TestRules(unittest.TestCase):
    def test_valid_names(self):
        for name in ("lumora", "verix", "trenova", "axion"):
            with self.subTest(name=name):
                self.assertEqual(check(name, RULES), [])

    def test_invalid_names(self):
        cases = {
            "abc": "longitud",
            "brrrt": "sin_vocales",
            "ptalo": "inicio_impronunciable",
            "lunstrka": "consonantes_consecutivas",
            "aeiola": "vocales_consecutivas",
            "qalor": "q_sin_u",
            "lunaj": "final_debil",
        }
        for name, reason in cases.items():
            with self.subTest(name=name):
                self.assertIn(reason, check(name, RULES))


class TestScoring(unittest.TestCase):
    def test_range(self):
        for name in ("lumora", "xyz", "a", "bababababa"):
            self.assertTrue(0 <= harmony_score(name) <= 100)

    def test_harmonic_beats_monotonous(self):
        self.assertGreater(harmony_score("lumora"), harmony_score("bababa"))


if __name__ == "__main__":
    unittest.main()
