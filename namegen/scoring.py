"""Puntuación de "armonía" (0-100) para ordenar nombres ya válidos.

Las reglas (rules.py) descartan lo impronunciable; este módulo prioriza lo
que además suena bien como marca. Cada componente devuelve un valor 0..1 y
se combinan con pesos ajustables en WEIGHTS.
"""

from namegen.phonetics import VOWELS, cv_pattern, syllabify

WEIGHTS = {
    "length": 0.20,
    "vowel_ratio": 0.20,
    "alternation": 0.25,
    "syllables": 0.15,
    "ending": 0.10,
    "variety": 0.10,
}

IDEAL_LENGTH = (5, 8)
IDEAL_VOWEL_RATIO = (0.35, 0.55)
IDEAL_SYLLABLES = (2, 3)
SOFT_ENDINGS = frozenset("aeiouynrslxm")


def _range_score(value: float, low: float, high: float, falloff: float) -> float:
    """1.0 dentro de [low, high]; decae linealmente fuera según `falloff`."""
    if low <= value <= high:
        return 1.0
    distance = low - value if value < low else value - high
    return max(0.0, 1.0 - distance / falloff)


def _alternation(word: str) -> float:
    """Proporción de transiciones consonante<->vocal (CVCV = 1.0)."""
    pattern = cv_pattern(word)
    if len(pattern) < 2:
        return 0.0
    changes = sum(a != b for a, b in zip(pattern, pattern[1:]))
    return changes / (len(pattern) - 1)


def _variety(word: str, syllables: list[str]) -> float:
    """Penaliza monotonía: vocales repetidas ('bababa') o sílabas duplicadas."""
    distinct_vowels = len({c for c in word if c in VOWELS})
    vowel_part = min(distinct_vowels, 3) / 3
    repeated = len(syllables) - len(set(syllables))
    return max(0.0, vowel_part - 0.3 * repeated)


def component_scores(word: str) -> dict[str, float]:
    """Desglose por componente (útil para auditar por qué puntúa un nombre)."""
    syllables = syllabify(word)
    vowel_ratio = sum(c in VOWELS for c in word) / len(word)
    return {
        "length": _range_score(len(word), *IDEAL_LENGTH, falloff=4),
        "vowel_ratio": _range_score(vowel_ratio, *IDEAL_VOWEL_RATIO, falloff=0.3),
        "alternation": _alternation(word),
        "syllables": _range_score(len(syllables), *IDEAL_SYLLABLES, falloff=2),
        "ending": 1.0 if word[-1] in SOFT_ENDINGS else 0.5,
        "variety": _variety(word, syllables),
    }


def harmony_score(word: str) -> float:
    """Puntuación ponderada 0-100 redondeada a un decimal."""
    if not word:
        return 0.0
    scores = component_scores(word)
    total = sum(WEIGHTS[name] * value for name, value in scores.items())
    return round(100 * total, 1)
