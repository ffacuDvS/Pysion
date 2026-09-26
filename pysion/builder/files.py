"""Lectura de fuentes locales: texto, CSV/TSV, HTML y PDF.

Cada lector recibe una ruta y devuelve el texto plano que contiene. Para
admitir un formato nuevo basta con escribir su lector y registrarlo en READERS.
"""

import csv
import io
import logging
from pathlib import Path
from typing import Callable

from pysion.builder.html_text import html_to_text
from pysion.exceptions import SourceError

logger = logging.getLogger(__name__)

# Más holgado que el de los diccionarios: aquí las fuentes pueden ser libros.
MAX_SOURCE_BYTES = 50 * 1024 * 1024
CSV_DELIMITERS = ",;\t|"
CSV_SNIFF_BYTES = 64 * 1024


def _check_file(path: Path) -> None:
    if not path.is_file():
        raise SourceError(f"No existe o no es un fichero regular: {path}")
    size = path.stat().st_size
    if size > MAX_SOURCE_BYTES:
        raise SourceError(f"Fichero demasiado grande ({size} bytes > {MAX_SOURCE_BYTES}): {path}")


def _read_text(path: Path) -> str:
    """Lee texto en UTF-8 (con o sin BOM); si falla, en Latin-1.

    Latin-1 nunca falla al decodificar y cubre los ficheros antiguos de
    Windows en español, portugués, italiano o alemán.
    """
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        logger.warning("%s no es UTF-8; se lee como Latin-1", path)
        return raw.decode("latin-1")


def read_plain(path: Path, column: str | None = None, header: bool = True) -> str:
    return _read_text(path)


def read_html(path: Path, column: str | None = None, header: bool = True) -> str:
    return html_to_text(_read_text(path))


def _column_index(header: list[str], column: str) -> int:
    """Traduce `column` (nombre o número desde 1) a un índice de lista."""
    if column.isdigit():
        index = int(column) - 1
        if index < 0 or index >= len(header):
            raise SourceError(f"Columna {column} fuera de rango (hay {len(header)})")
        return index
    names = [h.strip().lower() for h in header]
    if column.strip().lower() not in names:
        raise SourceError(f"No existe la columna '{column}'. Columnas: {', '.join(header)}")
    return names.index(column.strip().lower())


def read_csv(path: Path, column: str | None = None, header: bool = True) -> str:
    """Texto de todas las celdas, o solo de `column` (nombre o número).

    Con `header` la primera fila se considera cabecera y no aporta palabras
    ('nombre', 'descripcion'...). Las columnas por nombre la necesitan.
    """
    text = _read_text(path)
    try:
        dialect = csv.Sniffer().sniff(text[:CSV_SNIFF_BYTES], delimiters=CSV_DELIMITERS)
    except csv.Error:
        dialect = csv.excel_tab if path.suffix.lower() == ".tsv" else csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    if not rows:
        return ""
    if column is not None and not column.isdigit() and not header:
        raise SourceError("Para elegir la columna por nombre, el CSV necesita cabecera")
    body = rows[1:] if header else rows
    if column is None:
        return "\n".join(" ".join(row) for row in body)
    index = _column_index(rows[0], column)
    return "\n".join(row[index] for row in body if index < len(row))


def read_pdf(path: Path, column: str | None = None, header: bool = True) -> str:
    """Texto de todas las páginas. Requiere `pypdf` (dependencia opcional)."""
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError:
        raise SourceError(
            "Para leer PDF instala la dependencia opcional: pip install pypdf"
        ) from None
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise SourceError(f"El PDF está protegido con contraseña: {path}")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PyPdfError, ValueError, KeyError) as exc:
        raise SourceError(f"No se pudo leer el PDF {path}: {exc}") from exc


Reader = Callable[[Path, "str | None", bool], str]

READERS: dict[str, Reader] = {
    ".txt": read_plain,
    ".md": read_plain,
    ".text": read_plain,
    ".csv": read_csv,
    ".tsv": read_csv,
    ".html": read_html,
    ".htm": read_html,
    ".pdf": read_pdf,
}


def read_file(path: Path, column: str | None = None, header: bool = True) -> str:
    """Lee una fuente local eligiendo el lector por su extensión."""
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        raise SourceError(
            f"Formato no soportado: '{path.suffix or '(sin extensión)'}'. "
            f"Admitidos: {', '.join(sorted(READERS))}"
        )
    _check_file(path)
    if column is not None and reader is not read_csv:
        logger.warning("--column solo se aplica a CSV/TSV; se ignora en %s", path)
    try:
        return reader(path, column, header)
    except OSError as exc:
        raise SourceError(f"No se pudo leer {path}: {exc}") from exc
