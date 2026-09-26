"""Jerarquía de excepciones propias del generador."""


class PysionError(Exception):
    """Error base de pysion."""


class LexiconError(PysionError):
    """Error al cargar o validar diccionarios."""


class ConfigError(PysionError):
    """Configuración inválida (parámetros incoherentes)."""
