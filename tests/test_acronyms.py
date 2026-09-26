import io
import random
import re
import unittest
from contextlib import redirect_stdout

from pysion.acronyms import generate_acronyms
from pysion.cli import EXIT_OK, main
from pysion.presets import apply_format, combine_presets, load_preset


class TestAcronymGenerator(unittest.TestCase):
    def test_shape_and_uniqueness(self):
        result = generate_acronyms(30, 2, 4, frozenset(), 0.0, random.Random(1))
        self.assertEqual(len(result.names), 30)
        canon = [n.name for n in result.names]
        self.assertEqual(len(canon), len(set(canon)))  # sin repetidos
        for n in result.names:
            self.assertRegex(n.name, r"^[a-z]{2,4}$")           # canónico: minúsculas
            self.assertRegex(n.base_display, r"^[A-Z]{2,4}$")   # mostrado: mayúsculas
            self.assertEqual(n.strategy, "sigla")

    def test_history_excludes(self):
        result = generate_acronyms(20, 2, 3, frozenset({"ab", "cd"}), 0.0, random.Random(2))
        self.assertNotIn("ab", [n.name for n in result.names])

    def test_ampersand_variant(self):
        found = False
        for seed in range(40):
            r = generate_acronyms(20, 2, 2, frozenset(), 0.5, random.Random(seed))
            if any("&" in n.base_display for n in r.names):
                found = True
                break
        self.assertTrue(found, "no apareció la variante con &")


class TestCombine(unittest.TestCase):
    def test_sigla_plus_empresa(self):
        combined = combine_presets(["sigla", "empresa"])
        self.assertEqual(combined.mode, "acronym")
        self.assertEqual(combined.case, "upper")
        self.assertEqual(tuple(combined.qualifiers), load_preset("empresa").qualifiers)

    def test_order_independent(self):
        a, b = combine_presets(["sigla", "empresa"]), combine_presets(["empresa", "sigla"])
        self.assertEqual((a.mode, a.case, a.qualifiers), (b.mode, b.case, b.qualifiers))

    def test_format_keeps_acronym_and_adds_qualifier(self):
        combined = combine_presets(["sigla", "empresa"])
        # forzar calificador siempre
        combined = combined.__class__(**{**combined.__dict__, "qualifier_ratio": 1.0})
        from pysion.generator import GenerationResult, ScoredName
        result = GenerationResult([ScoredName("ibm", 100.0, "sigla", (), base_display="IBM")], 1, {})
        apply_format(result, combined, random.Random(0))
        display = result.names[0].display
        self.assertTrue(display.startswith("IBM "))
        self.assertIn(display.split(" ", 1)[1], combined.qualifiers)


class TestCli(unittest.TestCase):
    def _out(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_sigla_output_uppercase(self):
        code, out = self._out(["--type", "sigla", "-n", "5", "--seed", "1"])
        self.assertEqual(code, EXIT_OK)
        names = [line.split()[1] for line in out.splitlines() if line.strip()]
        self.assertTrue(all(re.fullmatch(r"[A-Z&]{2,4}", n) for n in names), names)

    def test_sigla_empresa_can_add_qualifier(self):
        code, out = self._out(["--type", "sigla,empresa", "-n", "20", "--seed", "3"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn(" ", out)  # al menos una línea con calificador


if __name__ == "__main__":
    unittest.main()
