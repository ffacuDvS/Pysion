# namegen

Generador de **nombres inventados con armonía fonética**, pensado para ayudar a elegir el nombre de una empresa o marca.

Toma palabras al azar de diccionarios temáticos, las combina por **sílabas** y descarta todo lo que no se pueda pronunciar. Después ordena los resultados según lo bien que "suenan". Las palabras resultantes no existen, pero conservan una estructura natural en español e inglés.

También puede:

- **Inventar palabras a partir de una palabra concreta** (por ejemplo "python" → *Pyxel*, *Pyrus*, *Metathon*). Consulta [Palabras base](#palabras-base).
- **Inventar palabras que suenen a un idioma**: latín, inglés, español, portugués, italiano, alemán o ruso (transliterado a nuestras letras). Consulta [Idiomas](#idiomas).

```text
$ python3 -m namegen -n 8 --seed 42
  1. Cimos    96.7  [syllable_mix: cipher + kosmos]
  2. Telor    96.7  [blend: terra + valor]
  3. Vatus    96.7  [syllable_mix: valor + ventus]
  4. Verix    96.7  [root_suffix: vertex + ix]
  5. Hona     91.7  [blend: honor + arena]
  6. Vertix   90.6  [mutate: vertex]
  7. Venio    90.4  [root_suffix: ventus + io]
  8. Cono     88.3  [blend: coral + destino]
```

Cada fila muestra el nombre, su puntuación de armonía (0-100), la estrategia usada y las palabras de origen.

- Python **3.10 o superior**
- **Solo biblioteca estándar**: no hay dependencias que instalar

---

## Tabla de contenidos

- [Cómo funciona](#cómo-funciona)
- [Instalación](#instalación)
- [Uso](#uso)
- [Palabras base](#palabras-base)
- [Idiomas](#idiomas)
- [Opciones](#opciones)
- [Estrategias de generación](#estrategias-de-generación)
- [Reglas de pronunciabilidad](#reglas-de-pronunciabilidad)
- [Puntuación de armonía](#puntuación-de-armonía)
- [Diccionarios](#diccionarios)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Decisiones de diseño](#decisiones-de-diseño)
- [Extender el generador](#extender-el-generador)
- [Códigos de salida](#códigos-de-salida)
- [Tests](#tests)
- [Limitaciones](#limitaciones)

---

## Cómo funciona

Cada nombre pasa por cuatro pasos:

1. **Selección**: se toman palabras al azar de los diccionarios elegidos (latín, naturaleza, tecnología, valores o los tuyos propios). Si indicas [palabras base](#palabras-base) con `-w`, cada nombre parte obligatoriamente de una de ellas. Si eliges [idiomas](#idiomas) con `-l`, se usan sus diccionarios y sus prefijos y sufijos.
2. **Combinación**: una de las 5 [estrategias](#estrategias-de-generación) las une. Siempre se corta por sílabas, no por letras al azar, para que el resultado suene natural.
3. **Filtrado**: se descarta lo impronunciable con [reglas fonéticas](#reglas-de-pronunciabilidad) (las de cada idioma, si eliges alguno), los duplicados y las palabras que ya existen en el diccionario, para que el nombre sea realmente inventado.
4. **Puntuación**: cada nombre válido recibe una [puntuación de armonía](#puntuación-de-armonía) de 0 a 100 y la lista se ordena de mejor a peor.

---

## Instalación

```bash
git clone <url-de-tu-repositorio> name-generator
cd name-generator
python3 --version   # debe ser 3.10 o superior
```

No hace falta `pip install` ni dar permisos de ejecución: el paquete se ejecuta con `python3 -m namegen` desde la raíz del proyecto.

---

## Uso

Uso básico (20 nombres con todos los temas):

```bash
python3 -m namegen
```

Solo con los temas latín y valores, empezando por "v":

```bash
python3 -m namegen -n 30 -t latin,valores --starts-with v
```

Con tu propio diccionario, sin usar los temas incluidos:

```bash
python3 -m namegen -d ~/mis_palabras.txt --no-themes -n 40
```

A partir de una palabra concreta:

```bash
python3 -m namegen -w python
```

Que suene a italiano:

```bash
python3 -m namegen -l it
```

Nombres cortos y de alta puntuación, exportados a CSV:

```bash
python3 -m namegen -n 50 --max-length 6 --min-score 90 -f csv > nombres.csv
```

Salida en JSON (para procesarla con otras herramientas):

```bash
python3 -m namegen -n 10 -f json
```

Resultado reproducible, con estadísticas de rechazo (útil para ajustar las reglas):

```bash
python3 -m namegen --seed 42 --stats
```

Solo algunas estrategias:

```bash
python3 -m namegen -s blend,root_suffix
```

---

## Palabras base

Con `-w/--word` indicas una palabra de la que **deben derivar todos los nombres**. Se puede repetir para usar varias:

```bash
python3 -m namegen -w python -n 12 --seed 1
```

```text
  1. Pyrus      96.7  [blend: python + clarus]
  2. Pysol      96.7  [blend: python + sol]
  3. Pyxel      96.7  [blend: python + pixel]
  4. Metathon   96.4  [prefix_root: meta + python]
  5. Vitathon   96.4  [prefix_root: vita + python]
  6. Pyno       91.7  [root_suffix: python + ino]
  7. Pyra       91.7  [blend: python + terra]
  8. Pyrit      91.7  [blend: python + spirit]
  9. Luthon     90.6  [syllable_mix: lucid + python]
 10. Pythan     90.6  [mutate: python]
 11. Neothon    88.3  [prefix_root: neo + python]
 12. Fothon     87.2  [blend: forest + python]
```

Sin `--seed`, cada ejecución da nombres distintos.

Cómo funciona:

- En cada intento se elige una de las palabras base, y la estrategia la usa como origen obligatorio. La columna de origen siempre la incluye.
- El resto de palabras (temas, `--dict` u otras palabras base) actúan como **compañeras** para las mezclas. Así, con `-t tecnologia` los nombres se mezclan con vocabulario tecnológico.
- La palabra base puede aportar el **inicio** del nombre (*Pyxel*) o el **final** (*Luthon*).
- La palabra base nunca aparece tal cual como resultado, porque no sería un nombre inventado.
- La palabra base se normaliza igual que los diccionarios (`Génesis` → `genesis`) y debe tener entre 3 y 14 letras. Si no, el programa termina con código 2.

Combinaciones útiles:

Dos palabras base mezcladas con el tema tecnología:

```bash
python3 -m namegen -w python -w generator -t tecnologia
```

Solo la palabra base, sin temas:

```bash
python3 -m namegen -w python --no-themes
```

Con una sola palabra y `--no-themes` no hay compañeras con las que mezclar, así que `blend` y `syllable_mix` no producen nada (aparecen en `--stats` como `estrategia_sin_resultado`). Los nombres salen de `mutate`, `root_suffix` y `prefix_root` (*Metathon*, *Pythan*, *Pyra*). Si quieres más variedad, añade otra palabra base o un tema.

---

## Idiomas

Con `-l/--lang` eliges uno o varios idiomas. Cada idioma aporta tres cosas:

1. **Su diccionario**: unas 65-85 palabras de naturaleza, valores y conceptos que funcionan bien como raíz de marca.
2. **Sus prefijos y sufijos**, que sustituyen a los genéricos (el alemán usa `-heim`, `-berg`, `-werk`; el italiano `-etta`, `-ino`, `-ezza`).
3. **Sus reglas fonéticas**: qué grupos de consonantes admite al principio y al final, qué letras dobles, cuántas vocales seguidas y qué letras le son ajenas.

| Código | Idioma | Carácter de sus reglas | Ejemplos (`-n 4 --seed 3`) |
|---|---|---|---|
| `la` | Latín | Finales en `-us`, `-um`, `-is`, `-ex`; sin `j`, `k`, `w` | *Sobum, Intesa, Scieta, Ultrarus* |
| `en` | Inglés | Grupos como `str`, `thr`, `ght`, `nk`; finales consonánticos | *Koral, Boldon, Cichard, Oley* |
| `es` | Español | Finales en vocal, `n`, `s`, `r`, `l`, `d`, `z`; `ll` inicial | *Semila, Lumogo, Jaro, Estrelista* |
| `pt` | Portugués | `nh`, `lh`; hasta 3 vocales (`praia`); sin `k`, `w`, `y` | *Veto, Auron, Zerra, Claria* |
| `it` | Italiano | Termina en vocal o `l`, `n`, `r`; dobles como `zz`, `cc`, `gg`; sin `j`, `k`, `w`, `x`, `y` | *Bellato, Ponetta, Arale, Valo* |
| `de` | Alemán | `sch`, `pf`, `zw`; finales como `-cht`, `-tz`, `-ng`; hasta 3 vocales (`feuer`) | *Funa, Lechto, Velicht, Leuchwerk* |
| `ru` | Ruso (transliterado) | `zh`, `kh`, `ts`, `shch`; finales como `-ov`, `-sk`; sin `q`, `w`, `x` | *Stepeva, Kavo, Ralet, Taysteplet* |

```bash
python3 -m namegen -l it -n 6 --seed 3
```

```text
  1. Bellato   95.8  [prefix_root: bella + raccolto]
  2. Ponetta   95.8  [root_suffix: ponte + etta]
  3. Arale     93.3  [syllable_mix: aquila + terra + valle]
  4. Orece     93.3  [syllable_mix: oliva + valore + radice]
  5. Valo      91.7  [syllable_mix: valore + cielo]
  6. Graro     90.4  [prefix_root: gran + libero]
```

### Cómo se combinan con el resto de opciones

- **Con `-l` y sin `-t`**, no se usan los temas incluidos. Son una mezcla de español e inglés que diluiría el carácter del idioma. Si quieres ambos, indícalo: `-l de -t tecnologia`.
- **Varios idiomas** (`-l it,la`): se juntan sus diccionarios y afijos, y las reglas se combinan de forma **permisiva**: se acepta lo que acepte cualquiera de ellos. Por ejemplo, con italiano y alemán se admite `sch` y la `k`.
- **Con palabras base** (`-l ru -w volga`): la palabra base se mezcla con el diccionario del idioma y sigue sus reglas.
- **Sin `-l`**, todo funciona como siempre: temas, afijos y reglas genéricas.

Algunas combinaciones:

Latín e italiano juntos:

```bash
python3 -m namegen -l la,it
```

Alemán mezclado con el tema de tecnología:

```bash
python3 -m namegen -l de -t tecnologia
```

Ruso a partir de una palabra escrita en cirílico:

```bash
python3 -m namegen -l ru -w Волга
```

```text
  1. Dobroga   92.5  [prefix_root: dobro + volga]
  2. Duga      91.7  [blend: dub + volga]
  3. Volo      88.3  [mutate: volga]
  4. Volok     88.3  [root_suffix: volga + ok]
  5. Yaga      70.0  [syllable_mix: yantar + volga]
```

(Salida con `-n 5 --seed 2`.)

### Ruso y otros alfabetos

El ruso se escribe **con nuestras letras**. Todo el texto (diccionarios, `-w` y `--dict`) pasa por una transliteración automática, así que puedes usar palabras o diccionarios rusos en cirílico directamente:

| Cirílico | Latino | Cirílico | Latino |
|---|---|---|---|
| ж | zh | ш | sh |
| х | kh | щ | shch |
| ц | ts | ю / я / ё | yu / ya / yo |
| ч | ch | ъ / ь | (se omiten) |

`Жар-птица` → `zharptitsa`, `Щука` → `shchuka`. También se convierten letras latinas especiales: `ß` → `ss`, `æ` → `ae`, `ø` → `o`; los acentos y la diéresis se eliminan (`Coração` → `coracao`, `Brücke` → `brucke`).

### Calibración

Las reglas de cada idioma están ajustadas para aceptar sus propias palabras reales. Hay un test que lo comprueba: el latín, el inglés, el español, el portugués y el alemán aceptan el 100 % de su diccionario, y el italiano y el ruso el 99 %. Las dos excepciones son casos extremos que no compensa relajar: *gioia* (4 vocales seguidas) y *solntse* (`lnts`).

---

## Opciones

| Opción | Por defecto | Descripción |
|---|---|---|
| `-n`, `--count` | `20` | Cantidad de nombres a generar (1-1000) |
| `-t`, `--themes` | todos | Temas incluidos, separados por comas |
| `-d`, `--dict FICHERO` | — | Diccionario adicional (una palabra por línea). Se puede repetir |
| `-l`, `--lang` | — | [Idiomas](#idiomas) separados por comas: `la`, `en`, `es`, `pt`, `it`, `de`, `ru` |
| `-w`, `--word PALABRA` | — | [Palabra base](#palabras-base): todos los nombres derivarán de ella. Se puede repetir |
| `--no-themes` | no | No usar los temas incluidos; solo `--dict`, `--word` y/o `--lang`. `--only-dicts` sigue funcionando como alias |
| `-s`, `--strategies` | todas | Estrategias separadas por comas |
| `--min-length` | `4` | Longitud mínima del nombre (3-20) |
| `--max-length` | `10` | Longitud máxima del nombre (3-20) |
| `--min-score` | `70` | Puntuación mínima de armonía (0-100) |
| `--starts-with` | — | Obliga a que el nombre empiece por esa/s letra/s |
| `--seed` | aleatoria | Semilla para obtener siempre los mismos resultados |
| `-f`, `--format` | `text` | Formato de salida: `text`, `json` o `csv` |
| `--stats` | no | Muestra en stderr los intentos y los motivos de rechazo |
| `-v`, `--verbose` | no | Logs de depuración en stderr |
| `--version` | — | Muestra la versión |

Temas incluidos: `latin`, `naturaleza`, `tecnologia`, `valores`. El tema `latin` es una lista temática (raíces latinas y griegas); el idioma `-l la` usa además afijos y reglas del latín.

---

## Estrategias de generación

| Estrategia | Qué hace | Ejemplo |
|---|---|---|
| `blend` | Primeras sílabas de una palabra + últimas sílabas de otra (portmanteau) | matrix + river → **Maver** |
| `syllable_mix` | Sílaba inicial de A + (sílaba de B) + sílaba final de C | coral + logos + sistema → **Cogoma** |
| `root_suffix` | Raíz de una palabra + sufijo comercial (`ix`, `ia`, `ora`, `ium`…) | vertex + ix → **Verix** |
| `prefix_root` | Prefijo de marca (`neo`, `evo`, `nova`…) + final de una palabra | evo + axis → **Evoxis** |
| `mutate` | 1-2 mutaciones sobre una palabra real: cambio de vocal, estilización (c→k, s→z, i→y) o final suave | halcon → **Halkan** |

### Unión suave entre fragmentos

Todas las estrategias unen fragmentos con `join_smooth()`, que corrige la juntura:

- **Letra repetida**: se funde (sol + luna → *soluna*).
- **Vocal + vocal**: se quita la vocal final de la raíz para conservar el sufijo intacto (nova + ia → *novia*, terra + ium → *terrium*). Si la raíz tiene 2 letras o menos, se recorta el sufijo para no perderla (py + ino → *pyno*).
- **Dos consonantes que no forman un grupo válido**: se elimina la última de la raíz. Los grupos como `tr`, `bl` o `ch` sí se mantienen.
- **Los dígrafos nunca se parten**: `ch`, `sh`, `sch`, `th`, `ph`, `kh`, `zh`, `gh` y `shch` cuentan como un solo sonido, tanto al dividir en sílabas (*za-shchi-ta*) como al unir (hoch + stall → *hochstall*, no *hocstall*).

---

## Reglas de pronunciabilidad

Definidas en [`namegen/rules.py`](namegen/rules.py). Si un nombre incumple cualquiera de ellas, se descarta. Cada regla tiene un identificador que aparece en `--stats`.

Los valores de la tabla son los genéricos (mezcla de español e inglés). Cada [idioma](#idiomas) los sustituye por los suyos en su `profile.json`.

| Regla | Identificador |
|---|---|
| Longitud fuera de `--min-length` / `--max-length` | `longitud` |
| El nombre no tiene vocales | `sin_vocales` |
| Más de 2 vocales seguidas (3 en alemán, portugués y ruso) | `vocales_consecutivas` |
| Inicio con más de una consonante que no forma grupo válido (`br`, `tr`, `st`; `sch` en alemán…) | `inicio_impronunciable` |
| Final con un grupo de consonantes no admitido (`ns`, `rt`, `nd`… sí lo están) | `final_impronunciable` |
| Grupo de consonantes interno que no se puede dividir en *coda válida + ataque válido* (n-tr, rn-t, ch-t sí), o con más de 3 unidades (los dígrafos cuentan como una) | `consonantes_consecutivas` |
| Tres letras iguales seguidas | `letra_triple` |
| Empieza con letra doble (salvo si es un grupo inicial del idioma, como la `ll` española) | `doble_inicial` |
| Letra doble no habitual (solo se admiten `ll`, `rr`, `ss`, `nn`, `tt`, `ee`, `oo`, `mm`, `ff`) | `doble_no_permitida` |
| "q" sin "u" detrás | `q_sin_u` |
| Combinaciones difíciles (`xz`, `jq`, `vw`, `dt`…) | `bigrama_prohibido` |
| Termina en consonante "cortada" (`q`, `j`, `v`, `b`, `g`, `p`…) | `final_debil` |
| Contiene una letra ajena al idioma elegido (`k` en italiano, `w` en ruso…) | `letra_ajena` |

El generador también descarta candidatos por `duplicado`, `palabra_real` (existe en el diccionario), `prefijo_usuario` (no cumple `--starts-with`) y `score_bajo` (por debajo de `--min-score`).

---

## Puntuación de armonía

Las reglas deciden **qué es válido**; la puntuación decide **qué suena mejor**. Está en [`namegen/scoring.py`](namegen/scoring.py) y suma seis componentes ponderados:

| Componente | Peso | Ideal |
|---|---|---|
| `alternation` | 25 % | Alternancia consonante-vocal (CVCV = máximo) |
| `length` | 20 % | Entre 5 y 8 letras |
| `vowel_ratio` | 20 % | Entre un 35 % y un 55 % de vocales |
| `syllables` | 15 % | 2 o 3 sílabas |
| `ending` | 10 % | Final suave: vocal o `n`, `r`, `s`, `l`, `x`, `m`, `y` |
| `variety` | 10 % | Varias vocales distintas y sin sílabas repetidas ("bababa" puntúa bajo) |

Los pesos están en el diccionario `WEIGHTS` y se pueden ajustar a tu gusto.

---

## Diccionarios

Están en `namegen/data/` y son ficheros de texto plano **editables sin tocar código**:

```text
namegen/data/
├── prefixes.txt        # genéricos: neo, evo, omni, nova, zen…
├── suffixes.txt        # genéricos: ia, io, ix, ex, ora, ium…
├── themes/
│   ├── latin.txt       # lux, terra, veritas, helios…
│   ├── naturaleza.txt  # aurora, cedar, luna, brisa…
│   ├── tecnologia.txt  # pixel, quantum, photon, nexo…
│   └── valores.txt     # honor, genesis, alianza, lucid…
└── languages/
    ├── de/             # un directorio por idioma (de, en, es, it, la, pt, ru)
    │   ├── profile.json  # nombre y reglas fonéticas
    │   ├── words.txt     # diccionario
    │   ├── prefixes.txt  # opcional
    │   └── suffixes.txt  # opcional
    └── …
```

Formato de los ficheros:

- Una palabra por línea, en UTF-8.
- `#` inicia un comentario.
- Los acentos y la ñ se normalizan (`Halcón` → `halcon`), y el cirílico se translitera (`Волга` → `volga`).
- Se ignoran las líneas con espacios y las palabras de menos de 3 o más de 14 letras.
- Tamaño máximo: 5 MB por fichero.

Puedes usar diccionarios grandes del sistema, por ejemplo `-d /usr/share/dict/spanish`.

---

## Estructura del proyecto

```text
name-generator/
├── README.md
├── namegen/
│   ├── __init__.py      # versión del paquete
│   ├── __main__.py      # punto de entrada de `python -m namegen`
│   ├── cli.py           # argumentos, validación y códigos de salida
│   ├── exceptions.py    # NameGenError, LexiconError, ConfigError
│   ├── generator.py     # bucle que genera, filtra, puntúa y ordena
│   ├── languages.py     # perfiles de idioma: carga, validación y fusión de reglas
│   ├── lexicon.py       # carga segura de diccionarios y palabras base
│   ├── output.py        # salida en texto, JSON o CSV, y estadísticas
│   ├── phonetics.py     # normalización, patrón CV, sílabas, dígrafos, unión suave
│   ├── rules.py         # reglas de pronunciabilidad
│   ├── scoring.py       # puntuación de armonía
│   ├── strategies.py    # estrategias de generación (con soporte de palabra base)
│   ├── transliteration.py  # cirílico y letras especiales → a-z
│   └── data/            # temas, idiomas, prefijos y sufijos
└── tests/
    ├── test_anchors.py         # palabras base (-w)
    ├── test_generator.py       # generador, léxico y CLI
    ├── test_languages.py       # idiomas, transliteración y calibración
    ├── test_phonetics.py       # sílabas, normalización, unión suave
    └── test_rules_scoring.py   # reglas y puntuación
```

Cada módulo tiene una sola responsabilidad y ninguno pasa de unas 160 líneas.

---

## Decisiones de diseño

- **Corte por sílabas.** `syllabify()` usa una aproximación ortográfica (lu-na, sil-va, ma-trix). Los grupos inseparables como `tr` o `bl` se mantienen juntos, lo que da uniones naturales (valor + altus → *Vatus*).
- **Reglas y puntuación van separadas.** Puedes endurecer o relajar una sin romper la otra.
- **Palabras base inyectadas, no filtradas.** Con `-w`, la palabra base se pasa a la estrategia en cada intento, en vez de generar al azar y quedarse con los nombres que la contengan. Así no se desperdician intentos, y funciona aunque la palabra base sea una entre miles del diccionario.
- **Idiomas como datos, no como código.** Cada idioma es un directorio con ficheros de texto y un JSON. Añadir o ajustar uno no requiere tocar Python, y las reglas de un idioma no afectan a los demás.
- **Reglas fonéticas basadas en la sílaba.** Un grupo de consonantes interno es válido si se puede dividir en *final de sílaba + inicio de sílaba* válidos para el idioma. Es más fiel a cómo funcionan los idiomas que un simple límite de consonantes seguidas.
- **Fusión permisiva de idiomas.** Al combinar idiomas, las listas de lo permitido se unen y las de lo prohibido se intersecan. Así ningún idioma del grupo queda bloqueado por las restricciones de otro.
- **Motivos de rechazo con nombre.** Cada regla devuelve un identificador, así `--stats` muestra exactamente por qué se descartan candidatos y qué conviene ajustar.
- **Bucle acotado.** Con filtros imposibles, el generador se detiene tras un máximo de intentos (`count × 500`) y devuelve lo que haya conseguido, en vez de colgarse.
- **Aleatoriedad reproducible.** Se usa `random.Random` y no `secrets`: no hace falta aleatoriedad criptográfica, y así `--seed` permite repetir exactamente un resultado.
- **Sin dependencias externas.** Todo se resuelve con la biblioteca estándar (`argparse`, `unicodedata`, `re`, `csv`, `json`, `dataclasses`).

### Seguridad

- Los diccionarios se validan antes de leerse: tiene que ser un fichero regular, de 5 MB como máximo y en UTF-8 válido.
- `-l` solo acepta códigos de idioma que existan como directorio en `data/languages/`, así que no se puede usar para leer otras rutas (`-l ../../etc` se rechaza).
- Cada `profile.json` se valida al cargarlo: claves conocidas, listas de letras `a-z` en minúsculas y enteros dentro de rango. Un perfil mal escrito produce un error claro en vez de un comportamiento extraño.
- Los nombres generados solo contienen letras `a-z`, así que el CSV no puede llevar fórmulas inyectadas (`=`, `+`, `-`, `@`) al abrirlo en una hoja de cálculo.
- No hay credenciales, llamadas de red ni ejecución de comandos externos.

---

## Extender el generador

### Añadir un tema

Crea un fichero `.txt` en `namegen/data/themes/`. Aparecerá automáticamente en `--themes`:

```bash
printf "# Mitología\nzeus\natenea\nodin\nfreya\n" > namegen/data/themes/mitologia.txt
python3 -m namegen -t mitologia
```

### Añadir un idioma

Crea un directorio en `namegen/data/languages/` con el código del idioma. Aparecerá automáticamente en `--lang`:

```text
namegen/data/languages/fr/
├── profile.json
├── words.txt       # obligatorio: una palabra por línea
├── prefixes.txt    # opcional
└── suffixes.txt    # opcional
```

Solo `name` es obligatorio en `profile.json`. Cualquier regla que no indiques usa el valor genérico:

```json
{
  "name": "Francés",
  "onset_clusters": ["bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "pl", "pr", "tr", "ch", "ph"],
  "allowed_doubles": ["ll", "ss", "nn", "mm", "tt", "rr", "ff", "pp"],
  "allowed_final_clusters": ["nt", "rt", "st", "ns", "rs"],
  "weak_final_consonants": ["b", "g", "j", "k", "p", "q", "v", "w"],
  "forbidden_letters": ["k", "w"],
  "max_vowel_run": 3,
  "max_consonant_run": 3
}
```

| Clave | Tipo | Qué controla |
|---|---|---|
| `onset_clusters` | lista | Grupos de consonantes permitidos al inicio de sílaba |
| `allowed_doubles` | lista | Letras dobles permitidas |
| `allowed_final_clusters` | lista | Grupos de consonantes permitidos al final |
| `weak_final_consonants` | lista | Consonantes que no pueden ir solas al final |
| `forbidden_bigrams` | lista | Parejas de letras prohibidas (sustituye a la lista genérica completa) |
| `forbidden_letters` | lista | Letras ajenas al idioma |
| `max_vowel_run` | entero 1-6 | Máximo de vocales seguidas |
| `max_consonant_run` | entero 1-6 | Máximo de unidades consonánticas seguidas en medio de palabra |

Después, comprueba que las reglas aceptan las palabras reales del idioma:

```bash
python3 -m unittest tests.test_languages -v
```

### Añadir una estrategia

Escribe una función con la firma `(rng, lexicon, anchor) -> Candidate | None` en [`namegen/strategies.py`](namegen/strategies.py) y regístrala en `STRATEGIES`. La línea de comandos la detecta sola.

`anchor` es la palabra base de `-w`, o `None` si no se indicó ninguna. Usa `_pick_words()` (para varias palabras) o `_one_word()` (para una), que ya incluyen la palabra base cuando la hay:

```python
def reverse_blend(rng: random.Random, lex: Lexicon, anchor: str | None = None) -> Candidate | None:
    """Final de A + inicio de B."""
    picked = _pick_words(rng, lex, anchor, 2)
    if len(picked) < 2:
        return None
    a, b = picked
    return Candidate(join_smooth(_tail(rng, a), _head(rng, b)), "reverse_blend", (a, b))


STRATEGIES: dict[str, Strategy] = {
    # ...estrategias existentes...
    "reverse_blend": reverse_blend,
}
```

### Ajustar reglas o puntuación

- Reglas de un idioma: su `profile.json`.
- Umbrales genéricos: `PhoneticRules` en [`namegen/rules.py`](namegen/rules.py).
- Combinaciones prohibidas y dobles permitidas: `FORBIDDEN_BIGRAMS`, `ALLOWED_DOUBLES`, `ALLOWED_FINAL_CLUSTERS`.
- Pesos e ideales de la puntuación: `WEIGHTS`, `IDEAL_LENGTH`, etc., en [`namegen/scoring.py`](namegen/scoring.py).

---

## Códigos de salida

| Código | Significado |
|---|---|
| `0` | Éxito: se generaron todos los nombres pedidos |
| `1` | Éxito parcial o sin resultados: los filtros son demasiado estrictos |
| `2` | Parámetros inválidos |
| `3` | Error al cargar un diccionario |
| `130` | Interrumpido con Ctrl+C |

Así puedes usarlo en scripts:

```bash
python3 -m namegen -n 100 -f csv > nombres.csv || echo "Revisa los filtros (código $?)"
```

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Cubren la división en sílabas, la unión suave, cada regla de rechazo, la puntuación, la reproducibilidad con semilla, la carga de diccionarios (temas desconocidos, ficheros inexistentes, acentos), las palabras base (cada nombre deriva de una, validación, uso sin temas), los idiomas (carga y validación de perfiles, rechazo de rutas no permitidas, fusión de reglas, transliteración y calibración con palabras reales) y los códigos de salida.

---

## Limitaciones

- **No comprueba marcas ni dominios.** No hace ninguna consulta de red. Antes de decidirte por un nombre, revisa la oficina de marcas de tu país (OEPM/EUIPO si estás en España o la UE) y la disponibilidad del dominio.
- **La silabificación es aproximada.** Se basa en la ortografía, no en la fonología real. Funciona bien con los idiomas incluidos, pero no distingue, por ejemplo, los diptongos de los hiatos.
- **La puntuación de armonía es común a todos los idiomas.** Las reglas sí son específicas de cada idioma, pero la puntuación premia los mismos rasgos (alternancia consonante-vocal, 2-3 sílabas) en todos. Los nombres alemanes y rusos, con más consonantes, tienden a puntuar algo menos.
- **Las mutaciones estilísticas son universales.** `mutate` aplica los mismos cambios en todos los idiomas (c→k, s→z, v→w…). Si un cambio produce una letra ajena al idioma, la regla `letra_ajena` descarta el nombre, pero no se generan variantes propias de cada idioma.
- **Diccionarios pequeños.** Cada idioma trae unas 65-85 palabras escogidas. Para más variedad, añade un diccionario grande del idioma con `--dict`.
- **No filtra significados.** Un nombre inventado puede coincidir con una palabra real de otro idioma o tener connotaciones no deseadas. Revisa los finalistas.
