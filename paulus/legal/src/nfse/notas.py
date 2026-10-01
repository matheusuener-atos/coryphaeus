"""
As notas: do rascunho (o cartão) até o fim, com cada passo registrado.

O rascunho é o que a pessoa vê e edita no cartão: o tomador (vindo dos
Cadastros, com o que falta pedido), a descrição, a competência, o valor, o
serviço e o município da prestação. Toda mudança refaz a conta
(tributos.py), monta a DPS de prévia e confere no XSD oficial e nas regras
(conferencia.py). Erro bloqueia; aviso não.

O número da DPS não é reservado no rascunho (rascunho se descarta): a prévia
usa o próximo número só para conferir o XSD.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime

from . import conferencia, numeracao, tributos
from . import dps as dps_mod
from .dinheiro import centavos_de_texto, reais

RASCUNHO = "rascunho"
AGUARDANDO_APROVACAO = "aguardando_aprovacao"
APROVADA = "aprovada"
ASSINADA = "assinada"
ENVIANDO = "enviando"
AGUARDANDO_CONFIRMACAO = "aguardando_confirmacao"
NA_FILA = "na_fila"
EMITIDA = "emitida"
REJEITADA = "rejeitada"
CANCELADA = "cancelada"
SUBSTITUIDA = "substituida"
DESCARTADA = "descartada"

ESTADOS = {
    RASCUNHO: "Rascunho",
    AGUARDANDO_APROVACAO: "Esperando aprovação",
    APROVADA: "Aprovada",
    ASSINADA: "Assinada",
    ENVIANDO: "Enviando",
    AGUARDANDO_CONFIRMACAO: "Aguardando confirmação",
    NA_FILA: "Na fila de envio",
    EMITIDA: "Emitida",
    REJEITADA: "Rejeitada",
    CANCELADA: "Cancelada",
    SUBSTITUIDA: "Substituída",
    DESCARTADA: "Descartada",
}

EDITAVEIS = (RASCUNHO, REJEITADA)

CAMPOS_TOMADOR = ("nome", "documento", "logradouro", "numero", "complemento", "bairro", "cep", "cmun", "uf",
                  "inscricao_municipal", "email", "telefone")


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json(texto, padrao):
    try:
        v = json.loads(texto) if texto else padrao
    except (TypeError, json.JSONDecodeError):
        return padrao
    return v if v is not None else padrao


class _ContaLida:
    """A conta gravada em JSON, com os mesmos atributos da tributos.Conta."""

    def __init__(self, d: dict) -> None:
        base = tributos.Conta().to_dict()
        base.update(d or {})
        self.__dict__.update(base)


class Notas:
    def __init__(self, emissor) -> None:
        self.emissor = emissor
        self.base = emissor.base

    # ------------------------------------------------------------- leitura

    def _ler(self, linha: dict | None) -> dict | None:
        if not linha:
            return None
        n = dict(linha)
        for campo, padrao in (("rascunho", {}), ("conta", {}), ("erros", []), ("avisos", []), ("rejeicao", [])):
            n[campo] = _json(n.get(campo), padrao)
        n["estado_rotulo"] = ESTADOS.get(n["estado"], n["estado"])
        n["valor"] = reais(int(n.get("centavos") or 0))
        n["editavel"] = n["estado"] in EDITAVEIS
        return n

    def obter(self, id_: int) -> dict | None:
        return self._ler(self.base.um("SELECT * FROM nfse_notas WHERE id = ?", (int(id_),)))

    def listar(self, estados: tuple | list | None = None, mes: str = "", limite: int = 300) -> list[dict]:
        sql, par = "SELECT * FROM nfse_notas WHERE 1=1", []
        if estados:
            sql += f" AND estado IN ({','.join('?' for _ in estados)})"
            par += list(estados)
        if mes:
            sql += " AND substr(competencia,1,7) = ?"
            par.append(mes)
        sql += " ORDER BY id DESC LIMIT ?"
        par.append(int(limite))
        return [self._ler(l) for l in self.base.buscar(sql, tuple(par))]

    def passos(self, id_: int) -> list[dict]:
        return self.base.buscar("SELECT * FROM nfse_passos WHERE nota_id = ? ORDER BY id", (int(id_),))

    def passo(self, id_: int, de: str, para: str, quem: str = "", detalhe: str = "") -> None:
        self.base.escrever("INSERT INTO nfse_passos (nota_id, quando, de, para, quem, detalhe) VALUES (?,?,?,?,?,?)",
                           (int(id_), _agora(), de, para, quem, detalhe[:2000]))

    def mudar_estado(self, id_: int, para: str, quem: str = "", detalhe: str = "", **campos) -> dict:
        """Grava o estado (e os campos) ANTES de o passo seguinte acontecer."""
        atual = self.obter(id_)
        sets = ["estado = ?", "atualizado_em = ?"]
        valores: list = [para, _agora()]
        for k, v in campos.items():
            sets.append(f"{k} = ?")
            valores.append(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
        valores.append(int(id_))
        self.base.escrever(f"UPDATE nfse_notas SET {', '.join(sets)} WHERE id = ?", tuple(valores))
        self.passo(id_, atual["estado"] if atual else "", para, quem, detalhe)
        return self.obter(id_)

    # ----------------------------------------------------------- tomador

    def tomador_do_cadastro(self, cadastro_id) -> dict:
        if not cadastro_id:
            return {}
        f = self.base.um("SELECT * FROM cadastros WHERE id = ?", (int(cadastro_id),))
        if not f:
            return {}
        return {
            "nome": f.get("nome") or "", "documento": re.sub(r"[^0-9A-Za-z]", "", f.get("documento") or "").upper(),
            "logradouro": f.get("end_logradouro") or "", "numero": f.get("end_numero") or "",
            "complemento": f.get("end_complemento") or "", "bairro": f.get("end_bairro") or "",
            "cep": f.get("end_cep") or "", "cmun": f.get("end_cmun") or "", "uf": f.get("end_uf") or "",
            "inscricao_municipal": f.get("inscricao_municipal") or "",
            "email": f.get("email_nota") or f.get("email") or "",
            "telefone": re.sub(r"\D", "", f.get("telefone") or ""),
        }

    def _gravar_no_cadastro(self, cadastro_id, tomador: dict) -> None:
        """O que a pessoa completou no cartão vai para a ficha — só onde a ficha estava vazia."""
        if not cadastro_id:
            return
        f = self.base.um("SELECT * FROM cadastros WHERE id = ?", (int(cadastro_id),))
        if not f:
            return
        mapa = {"logradouro": "end_logradouro", "numero": "end_numero", "complemento": "end_complemento",
                "bairro": "end_bairro", "cep": "end_cep", "cmun": "end_cmun", "uf": "end_uf",
                "inscricao_municipal": "inscricao_municipal", "email": "email_nota"}
        mudar = {col: tomador[k] for k, col in mapa.items() if tomador.get(k) and not f.get(col)}
        if mudar:
            sets = ", ".join(f"{c} = ?" for c in mudar)
            self.base.escrever(f"UPDATE cadastros SET {sets}, atualizado_em = datetime('now','localtime') WHERE id = ?",
                               tuple(mudar.values()) + (int(cadastro_id),))

    # ------------------------------------------------------------- escrita

    def _limpar(self, dados: dict, anterior: dict | None = None) -> dict:
        r = dict(anterior or {})
        tom = dict(r.get("tomador") or {})
        for k in CAMPOS_TOMADOR:
            if k in (dados.get("tomador") or {}):
                tom[k] = " ".join(str(dados["tomador"][k] or "").split())
        tom["documento"] = re.sub(r"[^0-9A-Za-z]", "", tom.get("documento") or "").upper()
        tom["cep"] = re.sub(r"\D", "", tom.get("cep") or "")
        tom["cmun"] = re.sub(r"\D", "", tom.get("cmun") or "")
        if tom.get("cmun"):
            from . import tabelas

            tom["uf"] = (tabelas.municipio(tom["cmun"]) or {}).get("uf", tom.get("uf", ""))
        r["tomador"] = tom
        if "valor" in dados:
            r["valor_centavos"] = centavos_de_texto(dados["valor"])
        if "valor_centavos" in dados:
            r["valor_centavos"] = int(dados["valor_centavos"])
        if "desconto" in dados:
            r["desconto_incond_centavos"] = centavos_de_texto(dados["desconto"])
        for k in ("descricao", "competencia", "ctribnac", "nbs", "ctribmun", "municipio_incidencia", "informacoes"):
            if k in dados:
                r[k] = str(dados[k] or "").strip()
        for k in ("ctribnac", "nbs", "ctribmun", "municipio_incidencia"):
            if r.get(k):
                r[k] = re.sub(r"\D", "", r[k])
        if "substitui" in dados:
            r["substitui"] = dados["substitui"]
        r.setdefault("valor_centavos", 0)
        r.setdefault("desconto_incond_centavos", 0)
        return r

    def criar(self, dados: dict, origem: str = "manual", quem: str = "") -> dict:
        dados = dict(dados or {})
        if dados.get("servico_id") and not dados.get("cadastro_id"):
            # A nota dos honorários do Serviço: o tomador é o cliente do Serviço.
            s = self.base.um("SELECT cadastro_id, nome FROM servicos WHERE id = ?", (int(dados["servico_id"]),))
            if s and s.get("cadastro_id"):
                dados["cadastro_id"] = s["cadastro_id"]
            if s and not dados.get("descricao"):
                dados["descricao_servico"] = s.get("nome") or ""
        prest = self.emissor.prestador.atual()
        rascunho_base = {"tomador": self.tomador_do_cadastro(dados.get("cadastro_id")),
                         "descricao": (prest["dados"].get("servico") or {}).get("descricao") or "",
                         "competencia": date.today().isoformat()}
        lanc = None
        if dados.get("lancamento_id"):
            lanc = self.base.um("SELECT * FROM lancamentos WHERE id = ?", (int(dados["lancamento_id"]),))
            if lanc:
                rascunho_base["valor_centavos"] = int(lanc.get("centavos") or 0)
                if lanc.get("liquidado_em"):
                    rascunho_base["competencia"] = str(lanc["liquidado_em"])[:10]
                if not rascunho_base["tomador"] and lanc.get("cadastro_id"):
                    rascunho_base["tomador"] = self.tomador_do_cadastro(lanc["cadastro_id"])
                    dados.setdefault("cadastro_id", lanc["cadastro_id"])
                if lanc.get("descricao") and not dados.get("descricao"):
                    rascunho_base["descricao"] = (rascunho_base["descricao"] + " — " if rascunho_base["descricao"] else "") + lanc["descricao"]
        if dados.get("descricao_servico") and not dados.get("descricao"):
            rascunho_base["descricao"] = (rascunho_base["descricao"] + " — " if rascunho_base["descricao"] else "") + dados["descricao_servico"]
        rascunho = self._limpar(dados, rascunho_base)
        agora = _agora()
        id_ = self.base.escrever(
            "INSERT INTO nfse_notas (estado, ambiente, origem, cadastro_id, lancamento_id, servico_id, recorrencia_id, "
            "prestador_versao, rascunho, pedido_por, criado_em, atualizado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (RASCUNHO, self.emissor.ambiente, origem, dados.get("cadastro_id"), dados.get("lancamento_id"),
             dados.get("servico_id"), dados.get("recorrencia_id"), prest["id"],
             json.dumps(rascunho, ensure_ascii=False), quem, agora, agora))
        self.passo(id_, "", RASCUNHO, quem, f"nota criada ({origem})")
        return self.conferir(id_)

    def atualizar(self, id_: int, dados: dict, quem: str = "", gravar_no_cadastro: bool = True) -> dict:
        nota = self.obter(id_)
        if not nota:
            raise ValueError("nota não encontrada")
        if nota["estado"] not in EDITAVEIS:
            raise ValueError(f"a nota está “{nota['estado_rotulo']}” e não se edita mais")
        rascunho = self._limpar(dados, nota["rascunho"])
        cadastro_id = dados.get("cadastro_id", nota.get("cadastro_id"))
        if dados.get("cadastro_id") and dados["cadastro_id"] != nota.get("cadastro_id"):
            rascunho["tomador"] = self.tomador_do_cadastro(dados["cadastro_id"])
            rascunho = self._limpar(dados, rascunho)
        if gravar_no_cadastro:
            self._gravar_no_cadastro(cadastro_id, rascunho.get("tomador") or {})
        self.base.escrever("UPDATE nfse_notas SET rascunho = ?, cadastro_id = ?, atualizado_em = ? WHERE id = ?",
                           (json.dumps(rascunho, ensure_ascii=False), cadastro_id, _agora(), int(id_)))
        self.passo(id_, nota["estado"], nota["estado"], quem, "rascunho editado")
        return self.conferir(id_)

    # ------------------------------------------------------------ conferir

    def prestador_da_nota(self, nota: dict) -> dict:
        """A versão da configuração com que a nota foi (ou será) montada."""
        if nota["estado"] in EDITAVEIS or not nota.get("prestador_versao"):
            return self.emissor.prestador.atual()
        return self.emissor.prestador.versao(nota["prestador_versao"]) or self.emissor.prestador.atual()

    def calcular(self, nota: dict) -> tuple[dict, tributos.Conta]:
        prest = self.prestador_da_nota(nota)["dados"]
        mun = self.emissor.situacao_municipio()
        conta = tributos.calcular(prest, nota["rascunho"], municipio_ativo=mun["situacao"] == "conveniado")
        return prest, conta

    def montar_xml(self, nota: dict, numero: int | None = None, quando: datetime | None = None,
                   conta=None) -> tuple[bytes, str]:
        prest = self.prestador_da_nota(nota)["dados"]
        if conta is None:
            _, conta = self.calcular(nota)
        serie = nota.get("serie") or prest.get("serie") or "1"
        if numero is None:
            numero = nota.get("numero") or numeracao.proximo(self.base, self.emissor.ambiente, serie)
        from versao import VERSAO

        return dps_mod.montar(prest=prest, nota=nota["rascunho"], conta=conta, ambiente=self.emissor.ambiente,
                              serie=serie, numero=numero, quando=quando, ver_aplic=f"PAULUS-{VERSAO}")

    def conferir(self, id_: int) -> dict:
        """Refaz a conta, monta a prévia da DPS e confere no XSD e nas regras."""
        nota = self.obter(id_)
        prest_v = self.prestador_da_nota(nota)
        prest = prest_v["dados"]
        _, conta = self.calcular(nota)
        lanc = self.base.um("SELECT * FROM lancamentos WHERE id = ?", (nota["lancamento_id"],)) if nota.get("lancamento_id") else None
        cert = (self.emissor.certificado_para_tela() or {}).get("certificado") or None
        erros, avisos = conferencia.conferir(prest=prest, nota=nota["rascunho"], conta=conta,
                                             municipio=self.emissor.situacao_municipio(), certificado=cert, lancamento=lanc)
        faltas = self.emissor.prestador.para_tela()["faltas"] if nota["estado"] in EDITAVEIS else []
        erros = [f"configuração: falta {f}" for f in faltas] + erros
        if not erros:
            try:
                xml, _ = self.montar_xml(nota, conta=conta)
                erros += conferencia.validar_xsd(xml, self.emissor.ambiente)
            except (ValueError, KeyError) as exc:
                erros.append(f"não consegui montar a DPS: {exc}")
        r = nota["rascunho"]
        campos = {"conta": conta.to_dict(), "erros": erros, "avisos": avisos,
                  "centavos": int(r.get("valor_centavos") or 0), "competencia": r.get("competencia") or "",
                  "tomador_nome": (r.get("tomador") or {}).get("nome") or "",
                  "tomador_documento": (r.get("tomador") or {}).get("documento") or ""}
        if nota["estado"] in EDITAVEIS:
            campos["prestador_versao"] = prest_v["id"]
        sets = ", ".join(f"{k} = ?" for k in campos)
        self.base.escrever(f"UPDATE nfse_notas SET {sets} WHERE id = ?",
                           tuple(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                                 for v in campos.values()) + (int(id_),))
        return self.obter(id_)

    def descartar(self, id_: int, quem: str = "") -> dict:
        """Rascunho, rejeitada ou esperando aprovação podem ser descartadas; emitida, nunca."""
        nota = self.obter(id_)
        if not nota:
            raise ValueError("nota não encontrada")
        if nota["estado"] not in (RASCUNHO, REJEITADA, AGUARDANDO_APROVACAO, APROVADA):
            raise ValueError(f"a nota está “{nota['estado_rotulo']}”: nota emitida não se apaga, se cancela")
        if nota.get("numero") and nota["estado"] == REJEITADA:
            # Rejeitada não virou NFS-e: o número volta para o próximo (sem buraco).
            numeracao.devolver(self.base, nota["ambiente"], nota["serie"], nota["numero"])
        return self.mudar_estado(id_, DESCARTADA, quem, "descartada", numero=None, id_dps=None)

    def conta_de(self, nota: dict):
        return _ContaLida(nota.get("conta") or {})
