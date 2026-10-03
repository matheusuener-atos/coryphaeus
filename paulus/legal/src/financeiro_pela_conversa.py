"""
O Financeiro e o Relatorio pela conversa (pacote de telas de 01/10/2026:
`Conversa - Financeiro` e `Conversa - Relatorio`).

  "como está o financeiro do mês?"      -> ler -> {"tipo": "financeiro"}
  "gera o relatório financeiro de outubro e compara com setembro"
                                        -> ler -> {"tipo": "relatorio"}

Os numeros sao somados aqui, dos lancamentos que existem (src/financeiro.py):
o modelo nunca calcula. A frase da conversa sai por regra; o "Parecer do
mes" e o unico texto do modelo, e ele recebe a conta feita.

A comparacao e "no mesmo periodo": outubro ate o dia 1 contra setembro ate
o dia 1. Comparar um mes que comecou ontem com um mes inteiro diria que tudo
caiu 95%.
"""
from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date

MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
MESES_TELA = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

RE_FINANCEIRO = re.compile(
    r"\b(como (?:esta|estao|anda|andam|vai|vao|ficou|ficaram)|resumo|panorama|situacao|balanco|me (?:mostra|mostre|diz|diga))\b"
    r".*\b(financeiro|caixa|contas|financas|dinheiro)\b")
RE_RELATORIO = re.compile(
    r"\b(gera|gere|gerar|faz|faca|fazer|monta|monte|montar|prepara|prepare|preparar|tira|tire|emite|emita|quero|me (?:manda|mande|da|de))\b"
    r".*\brelatorio\b.*\b(financeiro|do mes|mensal|de (?:" + "|".join(MESES) + r"))\b")


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def _mes_de(nome: str, hoje: date) -> str:
    i = MESES.index(nome) + 1
    ano = hoje.year if i <= hoje.month else hoje.year - 1
    return f"{ano}-{i:02d}"


def mes_antes(chave: str) -> str:
    ano, mes = int(chave[:4]), int(chave[5:7])
    return f"{ano - 1}-12" if mes == 1 else f"{ano}-{mes - 1:02d}"


def ler(texto: str, hoje: date | None = None) -> dict | None:
    hoje = hoje or date.today()
    plano = _plano(" ".join((texto or "").split()))
    if not plano:
        return None
    relatorio = bool(RE_RELATORIO.search(plano))
    if not relatorio and not RE_FINANCEIRO.search(plano):
        return None
    meses = [m.group(1) for m in re.finditer(r"\b(" + "|".join(MESES) + r")\b", plano)]
    mes = hoje.strftime("%Y-%m")
    if re.search(r"\bmes passado\b", plano):
        mes = mes_antes(mes)
    elif meses:
        mes = _mes_de(meses[0], hoje)
    comparar = mes_antes(mes)
    m = re.search(r"\bcompar\w*\s+(?:com|a|ao|contra)\s+(?:o\s+)?(?:mes de\s+)?(" + "|".join(MESES) + r")\b", plano)
    if m:
        comparar = _mes_de(m.group(1), hoje)
    return {"tipo": "relatorio" if relatorio else "financeiro", "mes": mes, "comparar": comparar}


def rotulo_do_mes(chave: str) -> str:
    return MESES_TELA[int(chave[5:7]) - 1]


def _curto(centavos: int) -> str:
    return "R$ " + f"{round(abs(centavos) / 100):,}".replace(",", ".")


def _reais(centavos: int) -> str:
    v = abs(int(centavos))
    return "R$ " + f"{v // 100:,}".replace(",", ".") + "," + f"{v % 100:02d}"


def _soma(base, tipo: str, de: str, ate: str) -> int:
    linha = base.um("SELECT COALESCE(SUM(centavos),0) AS s FROM lancamentos WHERE tipo = ? AND liquidado_em != '' "
                    "AND liquidado_em >= ? AND liquidado_em <= ?", (tipo, de, ate))
    return int(linha["s"]) if linha else 0


def _ate_o_dia(chave: str, dia: int) -> str:
    ano, mes = int(chave[:4]), int(chave[5:7])
    return f"{chave}-{min(dia, calendar.monthrange(ano, mes)[1]):02d}"


def _por_categoria(base, de: str, ate: str) -> dict:
    """O liquidado de cada categoria no periodo: {categoria: {"entradas", "saidas"}}."""
    saida: dict = {}
    for l in base.buscar("SELECT categoria, tipo, SUM(centavos) AS total FROM lancamentos WHERE liquidado_em != '' "
                         "AND liquidado_em >= ? AND liquidado_em <= ? GROUP BY categoria, tipo", (de, ate)):
        c = saida.setdefault(l["categoria"] or "outros", {"entradas": 0, "saidas": 0})
        c["entradas" if l["tipo"] == "recebimento" else "saidas"] += int(l["total"] or 0)
    return saida


def prazo_medio(base, de: str, ate: str) -> dict:
    """
    Quantos dias, em media, entre o vencimento e o recebimento, no periodo
    (a mesma conta de src/relatorios.py, aqui por periodo: a comparacao e
    "no mesmo periodo"). Com menos de tres recebimentos, nao ha media.
    """
    dias = []
    for l in base.buscar("SELECT vencimento, liquidado_em FROM lancamentos WHERE tipo = 'recebimento' AND liquidado_em != '' "
                         "AND vencimento != '' AND liquidado_em >= ? AND liquidado_em <= ?", (de, ate)):
        try:
            dias.append((date.fromisoformat(l["liquidado_em"][:10]) - date.fromisoformat(l["vencimento"][:10])).days)
        except ValueError:
            continue
    if len(dias) < 3:
        return {"tem": False, "quantos": len(dias)}
    return {"tem": True, "quantos": len(dias), "dias": round(sum(dias) / len(dias), 1)}


def relatorio(financeiro, base, mes: str, comparar: str = "", hoje: date | None = None) -> dict:
    """
    O mes: extrato (entradas, saidas, resultado), o que esta aberto, as
    categorias liquidadas e a comparacao no mesmo periodo do mes `comparar`.
    """
    hoje = hoje or date.today()
    corrente = mes == hoje.strftime("%Y-%m")
    ultimo = calendar.monthrange(int(mes[:4]), int(mes[5:7]))[1]
    dia = hoje.day if corrente else ultimo
    ate = _ate_o_dia(mes, dia)
    entradas = _soma(base, "recebimento", mes + "-01", ate)
    saidas = _soma(base, "despesa", mes + "-01", ate)
    painel = financeiro.painel(mes)
    from financeiro import CATEGORIAS

    # No mesmo periodo do extrato (ate hoje, no mes corrente).
    categorias = {k: {"categoria": k, "rotulo": CATEGORIAS.get(k, "Outros"), **v}
                  for k, v in _por_categoria(base, mes + "-01", ate).items()}
    lancamentos = base.um("SELECT COUNT(*) AS n FROM lancamentos WHERE liquidado_em != '' AND liquidado_em >= ? AND liquidado_em <= ?",
                          (mes + "-01", ate))
    comparacao = None
    if comparar:
        ate_antes = _ate_o_dia(comparar, dia)
        e0 = _soma(base, "recebimento", comparar + "-01", ate_antes)
        s0 = _soma(base, "despesa", comparar + "-01", ate_antes)
        r0 = e0 - s0
        comparacao = {
            "mes": comparar, "rotulo": rotulo_do_mes(comparar), "ate_o_dia": dia, "inteiro": not corrente,
            "entradas": e0, "saidas": s0, "resultado": r0,
            "entradas_pct": _pct(e0, entradas), "saidas_pct": _pct(s0, saidas), "resultado_pct": _pct(r0, entradas - saidas),
            "prazo_medio": prazo_medio(base, comparar + "-01", ate_antes),
        }
        # Cada categoria contra a mesma categoria no mesmo periodo do outro mes.
        antes = _por_categoria(base, comparar + "-01", ate_antes)
        for chave, c in categorias.items():
            a = antes.get(chave) or {"entradas": 0, "saidas": 0}
            c["antes_entradas"], c["antes_saidas"] = a["entradas"], a["saidas"]
            principal = "entradas" if c["entradas"] >= c["saidas"] else "saidas"
            c["pct"] = _pct(a[principal], c[principal])
    return {
        "mes": mes, "rotulo": rotulo_do_mes(mes), "ano": mes[:4], "ate": ate, "corrente": corrente,
        "entradas": entradas, "saidas": saidas, "resultado": entradas - saidas,
        "a_receber": painel.get("a_receber", 0), "a_pagar": painel.get("a_pagar", 0), "atrasado": painel.get("atrasado", 0),
        "categorias": sorted(categorias.values(), key=lambda c: -(c["entradas"] + c["saidas"])),
        "lancamentos": int(lancamentos["n"]) if lancamentos else 0,
        "prazo_medio": prazo_medio(base, mes + "-01", ate),
        "comparacao": comparacao,
    }


def _dias(d: float) -> str:
    """ 14.0 -> "14 dias"; -2.5 -> "2,5 dias antes" (pago antes do vencimento)."""
    n = abs(d)
    texto = (str(int(n)) if n == int(n) else str(n).replace(".", ",")) + (" dia" if n == 1 else " dias")
    return texto + (" antes" if d < 0 else "")


def _pct(antes: int, agora: int) -> int | None:
    if not antes:
        return None
    return round((agora - antes) * 100 / abs(antes))


def frase_do_financeiro(financeiro, mes: str, precisa: list[dict], hoje: date | None = None) -> str:
    """ "Outubro começou com R$ 24.456 em caixa. Entraram ... Há ... a receber e ... a pagar; uma conta precisa de você hoje." """
    hoje = hoje or date.today()
    extrato = financeiro.extrato(mes)
    painel = financeiro.painel(mes)
    inicio = int(extrato.get("saldo_anterior") or 0)
    corrente = mes == hoje.strftime("%Y-%m")
    nome = rotulo_do_mes(mes).capitalize()
    frase = (f"{nome} começou com {_curto(inicio)} em caixa. " if corrente else f"{nome} abriu com {_curto(inicio)} em caixa. ")
    frase += (f"Entraram {_curto(painel.get('entradas_mes', 0))} e saíram {_curto(painel.get('saidas_mes', 0))}"
              + (" até agora. " if corrente else ". "))
    frase += f"Há {_curto(painel.get('a_receber', 0))} a receber e {_curto(painel.get('a_pagar', 0))} a pagar"
    hoje_txt = [p for p in precisa if p.get("detalhe") == "vence hoje" or p.get("grau") == "urgente"]
    if hoje_txt:
        n = len(hoje_txt)
        frase += "; " + ("uma conta precisa" if n == 1 else f"{n} contas precisam") + " de você hoje."
    else:
        frase += "; nada precisa de você hoje."
    return frase


def frase_do_relatorio(r: dict) -> str:
    resultado = r["resultado"]
    frase = (f"Somei os lançamentos de {r['rotulo']}" + (" até hoje" if r["corrente"] else "") + ". "
             f"O resultado está {'positivo' if resultado >= 0 else 'negativo'} em {_curto(resultado)}")
    c = r.get("comparacao")
    if c and c.get("resultado_pct") is not None and c["resultado"] > 0:
        pct = c["resultado_pct"]
        frase += (f", {abs(pct)}% {'acima' if pct >= 0 else 'abaixo'} de {c['rotulo']}" +
                  (" no mesmo período" if not c["inteiro"] else ""))
    elif c:
        frase += f" (em {c['rotulo']}, {'no mesmo período, ' if not c['inteiro'] else ''}o resultado foi {_curto(c['resultado'])})"
    return frase + ". O PDF e a planilha estão prontos para baixar."


def numeros_para_o_parecer(r: dict, precisa: list[dict]) -> str:
    linhas = [f"Mês: {r['rotulo']} de {r['ano']}" + (" (até hoje)" if r["corrente"] else ""),
              f"Entradas: {_reais(r['entradas'])}. Saídas: {_reais(r['saidas'])}. Resultado: {_reais(r['resultado'])}.",
              f"A receber em aberto: {_reais(r['a_receber'])}. A pagar em aberto: {_reais(r['a_pagar'])}. Em atraso: {_reais(r['atrasado'])}."]
    for c in r["categorias"][:6]:
        partes = []
        if c["entradas"]:
            partes.append(f"entrou {_reais(c['entradas'])}")
        if c["saidas"]:
            partes.append(f"saiu {_reais(c['saidas'])}")
        linhas.append(f"{c['rotulo']}: " + ", ".join(partes) + ".")
    c = r.get("comparacao")
    if c:
        linhas.append(f"Em {c['rotulo']}" + (f" até o dia {c['ate_o_dia']}" if not c["inteiro"] else "") +
                      f": entradas {_reais(c['entradas'])}, saídas {_reais(c['saidas'])}, resultado {_reais(c['resultado'])}.")
    pm = r.get("prazo_medio") or {}
    if pm.get("tem"):
        linhas.append(f"Prazo médio de recebimento: {_dias(pm['dias'])} depois do vencimento, em {pm['quantos']} recebimentos." +
                      (f" Em {c['rotulo']}, no mesmo período: {_dias(c['prazo_medio']['dias'])}." if c and (c.get("prazo_medio") or {}).get("tem") else ""))
    for p in precisa[:5]:
        linhas.append(f"Pendente: {p.get('titulo', '')} ({p.get('detalhe', '')}).")
    return "\n".join(linhas)


INSTRUCAO_PARECER_DO_MES = """Voce e assistente de um advogado brasileiro. Escreva um
parecer curto sobre o financeiro do mes do escritorio, em portugues do Brasil.

Regras, e elas valem mais que o estilo:
- use SOMENTE os numeros que estao abaixo; nao calcule nada por conta propria
- nao invente numero, nome, data nem valor que nao esteja na lista
- tres ou quatro frases: como o mes vai, o ponto de atencao, o que fazer
- sem marcacao, sem asteriscos, sem titulo, sem saudacao"""


def html_do_relatorio(r: dict, escapar) -> str:
    """O relatorio do mes em HTML, para o gerador de PDF dos documentos."""
    c = r.get("comparacao")
    linhas = [f"<h1>Relatório financeiro · {r['rotulo']} {r['ano']}</h1>",
              f"<p>{r['lancamentos']} lançamento(s) liquidado(s)" + (f" até {r['ate'][8:10]}/{r['ate'][5:7]}" if r["corrente"] else "") + ".</p>",
              "<h2>Extrato do mês</h2>",
              f"<p>Entradas: + {_reais(r['entradas'])}<br>Saídas: – {_reais(r['saidas'])}<br><b>Resultado: {_reais(r['resultado'])}</b></p>",
              f"<p>A receber em aberto: {_reais(r['a_receber'])}<br>A pagar em aberto: {_reais(r['a_pagar'])}<br>Em atraso: {_reais(r['atrasado'])}</p>"]
    if r["categorias"]:
        linhas.append("<h2>Por categoria</h2><ul>")
        for x in r["categorias"]:
            valor = (f"+ {_reais(x['entradas'])}" if x["entradas"] else "") + (" · " if x["entradas"] and x["saidas"] else "") + \
                    (f"– {_reais(x['saidas'])}" if x["saidas"] else "")
            if c and "pct" in x:
                valor += f" ({'sem base' if x['pct'] is None else ('+' if x['pct'] >= 0 else '') + str(x['pct']) + '%'} contra {escapar(c['rotulo'])})"
            linhas.append(f"<li>{escapar(x['rotulo'])}: {valor}</li>")
        linhas.append("</ul>")
    if c:
        def var(p):
            return "sem base" if p is None else f"{'+' if p >= 0 else ''}{p}%"
        linhas.append(f"<h2>Contra {escapar(c['rotulo'])}</h2><p>" + ("No mesmo período (até o dia " + str(c["ate_o_dia"]) + "): " if not c["inteiro"] else "") +
                      f"entradas {var(c['entradas_pct'])}, saídas {var(c['saidas_pct'])}.</p>")
    pm = r.get("prazo_medio") or {}
    linhas.append("<h2>Prazo médio de recebimento</h2><p>" + (
        f"{_dias(pm['dias'])} depois do vencimento, em {pm['quantos']} recebimentos" +
        (f"; em {escapar(c['rotulo'])}, no mesmo período, {_dias(c['prazo_medio']['dias'])}" if c and (c.get("prazo_medio") or {}).get("tem") else "") + "."
        if pm.get("tem") else f"Sem média: {pm.get('quantos', 0)} recebimento(s) com vencimento no período, e a média pede pelo menos três.") + "</p>")
    linhas.append("<p><i>Os números foram somados nesta máquina, dos lançamentos do Financeiro.</i></p>")
    return "".join(linhas)
