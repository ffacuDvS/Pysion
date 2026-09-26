"""Primitivas fonéticas: normalización, patrón CV y silabificación.

Es una aproximación ortográfica (no fonológica real), suficiente para
cortar y unir palabras por fronteras "naturales" en español/inglés.
"""

import re
import unicodedata

from pysion.transliteration import transliterate

VOWELS = frozenset("aeiouy")

# Grupos consonánticos que no se separan al silabificar y que son
# pronunciables al inicio de sílaba (ataque silábico).
INSEPARABLE_CLUSTERS = frozenset({
    "bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "kr", "pl",
    "pr", "tr", "ch", "sh", "th", "ph", "st", "sk", "sp",
})

# Grupos de letras que representan un solo sonido y nunca se separan.
# Ordenados de más largo a más corto para reconocer 'shch' antes que 'sh'.
DIGRAPHS = ("shch", "sch", "ch", "sh", "th", "ph", "kh", "zh", "gh")

# Longitud mínima de `head` para recortarle la vocal final en join_smooth.
MIN_HEAD_TO_TRIM = 2

_VOWEL_RUN = re.compile(r"[aeiouy]+")
_NON_ALPHA = re.compile(r"[^a-z]")


def normalize(text: str) -> str:
    """Pasa a minúsculas ASCII: translitera (ж->zh, ß->ss), quita acentos
    (á->a, ñ->n) y elimina todo lo que no sea letra."""
    decomposed = unicodedata.normalize("NFKD", transliterate(text.lower()))
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NON_ALPHA.sub("", ascii_only.lower())


def is_vowel(char: str) -> bool:
    return char in VOWELS


def cv_pattern(word: str) -> str:
    """Devuelve el patrón consonante/vocal, p.ej. 'luna' -> 'CVCV'."""
    return "".join("V" if is_vowel(c) else "C" for c in word)


def consonant_units(cluster: str) -> list[str]:
    """Divide un grupo de consonantes en unidades: los dígrafos cuentan como
    una sola ('shcht' -> ['shch', 't'])."""
    units = []
    i = 0
    while i < len(cluster):
        unit = next((d for d in DIGRAPHS if cluster.startswith(d, i)), cluster[i])
        units.append(unit)
        i += len(unit)
    return units


def _split_offset(cluster: str) -> int:
    """Posición donde cortar un grupo de consonantes entre dos vocales.

    - 0 o 1 unidad: la consonante inicia la siguiente sílaba (lu-na, za-shchi-ta).
    - Si termina en grupo inseparable: se deja entero a la derecha (ma-tri-x).
    - En otro caso: solo la última unidad pasa a la derecha (sil-va, mech-ta).
    """
    units = consonant_units(cluster)
    if len(units) <= 1:
        return 0
    if units[-2] + units[-1] in INSEPARABLE_CLUSTERS:
        return len("".join(units[:-2]))
    return len("".join(units[:-1]))


def syllabify(word: str) -> list[str]:
    """Divide una palabra normalizada en sílabas aproximadas."""
    if not word:
        return []
    nuclei = [(m.start(), m.end()) for m in _VOWEL_RUN.finditer(word)]
    if len(nuclei) <= 1:
        return [word]

    syllables: list[str] = []
    start = 0
    for (_, vowel_end), (next_vowel_start, _) in zip(nuclei, nuclei[1:]):
        cluster = word[vowel_end:next_vowel_start]
        cut = vowel_end + _split_offset(cluster)
        syllables.append(word[start:cut])
        start = cut
    syllables.append(word[start:])
    return syllables


def join_smooth(head: str, tail: str) -> str:
    """Une dos fragmentos suavizando la juntura.

    - Letra repetida en la unión: se funde (sol + luna -> soluna).
    - Vocal + vocal: se elimina la vocal final de `head` para conservar
      intacto el sufijo/final (nova + ia -> novia, terra + ium -> terrium).
      Si `head` es muy corto (py, lu) se recorta `tail` en su lugar para no
      perder la raíz (py + ino -> pyno).
    - Consonante + consonante no inseparable: se elimina la última de `head`,
      salvo que forme parte de un dígrafo (hoch + stall -> hochstall, no hocstall).
    """
    if not head or not tail:
        return head + tail
    last, first = head[-1], tail[0]
    if last == first:
        return head + tail[1:]
    if is_vowel(last) and is_vowel(first):
        return head[:-1] + tail if len(head) > MIN_HEAD_TO_TRIM else head + tail[1:]
    if not is_vowel(last) and not is_vowel(first):
        breaks_digraph = head.endswith(DIGRAPHS)
        if last + first not in INSEPARABLE_CLUSTERS and len(head) > 1 and not breaks_digraph:
            return head[:-1] + tail
    return head + tail
