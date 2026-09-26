"""Carga y saneamiento de diccionarios (temas incluidos + ficheros del usuario)."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from pysion.exceptions import LexiconError
from pysion.phonetics import normalize

if TYPE_CHECKING:  # solo para anotaciones: evita importación circular
    from pysion.languages import LanguageProfile

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
THEMES_DIR = DATA_DIR / "themes"

MAX_FILE_BYTES = 5 * 1024 * 1024  # evita cargar ficheros gigantes por error
MIN_WORD_LEN = 3
MAX_WORD_LEN = 14
MIN_WORDS_REQUIRED = 2  # las estrategias combinan al menos dos palabras
AFFIX_MIN_LEN = 2  # admite sufijos cortos como 'ia' u 'on'


@dataclass(frozen=True)
class Lexicon:
    """Material de construcción disponible para las estrategias."""

    words: tuple[str, ...]
    prefixes: tuple[str, ...]
    suffixes: tuple[str, ...]
    # Palabras base del usuario (-w): si hay, todo nombre debe derivar de una.
    anchors: tuple[str, ...] = ()

    @property
    def known_words(self) -> frozenset[str]:
        """Palabras reales: se usan para descartar nombres no inventados."""
        return frozenset(self.words)


def available_themes() -> list[str]:
    """Nombres de los temas incluidos (ficheros data/themes/*.txt)."""
    return sorted(p.stem for p in THEMES_DIR.glob("*.txt"))


def read_text_file(path: Path) -> str:
    """Lee un fichero de texto de forma defensiva (tipo, tamaño, encoding)."""
    if not path.is_file():
        raise LexiconError(f"No existe o no es un fichero regular: {path}")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise LexiconError(
            f"Fichero demasiado grande ({size} bytes > {MAX_FILE_BYTES}): {path}"
        )
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise LexiconError(f"El fichero no es UTF-8 válido: {path}") from exc
    except OSError as exc:
        raise LexiconError(f"No se pudo leer {path}: {exc}") from exc


def load_wordfile(
    path: Path, min_len: int = MIN_WORD_LEN, max_len: int = MAX_WORD_LEN
) -> list[str]:
    """Carga un diccionario: una palabra por línea, '#' inicia comentario.

    Admite ficheros tipo /usr/share/dict/words: solo se conservan tokens que
    tras normalizar quedan entre `min_len` y `max_len` letras.
    """
    words = []
    for raw in read_text_file(path).splitlines():
        token = raw.split("#", 1)[0].strip()
        if not token or " " in token:
            continue
        word = normalize(token)
        if min_len <= len(word) <= max_len:
            words.append(word)
    logger.debug("Cargadas %d palabras de %s", len(words), path)
    return words


def _dedupe(items: Iterable[str]) -> tuple[str, ...]:
    """Elimina duplicados preservando el orden (resultado determinista)."""
    return tuple(dict.fromkeys(items))


def normalize_anchors(raw_words: Iterable[str]) -> tuple[str, ...]:
    """Normaliza y valida las palabras base indicadas por el usuario."""
    anchors = []
    for raw in raw_words:
        word = normalize(raw)
        if not MIN_WORD_LEN <= len(word) <= MAX_WORD_LEN:
            raise LexiconError(
                f"Palabra base inválida '{raw}': debe tener entre "
                f"{MIN_WORD_LEN} y {MAX_WORD_LEN} letras (sin contar símbolos)."
            )
        anchors.append(word)
    return _dedupe(anchors)


def build_lexicon(
    themes: Iterable[str] | None = None,
    extra_files: Iterable[Path] = (),
    anchors: Iterable[str] = (),
    languages: Iterable["LanguageProfile"] = (),
) -> Lexicon:
    """Construye el léxico a partir de temas, ficheros, palabras base e idiomas.

    Si `themes` es None se usan todos los temas incluidos. Las palabras base
    también se añaden a `words`: así pueden combinarse entre sí y se descartan
    como resultado (no son nombres inventados).

    Con idiomas, sus diccionarios se suman a `words` y sus prefijos/sufijos
    sustituyen a los genéricos, para que los afijos suenen a ese idioma.
    """
    languages = list(languages)
    anchor_words = normalize_anchors(anchors)
    valid_themes = available_themes()
    selected = valid_themes if themes is None else list(themes)
    unknown = sorted(set(selected) - set(valid_themes))
    if unknown:
        raise LexiconError(
            f"Temas desconocidos: {', '.join(unknown)}. "
            f"Disponibles: {', '.join(valid_themes)}"
        )

    words: list[str] = []
    for theme in selected:
        words.extend(load_wordfile(THEMES_DIR / f"{theme}.txt"))
    for path in extra_files:
        words.extend(load_wordfile(Path(path).expanduser()))
    for language in languages:
        words.extend(language.words)

    unique_words = _dedupe([*anchor_words, *words])
    # Con una palabra base basta: las estrategias con un solo origen
    # (mutate, root_suffix, prefix_root) pueden trabajar con ella.
    min_required = 1 if anchor_words else MIN_WORDS_REQUIRED
    if len(unique_words) < min_required:
        raise LexiconError(
            f"Se necesitan al menos {min_required} palabras válidas; "
            f"hay {len(unique_words)}."
        )

    if languages:
        prefixes = _dedupe(p for lang in languages for p in lang.prefixes)
        suffixes = _dedupe(s for lang in languages for s in lang.suffixes)
    else:
        prefixes = _dedupe(load_wordfile(DATA_DIR / "prefixes.txt", min_len=AFFIX_MIN_LEN))
        suffixes = _dedupe(load_wordfile(DATA_DIR / "suffixes.txt", min_len=AFFIX_MIN_LEN))

    return Lexicon(
        words=unique_words,
        prefixes=prefixes,
        suffixes=suffixes,
        anchors=anchor_words,
    )
