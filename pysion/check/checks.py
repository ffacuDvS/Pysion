"""Comprobaciones concretas: dominios (RDAP) y usuarios de redes sociales.

Cada comprobación devuelve un Availability. Un estado puede ser:
    free       parece libre
    taken      parece ocupado
    unknown    no se pudo determinar (red caída, o la plataforma no distingue)

La disponibilidad de un dominio por RDAP es fiable. La de una red social es
solo orientativa: se deduce del código HTTP del perfil y algunas plataformas
responden igual exista o no el usuario. Esos casos se marcan como `unknown`.
"""

import re
from dataclasses import dataclass
from enum import Enum

from pysion.check.http_client import request

FREE, TAKEN, UNKNOWN = "free", "taken", "unknown"


class Status(str, Enum):
    FREE = FREE
    TAKEN = TAKEN
    UNKNOWN = UNKNOWN


@dataclass(frozen=True)
class Availability:
    target: str          # "dominio .com", "GitHub"...
    handle: str          # el dominio o usuario consultado
    status: str
    detail: str = ""     # aclaración cuando el estado es unknown
    reliable: bool = True

    @property
    def url(self) -> str:
        return _TARGET_URLS.get(self.target, "")


# --- Dominios (RDAP: 404 = libre, 200 = registrado) ---

def _rdap(rdap_url: str, target: str, domain: str) -> Availability:
    result = request(rdap_url)
    if not result.ok:
        return Availability(target, domain, UNKNOWN, f"sin respuesta ({result.error})")
    if result.status == 404:
        return Availability(target, domain, FREE)
    if result.status == 200:
        return Availability(target, domain, TAKEN)
    return Availability(target, domain, UNKNOWN, f"respuesta inesperada (HTTP {result.status})")


def check_com(name: str) -> Availability:
    domain = f"{name}.com"
    return _rdap(f"https://rdap.org/domain/{domain}", "dominio .com", domain)


def check_com_ar(name: str) -> Availability:
    domain = f"{name}.com.ar"
    return _rdap(f"https://rdap.nic.ar/domain/{domain}", "dominio .com.ar", domain)


# --- Redes sociales (código HTTP del perfil) ---

@dataclass(frozen=True)
class _Social:
    name: str
    url_template: str
    reliable: bool = True
    # Algunas plataformas devuelven 200 aunque el usuario no exista (muro de
    # login). En esas, un 200 no confirma que esté ocupado: queda unknown.
    taken_means_taken: bool = True


SOCIALS = (
    _Social("GitHub", "https://github.com/{h}"),
    _Social("X (Twitter)", "https://x.com/{h}"),
    _Social("LinkedIn", "https://www.linkedin.com/company/{h}"),
    _Social("Instagram", "https://www.instagram.com/{h}/", reliable=False, taken_means_taken=False),
)


def check_social(social: _Social, handle: str) -> Availability:
    result = request(social.url_template.format(h=handle))
    if not result.ok:
        return Availability(social.name, handle, UNKNOWN, f"sin respuesta ({result.error})",
                            reliable=social.reliable)
    if result.status == 404:
        return Availability(social.name, handle, FREE, reliable=social.reliable)
    if result.status == 200:
        if social.taken_means_taken:
            return Availability(social.name, handle, TAKEN, reliable=social.reliable)
        return Availability(social.name, handle, UNKNOWN,
                            "responde igual exista o no; comprobar a mano", reliable=False)
    if result.status in (301, 302, 403, 429, 999):
        return Availability(social.name, handle, UNKNOWN,
                            f"la plataforma bloquea la consulta (HTTP {result.status})",
                            reliable=social.reliable)
    return Availability(social.name, handle, UNKNOWN, f"HTTP {result.status}", reliable=social.reliable)


# Sirve para mostrar el enlace en el informe.
_TARGET_URLS: dict[str, str] = {}


def build_checks(name: str, handle: str) -> list:
    """Lista de (target, url, función sin argumentos) para un nombre dado."""
    checks = [
        ("dominio .com", f"https://{name}.com", lambda: check_com(name)),
        ("dominio .com.ar", f"https://{name}.com.ar", lambda: check_com_ar(name)),
    ]
    for social in SOCIALS:
        url = social.url_template.format(h=handle)
        checks.append((social.name, url, lambda s=social: check_social(s, handle)))
    _TARGET_URLS.update({t: u for t, u, _ in checks})
    return checks


# Un usuario de red social válido: letras, números, punto, guion y guion bajo.
_HANDLE_CLEAN = re.compile(r"[^a-z0-9._-]")


def to_handle(name: str) -> str:
    """Convierte un nombre a un usuario plausible (minúsculas, solo a-z0-9._-)."""
    return _HANDLE_CLEAN.sub("", name.lower())
