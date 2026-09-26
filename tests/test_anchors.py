import io
import random
import unittest
from contextlib import redirect_stderr, redirect_stdout

from pysion.cli import EXIT_OK, EXIT_USAGE, main
from pysion.exceptions import LexiconError
from pysion.generator import GeneratorConfig, generate
from pysion.lexicon import build_lexicon, normalize_anchors
from pysion.strategies import STRATEGIES


class TestAnchorLexicon(unittest.TestCase):
    def test_normalize_anchors(self):
        self.assertEqual(normalize_anchors(["Python", "Génesis", "python"]), ("python", "genesis"))

    def test_invalid_anchor(self):
        for bad in ("ab", "!!", "a" * 20):
            with self.subTest(word=bad), self.assertRaises(LexiconError):
                normalize_anchors([bad])

    def test_single_anchor_without_themes(self):
        lex = build_lexicon(themes=[], anchors=["python"])
        self.assertEqual(lex.words, ("python",))
        self.assertEqual(lex.anchors, ("python",))


class TestAnchorGeneration(unittest.TestCase):
    def _assert_derived(self, lexicon, count):
        result = generate(lexicon, GeneratorConfig(count=count), random.Random(5))
        self.assertEqual(len(result.names), count)
        for n in result.names:
            self.assertTrue(set(n.sources) & set(lexicon.anchors), n)
            self.assertNotIn(n.name, lexicon.anchors)

    def test_every_name_derives_from_anchor(self):
        self._assert_derived(build_lexicon(anchors=["python", "generator"]), 40)

    def test_single_word_only(self):
        self._assert_derived(build_lexicon(themes=[], anchors=["python"]), 10)

    def test_each_strategy_uses_anchor(self):
        lex = build_lexicon(anchors=["python"])
        rng = random.Random(9)
        for name, strategy in STRATEGIES.items():
            with self.subTest(strategy=name):
                candidates = [strategy(rng, lex, "python") for _ in range(30)]
                self.assertTrue(all("python" in c.sources for c in candidates if c))

    def test_partner_strategies_without_partners(self):
        lex = build_lexicon(themes=[], anchors=["python"])
        rng = random.Random(1)
        self.assertIsNone(STRATEGIES["blend"](rng, lex, "python"))
        self.assertIsNone(STRATEGIES["syllable_mix"](rng, lex, "python"))


class TestAnchorCli(unittest.TestCase):
    def _run(self, argv):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            try:
                return main(argv)
            except SystemExit as exc:  # errores de argparse
                return exc.code

    def test_word_option(self):
        self.assertEqual(self._run(["-w", "python", "-n", "5", "--seed", "1"]), EXIT_OK)
        self.assertEqual(self._run(["-w", "python", "--no-themes", "-n", "5"]), EXIT_OK)

    def test_usage_errors(self):
        self.assertEqual(self._run(["-w", "ab"]), EXIT_USAGE)
        self.assertEqual(self._run(["--no-themes"]), EXIT_USAGE)

    def test_only_dicts_alias_still_works(self):
        self.assertEqual(self._run(["--only-dicts", "-w", "python", "-n", "3"]), EXIT_OK)


if __name__ == "__main__":
    unittest.main()
