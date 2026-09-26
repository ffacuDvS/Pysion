"""Transliteración a alfabeto latino básico (a-z).

Se aplica antes de quitar acentos, para las letras que NFKD no descompone
(ß, æ, ø...) y para el cirílico. Así un diccionario ruso escrito en
cirílico (o `-w Волга`) se convierte en palabras con nuestras letras.
"""

# Sistema práctico y legible (similar a BGN/PCGN simplificado): ж->zh, х->kh...
CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

# Letras latinas que NFKD no convierte a ASCII por sí solo.
SPECIAL_LATIN = {
    "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "ł": "l", "đ": "d",
    "ð": "d", "þ": "th", "ı": "i",
}

_TABLE = str.maketrans({**CYRILLIC, **SPECIAL_LATIN})


def transliterate(text: str) -> str:
    """Convierte cirílico y letras latinas especiales. Espera minúsculas."""
    return text.translate(_TABLE)
