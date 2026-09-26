"""Interfaz de línea de comandos.

Códigos de salida:
    0  éxito (se generaron todos los nombres pedidos)
    1  éxito parcial o sin resultados (filtros demasiado estrictos)
    2  error de uso / parámetros inválidos (argparse o ConfigError)
    3  error cargando diccionarios
    130 interrumpido por el usuario (Ctrl+C)
"""

import argparse
import logging
import random
import sys
from pathlib import Path

from pysion import __version__
from pysion.exceptions import ConfigError, LexiconError
from pysion.generator import GeneratorConfig, generate
from pysion.languages import LanguageProfile, available_languages, load_languages, merge_rules
from pysion.lexicon import available_themes, build_lexicon, load_wordfile, normalize_anchors
from pysion.output import RENDERERS, render_stats
from pysion.phonetics import normalize
from pysion.acronyms import generate_acronyms
from pysion.presets import Preset, apply_format, available_presets, combine_presets
from pysion.rules import PhoneticRules
from pysion.strategies import STRATEGIES

EXIT_OK, EXIT_PARTIAL, EXIT_USAGE, EXIT_LEXICON, EXIT_INTERRUPTED = 0, 1, 2, 3, 130

logger = logging.getLogger("pysion")


def bounded_int(low: int, high: int):
    """Tipo argparse: entero dentro de [low, high]."""
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"'{value}' no es un entero") from None
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f"debe estar entre {low} y {high}")
        return number
    return parse


def _anchor_word(value: str) -> str:
    """Tipo argparse: palabra base válida (error de uso si no lo es)."""
    try:
        return normalize_anchors([value])[0]
    except LexiconError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pysion",
        description="Genera nombres inventados y armónicos para marcas, productos, lugares, usuarios y más.",
    )
    parser.add_argument("-n", "--count", type=bounded_int(1, 1000), default=20,
                        help="cantidad de nombres (1-1000, por defecto 20)")
    parser.add_argument("-t", "--themes", type=_csv_list, default=None,
                        help=f"temas separados por coma. Disponibles: {', '.join(available_themes())}")
    parser.add_argument("-d", "--dict", dest="dicts", type=Path, action="append", default=[],
                        metavar="FICHERO",
                        help="diccionario adicional (una palabra por línea); repetible")
    parser.add_argument("-l", "--lang", dest="langs", type=_csv_list, default=[],
                        help="idiomas separados por coma (diccionario, afijos y reglas "
                             f"fonéticas propias). Disponibles: {', '.join(available_languages())}")
    parser.add_argument("-w", "--word", dest="words", type=_anchor_word, action="append",
                        default=[], metavar="PALABRA",
                        help="palabra base: todos los nombres derivarán de ella; repetible")
    parser.add_argument("--no-themes", "--only-dicts", dest="no_themes", action="store_true",
                        help="no usar los temas incluidos; solo --dict, --word y/o --lang")
    parser.add_argument("--type", dest="preset", type=_csv_list, default=[], metavar="TIPO",
                        help="tipo(s) de nombre separados por coma (fija caso, calificador y "
                             "valores por defecto; p. ej. 'sigla,empresa'). "
                             f"Disponibles: {', '.join(available_presets()) or '(ninguno)'}")
    parser.add_argument("-s", "--strategies", type=_csv_list, default=list(STRATEGIES),
                        help=f"estrategias separadas por coma. Disponibles: {', '.join(STRATEGIES)}")
    parser.add_argument("--min-length", type=bounded_int(3, 20), default=None,
                        help="longitud mínima (por defecto 4, o la del --type)")
    parser.add_argument("--max-length", type=bounded_int(3, 20), default=None,
                        help="longitud máxima (por defecto 10, o la del --type)")
    parser.add_argument("--min-score", type=bounded_int(0, 100), default=70,
                        help="puntuación mínima de armonía 0-100 (por defecto 70)")
    parser.add_argument("--starts-with", default="", help="forzar letra/s inicial/es")
    parser.add_argument("--seed", type=int, default=None,
                        help="semilla para resultados reproducibles")
    parser.add_argument("--history", type=Path, metavar="FICHERO",
                        help="fichero de historial: excluye los nombres que ya contiene "
                             "y añade los nuevos al final (evita repetir entre ejecuciones)")
    parser.add_argument("-f", "--format", choices=RENDERERS, default="text")
    parser.add_argument("--stats", action="store_true",
                        help="mostrar estadísticas de rechazo en stderr")
    parser.add_argument("-v", "--verbose", action="store_true", help="logs de depuración")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _resolve_length(value: int | None, preset_value: int | None, fallback: int) -> int:
    """Longitud efectiva: la del usuario manda, luego el preset, luego el defecto."""
    if value is not None:
        return value
    return preset_value if preset_value is not None else fallback


def _config_from_args(args: argparse.Namespace,
                      languages: list[LanguageProfile],
                      preset: Preset | None) -> GeneratorConfig:
    starts_with = normalize(args.starts_with)
    if args.starts_with and not starts_with:
        raise ConfigError("--starts-with debe contener letras")
    min_len = _resolve_length(args.min_length, preset.min_length if preset else None, 4)
    max_len = _resolve_length(args.max_length, preset.max_length if preset else None, 10)
    return GeneratorConfig(
        count=args.count,
        min_score=float(args.min_score),
        strategies=tuple(args.strategies),
        rules=merge_rules(PhoneticRules(min_length=min_len, max_length=max_len), languages),
        starts_with=starts_with,
        exclude=_load_history(args.history),
    )


def _load_history(path: Path | None) -> frozenset[str]:
    """Nombres ya generados en ejecuciones previas (normalizados)."""
    if path is None or not path.exists():
        return frozenset()
    # Sin límite de longitud: solo interesa reconocer lo ya visto.
    return frozenset(load_wordfile(path, min_len=1, max_len=10_000))


def _append_history(path: Path | None, result) -> None:
    """Añade los nombres nuevos al historial (uno por línea, en minúsculas)."""
    if path is None or not result.names:
        return
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write("".join(f"{n.name}\n" for n in result.names))
    except OSError as exc:
        raise LexiconError(f"No se pudo escribir el historial {path}: {exc}") from exc


def _selected_themes(args: argparse.Namespace) -> list[str] | None:
    """Temas a usar. Con --lang y sin -t explícito no se usan temas: son
    una mezcla español/inglés que diluiría el carácter del idioma."""
    if args.no_themes or (args.langs and args.themes is None):
        return []
    return args.themes


def run(args: argparse.Namespace) -> int:
    preset = combine_presets(args.preset) if args.preset else None
    # Los idiomas del preset solo se aplican si el usuario no indicó -l.
    if preset and preset.languages and not args.langs:
        args.langs = list(preset.languages)

    languages = load_languages(args.langs)
    config = _config_from_args(args, languages, preset)
    rng = random.Random(args.seed)  # no criptográfico: no se necesita

    if preset and preset.mode == "acronym":
        # Las siglas no usan léxico ni estrategias: su propio generador.
        result = generate_acronyms(
            config.count, config.rules.min_length, config.rules.max_length,
            config.exclude, preset.ampersand_ratio, rng,
        )
    else:
        lexicon = build_lexicon(themes=_selected_themes(args), extra_files=args.dicts,
                                anchors=args.words, languages=languages)
        logger.debug("Léxico: %d palabras, %d prefijos, %d sufijos, palabras base: %s, idiomas: %s",
                     len(lexicon.words), len(lexicon.prefixes), len(lexicon.suffixes),
                     ", ".join(lexicon.anchors) or "-",
                     ", ".join(lang.name for lang in languages) or "-")
        result = generate(lexicon, config, rng)

    if preset:
        apply_format(result, preset, rng)

    RENDERERS[args.format](result, sys.stdout)
    if args.stats:
        render_stats(result, sys.stderr)
    _append_history(args.history, result)
    return EXIT_OK if len(result.names) == config.count else EXIT_PARTIAL


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    if args.no_themes and not (args.dicts or args.words or args.langs):
        parser.error("--no-themes requiere al menos un --dict, --word o --lang")

    try:
        return run(args)
    except ConfigError as exc:
        logger.error("%s", exc)
        return EXIT_USAGE
    except LexiconError as exc:
        logger.error("%s", exc)
        return EXIT_LEXICON
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
