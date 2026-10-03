"""
O lancamento pela conversa (pacote de telas de 01/10/2026: `Conversa -
Lancamento` e `Conversa - Recebimento`).

  "lança a perícia contábil do José Carlos, 2.150 com vencimento dia 8. o
   boleto tá anexo"           -> despesa, com o boleto conferido
  "a Rio Fresco pagou a parcela de setembro, 6.036 com os juros. o
   comprovante tá anexo"      -> o recebimento que estava em aberto, pago hoje

Por regra: o valor, o dia, quem (as fichas de Cadastros), a categoria e a
forma pelas palavras, e o anexo lido (valor, vencimento, beneficiario).
O recebimento acha a cobranca em aberto do mesmo cliente (o mes dito, ou o
valor mais perto) e diz quanto e juros. Nada e gravado aqui: o lancamento
abre na coluna e so entra no Financeiro no clique em Lancar.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

RE_RECEBEU = re.compile(r"\b(pagou|pagaram|depositou|depositaram|transferiu|transferiram|quitou|quitaram|recebi|recebemos|recebeu)\b")
RE_LANCA = re.compile(r"^(?:(?:por favor|pode|me)\s+)*(lanca|lance|lancar|registra|registre|registrar|anota|anote|paga|pague|pagar)\b")
RE_VALOR = re.compile(r"(?:r\$\s*)?\b(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+,\d{2}|\d{3,6})\b(?![.\-/]\d)(?!\s*(?:dias|%|h\b|:))")
# Dinheiro de verdade na frase: R$, centavos, milhar com ponto, "reais"/"mil",
# ou um numero perto de palavra de dinheiro. CPF, telefone, ano e hora nao.
RE_DINHEIRO = re.compile(r"(r\$\s*\d|\b\d+,\d{2}\b|\b\d{1,3}(?:\.\d{3})+(?:,\d{2})?\b(?![.\-/]\d)|\b\d+\s*(?:reais|mil)\b)")
RE_PALAVRA_DINHEIRO = re.compile(r"\b(boleto|conta|despesa|recebimento|valor|pagamento|honorarios?|custas|pericia|parcela|aluguel|taxa|mensalidade)\b")
RE_NAO_E_DINHEIRO = re.compile(r"\b(reuniao|compromisso|audiencia|lembrete|tarefa|prazo|calendario|agenda|cpf|cnpj|telefone|cliente novo|novo cliente)\b")
CATEGORIAS = [
    ("pericias", r"\bperici"), ("diligencias", r"\bdiligenc"), ("custas", r"\b(custas|certidao|certidoes|cartorio|emolumento|preparo|guia)\b"),
    ("aluguel", r"\baluguel\b"), ("imposto", r"\b(imposto|das|iss|irpj|darf|inss)\b"), ("sistemas", r"\b(sistema|assinatura|software|licenca)\b"),
    ("folha", r"\b(salario|folha|estagio|bolsa)\b"), ("reembolso", r"\breembols"), ("honorarios", r"\b(honorario|parcela|acordo|exito|consulta)\b"),
]
FORMAS = [("boleto", r"\bboleto\b"), ("pix", r"\bpix\b"), ("transferencia", r"\b(transferencia|transferiu|ted|doc)\b"), ("cartao", r"\bcartao\b"),
          ("dinheiro", r"\b(dinheiro|especie)\b"), ("debito", r"\bdebito\b")]


def valor_centavos(trecho: str) -> int:
    for m in RE_VALOR.finditer(trecho or ""):
        bruto = m.group(1)
        antes = trecho[max(0, m.start() - 5):m.start()]
        if re.search(r"dia\s*$", antes):
            continue
        inteiro, _, cents = bruto.replace(".", "").partition(",")
        numero = int(inteiro or 0) * 100 + int((cents + "00")[:2])
        if numero >= 100:
            return numero
    return 0


def em_reais(centavos: int) -> str:
    return "R$ " + f"{centavos // 100:,}".replace(",", ".") + "," + f"{centavos % 100:02d}"


def dia_dito(plano: str, hoje: date) -> str:
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", plano)
    if m:
        ano = int(m.group(3)) if m.group(3) else hoje.year
        ano += 2000 if ano < 100 else 0
        try:
            return date(ano, int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return ""
    m = re.search(r"\b(?:vencimento|vence|vencendo|para o|pro)\s+(?:no\s+)?(?:dia\s+)?(\d{1,2})\b", plano) or re.search(r"\bdia\s+(\d{1,2})\b", plano)
    if m and 1 <= int(m.group(1)) <= 31:
        d = int(m.group(1))
        ano, mes = hoje.year, hoje.month
        if d < hoje.day:
            mes += 1
            if mes > 12:
                ano, mes = ano + 1, 1
        try:
            return date(ano, mes, d).isoformat()
        except ValueError:
            return ""
    return ""


def _quem(plano: str, fichas: list[dict]) -> dict | None:
    """A ficha que a frase cita: o nome inteiro, ou as duas primeiras palavras dele."""
    melhor, tamanho = None, 0
    for f in fichas or []:
        nome = re.sub(r"[^a-z0-9 ]", " ", _plano(f.get("nome", "")))
        palavras = [p for p in nome.split() if p not in {"da", "de", "do", "das", "dos", "e", "ltda", "s", "a"}]
        # O nome inteiro, ou qualquer pedaco seguido dele: "Rio Fresco" acha
        # "Cooperativa Rio Fresco"; palavra sozinha so se for comprida.
        achou = False
        for k in range(len(palavras), 0, -1):
            for i in range(0, len(palavras) - k + 1):
                pedaco = " ".join(palavras[i:i + k])
                if (k >= 2 or len(pedaco) >= 6) and re.search(r"\b" + re.escape(pedaco) + r"\b", plano):
                    if len(pedaco) > tamanho:
                        melhor, tamanho = f, len(pedaco)
                    achou = True
                    break
            if achou:
                break
    return melhor


def ler_lancamento(texto: str, fichas: list[dict] | None = None, hoje: date | None = None) -> dict | None:
    """O lancamento que a frase pede, ou None. Pergunta ("quanto pagou?") nao e pedido."""
    hoje = hoje or date.today()
    plano = _plano(" ".join((texto or "").split()))
    if not plano or plano.rstrip().endswith("?") or re.search(r"\b(despesas? fixas?|todo mes)\b", plano):
        return None
    recebimento = bool(RE_RECEBEU.search(plano)) and not RE_LANCA.search(plano)
    if not recebimento and not RE_LANCA.search(plano):
        return None
    if RE_NAO_E_DINHEIRO.search(plano):
        return None
    if not (RE_DINHEIRO.search(plano) or (RE_PALAVRA_DINHEIRO.search(plano) and RE_VALOR.search(plano))):
        return None
    centavos = valor_centavos(plano)
    if not centavos:
        return None
    if re.search(r"\b(recebimento|receita|entrada)\b", plano):
        recebimento = True
    ficha = _quem(plano, fichas)
    categoria = next((c for c, r in CATEGORIAS if re.search(r, plano)), "honorarios" if recebimento else "outros")
    forma = next((f for f, r in FORMAS if re.search(r, plano)), "")
    descricao = ""
    m = re.search(r"\b(?:lanca|lance|lancar|registra|registre|anota|anote|inclui|inclua|paga|pague|pagar|pagou|pagaram|quitou|depositou|transferiu)\s+"
                  r"(?:a|o|as|os)?\s*(.+?)(?:,|\s+(?:do|da|de|dos|das)\s+" + (re.escape(re.sub(r"[^a-z0-9 ]", " ", _plano(ficha["nome"])).split()[0]) if ficha else "@@") +
                  r"|\s+(?:de\s+)?(?:r\$\s*)?\d|\s+com\b|\.|$)", plano)
    if m:
        bruto = texto[m.start(1):m.end(1)] if len(texto) == len(plano) else m.group(1)
        descricao = bruto.strip(" .,")
        descricao = descricao[:1].upper() + descricao[1:]
    vencimento = dia_dito(plano, hoje)
    mes_dito = next((i + 1 for i, nome in enumerate(MESES) if re.search(r"\b" + nome + r"\b", plano)), 0)
    pago = recebimento or bool(re.search(r"\b(paguei|pago hoje|ja pago|ja paguei|quitei)\b", plano))
    anexo = "comprovante" if re.search(r"\bcomprovante\b", plano) else ("boleto" if re.search(r"\bboleto\b", plano) else "")
    return {
        "tipo": "recebimento" if recebimento else "despesa", "centavos": centavos, "descricao": descricao, "categoria": categoria,
        "forma": forma or ("boleto" if anexo == "boleto" and not recebimento else ""), "cadastro_id": ficha["id"] if ficha else None,
        "cadastro_nome": ficha["nome"] if ficha else "", "vencimento": vencimento, "pago": pago, "mes_dito": mes_dito, "anexo": anexo,
        "lembrar": not recebimento and bool(vencimento),
    }


def casar_aberto(pedido: dict, abertos: list[dict]) -> dict | None:
    """
    O recebimento em aberto que a frase paga: do mesmo cliente, do mes dito
    (pelo vencimento) ou, sem mes, o de valor mais perto. So casa quando o
    valor dito e o da cobranca, ou ela mais os juros (ate 20%).
    """
    candidatos = [a for a in abertos or [] if a.get("tipo") == "recebimento" and not a.get("liquidado_em")
                  and pedido.get("cadastro_id") and a.get("cadastro_id") == pedido["cadastro_id"]]
    if pedido.get("mes_dito"):
        do_mes = [a for a in candidatos if str(a.get("vencimento", ""))[5:7] == f"{pedido['mes_dito']:02d}"]
        candidatos = do_mes or candidatos
    valor = pedido.get("centavos") or 0
    possiveis = [a for a in candidatos if a["centavos"] <= valor <= a["centavos"] * 1.2]
    if not possiveis:
        return None
    return min(possiveis, key=lambda a: abs(valor - a["centavos"]))


def ler_papel(texto: str) -> dict:
    """O boleto ou o comprovante anexo, por regra: valor, vencimento, beneficiario/pagador."""
    t = " ".join((texto or "").split())
    p = _plano(t)
    achado: dict = {}
    m = re.search(r"(?:valor(?: do documento| cobrado| pago| total)?|total)\s*:?\s*r?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})", p)
    if m:
        achado["centavos"] = valor_centavos(m.group(1))
    m = re.search(r"vencimento\s*:?\s*(\d{1,2})/(\d{1,2})/(\d{4})", p)
    if m:
        achado["vencimento"] = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.search(r"(?i)\b(?:benefici[aá]rio|cedente|favorecido|recebedor)\s*:?\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n:;,]{2,60}?)(?=\s+(?:CPF|CNPJ|Ag[eê]ncia|Vencimento|Valor|Pagador)|[,;\n]|$)", t)
    if m:
        achado["beneficiario"] = m.group(1).strip(" .-")
    m = re.search(r"(?i)\b(?:pagador|sacado|pago por|remetente|de)\s*:?\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n:;,]{2,60}?)(?=\s+(?:CPF|CNPJ|Ag[eê]ncia|Valor|Data)|[,;\n]|$)", t)
    if m:
        achado["pagador"] = m.group(1).strip(" .-")
    return achado
