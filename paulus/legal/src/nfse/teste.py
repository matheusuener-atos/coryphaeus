"""
O teste do assistente: uma nota de verdade em produção restrita, e o cancelamento dela.

É o passo 4 da tela da nota fiscal (Configurações › Nota fiscal). A pessoa
escolhe um cliente do Cadastro e aperta "Fazer o teste"; o PAULUS:

1. monta uma nota de R$ 1,00 para esse cliente, com a configuração de agora,
   e confere no XSD e nas regras (erro de configuração aparece aqui, com a
   frase de sempre);
2. assina com o certificado A1 e manda ao Sistema Nacional de PRODUÇÃO
   RESTRITA (sem valor fiscal) — o envio confere antes os nomes da API no
   Swagger oficial (emissao.py);
3. cancela a nota no mesmo Sistema Nacional (evento 101101).

Deu tudo certo: o resultado fica gravado com a "impressão" da configuração
(tudo menos o ambiente e a revisão). Mudou a configuração depois, o teste
vale para a de antes e a tela pede outro.

O clique em "Fazer o teste" é a aprovação desta nota: ela não passa pela fila
de Aprovações porque não tem valor fiscal e só sai em produção restrita. Nada
é mandado ao cliente (nem e-mail, nem registro em notas fiscais do Financeiro).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from .cliente import CertificadoInvalido, NaoChegou, ProducaoBloqueada, SemResposta
from .notas import APROVADA, CANCELADA, EMITIDA, REJEITADA

ORIGEM = "teste_assistente"
VALOR_CENTAVOS = 100
DESCRICAO = "Nota de teste do PAULUS — produção restrita, sem valor fiscal"
MOTIVO_CANCELAMENTO = "1"
TEXTO_CANCELAMENTO = "Nota de teste do assistente do PAULUS, emitida em produção restrita, sem valor fiscal."
FORA_DA_IMPRESSAO = ("ambiente", "revisado_por", "revisado_em")


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def impressao(dados: dict) -> str:
    """A configuração fiscal que importa para o teste (sem ambiente e revisão)."""
    d = {k: v for k, v in (dados or {}).items() if k not in FORA_DA_IMPRESSAO}
    return hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _frases(lista) -> str:
    return "; ".join(x.get("frase", "") for x in (lista or []) if x.get("frase"))[:500]


class Teste:
    def __init__(self, emissor) -> None:
        self.emissor = emissor

    def ultimo(self) -> dict:
        teste = dict(self.emissor.producao._marcas().get("teste") or {})
        if teste:
            atual = impressao(self.emissor.prestador.atual()["dados"])
            teste["vale_para_agora"] = bool(teste.get("ok")) and teste.get("impressao") == atual
        return teste

    def _gravar(self, teste: dict) -> dict:
        prod = self.emissor.producao
        marcas = prod._marcas()
        marcas["teste"] = teste
        self.emissor.pasta.mkdir(parents=True, exist_ok=True)
        prod._arquivo.write_text(json.dumps(marcas, ensure_ascii=False, indent=1), encoding="utf-8")
        return self.ultimo()

    def fazer(self, cadastro_id: int, quem: str = "titular") -> dict:
        """Roda o teste e devolve {ok, etapas, frase, ...}; nunca levanta por falha do teste."""
        e = self.emissor
        etapas: list[dict] = []
        prest = e.prestador.atual()

        def etapa(titulo: str, ok: bool, detalhe: str = "") -> bool:
            etapas.append({"titulo": titulo, "ok": ok, "detalhe": detalhe})
            return ok

        def fim(ok: bool, frase: str, **extra) -> dict:
            return self._gravar({"ok": ok, "frase": frase, "etapas": etapas, "em": _agora(), "por": quem,
                                 "impressao": impressao(prest["dados"]), "versao": prest["id"], **extra})

        if e.ambiente != "producao_restrita":
            raise ValueError("o teste é em produção restrita: volte para ela antes de testar")
        if not cadastro_id:
            raise ValueError("escolha o cliente da nota de teste")
        if not e.ligado:
            e.ligar(True)
        pode, motivos = e.pode_emitir()
        if not etapa("Configuração completa", pode, "; ".join(motivos)):
            return fim(False, "Ainda falta configurar: " + "; ".join(motivos) + ".")

        nota = e.notas.criar({"cadastro_id": int(cadastro_id), "valor_centavos": VALOR_CENTAVOS, "descricao": DESCRICAO},
                             origem=ORIGEM, quem=quem)
        nota = e.notas.conferir(nota["id"])
        if not etapa("Nota montada e conferida no leiaute oficial", not nota["erros"], "; ".join(nota["erros"])):
            e.notas.descartar(nota["id"], quem=quem)
            return fim(False, "A nota de teste não passou na conferência: " + "; ".join(nota["erros"][:3]) + ".")

        e.notas.mudar_estado(nota["id"], APROVADA, quem, "teste do assistente: aprovada por quem pediu o teste",
                             aprovado_por=quem, aprovado_em=_agora())
        try:
            nota = e.envio.emitir(nota["id"], quem)
        except (CertificadoInvalido, ProducaoBloqueada, ValueError) as exc:
            etapa("Assinada e enviada ao Sistema Nacional", False, str(exc))
            return fim(False, f"Não consegui enviar: {exc}.", nota_id=nota["id"])
        if nota["estado"] == REJEITADA:
            etapa("Assinada e enviada ao Sistema Nacional", True)
            etapa("Aceita pela Sefin", False, _frases(nota.get("rejeicao")) or nota.get("ultimo_erro") or "")
            return fim(False, "A Sefin recusou a nota de teste: " + (_frases(nota.get("rejeicao")) or nota.get("ultimo_erro") or "")
                       + ". Corrija a configuração e teste de novo.", nota_id=nota["id"])
        if nota["estado"] != EMITIDA:
            etapa("Assinada e enviada ao Sistema Nacional", True)
            etapa("Aceita pela Sefin", False, nota.get("ultimo_erro") or nota["estado_rotulo"])
            return fim(False, "O Sistema Nacional não respondeu a tempo. O PAULUS consulta antes de reenviar; "
                       "tente o teste de novo em alguns minutos.", nota_id=nota["id"])
        etapa("Assinada e enviada ao Sistema Nacional", True)
        etapa("Aceita pela Sefin", True, f"NFS-e nº {nota['numero_nfse']}")

        ev_mod = e.eventos
        try:
            ev = ev_mod.criar_cancelamento_de_teste(nota["id"], MOTIVO_CANCELAMENTO, TEXTO_CANCELAMENTO, quem)
            ev = ev_mod.enviar(ev["id"], quem)
        except (CertificadoInvalido, ProducaoBloqueada, SemResposta, NaoChegou, ValueError, RuntimeError) as exc:
            etapa("Cancelamento registrado", False, str(exc))
            return fim(False, f"A nota de teste saiu (nº {nota['numero_nfse']}), mas o cancelamento falhou: {exc}.",
                       nota_id=nota["id"], numero=nota["numero_nfse"], chave=nota["chave"])
        nota = e.notas.obter(nota["id"])
        cancelou = nota["estado"] == CANCELADA
        if not etapa("Cancelamento registrado", cancelou, "" if cancelou else (_frases(ev.get("rejeicao")) or ev.get("ultimo_erro") or "")):
            return fim(False, f"A nota de teste saiu (nº {nota['numero_nfse']}), mas o cancelamento não foi confirmado: "
                       + (_frases(ev.get("rejeicao")) or ev.get("ultimo_erro") or "sem resposta") + ".",
                       nota_id=nota["id"], numero=nota["numero_nfse"], chave=nota["chave"])
        return fim(True, "Tudo certo: a nota de teste foi emitida e cancelada no Sistema Nacional. "
                         "Você já pode mudar para produção.",
                   nota_id=nota["id"], numero=nota["numero_nfse"], chave=nota["chave"])
