import io
import threading
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from pysion.builder import web
from pysion.builder.cli import EXIT_EMPTY, EXIT_OK, EXIT_SOURCE, EXIT_USAGE, main
from pysion.builder.extract import ExtractOptions, count_words, load_stopwords, select_words, tokenize
from pysion.builder.files import read_file
from pysion.builder.html_text import html_to_text
from pysion.builder.writer import HEADER, merge_into
from pysion.exceptions import SourceError

try:
    import pypdf  # noqa: F401
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


def make_pdf(path: Path, text: str) -> None:
    """PDF mínimo válido con una línea de texto (sin librerías)."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path.write_bytes(out)


class TestExtract(unittest.TestCase):
    def test_tokenize(self):
        text = "L'Aurora boreal, 2024: Жар-птица y e-mail_x"
        self.assertEqual(list(tokenize(text)),
                         ["l", "aurora", "boreal", "zhar", "ptitsa", "y", "e", "mail", "x"])

    def test_select_words_filters_and_orders(self):
        counts = Counter({"aurora": 3, "que": 9, "luna": 3, "sol": 1, "extraordinariamente": 5})
        options = ExtractOptions(stopwords=frozenset({"que"}))
        self.assertEqual(select_words(counts, options), ["aurora", "luna", "sol"])
        self.assertEqual(select_words(counts, ExtractOptions(min_freq=2, stopwords=options.stopwords)),
                         ["aurora", "luna"])
        self.assertEqual(select_words(counts, ExtractOptions(top=1, stopwords=options.stopwords)),
                         ["aurora"])

    def test_stopwords_multilingual(self):
        stopwords = load_stopwords()
        for word in ("que", "the", "und", "fur", "nao", "chto", "editar"):
            self.assertIn(word, stopwords)
        self.assertNotIn("aurora", stopwords)


class TestFiles(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, content, encoding="utf-8"):
        path = self.dir / name
        path.write_text(content, encoding=encoding)
        return path

    def test_txt_latin1_fallback(self):
        path = self._write("a.txt", "halcón volcán", encoding="latin-1")
        with self.assertLogs("pysion.builder.files", "WARNING"):
            self.assertEqual(read_file(path), "halcón volcán")

    def test_csv_header_and_columns(self):
        path = self._write("d.csv", "id;nombre;info\n1;Odín;dios sabio\n2;Freya;diosa\n")
        self.assertNotIn("nombre", read_file(path))
        self.assertEqual(read_file(path, "nombre").split(), ["Odín", "Freya"])
        self.assertEqual(read_file(path, "3").split(), ["dios", "sabio", "diosa"])
        self.assertIn("nombre", read_file(path, "2", header=False))
        for bad in ("99", "inexistente"):
            with self.subTest(column=bad), self.assertRaises(SourceError):
                read_file(path, bad)
        with self.assertRaises(SourceError):
            read_file(path, "nombre", header=False)

    def test_html_skips_code(self):
        html = "<head><title>T</title></head><p>Asgard &amp; Midgard</p><script>var x=1</script>"
        self.assertEqual(html_to_text(html).split(), ["Asgard", "&", "Midgard"])

    @unittest.skipUnless(HAS_PYPDF, "pypdf no instalado")
    def test_pdf(self):
        path = self.dir / "libro.pdf"
        make_pdf(path, "Valquiria Midgard")
        self.assertIn("Valquiria Midgard", read_file(path))

    def test_invalid_sources(self):
        for path in (self.dir / "no_existe.txt", self._write("x.docx", "hola"), self.dir):
            with self.subTest(path=path.name), self.assertRaises(SourceError):
                read_file(path)


class TestWriter(unittest.TestCase):
    def test_merge_creates_appends_and_never_duplicates(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "dict.txt"
            first = merge_into(target, ["aurora", "luna"], ["a.txt"])
            self.assertEqual(first.added, ("aurora", "luna"))
            second = merge_into(target, ["luna", "sol"], ["b.pdf"])
            self.assertEqual((second.added, second.already_present), (("sol",), 1))
            third = merge_into(target, ["sol"], ["b.pdf"])
            self.assertEqual(third.added, ())
            lines = target.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], HEADER)
            self.assertEqual([l for l in lines if not l.startswith("#")], ["aurora", "luna", "sol"])
            self.assertEqual(list(Path(tmp).iterdir()), [target])  # sin temporales

    def test_comment_cannot_inject_words(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "dict.txt"
            merge_into(target, ["aurora"], ["malo\ninyectada.txt"])
            words = [l for l in target.read_text().splitlines() if not l.startswith("#")]
            self.assertEqual(words, ["aurora"])

    def test_invalid_destinations(self):
        with TemporaryDirectory() as tmp:
            for target in (Path(tmp), Path(tmp) / "no" / "existe.txt"):
                with self.subTest(target=target), self.assertRaises(SourceError):
                    merge_into(target, ["aurora"], ["a.txt"])


class _Handler(BaseHTTPRequestHandler):
    ROUTES = {
        "/robots.txt": (200, "text/plain", "User-agent: *\nDisallow: /privado\n"),
        "/mitos": (200, "text/html; charset=utf-8",
                   "<html><body><p>Odín y Freya en Asgard</p><script>var x</script></body></html>"),
        "/lista.txt": (200, "text/plain", "aurora\nboreal\n"),
        "/privado": (200, "text/html", "<p>secreto</p>"),
        "/logo.png": (200, "image/png", "PNG"),
    }

    def do_GET(self):
        status, ctype, body = self.ROUTES.get(self.path, (404, "text/plain", "no"))
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args):  # silencia el log del servidor en los tests
        pass


class TestWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_html_and_plain_text(self):
        self.assertEqual(web.fetch_text(f"{self.base}/mitos").split(), ["Odín", "y", "Freya", "en", "Asgard"])
        self.assertEqual(web.fetch_text(f"{self.base}/lista.txt").split(), ["aurora", "boreal"])

    def test_rejections(self):
        for url in (f"{self.base}/privado", f"{self.base}/logo.png", f"{self.base}/no-existe",
                    "file:///etc/passwd", "ftp://127.0.0.1/x.txt"):
            with self.subTest(url=url), self.assertRaises(SourceError):
                web.fetch_text(url)

    def test_is_url(self):
        self.assertTrue(web.is_url("https://x.org"))
        self.assertFalse(web.is_url("C:\\datos\\lista.txt"))


class TestBuilderCli(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            try:
                code = main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue()

    def test_end_to_end(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "texto.txt"
            src.write_text("La aurora y la luna. La aurora brilla.", encoding="utf-8")
            code, out = self._run([str(src), "--dry-run"])
            self.assertEqual((code, out.split()), (EXIT_OK, ["aurora", "brilla", "luna"]))
            target = Path(tmp) / "dict.txt"
            self.assertEqual(self._run([str(src), "-o", str(target)])[0], EXIT_OK)
            self.assertEqual(self._run([str(src), "-o", str(target)])[0], EXIT_EMPTY)
            self.assertNotIn(tmp, target.read_text())  # no guarda rutas locales

    def test_errors(self):
        self.assertEqual(self._run(["x.txt"])[0], EXIT_USAGE)  # falta -o
        self.assertEqual(self._run(["x.txt", "--dry-run", "--min-length", "9", "--max-length", "3"])[0],
                         EXIT_USAGE)
        self.assertEqual(self._run(["/no/existe.txt", "--dry-run"])[0], EXIT_SOURCE)


if __name__ == "__main__":
    unittest.main()
