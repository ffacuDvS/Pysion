"""Jerarquía de excepciones propias del generador."""


class NameGenError(Exception):
    """Error base de namegen."""


class LexiconError(NameGenError):
    """Error al cargar o validar diccionarios."""


class ConfigError(NameGenError):
    """Configuración inválida (parámetros incoherentes)."""
