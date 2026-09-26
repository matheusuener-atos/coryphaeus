"""
Testes da caixa de entrada refeita e do Escrever.

  - marcar como lida e arquivar em lote: so UID numerico chega ao IMAP,
    e arquivar nunca apaga sem antes copiar
  - o resumo da caixa por regra diz so o que esta nos cabecalhos
  - o resumo do modelo roda em segundo plano, um por vez, com cache pela
    chave das mensagens - abrir uma mensagem nao custa outro minuto
  - o "Pedir aqui" do Escrever chama o modelo com o pedido certo e devolve
    so o corpo, sem assinatura inventada
  - as rotas novas respondem sem o modelo de verdade (e com ele desligado)

IMAP e modelo sao dubles: nada toca a rede.

    python tests/test_email_caixa.py
"""

from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import correio  # noqa: E402
import correio_contas  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


# ------------------------------------------------------------- dubles


class _IMAP:
    """Anota os comandos; a pasta de arquivo existe quando `tem_arquivo`."""

    comandos: list[tuple] = []
    tem_arquivo = True
    recusar_copia: set[str] = set()

    def __init__(self, host, porta, timeout=None):
        pass

    def login(self, usuario, senha):
        return ("OK", [b""])

    def select(self, pasta, readonly=False):
        _IMAP.comandos.append(("SELECT", pasta, readonly))
        return ("OK", [b"3"])

    def uid(self, comando, *args):
        _IMAP.comandos.append((comando,) + args)
        if comando == "COPY":
            if not _IMAP.tem_arquivo or args[0] in _IMAP.recusar_copia:
                return ("NO", [b"sem pasta"])
            return ("OK", [b""]) if args[1] == '"Archive"' else ("NO", [b""])
        return ("OK", [b""])

    def expunge(self):
        _IMAP.comandos.append(("EXPUNGE",))
        return ("OK", [b""])

    def logout(self):
        pass


class _Modelo:
    """Responde sem pensar; anota o que recebeu. `trava` segura a resposta."""

    def __init__(self, resposta: str = "Resposta.", trava: threading.Event | None = None):
        self.resposta = resposta
        self.chamadas: list[dict] = []
        self.trava = trava
        self.model = "duble"

    def ask(self, pergunta, contexto="", *, sistema="", **_):
        self.chamadas.append({"pergunta": pergunta, "contexto": contexto, "sistema": sistema})
        if self.trava:
            self.trava.wait(5)
        return self.resposta


def _conta():
    return correio_contas.Conta(id="c1", email="advogado@escritorio.adv.br",
                                imap_host="imap.escritorio.adv.br", imap_porta=993)


def _com_imap(fazer):
    original = correio.imaplib.IMAP4_SSL
    correio.imaplib.IMAP4_SSL = _IMAP
    _IMAP.comandos = []
    try:
        return fazer()
    finally:
        correio.imaplib.IMAP4_SSL = original
        _IMAP.tem_arquivo = True
        _IMAP.recusar_copia = set()


# ------------------------------------------------------------- lote


def test_uids_validos() -> None:
    print("\nso UID numerico chega ao servidor")
    limpos = correio._uids_validos(["101", " 102 ", "101", "1:*", "3 FLAGS", "", None, 7])
    checar(limpos == ["101", "102", "7"], f"filtra e tira repetidos ({limpos})")


def test_marcar_lidas() -> None:
    print("\nmarcar como lida em lote")
    n = _com_imap(lambda: correio.marcar_lidas(_conta(), "s", ["5", "9", "x"], True))
    checar(n == 2, f"conta so os validos ({n})")
    store = [c for c in _IMAP.comandos if c[0] == "STORE"]
    checar(store == [("STORE", "5,9", "+FLAGS", "(\\Seen)")], f"um STORE so, com +FLAGS ({store})")
    checar(("SELECT", "INBOX", False) in _IMAP.comandos, "abre a caixa para escrita (marca precisa)")

    _com_imap(lambda: correio.marcar_lidas(_conta(), "s", ["5"], False))
    store = [c for c in _IMAP.comandos if c[0] == "STORE"]
    checar(store == [("STORE", "5", "-FLAGS", "(\\Seen)")], "nao lida tira a marca")

    n = _com_imap(lambda: correio.marcar_lidas(_conta(), "s", ["1:*"], True))
    checar(n == 0 and not _IMAP.comandos, "sem UID valido nem conecta")


def test_arquivar_varias() -> None:
    print("\narquivar em lote")
    d = _com_imap(lambda: correio.arquivar_varias(_conta(), "s", ["11", "12", "13"]))
    checar(d == {"arquivadas": 3, "so_lidas": 0}, f"arquiva as tres ({d})")
    copias = [c for c in _IMAP.comandos if c[0] == "COPY" and c[2] == '"Archive"']
    checar(len(copias) == 3, "copia cada uma para o arquivo")
    apagar = [c for c in _IMAP.comandos if c[0] == "STORE" and c[2] == "+FLAGS" and c[3] == "(\\Deleted)"]
    checar(apagar == [("STORE", "11,12,13", "+FLAGS", "(\\Deleted)")], f"tira da caixa so as copiadas ({apagar})")
    ordem = [c[0] for c in _IMAP.comandos]
    checar(ordem.index("EXPUNGE") > max(i for i, c in enumerate(_IMAP.comandos) if c[0] == "COPY"),
           "so apaga depois de copiar")

    _IMAP.recusar_copia = {"12"}
    d = _com_imap(lambda: (setattr(_IMAP, "recusar_copia", {"12"}), correio.arquivar_varias(_conta(), "s", ["11", "12"]))[1])
    apagar = [c for c in _IMAP.comandos if c[0] == "STORE" and c[3] == "(\\Deleted)"]
    checar(d == {"arquivadas": 1, "so_lidas": 1} and apagar == [("STORE", "11", "+FLAGS", "(\\Deleted)")],
           f"a que nao copiou fica na caixa ({d}, {apagar})")

    d = _com_imap(lambda: (setattr(_IMAP, "tem_arquivo", False), correio.arquivar_varias(_conta(), "s", ["11", "12"]))[1])
    checar(d == {"arquivadas": 0, "so_lidas": 2}, f"sem pasta de arquivo, so marca lida ({d})")
    checar(not any(c[0] == "EXPUNGE" for c in _IMAP.comandos), "e nao apaga nada")


# ------------------------------------------------------------- resumo


_LISTA = [
    {"uid": "3", "de_nome": "Cartorio", "assunto": "Protocolo pronto", "lido": True, "respondido": False},
    {"uid": "2", "de_nome": "Fornecedor A", "assunto": "Prazo para renovar", "prazo": "2099-12-30", "lido": True, "respondido": False},
    {"uid": "1", "de_nome": "Cliente Exemplo", "de_cadastro": "Empresa Exemplo", "assunto": "Procuração", "lido": False, "tem_anexo": True},
    {"uid": "0", "de_nome": "Cliente Exemplo", "de_cadastro": "Empresa Exemplo", "assunto": "Re: contrato", "lido": True, "respondido": True},
]


def test_resumo_por_regra() -> None:
    print("\nresumo por regra")
    r = correio.resumo_por_regra(_LISTA)
    checar(r["total"] == 4, "conta todas")
    checar(r["pedem_resposta"] == 2, f"pedem resposta: nao lida ou com prazo, sem resposta ({r['pedem_resposta']})")
    checar(r["nao_lidas"] == 1 and r["com_anexo"] == 1 and r["de_clientes"] == 2, "nao lidas, anexos e clientes")
    checar(r["remetentes"][0] == {"nome": "Empresa Exemplo", "quantas": 2}, f"quem mais escreveu vem primeiro ({r['remetentes']})")
    checar([p["uid"] for p in r["prazos"]] == ["2"], "so prazo de mensagem sem resposta")
    checar(correio.resumo_por_regra([])["total"] == 0, "lista vazia nao quebra")


def test_resumo_do_modelo() -> None:
    print("\nresumo do modelo em segundo plano")
    modelo = _Modelo("Resumo: A Empresa Exemplo mandou a procuração, ainda não lida.")
    texto = correio.resumir_caixa(modelo, _LISTA)
    checar(texto.startswith("A Empresa Exemplo"), f"tira o 'Resumo:' da frente ({texto!r})")
    contexto = modelo.chamadas[0]["contexto"]
    checar("Procuração" in contexto and "não lida" in contexto and "prazo 2099-12-30" in contexto,
           "o modelo recebe remetente, assunto e marcas")
    checar("corpo" not in contexto.lower(), "e nenhum corpo de mensagem")

    k1 = correio.chave_do_resumo("c1", _LISTA)
    lida = [dict(m, lido=True) for m in _LISTA]
    checar(correio.chave_do_resumo("c1", lida) == k1, "abrir uma mensagem nao muda a chave")
    checar(correio.chave_do_resumo("c1", [{"uid": "9"}] + _LISTA) != k1, "mensagem nova muda a chave")
    checar(correio.chave_do_resumo("c2", _LISTA) != k1, "outra conta, outra chave")

    trava = threading.Event()
    lento = _Modelo("Primeiro.", trava)
    resumos = correio.ResumosDaCaixa()
    e1 = resumos.pedir("k1", _LISTA, lento)
    checar(e1["estado"] == "resumindo", "responde na hora, sem esperar o modelo")
    checar(resumos.estado("k1")["estado"] == "resumindo", "e diz que esta resumindo")
    checar(resumos.pedir("k1", _LISTA, lento)["estado"] == "resumindo", "pedir de novo nao roda outra vez")
    e2 = resumos.pedir("k2", _LISTA, lento)
    checar(e2["estado"] == "na_fila", "um de cada vez: o segundo espera")
    trava.set()
    for t in list(resumos.threads):
        t.join(5)
    for t in list(resumos.threads):
        t.join(5)
    checar(resumos.estado("k1") .get("texto") == "Primeiro.", "o primeiro fica guardado")
    checar(resumos.estado("k2").get("estado") == "pronto", "e o da fila roda depois")
    checar(len(lento.chamadas) == 2, f"duas chaves, duas chamadas ({len(lento.chamadas)})")
    resumos.pedir("k1", _LISTA, lento)
    checar(len(lento.chamadas) == 2, "chave pronta vem do cache, sem chamar o modelo")

    class _Quebra(_Modelo):
        def ask(self, *a, **k):
            raise RuntimeError("Ollama caiu")

    resumos.pedir("k3", _LISTA, _Quebra())
    for t in list(resumos.threads):
        t.join(5)
    e3 = resumos.estado("k3")
    checar(e3["estado"] == "falhou" and "Ollama caiu" in e3["erro"], f"falha vira estado, nao excecao ({e3})")


# ------------------------------------------------------------- escrever


def test_reescrever() -> None:
    print("\nreescrever no Escrever")
    modelo = _Modelo("Assunto: Procuração\n\nPrezado, segue a procuração.\n--\nNome Inventado OAB/XX 123")
    texto = correio.reescrever_email(modelo, "formal", "Procuração", "oi, segue a procuracao")
    checar(texto == "Prezado, segue a procuração.", f"volta so o corpo, sem assunto nem assinatura ({texto!r})")
    chamada = modelo.chamadas[0]
    checar("tom mais formal" in chamada["pergunta"], "o atalho vira pedido com palavras exatas")
    checar("oi, segue a procuracao" in chamada["contexto"], "o modelo recebe o texto atual")
    checar(chamada["sistema"] == correio.SISTEMA_EMAIL, "com a instrucao de sistema do e-mail")

    try:
        correio.reescrever_email(modelo, "resumir", "x", "   ")
        checar(False, "resumir texto vazio avisa")
    except ValueError as exc:
        checar("escreva o texto" in str(exc), f"resumir texto vazio avisa ({exc})")

    livre = _Modelo("Bom dia, [NOME].")
    checar(correio.reescrever_email(livre, "escreva um convite para reunião", "", "") == "Bom dia, [NOME].",
           "pedido livre funciona mesmo sem texto")


# ------------------------------------------------------------- rotas


def test_rotas(tmp: Path) -> None:
    print("\nas rotas novas")
    import api
    from fastapi import HTTPException

    guardadas = (api.estado.contas, api.estado.client, api.check_ollama, api._resumos_da_caixa)
    try:
        api.estado.contas = correio_contas.Contas(tmp / "contas.json")
        conta = api.estado.contas.salvar_conta({"email": "advogado@escritorio.adv.br",
                                                "imap_host": "imap.x", "smtp_host": "smtp.x"}, "senha")
        api.estado.contas.lembrar(conta.id, "senha")

        d = _com_imap(lambda: api.email_marcar({"conta_id": conta.id, "uids": ["4", "5"], "lido": True}))
        checar(d["marcadas"] == 2 and d["uids"] == ["4", "5"], f"marcar responde o que marcou ({d})")
        try:
            api.email_marcar({"conta_id": conta.id, "uids": ["1:*"]})
            checar(False, "marcar sem UID valido e recusado")
        except HTTPException as exc:
            checar(exc.status_code == 400, "marcar sem UID valido e recusado")

        d = _com_imap(lambda: api.email_arquivar({"conta_id": conta.id, "uids": ["4", "5"]}))
        checar(d["arquivadas"] == 2 and d["aviso"] == "", f"arquivar em lote ({d})")
        d = _com_imap(lambda: api.email_arquivar({"conta_id": conta.id, "uid": "4"}))
        checar(d["arquivada"] is True, "arquivar uma continua como antes")

        # Modelo desligado: a regra responde, o modelo diz por que nao.
        api.check_ollama = lambda *_a, **_k: (False, "Ollama nao respondeu")
        api._resumos_da_caixa = correio.ResumosDaCaixa()
        d = api.email_caixa_resumo({"conta_id": conta.id, "mensagens": _LISTA})
        checar(d["regra"]["pedem_resposta"] == 2, "a regra responde com o modelo desligado")
        checar(d["modelo"] == {"estado": "indisponivel", "motivo": "Ollama nao respondeu"}, f"e o modelo diz por que nao ({d['modelo']})")
        try:
            api.email_reescrever({"pedido": "formal", "corpo": "oi"})
            checar(False, "reescrever com o modelo desligado da erro claro")
        except HTTPException as exc:
            checar(exc.status_code == 503 and "Ollama" in exc.detail, f"reescrever com o modelo desligado da erro claro ({exc.detail})")

        # Modelo ligado (duble).
        api.check_ollama = lambda *_a, **_k: (True, "ok")
        api.estado.client = _Modelo("A procuração pede resposta.")
        d = api.email_caixa_resumo({"conta_id": conta.id, "mensagens": _LISTA})
        checar(d["modelo"]["estado"] == "resumindo", "o resumo do modelo comeca em segundo plano")
        for t in list(api._resumos_da_caixa.threads):
            t.join(5)
        e = api.email_caixa_resumo_estado(d["chave"])
        checar(e["modelo"].get("texto") == "A procuração pede resposta.", f"e fica pronto pela chave ({e})")
        d2 = api.email_caixa_resumo({"conta_id": conta.id, "mensagens": [dict(m, lido=True) for m in _LISTA]})
        checar(d2["modelo"]["estado"] == "pronto" and d2["regra"]["nao_lidas"] == 0,
               "marcar lida nao refaz o modelo, mas a regra acompanha")
        checar(len(api.estado.client.chamadas) == 1, "uma chamada so ao modelo")
        vazio = api.email_caixa_resumo({"conta_id": conta.id, "mensagens": []})
        checar(vazio["modelo"]["estado"] == "nenhum", "caixa vazia nao chama o modelo")

        api.estado.client = _Modelo("Prezado, segue.")
        d = api.email_reescrever({"pedido": "formal", "assunto": "x", "corpo": "oi, segue"})
        checar(d["sugestao"] == "Prezado, segue.", "reescrever devolve a sugestao")
        try:
            api.email_reescrever({"pedido": "resumir", "corpo": ""})
            checar(False, "resumir sem texto e recusado")
        except HTTPException as exc:
            checar(exc.status_code == 400, "resumir sem texto e recusado")

        arquivo = tmp / "peticao.pdf"
        arquivo.write_bytes(b"x" * 2048)
        d = api.email_anexos_conferir({"caminhos": [str(arquivo), str(tmp / "sumiu.pdf")]})
        checar(d["anexos"][0]["existe"] and d["anexos"][0]["nome"] == "peticao.pdf", "confere nome do anexo")
        checar(not d["anexos"][1]["existe"], "e diz quando o arquivo nao existe")
        checar(d["limite_mb"] == 20, "e o limite por anexo")
    finally:
        api.estado.contas, api.estado.client, api.check_ollama, api._resumos_da_caixa = guardadas


def main() -> int:
    print("=" * 55)
    print("PAULUS - caixa de entrada e Escrever")
    print("=" * 55)
    test_uids_validos()
    test_marcar_lidas()
    test_arquivar_varias()
    test_resumo_por_regra()
    test_resumo_do_modelo()
    test_reescrever()
    with tempfile.TemporaryDirectory() as bruto:
        test_rotas(Path(bruto))

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
