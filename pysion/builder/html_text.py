"""Extracción del texto visible de un documento HTML (biblioteca estándar)."""

from html.parser import HTMLParser

# Contenido que no es texto legible: código, estilos, metadatos, gráficos.
SKIPPED_TAGS = frozenset({"script", "style", "noscript", "template", "svg", "head"})


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)  # &aacute; -> á
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in SKIPPED_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """Devuelve el texto visible, separando bloques con espacios."""
    parser = _VisibleTextParser()
    parser.feed(html)
    parser.close()
    return " ".join(parser.parts)
