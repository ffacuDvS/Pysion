import unittest

from namegen.phonetics import cv_pattern, join_smooth, normalize, syllabify


class TestPhonetics(unittest.TestCase):
    def test_normalize_strips_accents_and_symbols(self):
        self.assertEqual(normalize("Halcón-Ñandú 3"), "halconnandu")

    def test_cv_pattern(self):
        self.assertEqual(cv_pattern("luna"), "CVCV")

    def test_syllabify(self):
        cases = {"luna": ["lu", "na"], "silva": ["sil", "va"],
                 "matrix": ["ma", "trix"], "sol": ["sol"],
                 "zashchita": ["za", "shchi", "ta"], "mechta": ["mech", "ta"]}
        for word, expected in cases.items():
            with self.subTest(word=word):
                self.assertEqual(syllabify(word), expected)

    def test_syllabify_roundtrip(self):
        for word in ("aurora", "quantum", "harmony", "kinesis"):
            self.assertEqual("".join(syllabify(word)), word)

    def test_join_smooth(self):
        self.assertEqual(join_smooth("sol", "luna"), "soluna")    # letra repetida
        self.assertEqual(join_smooth("nova", "ia"), "novia")
        self.assertEqual(join_smooth("py", "ino"), "pyno")        # raíz corta intacta       # vocal+vocal
        self.assertEqual(join_smooth("tre", "bra"), "trebra")     # C+V normal
        self.assertEqual(join_smooth("sol", "kan"), "sokan")      # C+C no inseparable
        self.assertEqual(join_smooth("hoch", "stall"), "hochstall")  # no rompe dígrafo


if __name__ == "__main__":
    unittest.main()
