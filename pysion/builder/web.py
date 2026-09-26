"""Descarga de páginas web como fuente de palabras (biblioteca estándar).

Medidas de seguridad y buena conducta:
- Solo http/https (nada de file://, ftp://...).
- Respeta robots.txt del sitio: si prohíbe el acceso, no se descarga.
- Tiempo de espera y tamaño máximo de descarga acotados.
- Solo se procesan respuestas de texto (HTML o texto plano).
"""

import urllib.error
import urllib.request
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from pysion import __version__
from pysion.builder.html_text import html_to_text
from pysion.exceptions import SourceError

ALLOWED_SCHEMES = frozenset({"http", "https"})
TIMEOUT_SECONDS = 15
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
USER_AGENT = f"pysion-builder/{__version__} (+https://github.com/ffacuDvS/Pysion)"
ROBOTS_AGENT = "pysion-builder"
TEXT_TYPES = frozenset({"text/html", "application/xhtml+xml", "text/plain"})


def is_url(source: str) -> bool:
    """True si parece una URL con esquema (http, https u otro no admitido)."""
    return "://" in source


def _open(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)  # noqa: S310 (esquema validado)


def _read_limited(response, url: str) -> bytes:
    data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise SourceError(f"La página supera {MAX_DOWNLOAD_BYTES} bytes: {url}")
    return data


def robots_allows(url: str) -> bool:
    """Consulta robots.txt con las mismas reglas que urllib.robotparser:
    401/403 prohíben todo, otros 4xx permiten todo y 5xx prohíbe (el sitio
    no puede confirmar sus normas). Si no hay conexión, lanza SourceError."""
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        with _open(robots_url) as response:
            lines = _read_limited(response, robots_url).decode("utf-8", "replace").splitlines()
    except urllib.error.HTTPError as exc:
        exc.close()  # un HTTPError mantiene abierta la conexión
        return exc.code not in (401, 403) and exc.code < 500
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise SourceError(f"No se pudo conectar con {parts.netloc}: {reason}") from exc
    parser = RobotFileParser()
    parser.parse(lines)
    return parser.can_fetch(ROBOTS_AGENT, url)


def fetch_text(url: str) -> str:
    """Descarga una URL y devuelve su texto visible."""
    scheme = urlparse(url).scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise SourceError(f"Esquema no permitido '{scheme}': solo http y https ({url})")
    if not robots_allows(url):
        raise SourceError(f"El robots.txt del sitio no permite descargar {url}")

    try:
        with _open(url) as response:
            content_type = response.headers.get_content_type()
            charset = response.headers.get_content_charset() or "utf-8"
            if content_type not in TEXT_TYPES:
                raise SourceError(f"Tipo de contenido no soportado ({content_type}): {url}")
            data = _read_limited(response, url)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise SourceError(f"El servidor respondió {exc.code} para {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise SourceError(f"No se pudo conectar con {url}: {reason}") from exc

    try:
        text = data.decode(charset, "replace")
    except LookupError:  # charset desconocido anunciado por el servidor
        text = data.decode("utf-8", "replace")
    return text if content_type == "text/plain" else html_to_text(text)
