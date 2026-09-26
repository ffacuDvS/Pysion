"""Orquestación: genera candidatos, los filtra, puntúa y ordena."""

import logging
import random
from collections import Counter
from dataclasses import dataclass, field

from pysion.exceptions import ConfigError
from pysion.lexicon import Lexicon
from pysion.rules import PhoneticRules, check
from pysion.scoring import harmony_score
from pysion.strategies import STRATEGIES, Candidate

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratorConfig:
    count: int = 20
    min_score: float = 70.0
    strategies: tuple[str, ...] = tuple(STRATEGIES)
    rules: PhoneticRules = field(default_factory=PhoneticRules)
    starts_with: str = ""
    # Nombres (normalizados) ya vistos en ejecuciones previas: no se repiten.
    exclude: frozenset[str] = frozenset()
    attempts_per_name: int = 500  # tope de intentos = count * este valor

    def validate(self) -> None:
        if self.count < 1:
            raise ConfigError("count debe ser >= 1")
        if not 0 <= self.min_score <= 100:
            raise ConfigError("min_score debe estar entre 0 y 100")
        if self.rules.min_length > self.rules.max_length:
            raise ConfigError("min_length no puede ser mayor que max_length")
        unknown = set(self.strategies) - set(STRATEGIES)
        if unknown or not self.strategies:
            raise ConfigError(
                f"Estrategias inválidas: {sorted(unknown) or '(vacío)'}. "
                f"Disponibles: {', '.join(STRATEGIES)}"
            )


@dataclass(frozen=True)
class ScoredName:
    name: str
    score: float
    strategy: str
    sources: tuple[str, ...]
    # Texto a mostrar cuando un preset cambia el caso o añade un calificador.
    # Si es None, se muestra el nombre capitalizado (comportamiento por defecto).
    display_override: str | None = None

    @property
    def display(self) -> str:
        return self.display_override if self.display_override is not None else self.name.capitalize()


@dataclass
class GenerationResult:
    names: list[ScoredName]
    attempts: int
    rejections: Counter

    @property
    def complete(self) -> bool:
        return bool(self.names)


def _rejection_reason(
    candidate: Candidate | None,
    config: GeneratorConfig,
    lexicon_words: frozenset[str],
    seen: set[str],
) -> str | None:
    """Motivo de descarte o None si el candidato pasa los filtros previos al score."""
    if candidate is None:
        return "estrategia_sin_resultado"
    name = candidate.name
    if name in config.exclude:
        return "en_historial"
    if name in seen:
        return "duplicado"
    if name in lexicon_words:
        return "palabra_real"
    if config.starts_with and not name.startswith(config.starts_with):
        return "prefijo_usuario"
    issues = check(name, config.rules)
    return issues[0] if issues else None


def generate(lexicon: Lexicon, config: GeneratorConfig, rng: random.Random) -> GenerationResult:
    """Genera hasta `config.count` nombres válidos, ordenados por puntuación.

    El bucle está acotado por `attempts_per_name` para no colgarse con
    configuraciones muy restrictivas; en ese caso devuelve lo conseguido.
    """
    config.validate()
    strategy_funcs = [STRATEGIES[name] for name in config.strategies]
    known = lexicon.known_words
    max_attempts = config.count * config.attempts_per_name

    accepted: list[ScoredName] = []
    seen: set[str] = set()
    rejections: Counter = Counter()
    attempts = 0

    while len(accepted) < config.count and attempts < max_attempts:
        attempts += 1
        # Con palabras base (-w), cada intento parte obligatoriamente de una.
        anchor = rng.choice(lexicon.anchors) if lexicon.anchors else None
        candidate = rng.choice(strategy_funcs)(rng, lexicon, anchor)
        reason = _rejection_reason(candidate, config, known, seen)
        if reason:
            rejections[reason] += 1
            continue

        seen.add(candidate.name)
        score = harmony_score(candidate.name)
        if score < config.min_score:
            rejections["score_bajo"] += 1
            continue
        accepted.append(ScoredName(candidate.name, score, candidate.strategy, candidate.sources))

    if len(accepted) < config.count:
        logger.warning(
            "Solo se generaron %d/%d nombres en %d intentos; relaja los filtros.",
            len(accepted), config.count, attempts,
        )
    accepted.sort(key=lambda n: (-n.score, n.name))
    return GenerationResult(accepted, attempts, rejections)
