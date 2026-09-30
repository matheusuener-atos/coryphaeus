"""
PAULUS - O "ver detalhes" de uma resposta (C2), a partir do registro da execucao.

O "o que estou fazendo" existia so no navegador: fechou a janela, sumiu. As
linhas dele sao o registro da execucao (src/execucoes.py) em linguagem
simples, e ficam guardadas com a resposta (`cobertura.detalhes`), para a
conversa reaberta mostrar o mesmo que mostrou na hora.

Cada linha: {"s": segundos desde o comeco, "texto": ..., "classe": "" | "feito" | "erro"}.
Vermelho so para erro: "documento sem trecho" e informacao, nao falha.
"""

from __future__ import annotations

from datetime import datetime

# Mais que isto de nomes numa linha vira contagem (C2: "a resposta salva nunca
# contem lista de mais de 5 nomes de documento").
NOMES_NA_LINHA = 5


def _milhar(n) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _seg(x) -> str:
    try:
        return f"{float(x):.1f}".replace(".", ",") + " s"
    except (TypeError, ValueError):
        return "? s"


def _plural(n: int, palavra: str) -> str:
    return f"{n} {palavra}" + ("" if n == 1 else "s")


def _quando(em: str) -> float:
    try:
        return datetime.fromisoformat(em).timestamp()
    except (TypeError, ValueError):
        return 0.0


def nomes_curtos(nomes: list[str], limite: int = NOMES_NA_LINHA) -> str:
    """'a, b e c' - ou 'a, b, c, d, e e mais 51' quando passa do limite."""
    nomes = [n for n in nomes if n]
    if len(nomes) <= limite:
        return ", ".join(nomes[:-1]) + (" e " if len(nomes) > 1 else "") + (nomes[-1] if nomes else "")
    return ", ".join(nomes[:limite]) + f" e mais {len(nomes) - limite}"


def linhas(eventos: list[dict]) -> list[dict]:
    """As linhas do "ver detalhes", na ordem em que aconteceram."""
    if not eventos:
        return []
    comeco = _quando(eventos[0].get("em", ""))
    saida: list[dict] = []

    def dizer(e: dict, texto: str, classe: str = "") -> None:
        s = max(0.0, _quando(e.get("em", "")) - comeco) if comeco else 0.0
        saida.append({"s": round(s, 1), "texto": texto, "classe": classe})

    ultima_posicao = None
    for e in eventos:
        tipo, d = e.get("tipo", ""), e.get("dados") or {}
        if tipo == "fila":
            if d.get("posicao") != ultima_posicao:
                ultima_posicao = d.get("posicao")
                dizer(e, f"esperando a vez no modelo: {d.get('posicao', '?')}ª da fila")
        elif tipo == "fontes":
            trechos = len(d.get("trechos") or [])
            apenas = d.get("apenas") or []
            if apenas:
                sobre = f"“{apenas[0]}” · li só ele" if len(apenas) == 1 else f"{_plural(len(apenas), 'documento')} · li só eles"
                dizer(e, f"a pergunta é sobre {sobre}, {_plural(trechos, 'trecho')}")
            else:
                dizer(e, f"procurei nos {_plural(int(d.get('total_contratos') or 0), 'documento')} abertos · "
                         f"vou usar {_plural(trechos, 'trecho')} de {_plural(len(d.get('consultados') or []), 'documento')}")
            sem = d.get("ignorados") or []
            if sem:
                dizer(e, f"{_plural(len(sem), 'documento')} sem nada sobre isso")
        elif tipo == "lendo":
            if d.get("molde") and not d.get("caracteres"):
                dizer(e, "respondi pelos fatos já conferidos, sem o modelo")
                continue
            dizer(e, f"mandei {_milhar(d.get('caracteres', 0))} caracteres para o {d.get('modelo') or 'modelo'}"
                     + (f", janela de {_milhar(d['janela'])} tokens" if d.get("janela") else ""))
            p = d.get("previsao") or {}
            if p.get("sabe"):
                dizer(e, f"aqui, leituras deste tamanho levaram ~{p.get('segundos')} s "
                         f"(mediana de {_plural(int(p.get('medicoes') or 0), 'leitura')})")
        elif tipo == "escrevendo":
            dizer(e, f"primeira palavra saiu · esperei {_seg(d.get('lendo_segundos'))} até aqui")
        elif tipo == "truncou":
            dizer(e, f"o texto passou da janela de {_milhar(d.get('num_ctx', 0))} tokens; o modelo leu só o final dele")
        elif tipo == "medida":
            dizer(e, f"pronto · o modelo gastou {_seg(d.get('lendo_segundos'))} lendo {_milhar(d.get('tokens_lidos', 0))} tokens"
                     + (" (boa parte já estava em cache)" if d.get("do_cache") else "")
                     + f" e {_seg(d.get('escrevendo_segundos'))} escrevendo {_milhar(d.get('tokens_escritos', 0))}", "feito")
        elif tipo == "revisao" and d.get("removidas"):
            dizer(e, "tirei da resposta o que não está nos trechos lidos: " + "; ".join(d["removidas"])[:300])
        elif tipo == "refazendo":
            dizer(e, "a resposta citou um trecho que não existe — refazendo com menos trechos")
        elif tipo == "parado":
            dizer(e, "parei a pedido")
        elif tipo == "erro":
            dizer(e, "não consegui terminar: " + str(d.get("mensagem", ""))[:200], "erro")
        elif tipo == "interrompida":
            dizer(e, "o programa fechou no meio da resposta; ficou o que já tinha saído", "erro")
    return saida
