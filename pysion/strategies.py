"""Estrategias de construcción de nombres.

Cada estrategia es una función `(rng, lexicon, anchor) -> Candidate | None`
y se registra en STRATEGIES. Para añadir una nueva basta con escribir la
función y añadirla al diccionario: el generador y la CLI la detectan solos.

`anchor` es una palabra base del usuario (-w) o None. Si llega, la estrategia
debe usarla como uno de sus orígenes, de modo que el nombre derive de ella.
"""

import random
from dataclasses import dataclass
from typing import Callable, Sequence

from pysion.lexicon import Lexicon
from pysion.phonetics import is_vowel, join_smooth, syllabify


@dataclass(frozen=True)
class Candidate:
    name: str
    strategy: str
    sources: tuple[str, ...]


Strategy = Callable[[random.Random, Lexicon, "str | None"], "Candidate | None"]

# Sustituciones "estilizadas" típicas de naming (c->k, i->y...).
STYLE_SWAPS = {"c": "k", "s": "z", "i": "y", "f": "ph", "qu": "k", "v": "w"}
VOWEL_SHIFTS = {"a": "o", "o": "a", "e": "i", "i": "e", "u": "o"}
SOFT_CLOSINGS = ("a", "o", "ia", "on", "ix")


def _pick(rng: random.Random, items: Sequence[str], k: int) -> list[str]:
    """Elige k elementos distintos (o menos si no hay suficientes)."""
    return rng.sample(list(items), min(k, len(items)))


def _pick_words(
    rng: random.Random, lex: Lexicon, anchor: str | None, k: int
) -> list[str]:
    """Elige k palabras distintas; si hay ancla, siempre está incluida.

    El ancla ocupa una posición aleatoria para que a veces aporte el inicio
    del nombre y otras el final. Puede devolver menos de k palabras si el
    léxico no tiene suficientes compañeras.
    """
    if anchor is None:
        return _pick(rng, lex.words, k)
    partners = _pick(rng, [w for w in lex.words if w != anchor], k - 1)
    partners.insert(rng.randint(0, len(partners)), anchor)
    return partners


def _one_word(rng: random.Random, lex: Lexicon, anchor: str | None) -> str:
    """Palabra única de origen: el ancla si existe, si no una al azar."""
    return anchor if anchor is not None else rng.choice(lex.words)


def _head(rng: random.Random, word: str) -> str:
    """Primeras 1..n-1 sílabas de una palabra (o la palabra si es monosílaba)."""
    syls = syllabify(word)
    if len(syls) == 1:
        return word
    return "".join(syls[:rng.randint(1, len(syls) - 1)])


def _tail(rng: random.Random, word: str) -> str:
    """Últimas 1..n-1 sílabas de una palabra (o la palabra si es monosílaba)."""
    syls = syllabify(word)
    if len(syls) == 1:
        return word
    return "".join(syls[rng.randint(1, len(syls) - 1):])


def blend(rng: random.Random, lex: Lexicon, anchor: str | None = None) -> Candidate | None:
    """Portmanteau: inicio de A + final de B (luna+aurora)."""
    picked = _pick_words(rng, lex, anchor, 2)
    if len(picked) < 2:
        return None
    a, b = picked
    return Candidate(join_smooth(_head(rng, a), _tail(rng, b)), "blend", (a, b))


def syllable_mix(rng: random.Random, lex: Lexicon, anchor: str | None = None) -> Candidate | None:
    """Sílaba inicial de A + (sílaba de B) + sílaba final de C."""
    picked = _pick_words(rng, lex, anchor, rng.choice((2, 3)))
    if len(picked) < 2:
        return None
    first = syllabify(picked[0])[0]
    middle = [rng.choice(syllabify(w)) for w in picked[1:-1]]
    last = syllabify(picked[-1])[-1]
    name = first
    for part in (*middle, last):
        name = join_smooth(name, part)
    return Candidate(name, "syllable_mix", tuple(picked))


def root_suffix(rng: random.Random, lex: Lexicon, anchor: str | None = None) -> Candidate | None:
    """Raíz (primeras sílabas) + sufijo comercial (terra -> terrix)."""
    if not lex.suffixes:
        return None
    word = _one_word(rng, lex, anchor)
    suffix = rng.choice(lex.suffixes)
    return Candidate(join_smooth(_head(rng, word), suffix), "root_suffix", (word, suffix))


def prefix_root(rng: random.Random, lex: Lexicon, anchor: str | None = None) -> Candidate | None:
    """Prefijo de marca + final de palabra (neo + lumen -> neomen)."""
    if not lex.prefixes:
        return None
    word = _one_word(rng, lex, anchor)
    prefix = rng.choice(lex.prefixes)
    return Candidate(join_smooth(prefix, _tail(rng, word)), "prefix_root", (prefix, word))


def _shift_vowel(rng: random.Random, word: str) -> str:
    positions = [i for i, c in enumerate(word) if c in VOWEL_SHIFTS]
    if not positions:
        return word
    i = rng.choice(positions)
    return word[:i] + VOWEL_SHIFTS[word[i]] + word[i + 1:]


def _style_swap(rng: random.Random, word: str) -> str:
    options = [src for src in STYLE_SWAPS if src in word]
    if not options:
        return word
    src = rng.choice(options)
    return word.replace(src, STYLE_SWAPS[src], 1)


def _soft_close(rng: random.Random, word: str) -> str:
    """Recorta la última sílaba y cierra con una terminación suave."""
    syls = syllabify(word)
    base = "".join(syls[:-1]) if len(syls) > 1 else word
    return join_smooth(base, rng.choice(SOFT_CLOSINGS))


MUTATIONS = (_shift_vowel, _style_swap, _soft_close)


def mutate(rng: random.Random, lex: Lexicon, anchor: str | None = None) -> Candidate | None:
    """Aplica 1-2 mutaciones a una palabra real (cobalt -> kobalo)."""
    word = _one_word(rng, lex, anchor)
    name = word
    for mutation in rng.sample(MUTATIONS, rng.randint(1, 2)):
        name = mutation(rng, name)
    # La estilización puede generar vocal+vocal nuevas; se revalidan en rules.
    if name == word or not any(is_vowel(c) for c in name):
        return None
    return Candidate(name, "mutate", (word,))


STRATEGIES: dict[str, Strategy] = {
    "blend": blend,
    "syllable_mix": syllable_mix,
    "root_suffix": root_suffix,
    "prefix_root": prefix_root,
    "mutate": mutate,
}
