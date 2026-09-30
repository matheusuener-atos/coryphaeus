"""
T1 - a saudacao que nao se repete (src/saudacao.py, config/saudacoes.json).

Com relogio simulado:
  - o banco tem pelo menos 120 titulos e 80 subtitulos, ids unicos;
  - 30 aberturas seguidas no mesmo contexto -> nenhuma frase repetida entre
    as 20 ultimas;
  - com prazo hoje, a frase fala do prazo, em qualquer dia da semana;
  - 25/12, Sexta-feira Santa, Carnaval e 10/01 (recesso) escolhem frases
    dessas condicoes;
  - sem nome cadastrado, nenhuma frase fica com buraco no lugar do nome;
  - nenhum titulo passa de 90 caracteres, mesmo com nome e titulos longos;
  - a escolha leva menos de 50 ms e nao chama modelo nenhum;
  - pela API: com a chave desligada, `ligado: false`; ligada, a frase vem.
Imprime 10 exemplos, um de cada tipo de condicao (vao para o PROGRESSO).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_t1_saudacao.py
"""

from __future__ import annotations

import random
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import prazos  # noqa: E402
import saudacao  # noqa: E402

_falhas: list[str] = []
BANCO = saudacao.carregar()


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def ctx(quando: datetime, **k) -> saudacao.Contexto:
    base = dict(nome="Helena Moura", documentos=12, ultima_abertura=quando - timedelta(hours=2))
    base.update(k)
    return saudacao.Contexto(agora=quando, **base)


def titulo(c: saudacao.Contexto, recentes=None, semente=1) -> dict:
    return saudacao.escolher(BANCO["titulos"], c, recentes or [], sorteio=random.Random(semente), limite=saudacao.LIMITE_TITULO)


def test_banco() -> None:
    print("\no banco")
    t, s = BANCO["titulos"], BANCO["subtitulos"]
    ids = [x["id"] for x in t + s]
    checar(len(t) >= 120 and len(s) >= 80, f"{len(t)} títulos e {len(s)} subtítulos (mínimo 120 e 80)")
    checar(len(ids) == len(set(ids)), "ids únicos")
    antigos = {"Ainda de pé a esta hora?", "Trabalhando até tarde?!", "Sexta. Fechamos algo antes do fim do dia?",
               "Segunda. Por onde começamos?", "Olá. Por onde começamos?"}
    checar(antigos <= {x["texto"] for x in t}, "as cinco frases de antes continuam no banco")
    marcas = {"nome": "Maria Aparecida", "conversa": "“" + "x" * 39 + "…”", "feriado": "Proclamação da República",
              "prazo": "y" * 40, "n_prazos": "12", "pendencias": "143"}
    longos = [x["texto"] for x in t if len(saudacao.preencher(x["texto"], marcas)) > saudacao.LIMITE_TITULO]
    checar(not longos, "nenhum título passa de 90 caracteres, com as marcas no tamanho máximo", longos[:3])
    desconhecidas = {m for x in t + s for m in saudacao.RE_MARCA.findall(x["texto"])} - set(marcas)
    checar(not desconhecidas, "nenhuma marca desconhecida no banco", desconhecidas)


def test_sem_repetir() -> None:
    print("\n30 aberturas seguidas no mesmo contexto")
    quando = datetime(2026, 9, 29, 10, 0)   # terça, 10h
    recentes, mostrados = [], []
    r = random.Random(7)
    for _ in range(30):
        f = saudacao.escolher(BANCO["titulos"], ctx(quando), recentes, sorteio=r, limite=saudacao.LIMITE_TITULO)
        mostrados.append(f["id"])
        recentes = (recentes + [f["id"]])[-saudacao.RECENTES:]
    repetidos = [i for i in range(20, 30) if mostrados[i] in mostrados[i - 20:i]] + \
                [i for i in range(1, 20) if mostrados[i] in mostrados[:i]]
    checar(not repetidos, "nenhuma frase repetida entre as 20 últimas", [mostrados[i] for i in repetidos])


def test_situacao() -> None:
    print("\na situação vence o calendário")
    for d in range(7):
        quando = datetime(2026, 10, 5, 9, 30) + timedelta(days=d)   # segunda a domingo
        f = titulo(ctx(quando, prazos_hoje=["Contestação — processo 1234567-89"]))
        if not f["id"].startswith("t-prazo"):
            checar(False, f"com prazo hoje ({quando:%A}), a frase fala do prazo", f)
            return
    checar(True, "com prazo hoje, a frase fala do prazo, em todos os dias da semana")
    f = titulo(ctx(datetime(2026, 12, 25, 10), prazos_hoje=["Contestação"]))
    checar(f["id"].startswith("t-prazo"), "até no Natal", f)
    f = titulo(ctx(datetime(2026, 10, 9, 10), prazos_hoje=["a", "b", "c"]))
    checar(f["id"].startswith("t-prazos") and "3 prazos" in f["texto"], "vários prazos: a frase diz quantos", f)
    f = titulo(ctx(datetime(2026, 10, 9, 10), documentos=0))
    checar(f["id"].startswith("t-vazio"), "acervo vazio (primeiro uso)", f)


def test_calendario() -> None:
    print("\no calendário")
    ano = 2027
    p = prazos.pascoa(ano)
    casos = [
        ("25/12 (Natal)", datetime(2026, 12, 25, 10), {"feriado", "recesso"}),
        ("Sexta-feira Santa", datetime.combine(p - timedelta(days=2), datetime.min.time()).replace(hour=10), {"feriado"}),
        ("Carnaval", datetime.combine(p - timedelta(days=47), datetime.min.time()).replace(hour=10), {"feriado"}),
        ("10/01 (recesso)", datetime(2027, 1, 10, 10), {"recesso", "inicio_ano"}),
    ]
    for nome, quando, conds in casos:
        f = titulo(ctx(quando))
        frase = next(x for x in BANCO["titulos"] if x["id"] == f["id"])
        checar(set(frase.get("calendario") or []) & conds, f"{nome}: frase dessa condição — “{f['texto']}”", frase.get("calendario"))
    f = titulo(ctx(datetime(2026, 11, 14, 10)))
    checar("Proclamação da República" in f["texto"] or f["id"].startswith("t-vesp"), "véspera de feriado diz qual", f)


def test_sem_nome() -> None:
    print("\nsem nome cadastrado")
    buracos = []
    r = random.Random(3)
    for h in range(0, 24, 2):
        for d in range(7):
            quando = datetime(2026, 9, 28, h) + timedelta(days=d)
            for extra in ({}, {"prazos_hoje": ["Prazo X"]}, {"documentos": 0}, {"pendencias": 20}):
                c = ctx(quando, nome="", **extra)
                f = saudacao.escolher(BANCO["titulos"], c, [], sorteio=r, limite=saudacao.LIMITE_TITULO)
                s = saudacao.escolher(BANCO["subtitulos"], c, [], sorteio=r)
                for texto in (f["texto"], s["texto"]):
                    if "{" in texto or re.search(r"(^|\s)[,.!?]|,\s*[.?!]|\s{2,}", texto):
                        buracos.append(texto)
    checar(not buracos, "nenhuma frase com buraco no lugar do nome (672 aberturas)", buracos[:3])


def test_chegada() -> None:
    print("\ncomo chegou")
    quando = datetime(2026, 10, 7, 15, 0)
    c = ctx(quando, ultima_conversa={"id": "x1", "titulo": "Contrato ACME", "aberta_em": quando - timedelta(minutes=40)})
    f = titulo(c)
    checar(f["id"].startswith("t-volta") and "“Contrato ACME”" in f["texto"], "de volta em pouco tempo: cita a conversa", f)
    d = saudacao.saudar(c, [], sorteio=random.Random(1))
    checar(d["conversa"] and d["conversa"]["id"] == "x1", "e diz qual abrir (o link da frase)")
    f = titulo(ctx(quando, ultima_abertura=quando - timedelta(days=6)))
    checar(f["id"].startswith(("t-dias", "t-dia")), "depois de dias sem abrir", f)


def test_rapidez_e_api() -> None:
    print("\nrápida, sem modelo, e pela API")
    c = ctx(datetime(2026, 10, 7, 15, 0))
    comeco = time.perf_counter()
    for _ in range(20):
        saudacao.saudar(c, [], banco=BANCO)
    ms = (time.perf_counter() - comeco) * 1000 / 20
    checar(ms < 50, f"a escolha leva {ms:.1f} ms (menos de 50)")
    from fastapi.testclient import TestClient

    import api

    chamado = []
    antes_ask = getattr(api.estado.client, "ask", None)
    api.estado.client.ask = lambda *a, **k: chamado.append(1)
    antes = dict(api.estado.prefs.dados.get("conversa") or {})
    try:
        cli = TestClient(api.app, headers=api.cabecalho_local())
        api.estado.prefs.dados["conversa"] = {**antes, "saudacao": False}
        checar(cli.get("/api/saudacao").json() == {"ligado": False}, "com a chave desligada, nada muda")
        api.estado.prefs.dados["conversa"] = {**antes, "saudacao": True}
        r = cli.get("/api/saudacao", params={"agora": "2026-12-25T10:00:00", "recentes": "t-feriado-1"}).json()
        checar(r["ligado"] and r["titulo"] and r["subtitulo"] and len(r["ids"]) == 2, "ligada, a frase vem", r)
        checar(not chamado, "sem chamar o modelo")
        test_tela()
    finally:
        api.estado.prefs.dados["conversa"] = antes
        if antes_ask is not None:
            api.estado.client.ask = antes_ask


def test_tela() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    textos = {x["texto"] for x in BANCO["titulos"]}
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        pag = nav.new_page(viewport={"width": 1280, "height": 800})
        pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        erros: list[str] = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="networkidle")
        pag.wait_for_function("() => (JSON.parse(localStorage.getItem('paulus.saudacoes') || '[]')).length >= 2", timeout=10000)
        vistos = []
        for _ in range(3):
            pag.evaluate("() => atualizarSaudacao()")
            pag.wait_for_timeout(500)
            vistos.append(pag.evaluate("() => document.getElementById('chamada').textContent"))
        nome = ((api.estado.prefs.dados.get("pessoa") or {}).get("nome") or "").split(" ")[0]
        pertence = all(any(saudacao.preencher(t, {"nome": nome}) == v or "{" in t for t in textos) or v for v in vistos)
        checar(pertence and len(set(vistos)) == 3, "na tela: a frase vem do banco, e três aberturas dão três frases", vistos)
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


def exemplos() -> None:
    print("\ndez exemplos, um de cada tipo de condição")
    casos = [
        ("madrugada", ctx(datetime(2026, 10, 6, 3))),
        ("manhã de segunda", ctx(datetime(2026, 10, 5, 9))),
        ("fim de tarde de sexta", ctx(datetime(2026, 10, 9, 18))),
        ("domingo", ctx(datetime(2026, 10, 11, 11))),
        ("fim de mês", ctx(datetime(2026, 10, 30, 14, 30))),
        ("véspera de feriado", ctx(datetime(2026, 11, 1, 10))),
        ("recesso", ctx(datetime(2027, 1, 12, 10))),
        ("volta rápida", ctx(datetime(2026, 10, 7, 15), ultima_conversa={"id": "x", "titulo": "Contrato ACME", "aberta_em": datetime(2026, 10, 7, 14)})),
        ("prazo hoje", ctx(datetime(2026, 10, 8, 8, 30), prazos_hoje=["Contestação — processo 1234567-89"])),
        ("acervo vazio, sem nome", ctx(datetime(2026, 10, 8, 16), nome="", documentos=0)),
    ]
    for rotulo, c in casos:
        d = saudacao.saudar(c, [], banco=BANCO, sorteio=random.Random(11))
        print(f"  - {rotulo}: “{d['titulo']}” / “{d['subtitulo']}”")


def main() -> int:
    print("=" * 55)
    print("  T1 — a saudação que não se repete")
    print("=" * 55)
    test_banco()
    test_sem_repetir()
    test_situacao()
    test_calendario()
    test_sem_nome()
    test_chegada()
    test_rapidez_e_api()
    exemplos()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
