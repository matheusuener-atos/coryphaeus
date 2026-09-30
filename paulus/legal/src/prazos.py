"""
Prazos processuais em dias uteis (docs/PLANO-PRODUTO.md, P3).

As regras (CPC/2015 e Lei 11.419/2006):

  - art. 219: na contagem em dias, so os dias uteis;
  - art. 224: exclui o dia do comeco e inclui o do vencimento; comeco ou
    vencimento em dia sem expediente passa para o primeiro dia util seguinte;
  - art. 220: de 20 de dezembro a 20 de janeiro os prazos ficam suspensos;
  - Lei 11.419, art. 4o, par. 3o e 4o: no Diario eletronico, a publicacao e o
    primeiro dia util seguinte ao da disponibilizacao, e o prazo comeca no
    primeiro dia util seguinte ao da publicacao.

Dias sem expediente: os feriados nacionais (Lei 662/1949, Lei 6.802/1980,
Lei 14.759/2023), a segunda e a terca de Carnaval, a Sexta-feira Santa e
Corpus Christi (sem expediente forense na pratica dos tribunais), e os que o
escritorio cadastrar - feriado municipal ou estadual, ponto facultativo e
suspensao do tribunal. O PAULUS mostra a conta passo a passo: o advogado
confere, porque a regra de cada tribunal manda.
"""

from __future__ import annotations

from datetime import date, timedelta

FIXOS = {(1, 1): "Confraternização Universal", (4, 21): "Tiradentes", (5, 1): "Dia do Trabalho",
         (9, 7): "Independência", (10, 12): "Nossa Senhora Aparecida", (11, 2): "Finados",
         (11, 15): "Proclamação da República", (11, 20): "Consciência Negra", (12, 25): "Natal"}


def pascoa(ano: int) -> date:
    """Domingo de Pascoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados(ano: int) -> dict[date, str]:
    p = pascoa(ano)
    dias = {date(ano, m, d): nome for (m, d), nome in FIXOS.items()}
    dias[p - timedelta(days=48)] = "Carnaval (segunda)"
    dias[p - timedelta(days=47)] = "Carnaval (terça)"
    dias[p - timedelta(days=2)] = "Sexta-feira Santa"
    dias[p + timedelta(days=60)] = "Corpus Christi"
    return dias


def em_recesso(d: date) -> bool:
    """CPC art. 220: suspensos de 20/12 a 20/01, inclusive."""
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 20)


def motivo_sem_expediente(d: date, extras: dict[date, str] | None = None) -> str:
    """Por que `d` nao conta ("" quando e dia util)."""
    if d.weekday() == 5:
        return "sábado"
    if d.weekday() == 6:
        return "domingo"
    if extras and d in extras:
        return extras[d]
    nome = feriados(d.year).get(d)
    if nome:
        return "feriado: " + nome
    return ""


def util(d: date, extras: dict[date, str] | None = None, recesso: bool = True) -> bool:
    return not motivo_sem_expediente(d, extras) and not (recesso and em_recesso(d))


def proximo_util(d: date, extras: dict[date, str] | None = None, recesso: bool = True) -> date:
    while not util(d, extras, recesso):
        d += timedelta(days=1)
    return d


def _dia(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def calcular(data: date, dias: int, *, origem: str = "intimacao", uteis: bool = True,
             extras: dict[date, str] | None = None, recesso: bool = True) -> dict:
    """
    O vencimento de um prazo de `dias` a partir de `data`.

    `origem`: "disponibilizacao" (a data em que o Diario eletronico pos no ar)
    ou "intimacao" (a data da ciencia: publicacao, intimacao pessoal, juntada
    do mandado). Devolve {vencimento, publicacao, inicio, passos} - os passos
    em portugues, para o advogado conferir. `recesso=False` no processo penal:
    o art. 220 do CPC nao suspende o prazo (CPP, art. 798).
    """
    if dias < 1 or dias > 3650:
        raise ValueError("o prazo precisa ter de 1 a 3650 dias")
    passos: list[str] = []
    publicacao = data
    if origem == "disponibilizacao":
        publicacao = proximo_util(data + timedelta(days=1), extras, recesso)
        passos.append(f"Disponibilizado em {_dia(data)}; publicado no primeiro dia útil seguinte, {_dia(publicacao)} (Lei 11.419, art. 4º, § 3º).")
    else:
        passos.append(f"Intimação em {_dia(data)}: o dia do começo não conta (CPC, art. 224).")
    inicio = proximo_util(publicacao + timedelta(days=1), extras, recesso)
    pulados = []
    d = publicacao + timedelta(days=1)
    while d < inicio:
        pulados.append(d)
        d += timedelta(days=1)
    passos.append(f"O prazo começa em {_dia(inicio)}" + (f", depois de {len(pulados)} dia(s) sem expediente ou em recesso" if pulados else "") + ".")
    if uteis:
        contados, d = 1, inicio
        sem: list[str] = []
        while contados < dias:
            d += timedelta(days=1)
            if util(d, extras, recesso):
                contados += 1
            else:
                sem.append(_dia(d) + " (" + (motivo_sem_expediente(d, extras) or "recesso forense, CPC art. 220") + ")")
        vencimento = d
        passos.append(f"{dias} dias úteis (CPC, art. 219)" + (f"; não contam: {', '.join(sem[:12])}" + (" e outros" if len(sem) > 12 else "") if sem else "") + ".")
    else:
        bruto = inicio + timedelta(days=dias - 1)
        vencimento = proximo_util(bruto, extras, recesso)
        passos.append(f"{dias} dias corridos" + ("" if recesso else " (sem a suspensão do art. 220 do CPC)") + f": {_dia(bruto)}" +
                      (f", que cai em dia sem expediente — passa para {_dia(vencimento)} (CPC, art. 224, § 1º)" if vencimento != bruto else "") + ".")
    passos.append(f"Vence em {_dia(vencimento)}.")
    return {"vencimento": vencimento.isoformat(), "publicacao": publicacao.isoformat(), "inicio": inicio.isoformat(), "passos": passos}


def extras_das_preferencias(lista) -> dict[date, str]:
    """Os feriados e suspensoes que o escritorio cadastrou: [{data: "AAAA-MM-DD", nome}]."""
    saida: dict[date, str] = {}
    for item in lista or []:
        try:
            saida[date.fromisoformat(str(item.get("data")))] = str(item.get("nome") or "sem expediente")
        except (ValueError, AttributeError):
            continue
    return saida
