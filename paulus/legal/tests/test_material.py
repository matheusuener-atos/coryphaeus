"""
Testes do material de consulta (src/material.py): o PDF que o escritório
entrega para o PAULUS aprender.

  - um PDF de três páginas entra, com o número de páginas e de trechos;
  - o mesmo arquivo não entra duas vezes; formato estranho e PDF sem texto
    (imagem escaneada) são recusados com o motivo;
  - a consulta acha o trecho certo, com a página certa, e não traz trecho
    que mal toca a pergunta;
  - o índice sobrevive a fechar e abrir o programa; remover apaga tudo;
  - na conversa: o trecho do material vai para o modelo com nome e página,
    vira fonte marcada como material, e sem documento aberto a pergunta é
    respondida pelo material;
  - pela API: enviar, listar, remover.

Sem Ollama: o modelo é trocado por um que só guarda o que leu.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_material.py
"""

from __future__ import annotations

import io
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "habilidades"))

import material as material_mod  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


PAGINAS = [
    ["Manual interno do escritório", "Este manual reúne as regras de trabalho da equipe.",
     "Vale para advogados, estagiários e a secretaria."],
    ["Prazos internos", "Toda contestação deve ser protocolada com três dias úteis de antecedência",
     "do prazo final. O revisor confere a peça até o quarto dia útil antes do prazo.",
     "Recurso de apelação segue a mesma regra de antecedência."],
    ["Honorários de consulta", "A consulta avulsa custa R$ 450,00 e é paga antes do atendimento.",
     "Retorno em até trinta dias sobre o mesmo assunto não é cobrado.",
     "Parecer escrito é orçado à parte, conforme a complexidade."],
]


def pdf_de(paginas: list[list[str]]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    saida = io.BytesIO()
    c = canvas.Canvas(saida, pagesize=A4)
    for linhas in paginas:
        y = 800
        for linha in linhas:
            c.drawString(60, y, linha)
            y -= 18
        c.showPage()
    c.save()
    return saida.getvalue()


def pdf_sem_texto() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    saida = io.BytesIO()
    c = canvas.Canvas(saida, pagesize=A4)
    for _ in range(2):
        c.rect(50, 50, 400, 600, fill=1)  # uma "imagem": nada de texto
        c.showPage()
    c.save()
    return saida.getvalue()


def test_absorver(pasta: Path) -> material_mod.Material:
    print("\nentrar")
    m = material_mod.Material(pasta)
    manual = pdf_de(PAGINAS)  # o reportlab carimba data: dois PDFs gerados nunca sao iguais
    item = m.absorver("Manual do escritório.pdf", manual)
    checar(item["paginas"] == 3 and item["trechos"] == 3, "PDF de três páginas entra, um trecho por página", item)
    checar(Path(item["arquivo"]).exists(), "o arquivo original fica guardado nesta máquina")
    de_novo = m.absorver("copia.pdf", manual)
    checar(de_novo.get("ja_existia") and len(m.itens) == 1, "o mesmo arquivo não entra duas vezes", de_novo)
    for nome, conteudo, parte in (
        ("foto.jpg", b"\xff\xd8\xff", "formato"),
        ("vazio.pdf", b"", "vazio"),
        ("escaneado.pdf", pdf_sem_texto(), "imagem"),
    ):
        try:
            m.absorver(nome, conteudo)
            checar(False, f"recusa {nome}")
        except ValueError as exc:
            checar(parte in str(exc), f"recusa {nome}, dizendo por quê", str(exc))
    checar(len(list((pasta / "arquivos").iterdir())) == 1, "o que foi recusado não fica no disco")
    texto = m.absorver("regras.txt", "Regra da casa: toda petição inicial passa pela sócia antes de protocolar.".encode("utf-8"))
    checar(texto["paginas"] == 0 and len(m.itens) == 2, "texto simples também entra", texto)
    return m


def test_consultar(m: material_mod.Material) -> None:
    print("\nconsultar")
    hits = m.consultar("Com quantos dias de antecedência a contestação deve ser protocolada?")
    checar(hits and hits[0].doc_name == "Manual do escritório.pdf", "acha o manual", [h.doc_name for h in hits])
    checar(hits and m.pagina(hits[0]) == 2, "e diz que está na página 2", hits and m.pagina(hits[0]))
    bloco = m.bloco(hits)
    checar("[Material: Manual do escritório.pdf, página 2]" in bloco, "o bloco leva nome e página", bloco[:120])
    checar("[pagina" not in bloco, "sem as marcas internas de página no texto")
    checar(m.consultar("qual a cor do carro do vizinho?") == [], "pergunta sem nada a ver não traz trecho")
    hits = m.consultar("quanto custa a consulta avulsa")
    checar(hits and "450" in hits[0].chunk.text, "acha o valor da consulta", [h.chunk.text[:60] for h in hits])


def test_guardar_e_remover(pasta: Path) -> None:
    print("\nguardar e remover")
    m = material_mod.Material(pasta)
    checar(len(m.itens) == 2 and m.buscador.chunks, "abrir de novo carrega o índice", len(m.itens))
    manual = next(x for x in m.itens if x["nome"].startswith("Manual"))
    checar(m.remover(manual["id"]), "remover responde que removeu")
    checar(not Path(manual["arquivo"]).exists() and not (pasta / "textos" / f"{manual['id']}.txt").exists(),
           "remover apaga o arquivo e o texto")
    checar(m.consultar("antecedência da contestação") == [], "o que foi removido não é mais consultado")
    checar(material_mod.Material(pasta).itens == m.itens, "a remoção vale depois de reabrir")
    checar(not m.remover("nao-existe"), "remover o que não existe responde que não")


class ClienteQueLe:
    model = "falso"
    num_ctx = 8192

    def __init__(self):
        self.contexto = ""

    def ask(self, pergunta, contexto="", **k):
        self.contexto = contexto
        if k.get("on_token"):
            k["on_token"]("resposta")
        return "resposta"


def test_na_conversa(pasta: Path) -> None:
    print("\nna conversa")
    import perguntar
    from extract import Document
    from habilidade_base import Contexto
    from search import ContractSearcher

    m = material_mod.Material(pasta)
    m.absorver("Manual do escritório.pdf", pdf_de(PAGINAS))

    def rodar(docs, pergunta):
        buscador = ContractSearcher()
        if docs:
            buscador.add_contracts(docs)
            buscador.build()
        cliente = ClienteQueLe()
        eventos = list(perguntar.executar(Contexto(searcher=buscador, client=cliente, material=m), pergunta=pergunta))
        return eventos, cliente

    contrato = Document(name="Contrato Silva.txt", path="x",
                        text="CONTRATO DE PRESTAÇÃO DE SERVIÇOS. O prazo de vigência é de doze meses.")
    eventos, cliente = rodar([contrato], "Com quantos dias de antecedência a contestação deve ser protocolada?")
    fontes = next((d for t, d in eventos if t == "fontes"), {})
    do_material = [f for f in fontes.get("trechos", []) if f.get("material")]
    checar(do_material and do_material[0]["onde"] == "página 2", "o trecho do material vira fonte, com a página", do_material[:1])
    checar(fontes.get("material") == ["Manual do escritório.pdf"], "o evento diz qual material foi usado", fontes.get("material"))
    checar("MATERIAL DE CONSULTA" in cliente.contexto and "três dias úteis" in cliente.contexto,
           "o modelo lê o trecho do material", cliente.contexto[-300:])
    checar("Contrato Silva" in cliente.contexto, "e continua lendo os documentos abertos")

    eventos, cliente = rodar([], "Com quantos dias de antecedência a contestação deve ser protocolada?")
    tipos = [t for t, _ in eventos]
    checar("vazio" not in tipos and "três dias úteis" in cliente.contexto,
           "sem documento aberto, responde pelo material", tipos)
    fontes = next((d for t, d in eventos if t == "fontes"), {})
    checar(fontes.get("ignorados") == [], "e não diz que documento ficou de fora", fontes.get("ignorados"))

    eventos, _ = rodar([], "qual a cor do carro do vizinho?")
    vazio = next((d for t, d in eventos if t == "vazio"), {})
    checar("material de consulta" in vazio.get("mensagem", ""), "sem nada em lugar nenhum, diz onde procurou", vazio)

    eventos, cliente = rodar([contrato], "Qual o prazo de vigência do contrato?")
    checar("MATERIAL DE CONSULTA" not in cliente.contexto, "pergunta de documento não leva material que não tem a ver")


def test_api() -> None:
    print("\npela API")
    from fastapi.testclient import TestClient

    import api

    original = api.estado.material
    pasta = Path(tempfile.mkdtemp(prefix="paulus-material-api-"))
    api.estado.material = material_mod.Material(pasta)
    try:
        c = TestClient(api.app)
        r = c.post("/api/material", files=[("arquivos", ("Manual.pdf", pdf_de(PAGINAS), "application/pdf")),
                                           ("arquivos", ("foto.jpg", b"\xff\xd8", "image/jpeg"))])
        d = r.json()
        checar(r.status_code == 200 and len(d["entraram"]) == 1 and len(d["recusados"]) == 1,
               "envio misto: o PDF entra, a foto volta com o motivo", d)
        checar(len(c.get("/api/material").json()["itens"]) == 1, "a lista mostra o que entrou")
        r = c.post("/api/material", files=[("arquivos", ("foto.jpg", b"\xff\xd8", "image/jpeg"))])
        checar(r.status_code == 400 and "formato" in r.json()["detail"], "só coisa ilegível: erro com o motivo", r.json())
        id_ = d["entraram"][0]["id"]
        checar(c.delete(f"/api/material/{id_}").json()["itens"] == [], "remover pela API")
        checar(c.delete(f"/api/material/{id_}").status_code == 404, "remover de novo: não existe")
    finally:
        api.estado.material = original
        shutil.rmtree(pasta, ignore_errors=True)


def main() -> int:
    print("=" * 55)
    print("  o material de consulta")
    print("=" * 55)
    pasta = Path(tempfile.mkdtemp(prefix="paulus-material-"))
    outra = Path(tempfile.mkdtemp(prefix="paulus-material-conversa-"))
    try:
        m = test_absorver(pasta)
        test_consultar(m)
        test_guardar_e_remover(pasta)
        test_na_conversa(outra)
        test_api()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
        shutil.rmtree(outra, ignore_errors=True)
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
