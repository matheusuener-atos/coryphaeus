"""
O extrato do banco, lido e conferido contra o que o escritorio lancou.

A tela do Financeiro tinha dois avisos de "em breve" que eram o mesmo assunto:
importar extrato e conciliacao bancaria. Sem o extrato nao ha o que conferir; e
com ele, conferir a mao e ler duas listas em paralelo procurando o mesmo valor
- o trabalho que um programa faz sem errar.

Tres decisoes:

**Le o que o banco exporta, nao o que seria bonito.** OFX e o formato que todo
banco brasileiro oferece no internet banking, e vem em SGML antigo, sem
fechar etiqueta. CSV vem de qualquer jeito: ponto e virgula ou virgula,
data com barra ou com traco, valor com virgula decimal, as vezes debito e
credito em colunas separadas. Aqui as duas coisas entram.

**Conciliar propoe, nao decide.** Cada par que o programa acha volta para a
tela com o motivo, e quem marca e a pessoa. Dar baixa sozinho num lancamento
por causa de um valor igual seria escrever no livro-caixa de alguem por
palpite - e valor igual acontece o tempo todo num escritorio que cobra
honorario fixo.

**O centavo e inteiro.** Igual ao resto do Financeiro: comparar dinheiro em
ponto flutuante erra silenciosamente, e conciliacao e justamente onde o erro
de um centavo faz o par nao aparecer.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

# Quantos dias de distancia entre o vencimento e a data do banco ainda contam
# como o mesmo pagamento. Boleto pago com atraso de uma semana e comum; um mes
# depois ja e outra historia, e a pessoa que decide.
JANELA_DIAS = 10

FORMATOS = (".ofx", ".csv", ".txt")


@dataclass
class Movimento:
    """Uma linha do extrato, do jeito que o banco mandou."""

    data: str = ""          # ISO
    descricao: str = ""
    centavos: int = 0       # positivo entra, negativo sai
    documento: str = ""     # FITID do OFX, quando houver

    def to_dict(self) -> dict:
        return {"data": self.data, "descricao": self.descricao,
                "centavos": self.centavos, "documento": self.documento,
                "tipo": "recebimento" if self.centavos >= 0 else "despesa"}


@dataclass
class Par:
    """Um movimento do banco e o lancamento que parece ser ele."""

    movimento: Movimento
    lancamento: dict | None = None
    pontos: int = 0
    motivos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "movimento": self.movimento.to_dict(),
            "lancamento_id": (self.lancamento or {}).get("id"),
            "lancamento": {
                "descricao": (self.lancamento or {}).get("descricao", ""),
                "cliente": (self.lancamento or {}).get("cadastro_nome") or "",
                "vencimento": (self.lancamento or {}).get("vencimento") or "",
                "centavos": (self.lancamento or {}).get("centavos", 0),
            } if self.lancamento else None,
            "pontos": self.pontos,
            "porque": " · ".join(self.motivos),
        }


# ------------------------------------------------------------------ leitura


def ler(dados: bytes, nome: str = "") -> list[Movimento]:
    """
    Os movimentos do arquivo - OFX ou CSV.

    Levanta ValueError com a frase que a tela mostra. Nao adivinha formato pelo
    conteudo quando a extensao ja diz; adivinhar so serve para achar que leu.
    """
    texto = _texto(dados)
    sufixo = ("." + nome.rsplit(".", 1)[-1].lower()) if "." in nome else ""
    if sufixo == ".ofx" or "<OFX>" in texto.upper():
        movimentos = _do_ofx(texto)
    elif sufixo in (".csv", ".txt"):
        movimentos = _do_csv(texto)
    else:
        raise ValueError("leio extrato em OFX ou CSV — é o que os bancos exportam")

    if not movimentos:
        raise ValueError("não achei lançamento nenhum nesse arquivo")
    return sorted(movimentos, key=lambda m: (m.data, -abs(m.centavos)))


def _texto(dados: bytes) -> str:
    """O arquivo como texto. Banco ainda manda Latin-1, e nao avisa."""
    for codigo in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = dados.decode(codigo)
        except UnicodeDecodeError:
            continue
        if texto.count("�") < len(texto) * 0.01:
            return texto
    return dados.decode("latin-1", errors="replace")


RE_TRN = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.S | re.I)


def _campo_ofx(bloco: str, etiqueta: str) -> str:
    """O valor de <TAG>, com ou sem fechamento - o OFX dos bancos nao fecha."""
    achado = re.search(rf"<{etiqueta}>([^<\r\n]*)", bloco, re.I)
    return (achado.group(1).strip() if achado else "")


def _do_ofx(texto: str) -> list[Movimento]:
    movimentos = []
    for bloco in RE_TRN.findall(texto):
        valor = _centavos(_campo_ofx(bloco, "TRNAMT"))
        if valor is None:
            continue
        bruta = _campo_ofx(bloco, "DTPOSTED")[:8]
        try:
            quando = date(int(bruta[0:4]), int(bruta[4:6]), int(bruta[6:8])).isoformat()
        except (ValueError, IndexError):
            continue
        descricao = _campo_ofx(bloco, "MEMO") or _campo_ofx(bloco, "NAME") or "Movimento"
        movimentos.append(Movimento(data=quando, descricao=" ".join(descricao.split()),
                                    centavos=valor, documento=_campo_ofx(bloco, "FITID")))
    return movimentos


CABECA_DATA = ("data", "dt", "data lancamento", "data movimento", "data do lancamento")
CABECA_VALOR = ("valor", "valor r$", "montante", "quantia", "credito/debito")
CABECA_SALDO = ("saldo",)
CABECA_TEXTO = ("historico", "descricao", "lancamento", "detalhe", "memo", "documento")


def _do_csv(texto: str) -> list[Movimento]:
    linhas = [x for x in texto.splitlines() if x.strip()]
    if not linhas:
        return []
    separador = ";" if linhas[0].count(";") >= linhas[0].count(",") else ","
    tabela = list(csv.reader(io.StringIO("\n".join(linhas)), delimiter=separador))
    tabela = [linha for linha in tabela if any(c.strip() for c in linha)]
    if not tabela:
        return []

    cabeca = [_plano(c) for c in tabela[0]]
    tem_cabecalho = any(c in CABECA_DATA or c in CABECA_VALOR or c in CABECA_TEXTO for c in cabeca)
    corpo = tabela[1:] if tem_cabecalho else tabela

    col_data = col_valor = col_texto = -1
    if tem_cabecalho:
        for i, nome in enumerate(cabeca):
            if col_data < 0 and nome in CABECA_DATA:
                col_data = i
            elif col_valor < 0 and nome in CABECA_VALOR:
                col_valor = i
            elif col_texto < 0 and nome in CABECA_TEXTO:
                col_texto = i

    movimentos = []
    for linha in corpo:
        quando = _data(linha[col_data]) if 0 <= col_data < len(linha) else _primeira_data(linha)
        if not quando:
            continue
        if 0 <= col_valor < len(linha):
            valor = _centavos(linha[col_valor])
        else:
            valor = _ultimo_valor(linha, cabeca if tem_cabecalho else [])
        if valor is None or valor == 0:
            continue
        if 0 <= col_texto < len(linha):
            descricao = linha[col_texto]
        else:
            descricao = max((c for c in linha if not _data(c) and _centavos(c) is None),
                            key=len, default="Movimento")
        movimentos.append(Movimento(data=quando, descricao=" ".join(descricao.split()) or "Movimento",
                                    centavos=valor))
    return movimentos


def _primeira_data(linha: list[str]) -> str:
    for celula in linha:
        quando = _data(celula)
        if quando:
            return quando
    return ""


def _ultimo_valor(linha: list[str], cabeca: list[str]) -> int | None:
    """
    O valor da linha quando nao ha coluna dita "valor".

    Pega o ultimo numero da linha, mas nunca o que estiver debaixo de "saldo":
    conciliar pelo saldo daria sempre errado, e errado de um jeito dificil de
    perceber - o numero existe e parece dinheiro.
    """
    escolhido = None
    for i, celula in enumerate(linha):
        if i < len(cabeca) and cabeca[i] in CABECA_SALDO:
            continue
        valor = _centavos(celula)
        if valor is not None and valor != 0:
            escolhido = valor
    return escolhido


RE_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
RE_DATA_BR = re.compile(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})")


def _data(celula: str) -> str:
    bruto = (celula or "").strip()
    achado = RE_DATA_ISO.match(bruto)
    if achado:
        try:
            return date(int(achado.group(1)), int(achado.group(2)), int(achado.group(3))).isoformat()
        except ValueError:
            return ""
    achado = RE_DATA_BR.match(bruto)
    if achado:
        dia, mes, ano = (int(x) for x in achado.groups())
        ano += 2000 if ano < 100 else 0
        try:
            return date(ano, mes, dia).isoformat()
        except ValueError:
            return ""
    return ""


RE_VALOR = re.compile(r"^-?R?\$?\s*-?\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?-?$|^-?R?\$?\s*-?\d+(?:[.,]\d{1,2})?-?$")


def _centavos(celula: str) -> int | None:
    """
    "1.234,56" e "-1234.56" viram centavos. Devolve None quando nao e numero.

    O sinal pode vir depois ("1.234,56-"), como alguns bancos exportam, e o
    "D" de debito tambem aparece; os dois viram saida.
    """
    bruto = (celula or "").strip().replace("\xa0", " ")
    if not bruto:
        return None
    negativo = bruto.startswith("-") or bruto.endswith("-") or bruto.upper().endswith(" D")
    bruto = re.sub(r"(?i)\s*[CD]$", "", bruto).strip()
    if not RE_VALOR.match(bruto):
        return None
    limpo = bruto.replace("R$", "").replace(" ", "").strip("-")
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        valor = round(float(limpo) * 100)
    except ValueError:
        return None
    return -abs(valor) if negativo else valor


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", (texto or "").strip().lower())
    return " ".join("".join(c for c in normal if unicodedata.category(c) != "Mn").split())


# --------------------------------------------------------------- conciliar


PALAVRAS_DE_BANCO = {
    "pix", "ted", "doc", "tarifa", "pagto", "pagamento", "transferencia", "recebido",
    "enviado", "credito", "debito", "cobranca", "boleto", "liquidacao", "titulo",
    "de", "da", "do", "para", "ref", "cc", "cp", "sa", "ltda", "me", "eireli",
}


def _palavras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z0-9]{3,}", _plano(texto)) if p not in PALAVRAS_DE_BANCO}


def conciliar(movimentos: list[Movimento], lancamentos: list[dict]) -> list[Par]:
    """
    Para cada movimento do banco, o lancamento em aberto que parece ser ele.

    O valor tem de bater no centavo e o sinal tem de fazer sentido (dinheiro
    que entrou so casa com recebimento). Dai a data aproxima e o nome
    desempata. Cada lancamento e usado uma vez so: dois recebimentos iguais no
    mesmo mes sao coisas diferentes, e casar os dois com a mesma linha do banco
    seria dar baixa em dobro.
    """
    abertos = [l for l in lancamentos if not l.get("liquidado_em")]
    usados: set[int] = set()
    pares: list[Par] = []

    # Os candidatos sao avaliados por movimento, e o melhor par de cada um vale
    # na ordem em que o extrato veio - que e a ordem do dia.
    for movimento in movimentos:
        melhor, melhor_pontos, melhor_motivos = None, 0, []
        for lancamento in abertos:
            if lancamento["id"] in usados:
                continue
            if abs(int(lancamento.get("centavos", 0))) != abs(movimento.centavos):
                continue
            entrada = movimento.centavos >= 0
            if entrada != (lancamento.get("tipo") == "recebimento"):
                continue

            pontos, motivos = 60, ["valor igual"]
            dias = _distancia(movimento.data, lancamento.get("vencimento") or "")
            if dias is None:
                pontos -= 10
            elif dias == 0:
                pontos += 30
                motivos.append("mesma data do vencimento")
            elif dias <= JANELA_DIAS:
                pontos += 20 - dias
                motivos.append(f"{dias} dia(s) do vencimento")
            else:
                continue

            comuns = _palavras(movimento.descricao) & (
                _palavras(lancamento.get("descricao", "")) | _palavras(lancamento.get("cadastro_nome") or ""))
            if comuns:
                pontos += 15
                motivos.append("nome parecido: " + ", ".join(sorted(comuns)[:2]))

            if pontos > melhor_pontos:
                melhor, melhor_pontos, melhor_motivos = lancamento, pontos, motivos

        if melhor:
            usados.add(melhor["id"])
        pares.append(Par(movimento=movimento, lancamento=melhor, pontos=melhor_pontos,
                         motivos=melhor_motivos or ["sem lançamento parecido"]))
    return pares


def _distancia(a: str, b: str) -> int | None:
    try:
        return abs((date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days)
    except (ValueError, TypeError):
        return None


def resumo(pares: list[Par]) -> dict:
    """O que a tela mostra em cima da lista."""
    achados = [p for p in pares if p.lancamento]
    entradas = sum(p.movimento.centavos for p in pares if p.movimento.centavos > 0)
    saidas = sum(-p.movimento.centavos for p in pares if p.movimento.centavos < 0)
    dias = sorted({p.movimento.data for p in pares})
    return {
        "movimentos": len(pares),
        "conciliados": len(achados),
        "sozinhos": len(pares) - len(achados),
        "entradas": entradas,
        "saidas": saidas,
        "de": dias[0] if dias else "",
        "ate": dias[-1] if dias else "",
    }


def meses_do_extrato(movimentos: list[Movimento]) -> list[str]:
    """Os meses que o arquivo cobre, para buscar so os lancamentos deles."""
    meses = {m.data[:7] for m in movimentos if m.data}
    # Boleto vence num mes e cai no outro: o mes anterior ao primeiro entra.
    if meses:
        primeiro = min(meses)
        try:
            ano, mes = int(primeiro[:4]), int(primeiro[5:7])
            anterior = date(ano, mes, 1) - timedelta(days=1)
            meses.add(anterior.isoformat()[:7])
        except ValueError:
            pass
    return sorted(meses)
