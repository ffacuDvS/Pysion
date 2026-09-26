"""Reglas duras de pronunciabilidad.

Cada regla devuelve un identificador cuando se incumple. Así el generador
puede contar motivos de rechazo (útil para depurar y ajustar reglas).

Los conjuntos de letras son campos de PhoneticRules: los valores por defecto
(mezcla español/inglés) se pueden sustituir por los de un perfil de idioma.
"""

import re
from dataclasses import dataclass

from pysion.phonetics import INSEPARABLE_CLUSTERS, consonant_units, cv_pattern

# Dobles letras aceptables (existen en español/inglés y se leen con naturalidad).
ALLOWED_DOUBLES = frozenset({"ll", "rr", "ss", "nn", "tt", "ee", "oo", "mm", "ff"})

# Combinaciones difíciles de pronunciar o de aspecto "roto".
FORBIDDEN_BIGRAMS = frozenset({
    "jx", "xj", "xz", "zx", "vw", "wv", "wq", "kq", "gq", "fq", "vq", "bx",
    "cx", "dx", "vx", "hx", "jq", "qj", "yi", "iy", "uw", "wu", "yy", "hj",
    "jh", "vj", "jv", "fv", "vf", "gk", "kg", "pb", "bp", "dt", "td", "zs",
})

# Grupos consonánticos permitidos al final de la palabra.
ALLOWED_FINAL_CLUSTERS = frozenset({
    "ns", "rs", "nt", "rt", "st", "nd", "rk", "rn", "ch", "sh", "th", "ph",
    "ll", "ss", "ff", "lt", "ld", "ls", "ms", "ks", "ts", "nx", "rx",
})

# Consonantes finales que suenan cortadas si van solas tras vocal.
WEAK_FINAL_CONSONANTS = frozenset("qjvwbgcpfh")

_RUNS = re.compile(r"C+|V+")
_TRIPLE = re.compile(r"(.)\1\1")
_DOUBLE = re.compile(r"(.)\1")


@dataclass(frozen=True)
class PhoneticRules:
    """Umbrales y conjuntos de letras configurables de las reglas."""

    min_length: int = 4
    max_length: int = 10
    max_vowel_run: int = 2
    max_consonant_run: int = 3  # en medio, contando dígrafos (ch, sch) como una unidad
    onset_clusters: frozenset[str] = INSEPARABLE_CLUSTERS
    allowed_doubles: frozenset[str] = ALLOWED_DOUBLES
    forbidden_bigrams: frozenset[str] = FORBIDDEN_BIGRAMS
    allowed_final_clusters: frozenset[str] = ALLOWED_FINAL_CLUSTERS
    weak_final_consonants: frozenset[str] = WEAK_FINAL_CONSONANTS
    forbidden_letters: frozenset[str] = frozenset()  # letras ajenas al idioma


def _valid_medial(run: str, rules: PhoneticRules) -> bool:
    """Grupo consonántico interno = coda de una sílaba + ataque de la siguiente.

    Se busca un punto de corte donde la parte izquierda sea una coda válida
    (1 unidad o grupo final permitido) y la derecha un ataque válido
    (1 unidad o grupo inicial permitido): n-tr, rn-t, ch-t, n-schl.
    Los dígrafos (ch, sh, sch...) cuentan como una sola unidad.
    """
    units = consonant_units(run)
    if len(units) <= 2:
        return True
    if len(units) > rules.max_consonant_run:
        return False
    for cut in range(1, len(units)):
        coda, onset = "".join(units[:cut]), "".join(units[cut:])
        coda_ok = cut == 1 or coda in rules.allowed_final_clusters
        onset_ok = cut == len(units) - 1 or onset in rules.onset_clusters
        if coda_ok and onset_ok:
            return True
    return False


def _check_consonant_run(run: str, start: int, end: int, size: int,
                         rules: PhoneticRules) -> str | None:
    if start == 0:  # ataque inicial: 'b' o grupo conocido 'br', 'sch'
        if len(run) > 1 and run not in rules.onset_clusters:
            return "inicio_impronunciable"
    elif end == size:  # coda final
        if len(run) == 1 and run in rules.weak_final_consonants:
            return "final_debil"
        if len(run) > 1 and run not in rules.allowed_final_clusters:
            return "final_impronunciable"
    elif not _valid_medial(run, rules):
        return "consonantes_consecutivas"
    return None


def _check_runs(word: str, pattern: str, rules: PhoneticRules) -> list[str]:
    """Valida longitudes de secuencias de vocales/consonantes."""
    issues = []
    for match in _RUNS.finditer(pattern):
        start, end = match.span()
        run = word[start:end]
        if match.group()[0] == "V":
            if len(run) > rules.max_vowel_run:
                issues.append("vocales_consecutivas")
            continue
        issue = _check_consonant_run(run, start, end, len(word), rules)
        if issue:
            issues.append(issue)
    return issues


def _check_letters(word: str, rules: PhoneticRules) -> list[str]:
    """Valida repeticiones y combinaciones concretas de letras."""
    issues = []
    if rules.forbidden_letters.intersection(word):
        issues.append("letra_ajena")
    if _TRIPLE.search(word):
        issues.append("letra_triple")
    if len(word) > 1 and word[0] == word[1] and word[:2] not in rules.onset_clusters:
        issues.append("doble_inicial")  # salvo ataques como la 'll' española
    if any(m.group() not in rules.allowed_doubles for m in _DOUBLE.finditer(word)):
        issues.append("doble_no_permitida")
    if any(c == "q" and word[i + 1:i + 2] != "u" for i, c in enumerate(word)):
        issues.append("q_sin_u")
    if any(word[i:i + 2] in rules.forbidden_bigrams for i in range(len(word) - 1)):
        issues.append("bigrama_prohibido")
    return issues


def check(word: str, rules: PhoneticRules) -> list[str]:
    """Devuelve la lista de reglas incumplidas (vacía = válida)."""
    if not rules.min_length <= len(word) <= rules.max_length:
        return ["longitud"]
    pattern = cv_pattern(word)
    if "V" not in pattern:
        return ["sin_vocales"]
    return _check_runs(word, pattern, rules) + _check_letters(word, rules)
