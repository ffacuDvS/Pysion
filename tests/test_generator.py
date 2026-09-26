import io
import random
from contextlib import redirect_stderr, redirect_stdout
import tempfile
import unittest
from pathlib import Path

from pysion.cli import EXIT_LEXICON, EXIT_OK, EXIT_USAGE, main
from pysion.exceptions import ConfigError, LexiconError
from pysion.generator import GeneratorConfig, generate
from pysion.lexicon import build_lexicon
from pysion.rules import check


class TestGenerator(unittest.TestCase):
    def setUp(self):
        self.lexicon = build_lexicon()

    def test_reproducible_with_seed(self):
        config = GeneratorConfig(count=10)
        a = generate(self.lexicon, config, random.Random(1))
        b = generate(self.lexicon, config, random.Random(1))
        self.assertEqual(a.names, b.names)

    def test_results_are_valid_unique_and_invented(self):
        config = GeneratorConfig(count=50)
        result = generate(self.lexicon, config, random.Random(7))
        names = [n.name for n in result.names]
        self.assertEqual(len(names), len(set(names)))
        for n in result.names:
            self.assertEqual(check(n.name, config.rules), [])
            self.assertNotIn(n.name, self.lexicon.known_words)
            self.assertGreaterEqual(n.score, config.min_score)

    def test_starts_with(self):
        result = generate(self.lexicon, GeneratorConfig(count=5, starts_with="l"), random.Random(3))
        self.assertTrue(all(n.name.startswith("l") for n in result.names))

    def test_invalid_config(self):
        with self.assertRaises(ConfigError):
            generate(self.lexicon, GeneratorConfig(strategies=("nope",)), random.Random())


class TestLexicon(unittest.TestCase):
    def test_unknown_theme(self):
        with self.assertRaises(LexiconError):
            build_lexicon(themes=["inexistente"])

    def test_custom_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "words.txt"
            path.write_text("# comentario\nÁrbol\nCanción\nxx\nfrase con espacios\n", encoding="utf-8")
            lex = build_lexicon(themes=[], extra_files=[path])
            self.assertEqual(lex.words, ("arbol", "cancion"))

    def test_missing_file(self):
        with self.assertRaises(LexiconError):
            build_lexicon(extra_files=[Path("/no/existe.txt")])


class TestCli(unittest.TestCase):
    def test_exit_codes(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self._assert_exit_codes()

    def _assert_exit_codes(self):
        self.assertEqual(main(["-n", "3", "--seed", "1", "-f", "json"]), EXIT_OK)
        self.assertEqual(main(["-d", "/no/existe.txt"]), EXIT_LEXICON)
        self.assertEqual(main(["-s", "nope"]), EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
