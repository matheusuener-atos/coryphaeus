"""
O e-mail pela conversa (pacote de telas de 01/10/2026: `Conversa - E-mail`
e `Conversa - Escrever e-mail`).

  "abra o último e-mail do Mercado Pago"   ler_pedido -> {"acao": "abrir", ...}
  "responda a Priscila confirmando o acordo da parcela de setembro"
                                           ler_pedido -> {"acao": "responder", ...}

O que a conversa diz sobre a mensagem ("É um código de verificação de 26 de
setembro — não achei prazo, e o remetente não recebe resposta") sai por
regra, do que a mensagem tem: o codigo (a mesma regra da caixa,
js/29-email-caixa.js, exCodigo), o prazo (correio.detectar_prazo) e o
remetente de nao-responder. Nada disso passa pelo modelo.

O rascunho da resposta passa: o modelo escreve com o pedido do advogado, e o
texto do remetente vai cercado (src/blindagem.py), como no rascunho da
caixa. Depois, as conferencias por regra: os valores do texto estao no
e-mail recebido ou no Acervo? "até sexta" e que dia? e o envio passa por
Aprovacoes? A tela mostra o que conferiu; nada sai sem o clique em Enviar.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

# --------------------------------------------------------------- o pedido

_VERBO_ABRIR = r"(?:abra|abre|abrir|mostre|mostra|mostrar|leia|le|lê|ler|veja|ve|vê|traga|traz|exiba|exibe)"
_ENFEITE = r"(?:(?:por favor|pode|voce pode|você pode|consegue|me|pra mim|para mim)\s*,?\s+)*"
_UM_EMAIL = r"(?:(?:o|a)\s+)?(?:(?:[uú]ltim[oa]|mais recente)\s+)?(?:e-?mail|mensagem)(?:\s+mais recente)?"
RE_ABRIR = re.compile(
    r"^" + _ENFEITE + _VERBO_ABRIR + r"\s+(?:(?:pra mim|para mim|aqui)\s+)?" + _UM_EMAIL +
    r"\s+(?:que\s+(?:o|a)\s+|d[oae]s?\s+|de\s+)(?P<quem>.+?)"
    r"(?:\s+(?:me\s+)?(?:mandou|enviou|mandaram|enviaram))?(?:\s+(?:aqui|pra mim|para mim|no chat|na conversa))?\s*[.!?]*$",
    re.I)
_VERBO_RESPONDER = r"(?:responda|responde|responder|respondam)"
_COMO = (r"(?:confirmando|dizendo|agradecendo|informando|pedindo|perguntando|avisando|recusando|aceitando|"
         r"explicando|lembrando|propondo|sugerindo|cobrando|enviando|mandando|que|com|sobre|e diga|e diz|e confirme|e pe[cç]a)")
RE_RESPONDER = re.compile(
    r"^" + _ENFEITE + _VERBO_RESPONDER + r"\s+(?:(?:a|à|ao|o|os|as)\s+)?(?:" + _UM_EMAIL + r"\s+(?:d[oae]s?|de)\s+)?"
    r"(?P<quem>.+?)(?:\s*,\s*|\s+)(?P<pedido>" + _COMO + r"\b.*)$",
    re.I)
RE_RESPONDER_SO = re.compile(
    r"^" + _ENFEITE + _VERBO_RESPONDER + r"\s+(?:(?:a|à|ao|o|os|as)\s+)?(?:" + _UM_EMAIL + r"\s+(?:d[oae]s?|de)\s+)?"
    r"(?P<quem>[^,.!?]+?)\s*[.!?]*$",
    re.I)
# O que nao e nome de remetente: "responda isso", "abra o e-mail aqui".
_NAO_E_QUEM = {"isso", "isto", "esse", "este", "essa", "esta", "aqui", "ele", "ela", "todos", "tudo", "agora", "depois"}
# ...nem comeco de frase que nao seja nome: "responda em portugues",
# "responda que sim", "responda com calma".
_NAO_COMECA = {"que", "se", "em", "com", "por", "sem", "como", "sobre", "sim", "nao", "so", "apenas", "rapido",
               "curto", "direito", "melhor", "assim", "isso", "a", "o", "minha", "meu", "essa", "esta", "pergunta"}


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def _quem_valido(quem: str) -> bool:
    plano = _plano(quem)
    return bool(plano) and plano not in _NAO_E_QUEM and plano.split()[0] not in _NAO_COMECA and len(plano.split()) <= 6


def _limpar_quem(quem: str) -> str:
    quem = " ".join((quem or "").split()).strip(" ,.;:!?\"'“”")
    # "a Priscila" / "o Mercado Pago": o artigo fica de fora.
    quem = re.sub(r"^(?:o|a|os|as|do|da|de|dos|das)\s+", "", quem, flags=re.I)
    return quem


def ler_pedido(texto: str) -> dict | None:
    """
    O pedido de e-mail na frase, ou None. Devolve {"acao", "quem", "sobre",
    "pedido"}: quem e de onde veio a mensagem (nome ou endereco), sobre e o
    assunto quando a frase diz ("o e-mail da Priscila sobre a parcela").
    """
    frase = " ".join((texto or "").split())
    if not frase or len(frase) > 400:
        return None
    baixo = frase.lower()
    m = RE_RESPONDER.match(baixo)
    if m:
        quem = _limpar_quem(frase[m.start("quem"):m.end("quem")])
        pedido = frase[m.start("pedido"):].strip().rstrip(".")
        if _quem_valido(quem):
            return {"acao": "responder", "quem": quem, "sobre": "", "pedido": pedido}
    m = RE_RESPONDER_SO.match(baixo)
    if m:
        quem = _limpar_quem(frase[m.start("quem"):m.end("quem")])
        if _quem_valido(quem):
            return {"acao": "responder", "quem": quem, "sobre": "", "pedido": ""}
    m = RE_ABRIR.match(baixo)
    if m:
        quem = _limpar_quem(frase[m.start("quem"):m.end("quem")])
        sobre = ""
        partes = re.split(r"\s+sobre\s+", quem, maxsplit=1, flags=re.I)
        if len(partes) == 2:
            quem, sobre = _limpar_quem(partes[0]), partes[1].strip()
        if _quem_valido(quem):
            return {"acao": "abrir", "quem": quem, "sobre": sobre, "pedido": ""}
    return None


# ------------------------------------------------- o que a mensagem tem

# A mesma regra da caixa (js/29-email-caixa.js, exCodigo): um numero de 4 a
# 8 digitos, ou letras e numeros, perto de "codigo", "code", "verificacao".
RE_GATILHO_CODIGO = re.compile(
    r"(c[oó]digo|code|verifica|autentica|authenticat|confirma|one[- ]time|otp\b|\bpin\b|token|senha tempor|passcode|security)", re.I)
RE_CANDIDATO = re.compile(r"(?<![\w@./:#-])(\d{3}[ -]\d{3}|\d{4,8}|[A-Z0-9]{6,8})(?![\w@/:-]|\.\d)")


def codigo_de_verificacao(assunto: str, corpo: str) -> str:
    texto = ((assunto or "") + "\n" + (corpo or ""))[:8000]
    if not RE_GATILHO_CODIGO.search(texto):
        return ""
    for achado in RE_CANDIDATO.finditer(texto):
        bruto = achado.group(1)
        limpo = re.sub(r"[ -]", "", bruto)
        if re.fullmatch(r"[A-Z0-9]+", limpo) and not (re.search(r"\d", limpo) and (limpo.isdigit() or re.search(r"[A-Z]", limpo))):
            continue
        if re.fullmatch(r"(19|20)\d\d", limpo):
            continue
        antes = texto[max(0, achado.start() - 160):achado.start()]
        depois = texto[achado.end():achado.end() + 60]
        if RE_GATILHO_CODIGO.search(antes) or RE_GATILHO_CODIGO.search(depois):
            return limpo
    return ""


RE_NAO_RESPONDA = re.compile(r"(no-?reply|nao-?respond|naorespond|do-?not-?reply|donotreply|mailer-daemon|notifica[cç]|bounce)", re.I)

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]


def _data_extenso(iso: str) -> str:
    try:
        d = datetime.fromisoformat(str(iso)[:19]).date()
    except ValueError:
        return ""
    return f"{d.day} de {MESES[d.month - 1]}"


def _dd_mm(iso: str) -> str:
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return ""
    return f"{d.day:02d}/{d.month:02d}"


def sem_resposta(de_email: str) -> bool:
    """O remetente e um endereco que nao recebe resposta (nao-responder@...)."""
    return bool(RE_NAO_RESPONDA.search((de_email or "").split("@")[0]))


def frase_da_mensagem(m: dict, codigo: str) -> str:
    """O que a conversa diz ao abrir: o que e, de quando, o prazo e se pede resposta."""
    quando = _data_extenso(m.get("quando", ""))
    de = m.get("de_nome") or m.get("de_email") or "o remetente"
    if codigo:
        o_que = "É um código de verificação" + (f" de {quando}" if quando else "")
    else:
        o_que = f"É de {de}" + (f", de {quando}" if quando else "") + (f": “{m.get('assunto')}”" if m.get("assunto") else "")
    partes = []
    if m.get("prazo"):
        partes.append(f"achei um prazo, {_dd_mm(m['prazo'])}" + (f" (“{m.get('prazo_trecho')}”)" if m.get("prazo_trecho") else ""))
    else:
        partes.append("não achei prazo")
    if sem_resposta(m.get("de_email", "")):
        partes.append("o remetente não recebe resposta")
    anexos = m.get("anexos") or []
    frase = "Abri aqui. " + o_que + " — " + ", e ".join(partes) + "."
    if anexos:
        frase += f" Tem {len(anexos)} anexo{'s' if len(anexos) != 1 else ''}."
    return frase


# ------------------------------------------------------ o rascunho

INSTRUCAO_COM_PEDIDO = """Voce e assistente de um advogado brasileiro. Escreva
APENAS o corpo da resposta ao e-mail abaixo, em portugues do Brasil, fazendo o
que o advogado pediu.

Regras:
- comece com a saudacao pelo primeiro nome de quem escreveu ("Olá, Fulana,")
- tom profissional e cordial; de 3 a 10 linhas
- faca o que o advogado pediu; nao invente fato, data, valor, prazo nem promessa
  que nao estejam no e-mail ou no pedido. Se faltar, deixe a lacuna entre
  colchetes, por exemplo [VALOR]
- nao escreva assunto nem assinatura com nome: o programa acrescenta a da conta
- termine com "Atenciosamente,"
- nao use marcacao nem asteriscos"""


def escrever_resposta(cliente, mensagem, pedido: str, quem_assina: str = "") -> tuple[str, str]:
    """
    O rascunho com o pedido do advogado. Sem pedido, e o rascunho da caixa
    (correio.sugerir_resposta_com_aviso). Devolve (texto, aviso).
    """
    import blindagem
    import correio

    if not (pedido or "").strip():
        texto, aviso = correio.sugerir_resposta_com_aviso(cliente, mensagem, quem_assina)
        return texto, aviso
    original = (f"De: {mensagem.de_nome} <{mensagem.de_email}>\n"
                f"Assunto: {mensagem.assunto}\n\n"
                f"{mensagem.corpo[:3000]}")
    # O pedido e do advogado (fora da cerca); o e-mail e do remetente (dentro).
    contexto = "E-mail recebido:\n" + blindagem.cercar(original)
    instrucao = (INSTRUCAO_COM_PEDIDO + "\n\nO que o advogado pediu para a resposta: " + " ".join(pedido.split())[:400]
                 + "\n\n" + blindagem.REGRA)
    if quem_assina:
        instrucao += f"\n- quem responde e {quem_assina}"
    resposta = cliente.ask(instrucao, contexto)
    texto, fora = blindagem.conferir_saida(_sem_assinatura(correio._limpar_rascunho(resposta)), original + "\n" + pedido,
                                           [mensagem.de_email])
    avisos = [blindagem.aviso(blindagem.suspeitas(original))]
    if fora:
        avisos.append("Tirei do rascunho " + ", ".join(fora[:3]) + ": não estava no e-mail recebido.")
    return texto, " ".join(a for a in avisos if a)


def _sem_assinatura(texto: str) -> str:
    """O nome que o modelo pos depois do "Atenciosamente," sai: a assinatura e a da conta."""
    linhas = (texto or "").rstrip().split("\n")
    for i, linha in enumerate(linhas):
        if re.match(r"^\s*(atenciosamente|cordialmente|abra[cç]os|att\.?|grato|grata)\s*,?\s*$", linha, re.I):
            return "\n".join(linhas[:i + 1]).strip()
    return "\n".join(linhas).strip()


# ---------------------------------------------------- as conferencias

RE_VALOR = re.compile(r"R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?|R\$\s?\d+(?:,\d{2})?")
DIAS = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
RE_RELATIVA = re.compile(
    r"\b(?:ate|na|no|nesta|neste|nessa|nesse|esta|este|proxima|proximo|para|pra)\s+"
    r"(segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?\b|\b(amanha|depois de amanha)\b")
RE_DDMM = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")


def _numero(valor: str) -> str:
    return re.sub(r"[^\d,]", "", valor).lstrip("0") or "0"


def _centavos(valor: str) -> int:
    n = _numero(valor)
    inteiro, _, cents = n.partition(",")
    return int(inteiro or 0) * 100 + int((cents + "00")[:2])


def _e_soma(valor: str, outros: list[str]) -> bool:
    """O total do texto ("O total fica em R$ 6.036,00") e a soma de dois ou tres dos outros valores."""
    from itertools import combinations

    alvo = _centavos(valor)
    numeros = [_centavos(o) for o in outros if _numero(o) != _numero(valor)]
    return any(sum(c) == alvo for k in (2, 3) for c in combinations(numeros, k))


def _valores(texto: str) -> list[str]:
    vistos, saida = set(), []
    for v in RE_VALOR.findall(texto or ""):
        n = _numero(v)
        if n not in vistos:
            vistos.add(n)
            saida.append(" ".join(v.split()))
    return saida


def conferir(corpo: str, original: str, documentos: list[tuple[str, str]], hoje: date,
             passa_por_aprovacao: bool, aviso: str = "") -> list[dict]:
    """
    O que se confere por regra no texto da resposta. Cada item: {ok, icone,
    texto}. `documentos`: (nome, texto) do Acervo, para achar o valor que
    nao esta no e-mail recebido.
    """
    itens: list[dict] = []
    valores = _valores(corpo)
    if valores:
        no_email = {_numero(v) for v in _valores(original)}
        faltam, fontes, somas = [], [], []
        for v in valores:
            n = _numero(v)
            if _e_soma(v, valores):
                somas.append(v)
                continue
            if n in no_email:
                fontes.append("o e-mail recebido")
                continue
            achou = next((nome for nome, texto in documentos if n in {_numero(x) for x in _valores(texto)}), "")
            if achou:
                fontes.append(achou)
            else:
                faltam.append(v)
        if faltam:
            itens.append({"ok": False, "icone": "error", "texto": ", ".join(faltam[:3]) + " não aparece no e-mail nem no Acervo — confira"})
        else:
            unicas = list(dict.fromkeys(fontes))
            if unicas:
                onde = unicas[0] if len(unicas) == 1 else ", ".join(unicas[:-1]) + " e " + unicas[-1]
                texto = ("o valor bate" if len(valores) - len(somas) == 1 else "os valores batem") + " com " + onde
                if somas:
                    texto += " (" + ", ".join(somas) + (" é a soma" if len(somas) == 1 else " são somas") + ")"
                itens.append({"ok": True, "icone": "check_circle", "texto": texto})
    plano = _plano(corpo)
    for m in RE_RELATIVA.finditer(plano):
        if m.group(1):
            alvo = DIAS[m.group(1)]
            dias = (alvo - hoje.weekday()) % 7 or 7
            dia = hoje + timedelta(days=dias)
        else:
            dia = hoje + timedelta(days=2 if "depois" in m.group(2) else 1)
        dita = corpo[m.start():m.end()].strip()
        certa = f"{dia.day:02d}/{dia.month:02d}"
        perto = RE_DDMM.search(plano, m.end(), m.end() + 30)
        if perto and f"{int(perto.group(1)):02d}/{int(perto.group(2)):02d}" != certa:
            itens.append({"ok": False, "icone": "error", "texto": f"“{dita}” seria {certa}, e o texto diz {perto.group(0)}"})
        else:
            itens.append({"ok": False, "icone": "schedule", "texto": f"“{dita}” — confirme se é {certa}"})
        break
    if aviso:
        itens.append({"ok": False, "icone": "error", "texto": aviso})
    if passa_por_aprovacao:
        itens.append({"ok": True, "icone": "check_circle", "texto": "passa por Aprovações antes de sair"})
    else:
        itens.append({"ok": True, "icone": "check_circle", "texto": "só sai quando você clicar em Enviar e confirmar"})
    return itens


def palavras(texto: str) -> int:
    return len(re.findall(r"\w+", texto or ""))
