import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from pysion.check import checks
from pysion.check.checks import (Availability, FREE, TAKEN, UNKNOWN, SOCIALS,
                                 check_com, check_social, to_handle)
from pysion.check.cli import _fully_free, main, names_from_stdin
from pysion.check.http_client import HttpResult


def fake_request(status=None, error=None):
    return lambda *a, **k: HttpResult(status=status, error=error)


class TestDomain(unittest.TestCase):
    def test_rdap_statuses(self):
        cases = {404: FREE, 200: TAKEN, 500: UNKNOWN}
        for code, expected in cases.items():
            with mock.patch.object(checks, "request", fake_request(status=code)):
                self.assertEqual(check_com("ejemplo").status, expected)

    def test_network_error_is_unknown(self):
        with mock.patch.object(checks, "request", fake_request(error="timeout")):
            result = check_com("ejemplo")
        self.assertEqual(result.status, UNKNOWN)
        self.assertIn("timeout", result.detail)


class TestSocial(unittest.TestCase):
    def _social(self, name):
        return next(s for s in SOCIALS if s.name == name)

    def test_github_free_and_taken(self):
        gh = self._social("GitHub")
        with mock.patch.object(checks, "request", fake_request(status=404)):
            self.assertEqual(check_social(gh, "x").status, FREE)
        with mock.patch.object(checks, "request", fake_request(status=200)):
            self.assertEqual(check_social(gh, "x").status, TAKEN)

    def test_instagram_200_is_unknown(self):
        ig = self._social("Instagram")
        with mock.patch.object(checks, "request", fake_request(status=200)):
            result = check_social(ig, "x")
        self.assertEqual(result.status, UNKNOWN)
        self.assertFalse(result.reliable)

    def test_block_codes_are_unknown(self):
        gh = self._social("GitHub")
        for code in (403, 429):
            with mock.patch.object(checks, "request", fake_request(status=code)):
                self.assertEqual(check_social(gh, "x").status, UNKNOWN)


class TestHandle(unittest.TestCase):
    def test_to_handle(self):
        self.assertEqual(to_handle("Cisegus"), "cisegus")
        self.assertEqual(to_handle("Aciron-98!"), "aciron-98")


class TestFullyFree(unittest.TestCase):
    def test_unreliable_unknown_does_not_block(self):
        results = [Availability("dominio .com", "x.com", FREE),
                   Availability("Instagram", "x", UNKNOWN, reliable=False)]
        self.assertTrue(_fully_free(results))

    def test_reliable_unknown_blocks(self):
        results = [Availability("dominio .com", "x.com", FREE),
                   Availability("GitHub", "x", UNKNOWN, reliable=True)]
        self.assertFalse(_fully_free(results))

    def test_taken_blocks(self):
        self.assertFalse(_fully_free([Availability("dominio .com", "x.com", TAKEN)]))


class TestStdin(unittest.TestCase):
    def test_parses_text_csv_json(self):
        text = io.StringIO("  1. Cimos    96.7  [blend: a + b]\n  2. Telor   90.0\n")
        self.assertEqual(names_from_stdin(text), ["Cimos", "Telor"])
        csv_in = io.StringIO("name,score\nCira,91.7\nApher,90.4\n")
        self.assertEqual(names_from_stdin(csv_in), ["Cira", "Apher"])  # 'name' se ignora

    def test_ignores_blank_and_symbols(self):
        self.assertEqual(names_from_stdin(io.StringIO("\n---\n42\nOnyx 100\n")), ["Onyx"])


class TestCli(unittest.TestCase):
    def _run(self, argv, stdin=""):
        out = io.StringIO()
        all_free = [Availability("dominio .com", "x.com", FREE)]
        with mock.patch("pysion.check.cli._run_checks", return_value=all_free), \
             mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out):
            try:
                code = main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue()

    def test_names_from_args(self):
        code, out = self._run(["cisegus"])
        self.assertEqual(code, 0)
        self.assertIn("cisegus", out)

    def test_names_from_stdin(self):
        code, out = self._run([], stdin="  1. Cimos  96.7\n")
        self.assertEqual(code, 0)
        self.assertIn("cimos", out)

    def test_no_input_is_usage_error(self):
        self.assertEqual(self._run([], stdin="")[0], 2)


if __name__ == "__main__":
    unittest.main()
