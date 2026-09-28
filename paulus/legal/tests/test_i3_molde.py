"""
Portao da I3 - o nivel 0 por molde, sem modelo (src/inteligencia/molde.py).

  - as perguntas factuais (numero do processo, valor, tribunal, partes, data
    de assinatura, leis citadas) respondem sem chamar o cliente: o cliente
    de mentira falha se for chamado;
  - uma resposta do modelo com um digito trocado e rejeitada pela
    conferencia mecanica;
  - a resposta por molde nao entra na fila do modelo (R4): com a fila
    ocupada, ela sai na hora;
  - o nivel 0 responde em menos de 200 ms.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_i3_molde.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-i3-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "habilidades"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


PETICAO = """EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 2ª VARA CÍVEL DA COMARCA DE BELÉM - TJPA

Processo nº 0801234-50.2024.8.14.0301

MARIA DA SILVA, brasileira, vem propor AÇÃO DE COBRANÇA em face de JOSÉ PEREIRA, pelos fatos
a seguir.

DOS FATOS
A autora emprestou ao réu a quantia combinada, que não foi devolvida no prazo.

DO DIREITO
Aplica-se o art. 389 da Lei 10.406/2002 (Código Civil) e o art. 300 do CPC.

DOS PEDIDOS
Requer a condenação do réu ao pagamento do valor emprestado, com juros e correção.

Dá-se à causa o valor de R$ 15.000,00 (quinze mil reais).

Belém/PA, assinado em 10 de março de 2024.
"""


class Falha:
    """O cliente que nao pode ser chamado."""

    model = "falso:1b"
    num_ctx = 16384
    host = "http://127.0.0.1:9"

    def __init__(self) -> None:
        self.chamadas = 0

    def ask(self, *a, **k):
        self.chamadas += 1
        raise AssertionError("o modelo foi chamado")

    def digest(self, model=""):
        return ""


class Trocador:
    """O cliente que responde com um digito trocado."""

    model = "falso:1b"
    num_ctx = 16384
    host = "http://127.0.0.1:9"

    def __init__(self, resposta: str) -> None:
        self.resposta = resposta
        self.chamadas = 0

    def ask(self, *a, **k):
        self.chamadas += 1
        return self.resposta

    def digest(self, model=""):
        return ""


def test_moldes() -> None:
    print("\nos moldes, fato a fato")
    from inteligencia import molde
    from inteligencia.roteador import Fato, Intencao, Pacote

    def pacote(secao, chave, fatos, **extra):
        return Pacote(nivel=0, fatos=fatos, documentos=[fatos[0].documento], fallback=False,
                      intencao=Intencao(secao=secao, chave=chave, nivel=0), **extra)

    p = pacote("case", "case_number", [Fato(documento="p.pdf", valor="0801234-50.2024.8.14.0301", pagina=1)])
    checar(molde.montar(p, "qual o número do processo?") == "O número do processo é 0801234-50.2024.8.14.0301 (p. 1).",
           "número do processo, com a página", molde.montar(p, "qual o número do processo?"))
    p = pacote("amounts", "claim", [Fato(documento="p.pdf", rotulo="valor da causa", valor="R$ 15.000,00", pagina=2)])
    checar(molde.montar(p, "qual o valor da causa?") == "O valor da causa é R$ 15.000,00 (p. 2).", "valor da causa",
           molde.montar(p, "qual o valor da causa?"))
    p = pacote("amounts", "", [Fato(documento="c.docx", rotulo="aluguel", valor="R$ 6.200,00")])
    checar(molde.montar(p, "qual o valor da multa?") == "", "valor de outro tipo na pergunta: o molde nao responde")
    checar("6.200,00 (c.docx)" in molde.montar(p, "qual o valor?"), "sem página, o nome do documento",
           molde.montar(p, "qual o valor?"))
    dois = pacote("amounts", "", [Fato(documento="c.docx", valor="R$ 1,00"), Fato(documento="c.docx", valor="R$ 2,00")])
    checar(molde.montar(dois, "qual o valor?") == "", "dois valores: escolher seria sortear")
    p = pacote("jurisdiction", "court", [Fato(documento="p.pdf", valor="TJPA", pagina=1)])
    checar(molde.montar(p, "qual o tribunal?") == "O tribunal é TJPA (p. 1).", "tribunal")
    checar(molde.montar(p, "qual a vara?") == "", "a vara nao e o tribunal")
    partes = [Fato(documento="p.pdf", rotulo="autor", valor="MARIA DA SILVA", pagina=1),
              Fato(documento="p.pdf", rotulo="réu", valor="JOSÉ PEREIRA", pagina=1)]
    texto = molde.montar(pacote("parties", "", partes), "quais as partes?")
    checar("MARIA DA SILVA (p. 1)" in texto and "JOSÉ PEREIRA (p. 1)" in texto, "partes, as duas", texto)
    texto = molde.montar(pacote("parties", "", partes), "quem é o réu?")
    checar("JOSÉ PEREIRA" in texto and "MARIA" not in texto, "o papel perguntado, só ele", texto)
    p = pacote("dates", "signature", [Fato(documento="p.pdf", valor="2024-03-10", pagina=3)])
    checar(molde.montar(p, "quando foi assinado?") == "O documento foi assinado em 10/03/2024 (p. 3).", "data de assinatura",
           molde.montar(p, "quando foi assinado?"))
    leis = [Fato(documento="p.pdf", valor="Lei 10.406/2002, art. 389", pagina=2),
            Fato(documento="p.pdf", valor="CPC, art. 300", pagina=2)]
    texto = molde.montar(pacote("legal_references", "", leis), "quais leis são citadas?")
    checar("art. 389 (p. 2)" in texto and "art. 300 (p. 2)" in texto, "leis citadas, em lista", texto)

    print("\na conferência mecânica")
    fatos = [Fato(documento="p.pdf", rotulo="valor da causa", valor="R$ 15.000,00",
                  quote="Dá-se à causa o valor de R$ 15.000,00", pagina=2)]
    checar(not molde.conferir("O valor da causa é R$ 15.000,00, na página 2.", fatos), "o valor certo passa")
    checar(not molde.conferir("São quinze mil: R$ 15.000.", fatos), "15.000 e 15.000,00 são o mesmo número")
    checar(molde.conferir("O valor da causa é R$ 15.010,00.", fatos) == ["15010"], "um dígito trocado no valor é pego",
           molde.conferir("O valor da causa é R$ 15.010,00.", fatos))
    cnj = [Fato(documento="p.pdf", valor="0801234-50.2024.8.14.0301", pagina=1)]
    checar(molde.conferir("O processo é o 0801234-50.2024.8.14.0301.", cnj) == [], "o CNJ certo passa")
    checar(molde.conferir("O processo é o 0801234-05.2024.8.14.0301.", cnj) != [], "o CNJ com dígito trocado é pego")
    data = [Fato(documento="p.pdf", valor="2024-03-10", quote="assinado em 10 de março de 2024")]
    checar(not molde.conferir("Foi assinado em 10/03/2024.", data), "a data em outro formato passa")
    checar(molde.conferir("Foi assinado em 11/03/2024.", data) != [], "a data errada é pega")
    checar(not molde.conferir("A sala 402 é do locador.", [], "quem é o locador da sala 402?"),
           "número que veio da pergunta passa")


def test_na_conversa() -> None:
    print("\nna conversa, sem modelo e sem fila")
    from fastapi.testclient import TestClient

    import api
    from inteligencia import portas

    falha = Falha()
    api.estado.client = falha
    api.estado.cliente_para = lambda tarefa: falha
    api.estado.saber.ligada = False  # a análise em segundo plano não pode chamar o modelo de mentira
    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "peticao.txt").write_text(PETICAO, encoding="utf-8")
    api.estado.recarregar()
    doc = api.estado.searcher.documents[0]
    portas.analisar_documento(api.estado.saber.biblioteca, api.estado.catalogo, doc.path, texto=doc.text,
                              paginas=doc.pages, sha1=doc.sha1, titulo=doc.name)
    api.estado.saber.ligada = True

    c = TestClient(api.app, headers=api.cabecalho_local())

    def perguntar(texto: str) -> tuple[list[tuple[str, dict]], float]:
        id_ = c.post("/api/trabalhos", json={"pedido": "teste"}).json()["id"]
        comeco = time.time()
        r = c.post(f"/api/trabalhos/{id_}/perguntar",
                   json={"pergunta": texto, "apenas": [doc.name], "documentos": True})
        gasto = time.time() - comeco
        eventos = []
        for bloco in r.text.split("\n\n"):
            tipo = next((l[7:] for l in bloco.splitlines() if l.startswith("event: ")), "")
            corpo = "".join(l[6:] for l in bloco.splitlines() if l.startswith("data: "))
            if tipo:
                eventos.append((tipo, json.loads(corpo or "{}")))
        return eventos, gasto

    # A fila ocupada por outra pessoa: o molde não pode esperar por ela.
    outra = api.estado.fila_modelo.entrar("outra pessoa", rotulo="ocupando")
    try:
        casos = [
            ("qual o número do processo?", "0801234-50.2024.8.14.0301"),
            ("qual o valor da causa?", "15.000,00"),
            ("qual o tribunal?", "TJPA"),
            ("quando foi assinado?", "10/03/2024"),
            ("quais leis são citadas?", "300"),
        ]
        tempos = []
        habilidade = api.estado.registro.obter("perguntar")
        for pergunta, esperado in casos:
            # Sem molde, a pergunta esperaria a fila ocupada para sempre: o
            # teste falha aqui em vez de travar.
            if not api._sem_modelo(habilidade, pergunta, [doc.name]):
                checar(False, f"“{pergunta}” sai sem o modelo")
                continue
            eventos, gasto = perguntar(pergunta)
            texto = "".join(d.get("t", "") for t, d in eventos if t == "token")
            tempos.append(gasto)
            checar(esperado in texto and not any(t == "fila" for t, _ in eventos),
                   f"“{pergunta}” responde por molde, sem fila", (texto, [t for t, _ in eventos]))
        checar(falha.chamadas == 0, "o modelo não foi chamado nenhuma vez", falha.chamadas)
        tempos.sort()
        checar(tempos[len(tempos) // 2] < 0.2, f"nível 0 em menos de 200 ms (mediana {tempos[len(tempos) // 2] * 1000:.0f} ms)")
        eventos, _ = perguntar("qual o valor da causa?")
        lendo = next((d for t, d in eventos if t == "lendo"), {})
        checar(lendo.get("caminho") == "nivel0" and lendo.get("molde") is True, "a tela sabe que foi por molde", lendo)
    finally:
        api.estado.fila_modelo.sair(outra)

    print("\no modelo no nível 0, com um dígito trocado")
    import perguntar as perguntar_mod
    from habilidade_base import Contexto
    from inteligencia.roteador import Fato, Intencao, Pacote

    # Prazo não tem molde: o modelo responde, e a conferência olha.
    pacote = Pacote(nivel=0, fatos=[Fato(documento=doc.name, rotulo="prazo", valor="2024-04-10", pagina=3)],
                    documentos=[doc.name], fallback=False, intencao=Intencao(secao="dates", chave="deadline", nivel=0))
    for resposta, passa in (("O prazo vence em 10/04/2024.", True), ("O prazo vence em 10/04/2025.", False)):
        cliente = Trocador(resposta)
        ctx = Contexto(searcher=api.estado.searcher, client=cliente, registrar=lambda t: None)
        sinal = {"escalou": False}
        eventos = list(perguntar_mod._responder_do_que_ja_se_sabe(ctx, "quando vence o prazo?", pacote, sinal))
        texto = "".join(d.get("t", "") for t, d in eventos if t == "token")
        if passa:
            checar(texto == resposta and not sinal["escalou"], "a resposta certa do modelo passa", (texto, sinal))
        else:
            checar(not texto and sinal["escalou"], "a do dígito trocado é descartada e a pergunta escala", (texto, sinal))


def main() -> int:
    print("=" * 55)
    print("  I3 - nivel 0 por molde")
    print("=" * 55)
    try:
        test_moldes()
        test_na_conversa()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("   -", f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
