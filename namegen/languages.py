"""Perfiles de idioma: diccionario, afijos y reglas fonéticas propias.

Cada idioma es un directorio en data/languages/<código>/ con:
    profile.json   nombre y reglas fonéticas que sustituyen a las genéricas
    words.txt      diccionario del idioma
    prefixes.txt   prefijos (opcional)
    suffixes.txt   sufijos (opcional)

Para añadir un idioma basta con crear su directorio: no hay que tocar código.
"""

import json
import re
from dataclasses import dataclass, replace
from typing import Iterable

from namegen.exceptions import LexiconError
from namegen.lexicon import AFFIX_MIN_LEN, DATA_DIR, load_wordfile, read_text_file
from namegen.rules import PhoneticRules

LANGUAGES_DIR = DATA_DIR / "languages"

# Al combinar idiomas, los conjuntos "permisivos" se unen y los "restrictivos"
# se intersecan: se acepta lo que acepte cualquiera de los idiomas elegidos.
UNION_FIELDS = ("onset_clusters", "allowed_doubles", "allowed_final_clusters")
INTERSECTION_FIELDS = ("forbidden_bigrams", "weak_final_consonants", "forbidden_letters")
INT_FIELDS = ("max_vowel_run", "max_consonant_run")
ALLOWED_KEYS = frozenset({"name", *UNION_FIELDS, *INTERSECTION_FIELDS, *INT_FIELDS})
INT_RANGE = (1, 6)

_LETTERS = re.compile(r"[a-z]+")


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    name: str
    words: tuple[str, ...]
    prefixes: tuple[str, ...]
    suffixes: tuple[str, ...]
    rule_overrides: dict

    def rules(self, base: PhoneticRules) -> PhoneticRules:
        """Reglas del idioma: las del perfil sustituyen a las de `base`."""
        return replace(base, **self.rule_overrides)


def available_languages() -> list[str]:
    """Códigos de idioma disponibles (directorios con profile.json)."""
    if not LANGUAGES_DIR.is_dir():
        return []
    return sorted(d.name for d in LANGUAGES_DIR.iterdir() if (d / "profile.json").is_file())


def _parse_letter_set(code: str, key: str, value: object) -> frozenset[str]:
    if not isinstance(value, list) or not all(
        isinstance(v, str) and _LETTERS.fullmatch(v) for v in value
    ):
        raise LexiconError(f"[{code}] '{key}' debe ser una lista de textos en minúsculas a-z")
    return frozenset(value)


def _parse_int(code: str, key: str, value: object) -> int:
    low, high = INT_RANGE
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise LexiconError(f"[{code}] '{key}' debe ser un entero entre {low} y {high}")
    return value


def _parse_profile(code: str, raw: object) -> tuple[str, dict]:
    """Valida profile.json y devuelve (nombre, reglas que sobrescribe)."""
    if not isinstance(raw, dict):
        raise LexiconError(f"[{code}] profile.json debe contener un objeto JSON")
    unknown = sorted(set(raw) - ALLOWED_KEYS)
    if unknown:
        raise LexiconError(f"[{code}] claves desconocidas en profile.json: {', '.join(unknown)}")

    name = raw.get("name", code)
    if not isinstance(name, str) or not name.strip():
        raise LexiconError(f"[{code}] 'name' debe ser un texto no vacío")

    overrides: dict = {}
    for key in (*UNION_FIELDS, *INTERSECTION_FIELDS):
        if key in raw:
            overrides[key] = _parse_letter_set(code, key, raw[key])
    for key in INT_FIELDS:
        if key in raw:
            overrides[key] = _parse_int(code, key, raw[key])
    return name.strip(), overrides


def _load_optional_affixes(path) -> tuple[str, ...]:
    if not path.is_file():
        return ()
    return tuple(dict.fromkeys(load_wordfile(path, min_len=AFFIX_MIN_LEN)))


def load_language(code: str) -> LanguageProfile:
    """Carga y valida un perfil de idioma por su código."""
    # Solo se aceptan códigos de la lista: impide rutas como '../../etc'.
    if code not in available_languages():
        raise LexiconError(
            f"Idioma desconocido: '{code}'. Disponibles: {', '.join(available_languages())}"
        )
    folder = LANGUAGES_DIR / code
    try:
        raw = json.loads(read_text_file(folder / "profile.json"))
    except json.JSONDecodeError as exc:
        raise LexiconError(f"[{code}] profile.json no es JSON válido: {exc}") from exc
    name, overrides = _parse_profile(code, raw)

    words = tuple(dict.fromkeys(load_wordfile(folder / "words.txt")))
    if not words:
        raise LexiconError(f"[{code}] words.txt no contiene palabras válidas")

    return LanguageProfile(
        code=code,
        name=name,
        words=words,
        prefixes=_load_optional_affixes(folder / "prefixes.txt"),
        suffixes=_load_optional_affixes(folder / "suffixes.txt"),
        rule_overrides=overrides,
    )


def load_languages(codes: Iterable[str]) -> list[LanguageProfile]:
    """Carga varios idiomas (sin duplicados, en el orden indicado)."""
    return [load_language(code) for code in dict.fromkeys(codes)]


def merge_rules(base: PhoneticRules, profiles: Iterable[LanguageProfile]) -> PhoneticRules:
    """Combina las reglas de varios idiomas sobre `base`.

    Con un idioma devuelve sus reglas tal cual. Con varios, el resultado es
    permisivo: admite lo que admita cualquiera de ellos. Las longitudes
    mínima y máxima siempre se toman de `base` (las decide el usuario).
    """
    variants = [profile.rules(base) for profile in profiles]
    if not variants:
        return base
    merged: dict = {}
    for key in UNION_FIELDS:
        merged[key] = frozenset().union(*(getattr(v, key) for v in variants))
    for key in INTERSECTION_FIELDS:
        merged[key] = frozenset.intersection(*(getattr(v, key) for v in variants))
    for key in INT_FIELDS:
        merged[key] = max(getattr(v, key) for v in variants)
    return replace(base, **merged)
