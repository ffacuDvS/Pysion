"""Interfaz de línea de comandos del constructor de diccionarios.

Códigos de salida (mismos criterios que `python -m pysion`):
    0  éxito: se añadieron palabras (o se listaron con --dry-run)
    1  no hay palabras nuevas que añadir
    2  error de uso / parámetros inválidos
    3  error leyendo una fuente o escribiendo la salida
    130 interrumpido por el usuario (Ctrl+C)
"""

import argparse
import logging
import sys
from pathlib import Path

from pysion import __version__
from pysion.builder.extract import ExtractOptions, count_words, load_stopwords, select_words
from pysion.builder.files import READERS, read_file
from pysion.builder.web import fetch_text, is_url
from pysion.builder.writer import merge_into
from pysion.cli import bounded_int
from pysion.exceptions import SourceError

EXIT_OK, EXIT_EMPTY, EXIT_USAGE, EXIT_SOURCE, EXIT_INTERRUPTED = 0, 1, 2, 3, 130

logger = logging.getLogger("pysion.builder")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pysion.builder",
        description="Crea o amplía un diccionario .txt con palabras extraídas de "
                    "ficheros o páginas web.",
    )
    parser.add_argument("sources", nargs="+", metavar="FUENTE",
                        help=f"fichero ({', '.join(sorted(READERS))}) o URL http(s)")
    parser.add_argument("-o", "--output", type=Path,
                        help="diccionario .txt de destino (se crea o se amplía)")
    parser.add_argument("--dry-run", action="store_true",
                        help="mostrar las palabras por pantalla sin escribir nada")
    parser.add_argument("--column", help="solo CSV/TSV: columna por nombre o número (desde 1)")
    parser.add_argument("--no-header", dest="header", action="store_false",
                        help="solo CSV/TSV: la primera fila son datos, no cabecera")
    parser.add_argument("--min-length", type=bounded_int(1, 30), default=3)
    parser.add_argument("--max-length", type=bounded_int(1, 30), default=14)
    parser.add_argument("--min-freq", type=bounded_int(1, 1_000_000), default=1,
                        help="apariciones mínimas de una palabra en las fuentes")
    parser.add_argument("--top", type=bounded_int(1, 1_000_000), default=None,
                        help="quedarse solo con las N palabras más frecuentes")
    parser.add_argument("--keep-stopwords", action="store_true",
                        help="no descartar palabras vacías (artículos, preposiciones...)")
    parser.add_argument("-v", "--verbose", action="store_true", help="logs de depuración")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def read_source(source: str, column: str | None, header: bool = True) -> str:
    """Texto de una fuente: URL si lleva esquema (http://...), si no, fichero."""
    logger.info("Leyendo %s", source)
    if is_url(source):
        return fetch_text(source)
    return read_file(Path(source).expanduser(), column, header)


def _source_label(source: str) -> str:
    """Nombre de la fuente para el comentario del diccionario: la URL completa
    o solo el nombre del fichero (no se publica la estructura de carpetas)."""
    return source if is_url(source) else Path(source).name


def _options(args: argparse.Namespace) -> ExtractOptions:
    return ExtractOptions(
        min_length=args.min_length,
        max_length=args.max_length,
        min_freq=args.min_freq,
        top=args.top,
        stopwords=frozenset() if args.keep_stopwords else load_stopwords(),
    )


def run(args: argparse.Namespace) -> int:
    counts = count_words(read_source(src, args.column, args.header) for src in args.sources)
    words = select_words(counts, _options(args))
    logger.info("Palabras distintas: %d | tras filtros: %d", len(counts), len(words))

    if args.dry_run:
        sys.stdout.write("".join(f"{w}\n" for w in words))
        return EXIT_OK if words else EXIT_EMPTY

    result = merge_into(args.output, words, [_source_label(src) for src in args.sources])
    sys.stderr.write(
        f"Fuentes: {len(args.sources)} | palabras distintas: {len(counts)} | "
        f"tras filtros: {len(words)} | añadidas: {len(result.added)} | "
        f"ya existían: {result.already_present} -> {result.path}\n"
    )
    return EXIT_OK if result.added else EXIT_EMPTY


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    if not args.dry_run and args.output is None:
        parser.error("indica el fichero de destino con -o/--output (o usa --dry-run)")
    if args.min_length > args.max_length:
        parser.error("--min-length no puede ser mayor que --max-length")

    try:
        return run(args)
    except SourceError as exc:
        logger.error("%s", exc)
        return EXIT_SOURCE
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
