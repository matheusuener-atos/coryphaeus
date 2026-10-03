"""
A triagem da pergunta na nuvem (02/10/2026).

Antes de ler qualquer coisa, uma chamada curta ao modelo da nuvem responde três
coisas, em JSON:

- `assunto`: "lei" (o direito em tese: prazo, requisito, cabimento),
  "documentos" (o que está escrito nos documentos do escritório) ou "ambos"
  (a lei aplicada a um documento);
- `documentos`: quais documentos do Acervo a pergunta pede, pelo nome exato
  da lista - "o contrato entre Wanderson e Valter" é o arquivo "COMPRA E VENDA
  - WANDERSON X VALTER UENER R$ 200.000,00.pdf";
- `dispositivos`: os artigos que fundamentam a resposta ("cpc", "335").

Por quê, medido na bateria de 02/10: a pergunta "qual o prazo para contestar?"
lia trechos de 19 documentos do Acervo e respondia de um PDF sobre confissão;
os 11 códigos instalados (7.015 artigos) nunca eram lidos, porque a conversa
só chegava a eles quando a pergunta escrevia o número do artigo. E a pergunta
sobre o contrato do Wanderson mandava 44 KB de trechos de 15 documentos sem a
cláusula do preço - o contrato inteiro tem 5 mil caracteres.

O que a triagem diz é conferido em código antes de valer: documento fora da
lista some; artigo que não existe na base de leis some (src/leis.py). Sem
nuvem, sem internet ou com JSON quebrado, devolve None e a conversa segue pelo
caminho de sempre.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
import uuid

_log = logging.getLogger("paulus.triagem")

CODIGOS_VALIDOS = ("cc", "cpc", "cf", "clt", "cdc", "cp", "cpp", "ctn", "eca", "ctb", "inquilinato")
MAX_DOCUMENTOS = 4
MAX_DISPOSITIVOS = 6
# A lista de nomes que vai junto: acervo grande não vira uma pergunta cara.
MAX_NOMES = 120

INSTRUCAO = """Você faz a triagem de uma pergunta feita ao PAULUS, o programa de um escritório de advocacia \
brasileiro. Responda só com um objeto JSON, nesta ordem:
{"assunto": "lei", "documentos": [], "em_tese": "o réu contesta em 15 dias úteis (art. 335 do CPC)", \
"dispositivos": [{"codigo": "cpc", "artigo": "335"}]}

em_tese: só com assunto "lei" ou "ambos" - a resposta em uma frase curta, com o artigo que a fundamenta. \
Escreva antes dos dispositivos: os dispositivos são os artigos que esta frase cita. Com assunto "documentos", "".

assunto:
- "lei": a pergunta é sobre o direito em tese (prazo, requisito, cabimento, o que a lei diz) e não pede nada \
dos documentos do escritório;
- "documentos": pede o que está escrito nos documentos do escritório (valores, datas, partes, cláusulas, \
validade);
- "ambos": aplica a lei a um documento do escritório (por exemplo: "esta procuração atende o art. 105 do CPC?").

documentos: os nomes EXATOS, copiados da lista abaixo, dos documentos que a pergunta pede. Só quando a \
pergunta indica claramente quais (pelas partes, pelo tipo e pelas pessoas). Se puder ser mais de um e a \
pergunta não disser qual, ponha todos os candidatos (até 4). Se a pergunta for sobre todos ou não der para \
saber, []. Com assunto "lei", [].

dispositivos: até 6 artigos que fundamentam a resposta, só quando você tiver segurança do número. codigo é \
um destes: cc, cpc, cf, clt, cdc, cp, cpp, ctn, eca, ctb, inquilinato. artigo é o número ("335", "1.003", \
"5"). Pergunta só sobre documentos: [].

Documentos do escritório:
{nomes}"""


def _plano(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


def _ler_json(bruto: str) -> dict | None:
    try:
        dados = json.loads(bruto)
    except ValueError:
        ini, fim = bruto.find("{"), bruto.rfind("}")
        if ini == -1 or fim <= ini:
            return None
        try:
            dados = json.loads(bruto[ini:fim + 1])
        except ValueError:
            return None
    return dados if isinstance(dados, dict) else None


def conferir(dados: dict, nomes: list[str], leis=None) -> dict:
    """
    O que a triagem disse, só com o que existe: nomes da lista (comparados sem
    acento e sem caixa) e artigos que estão na base de leis.
    """
    assunto = str(dados.get("assunto") or "").strip().lower()
    if assunto not in ("lei", "documentos", "ambos"):
        assunto = "documentos"
    por_plano = {_plano(n): n for n in nomes}
    documentos: list[str] = []
    for n in dados.get("documentos") or []:
        achado = por_plano.get(_plano(str(n)).strip())
        if achado and achado not in documentos:
            documentos.append(achado)
    dispositivos: list[tuple[str, str]] = []
    for d in dados.get("dispositivos") or []:
        if not isinstance(d, dict):
            continue
        codigo = str(d.get("codigo") or "").strip().lower()
        numero = str(d.get("artigo") or d.get("numero") or "").strip()
        numero = re.sub(r"(?i)^art(?:igo)?\.?\s*", "", numero).strip().rstrip("º°o ")
        if codigo not in CODIGOS_VALIDOS or not numero:
            continue
        if leis is not None and not leis.artigo(codigo, numero):
            continue
        if (codigo, numero) not in dispositivos:
            dispositivos.append((codigo, numero))
    if assunto == "lei":
        documentos = []
    return {"assunto": assunto, "documentos": documentos[:MAX_DOCUMENTOS],
            "dispositivos": dispositivos[:MAX_DISPOSITIVOS]}


def triar(estado, pergunta: str, documentos, historico=None, leis=None, trabalho_id: str = "", pessoa=None) -> dict | None:
    """
    {"assunto", "documentos", "dispositivos", "tokens"} ou None (sem nuvem, sem
    internet, resposta que não é JSON). Mascarado e registrado como todo envio.
    """
    import nuvem

    if not nuvem.usa(estado, "conversa"):
        return None
    quem = nuvem.quem_envia(estado, pessoa)
    if nuvem.limite_atingido(estado, quem):
        return None
    caminhos = [str(getattr(d, "path", "") or "") for d in documentos or []]
    # O nome de um documento que não pode sair (caso só do escritório, anexo do
    # e-mail, cópia do Drive) também não sai na lista.
    nomes = [d.name for d, c in zip(documentos or [], caminhos) if not nuvem.motivo_para_ficar(estado, [c])][:MAX_NOMES]
    c = nuvem.config(estado)
    provedor = c.get("provedor") or "paulus"
    modelo = c.get("modelo") or nuvem.PROVEDORES.get(provedor, {}).get("padrao", "")
    mascara = nuvem.Mascara() if c.get("mascarar", True) else None
    lista = "\n".join("- " + n for n in nomes) or "(nenhum)"
    sistema = INSTRUCAO.replace("{nomes}", lista)
    antes = ""
    for m in (historico or [])[-2:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            antes += ("Pergunta anterior: " if m["role"] == "user" else "Resposta anterior: ") + m["content"][:600] + "\n"
    usuario = (antes + "\n" if antes else "") + "Pergunta: " + pergunta
    mensagens = [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]
    if mascara is not None:
        mensagens = [dict(x, content=mascara.aplicar(x["content"])) for x in mensagens]
    partes: list[str] = []
    try:
        uso = nuvem.chamar(provedor, modelo, nuvem.chave(estado, provedor), mensagens, partes.append,
                           json_mode=provedor != "anthropic", max_tokens=400)
    except Exception as exc:  # noqa: BLE001 - sem triagem, o caminho de sempre
        _log.info("triagem não foi: %s", exc)
        return None
    bruto = "".join(partes)
    if mascara is not None:
        bruto = mascara.desfazer(bruto)
    try:
        nuvem.registrar_envio(estado, mensagens, {
            "envio": uuid.uuid4().hex[:12], "tarefa": "conversa", "titulo": "Triagem da pergunta", "trabalho_id": trabalho_id,
            "pessoa": quem, "pergunta": " ".join(str(pergunta or "").split())[:140],
            "provedor": provedor, "modelo": modelo, "caracteres": sum(len(x["content"]) for x in mensagens),
            "documentos": [], "mascarados": dict(mascara.contagem) if mascara else {},
            "como": "com o sim do titular de " + nuvem._data_do_sim(estado), **uso})
    except Exception:  # noqa: BLE001 - o registro não derruba a pergunta
        pass
    dados = _ler_json(bruto)
    if dados is None:
        return None
    saida = conferir(dados, nomes, leis)
    saida["tokens"] = int(uso.get("tokens_entrada", 0)) + int(uso.get("tokens_saida", 0))
    return saida
