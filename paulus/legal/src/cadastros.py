"""
PAULUS - Cadastros.

Clientes, colaboradores, socios e despesas fixas, com os documentos vinculados
a cada um.

O que faz esta tela nascer meio pronta: a classificacao ja le as partes, o
CPF/CNPJ, a data e o valor de cada contrato do acervo. Entao cadastro nao
comeca em folha em branco - comeca com uma lista de quem ja aparece nos
documentos e ainda nao esta cadastrado. Digitar vira conferir.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from financeiro import em_reais as _reais

TIPOS = {
    "cliente": "Clientes",
    "colaborador": "Colaboradores",
    "socio": "Sócios",
    "despesa": "Despesas fixas",
}

# O que uma ficha sem nada em aberto mostra. Zero e um numero; vazio nao e.
_SEM_ABERTO = {"aberto_centavos": 0, "aberto": "", "aberto_quantos": 0, "atraso_dias": 0}

CAMPOS = (
    "tipo", "nome", "documento", "telefone", "email", "endereco",
    "honorario", "dia_vencimento", "avisar_dias", "observacao",
    # Como a pessoa e paga. Fica aqui, e nao numa lista separada de gente:
    # duas listas divergem, e a hora de descobrir e a hora de pagar.
    "vinculo", "salario_centavos", "encargos_centavos",
)

# Sem vinculo, a pessoa nao entra na folha. Nao por engano - porque nao foi
# dito como ela e paga, e por um valor que ninguem digitou a folha sairia
# errada com cara de certa.
VINCULOS = {"": "não entra na folha", "clt": "CLT", "estagio": "Estágio",
            "prolabore": "Pró-labore", "autonomo": "Autônomo"}


def _chave(nome: str) -> str:
    """Nome comparavel: sem acento, sem caixa, sem pontuacao."""
    plano = unicodedata.normalize("NFKD", (nome or "").lower())
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", plano).strip()


def _so_digitos(documento: str) -> str:
    return re.sub(r"\D", "", documento or "")


class Cadastros:
    def __init__(self, base) -> None:
        self.base = base

    # ---------------------------------------------------------------- leitura

    def listar(self, tipo: str = "", termo: str = "", ordem: str = "nome") -> list[dict]:
        onde, parametros = [], []
        if tipo:
            onde.append("tipo = ?")
            parametros.append(tipo)
        if termo:
            onde.append("(nome LIKE ? OR documento LIKE ? OR email LIKE ?)")
            like = f"%{termo}%"
            parametros += [like, like, like]

        sql = "SELECT * FROM cadastros"
        if onde:
            sql += " WHERE " + " AND ".join(onde)
        sql += " ORDER BY nome COLLATE NOCASE"

        fichas = self.base.buscar(sql, tuple(parametros))
        abertos = self.em_aberto()
        for ficha in fichas:
            ficha["documentos"] = self.documentos_de(ficha["id"])
            ficha.update(abertos.get(ficha["id"], _SEM_ABERTO))

        if ordem == "aberto":
            fichas.sort(key=lambda f: -f["aberto_centavos"])
        elif ordem == "atraso":
            fichas.sort(key=lambda f: -f["atraso_dias"])
        return fichas

    def em_aberto(self) -> dict[int, dict]:
        """
        Quanto cada ficha deve, e ha quantos dias.

        Sai de uma consulta so para a lista inteira: uma por ficha seria N+1
        consultas para mostrar uma coluna. O atraso conta do vencimento mais
        antigo que ainda nao foi liquidado - e o numero que decide quem cobrar
        primeiro.
        """
        hoje = datetime.now().strftime("%Y-%m-%d")
        linhas = self.base.buscar(
            "SELECT cadastro_id, SUM(centavos) total, COUNT(*) quantos, "
            "MIN(CASE WHEN vencimento != '' AND vencimento < ? THEN vencimento END) mais_velho "
            "FROM lancamentos "
            "WHERE tipo = 'recebimento' AND liquidado_em = '' AND cadastro_id IS NOT NULL "
            "GROUP BY cadastro_id",
            (hoje,),
        )

        por_ficha: dict[int, dict] = {}
        for l in linhas:
            atraso = 0
            if l["mais_velho"]:
                atraso = (datetime.strptime(hoje, "%Y-%m-%d")
                          - datetime.strptime(l["mais_velho"], "%Y-%m-%d")).days
            por_ficha[l["cadastro_id"]] = {
                "aberto_centavos": l["total"] or 0,
                "aberto": _reais(l["total"] or 0),
                "aberto_quantos": l["quantos"],
                "atraso_dias": max(0, atraso),
            }
        return por_ficha

    def obter(self, id_: int) -> dict | None:
        ficha = self.base.um("SELECT * FROM cadastros WHERE id = ?", (id_,))
        if ficha:
            ficha["documentos"] = self.documentos_de(id_)
        return ficha

    def contagem(self) -> dict:
        return {
            tipo: self.base.contar("cadastros", "tipo = ?", (tipo,))
            for tipo in TIPOS
        }

    # ---------------------------------------------------------------- escrita

    def salvar(self, dados: dict, id_: int | None = None) -> int:
        nome = " ".join(str(dados.get("nome", "")).split())
        if not nome:
            raise ValueError("o cadastro precisa de um nome")

        limpo = {c: dados.get(c, "") for c in CAMPOS}
        limpo["nome"] = nome
        limpo["tipo"] = limpo["tipo"] if limpo["tipo"] in TIPOS else "cliente"
        limpo["dia_vencimento"] = int(limpo["dia_vencimento"] or 0)
        limpo["avisar_dias"] = int(limpo["avisar_dias"] or 0)
        limpo["vinculo"] = limpo["vinculo"] if limpo["vinculo"] in VINCULOS else ""
        limpo["salario_centavos"] = int(limpo["salario_centavos"] or 0)
        limpo["encargos_centavos"] = int(limpo["encargos_centavos"] or 0)

        if id_:
            atribui = ", ".join(f"{c} = ?" for c in CAMPOS)
            self.base.escrever(
                f"UPDATE cadastros SET {atribui}, atualizado_em = datetime('now','localtime') WHERE id = ?",
                tuple(limpo[c] for c in CAMPOS) + (id_,),
            )
            return id_

        colunas = ", ".join(CAMPOS)
        marcas = ", ".join("?" for _ in CAMPOS)
        return self.base.escrever(
            f"INSERT INTO cadastros ({colunas}, criado_em, atualizado_em) "
            f"VALUES ({marcas}, datetime('now','localtime'), datetime('now','localtime'))",
            tuple(limpo[c] for c in CAMPOS),
        )

    def apagar(self, id_: int) -> bool:
        self.base.escrever("DELETE FROM vinculos WHERE tipo = 'cadastro' AND alvo_id = ?", (id_,))
        return self.base.escrever("DELETE FROM cadastros WHERE id = ?", (id_,)) > 0

    # -------------------------------------------------------------- vinculos

    def documentos_de(self, id_: int) -> list[dict]:
        return self.base.buscar(
            "SELECT sha1, nome FROM vinculos WHERE tipo = 'cadastro' AND alvo_id = ? ORDER BY nome",
            (id_,),
        )

    def vincular(self, id_: int, sha1: str, nome: str) -> None:
        self.base.escrever(
            "INSERT OR IGNORE INTO vinculos (tipo, alvo_id, sha1, nome, criado_em) "
            "VALUES ('cadastro', ?, ?, ?, datetime('now','localtime'))",
            (id_, sha1, nome),
        )

    # ------------------------------------------------------------- sugestoes

    def sugestoes(self, cache_classificacao: Path, limite: int = 40) -> list[dict]:
        """
        Quem aparece nos documentos e ainda nao esta cadastrado.

        Le o cache da classificacao, junta as partes por nome e devolve cada
        uma com em quantos documentos apareceu e o CPF/CNPJ que veio junto.
        Cadastrar deixa de ser digitar do zero.
        """
        caminho = Path(cache_classificacao)
        if not caminho.exists():
            return []
        try:
            bruto = json.loads(caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        ja = {_chave(f["nome"]) for f in self.base.buscar("SELECT nome FROM cadastros")}
        documentos_ja = {
            _so_digitos(f["documento"])
            for f in self.base.buscar("SELECT documento FROM cadastros")
            if _so_digitos(f["documento"])
        }

        achados: dict[str, dict] = {}
        for item in (bruto.get("itens") or {}).values():
            partes = item.get("partes") or []
            docs = item.get("documentos") or []
            nome_arquivo = item.get("nome", "")
            sha1 = item.get("sha1", "")

            for posicao, parte in enumerate(partes):
                chave = _chave(parte)
                if not chave or chave in ja:
                    continue

                registro = achados.setdefault(chave, {
                    "nome": parte,
                    "documento": "",
                    "aparicoes": 0,
                    "arquivos": [],
                })
                registro["aparicoes"] += 1
                if sha1 and len(registro["arquivos"]) < 6:
                    registro["arquivos"].append({"sha1": sha1, "nome": nome_arquivo})

                # O CPF/CNPJ na mesma posicao da parte costuma ser o dela.
                if not registro["documento"] and posicao < len(docs):
                    if _so_digitos(docs[posicao]) not in documentos_ja:
                        registro["documento"] = docs[posicao]

        ordenadas = sorted(achados.values(), key=lambda x: (-x["aparicoes"], x["nome"].lower()))
        return ordenadas[:limite]
