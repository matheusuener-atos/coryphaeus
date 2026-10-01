"""
Assinar, enviar e não emitir duas vezes.

A máquina de estados da nota, gravada ANTES de cada passo:

    rascunho → (Aprovações) → aprovada → assinada → enviando → emitida
                                                   ↘ aguardando confirmação → (consulta) → emitida | (não existe) reenvio
                                                   ↘ rejeitada → (corrigir) → rascunho de novo, com a MESMA identidade
                                                   ↘ na fila (não chegou) → (espera crescente) → consulta → envio

A regra que manda: **sem resposta, primeiro consulta**. Toda tentativa
depois da primeira começa consultando a identidade da DPS no Sistema
Nacional (`HEAD /dps/{id}` e `GET /dps/{id}`); reenviar só quando a consulta
diz, com certeza, que não existe nota. Se o reenvio ainda assim encontrar a
nota (E0014: "já existe NFS-e para esta DPS"), é a consulta de novo, nunca
uma segunda nota.

A nota nunca some: a que não sai fica "na fila" ou "aguardando confirmação",
com aviso, e é tentada de novo com espera crescente até alguém olhar.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

from lxml import etree

from . import assinatura, numeracao, tabelas
from .cliente import CAMPOS, NaoChegou, ProducaoBloqueada, SemResposta, de_gzip_b64
from .dinheiro import centavos_do_xml
from .notas import (AGUARDANDO_CONFIRMACAO, APROVADA, ASSINADA, EMITIDA, ENVIANDO, NA_FILA, REJEITADA)

log = logging.getLogger("paulus.nfse")

NS = "http://www.sped.fazenda.gov.br/nfse"
# Espera crescente entre tentativas, em minutos (e fica no último).
ESPERAS_MIN = (1, 2, 5, 10, 20, 40, 60)
# Rejeições que dizem "a nota já existe": não é erro do rascunho, é a prova
# de que uma tentativa anterior foi gerada — consulta e segue.
JA_EXISTE = {"E0014"}


def _agora() -> datetime:
    return datetime.now()


def _hash(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def frase_da_rejeicao(codigo: str, descricao: str = "", complemento: str = "") -> dict:
    """Código oficial + frase simples + o campo, para o cartão destacar."""
    r = tabelas.regra(codigo) or {}
    oficial = r.get("mensagem") or descricao or "rejeição sem descrição"
    campo = r.get("campo") or ""
    from .conferencia import CAMPOS as NOMES

    rotulo = NOMES.get(campo, campo)
    frase = oficial if oficial.endswith(".") else oficial + "."
    if rotulo:
        frase = f"{frase} Campo: {rotulo}."
    if complemento:
        frase += f" ({complemento[:200]})"
    return {"codigo": codigo, "descricao": descricao or oficial, "frase": frase, "campo": campo,
            "caminho": r.get("caminho", "")}


def _erros_da_resposta(corpo: dict | None, texto: str = "") -> list[dict]:
    """A lista `erros` da Sefin, tolerante a maiúsculas no nome dos campos."""
    brutos = []
    if isinstance(corpo, dict):
        for k, v in corpo.items():
            if k.lower() in ("erros", "erro", "errors") and isinstance(v, list):
                brutos = v
                break
    saida = []
    for e in brutos:
        if not isinstance(e, dict):
            continue
        low = {k.lower(): v for k, v in e.items()}
        saida.append(frase_da_rejeicao(str(low.get("codigo") or low.get("code") or ""),
                                       str(low.get("descricao") or low.get("mensagem") or ""),
                                       str(low.get("complemento") or "")))
    if not saida and texto:
        saida.append({"codigo": "", "descricao": texto[:300], "frase": texto[:300], "campo": "", "caminho": ""})
    return saida


def ler_nfse(xml: bytes) -> dict:
    """O que a nota emitida diz: chave, número, data, valores calculados pela Sefin."""
    raiz = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
    ns = {"n": NS}
    inf = raiz.find("n:infNFSe", ns)
    if inf is None:
        raise ValueError("o XML devolvido não é uma NFS-e")
    ident = inf.get("Id") or ""

    def txt(caminho: str) -> str:
        return (inf.findtext(caminho, default="", namespaces=ns) or "").strip()

    def cent(caminho: str) -> int:
        t = txt(caminho)
        return centavos_do_xml(t) if t else 0

    return {
        "chave": ident[3:] if ident.startswith("NFS") else ident,
        "numero_nfse": txt("n:nNFSe"),
        "dh_proc": txt("n:dhProc"),
        "id_dps": (inf.find("n:DPS/n:infDPS", ns).get("Id") if inf.find("n:DPS/n:infDPS", ns) is not None else ""),
        "valores": {"v_bc": cent("n:valores/n:vBC"), "p_aliq_aplic": txt("n:valores/n:pAliqAplic"),
                    "v_issqn": cent("n:valores/n:vISSQN"), "v_total_ret": cent("n:valores/n:vTotalRet"),
                    "v_liq": cent("n:valores/n:vLiq")},
        "ibscbs": {"v_bc": cent("n:IBSCBS/n:valores/n:vBC"), "v_ibs": cent("n:IBSCBS/n:totCIBS/n:gIBS/n:vIBSTot"),
                   "v_cbs": cent("n:IBSCBS/n:totCIBS/n:gCBS/n:vCBS"), "v_tot_nf": cent("n:IBSCBS/n:totCIBS/n:vTotNF")},
    }


class Envio:
    """O envio das notas de um Emissor (servico.Emissor)."""

    def __init__(self, emissor) -> None:
        self.emissor = emissor
        self.notas = emissor.notas
        self._trava = threading.RLock()
        self.ao_emitir: list = []        # quem precisa saber (N4: Acervo, papeis, e-mail, aviso)
        self._parar = threading.Event()
        self._fio: threading.Thread | None = None

    # ------------------------------------------------------------- arquivos

    def _pasta(self, nota: dict) -> Path:
        mes = (nota.get("competencia") or datetime.now().date().isoformat())[:7]
        p = self.emissor.pasta / "xml" / nota["ambiente"] / mes
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _guardar(self, nota: dict, nome: str, conteudo: bytes) -> str:
        alvo = self._pasta(nota) / nome
        alvo.write_bytes(conteudo)
        return str(alvo)

    # ------------------------------------------------------------- assinar

    def assinar(self, nota_id: int, quem: str = "") -> dict:
        """Reserva o número (se ainda não tem), monta, valida no XSD e assina."""
        from .conferencia import validar_xsd

        nota = self.notas.obter(nota_id)
        if nota["estado"] != APROVADA:
            raise ValueError(f"a nota está “{nota['estado_rotulo']}”; só se assina a aprovada")
        self._conferir_ambiente(nota)
        prest = self.notas.prestador_da_nota(nota)["dados"]
        serie = nota.get("serie") or prest.get("serie") or "1"
        numero = nota.get("numero")
        if not numero:
            numero = numeracao.reservar(self.emissor.base, nota["ambiente"], serie)
        conta = self.notas.conta_de(nota)
        xml, ident = self.notas.montar_xml({**nota, "serie": serie, "numero": numero}, numero=numero, conta=conta)
        erros = validar_xsd(xml, nota["ambiente"])
        if erros:
            raise ValueError("a DPS não passou no XSD oficial: " + "; ".join(erros[:3]))
        pfx, senha = self.emissor._pfx_e_senha()
        algoritmo = (self.emissor.prefs.dados.get("nfse") or {}).get("assinatura") or "sha1"
        assinado = assinatura.assinar(xml, pfx, senha, ident, algoritmo)
        del pfx, senha
        caminho = self._guardar(nota, f"{ident}-dps.xml", assinado)
        raiz = etree.fromstring(xml)
        dh = raiz.findtext(f"{{{NS}}}infDPS/{{{NS}}}dhEmi") or ""
        return self.notas.mudar_estado(nota_id, ASSINADA, quem, f"assinada; DPS {ident}", serie=serie, numero=numero,
                                       id_dps=ident, dh_emi=dh, xml_dps=caminho, hash_enviado=_hash(assinado))

    # -------------------------------------------------------------- enviar

    def emitir(self, nota_id: int, quem: str = "") -> dict:
        """Da aprovada (ou assinada) até emitida, rejeitada, na fila ou aguardando confirmação."""
        with self._trava:
            nota = self.notas.obter(nota_id)
            self._conferir_ambiente(nota)
            if nota["estado"] == APROVADA:
                nota = self.assinar(nota_id, quem)
            if nota["estado"] in (NA_FILA, AGUARDANDO_CONFIRMACAO, ENVIANDO) or (nota["estado"] == ASSINADA and nota["tentativas"]):
                # Já houve tentativa: a próxima coisa é SEMPRE consultar.
                return self.consultar(nota_id, quem, reenviar_se_nao_existe=True)
            if nota["estado"] != ASSINADA:
                raise ValueError(f"a nota está “{nota['estado_rotulo']}” e não vai ao Sistema Nacional")
            return self._enviar(nota, quem)

    def _enviar(self, nota: dict, quem: str) -> dict:
        assinado = Path(nota["xml_dps"]).read_bytes()
        try:
            cliente = self.emissor.cliente(nota["ambiente"])
        except ProducaoBloqueada:
            raise
        except Exception as exc:  # noqa: BLE001 - certificado ou senha: fica na fila, com o motivo
            return self._para_fila(nota, f"não deu para preparar o envio: {exc}", quem, chegou=False)
        if self.emissor.transporte is None:
            # Antes do primeiro envio de verdade, os nomes do JSON conferidos no
            # Swagger oficial (só abre com o certificado). Divergência trava.
            if not self.emissor.contrato():
                try:
                    self.emissor.conferir_contrato(cliente)
                except (SemResposta, NaoChegou):
                    pass
            trava = self.emissor.contrato_trava()
            if trava:
                raise ValueError(trava)
        nota = self.notas.mudar_estado(nota["id"], ENVIANDO, quem, "enviando ao Sistema Nacional",
                                       tentativas=int(nota["tentativas"] or 0) + 1)
        try:
            r = cliente.emitir(assinado)
        except NaoChegou as exc:
            return self._para_fila(nota, str(exc), quem, chegou=False)
        except SemResposta as exc:
            self.notas.mudar_estado(nota["id"], AGUARDANDO_CONFIRMACAO, quem, f"sem resposta: {exc}",
                                    ultimo_erro=str(exc))
            return self.consultar(nota["id"], quem, reenviar_se_nao_existe=False)
        return self._tratar_resposta(nota, r, quem)

    def _tratar_resposta(self, nota: dict, r, quem: str) -> dict:
        corpo = r.corpo or {}
        xml_b64 = next((v for k, v in corpo.items() if k.lower() == CAMPOS["nfse"].lower()), None)
        if r.ok and xml_b64:
            return self._registrar_emitida(nota, de_gzip_b64(xml_b64), quem, "emitida")
        if r.status >= 500 or r.status in (408, 429):
            # Servidor com problema: pode ter gerado ou não. Consulta antes de tudo.
            self.notas.mudar_estado(nota["id"], AGUARDANDO_CONFIRMACAO, quem, f"resposta {r.status} do Sistema Nacional",
                                    ultimo_erro=f"HTTP {r.status}")
            return self.consultar(nota["id"], quem, reenviar_se_nao_existe=False)
        erros = _erros_da_resposta(corpo, r.texto)
        if any(e["codigo"] in JA_EXISTE for e in erros):
            self.notas.mudar_estado(nota["id"], AGUARDANDO_CONFIRMACAO, quem,
                                    "a Sefin diz que esta DPS já gerou nota (E0014): consultando", ultimo_erro="E0014")
            return self.consultar(nota["id"], quem, reenviar_se_nao_existe=False)
        return self.notas.mudar_estado(nota["id"], REJEITADA, quem,
                                       "rejeitada: " + ", ".join(e["codigo"] for e in erros if e["codigo"]),
                                       rejeicao=erros, ultimo_erro=(erros[0]["frase"] if erros else f"HTTP {r.status}"),
                                       esperas=0, proxima_tentativa="")

    def _para_fila(self, nota: dict, motivo: str, quem: str, chegou: bool) -> dict:
        atual = self.notas.obter(nota["id"]) or nota
        n = int(atual.get("esperas") or 0)
        espera = ESPERAS_MIN[min(n, len(ESPERAS_MIN) - 1)]
        proxima = (_agora() + timedelta(minutes=espera)).isoformat(timespec="seconds")
        return self.notas.mudar_estado(nota["id"], NA_FILA if not chegou else AGUARDANDO_CONFIRMACAO, quem,
                                       f"{motivo}; nova tentativa em {espera} min", ultimo_erro=motivo,
                                       proxima_tentativa=proxima, esperas=n + 1)

    def _conferir_ambiente(self, nota: dict) -> None:
        """Produção só com a liberação do titular — antes de reservar número ou assinar."""
        if nota["ambiente"] == "producao" and not self.emissor.producao_liberada():
            raise ProducaoBloqueada("a produção ainda não foi liberada pelo titular "
                                    "(Configurações › Nota fiscal › Produção)")

    # ------------------------------------------------------------ consultar

    def consultar(self, nota_id: int, quem: str = "", reenviar_se_nao_existe: bool = True) -> dict:
        """
        Pergunta ao Sistema Nacional se a DPS desta nota já virou NFS-e.

        - existe: busca a chave e o XML e registra como emitida;
        - não existe, com certeza (404 no HEAD): reenvia a MESMA DPS, se pedido;
        - sem resposta: continua aguardando confirmação, com nova consulta agendada.
        """
        with self._trava:
            nota = self.notas.obter(nota_id)
            if nota["estado"] == EMITIDA:
                return nota
            self._conferir_ambiente(nota)
            if not nota.get("id_dps"):
                raise ValueError("a nota ainda não tem DPS assinada")
            try:
                cliente = self.emissor.cliente(nota["ambiente"])
                existe = cliente.dps_existe(nota["id_dps"])
            except (SemResposta, NaoChegou) as exc:
                return self._para_fila({**nota, "estado": AGUARDANDO_CONFIRMACAO}, f"consulta sem resposta: {exc}", quem, chegou=True)
            if existe.status == 200:
                try:
                    r = cliente.consultar_dps(nota["id_dps"])
                    chave = next((v for k, v in (r.corpo or {}).items() if k.lower() == CAMPOS["chave"].lower()), "")
                    if not chave:
                        raise SemResposta("a consulta da DPS não trouxe a chave")
                    rn = cliente.consultar_nfse(chave)
                    xml_b64 = next((v for k, v in (rn.corpo or {}).items() if k.lower() == CAMPOS["nfse"].lower()), "")
                    if not xml_b64:
                        raise SemResposta("a consulta da NFS-e não trouxe o XML")
                except (SemResposta, NaoChegou) as exc:
                    return self._para_fila({**nota, "estado": AGUARDANDO_CONFIRMACAO},
                                           f"a nota existe, mas a consulta não terminou: {exc}", quem, chegou=True)
                return self._registrar_emitida(nota, de_gzip_b64(xml_b64), quem, "confirmada pela consulta")
            if existe.status == 404:
                self.notas.passo(nota_id, nota["estado"], nota["estado"], quem,
                                 "consulta: a DPS não gerou nota no Sistema Nacional")
                if not reenviar_se_nao_existe:
                    return self._para_fila({**nota, "estado": NA_FILA}, "a DPS não chegou a gerar nota", quem, chegou=False)
                nota = self.notas.mudar_estado(nota_id, ASSINADA, quem, "consulta confirmou: não existe; reenviando a mesma DPS")
                return self._enviar(nota, quem)
            return self._para_fila({**nota, "estado": AGUARDANDO_CONFIRMACAO},
                                   f"a consulta respondeu {existe.status}", quem, chegou=True)

    def _registrar_emitida(self, nota: dict, xml_nfse: bytes, quem: str, como: str) -> dict:
        dados = ler_nfse(xml_nfse)
        if dados["id_dps"] and nota.get("id_dps") and dados["id_dps"] != nota["id_dps"]:
            raise ValueError("a NFS-e devolvida é de outra DPS")
        caminho = self._guardar(nota, f"{dados['chave'] or nota['id_dps']}-nfse.xml", xml_nfse)
        conta = dict(nota.get("conta") or {})
        conta["sefin"] = {**dados["valores"], "ibscbs": dados["ibscbs"]}
        avisos = list(nota.get("avisos") or [])
        prev = conta.get("v_liq")
        if prev is not None and dados["valores"]["v_liq"] and dados["valores"]["v_liq"] != prev:
            from .dinheiro import reais

            avisos.append(f"a Sefin calculou valor líquido {reais(dados['valores']['v_liq'])}, diferente da previsão "
                          f"({reais(prev)}): vale o da nota emitida")
        emitida = self.notas.mudar_estado(nota["id"], EMITIDA, quem, f"{como}: NFS-e {dados['numero_nfse']}, chave {dados['chave']}",
                                          chave=dados["chave"], numero_nfse=dados["numero_nfse"], dh_proc=dados["dh_proc"],
                                          xml_nfse=caminho, hash_recebido=_hash(xml_nfse), conta=conta, avisos=avisos,
                                          ultimo_erro="", proxima_tentativa="", rejeicao=[], esperas=0)
        for funcao in self.ao_emitir:
            try:
                funcao(emitida)
            except Exception:  # noqa: BLE001 - o que vem depois não desfaz a nota emitida
                log.exception("nfse: depois de emitir")
        return self.notas.obter(nota["id"])

    # --------------------------------------------------- fila e retomada

    def pendentes(self) -> list[dict]:
        return self.notas.listar((NA_FILA, AGUARDANDO_CONFIRMACAO, ENVIANDO, ASSINADA))

    def retomar(self, quem: str = "abertura") -> list[dict]:
        """
        Ao abrir o programa: a nota que estava "enviando" quando ele caiu vai
        para "aguardando confirmação" e é consultada; nada é reenviado às cegas.
        """
        resultados = []
        for nota in self.pendentes():
            if nota["estado"] == ENVIANDO:
                self.notas.mudar_estado(nota["id"], AGUARDANDO_CONFIRMACAO, quem,
                                        "o programa fechou durante o envio: consultando antes de qualquer reenvio")
            try:
                resultados.append(self.consultar(nota["id"], quem, reenviar_se_nao_existe=True)
                                  if nota["tentativas"] else self.emitir(nota["id"], quem))
            except (ValueError, ProducaoBloqueada) as exc:
                log.warning("nfse: retomar nota %s: %s", nota["id"], exc)
        return resultados

    def processar_fila(self, quem: str = "fila") -> list[dict]:
        """As notas cuja próxima tentativa já chegou."""
        agora = _agora().isoformat(timespec="seconds")
        feitas = []
        for nota in self.pendentes():
            if nota["estado"] in (NA_FILA, AGUARDANDO_CONFIRMACAO) and (nota.get("proxima_tentativa") or "") <= agora:
                try:
                    feitas.append(self.emitir(nota["id"], quem))
                except (ValueError, ProducaoBloqueada) as exc:
                    log.warning("nfse: fila nota %s: %s", nota["id"], exc)
        return feitas

    def ligar_fila(self, intervalo_s: int = 60) -> None:
        """O fio que tenta de novo, em segundo plano, enquanto o programa está aberto."""
        if self._fio and self._fio.is_alive():
            return

        def girar() -> None:
            try:
                self.retomar()
            except Exception:  # noqa: BLE001
                log.exception("nfse: retomar")
            while not self._parar.wait(intervalo_s):
                if not self.emissor.ligado:
                    continue
                try:
                    self.processar_fila()
                except Exception:  # noqa: BLE001
                    log.exception("nfse: fila")
                try:
                    self.emissor.rotina_diaria()
                except Exception:  # noqa: BLE001
                    log.exception("nfse: rotina diária")

        self._fio = threading.Thread(target=girar, name="nfse-fila", daemon=True)
        self._fio.start()

    def parar_fila(self) -> None:
        self._parar.set()
