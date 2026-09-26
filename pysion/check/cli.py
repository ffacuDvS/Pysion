"""Interfaz de línea de comandos del comprobador de disponibilidad.

Códigos de salida:
    0  todos los nombres consultados están totalmente libres
    1  al menos un nombre tiene algo ocupado o no concluyente
    2  error de uso / parámetros inválidos
    130 interrumpido por el usuario (Ctrl+C)
"""

import argparse
import concurrent.futures
import json
import re
import sys
from dataclasses import asdict

from pysion import __version__
from pysion.check.checks import FREE, TAKEN, UNKNOWN, build_checks, to_handle
from pysion.phonetics import normalize

# Marcas de texto para la salida (sin color: legible en cualquier terminal).
MARKS = {FREE: "[LIBRE]   ", TAKEN: "[OCUPADO] ", UNKNOWN: "[?]       "}
MAX_WORKERS = 8


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pysion.check",
        description="Comprueba si un nombre está libre como dominio (.com, .com.ar) "
                    "y como usuario en redes sociales. Es una ayuda orientativa: "
                    "confirma siempre en el registrador y en cada red.",
    )
    parser.add_argument("names", nargs="*", metavar="NOMBRE",
                        help="uno o varios nombres; si se omiten, se leen de la entrada "
                             "estándar (permite: pysion ... | pysion.check)")
    parser.add_argument("-f", "--format", choices=("text", "json"), default="text")
    parser.add_argument("--only-free", action="store_true",
                        help="mostrar solo los nombres con todo libre")
    return parser


# En una línea de la salida del generador, el nombre es el primer token con
# letras: "  1. Cimos  96.7 ..." -> Cimos; "Cimos,96.7,..." -> Cimos.
_NAME_TOKEN = re.compile(r"[A-Za-zÀ-ÿ]+")
_SKIP_TOKENS = frozenset({"name"})  # cabecera del CSV


def names_from_stdin(stream) -> list[str]:
    """Extrae un nombre por línea de la salida del generador (texto/CSV/JSON)."""
    names = []
    for line in stream:
        for token in line.replace(",", " ").split():
            if not _NAME_TOKEN.fullmatch(token):
                continue
            # El primer token con letras manda: si es cabecera, se ignora la línea.
            if token.lower() not in _SKIP_TOKENS:
                names.append(token)
            break
    return names


def _run_checks(name: str) -> list:
    """Ejecuta en paralelo todas las comprobaciones de un nombre."""
    handle = to_handle(name)
    checks = build_checks(name.lower(), handle)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fn): (target, url) for target, url, fn in checks}
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    # Orden estable: dominios primero, luego redes, como en build_checks.
    order = [target for target, _, _ in checks]
    results.sort(key=lambda a: order.index(a.target))
    return results


def _fully_free(results: list) -> bool:
    """Libre si ningún check fiable está ocupado o no concluyente.

    Los checks no fiables (p. ej. Instagram, que responde igual exista o no)
    quedan siempre como '?' y no deben impedir marcar un nombre como libre.
    """
    reliable = [a for a in results if a.reliable]
    return bool(reliable) and all(a.status == FREE for a in reliable)


def render_text(name: str, results: list, stream) -> None:
    flag = "todo libre" if _fully_free(results) else "revisar"
    stream.write(f"\n{name}  ({flag})\n")
    for a in results:
        line = f"  {MARKS[a.status]}{a.target:<16} {a.handle}"
        if a.detail:
            line += f"  — {a.detail}"
        if a.status == UNKNOWN and a.url:
            line += f"  {a.url}"
        stream.write(line + "\n")


def run(args: argparse.Namespace) -> int:
    report = {}
    all_free = True
    for name in args.names:
        results = _run_checks(name)
        free = _fully_free(results)
        all_free = all_free and free
        if args.only_free and not free:
            continue
        report[name] = results
        if args.format == "text":
            render_text(name, results, sys.stdout)

    if args.format == "json":
        payload = {name: [asdict(a) for a in results] for name, results in report.items()}
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    elif not report:
        sys.stdout.write("Ningún nombre está totalmente libre.\n")

    return 0 if all_free else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    raw_names = args.names or names_from_stdin(sys.stdin)
    if not raw_names:
        parser.error("indica al menos un NOMBRE o pásalos por la entrada estándar")
    # Normaliza y quita duplicados conservando el orden (útil desde un pipe).
    cleaned = list(dict.fromkeys(n for n in (normalize(r) for r in raw_names) if n))
    if not cleaned:
        parser.error("los nombres deben contener letras")
    args.names = cleaned

    try:
        return run(args)
    except KeyboardInterrupt:
        return 130
