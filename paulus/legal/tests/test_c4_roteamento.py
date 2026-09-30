"""
C4 - o roteamento: perguntas sobre o programa e consultas de cadastro.

Antes (30/09/2026): "Pra que serve a busca no DJE?" caía na busca de
documentos e respondia "Não achei nada nos documentos abertos"; "Qual o CPF
do cliente Matheus" lia 21 documentos (~165 s) para achar um número que está
na ficha de Cadastros. Com a chave `conversa.roteamento`:

  - perguntas sobre Publicações e DJE, a busca Ctrl+K, a Biblioteca, os
    Códigos de lei, a Agenda, as Aprovações e o Acesso de fora respondem pela
    tela certa (src/programa_mapa.json), sem chamar o modelo de conversa nem o
    juiz;
  - "CPF de", "CNPJ de", "telefone de", "e-mail de", "endereço de", "OAB de"
    + nome respondem por molde, dos Cadastros, em menos de 200 ms e sem
    modelo (src/consulta_cadastro.py);
  - nome ambíguo vira lista para escolher; nome que não está em lugar nenhum
    vira oferta de ler os documentos - e nada é lido sem o clique;
  - sem cadastro, os fatos já conferidos dos documentos (metadata) respondem,
    com o documento e a página;
  - as perguntas de documento do banco de provas (tools/demo/roteiro.py)
    continuam indo para os documentos: só o roteamento, sem modelo;
  - com a chave desligada, tudo como antes.

Não precisa do Ollama.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_c4_roteamento.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))
sys.path.insert(0, str(RAIZ / "tools" / "demo"))

import consulta_cadastro  # noqa: E402
import intencao  # noqa: E402
import programa  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _cpf(nove: str) -> str:
    """Um CPF que fecha a conta, a partir de nove dígitos."""
    d = [int(c) for c in nove]
    for peso in (10, 11):
        s = sum(n * (peso - i) for i, n in enumerate(d))
        d.append(0 if s % 11 < 2 else 11 - s % 11)
    t = "".join(map(str, d))
    return f"{t[:3]}.{t[3:6]}.{t[6:9]}-{t[9:]}"


def _cnpj(doze: str) -> str:
    d = [int(c) for c in doze]
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        s = sum(n * p for n, p in zip(d, pesos))
        d.append(0 if s % 11 < 2 else 11 - s % 11)
    t = "".join(map(str, d))
    return f"{t[:2]}.{t[2:5]}.{t[5:8]}/{t[8:12]}-{t[12:]}"


# Nomes que nao existem nos Cadastros de verdade: o teste roda tambem nos
# dados do escritorio, e um "Matheus" de la tornava a consulta ambigua.
CPF_MATHEUS = _cpf("529982247")
CPF_ANDRADE = _cpf("111444777")
CPF_LIVIA = _cpf("123456789")
CNPJ_CLINICA = _cnpj("112223330001")
CNPJ_COOP = _cnpj("183904570001")

FICHAS = [
    {"tipo": "cliente", "nome": "Teodoro Quintanilha Braga", "documento": CPF_MATHEUS, "telefone": "(62) 99999-8888",
     "email": "matheus@exemplo.com.br", "endereco": "Rua 10, 200, Setor Oeste, Goiânia/GO"},
    {"tipo": "cliente", "nome": "Teodoro Andrade", "documento": CPF_ANDRADE},
    {"tipo": "cliente", "nome": "Clínica Bem Viver Ltda.", "documento": CNPJ_CLINICA, "telefone": "(62) 3222-1100",
     "email": "contato@bemviver.exemplo", "endereco": "Av. T-63, 1500, sala 402, Goiânia/GO"},
    {"tipo": "cliente", "nome": "Cooperativa Agrícola Vale Verde", "documento": CNPJ_COOP},
    {"tipo": "colaborador", "nome": "Lívia Santos", "documento": CPF_LIVIA, "email": "livia@escritorio.exemplo"},
]
TITULAR = {"nome": "Helena Moura Campos", "oab": "GO 12.345", "cpf": "", "telefone": "", "email": "", "endereco": ""}


class _NaoChame(Exception):
    pass


class JuizQueFalha:
    """O juiz que não pode ser chamado: a regra decide sozinha."""

    chamadas = 0

    def escolher(self, *a, **k):
        JuizQueFalha.chamadas += 1
        raise _NaoChame("o juiz foi chamado")


# ------------------------------------------------ 1. sobre o programa

# (pergunta, destino). Cada tela nova com pelo menos duas; as antigas da
# lista (Agenda, Aprovações) com a pergunta de "para que serve".
SOBRE_O_PROGRAMA = [
    ("Pra que serve a busca no DJE?", "publicacoes"),
    ("o que são as publicações do DJEN?", "publicacoes"),
    ("como vejo as intimações do diário oficial?", "publicacoes"),
    ("como acompanho as publicações de outra OAB da equipe?", "publicacoes"),
    ("como cadastro os feriados do município para os prazos?", "publicacoes"),
    ("pra que serve o Ctrl+K?", "busca"),
    ("o que é a busca de tudo?", "busca"),
    ("como acho um cliente de qualquer tela?", "busca"),
    ("pra que serve a Biblioteca?", "habilidades"),
    ("como coloco um livro de doutrina na biblioteca?", "habilidades"),
    ("como importo um pacote de material de outro PAULUS?", "habilidades"),
    ("como cito um artigo de lei no texto?", "leis"),
    ("como instalo o código civil?", "leis"),
    ("o que são os códigos de lei?", "leis"),
    ("como uso o PAULUS de casa?", "acesso"),
    ("o que é o acesso de fora?", "acesso"),
    ("como vejo quem acessou de fora?", "acesso"),
    ("como desligo o acesso de fora?", "acesso"),
    ("pra que serve a Agenda?", "calendario"),
    ("como calculo um prazo processual?", "calendario"),
    ("pra que servem as Aprovações?", "aprovacoes"),
    ("onde vejo o que já aprovei?", "aprovacoes"),
]


def test_programa() -> None:
    print("\nsobre o programa: a tela certa, pela regra")
    JuizQueFalha.chamadas = 0
    errados = []
    for frase, destino in SOBRE_O_PROGRAMA:
        try:
            leitura = programa.ler(frase, dados=None, juiz=JuizQueFalha(), ampliado=True)
        except _NaoChame:
            leitura = None
        veio = (leitura.tipo, leitura.destino) if leitura else None
        if not leitura or leitura.tipo not in ("como", "ir") or leitura.destino != destino:
            errados.append((frase, destino, veio))
    checar(len(SOBRE_O_PROGRAMA) >= 15 and not errados,
           f"as {len(SOBRE_O_PROGRAMA)} perguntas sobre o programa vão à tela certa", errados)
    checar(JuizQueFalha.chamadas == 0, "sem chamar o juiz", JuizQueFalha.chamadas)

    telas = {d: programa.nome_da_tela(d, ampliado=True) for d in ("publicacoes", "busca", "leis", "acesso", "habilidades")}
    checar(telas == {"publicacoes": "Publicações", "busca": "Buscar em tudo", "leis": "Códigos de lei",
                     "acesso": "Acesso de fora", "habilidades": "Biblioteca"},
           "os nomes que a pessoa lê na tela", telas)

    mapa = programa.mapa_para(True)
    novas = {d: len([t for t in mapa[d].tarefas if t.c4])
             for d in ("publicacoes", "busca", "leis", "acesso", "habilidades")}
    checar(all(3 <= n <= 5 for n in novas.values()), f"cada tela nova ganhou de 3 a 5 perguntas de exemplo {novas}",
           novas)
    antigas = {d: len([t for t in mapa[d].tarefas if t.c4]) for d in ("calendario", "tarefas", "aprovacoes")}
    checar(all(antigas.values()) and sum(antigas.values()) >= 3,
           f"Agenda, To-do e Aprovações, que já tinham 17, ganharam mais {sum(antigas.values())}", antigas)
    checar("agentes" not in mapa, "a tela Agentes ainda não existe e não entrou no mapa")

    print("\nsobre o programa: com a chave desligada, como antes")
    antes = programa.ler("Pra que serve a busca no DJE?", dados=None, juiz=None, ampliado=False)
    checar(antes is None, "“Pra que serve a busca no DJE?” segue para os documentos", antes and antes.to_dict())
    desligado = programa.mapa_para(False)
    checar("publicacoes" not in desligado and all(not t.c4 for tela in desligado.values() for t in tela.tarefas),
           "o mapa sem a chave não tem as telas nem as perguntas da C4")
    checar(programa.ler("para que serve o acervo?", ampliado=False).destino == "biblioteca"
           and programa.ler("para que serve o acervo?", ampliado=True).destino == "biblioteca",
           "o Acervo continua o Acervo, com ou sem a chave")


# --------------------------------------------- 2. consulta de cadastro


def _fichas_com_id() -> list[dict]:
    return [dict(f, id=i + 1) for i, f in enumerate(FICHAS)]


CONSULTAS = [
    ("qual o CPF de Teodoro Quintanilha Braga?", CPF_MATHEUS, "Cadastros"),
    ("Qual o CPF do cliente Teodoro Andrade", CPF_ANDRADE, "Cadastros"),
    ("qual o telefone da Clínica Bem Viver?", "(62) 3222-1100", "Cadastros"),
    ("qual é o e-mail da clinica bem viver?", "contato@bemviver.exemplo", "Cadastros"),
    ("qual o endereço da Clínica Bem Viver?", "Av. T-63, 1500", "Cadastros"),
    ("me passa o CNPJ da Cooperativa Agrícola Vale Verde", CNPJ_COOP, "Cadastros"),
    ("qual o telefone do Teodoro Quintanilha?", "(62) 99999-8888", "Cadastros"),
    ("qual o email da Lívia?", "livia@escritorio.exemplo", "Cadastros"),
    ("qual o CPF da Clínica Bem Viver?", CNPJ_CLINICA, "Cadastros"),
    ("qual a OAB da Dra. Helena Moura Campos?", "GO 12.345", "Meus dados"),
    ("qual o número de telefone de contato do Teodoro Quintanilha Braga?", "(62) 99999-8888", "Cadastros"),
]


def test_consulta_modulo() -> None:
    print("\nconsulta de cadastro: o molde, sem modelo")
    fichas = _fichas_com_id()
    prefs = {"pessoa": TITULAR, "escritorio": {"nome": "Moura Campos Advocacia", "cnpj": "", "oab": ""}}
    errados = []
    for frase, valor, fonte in CONSULTAS:
        r = consulta_cadastro.ler(frase, cadastros=fichas, preferencias=prefs)
        if not r or r.modo != "achado" or valor not in r.texto or f"({fonte})" not in r.texto:
            errados.append((frase, r and (r.modo, r.texto)))
    checar(not errados, f"as {len(CONSULTAS)} consultas respondem pelo molde, com a fonte", errados)

    r = consulta_cadastro.ler("qual o CPF de Teodoro Quintanilha Braga?", cadastros=fichas, preferencias=prefs)
    checar(r and r.texto == f"O CPF de Teodoro Quintanilha Braga é {CPF_MATHEUS} (Cadastros).", "a frase do molde", r and r.texto)
    r = consulta_cadastro.ler("qual o CPF da Clínica Bem Viver?", cadastros=fichas, preferencias=prefs)
    checar(r and "CNPJ" in r.texto and "não um CPF" in r.texto, "CPF pedido, CNPJ cadastrado: diz o que há", r and r.texto)

    r = consulta_cadastro.ler("qual o CPF do Teodoro?", cadastros=fichas, preferencias=prefs)
    nomes = sorted(o["nome"] for o in (r.opcoes if r else []))
    checar(r and r.modo == "escolher" and nomes == ["Teodoro Andrade", "Teodoro Quintanilha Braga"],
           "nome ambíguo: a lista para escolher", r and (r.modo, nomes))
    checar(r and all(o["pergunta"].startswith("qual o CPF de ") for o in r.opcoes),
           "cada opção refaz a pergunta com o nome inteiro", r and r.opcoes)

    for frase in ("qual o CPF do cliente Fulano Beltrano?", "qual o telefone de Fulano Beltrano?"):
        chamado = []
        r = consulta_cadastro.ler(frase, cadastros=fichas, preferencias=prefs,
                                  fatos=lambda nome, campo: chamado.append((nome, campo)) or [])
        checar(r and r.modo == "nada" and "não encontrei" in r.texto.lower() and r.oferta,
               f"“{frase}”: não encontrei, com a oferta de ler os documentos", r and (r.modo, r.texto))
    checar(chamado == [] or all(c[1] for c in chamado), "os fatos são consultados pelo campo, nunca o acervo")

    r = consulta_cadastro.ler("qual o CPF de Teodoro Quintanilha Braga?", cadastros=fichas, preferencias=prefs)
    p = consulta_cadastro.proposta(r, "qual o CPF de Teodoro Quintanilha Braga?")
    checar(p["tipo"] == "consulta_cadastro" and p["modo"] == "achado" and p["campos"]["ficha_id"] == 1,
           "o cartão leva à ficha", p)

    # O que NÃO é consulta de cadastro.
    nao = [
        "qual o CPF do locador?",
        "qual o CPF do réu no processo?",
        "qual o CNPJ da contratada no contrato?",
        "responda o e-mail da Clínica Bem Viver",
        "traduza o e-mail do Teodoro",
        "qual o endereço do imóvel?",
        "como conecto meu e-mail?",
        "qual o valor do contrato da Cooperativa?",
        "cadastre o cliente João, CPF 529.982.247-25",
        "qual a OAB do advogado da Transportes Rio Fresco?",
        "mostre o e-mail da Clínica Bem Viver",
    ]
    viraram = [(f, r.modo) for f in nao for r in [consulta_cadastro.ler(f, cadastros=fichas, preferencias=prefs)] if r]
    checar(not viraram, "papel no documento, e-mail a responder e pedido de cadastrar não são consulta", viraram)


def test_fatos() -> None:
    print("\nconsulta de cadastro: sem ficha, os fatos já conferidos dos documentos")
    import base as base_mod
    from inteligencia import portas
    from inteligencia.catalogo import Catalogo
    from inteligencia.guarda import Biblioteca

    cpf = _cpf("987654321")
    texto = ("[pagina 1]\nCONTRATO DE PRESTAÇÃO DE SERVIÇOS\n\n[pagina 2]\n"
             f"CONTRATANTE: MARIA APARECIDA SOUZA, brasileira, casada, CPF {cpf}, residente em Goiânia.\n"
             "As partes assinam o presente.\n")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        pasta = Path(tmp)
        bd = base_mod.Base(pasta / "teste.db")
        bd.migrar()
        biblioteca = Biblioteca(pasta / "conhecimento", bd)
        arquivo = pasta / "Contrato Maria.txt"
        arquivo.write_text(texto, encoding="utf-8")
        portas.analisar_documento(biblioteca, Catalogo.carregar(), arquivo, texto=texto, paginas=2,
                                  sha1="sha-maria", titulo="Contrato Maria.txt")

        def fatos(nome, campo):
            return consulta_cadastro.fatos_dos_documentos(bd, biblioteca, nome, campo)

        comeco = time.perf_counter()
        r = consulta_cadastro.ler("qual o CPF da Maria Aparecida Souza?", cadastros=[], fatos=fatos)
        ms = (time.perf_counter() - comeco) * 1000
        checar(r and r.modo == "achado" and cpf in r.texto and "Contrato Maria.txt" in r.texto
               and "página 2" in r.texto, "o CPF sai do fato conferido, com o documento e a página", r and r.texto)
        checar(ms < 200, f"em menos de 200 ms ({ms:.0f} ms)")
        r = consulta_cadastro.ler("qual o CPF da Maria?", cadastros=[], fatos=fatos)
        checar(r and r.modo == "achado" and cpf in r.texto, "o primeiro nome basta quando só uma pessoa casa", r and r.texto)
        r = consulta_cadastro.ler("qual o CPF de Joana Prado?", cadastros=[], fatos=fatos)
        checar(r is None or r.modo == "nada", "quem não está nos fatos não vira o CPF de outra pessoa", r and r.texto)
        bd.fechar()


# ---------------------------------------------------------- 3. a API


def test_api() -> None:
    print("\npela API: molde em menos de 200 ms, sem modelo e sem ler o acervo")
    from test_gravacoes import Cliente, _porta_livre, _subir_servidor

    import api
    import juizo
    import llama_client

    porta = _porta_livre()
    _subir_servidor(porta)
    c = Cliente(porta)
    chamadas: list = []
    buscas: list = []
    original_chat, original_letras = llama_client.LlamaClient._chat, juizo.Juiz._letras
    original_busca = api.estado.searcher.search
    llama_client.LlamaClient._chat = lambda self, *a, **k: chamadas.append("chat") or (_ for _ in ()).throw(_NaoChame())
    juizo.Juiz._letras = lambda self, *a, **k: chamadas.append("juiz") or None
    conversa_antes = dict(api.estado.prefs.dados.get("conversa") or {})
    pessoa_antes = dict(api.estado.prefs.dados.get("pessoa") or {})
    api.estado.prefs.dados["conversa"] = {**conversa_antes, "roteamento": True}
    api.estado.prefs.dados["pessoa"] = {**pessoa_antes, **TITULAR}
    criados_cad: list[int] = []
    criados: list[str] = []
    try:
        for f in FICHAS:
            criados_cad.append(api.estado.cadastros.salvar(f))
        api.estado.searcher.search = lambda *a, **k: buscas.append(a) or original_busca(*a, **k)

        def perguntar(frase: str, **extra):
            st, t = c.pedir("POST", "/api/trabalhos", {"pedido": frase})
            criados.append(t["id"])
            comeco = time.perf_counter()
            eventos = c.conversar(f"/api/trabalhos/{t['id']}/perguntar", {"pergunta": frase, **extra})
            ms = (time.perf_counter() - comeco) * 1000
            texto = "".join(d.get("t", "") for tipo, d in eventos if tipo == "token")
            p = next((d for tipo, d in eventos if tipo == "proposta"), {})
            return texto, p, ms, t["id"]

        perguntar("qual o CPF de Teodoro Quintanilha Braga?")  # aquece (a primeira carrega o que for preguiçoso)
        tempos, errados = [], []
        for frase, valor, fonte in CONSULTAS[:10]:
            texto, p, ms, _ = perguntar(frase)
            tempos.append(round(ms))
            if p.get("tipo") != "consulta_cadastro" or valor not in texto or ms >= 200:
                errados.append((frase, p.get("tipo"), texto, round(ms)))
        checar(not errados, f"10 consultas de cadastro por molde, cada uma em menos de 200 ms (máx. {max(tempos)} ms)",
               errados)
        checar(not chamadas, "nenhuma chamou o modelo", chamadas)
        checar(not buscas, "nenhuma procurou nos documentos", len(buscas))

        texto, p, ms, _ = perguntar("qual o CPF do Teodoro?")
        checar(p.get("modo") == "escolher" and len(p.get("opcoes") or []) == 2, "ambíguo: o cartão com a lista", p)
        texto, p, ms, id_ = perguntar("qual o CPF do cliente Fulano Beltrano?")
        checar(p.get("modo") == "nada" and p.get("oferta") and not buscas and not chamadas,
               "inexistente: a oferta, sem leitura automática", (p, len(buscas), chamadas))
        st, trabalho = c.pedir("GET", f"/api/trabalhos/{id_}")
        etapas = [e["titulo"] for e in trabalho.get("etapas", [])]
        checar("Procurar nos documentos" not in etapas, "nenhuma etapa de procurar nos documentos", etapas)

        # A oferta refaz a pergunta pelos documentos: o cartão "onde eu
        # procuro?" (sem anexo) prova que ela foi para lá, sem modelo.
        eventos = c.conversar(f"/api/trabalhos/{id_}/perguntar",
                              {"pergunta": "qual o CPF do cliente Fulano Beltrano?", "retomar": True,
                               "documentos": True, "sem_anexo": True})
        p = next((d for tipo, d in eventos if tipo == "proposta"), {})
        checar(p.get("tipo") == "escopo", "a oferta aceita vai para os documentos", p.get("tipo"))
        st, trabalho = c.pedir("GET", f"/api/trabalhos/{id_}")
        guardados = [(m.get("proposta") or {}).get("tipo") for m in trabalho["mensagens"] if m["autor"] == "paulus"]
        checar(guardados == ["escopo"], "o Retomar troca o cartão da consulta", guardados)

        print("\npela API: sobre o programa, sem modelo")
        for frase, destino in (("Pra que serve a busca no DJE?", "publicacoes"),
                               ("como funciona o acesso de fora?", "acesso"),
                               ("abra a biblioteca", "habilidades")):
            texto, p, ms, _ = perguntar(frase)
            checar(p.get("tipo") == "programa" and p["campos"]["destino"] == destino and texto,
                   f"“{frase}” → {destino}", (p.get("tipo"), (p.get("campos") or {}).get("destino"), texto[:80]))
        checar(not chamadas, "sem modelo nem juiz", chamadas)

        print("\npela API: a chave desligada")
        api.estado.prefs.dados["conversa"] = {**conversa_antes, "roteamento": False}
        texto, p, ms, _ = perguntar("qual o CPF do cliente Teodoro Andrade?", sem_anexo=True)
        checar(p.get("tipo") == "escopo", "a consulta segue o caminho de antes (os documentos)", p.get("tipo"))
        texto, p, ms, _ = perguntar("Pra que serve a busca no DJE?", sem_anexo=True)
        checar(p.get("tipo") == "escopo", "a pergunta do DJE também", p.get("tipo"))
    finally:
        llama_client.LlamaClient._chat = original_chat
        juizo.Juiz._letras = original_letras
        api.estado.searcher.search = original_busca
        api.estado.prefs.dados["conversa"] = conversa_antes
        api.estado.prefs.dados["pessoa"] = pessoa_antes
        for id_ in criados_cad:
            api.estado.cadastros.apagar(id_)
        for id_ in criados:
            c.pedir("DELETE", f"/api/trabalhos/{id_}")


# ------------------------------------------- 4. o banco de provas


def test_banco_de_provas() -> None:
    print("\nbanco de provas: as perguntas de documento continuam nos documentos")
    antes = os.environ.get("PAULUS_DADOS")
    import roteiro  # define PAULUS_DADOS ao ser importado; devolvido abaixo

    if antes is None:
        os.environ.pop("PAULUS_DADOS", None)
    else:
        os.environ["PAULUS_DADOS"] = antes

    # Os cadastros e o titular da demonstração (tools/demo/criar_demo.py).
    import criar_demo

    fichas = [
        {"id": 1, "tipo": "cliente", "nome": "Cooperativa Agrícola Vale Verde", "documento": criar_demo.CNPJ_COOPERATIVA},
        {"id": 2, "tipo": "cliente", "nome": "Clínica Bem Viver Ltda.", "documento": criar_demo.CNPJ_CLINICA},
        {"id": 3, "tipo": "cliente", "nome": "João Batista Ferreira", "documento": criar_demo.CPF_JOAO},
        {"id": 4, "tipo": "colaborador", "nome": "Lívia Santos"},
        {"id": 5, "tipo": "despesa", "nome": "Aluguel do escritório"},
    ]
    prefs = {"pessoa": {"nome": criar_demo.ADVOGADA, "oab": criar_demo.OAB}, "escritorio": {"nome": criar_demo.ESCRITORIO}}
    todas = roteiro.BASICO + roteiro.DIFICIL + roteiro.MATERIAL
    docs = [p["pergunta"] for p in todas if p["caminho"] == "documentos"]
    prog = [p["pergunta"] for p in todas if p["caminho"] == "programa"]

    def rota(frase: str, ampliado: bool) -> str:
        lido = intencao.ler(frase, cadastros=[f["nome"] for f in fichas])
        if lido.tipo != "documentos":
            return lido.tipo
        if ampliado and consulta_cadastro.ler(frase, cadastros=fichas, preferencias=prefs,
                                              fatos=lambda n, c: []) is not None:
            return "cadastro"
        lista, sinais = programa.candidatos(frase, programa.mapa_para(ampliado), ampliado=ampliado)
        decidido = programa._por_regra(lista, sinais)
        if decidido:
            return "programa:" + decidido.destino
        juiz = any(c.forte or (c.tipo == "como" and c.pontos >= 1.0) for c in lista)
        return "juiz" if juiz else "documentos"

    mudou = [(f, rota(f, False), rota(f, True)) for f in docs if rota(f, True) != rota(f, False)]
    checar(not mudou, f"as {len(docs)} de documento seguem pelo mesmo caminho de antes", mudou)
    fora = [(f, rota(f, True)) for f in docs if rota(f, True) not in ("documentos", "juiz")]
    checar(not fora, "nenhuma virou programa nem cadastro", fora)
    mudou = [(f, rota(f, False), rota(f, True)) for f in prog if rota(f, True) != rota(f, False)]
    checar(not mudou, f"as {len(prog)} do programa continuam com a mesma resposta", mudou)


def test_regressoes_com_a_chave() -> None:
    print("\ncom a chave: as garantias de test_programa e da regressão continuam")
    import test_programa as tp
    from test_inteligencia_regressao import PERGUNTAS

    errados = []
    for frase, tipo, destino in tp.POSITIVOS:
        espiao = tp._Espiao()
        l = programa.ler(frase, dados=tp._Dados(), juiz=espiao, ampliado=True)
        if not (l and l.tipo == tipo and l.destino == destino and not espiao.chamadas):
            errados.append((frase, l and (l.tipo, l.destino)))
    checar(not errados, f"as {len(tp.POSITIVOS)} do programa, com a mesma resposta", errados)
    viraram = [f for f in tp.NEGATIVOS if programa.ler(f, dados=tp._Dados(), ampliado=True)]
    checar(not viraram, f"as {len(tp.NEGATIVOS)} de documento ficam nos documentos", viraram)
    desviadas, julgadas = [], []
    for item in PERGUNTAS:
        espiao = tp._Espiao(0.99)
        if programa.ler(item[0], dados=tp._Dados(), juiz=espiao, ampliado=True):
            desviadas.append(item[0])
        julgadas += espiao.chamadas
        if consulta_cadastro.ler(item[0], cadastros=_fichas_com_id(), fatos=lambda n, c: []):
            desviadas.append("cadastro: " + item[0])
    checar(not desviadas and not julgadas,
           f"as {len(PERGUNTAS)} da regressão da inteligência não saem dos documentos nem chamam o modelo",
           (desviadas, julgadas))


def main() -> int:
    print("=" * 55)
    print("  C4 - roteamento: programa e cadastros")
    print("=" * 55)
    test_programa()
    test_consulta_modulo()
    test_fatos()
    test_banco_de_provas()
    test_regressoes_com_a_chave()
    test_api()
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
