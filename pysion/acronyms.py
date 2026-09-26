"""Generador de siglas y acrónimos (IBM, IKEA, BMW, H&H).

No usa el léxico ni las estrategias de mezcla: una sigla es una secuencia
corta de letras, no una palabra silábica, así que tiene su propio camino.
Reutiliza `ScoredName` y `GenerationResult` para encajar con la salida, el
historial y el pipe hacia `pysion.check`.
"""

import random
from collections import Counter

from pysion.generator import GenerationResult, ScoredName

VOWELS = "aeiou"
# Consonantes comunes (como en las siglas reales) frente a las raras (j, q, x...).
COMMON_CONSONANTS = "bcdfghklmnprstv"
RARE_CONSONANTS = "jqwxyz"
CONSONANTS = COMMON_CONSONANTS + RARE_CONSONANTS
LETTERS = CONSONANTS + VOWELS

# Reparto de estilos: la mayoría iniciales (IBM, HSBC), algunas pronunciables (IKEA).
CONSONANT_BIAS = 0.72          # en las iniciales, peso de consonante sobre vocal
RARE_CONSONANT_RATIO = 0.12    # cada tanto una letra rara, para que no sea monótono
PRONOUNCEABLE_RATIO = 0.35     # proporción de siglas legibles como palabra


def _consonant(rng: random.Random) -> str:
    pool = RARE_CONSONANTS if rng.random() < RARE_CONSONANT_RATIO else COMMON_CONSONANTS
    return rng.choice(pool)


def _pronounceable(rng: random.Random, length: int) -> str:
    """Alterna consonante y vocal para que se lea como palabra (tipo IKEA)."""
    start_vowel = rng.random() < 0.4
    letters = []
    for i in range(length):
        is_vowel = (i % 2 == 0) == start_vowel
        letters.append(rng.choice(VOWELS) if is_vowel else _consonant(rng))
    return "".join(letters)


def _initialism(rng: random.Random, length: int) -> str:
    """Letras sueltas, con más consonantes (tipo IBM, HSBC, BMW)."""
    letters = [
        _consonant(rng) if rng.random() < CONSONANT_BIAS else rng.choice(VOWELS)
        for _ in range(length)
    ]
    return "".join(letters)


def _one_acronym(rng: random.Random, length: int, ampersand_ratio: float) -> tuple[str, str]:
    """Devuelve (canónico en minúsculas, forma mostrada).

    La forma mostrada va en mayúsculas y puede llevar '&' (H&H); el canónico
    solo tiene letras a-z, para usarlo como usuario o dominio.
    """
    if length == 2 and rng.random() < ampersand_ratio:
        a = rng.choice(LETTERS)
        b = a if rng.random() < 0.5 else rng.choice(LETTERS)
        return a + b, f"{a.upper()}&{b.upper()}"
    make = _pronounceable if rng.random() < PRONOUNCEABLE_RATIO else _initialism
    letters = make(rng, length)
    return letters, letters.upper()


def _score(canonical: str) -> float:
    """Puntuación orientativa: premia variedad de letras y tener alguna vocal."""
    distinct = len(set(canonical)) / len(canonical)
    has_vowel = any(c in VOWELS for c in canonical)
    return round(min(100.0, 60 + 30 * distinct + (10 if has_vowel else 0)), 1)


def generate_acronyms(
    count: int,
    min_length: int,
    max_length: int,
    exclude: frozenset[str],
    ampersand_ratio: float,
    rng: random.Random,
    attempts_per_name: int = 200,
) -> GenerationResult:
    """Genera `count` siglas únicas, ordenadas por puntuación."""
    low = max(2, min_length)
    high = max(low, max_length)
    max_attempts = count * attempts_per_name

    accepted: list[ScoredName] = []
    seen: set[str] = set()
    rejections: Counter = Counter()
    attempts = 0

    while len(accepted) < count and attempts < max_attempts:
        attempts += 1
        canonical, shown = _one_acronym(rng, rng.randint(low, high), ampersand_ratio)
        if canonical in exclude:
            rejections["en_historial"] += 1
            continue
        if canonical in seen:
            rejections["duplicado"] += 1
            continue
        seen.add(canonical)
        accepted.append(ScoredName(canonical, _score(canonical), "sigla", (), base_display=shown))

    accepted.sort(key=lambda n: (-n.score, n.name))
    return GenerationResult(accepted, attempts, rejections)
