import io
import random
import unittest
from contextlib import redirect_stdout

from pysion.cli import EXIT_OK, EXIT_USAGE, main
from pysion.exceptions import ConfigError
from pysion.generator import GenerationResult, ScoredName
from pysion.presets import apply_format, available_presets, load_preset

EXPECTED = {"empresa", "software", "emprendimiento", "usuario", "script",
            "ciudad", "pueblo", "barrio", "calle"}


def _result(*names):
    return GenerationResult([ScoredName(n, 90.0, "blend", ("a", "b")) for n in names], 10, {})


class TestLoad(unittest.TestCase):
    def test_all_presets_available(self):
        self.assertEqual(set(available_presets()), EXPECTED)

    def test_every_preset_loads_and_is_valid(self):
        for name in available_presets():
            with self.subTest(preset=name):
                p = load_preset(name)
                self.assertIn(p.case, ("lower", "title"))
                self.assertTrue(0 <= p.qualifier_ratio <= 1)

    def test_unknown_preset(self):
        with self.assertRaises(ConfigError):
            load_preset("inexistente")


class TestFormat(unittest.TestCase):
    def test_lower_case_no_qualifier(self):
        p = load_preset("usuario")
        r = _result("cipher")
        apply_format(r, p, random.Random(0))
        self.assertEqual(r.names[0].display, "cipher")
        self.assertEqual(r.names[0].name, "cipher")  # el nombre base no cambia

    def test_title_case(self):
        p = load_preset("ciudad")  # title, sin calificador
        r = _result("verona")
        apply_format(r, p, random.Random(0))
        self.assertEqual(r.names[0].display, "Verona")

    def test_qualifier_appended_sometimes(self):
        p = load_preset("empresa")
        r = _result(*[f"cipher{i}" for i in range(60)])
        apply_format(r, p, random.Random(1))
        with_q = [n.display for n in r.names if " " in n.display]
        without_q = [n.display for n in r.names if " " not in n.display]
        self.assertTrue(with_q and without_q)  # unos con calificador, otros no
        for disp in with_q:
            base, qual = disp.split(" ", 1)
            self.assertTrue(base[0].isupper())
            self.assertIn(qual, p.qualifiers)


class TestCli(unittest.TestCase):
    def _out(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_username_is_lowercase(self):
        code, out = self._out(["--type", "usuario", "-n", "5", "--seed", "1"])
        self.assertEqual(code, EXIT_OK)
        names = [line.split()[1] for line in out.splitlines() if line.strip()]
        self.assertTrue(all(n == n.lower() for n in names))

    def test_user_length_overrides_preset(self):
        code, out = self._out(["--type", "usuario", "--min-length", "9", "-n", "5", "--seed", "1"])
        names = [line.split()[1] for line in out.splitlines() if line.strip()]
        self.assertTrue(all(len(n) >= 9 for n in names))

    def test_unknown_type_is_usage_error(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--type", "nope"]), EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
