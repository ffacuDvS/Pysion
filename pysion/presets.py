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
CASES = frozenset({"lower", "title"})
ALLOWED_KEYS = frozenset({
    "description", "case", "min_length", "max_length",
    "qualifiers", "qualifier_ratio", "languages",
})


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

    def format(self, base: str, rng: random.Random) -> str:
        """Aplica el caso y, con su probabilidad, añade un calificador."""
        text = base.capitalize() if self.case == "title" else base.lower()
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
        raise ConfigError(f"[preset {name}] 'case' debe ser 'lower' o 'title'")
    ratio = cfg.get("qualifier_ratio", 0.0)
    if not isinstance(ratio, (int, float)) or not 0 <= ratio <= 1:
        raise ConfigError(f"[preset {name}] 'qualifier_ratio' debe estar entre 0 y 1")


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
    )


def apply_format(result: GenerationResult, preset: Preset, rng: random.Random) -> None:
    """Reescribe el texto mostrado de cada nombre según el preset.

    Solo cambia lo que se muestra (`display`); `name` sigue en minúsculas, así
    el pipe hacia `pysion.check` y los orígenes no se ven afectados.
    """
    result.names = [
        replace(item, display_override=preset.format(item.name, rng))
        for item in result.names
    ]
