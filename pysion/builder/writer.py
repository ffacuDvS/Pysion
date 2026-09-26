"""Fusión de palabras nuevas en un diccionario .txt existente o nuevo.

- Nunca duplica: solo añade palabras que el fichero aún no contiene.
- Conserva el contenido previo (incluidos comentarios) y añade al final.
- Escritura atómica: se escribe un temporal y se renombra, así un error a
  mitad de camino nunca deja el diccionario corrupto o a medias.
"""

import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pysion.exceptions import LexiconError, SourceError
from pysion.lexicon import load_wordfile

HEADER = "# Diccionario generado por pysion.builder (una palabra por línea)"
MAX_COMMENT_LEN = 300
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class MergeResult:
    path: Path
    added: tuple[str, ...]
    already_present: int


def _existing_words(path: Path) -> set[str]:
    # Sin límite de longitud: se trata de detectar duplicados, no de filtrar.
    return set(load_wordfile(path, min_len=1, max_len=10_000)) if path.exists() else set()


def _comment(sources: list[str], count: int) -> str:
    """Línea de comentario con el origen. Se eliminan los caracteres de control:
    un salto de línea en un nombre de fichero convertiría texto en 'palabras'."""
    origin = _CONTROL_CHARS.sub(" ", ", ".join(sources))[:MAX_COMMENT_LEN]
    return f"# {date.today().isoformat()}: {count} palabras desde {origin}"


def _atomic_write(path: Path, content: str) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def merge_into(path: Path, words: list[str], sources: list[str]) -> MergeResult:
    """Añade a `path` las palabras de `words` que no estén ya en él."""
    if path.is_dir():
        raise SourceError(f"La salida es un directorio, no un fichero: {path}")
    if not path.parent.is_dir():
        raise SourceError(f"No existe la carpeta de destino: {path.parent}")

    try:
        existing = _existing_words(path)
        new_words = tuple(w for w in words if w not in existing)
        if new_words:
            previous = path.read_text(encoding="utf-8") if path.exists() else HEADER + "\n"
            if previous and not previous.endswith("\n"):
                previous += "\n"
            block = "\n".join([_comment(sources, len(new_words)), *new_words])
            _atomic_write(path, f"{previous}{block}\n")
    except LexiconError as exc:  # el destino existe pero no es un .txt válido
        raise SourceError(str(exc)) from exc
    except OSError as exc:
        raise SourceError(f"No se pudo escribir {path}: {exc}") from exc
    return MergeResult(path, new_words, len(words) - len(new_words))
