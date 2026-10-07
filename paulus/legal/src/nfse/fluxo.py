"""
O fluxo da nota no PAULUS: as portas, Aprovações e o que acontece depois.

As quatro portas (Financeiro, Serviço, conversa e recorrência) criam o mesmo
rascunho e abrem o mesmo cartão (notas.py). Do cartão, "Pedir aprovação" põe
a nota em Aprovações como pedido próprio, com a conta e o XML resumido à
vista; quem aprova é o titular ou quem ele liberou (o nível "nfse" da
equipe), e de fora pede o código do autenticador de novo. Agente nunca
aprova: agente só propõe (a conversa cria o rascunho).

Depois de emitida: o XML (e o DANFSe, N5) na pasta do Serviço ou do cliente
no Acervo; o registro em papeis_fiscais (com situação, chave e ambiente), o
que tira o recebimento da lista "sem nota"; a proposta de e-mail ao cliente
pela Aprovação do e-mail; o aviso no carrossel; e a auditoria de cada passo.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date
from pathlib import Path

from .dinheiro import reais
from .notas import (AGUARDANDO_APROVACAO, AGUARDANDO_CONFIRMACAO, APROVADA, EMITIDA, NA_FILA, RASCUNHO,
                    REJEITADA)

log = logging.getLogger("paulus.nfse")

ACAO_EMITIR = "nfse.emitir"
CATEGORIA = "fiscal"
MESES = ("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro")


def _sem_acento(t: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()


def _hash_do_pedido(nota: dict) -> str:
    """O que foi aprovado: rascunho + conta. Mudou depois do pedido, o sim não vale."""
    bruto = json.dumps({"r": nota.get("rascunho"), "c": (nota.get("conta") or {}).get("linhas")},
                       ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def _de_onde(pessoa: dict | None) -> str:
    return "de fora" if pessoa else "na janela do escritório"


def auditar(estado, acao_texto: str, pessoa: dict | None = None, ip: str = "") -> None:
    try:
        estado.acesso_de_fora.anotar(acao="nfse", alvo=acao_texto[:400],
                                     pessoa=(pessoa or {}).get("nome") or "titular (escritório)",
                                     email=(pessoa or {}).get("email") or "", ip=ip)
    except Exception:  # noqa: BLE001 - auditoria que falha não desfaz a nota
        log.exception("nfse: auditoria")


# ------------------------------------------------------------------ portas

def competencia_da_frase(texto: str, hoje: date | None = None) -> str:
    """"setembro", "referente a setembro de 2026" -> "2026-09-01" (o mês mais
    recente que não é futuro). Sem mês na frase: vazio."""
    hoje = hoje or date.today()
    t = _sem_acento(texto)
    for i, nome in enumerate(MESES, start=1):
        if re.search(r"\b" + nome + r"\b", t):
            ano = re.search(r"\b(20\d{2})\b", t)
            a = int(ano.group(1)) if ano else (hoje.year if i <= hoje.month else hoje.year - 1)
            return f"{a}-{i:02d}-01"
    return ""


def nota_da_conversa(estado, campos: dict, quem: str = "conversa") -> dict:
    """A frase "emita a NFS-e da ACME de R$ 5.000,00 referente a setembro" vira
    o rascunho, com o que falta pedido no cartão (nunca inventado)."""
    dados: dict = {"tomador": {}}
    nome = str(campos.get("cliente") or "").strip()
    if nome:
        achado = None
        chave = _sem_acento(nome)
        for f in estado.cadastros.listar(termo=nome):
            if _sem_acento(f.get("nome") or "") == chave:
                achado = f
                break
        if achado:
            dados["cadastro_id"] = achado["id"]
        else:
            dados["tomador"]["nome"] = nome
    if campos.get("valor"):
        dados["valor_centavos"] = int(campos["valor"])
    descricao = str(campos.get("descricao") or "").strip()
    comp = competencia_da_frase(descricao) or str(campos.get("data") or "")[:10]
    if comp:
        dados["competencia"] = comp
    if descricao:
        prest = estado.nfse.prestador.atual()["dados"]
        base = (prest.get("servico") or {}).get("descricao") or "Honorários advocatícios"
        dados["descricao"] = f"{base} — {descricao}" if competencia_da_frase(descricao) else descricao
    return estado.nfse.notas.criar(dados, origem="conversa", quem=quem)


# ---------------------------------------------------------------- aprovação

def resumo_para_aprovar(estado, nota: dict) -> str:
    """O que a pessoa vê antes do sim: quem, quanto, a conta e a DPS resumida."""
    r = nota["rascunho"]
    t = r.get("tomador") or {}
    c = nota.get("conta") or {}
    linhas = [f"Tomador: {t.get('nome', '')} ({t.get('documento', '')})",
              f"Serviço: {r.get('descricao', '')}",
              f"Competência: {r.get('competencia', '')} · ambiente: "
              + ("PRODUÇÃO (vale de verdade)" if nota["ambiente"] == "producao" else "produção restrita (sem valor fiscal)")]
    for l in c.get("linhas") or []:
        if l.get("tipo") in ("valor", "retencao", "total"):
            linhas.append(f"{l['rotulo']}: {reais(int(l['centavos']))}")
    try:
        xml, ident = estado.nfse.notas.montar_xml(nota)
        texto = xml.decode("utf-8")
        resumo_xml = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " · ", texto)).strip(" ·")[:600]
        linhas.append(f"DPS {ident} (prévia; o número é reservado ao assinar): {resumo_xml}")
    except (ValueError, KeyError):
        pass
    return "\n".join(linhas)


class PrecisaConfirmar(ValueError):
    """A primeira nota de produção: a pessoa confirma que vale de verdade (N8)."""


def pedir_aprovacao(estado, nota_id: int, quem: str = "titular", pessoa: dict | None = None,
                    confirmou_producao: bool = False) -> dict:
    notas = estado.nfse.notas
    nota = notas.conferir(nota_id)
    if estado.nfse.producao.precisa_confirmar_primeira(nota) and not confirmou_producao:
        from .producao import FRASE_PRIMEIRA

        raise PrecisaConfirmar(FRASE_PRIMEIRA)
    if nota["estado"] not in (RASCUNHO, REJEITADA):
        raise ValueError(f"a nota está “{nota['estado_rotulo']}”")
    if nota["erros"]:
        raise ValueError("a nota ainda tem o que resolver: " + "; ".join(nota["erros"][:3]))
    if not estado.nfse.ligado:
        raise ValueError("a emissão de nota fiscal está desligada em Configurações › Nota fiscal")
    pode, motivos = estado.nfse.pode_emitir()
    if not pode:
        raise ValueError("ainda não dá para emitir: " + "; ".join(motivos[:3]))
    t = (nota["rascunho"].get("tomador") or {}).get("nome") or "tomador"
    titulo = f"Emitir NFS-e — {t} — {nota['valor']}"
    pedido = estado.fila.pedir(
        titulo, CATEGORIA, resumo=resumo_para_aprovar(estado, nota),
        etiquetas=["não dá para desfazer (cancela-se depois)", "sai para o Sistema Nacional",
                   "produção" if nota["ambiente"] == "producao" else "produção restrita"],
        pedido_por=quem, acao=ACAO_EMITIR,
        dados={"nota_id": nota["id"], "hash": _hash_do_pedido(nota), "sai_daqui": True,
               "ambiente": nota["ambiente"]},
        reversivel=False)
    nota = notas.mudar_estado(nota_id, AGUARDANDO_APROVACAO, quem,
                              f"pedido de aprovação ({_de_onde(pessoa)})"
                              + (" — primeira nota de produção, confirmada: vale de verdade" if confirmou_producao else ""),
                              aprovacao_id=pedido.id, pedido_por=quem)
    auditar(estado, f"pediu a emissão: {titulo}", pessoa)
    return nota


def pode_aprovar(pedido, pessoa: dict | None) -> str:
    """Vazio se pode; senão o motivo. Na janela do escritório (pessoa None), é o titular."""
    if pessoa is None:
        return ""
    if pessoa.get("papel") == "titular":
        return ""
    if (pessoa.get("permissoes") or {}).get("nfse") == "faz":
        return ""
    return "aprovar nota fiscal é do titular ou de quem ele liberou (Escritório e equipe › nível “Emitir nota fiscal”)"


def executar_aprovado(estado, pedido) -> dict | str:
    """O executor de Aprovações (acao "nfse.emitir")."""
    dados = pedido.dados or {}
    notas = estado.nfse.notas
    nota = notas.obter(int(dados.get("nota_id") or 0))
    if not nota:
        raise RuntimeError("a nota não existe mais")
    if nota["estado"] != AGUARDANDO_APROVACAO or nota.get("aprovacao_id") != pedido.id:
        raise RuntimeError(f"a nota está “{nota['estado_rotulo']}”: este pedido não vale mais")
    if _hash_do_pedido(nota) != dados.get("hash"):
        raise RuntimeError("a nota mudou depois do pedido: peça a aprovação de novo")
    quem = dados.get("decidido_por") or "titular"
    notas.mudar_estado(nota["id"], APROVADA, quem, "aprovada em Aprovações", aprovado_por=quem,
                       aprovado_em=pedido.decidido_em)
    nota = estado.nfse.envio.emitir(nota["id"], quem)
    if nota["estado"] == EMITIDA:
        texto = f"NFS-e nº {nota['numero_nfse']} emitida para {nota['tomador_nome']} ({nota['valor']}) — chave {nota['chave']}"
        return {"texto": texto, "desfecho": {"tela": "nfse", "id": nota["id"]}}
    if nota["estado"] == REJEITADA:
        frases = "; ".join(x.get("frase", "") for x in nota.get("rejeicao") or [])[:500]
        raise RuntimeError(f"a Sefin recusou a nota: {frases} — corrija no cartão e peça a aprovação de novo")
    if nota["estado"] in (AGUARDANDO_CONFIRMACAO, NA_FILA):
        return {"texto": f"enviada; {nota['estado_rotulo'].lower()}: o Paulus consulta o Sistema Nacional antes de "
                         f"qualquer reenvio e avisa quando confirmar ({nota.get('ultimo_erro') or ''})",
                "desfecho": {"tela": "nfse", "id": nota["id"]}}
    return {"texto": f"a nota ficou “{nota['estado_rotulo']}”", "desfecho": {"tela": "nfse", "id": nota["id"]}}


# ----------------------------------------------------------- depois de emitir

def _nome_arquivo(texto: str) -> str:
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", texto)
    return " ".join(t.split())[:120]


def pasta_da_nota(estado, nota: dict) -> Path:
    """A pasta do Serviço (Notas fiscais), ou Notas fiscais/<cliente> no Acervo."""
    raiz = Path(estado.pasta)
    if nota.get("origem") == "teste_assistente":
        alvo = raiz / "Notas fiscais" / "Testes"
        alvo.mkdir(parents=True, exist_ok=True)
        return alvo
    if nota.get("servico_id"):
        p = estado.servicos.pasta_de(int(nota["servico_id"]))
        if p:
            alvo = p / "Notas fiscais"
            alvo.mkdir(parents=True, exist_ok=True)
            return alvo
    cliente = nota.get("tomador_nome") or "Sem tomador"
    alvo = raiz / "Notas fiscais" / _nome_arquivo(cliente)
    alvo.mkdir(parents=True, exist_ok=True)
    return alvo


def depois_de_emitir(estado, nota: dict) -> None:
    """Acervo, registro, lançamento, e-mail, aviso e auditoria. Cada parte que
    falha fica escrita nos passos da nota; nenhuma desfaz a nota emitida."""
    notas = estado.nfse.notas
    ambiente = "produção" if nota["ambiente"] == "producao" else "produção restrita"
    base_nome = _nome_arquivo(f"NFS-e {nota['numero_nfse']} - {nota.get('tomador_nome') or ''} - "
                              f"{(nota.get('competencia') or '')[:7]}" + (" (produção restrita)" if nota["ambiente"] != "producao" else ""))
    anexos: list[str] = []
    try:
        pasta = pasta_da_nota(estado, nota)
        destino = pasta / f"{base_nome}.xml"
        destino.write_bytes(Path(nota["xml_nfse"]).read_bytes())
        anexos.append(str(destino))
        gerar_pdf = getattr(estado.nfse, "danfse_para", None)
        if gerar_pdf:
            pdf = gerar_pdf(nota)
            if pdf:
                alvo_pdf = pasta / f"{base_nome}.pdf"
                alvo_pdf.write_bytes(pdf)
                anexos.insert(0, str(alvo_pdf))
        notas.passo(nota["id"], EMITIDA, EMITIDA, "Paulus", "no Acervo: " + ", ".join(Path(a).name for a in anexos))
        if hasattr(estado, "recarregar_em_segundo_plano"):
            estado.recarregar_em_segundo_plano()
    except Exception as exc:  # noqa: BLE001
        notas.passo(nota["id"], EMITIDA, EMITIDA, "Paulus", f"não consegui guardar no Acervo: {exc}")

    if nota.get("origem") == "teste_assistente":
        # A nota do teste do assistente (teste.py): só no Acervo; nada no
        # Financeiro, nenhum e-mail ao cliente.
        auditar(estado, f"NFS-e de teste {nota['numero_nfse']} emitida (produção restrita)")
        return

    try:
        papel = estado.base.escrever(
            "INSERT INTO papeis_fiscais (tipo, numero, cadastro_id, lancamento_id, centavos, data, situacao, observacao, "
            "criado_em, chave, ambiente, nfse_nota_id) VALUES ('nota',?,?,?,?,?,?,?,datetime('now','localtime'),?,?,?)",
            (nota["numero_nfse"], nota.get("cadastro_id"), nota.get("lancamento_id"), int(nota["centavos"]),
             (nota.get("dh_proc") or date.today().isoformat())[:10], "emitida",
             f"NFS-e nacional emitida pelo Paulus ({ambiente})", nota["chave"], nota["ambiente"], nota["id"]))
        estado.base.escrever("UPDATE nfse_notas SET papel_id = ? WHERE id = ?", (papel, nota["id"]))
        notas.passo(nota["id"], EMITIDA, EMITIDA, "Paulus",
                    "registrada em notas fiscais" + (" e ligada ao recebimento" if nota.get("lancamento_id") else ""))
    except Exception as exc:  # noqa: BLE001
        notas.passo(nota["id"], EMITIDA, EMITIDA, "Paulus", f"não consegui registrar em notas fiscais: {exc}")

    try:
        proposta = propor_email(estado, nota, anexos)
        notas.passo(nota["id"], EMITIDA, EMITIDA, "Paulus", proposta)
    except Exception as exc:  # noqa: BLE001
        notas.passo(nota["id"], EMITIDA, EMITIDA, "Paulus", f"não consegui propor o e-mail: {exc}")

    auditar(estado, f"NFS-e {nota['numero_nfse']} emitida ({ambiente}) para {nota.get('tomador_nome')}, "
                    f"{nota['valor']} · pedida por {nota.get('pedido_por') or '—'} · aprovada por {nota.get('aprovado_por') or '—'}"
                    f" · DPS enviada sha256 {nota.get('hash_enviado', '')[:16]}… · NFS-e recebida sha256 "
                    f"{nota.get('hash_recebido', '')[:16]}…")


def propor_email(estado, nota: dict, anexos: list[str]) -> str:
    """O e-mail ao cliente com o PDF e o XML, como proposta em Aprovações."""
    para = (nota["rascunho"].get("tomador") or {}).get("email") or ""
    if not para:
        return "sem e-mail do tomador: a proposta de e-mail não foi criada"
    conta = estado.contas.em_uso if hasattr(estado, "contas") else None
    if conta is None:
        return "sem conta de e-mail no Paulus: a proposta de e-mail não foi criada"
    if not anexos:
        return "sem os arquivos da nota no Acervo: a proposta de e-mail não foi criada"
    prest = estado.nfse.notas.prestador_da_nota(nota)["dados"]
    assunto = f"Nota fiscal de serviço nº {nota['numero_nfse']} — {prest.get('razao_social') or ''}".strip(" —")
    corpo = (f"Prezados,\n\nSegue a nota fiscal de serviço eletrônica nº {nota['numero_nfse']}, "
             f"no valor de {nota['valor']}, referente a: {nota['rascunho'].get('descricao', '')}.\n\n"
             f"Chave de acesso: {nota['chave']}\n"
             + ("\n(Emitida em PRODUÇÃO RESTRITA, sem valor fiscal.)\n" if nota["ambiente"] != "producao" else "")
             + "\nAtenciosamente,\n" + (prest.get("razao_social") or ""))
    dados = {"conta_id": conta.id, "para": para, "cc": "", "cco": "", "assunto": assunto, "corpo": corpo,
             "corpo_html": "", "anexos": anexos, "responder_a": ""}
    try:
        import correio

        resumo = correio.resumo_do_envio(conta, para, anexos, False)
    except Exception:  # noqa: BLE001
        resumo = f"Para {para}, com {len(anexos)} anexo(s)"
    pedido = estado.fila.pedir(f"Enviar a NFS-e {nota['numero_nfse']} para {para}", "email", resumo=resumo,
                               etiquetas=["não dá para desfazer", "com anexo"], acao="correio.enviar",
                               dados=dados, reversivel=False, pedido_por="Paulus (nota fiscal)")
    return f"e-mail ao cliente proposto em Aprovações ({pedido.id})"


# ------------------------------------------------------------------ avisos

def avisos(estado, hoje: date | None = None) -> list[dict]:
    """
    O que a nota fiscal põe no carrossel (central_avisos, tipo "nota_fiscal"):
    a emitida hoje, a rejeitada, a que espera confirmação ou está na fila. Os
    ids são estáveis: o mesmo fato é sempre o mesmo aviso.
    """
    hoje = hoje or date.today()
    saida = []
    for n in estado.nfse.notas.listar((EMITIDA, REJEITADA, AGUARDANDO_CONFIRMACAO, NA_FILA, AGUARDANDO_APROVACAO), limite=100):
        nome = n.get("tomador_nome") or "tomador"
        if n["estado"] == EMITIDA:
            if (n.get("dh_proc") or "")[:10] != hoje.isoformat():
                continue
            saida.append({"id": f"nfse:emitida:{n['id']}", "titulo": f"NFS-e {n['numero_nfse']} emitida — {nome}",
                          "detalhe": n["valor"] + (" · produção restrita" if n["ambiente"] != "producao" else ""),
                          "nota_id": n["id"]})
        elif n["estado"] == REJEITADA:
            saida.append({"id": f"nfse:rejeitada:{n['id']}:{n['tentativas']}", "titulo": f"Nota fiscal recusada — {nome}",
                          "detalhe": (n.get("ultimo_erro") or "")[:140], "nota_id": n["id"]})
        elif n["estado"] in (AGUARDANDO_CONFIRMACAO, NA_FILA):
            saida.append({"id": f"nfse:{n['estado']}:{n['id']}", "titulo": f"Nota fiscal {n['estado_rotulo'].lower()} — {nome}",
                          "detalhe": "o Paulus consulta antes de reenviar; " + (n.get("ultimo_erro") or "")[:100],
                          "nota_id": n["id"]})
    for a in getattr(estado.nfse, "avisos_extras", lambda h: [])(hoje):
        saida.append(a)
    return saida
