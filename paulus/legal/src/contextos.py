"""
O que o escritorio ensinou ao assistente, com as proprias palavras.

A tela de Configuracoes pede isso desde o desenho (docs/ui, A13): um titulo,
um texto curto, e em que gaveta guardar - regras de redacao, modelos,
clientes, correcoes. Ate agora o botao Guardar dizia "em breve", e o que o
assistente sabia era so o que estava no Acervo.

A diferenca entre isto e o Acervo importa. O Acervo sao os documentos, e a
busca escolhe os trechos que tem a ver com a pergunta. Isto aqui e o que vale
SEMPRE: "o aviso de nao renovacao neste escritorio e de 90 dias", "a cliente
se chama Cooperativa Brasileira, nunca COOBRAMEX no texto final". Sao poucas
linhas, e elas entram em toda pergunta.

Por isso o tamanho e limitado de proposito. O modelo desta maquina tem 3
bilhoes de parametros e uma janela que ja e disputada pelos trechos dos
documentos; encher metade dela de regras deixaria menos espaco justamente
para o que a pergunta pediu. O limite e por lembrete e no total, e a tela
mostra quanto ja esta em uso.
"""

from __future__ import annotations

import re
from datetime import datetime

# As gavetas do desenho. "Regras de redacao" tem um papel a mais: e a unica
# que tambem vai junto quando o assistente escreve no editor - regra de como
# escrever serve para escrever; o nome de um cliente, nao.
GAVETAS = ("Regras de redação", "Modelos", "Clientes", "Correções")
GAVETA_PADRAO = GAVETAS[0]

MAX_TITULO = 80
MAX_TEXTO = 600

# Quanto tudo isto pode ocupar em cada pergunta, somado. Ver o cabecalho.
LIMITE_BLOCO = 2400


# Quanto de um arquivo vai para o modelo quando alguem ensina por documento.
# Um contrato inteiro nao cabe na janela junto com a instrucao, e as regras
# que interessam costumam estar no comeco - qualificacao, objeto, prazos.
LEITURA_MAX = 6000

INSTRUCAO_DO_ARQUIVO = (
    "Leia o documento abaixo e escreva o que um assistente do escritorio precisa "
    "LEMBRAR dele para sempre: regras, prazos, nomes proprios como sao escritos, "
    "o jeito da casa. Nao resuma o documento e nao conte o que aconteceu no caso. "
    "No maximo 4 frases curtas, em portugues do Brasil, sem lista e sem titulo. "
    "So o que estiver escrito no documento - nao invente nada."
)


def titulo_do_arquivo(nome: str) -> str:
    """Um titulo apresentavel a partir do nome do arquivo."""
    limpo = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", str(nome or "")).replace("_", " ").replace("-", " ")
    limpo = " ".join(limpo.split())[:MAX_TITULO]
    return (limpo[0].upper() + limpo[1:]) if limpo else "Do arquivo"


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Contextos:
    """Os lembretes que entram em toda conversa com o assistente."""

    def __init__(self, base) -> None:
        self.base = base

    def listar(self, gaveta: str = "") -> list[dict]:
        sql = "SELECT * FROM contextos"
        args: tuple = ()
        if gaveta:
            sql += " WHERE gaveta = ?"
            args = (gaveta,)
        sql += " ORDER BY id DESC"
        return self.base.buscar(sql, args)

    def obter(self, id_: int) -> dict | None:
        return self.base.um("SELECT * FROM contextos WHERE id = ?", (id_,))

    def salvar(self, dados: dict, id_: int | None = None) -> int:
        titulo = " ".join(str(dados.get("titulo", "")).split())[:MAX_TITULO]
        texto = str(dados.get("texto", "")).strip()[:MAX_TEXTO]
        gaveta = dados.get("gaveta") if dados.get("gaveta") in GAVETAS else GAVETA_PADRAO
        if not titulo:
            raise ValueError("o lembrete precisa de um título")
        if not texto:
            raise ValueError("escreva o que eu devo saber")

        if id_:
            self.base.escrever(
                "UPDATE contextos SET titulo = ?, texto = ?, gaveta = ? WHERE id = ?",
                (titulo, texto, gaveta, id_))
            return id_
        return self.base.escrever(
            "INSERT INTO contextos (titulo, texto, gaveta, criado_em) VALUES (?, ?, ?, ?)",
            (titulo, texto, gaveta, _agora()))

    def bloco(self, gavetas=None, limite: int = LIMITE_BLOCO) -> str:
        """
        O texto que entra na instrucao do assistente - ou vazio, se nao ha nada.

        Os mais novos entram primeiro: quem acabou de ensinar alguma coisa
        espera que ela valha na proxima pergunta. Se o total passar do limite,
        o que sobra fica de fora em silencio aqui, mas a tela avisa: ela mostra
        quanto esta em uso e marca os que nao couberam.
        """
        linhas, usado = [], 0
        for item in self.listar():
            if gavetas and item["gaveta"] not in gavetas:
                continue
            pedaco = f"- {item['titulo']}: {item['texto']}"
            if usado + len(pedaco) > limite:
                break
            linhas.append(pedaco)
            usado += len(pedaco) + 1
        if not linhas:
            return ""
        return ("O escritório me ensinou o seguinte, e isto vale sempre:\n"
                + "\n".join(linhas))

    def cabem(self, gavetas=None, limite: int = LIMITE_BLOCO) -> set[int]:
        """Quais lembretes entram de fato na pergunta, pelo limite de tamanho."""
        dentro, usado = set(), 0
        for item in self.listar():
            if gavetas and item["gaveta"] not in gavetas:
                continue
            pedaco = f"- {item['titulo']}: {item['texto']}"
            if usado + len(pedaco) > limite:
                break
            dentro.add(item["id"])
            usado += len(pedaco) + 1
        return dentro

    def para_tela(self) -> dict:
        """A lista, as gavetas e quanto disso o assistente carrega por pergunta."""
        itens = self.listar()
        cabem = self.cabem()
        for item in itens:
            item["entra"] = item["id"] in cabem
        bloco = self.bloco()
        return {
            "contextos": itens,
            "gavetas": list(GAVETAS),
            "caracteres": len(bloco),
            "limite": LIMITE_BLOCO,
            "de_fora": len([x for x in itens if not x["entra"]]),
        }
