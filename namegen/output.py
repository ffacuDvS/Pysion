"""Renderizado de resultados en texto, JSON o CSV."""

import csv
import json
from typing import Callable, TextIO

from namegen.generator import GenerationResult, ScoredName


def _sources(item: ScoredName) -> str:
    return " + ".join(item.sources)


def render_text(result: GenerationResult, stream: TextIO) -> None:
    width = max((len(n.name) for n in result.names), default=6)
    for i, item in enumerate(result.names, start=1):
        stream.write(
            f"{i:>3}. {item.display:<{width}}  {item.score:5.1f}  "
            f"[{item.strategy}: {_sources(item)}]\n"
        )


def render_json(result: GenerationResult, stream: TextIO) -> None:
    payload = [
        {"name": n.display, "score": n.score, "strategy": n.strategy, "sources": list(n.sources)}
        for n in result.names
    ]
    json.dump(payload, stream, ensure_ascii=False, indent=2)
    stream.write("\n")


def render_csv(result: GenerationResult, stream: TextIO) -> None:
    # Los nombres solo contienen [a-z], así que no hay riesgo de inyección
    # de fórmulas (=, +, -, @) al abrir el CSV en una hoja de cálculo.
    writer = csv.writer(stream)
    writer.writerow(["name", "score", "strategy", "sources"])
    for n in result.names:
        writer.writerow([n.display, n.score, n.strategy, "|".join(n.sources)])


def render_stats(result: GenerationResult, stream: TextIO) -> None:
    """Resumen de intentos y motivos de rechazo (para depurar reglas)."""
    stream.write(f"\nIntentos: {result.attempts}  Aceptados: {len(result.names)}\n")
    for reason, total in result.rejections.most_common():
        stream.write(f"  - {reason:<26} {total}\n")


RENDERERS: dict[str, Callable[[GenerationResult, TextIO], None]] = {
    "text": render_text,
    "json": render_json,
    "csv": render_csv,
}
