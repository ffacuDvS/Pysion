"""Cliente HTTP mínimo y prudente para las comprobaciones (stdlib)."""

import urllib.error
import urllib.request

TIMEOUT_SECONDS = 20
# Algunas redes rechazan clientes sin apariencia de navegador.
USER_AGENT = "Mozilla/5.0 (compatible; pysion-check/1.0; +https://github.com/ffacuDvS/Pysion)"


class HttpResult:
    """Resultado de una petición: código de estado o motivo del fallo."""

    __slots__ = ("status", "error")

    def __init__(self, status: int | None = None, error: str | None = None) -> None:
        self.status = status
        self.error = error

    @property
    def ok(self) -> bool:
        return self.status is not None


def request(url: str, method: str = "GET") -> HttpResult:
    """Petición HTTP que nunca lanza: devuelve el estado o el error."""
    req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            return HttpResult(status=response.status)
    except urllib.error.HTTPError as exc:
        exc.close()
        return HttpResult(status=exc.code)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return HttpResult(error=str(getattr(exc, "reason", exc)))
