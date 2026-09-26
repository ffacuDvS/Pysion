"""De texto libre a una lista de palabras candidatas, contadas y filtradas."""

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Iterator

from pysion.lexicon import DATA_DIR, MAX_WORD_LEN, MIN_WORD_LEN, load_wordfile
from pysion.phonetics import normalize

STOPWORDS_FILE = DATA_DIR / "stopwords.txt"

# Secuencias de letras de cualquier alfabeto (sin dígitos ni '_'), para que
# "e-mail", "l'aurora" o "Жар-птица" se separen en palabras.
_TOKEN = re.compile(r"[^\W\d_]+")


@dataclass(frozen=True)
class ExtractOptions:
    min_length: int = MIN_WORD_LEN
    max_length: int = MAX_WORD_LEN
    min_freq: int = 1
    top: int | None = None
    stopwords: frozenset[str] = frozenset()


def load_stopwords() -> frozenset[str]:
    """Palabras vacías (artículos, preposiciones...) en los idiomas incluidos."""
    return frozenset(load_wordfile(STOPWORDS_FILE, min_len=1))


def tokenize(text: str) -> Iterator[str]:
    """Palabras normalizadas a a-z (translitera cirílico, quita acentos)."""
    for match in _TOKEN.finditer(text):
        word = normalize(match.group())
        if word:
            yield word


def count_words(texts: Iterable[str]) -> Counter:
    counts: Counter = Counter()
    for text in texts:
        counts.update(tokenize(text))
    return counts


def select_words(counts: Counter, options: ExtractOptions) -> list[str]:
    """Aplica los filtros y ordena de más a menos frecuente (empate: alfabético)."""
    selected = [
        word for word, total in counts.items()
        if options.min_length <= len(word) <= options.max_length
        and total >= options.min_freq
        and word not in options.stopwords
    ]
    selected.sort(key=lambda w: (-counts[w], w))
    return selected[:options.top] if options.top else selected
