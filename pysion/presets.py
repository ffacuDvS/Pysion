"""Presets de tipo de nombre: empaquetan formato y ajustes por propósito.

Un preset no genera nada nuevo: reutiliza el generador, pero fija cosas que
dependen del uso final y que hoy no se pueden expresar con las otras opciones:

- el CASO de la salida (minúsculas para usuarios/scripts, Título para marcas);
- un CALIFICADOR como palabra aparte ("Cipher Security"), que los sufijos
  pegados (-ix, -ia) no cubren;
- valores por defecto de longitud e idiomas, aplicados solo si el usuario no
  los indica.

Los presets viven en data/presets.json: añadir uno no requiere tocar código.
"""

import json
import random
from dataclasses import dataclass, field, replace
from typing import Iterable

from pysion.exceptions import ConfigError
from pysion.generator import GenerationResult, ScoredName
from pysion.lexicon import DATA_DIR, read_text_file

PRESETS_FILE = DATA_DIR / "presets.json"
CASES = frozenset({"lower", "title", "upper"})
MODES = frozenset({"blend", "acronym"})
ALLOWED_KEYS = frozenset({
    "description", "case", "min_length", "max_length",
    "qualifiers", "qualifier_ratio", "languages", "mode", "ampersand_ratio",
})

_CASE_FUNCS = {
    "lower": str.lower,
    "upper": str.upper,
    "title": str.capitalize,
}


@dataclass(frozen=True)
class Preset:
    name: str
    description: str = ""
    case: str = "title"
    min_length: int | None = None
    max_length: int | None = None
    qualifiers: tuple[str, ...] = ()
    qualifier_ratio: float = 0.0
    languages: tuple[str, ...] = field(default_factory=tuple)
    mode: str = "blend"            # "blend" (motor normal) o "acronym" (siglas)
    ampersand_ratio: float = 0.0   # solo acronym: probabilidad de forma H&H

    def format(self, base: str, rng: random.Random, styled: bool = False) -> str:
        """Aplica el caso (si `styled`, el base ya viene con su forma) y, con su
        probabilidad, añade un calificador aparte."""
        text = base if styled else _CASE_FUNCS[self.case](base)
        if self.qualifiers and rng.random() < self.qualifier_ratio:
            text = f"{text} {rng.choice(self.qualifiers)}"
        return text


def available_presets() -> dict[str, str]:
    """Nombres de preset -> descripción (para la ayuda de la CLI)."""
    try:
        raw = json.loads(read_text_file(PRESETS_FILE))
    except (OSError, json.JSONDecodeError):
        return {}
    return {name: cfg.get("description", "") for name, cfg in raw.items()}


def _validate(name: str, cfg: dict) -> None:
    unknown = sorted(set(cfg) - ALLOWED_KEYS)
    if unknown:
        raise ConfigError(f"[preset {name}] claves desconocidas: {', '.join(unknown)}")
    if cfg.get("case", "title") not in CASES:
        raise ConfigError(f"[preset {name}] 'case' debe ser uno de: {', '.join(sorted(CASES))}")
    if cfg.get("mode", "blend") not in MODES:
        raise ConfigError(f"[preset {name}] 'mode' debe ser uno de: {', '.join(sorted(MODES))}")
    for key in ("qualifier_ratio", "ampersand_ratio"):
        value = cfg.get(key, 0.0)
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ConfigError(f"[preset {name}] '{key}' debe estar entre 0 y 1")


def load_preset(name: str) -> Preset:
    """Carga un preset por su nombre; error claro si no existe o es inválido."""
    try:
        raw = json.loads(read_text_file(PRESETS_FILE))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"No se pudo leer presets.json: {exc}") from exc
    if name not in raw:
        raise ConfigError(
            f"Tipo desconocido: '{name}'. Disponibles: {', '.join(sorted(raw))}"
        )
    cfg = raw[name]
    _validate(name, cfg)
    return Preset(
        name=name,
        description=cfg.get("description", ""),
        case=cfg.get("case", "title"),
        min_length=cfg.get("min_length"),
        max_length=cfg.get("max_length"),
        qualifiers=tuple(cfg.get("qualifiers", ())),
        qualifier_ratio=float(cfg.get("qualifier_ratio", 0.0)),
        languages=tuple(cfg.get("languages", ())),
        mode=cfg.get("mode", "blend"),
        ampersand_ratio=float(cfg.get("ampersand_ratio", 0.0)),
    )


def combine_presets(names: list[str]) -> Preset:
    """Combina varios tipos en uno efectivo (p. ej. 'sigla,empresa').

    - El modo es 'acronym' si algún tipo lo es (las siglas mandan la forma).
    - Los calificadores se unen; la probabilidad es la mayor de todas.
    - La longitud e idiomas: del tipo de siglas si las hay, si no del primero.
    """
    presets = [load_preset(name) for name in dict.fromkeys(names)]
    if len(presets) == 1:
        return presets[0]

    qualifiers: list[str] = []
    for preset in presets:
        qualifiers.extend(q for q in preset.qualifiers if q not in qualifiers)
    ratio = max((p.qualifier_ratio for p in presets), default=0.0)
    languages = next((p.languages for p in presets if p.languages), ())

    acronym = next((p for p in presets if p.mode == "acronym"), None)
    base = acronym or presets[0]
    return Preset(
        name="+".join(dict.fromkeys(names)),
        case="upper" if acronym else presets[0].case,
        min_length=base.min_length,
        max_length=base.max_length,
        qualifiers=tuple(qualifiers),
        qualifier_ratio=ratio,
        languages=languages,
        mode="acronym" if acronym else "blend",
        ampersand_ratio=base.ampersand_ratio,
    )


def apply_format(result: GenerationResult, preset: Preset, rng: random.Random) -> None:
    """Reescribe el texto mostrado de cada nombre según el preset.

    Solo cambia lo que se muestra (`display`); `name` sigue en minúsculas, así
    el pipe hacia `pysion.check` y los orígenes no se ven afectados. Las siglas
    llevan su forma en `base_display` (IBM, H&H) y no se le reaplica el caso.
    """
    formatted = []
    for item in result.names:
        styled = item.base_display is not None
        base = item.base_display if styled else item.name
        display = preset.format(base, rng, styled=styled)
        formatted.append(replace(item, display_override=display))
    result.names = formatted
