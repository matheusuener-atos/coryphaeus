"""
Testes do registro de habilidades.

Cobrem duas coisas: se os modulos reais da pasta `habilidades/` estao
consistentes, e se o carregador aguenta arquivo quebrado sem derrubar o
programa - que e a promessa toda da modularizacao.

    python tests/test_habilidades.py
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import registro  # noqa: E402
from habilidade_base import (  # noqa: E402
    COM_PROBLEMA,
    EM_BREVE,
    GRUPOS,
    PRECISA_ASSISTENTE,
    PRECISA_DOCUMENTOS,
    PRONTA,
    ROTULOS_PRECISA,
    Contexto,
    Ponte,
)

PASTA = RAIZ / "habilidades"

# Acoes que a interface sabe abrir. Habilidade pronta apontando para outra
# coisa vira botao "Usar" que nao faz nada.
ACOES_CONHECIDAS = {"conversa", "busca", "anexar", "organizacao"}

_falhas: list[str] = []


def checar(condicao: bool, descricao: str) -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        _falhas.append(descricao)


def _escrever(pasta: Path, nome: str, conteudo: str) -> None:
    (pasta / nome).write_text(conteudo, encoding="utf-8")


# ------------------------------------------------------------ modulos reais


def test_modulos_do_projeto() -> None:
    print("\nmodulos em habilidades/")
    r = registro.carregar(PASTA)

    checar(bool(r.habilidades), "a pasta tem habilidades")
    checar(not r.problemas, f"nenhum modulo com problema (achou {len(r.problemas)})")

    ids = [h.id for h in r.habilidades]
    checar(len(ids) == len(set(ids)), "nenhum id repetido")
    checar(all(h.grupo in GRUPOS for h in r.habilidades), "todo grupo existe em GRUPOS")
    checar(all(h.nome and h.resumo for h in r.habilidades), "toda habilidade tem nome e resumo")
    checar(all(h.arquivo for h in r.habilidades), "toda habilidade sabe de que arquivo veio")

    prontas = [h for h in r.habilidades if h.estado == PRONTA]
    checar(bool(prontas), "existe habilidade pronta")
    checar(all(h.executavel for h in prontas), "toda habilidade pronta tem executar()")
    checar(all(h.acao in ACOES_CONHECIDAS for h in prontas), "acao conhecida pela interface")
    checar(all(h.demora for h in prontas), "habilidade pronta declara quanto demora")

    futuras = [h for h in r.habilidades if h.estado == EM_BREVE]
    checar(bool(futuras), "o catalogo admite o que ainda nao existe")
    checar(all(not h.executavel for h in futuras), "habilidade futura nunca e executavel")
    checar(all(not h.acao for h in futuras), "habilidade futura nao oferece acao")

    checar(
        all(p in ROTULOS_PRECISA for h in r.habilidades for p in h.precisa),
        "todo requisito tem rotulo em portugues",
    )


def test_disponibilidade() -> None:
    print("\ndisponibilidade conforme o estado da maquina")
    r = registro.carregar(PASTA)

    tudo = [h for g in r.por_grupo({PRECISA_DOCUMENTOS: True, PRECISA_ASSISTENTE: True})
            for h in g["habilidades"]]
    perguntar = next(h for h in tudo if h["id"] == "perguntar")
    checar(perguntar["utilizavel"], "com documento e assistente, perguntar e utilizavel")
    checar(not perguntar["faltando"], "nada faltando quando tudo esta disponivel")

    sem_docs = [h for g in r.por_grupo({PRECISA_DOCUMENTOS: False, PRECISA_ASSISTENTE: True})
                for h in g["habilidades"]]
    p2 = next(h for h in sem_docs if h["id"] == "perguntar")
    checar(not p2["utilizavel"], "sem documento aberto, perguntar nao e utilizavel")
    checar("documentos abertos" in p2["faltando"], "diz em portugues o que falta")

    organizar = next(h for h in sem_docs if h["id"] == "organizar")
    checar(organizar["utilizavel"], "organizar nao depende de documento ja aberto")

    sem_nada = [h for g in r.por_grupo({}) for h in g["habilidades"]]
    checar(
        all(not h["utilizavel"] for h in sem_nada if h["precisa"]),
        "sem informacao de disponibilidade, nada que exige requisito e oferecido",
    )

    c = r.contagem()
    checar(c["total"] == len(r.habilidades), "contagem total confere")
    checar(c["prontas"] < c["total"], "ha habilidade nao entregue - o catalogo nao mente")


# ------------------------------------------------------- carregador robusto


def test_arquivo_quebrado_nao_derruba() -> None:
    """
    A promessa da modularizacao: mexer num modulo nao pode quebrar o programa.
    Cada forma de erro vira uma entrada marcada, e o resto continua de pe.
    """
    print("\ncarregador aguenta arquivo quebrado")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)

        _escrever(pasta, "boa.py", (
            "from habilidade_base import Contexto, Habilidade\n"
            "HABILIDADE = Habilidade(id='boa', nome='Boa', resumo='r', grupo='Documentos',\n"
            "                        acao='busca', demora='rapido')\n"
            "def executar(ctx: Contexto):\n"
            "    return {'ok': True}\n"
        ))
        _escrever(pasta, "sintaxe.py", "isto nao e python (((\n")
        _escrever(pasta, "sem_declaracao.py", "X = 1\n")
        _escrever(pasta, "estoura.py", "raise RuntimeError('estouro no import')\n")
        _escrever(pasta, "grupo_ruim.py", (
            "from habilidade_base import Habilidade\n"
            "HABILIDADE = Habilidade(id='g', nome='G', resumo='r', grupo='Inventado')\n"
        ))
        _escrever(pasta, "sem_executar.py", (
            "from habilidade_base import Habilidade\n"
            "HABILIDADE = Habilidade(id='s', nome='S', resumo='r', grupo='Documentos')\n"
        ))
        _escrever(pasta, "_ajudante.py", "NAO_E_HABILIDADE = True\n")

        r = registro.carregar(pasta)

        boa = r.obter("boa")
        checar(boa is not None and boa.executavel, "a habilidade boa carregou apesar das quebradas")
        checar(boa.executar(Contexto()) == {"ok": True}, "e roda normalmente")

        problemas = {Path(h.arquivo).name: h.problema for h in r.problemas}
        checar("sintaxe.py" in problemas, "erro de sintaxe vira problema, nao exception")
        checar("sem_declaracao.py" in problemas, "arquivo sem HABILIDADE vira problema")
        checar("estoura.py" in problemas, "erro no import vira problema")
        checar("grupo_ruim.py" in problemas, "grupo inexistente vira problema")
        checar("sem_executar.py" in problemas, "pronta sem executar() vira problema")
        checar(all(problemas.values()), "todo problema tem mensagem explicando")
        checar(
            not any("ajudante" in h.arquivo for h in r.habilidades),
            "arquivo com _ no inicio e ignorado, nao vira habilidade",
        )
        checar(r.contagem()["com_problema"] == 5, "conta os cinco quebrados")

        grupos = [g["grupo"] for g in r.por_grupo({})]
        checar("Com problema" in grupos, "quebradas aparecem num grupo proprio na tela")


def test_id_repetido() -> None:
    print("\ndois modulos com o mesmo id")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        corpo = (
            "from habilidade_base import Contexto, Habilidade\n"
            "HABILIDADE = Habilidade(id='mesmo', nome='{nome}', resumo='r',\n"
            "                        grupo='Documentos', acao='busca', demora='rapido')\n"
            "def executar(ctx: Contexto):\n"
            "    return {{'de': '{nome}'}}\n"
        )
        _escrever(pasta, "a_primeira.py", corpo.format(nome="Primeira"))
        _escrever(pasta, "b_segunda.py", corpo.format(nome="Segunda"))

        r = registro.carregar(pasta)
        checar(len(r.habilidades) == 2, "as duas entram na lista")
        checar(len(r.problemas) == 1, "a segunda e marcada como problema")
        checar(
            "já é usado" in r.problemas[0].problema,
            "o conflito e explicado em vez de resolvido em silencio",
        )
        checar(r.obter("mesmo").nome == "Primeira", "a primeira continua utilizavel")


def test_pasta_ausente() -> None:
    print("\npasta de habilidades ausente")
    r = registro.carregar(Path("pasta/que/nao/existe"))
    checar(r.habilidades == [], "nao quebra, so devolve lista vazia")
    checar(r.contagem()["total"] == 0, "contagem zerada")


# -------------------------------------------------------------------- ponte


def test_ponte() -> None:
    print("\nponte de callback para iterador")

    def trabalho(empurrar):
        for i in range(5):
            empurrar(i)
        return "terminou"

    ponte = Ponte(trabalho)
    recebidos = list(ponte)
    checar(recebidos == [0, 1, 2, 3, 4], "entrega os avisos na ordem")
    checar(ponte.resultado == "terminou", "guarda o valor de retorno")

    def estoura(empurrar):
        empurrar("antes")
        raise ValueError("falhou no meio")

    ponte2 = Ponte(estoura)
    itens, erro = [], None
    try:
        for item in ponte2:
            itens.append(item)
    except ValueError as exc:
        erro = exc
    checar(itens == ["antes"], "entrega o que veio antes do erro")
    checar(erro is not None, "o erro chega em quem consome, nao some na thread")

    ponte3 = Ponte(lambda empurrar: "sem avisos")
    naoconsumida = True
    try:
        _ = ponte3.resultado
        naoconsumida = False
    except RuntimeError:
        pass
    checar(naoconsumida, "pedir resultado antes de consumir e erro explicito")

    # O botao de parar: no silencio longo em que o modelo le e nao emite nada,
    # quem consome a ponte tem de largar sem esperar a thread acabar.
    import threading
    import time

    sinal = threading.Event()

    def le_devagar(empurrar):
        empurrar("comecou")
        time.sleep(5)
        empurrar("tarde demais")

    ponte4 = Ponte(le_devagar, parar=sinal.is_set)
    threading.Timer(0.3, sinal.set).start()
    comeco = time.time()
    itens = list(ponte4)
    checar(itens == ["comecou"] and time.time() - comeco < 1.5,
           "com parar, a ponte larga a espera em menos de um segundo e meio")


# -------------------------------------------------------------- parar


def test_parar_resposta() -> None:
    """
    O botao de parar pela API, de ponta a ponta: a resposta que esta sendo
    escrita para, o que ja saiu fica guardado como interrompido, e a conversa
    volta como parada. Sem Ollama: a habilidade de perguntar e trocada por
    uma que escreve devagar e obedece ao `ctx.parar`, que e o contrato real.
    """
    print("\nparar a resposta pela caixa de pedido")
    import threading
    import time

    import requests
    import api

    habilidade = api.estado.registro.obter("perguntar")
    guardado = (habilidade.executar, habilidade.estado)

    def devagar(ctx, pergunta="", top=6, apenas=None):
        yield "fontes", {"consultados": [], "ignorados": [], "total_contratos": 0, "trechos": []}
        yield "lendo", {"caracteres": 10}

        def escreve(empurrar):
            empurrar(("escrevendo", {"lendo_segundos": 0}))
            for i in range(400):
                if ctx.parar and ctx.parar():
                    return
                empurrar(("token", {"t": f"palavra{i} "}))
                time.sleep(0.02)

        for item in Ponte(escreve, parar=ctx.parar):
            yield item
        yield "fim", {}

    habilidade.executar, habilidade.estado = devagar, "pronta"
    # Servidor de verdade, e nao o TestClient: o TestClient junta a resposta
    # inteira antes de entregar a primeira linha, e o parar so chegaria
    # depois do fim - o teste mediria o cliente de teste, nao o programa.
    from test_tela import _porta_livre, _subir_servidor

    porta = _porta_livre()
    servidor = _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    criado = None
    try:
        criado = requests.post(base + "/api/trabalhos", json={"pedido": "teste do parar"}).json()
        eventos: list[str] = []
        comeco = time.time()
        with requests.post(f"{base}/api/trabalhos/{criado['id']}/perguntar",
                           json={"pergunta": "qual o prazo do contrato?"}, stream=True) as r:
            pediu = False
            for linha in r.iter_lines(decode_unicode=True):
                if linha.startswith("event: "):
                    eventos.append(linha[7:])
                    if linha == "event: token" and eventos.count("token") == 5 and not pediu:
                        pediu = True
                        threading.Thread(target=lambda: requests.post(f"{base}/api/trabalhos/{criado['id']}/parar")).start()
        demorou = time.time() - comeco
        print("         eventos: " + ", ".join(dict.fromkeys(eventos)))
        checar("parado" in eventos and "fim" not in eventos, "a resposta termina com 'parado', e nao com 'fim'")
        checar(demorou < 4, f"e para logo (escreveria 8 s; parou em {demorou:.1f} s)")
        depois = requests.get(f"{base}/api/trabalhos/{criado['id']}").json()
        ultima = depois["mensagens"][-1]
        checar(depois["estado"] == "pausado", "a conversa volta como parada")
        checar(ultima["autor"] == "paulus" and ultima["interrompida"] and ultima["texto"].startswith("palavra0"),
               "o que ja tinha sido escrito fica guardado, marcado como interrompido")
        checar(criado["id"] not in api.estado.respondendo, "o sinal da resposta e solto no fim")

        # Retomar: a mesma pergunta de novo nao se repete no historico, e a
        # resposta que tinha parado no meio da lugar a nova.
        with requests.post(f"{base}/api/trabalhos/{criado['id']}/perguntar",
                           json={"pergunta": "qual o prazo do contrato?", "retomar": True}, stream=True) as r:
            pediu = False
            for linha in r.iter_lines(decode_unicode=True):
                if linha == "event: token" and not pediu:
                    pediu = True
                    threading.Thread(target=lambda: requests.post(f"{base}/api/trabalhos/{criado['id']}/parar")).start()
        retomada = requests.get(f"{base}/api/trabalhos/{criado['id']}").json()["mensagens"]
        checar([m["autor"] for m in retomada] == ["pessoa", "paulus"],
               "retomar nao repete a pergunta e troca a resposta parada pela nova")

        # Conversa presa em "trabalhando" de uma sessao que ja acabou.
        preso = api.estado.trabalhos.obter(criado["id"])
        preso.estado = "executando"
        r = requests.post(f"{base}/api/trabalhos/{criado['id']}/parar").json()
        checar(r["parando"] is False and r["estado"] == "pausado",
               "sem resposta andando, parar destrava a conversa presa")
    finally:
        habilidade.executar, habilidade.estado = guardado
        if criado:
            # Apagar manda para a lixeira; o teste nao deixa rastro la.
            lixo = requests.delete(f"{base}/api/trabalhos/{criado['id']}").json().get("lixeira")
            if lixo:
                api.estado.lixeira.tirar(lixo)
        servidor.should_exit = True


# ------------------------------------------------------------- destinos


def test_destinos() -> None:
    """
    O menu do manual do sistema. Destino pronto tem que apontar para algo que a
    interface sabe abrir; destino ainda nao construido tem que dizer o que
    falta, senao vira botao morto sem explicacao.
    """
    print("\ndestinos do menu")
    import destinos

    # Lido do proprio roteador da interface, nao de uma lista a parte: uma
    # lista escrita aqui so provaria que alguem lembrou de atualiza-la, e o
    # que precisa ser verdade e que a tela realmente sabe abrir o destino.
    # A pagina virou index.html + css + js; o roteador mora no js dos destinos.
    # Le-se a pasta inteira para o teste nao quebrar de novo se ele mudar de
    # arquivo - o que importa e que ALGUMA parte da interface saiba abrir.
    pasta = RAIZ / "frontend"
    codigo = "\n".join(
        a.read_text(encoding="utf-8")
        for a in [pasta / "index.html"] + sorted((pasta / "js").glob("*.js"))
    )
    ABRE_CONHECIDO = set(re.findall(r'd\.abre === "([a-z]+)"', codigo))
    checar(bool(ABRE_CONHECIDO), f"o roteador da interface foi lido ({len(ABRE_CONHECIDO)} destinos)")

    ids = [d.id for d in destinos.DESTINOS]
    checar(len(ids) == len(set(ids)), "nenhum id de destino repetido")
    checar(len(destinos.DESTINOS) == 20, f"20 destinos, como o manual (achou {len(ids)})")
    checar(
        all(d.grupo in destinos.GRUPOS for d in destinos.DESTINOS),
        "todo destino esta num dos quatro grupos",
    )
    checar(all(d.nome and d.resolve for d in destinos.DESTINOS), "todo destino diz o que resolve")

    prontos = [d for d in destinos.DESTINOS if d.pronta]
    checar(bool(prontos), "existe destino com motor")
    checar(
        all(d.abre in ABRE_CONHECIDO for d in prontos),
        "destino pronto abre algo que a interface conhece",
    )

    # Nao se exige que haja tela por construir - houve durante todo o caminho,
    # e deixou de haver na Etapa 7. O que tem que valer sempre e a regra: ou a
    # tela abre algo, ou ela diz o que falta. Nunca as duas, nunca nenhuma.
    adiante = [d for d in destinos.DESTINOS if not d.pronta]
    checar(all(not d.abre for d in adiante), "destino nao construido nao finge ter tela")
    checar(all(d.precisa for d in adiante), "destino nao construido diz o que falta")
    checar(all(not d.precisa for d in prontos),
           "destino pronto nao fica pedindo o que ja tem")

    c = destinos.contagem()
    checar(c["prontas"] == len(prontos) and c["prontas"] <= c["total"],
           f"a contagem confere com a lista ({c['prontas']} de {c['total']})")
    checar(destinos.obter("conversa") is not None, "acha destino por id")
    checar(destinos.obter("nao-existe") is None, "id desconhecido devolve None")


def main() -> int:
    print("=" * 55)
    print("  PAULUS - testes do registro de habilidades")
    print("=" * 55)

    test_modulos_do_projeto()
    test_disponibilidade()
    test_arquivo_quebrado_nao_derruba()
    test_id_repetido()
    test_pasta_ausente()
    test_ponte()
    test_parar_resposta()
    test_destinos()

    total = len(registro.carregar(PASTA).habilidades)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print(f"  todos os testes passaram ({total} habilidades na pasta)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
