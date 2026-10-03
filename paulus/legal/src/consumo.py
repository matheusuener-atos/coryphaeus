"""
Plano e consumo (03/10/2026): quanto o escritório gasta da IA da nuvem, quem
gasta, e os limites de uso.

A conta de tokens que vale para a cobrança é a do Worker (worker/ia.js): o
ciclo, os usados e os restantes. Quem gastou cada token sai daqui, do registro
de envios deste computador (`data/nuvem/envios.jsonl`, src/nuvem.py) - cada
linha leva, desde hoje, a pessoa (`pessoa`: conta da equipe, 0 = a janela do
escritório) e o começo da pergunta (`pergunta`). Linha de antes disso conta
para a janela do escritório (ou "de fora, antes do registro por pessoa"), com
o título da conversa no lugar da pergunta.

Os limites ficam em preferencias.json, bloco "limites_ia": diário e mensal do
escritório inteiro e, por pessoa, diário e mensal - 0 é sem limite. O mês é o
ciclo da assinatura, quando se sabe; senão, o mês do calendário. Passou do
limite, a pergunta não vai à nuvem: o modelo deste computador escreve, como
sem internet, e a resposta diz por quê (src/nuvem.py, Envio.preparar).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

ALERTA = 0.8           # a partir daqui, a tela avisa que está perto do limite
JANELA_MESMA_PERGUNTA_S = 180
FORA_ANTIGO = -1       # "de fora, antes do registro por pessoa"


def _arquivo(estado):
    import nuvem

    return nuvem._pasta(estado) / "envios.jsonl"


def ler(estado, desde: datetime | None = None) -> list[dict]:
    """As linhas do registro de envios, da mais antiga para a mais nova (desde `desde`)."""
    arq = _arquivo(estado)
    if not arq.exists():
        return []
    saida = []
    with arq.open(encoding="utf-8") as f:
        for linha in f:
            try:
                d = json.loads(linha)
            except ValueError:
                continue
            if desde is not None:
                try:
                    if datetime.fromisoformat(str(d.get("quando", ""))[:19]) < desde:
                        continue
                except ValueError:
                    continue
            saida.append(d)
    return saida


def tokens_de(linha: dict) -> int:
    return int(linha.get("tokens_entrada") or 0) + int(linha.get("tokens_saida") or 0)


def nome_da_janela(estado) -> str:
    nome = str(((estado.prefs.dados.get("pessoa") or {}).get("nome")) or "").strip()
    return nome or "Janela do escritório"


def pessoa_de(linha: dict) -> int:
    p = linha.get("pessoa")
    if isinstance(p, dict) and "conta_id" in p:
        try:
            return int(p["conta_id"])
        except (TypeError, ValueError):
            return 0
    return FORA_ANTIGO if linha.get("de_fora") else 0


def inicio_do_ciclo(estado, hoje: datetime | None = None) -> tuple[datetime, str]:
    """(o começo do mês que conta, o fim dele em ISO ou ""): o ciclo da assinatura, ou o mês do calendário."""
    import nuvem

    agora = hoje or datetime.now()
    conta = nuvem._CONTA_CACHE.get("dados") if hasattr(nuvem, "_CONTA_CACHE") else None
    ciclo = (conta or {}).get("ciclo") or {}
    try:
        inicio = datetime.fromisoformat(str(ciclo.get("inicio", "")).replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        if inicio <= agora:
            return inicio, str(ciclo.get("fim") or "")
    except ValueError:
        pass
    return agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0), ""


# ------------------------------------------------------------- limites

def limites(estado) -> dict:
    bruto = dict(estado.prefs.dados.get("limites_ia") or {})
    pessoas = {}
    for k, v in (bruto.get("pessoas") or {}).items():
        try:
            pessoas[str(int(k))] = {"diario": max(0, int((v or {}).get("diario") or 0)),
                                    "mensal": max(0, int((v or {}).get("mensal") or 0))}
        except (TypeError, ValueError):
            continue
    return {"diario": max(0, int(bruto.get("diario") or 0)), "mensal": max(0, int(bruto.get("mensal") or 0)),
            "pessoas": {k: v for k, v in pessoas.items() if v["diario"] or v["mensal"]}}


def guardar_limites(estado, novos: dict) -> dict:
    """Grava o bloco inteiro; números negativos ou inválidos viram 0 (sem limite)."""
    def n(v):
        try:
            return max(0, int(float(str(v).replace(".", "").replace(",", ".") or 0)))
        except (TypeError, ValueError):
            return 0

    pessoas = {}
    for k, v in (novos.get("pessoas") or {}).items():
        d, m = n((v or {}).get("diario")), n((v or {}).get("mensal"))
        if d or m:
            pessoas[str(int(k))] = {"diario": d, "mensal": m}
    # O bloco inteiro, e nao `atualizar`: a fusao das preferencias guardaria
    # o limite da pessoa que acabou de sair da lista.
    prefs = estado.prefs
    with prefs._trava:
        prefs.dados["limites_ia"] = {"diario": n(novos.get("diario")), "mensal": n(novos.get("mensal")), "pessoas": pessoas}
    prefs.salvar()
    return limites(estado)


def _uso(linhas: list[dict], conta_id: int | None, desde: datetime) -> int:
    total = 0
    for d in linhas:
        if conta_id is not None and pessoa_de(d) != conta_id:
            continue
        try:
            if datetime.fromisoformat(str(d.get("quando", ""))[:19]) < desde:
                continue
        except ValueError:
            continue
        total += tokens_de(d)
    return total


def motivo_do_limite(estado, conta_id: int) -> str:
    """"" quando pode ir à nuvem; senão, por que não (o limite que passou)."""
    lim = limites(estado)
    proprio = lim["pessoas"].get(str(int(conta_id)), {})
    if not (lim["diario"] or lim["mensal"] or proprio):
        return ""
    agora = datetime.now()
    hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    mes, _ = inicio_do_ciclo(estado, agora)
    linhas = ler(estado, min(hoje, mes))
    regras = [
        (lim["diario"], None, hoje, "o limite diário de tokens do escritório"),
        (lim["mensal"], None, mes, "o limite mensal de tokens do escritório"),
        (proprio.get("diario", 0), int(conta_id), hoje, "o seu limite diário de tokens"),
        (proprio.get("mensal", 0), int(conta_id), mes, "o seu limite mensal de tokens"),
    ]
    for teto, quem, desde, nome in regras:
        if teto and _uso(linhas, quem, desde) >= teto:
            return f"{nome} ({teto:,} tokens) foi atingido - ajuste em Plano e consumo".replace(",", ".")
    return ""


# ------------------------------------------------------------- o painel

def _equipe(estado) -> dict[int, str]:
    nomes = {0: nome_da_janela(estado)}
    try:
        for c in estado.acesso_de_fora.contas.listar():
            nomes[int(c.get("id") or c.get("conta_id") or 0)] = str(c.get("nome") or c.get("email") or "Pessoa da equipe")
    except Exception:  # noqa: BLE001 - sem a equipe, só quem aparece no registro
        pass
    return nomes


def painel(estado) -> dict:
    """O consumo do ciclo por pessoa, os limites e os alertas - o que a tela Plano e consumo mostra."""
    agora = datetime.now()
    hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    mes, fim = inicio_do_ciclo(estado, agora)
    linhas = ler(estado, min(hoje, mes))
    nomes = _equipe(estado)
    lim = limites(estado)
    por: dict[int, dict] = {}
    for d in linhas:
        try:
            quando = datetime.fromisoformat(str(d.get("quando", ""))[:19])
        except ValueError:
            continue
        quem = pessoa_de(d)
        p = por.setdefault(quem, {"mes": 0, "hoje": 0})
        if quando >= mes:
            p["mes"] += tokens_de(d)
        if quando >= hoje:
            p["hoje"] += tokens_de(d)
        if isinstance(d.get("pessoa"), dict) and quem not in nomes:
            nomes[quem] = str(d["pessoa"].get("nome") or "Pessoa da equipe")
    if FORA_ANTIGO in por:
        nomes[FORA_ANTIGO] = "De fora (antes do registro por pessoa)"
    total = sum(p["mes"] for p in por.values())
    pessoas = []
    for quem in sorted(set(por) | set(nomes), key=lambda q: -(por.get(q, {}).get("mes", 0))):
        uso = por.get(quem, {"mes": 0, "hoje": 0})
        proprio = lim["pessoas"].get(str(quem), {})
        alerta = ""
        for teto, gasto, rotulo in ((proprio.get("diario", 0), uso["hoje"], "diário"), (proprio.get("mensal", 0), uso["mes"], "mensal")):
            if teto and gasto >= teto:
                alerta = f"atingiu o limite {rotulo}"
                break
            if teto and gasto >= teto * ALERTA and not alerta:
                alerta = f"perto do limite {rotulo} ({round(100 * gasto / teto)}%)"
        pessoas.append({"conta_id": quem, "nome": nomes.get(quem, "Pessoa da equipe"), "tokens": uso["mes"], "hoje": uso["hoje"],
                        "porcento": round(100 * uso["mes"] / total, 1) if total else 0.0, "limite": proprio or None, "alerta": alerta})
    gasto_hoje = sum(p["hoje"] for p in por.values())
    alertas = []
    for teto, gasto, rotulo in ((lim["diario"], gasto_hoje, "diário"), (lim["mensal"], total, "mensal")):
        if teto and gasto >= teto * ALERTA:
            alertas.append(f"O escritório está {'no' if gasto >= teto else 'perto do'} limite {rotulo}: "
                           f"{gasto:,} de {teto:,} tokens.".replace(",", "."))
    return {"ciclo": {"inicio": mes.isoformat(timespec="minutes"), "fim": fim}, "total": total, "hoje": gasto_hoje,
            "pessoas": pessoas, "limites": lim, "alertas": alertas, "areas": _areas(linhas, mes, total),
            "profundidade": _por_profundidade(linhas, mes)}


def _por_profundidade(linhas: list[dict], desde: datetime) -> list[dict]:
    """
    O consumo do ciclo por nível de profundidade (src/profundidade.py), na
    ordem Estagiário -> Ministro: os tokens, quantos pedidos e a média por
    pedido - é a conta que mostra que o Ministro gasta mais da franquia.
    Envio de antes da profundidade não entra.
    """
    import profundidade

    por: dict[str, dict] = {}
    for d in linhas:
        nivel = str(d.get("profundidade") or "")
        if nivel not in profundidade.NIVEIS:
            continue
        try:
            if datetime.fromisoformat(str(d.get("quando", ""))[:19]) < desde:
                continue
        except ValueError:
            continue
        x = por.setdefault(nivel, {"tokens": 0, "pedidos": set()})
        x["tokens"] += tokens_de(d)
        x["pedidos"].add(str(d.get("trabalho_id") or "") + "|" + str(d.get("pergunta") or "")[:60])
    saida = []
    for nid in profundidade.ORDEM:
        n = profundidade.NIVEIS[nid]
        x = por.get(nid) or {"tokens": 0, "pedidos": set()}
        pedidos = len(x["pedidos"])
        saida.append({"nivel": nid, "nome": n.nome, "consumo": n.consumo, "resumo": n.resumo, "tokens": x["tokens"],
                      "pedidos": pedidos, "media": round(x["tokens"] / pedidos) if pedidos else 0})
    return saida


def _areas(linhas: list[dict], desde: datetime, total: int) -> list[dict]:
    """O consumo do ciclo por tarefa do registro (conversa, resumos, redação), da maior para a menor."""
    import nuvem

    por: dict[str, int] = {}
    for d in linhas:
        try:
            if datetime.fromisoformat(str(d.get("quando", ""))[:19]) < desde:
                continue
        except ValueError:
            continue
        tarefa = str(d.get("tarefa") or "conversa")
        por[tarefa] = por.get(tarefa, 0) + tokens_de(d)
    return [{"tarefa": t, "nome": nuvem.TAREFAS.get(t, t), "tokens": n, "porcento": round(100 * n / total, 1) if total else 0.0}
            for t, n in sorted(por.items(), key=lambda x: -x[1]) if n]


# ------------------------------------------------------------- o extrato

def extrato(estado) -> dict:
    """
    O extrato do ciclo: por área e por pessoa, o total e o custo pela conta do
    plano (o valor do plano dividido pelos tokens dele) - não é a fatura, que
    é a mensalidade.
    """
    import nuvem

    p = painel(estado)
    conta = (nuvem._CONTA_CACHE.get("dados") if hasattr(nuvem, "_CONTA_CACHE") else None) or {}
    plano = conta.get("plano") or {}
    por_milhao = None
    if not conta.get("cortesia") and plano.get("valor") and plano.get("tokens"):
        por_milhao = round(float(plano["valor"]) / float(plano["tokens"]) * 1e6, 2)
    return {"ciclo": p["ciclo"], "total": p["total"], "areas": p["areas"],
            "pessoas": [{"nome": x["nome"], "tokens": x["tokens"], "porcento": x["porcento"]} for x in p["pessoas"] if x["tokens"]],
            "plano": str(plano.get("nome") or ""), "por_milhao": por_milhao,
            "custo": round(p["total"] / 1e6 * por_milhao, 2) if por_milhao is not None else None}


def _milhar(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def _reais(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "x").replace(".", ",").replace("x", ".")


def html_do_extrato(e: dict, escapar) -> str:
    """O extrato em HTML, para o gerador de PDF dos documentos."""
    inicio = str(e["ciclo"].get("inicio") or "")[:10]
    fim = str(e["ciclo"].get("fim") or "")[:10]
    periodo = (f"{inicio[8:10]}/{inicio[5:7]}/{inicio[:4]}" if inicio else "") + \
        (f" a {fim[8:10]}/{fim[5:7]}/{fim[:4]}" if fim else " até hoje")
    linhas = ["<h1>Extrato de consumo da IA</h1>",
              f"<p>Ciclo de {escapar(periodo)}" + (f" · plano {escapar(e['plano'])}" if e["plano"] else "") + ".</p>",
              f"<p><b>Total: {_milhar(e['total'])} tokens</b>" +
              (f"<br>Custo pela conta do plano: {_reais(e['custo'])} ({_reais(e['por_milhao'])} por milhão de tokens)" if e["custo"] is not None else "") +
              "</p>"]
    for titulo, itens in (("Por área", e["areas"]), ("Por pessoa", e["pessoas"])):
        linhas.append(f"<h2>{titulo}</h2>")
        if not itens:
            linhas.append("<p>Nenhum envio à nuvem neste ciclo.</p>")
            continue
        linhas.append("<ul>" + "".join(f"<li>{escapar(x['nome'])}: {_milhar(x['tokens'])} tokens "
                                       f"({str(x['porcento']).replace('.', ',')}%)</li>" for x in itens) + "</ul>")
    linhas.append("<p><i>Quem gastou e em quê saem do registro de envios desta máquina; o total que vale para o plano é o "
                  "de paulus.ia.br. O custo é a parte do valor do plano que esses tokens representam, não uma cobrança à parte.</i></p>")
    return "".join(linhas)


def gravar_pdf_do_extrato(estado, escapar) -> Path:
    """O PDF do extrato no Acervo (Relatórios/Consumo da IA), um por dia: refazer no mesmo dia troca o do dia."""
    import documento

    e = extrato(estado)
    pasta = Path(estado.pasta) / "Relatórios" / "Consumo da IA"
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"extrato-consumo-{date.today().isoformat()}.pdf"
    arq.write_bytes(documento.para_pdf(documento.ler_html(html_do_extrato(e, escapar)), "Extrato de consumo da IA",
                                       "PAULUS · extrato gerado nesta máquina"))
    return arq


def historico(estado, conta_id: int, dias: int = 31) -> list[dict]:
    """
    As interações de uma pessoa, da mais nova para a mais antiga, por dia: a
    triagem e a resposta da mesma pergunta viram uma só, com os tokens somados.
    """
    desde = datetime.now() - timedelta(days=dias)
    interacoes: list[dict] = []
    # Pela hora, e nao pela ordem do arquivo: a triagem e a resposta precisam ficar lado a lado.
    for d in sorted(ler(estado, desde), key=lambda x: str(x.get("quando", ""))):
        if pessoa_de(d) != conta_id:
            continue
        pergunta = str(d.get("pergunta") or d.get("titulo") or "").strip()
        quando = str(d.get("quando", ""))[:19]
        ultima = interacoes[-1] if interacoes else None
        if (ultima and ultima["trabalho_id"] and ultima["trabalho_id"] == d.get("trabalho_id") and ultima["pergunta"] == pergunta
                and _segundos(ultima["quando"], quando) <= JANELA_MESMA_PERGUNTA_S):
            ultima["tokens"] += tokens_de(d)
            ultima["quando"] = quando
            continue
        interacoes.append({"quando": quando, "pergunta": pergunta[:140], "tokens": tokens_de(d),
                           "trabalho_id": str(d.get("trabalho_id") or ""), "tarefa": str(d.get("tarefa") or "")})
    dias_saida: dict[str, list] = {}
    for i in reversed(interacoes):
        dias_saida.setdefault(i["quando"][:10], []).append(i)
    hoje = date.today()
    nomes = {hoje.isoformat(): "Hoje", (hoje - timedelta(days=1)).isoformat(): "Ontem"}
    return [{"dia": dia, "rotulo": nomes.get(dia) or datetime.fromisoformat(dia).strftime("%d/%m/%Y"),
             "tokens": sum(i["tokens"] for i in lista), "itens": lista} for dia, lista in dias_saida.items()]


def _segundos(a: str, b: str) -> float:
    try:
        return abs((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds())
    except ValueError:
        return 1e9
