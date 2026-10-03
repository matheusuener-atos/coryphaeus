"""
Consultar, cancelar e substituir a nota emitida (N5).

- **Cancelar** é o evento e101101 (Anexo II): motivo da tabela oficial (1 –
  Erro na emissão, 2 – Serviço não prestado, 9 – Outros) e a descrição, de
  15 a 255 caracteres. O prazo é do município (parâmetros consultados na N1):
  fora dele, o PAULUS recusa aqui, explica e oferece a substituição; sem o
  prazo nos parâmetros, quem decide é a Sefin (regra E0822), e a rejeição
  volta traduzida. Passa por Aprovações, como a emissão.
- **Substituir** é emitir uma DPS nova com o grupo `subst` (a chave da
  substituída e o motivo 01–05 ou 99). A Sefin gera a nota nova e cancela a
  antiga sozinha (evento e105102). No Simples Nacional, tomador, competência
  e valor não mudam (regra E0061) — o cartão confere.
- **Atualizar a situação** consulta os eventos da nota no Sistema Nacional e
  marca a nota cancelada ou substituída quando o evento existe lá (inclusive
  o cancelamento por ofício, feito pelo município).

O evento segue a regra da nota: o estado é gravado antes de cada passo, e
sem resposta o PAULUS consulta os eventos da nota antes de pedir de novo.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from lxml import etree

from . import assinatura, conferencia, tabelas
from .cliente import CAMPOS, NaoChegou, ProducaoBloqueada, SemResposta, de_gzip_b64
from .notas import AGUARDANDO_APROVACAO, CANCELADA, EMITIDA, SUBSTITUIDA

NS = "http://www.sped.fazenda.gov.br/nfse"
CANCELAMENTO = "101101"
POR_SUBSTITUICAO = "105102"
POR_OFICIO = "305101"
DESCRICOES = {CANCELAMENTO: "Cancelamento de NFS-e", POR_SUBSTITUICAO: "Cancelamento de NFS-e por Substituição"}
ACAO_CANCELAR = "nfse.cancelar"

PEDIDO, ESPERANDO, ENVIANDO_EV, CONFIRMANDO, REGISTRADO, REJEITADO = (
    "pedido", "aguardando_aprovacao", "enviando", "aguardando_confirmacao", "registrado", "rejeitado")


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _hash(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Eventos:
    def __init__(self, emissor) -> None:
        self.emissor = emissor
        self.base = emissor.base
        self.notas = emissor.notas

    # ------------------------------------------------------------ leitura

    def obter(self, id_: int) -> dict | None:
        e = self.base.um("SELECT * FROM nfse_eventos WHERE id = ?", (int(id_),))
        if e:
            e["rejeicao"] = json.loads(e.get("rejeicao") or "[]")
        return e

    def da_nota(self, nota_id: int) -> list[dict]:
        return self.base.buscar("SELECT * FROM nfse_eventos WHERE nota_id = ? ORDER BY id", (int(nota_id),))

    def _mudar(self, id_: int, **campos) -> dict:
        campos["atualizado_em"] = _agora()
        sets = ", ".join(f"{k} = ?" for k in campos)
        self.base.escrever(f"UPDATE nfse_eventos SET {sets} WHERE id = ?",
                           tuple(json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                                 for v in campos.values()) + (int(id_),))
        return self.obter(id_)

    # ------------------------------------------------------------ prazo

    def prazo_de_cancelamento(self, nota: dict, hoje: date | None = None) -> dict:
        """{dias, ate, dentro} — o prazo do município, quando os parâmetros dizem."""
        hoje = hoje or date.today()
        dias = self.emissor.situacao_municipio().get("prazo_cancelamento_dias")
        emitida = (nota.get("dh_proc") or "")[:10]
        if dias is None or not emitida:
            return {"dias": None, "ate": "", "dentro": True,
                    "frase": "O prazo de cancelamento é do município e não veio nos parâmetros: se tiver passado, a "
                             "Sefin recusa (regra E0822) e o PAULUS mostra o motivo."}
        ate = date.fromisoformat(emitida) + timedelta(days=int(dias))
        dentro = hoje <= ate
        return {"dias": int(dias), "ate": ate.isoformat(), "dentro": dentro,
                "frase": (f"O município deixa cancelar em até {dias} dia(s) da emissão: até {ate:%d/%m/%Y}."
                          if dentro else
                          f"O prazo de cancelamento do município ({dias} dia(s)) acabou em {ate:%d/%m/%Y}. "
                          "Para corrigir, emita uma nota substituta (a Sefin cancela esta sozinha), se o motivo for "
                          "um dos da tabela de substituição; senão, o caminho é o pedido de análise fiscal ao município.")}

    # -------------------------------------------------------- cancelamento

    def pedir_cancelamento(self, estado, nota_id: int, motivo: str, texto: str, quem: str = "titular") -> dict:
        nota = self.notas.obter(nota_id)
        if not nota or nota["estado"] != EMITIDA:
            raise ValueError("só se cancela nota emitida")
        if motivo not in tabelas.dominio("motivo_cancelamento"):
            raise ValueError("escolha o motivo da tabela oficial: 1 – Erro na emissão, 2 – Serviço não prestado, 9 – Outros")
        texto = " ".join(str(texto or "").split())
        if not 15 <= len(texto) <= 255:
            raise ValueError("descreva o motivo com 15 a 255 caracteres (regra do leiaute do evento)")
        prazo = self.prazo_de_cancelamento(nota)
        if not prazo["dentro"]:
            raise ValueError(prazo["frase"])
        abertos = [e for e in self.da_nota(nota_id) if e["tipo"] == CANCELAMENTO and e["estado"] not in (REJEITADO,)]
        if abertos:
            raise ValueError("já há um pedido de cancelamento desta nota")
        agora = _agora()
        ev_id = self.base.escrever(
            "INSERT INTO nfse_eventos (nota_id, tipo, estado, motivo, texto, pedido_por, criado_em, atualizado_em) "
            "VALUES (?,?,?,?,?,?,?,?)", (nota_id, CANCELAMENTO, PEDIDO, motivo, texto, quem, agora, agora))
        rot = tabelas.dominio("motivo_cancelamento").get(motivo, motivo)
        pedido = estado.fila.pedir(
            f"Cancelar a NFS-e {nota['numero_nfse']} — {nota.get('tomador_nome') or ''} — {nota['valor']}", "fiscal",
            resumo=(f"Motivo: {motivo} – {rot}. {texto}\n{prazo['frase']}\nChave: {nota['chave']}\n"
                    + ("Ambiente: PRODUÇÃO (vale de verdade)" if nota["ambiente"] == "producao" else "Ambiente: produção restrita")),
            etiquetas=["não dá para desfazer", "sai para o Sistema Nacional"], pedido_por=quem, acao=ACAO_CANCELAR,
            dados={"evento_id": ev_id, "nota_id": nota_id, "sai_daqui": True}, reversivel=False)
        self._mudar(ev_id, estado=ESPERANDO, aprovacao_id=pedido.id)
        self.notas.passo(nota_id, EMITIDA, EMITIDA, quem, f"pedido de cancelamento em Aprovações (motivo {motivo})")
        return self.obter(ev_id)

    def criar_cancelamento_de_teste(self, nota_id: int, motivo: str, texto: str, quem: str = "titular") -> dict:
        """O cancelamento da nota do teste do assistente (teste.py): só em produção restrita, sem Aprovações."""
        nota = self.notas.obter(nota_id)
        if not nota or nota["estado"] != EMITIDA:
            raise ValueError("só se cancela nota emitida")
        if nota["ambiente"] != "producao_restrita" or nota.get("origem") != "teste_assistente":
            raise ValueError("só a nota de teste do assistente se cancela sem Aprovações")
        agora = _agora()
        ev_id = self.base.escrever(
            "INSERT INTO nfse_eventos (nota_id, tipo, estado, motivo, texto, pedido_por, criado_em, atualizado_em) "
            "VALUES (?,?,?,?,?,?,?,?)", (nota_id, CANCELAMENTO, ESPERANDO, motivo, texto, quem, agora, agora))
        self.notas.passo(nota_id, EMITIDA, EMITIDA, quem, "teste do assistente: cancelamento pedido")
        return self._mudar(ev_id, aprovado_por=quem)

    def _pedido_xml(self, nota: dict, tipo: str, motivo: str, texto: str, chave_substituta: str = "") -> tuple[bytes, str]:
        from versao import VERSAO

        prest = self.notas.prestador_da_nota(nota)["dados"]
        ident = f"PRE{nota['chave']}{tipo}"
        raiz = etree.Element(f"{{{NS}}}pedRegEvento", nsmap={None: NS})
        raiz.set("versao", "1.01")
        inf = etree.SubElement(raiz, f"{{{NS}}}infPedReg")
        inf.set("Id", ident)

        def sub(pai, nome, valor):
            el = etree.SubElement(pai, f"{{{NS}}}{nome}")
            el.text = valor
            return el

        sub(inf, "tpAmb", "1" if nota["ambiente"] == "producao" else "2")
        sub(inf, "verAplic", f"PAULUS-{VERSAO}"[:20])
        agora = datetime.now(timezone(timedelta(hours=-3)))
        sub(inf, "dhEvento", agora.strftime("%Y-%m-%dT%H:%M:%S") + "-03:00")
        doc = prest["documento"]
        sub(inf, "CNPJAutor" if len(doc) == 14 else "CPFAutor", doc)
        sub(inf, "chNFSe", nota["chave"])
        ev = etree.SubElement(inf, f"{{{NS}}}e{tipo}")
        sub(ev, "xDesc", DESCRICOES[tipo])
        sub(ev, "cMotivo", motivo)
        if texto:
            sub(ev, "xMotivo", texto[:255])
        if chave_substituta:
            sub(ev, "chSubstituta", chave_substituta)
        return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8"), ident

    def executar_cancelamento(self, estado, pedido) -> dict | str:
        """O executor de Aprovações (acao "nfse.cancelar")."""
        dados = pedido.dados or {}
        ev = self.obter(int(dados.get("evento_id") or 0))
        if not ev or ev["estado"] != ESPERANDO or ev.get("aprovacao_id") != pedido.id:
            raise RuntimeError("este pedido de cancelamento não vale mais")
        nota = self.notas.obter(ev["nota_id"])
        if nota["estado"] != EMITIDA:
            raise RuntimeError(f"a nota está “{nota['estado_rotulo']}”")
        quem = dados.get("decidido_por") or "titular"
        self._mudar(ev["id"], aprovado_por=quem)
        ev = self.enviar(ev["id"], quem)
        nota = self.notas.obter(ev["nota_id"])
        if ev["estado"] == REGISTRADO:
            return {"texto": f"NFS-e {nota['numero_nfse']} cancelada no Sistema Nacional", "desfecho": {"tela": "nfse", "id": nota["id"]}}
        if ev["estado"] == REJEITADO:
            frases = "; ".join(x.get("frase", "") for x in ev["rejeicao"])[:500]
            raise RuntimeError(f"a Sefin recusou o cancelamento: {frases}")
        return {"texto": "pedido enviado; aguardando confirmação: o PAULUS consulta os eventos da nota antes de pedir de novo",
                "desfecho": {"tela": "nfse", "id": nota["id"]}}

    def enviar(self, ev_id: int, quem: str = "") -> dict:
        ev = self.obter(ev_id)
        nota = self.notas.obter(ev["nota_id"])
        if nota["ambiente"] == "producao" and not self.emissor.producao_liberada():
            raise ProducaoBloqueada("a produção ainda não foi liberada pelo titular")
        if ev["tentativas"]:
            # Já houve tentativa: consulta antes de pedir de novo.
            achado = self._consultar_evento(nota, ev["tipo"])
            if achado is not None:
                return self._registrado(ev, nota, achado, quem, "confirmado pela consulta")
        xml, ident = self._pedido_xml(nota, ev["tipo"], ev["motivo"], ev["texto"])
        erros = conferencia.validar_xsd(xml, nota["ambiente"], "pedRegEvento_v1.01.xsd")
        if erros:
            raise RuntimeError("o pedido de evento não passou no XSD oficial: " + "; ".join(erros[:2]))
        pfx, senha = self.emissor._pfx_e_senha()
        algoritmo = (self.emissor.prefs.dados.get("nfse") or {}).get("assinatura") or "sha1"
        assinado = assinatura.assinar(xml, pfx, senha, ident, algoritmo)
        del pfx, senha
        pasta = self.emissor.envio._pasta(nota)
        caminho = pasta / f"{ident}-pedido.xml"
        caminho.write_bytes(assinado)
        ev = self._mudar(ev_id, estado=ENVIANDO_EV, xml_pedido=str(caminho), hash_enviado=_hash(assinado),
                         tentativas=int(ev["tentativas"] or 0) + 1)
        try:
            r = self.emissor.cliente(nota["ambiente"]).registrar_evento(nota["chave"], assinado)
        except (SemResposta, NaoChegou) as exc:
            self._mudar(ev_id, estado=CONFIRMANDO, ultimo_erro=str(exc))
            achado = None
            try:
                achado = self._consultar_evento(nota, ev["tipo"])
            except (SemResposta, NaoChegou):
                pass
            if achado is not None:
                return self._registrado(self.obter(ev_id), nota, achado, quem, "confirmado pela consulta")
            return self.obter(ev_id)
        corpo = r.corpo or {}
        xml_b64 = next((v for k, v in corpo.items() if k.lower() == CAMPOS["evento"].lower()), None)
        if r.ok and xml_b64:
            return self._registrado(ev, nota, de_gzip_b64(xml_b64), quem, "registrado")
        if r.status >= 500:
            self._mudar(ev_id, estado=CONFIRMANDO, ultimo_erro=f"HTTP {r.status}")
            return self.obter(ev_id)
        from .emissao import _erros_da_resposta

        erros = _erros_da_resposta(corpo, r.texto)
        self.notas.passo(nota["id"], EMITIDA, EMITIDA, quem,
                         "cancelamento recusado: " + ", ".join(e["codigo"] for e in erros if e["codigo"]))
        return self._mudar(ev_id, estado=REJEITADO, rejeicao=erros, ultimo_erro=erros[0]["frase"] if erros else f"HTTP {r.status}")

    def _consultar_evento(self, nota: dict, tipo: str) -> bytes | None:
        """O XML do evento `tipo` da nota, se o Sistema Nacional já o tem."""
        r = self.emissor.cliente(nota["ambiente"]).consultar_eventos(nota["chave"], tipo)
        if r.status == 404 or not r.corpo:
            return None
        for v in _valores_b64(r.corpo):
            try:
                xml = de_gzip_b64(v)
            except Exception:  # noqa: BLE001
                continue
            if f"e{tipo}".encode() in xml:
                return xml
        return None

    def _registrado(self, ev: dict, nota: dict, xml_evento: bytes, quem: str, como: str) -> dict:
        pasta = self.emissor.envio._pasta(nota)
        caminho = pasta / f"EVT{nota['chave']}{ev['tipo']}-evento.xml"
        caminho.write_bytes(xml_evento)
        ev = self._mudar(ev["id"], estado=REGISTRADO, xml_evento=str(caminho), hash_recebido=_hash(xml_evento), ultimo_erro="")
        if ev["tipo"] == CANCELAMENTO:
            self._marcar(nota, CANCELADA, "cancelada", quem, f"cancelamento {como} (motivo {ev['motivo']})")
        return ev

    def _marcar(self, nota: dict, estado_nota: str, situacao_papel: str, quem: str, detalhe: str, **campos) -> None:
        self.notas.mudar_estado(nota["id"], estado_nota, quem, detalhe, **campos)
        self.base.escrever("UPDATE papeis_fiscais SET situacao = ? WHERE nfse_nota_id = ?", (situacao_papel, nota["id"]))

    # ------------------------------------------------------ atualizar situação

    def atualizar_situacao(self, nota_id: int, quem: str = "titular") -> dict:
        """Os eventos da nota no Sistema Nacional: cancelada, substituída, por ofício."""
        nota = self.notas.obter(nota_id)
        if nota["estado"] not in (EMITIDA, CANCELADA, SUBSTITUIDA):
            return self.emissor.envio.consultar(nota_id, quem, reenviar_se_nao_existe=False)
        r = self.emissor.cliente(nota["ambiente"]).consultar_eventos(nota["chave"])
        tipos = set()
        for v in _valores_b64(r.corpo or {}):
            try:
                xml = de_gzip_b64(v)
            except Exception:  # noqa: BLE001
                continue
            for t in (CANCELAMENTO, POR_SUBSTITUICAO, POR_OFICIO):
                if f"<e{t}".encode() in xml:
                    tipos.add(t)
        if nota["estado"] == EMITIDA and (CANCELAMENTO in tipos or POR_OFICIO in tipos):
            como = "por ofício (o município cancelou)" if POR_OFICIO in tipos and CANCELAMENTO not in tipos else "no Sistema Nacional"
            self._marcar(nota, CANCELADA, "cancelada", quem, f"a consulta mostrou a nota cancelada {como}")
        elif nota["estado"] == EMITIDA and POR_SUBSTITUICAO in tipos:
            self._marcar(nota, SUBSTITUIDA, "substituída", quem, "a consulta mostrou a nota cancelada por substituição")
        else:
            self.notas.passo(nota_id, nota["estado"], nota["estado"], quem,
                             "situação consultada: " + (", ".join(sorted(tipos)) if tipos else "sem eventos de cancelamento"))
        return self.notas.obter(nota_id)

    # ------------------------------------------------------------ substituir

    def criar_substituta(self, nota_id: int, motivo: str, texto: str, quem: str = "titular") -> dict:
        nota = self.notas.obter(nota_id)
        if not nota or nota["estado"] != EMITIDA:
            raise ValueError("só se substitui nota emitida")
        if motivo not in tabelas.dominio("motivo_substituicao"):
            raise ValueError("escolha o motivo da tabela oficial de substituição (01 a 05 ou 99)")
        texto = " ".join(str(texto or "").split())
        if texto and not 15 <= len(texto) <= 255:
            raise ValueError("a descrição do motivo tem de 15 a 255 caracteres")
        if motivo == "99" and not texto:
            raise ValueError("com o motivo 99 – Outros, descreva o motivo (15 a 255 caracteres)")
        ja = self.base.um("SELECT id FROM nfse_notas WHERE substitui_id = ? AND estado NOT IN ('descartada')", (nota_id,))
        if ja:
            raise ValueError("já existe uma nota substituta desta (veja a nota nova)")
        r = json.loads(json.dumps(nota["rascunho"]))
        r["substitui"] = {"chave": nota["chave"], "motivo": motivo, "texto": texto}
        nova = self.notas.criar({"cadastro_id": nota.get("cadastro_id"), "lancamento_id": nota.get("lancamento_id"),
                                 "servico_id": nota.get("servico_id"), "tomador": r.get("tomador") or {},
                                 "valor_centavos": r.get("valor_centavos"), "descricao": r.get("descricao"),
                                 "competencia": r.get("competencia"), "municipio_incidencia": r.get("municipio_incidencia", ""),
                                 "informacoes": r.get("informacoes", ""), "substitui": r["substitui"]},
                                origem="substituicao", quem=quem)
        self.base.escrever("UPDATE nfse_notas SET substitui_id = ? WHERE id = ?", (nota_id, nova["id"]))
        self.notas.passo(nota_id, EMITIDA, EMITIDA, quem, f"nota substituta criada (rascunho {nova['id']}, motivo {motivo})")
        return self.notas.conferir(nova["id"])

    def depois_de_emitir(self, nota: dict) -> None:
        """A substituta emitida: a original fica substituída e ligada à nova."""
        if not nota.get("substitui_id"):
            return
        original = self.notas.obter(nota["substitui_id"])
        if original and original["estado"] == EMITIDA:
            self._marcar(original, SUBSTITUIDA, "substituída", "PAULUS",
                         f"substituída pela NFS-e {nota['numero_nfse']} (a Sefin cancela por substituição)",
                         substituida_por_id=nota["id"])


def _valores_b64(corpo) -> list[str]:
    """Todos os textos que parecem XML compactado em base64 na resposta (lista ou objeto)."""
    saida: list[str] = []
    if isinstance(corpo, dict):
        for k, v in corpo.items():
            if isinstance(v, str) and k.lower().endswith("b64"):
                saida.append(v)
            elif isinstance(v, (list, dict)):
                saida += _valores_b64(v)
    elif isinstance(corpo, list):
        for v in corpo:
            saida += _valores_b64(v)
    return saida
