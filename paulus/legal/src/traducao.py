"""
Traducao para o portugues nesta maquina, sem rede e sem o modelo de conversa.

Usa os pacotes do Argos Translate (modelos de traducao de verdade, pequenos,
em CPU) direto pelo CTranslate2 - o mesmo motor do faster-whisper das
Gravacoes - e o SentencePiece. Nao usa o pacote argostranslate: ele puxa o
stanza e o torch so para separar frases, e aqui uma regra basta.

Os pacotes ficam em data/modelos/traducao/<pacote>/ (model/,
sentencepiece.model, metadata.json). Para baixar:

    python src/traducao.py baixar

O HTML do e-mail e traduzido no lugar: cada trecho de texto entre as tags
vira portugues e as tags ficam como estavam - o layout do remetente continua
o mesmo. Numeros (codigo, valor, data) sao conferidos trecho a trecho: se a
traducao perdeu algum, aquele trecho fica no original.
"""

from __future__ import annotations

import html
import json
import re
import threading
import time
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path

PASTA = Path(__file__).parent.parent / "data" / "modelos" / "traducao"

# De qual lingua, qual pacote. "pb" e o portugues do Brasil do Argos.
PACOTES = {
    "en": ("translate-en_pb-1_9", "https://argos-net.com/v1/translate-en_pb-1_9.argosmodel"),
    "es": ("translate-es_pt-1_0", "https://argos-net.com/v1/translate-es_pt-1_0.argosmodel"),
}

LINGUAS = {"en": "inglês", "es": "espanhol"}

# Palavras comuns de cada lingua, para adivinhar de onde traduzir.
_PALAVRAS = {
    "pt": {"de", "que", "não", "para", "com", "uma", "você", "está", "por", "os", "das", "dos", "é", "ao", "seu", "sua", "obrigado", "olá", "mais", "como"},
    "en": {"the", "and", "you", "your", "to", "of", "is", "this", "for", "with", "are", "that", "will", "be", "on", "we", "our", "have", "please", "here"},
    "es": {"el", "los", "las", "usted", "con", "una", "es", "su", "está", "gracias", "hola", "para", "por", "del", "que", "nuestro", "aquí", "correo"},
}

_trava = threading.Lock()
_carregados: dict[str, tuple] = {}


def disponivel(lingua: str = "") -> bool:
    """O pacote da lingua (ou algum, sem lingua) esta nesta maquina e o motor abre."""
    try:
        import ctranslate2  # noqa: F401
        import sentencepiece  # noqa: F401
    except ImportError:
        return False
    linguas = [lingua] if lingua else list(PACOTES)
    return any(lingua in PACOTES and (PASTA / PACOTES[lingua][0] / "model").is_dir() for lingua in linguas)


def adivinhar_lingua(texto: str) -> str:
    """'en', 'es' ou '' (portugues, ou sem certeza)."""
    palavras = re.findall(r"[a-zà-úñ]+", (texto or "")[:6000].lower())
    conta = {l: sum(1 for p in palavras if p in conj) for l, conj in _PALAVRAS.items()}
    fora = "en" if conta["en"] >= conta["es"] else "es"
    return fora if conta[fora] >= 5 and conta[fora] > conta["pt"] * 2 else ""


def _motor(lingua: str):
    with _trava:
        if lingua not in _carregados:
            import ctranslate2
            import sentencepiece

            pasta = PASTA / PACOTES[lingua][0]
            tradutor = ctranslate2.Translator(str(pasta / "model"), device="cpu", compute_type="int8")
            pecas = sentencepiece.SentencePieceProcessor(model_file=str(pasta / "sentencepiece.model"))
            _carregados[lingua] = (tradutor, pecas)
        return _carregados[lingua]


# Frase termina em . ! ? seguido de espaco e maiuscula/numero. Abreviacao
# comum ("Mr.", "e.g.") pode cortar errado - o custo e uma frase partida.
_FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ0-9¿¡\"'(])")


def _frases(texto: str) -> list[str]:
    return [f for f in _FIM_DE_FRASE.split(texto) if f.strip()]


_PONTA = re.compile(r"^([\s:;,.\-–—·|•()]*)(.*?)([\s:;,.\-–—·|•()]*)$", re.S)


def _acertar_pontas(original: str, traduzido: str) -> str:
    """
    O trecho de HTML costuma ser pedaco de frase: ": ChatGPT Web", "Hi,",
    "revise a seguranca" no meio de um paragrafo. O modelo devolve frase
    inteira - maiuscula no comeco, ponto no fim - e come a pontuacao das
    pontas. Aqui as pontas voltam a ser as do original.
    """
    if not traduzido:
        return ""
    antes, miolo, depois = _PONTA.match(original).groups()
    t = _PONTA.match(traduzido).group(2)
    if not t:
        return ""
    if miolo[:1].islower() and t[:1].isupper():
        t = t[0].lower() + t[1:]
    return antes + t + depois


def traduzir_trechos(trechos: list[str], lingua: str) -> list[str]:
    """Cada trecho traduzido, na mesma ordem. Trecho vazio volta vazio."""
    if lingua not in PACOTES:
        raise ValueError("não sei traduzir dessa língua")
    if not disponivel(lingua):
        raise RuntimeError("o tradutor desta máquina não está instalado")
    tradutor, pecas = _motor(lingua)

    frases, dono = [], []
    for i, t in enumerate(trechos):
        for f in _frases(t):
            frases.append(f.strip())
            dono.append(i)
    saida = [[] for _ in trechos]
    if frases:
        tokens = [pecas.encode(f, out_type=str) for f in frases]
        with _trava:
            resultados = tradutor.translate_batch(tokens, beam_size=2, max_batch_size=32,
                                                  max_decoding_length=256)
        for i, r in zip(dono, resultados):
            saida[i].append("".join(r.hypotheses[0]).replace("▁", " ").strip())

    final = []
    for original, partes in zip(trechos, saida):
        traduzido = _acertar_pontas(original.strip(), " ".join(partes).strip())
        if not traduzido:
            final.append(original)
            continue
        # Os numeros tem de sobreviver: codigo, valor, data.
        if any(n not in traduzido for n in re.findall(r"\d{2,}", original)):
            final.append(original)
            continue
        # Mantem o espaco das pontas, que separa o trecho das tags vizinhas.
        inicio = original[: len(original) - len(original.lstrip())]
        fim = original[len(original.rstrip()):]
        final.append(inicio + traduzido + fim)
    return final


def traduzir_texto(texto: str, lingua: str) -> str:
    """Texto puro, paragrafo por paragrafo."""
    paragrafos = re.split(r"(\n\s*\n)", texto or "")
    idx = [i for i, p in enumerate(paragrafos) if p.strip() and not p.isspace()]
    traduzidos = traduzir_trechos([paragrafos[i] for i in idx], lingua)
    for i, t in zip(idx, traduzidos):
        paragrafos[i] = t
    return "".join(paragrafos)


# ------------------------------------------------------------- o HTML


class _Pedacos(HTMLParser):
    """Separa o HTML em tags (ficam) e textos (traduzem), na ordem."""

    PULAR = {"style", "script", "head", "title", "code", "pre"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.pedacos: list[tuple[str, str]] = []
        self._pulando = 0

    def _tag(self) -> None:
        self.pedacos.append(("tag", self.get_starttag_text() or ""))

    def handle_starttag(self, tag, attrs):
        self.pedacos.append(("tag", self.get_starttag_text() or ""))
        if tag in self.PULAR:
            self._pulando += 1

    def handle_startendtag(self, tag, attrs):
        self.pedacos.append(("tag", self.get_starttag_text() or ""))

    def handle_endtag(self, tag):
        self.pedacos.append(("tag", f"</{tag}>"))
        if tag in self.PULAR and self._pulando:
            self._pulando -= 1

    def handle_data(self, data):
        self.pedacos.append(("tag" if self._pulando else "texto", data))

    def handle_entityref(self, name):
        self._texto_bruto(f"&{name};")

    def handle_charref(self, name):
        self._texto_bruto(f"&#{name};")

    def _texto_bruto(self, bruto: str) -> None:
        tipo = "tag" if self._pulando else "texto"
        if self.pedacos and self.pedacos[-1][0] == tipo == "texto":
            self.pedacos[-1] = ("texto", self.pedacos[-1][1] + bruto)
        else:
            self.pedacos.append((tipo, bruto))

    def handle_comment(self, data):
        self.pedacos.append(("tag", f"<!--{data}-->"))

    def handle_decl(self, decl):
        self.pedacos.append(("tag", f"<!{decl}>"))


def _vale_traduzir(texto: str) -> bool:
    limpo = texto.strip()
    if len(limpo) < 2 or not re.search(r"[A-Za-zÀ-ú]{2,}", limpo):
        return False
    if re.fullmatch(r"(https?://|www\.)\S+|\S+@\S+\.\S+", limpo):
        return False
    return True


def traduzir_html(documento: str, lingua: str) -> str:
    """O mesmo HTML, com o texto em portugues e as tags intactas."""
    leitor = _Pedacos()
    leitor.feed(documento or "")
    leitor.close()
    pedacos = leitor.pedacos
    # Textos vizinhos (separados so por entidade) viram um trecho so.
    juntos: list[list] = []
    for tipo, valor in pedacos:
        if tipo == "texto" and juntos and juntos[-1][0] == "texto":
            juntos[-1][1] += valor
        else:
            juntos.append([tipo, valor])
    alvos = [i for i, (tipo, valor) in enumerate(juntos) if tipo == "texto" and _vale_traduzir(html.unescape(valor))]
    textos = [html.unescape(juntos[i][1]) for i in alvos]
    traduzidos = traduzir_trechos(textos, lingua)
    for i, original, novo in zip(alvos, textos, traduzidos):
        if novo != original:
            juntos[i][1] = html.escape(novo, quote=False)
    return "".join(valor for _, valor in juntos)


# ------------------------------------------------------------- baixar


def baixar(linguas: list[str] | None = None) -> None:
    PASTA.mkdir(parents=True, exist_ok=True)
    for lingua in linguas or list(PACOTES):
        nome, url = PACOTES[lingua]
        if (PASTA / nome / "model").is_dir():
            print(f"  {lingua}: já está")
            continue
        destino = PASTA / f"{nome}.zip"
        print(f"  {lingua}: baixando {url}")
        urllib.request.urlretrieve(url, destino)
        with zipfile.ZipFile(destino) as z:
            z.extractall(PASTA)
        destino.unlink()
        print(f"  {lingua}: pronto")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "baixar":
        baixar(sys.argv[2:] or None)
    else:
        inicio = time.time()
        print(traduzir_texto("Hello! We detected a new login to your account. If this was you, no action is needed.", "en"))
        print(f"{time.time() - inicio:.1f}s")
        print(json.dumps(disponivel()))
