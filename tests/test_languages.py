import io
import json
import random
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from pysion import languages
from pysion.cli import EXIT_LEXICON, EXIT_OK, main
from pysion.exceptions import LexiconError
from pysion.generator import GeneratorConfig, generate
from pysion.languages import available_languages, load_language, load_languages, merge_rules
from pysion.lexicon import build_lexicon
from pysion.phonetics import normalize
from pysion.rules import PhoneticRules, check

EXPECTED = {"de", "en", "es", "it", "la", "pt", "ru"}
BASE = PhoneticRules(min_length=3, max_length=14)


class TestTransliteration(unittest.TestCase):
    def test_cyrillic_and_special_latin(self):
        cases = {"Волга": "volga", "Щука": "shchuka", "Жар-птица": "zharptitsa",
                 "Straße": "strasse", "Ødegaard": "odegaard", "Coração": "coracao"}
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize(raw), expected)


class TestProfiles(unittest.TestCase):
    def test_all_expected_languages_available(self):
        self.assertTrue(EXPECTED <= set(available_languages()))

    def test_profiles_load(self):
        for code in available_languages():
            with self.subTest(lang=code):
                lang = load_language(code)
                self.assertTrue(lang.words and lang.prefixes and lang.suffixes)

    def test_real_words_mostly_pass_own_rules(self):
        """Calibración: las reglas de un idioma deben aceptar sus palabras reales."""
        for code in available_languages():
            with self.subTest(lang=code):
                lang = load_language(code)
                rules = lang.rules(BASE)
                accepted = sum(not check(w, rules) for w in lang.words)
                self.assertGreaterEqual(accepted / len(lang.words), 0.95)

    def test_unknown_and_traversal_codes_rejected(self):
        for code in ("xx", "../../etc", "de/../ru"):
            with self.subTest(code=code), self.assertRaises(LexiconError):
                load_language(code)


class TestInvalidProfile(unittest.TestCase):
    def _load_with(self, profile):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "zz"
            folder.mkdir()
            (folder / "profile.json").write_text(profile, encoding="utf-8")
            (folder / "words.txt").write_text("alfa\nbeta\n", encoding="utf-8")
            with mock.patch.object(languages, "LANGUAGES_DIR", Path(tmp)):
                return load_language("zz")

    def test_valid_minimal_profile(self):
        self.assertEqual(self._load_with('{"name": "Prueba"}').words, ("alfa", "beta"))

    def test_invalid_profiles(self):
        bad = ['{no json', '[]', '{"clave_rara": 1}', '{"max_vowel_run": 99}',
               '{"onset_clusters": ["Br"]}', '{"allowed_doubles": "ll"}']
        for profile in bad:
            with self.subTest(profile=profile), self.assertRaises(LexiconError):
                self._load_with(profile)


class TestMergeRules(unittest.TestCase):
    def test_single_language_uses_its_rules(self):
        it = load_language("it")
        self.assertEqual(merge_rules(BASE, [it]), it.rules(BASE))

    def test_multiple_languages_are_permissive(self):
        it, de = load_languages(["it", "de"])
        merged = merge_rules(BASE, [it, de])
        self.assertIn("sch", merged.onset_clusters)            # aporta alemán
        self.assertNotIn("k", merged.forbidden_letters)         # alemán sí la usa
        self.assertEqual(merged.max_vowel_run, 3)
        self.assertEqual((merged.min_length, merged.max_length), (3, 14))

    def test_no_languages_returns_base(self):
        self.assertIs(merge_rules(BASE, []), BASE)


class TestLanguageGeneration(unittest.TestCase):
    def test_names_follow_language_rules(self):
        for code in ("it", "ru", "de"):
            with self.subTest(lang=code):
                langs = load_languages([code])
                rules = merge_rules(PhoneticRules(), langs)
                lexicon = build_lexicon(themes=[], languages=langs)
                result = generate(lexicon, GeneratorConfig(count=30, rules=rules), random.Random(4))
                self.assertEqual(len(result.names), 30)
                for n in result.names:
                    self.assertEqual(check(n.name, rules), [], n)

    def test_italian_ends_in_vowel_or_soft_consonant(self):
        langs = load_languages(["it"])
        rules = merge_rules(PhoneticRules(), langs)
        lexicon = build_lexicon(themes=[], languages=langs)
        result = generate(lexicon, GeneratorConfig(count=40, rules=rules), random.Random(2))
        self.assertTrue(all(n.name[-1] in "aeioulnr" for n in result.names))

    def test_language_affixes_replace_generic(self):
        lexicon = build_lexicon(themes=[], languages=load_languages(["de"]))
        self.assertIn("heim", lexicon.suffixes)
        self.assertNotIn("ix", lexicon.suffixes)


class TestLanguageCli(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            try:
                code = main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue()

    def test_lang_option(self):
        code, out = self._run(["-l", "it,la", "-n", "5", "--seed", "1", "-f", "json"])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(len(json.loads(out)), 5)

    def test_lang_with_cyrillic_anchor(self):
        code, out = self._run(["-l", "ru", "-w", "Волга", "-n", "5", "--seed", "1", "-f", "json"])
        self.assertEqual(code, EXIT_OK)
        self.assertTrue(all("volga" in item["sources"] for item in json.loads(out)))

    def test_unknown_lang(self):
        self.assertEqual(self._run(["-l", "xx"])[0], EXIT_LEXICON)


if __name__ == "__main__":
    unittest.main()
