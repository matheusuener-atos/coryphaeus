"""
O editor diante do documento de verdade (13/10/2026): os erros que o dono viu
no "Contrato Obedi Lourenço" viraram casos deste teste, com dados fictícios.

  - o rascunho que veio do PDF linha a linha: juntar as linhas sem mudar
    palavra (src/pdf_em_texto.py), recomeçar do original, a marca na tela;
  - o esboço do fim do documento: "Assinado em…, em duas vias", os nomes em
    maiúsculas, o "Parágrafo 1º:" (src/esboco.py);
  - a conferência da estrutura: o trecho repetido, a cláusula depois do fecho,
    os itens com o número de outra cláusula, a cabeça com o corpo junto;
  - o agente: "dê uma revisada" é revisão (corrige o que é seguro, como
    sugestão, e lê como revisor); "isso mesmo" faz o que a última resposta
    deixou; o texto colado é comparado e as diferenças marcadas;
  - a renumeração que leva os itens junto e não risca dentro do que é novo;
  - o fim do documento: cláusula não entra depois das assinaturas;
  - o que o modelo escreve, limpo.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_editor_revisao.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-editor-revisao-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tools" / "bancada_editor"))

import agente_de_edicao as AG  # noqa: E402
import bancada  # noqa: E402
import blocos as B  # noqa: E402
import conferencia_juridica as C  # noqa: E402
import edicao as ED  # noqa: E402
import esboco as E  # noqa: E402
import pdf_em_texto as P  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def html(linhas: list[str]) -> str:
    return "".join(f"<p>{x}</p>" for x in linhas)


# O rascunho da importação de antes: uma linha do PDF por parágrafo, as marcas
# de página, o rodapé repetido, a palavra partida pelo hífen e a cabeça partida.
SUJO = [
    "[pagina 1]", "CONTRATO DE LOCAÇÃO RESIDENCIAL",
    "<b>LOCADOR:</b> JOÃO DA SILVA TESTE, brasileiro, casado, engenheiro, portador do RG",
    "nº 1234567 SSP/MG, residente na Rua das Flores, 100, Belo Horizonte/MG.",
    "LOCATÁRIA: MARIA DE SOUZA EXEMPLO, brasileira, solteira, professora, portado-",
    "ra do RG nº 7654321 SSP/MG.",
    "CLÁUSULA 1ª – DO OBJETO DO", "CONTRATO DE LOCAÇÃO",
    "O presente contrato tem por objeto a locação do imóvel situado na Rua das",
    "Acácias, 200, Belo Horizonte/MG, para fins exclusivamente residenciais.",
    "CONTRATO DE LOCAÇÃO RESIDENCIAL página 1", "[pagina 2]",
    "CLÁUSULA 2ª – DO PRAZO",
    "O prazo da locação é de 30 (trinta) meses, contados da assinatura deste",
    "instrumento.",
    "Parágrafo 1º: Findo o prazo, a locação prorroga-se por prazo indeterminado.",
    "CONTRATO DE LOCAÇÃO RESIDENCIAL página 2", "[pagina 3]",
    "CLÁUSULA 3ª – DO ALUGUEL",
    "O aluguel mensal é de R$ 2.000,00 (dois mil reais), pago até o dia 5 de cada",
    "mês.",
    "Assinado em 10 de outubro de 2026, em duas vias de igual teor.",
    "JOÃO DA SILVA TESTE", "MARIA DE SOUZA EXEMPLO",
    "CONTRATO DE LOCAÇÃO RESIDENCIAL página 3",
]

# A estrutura que as rodadas antigas deixaram: fecho e assinaturas em dobro,
# cláusula depois deles, itens com o número de outra cláusula, cabeça com o corpo.
BAGUNCADO = [
    "CONTRATO DE PRESTAÇÃO DE SERVIÇOS",
    "CLÁUSULA 1ª – DO OBJETO", "O objeto deste contrato é a prestação de serviços de consultoria tributária.",
    "CLÁUSULA 2ª – DO PREÇO", "O preço é de R$ 1.000,00 (mil reais) por mês, pago até o dia 10.",
    "CLÁUSULA 3ª – DISPOSIÇÕES GERAIS<br>2.1. Este contrato obriga as partes e os seus sucessores a qualquer título.",
    "2.2. As partes elegem o foro da comarca de Belo Horizonte para as questões deste contrato.",
    "Assinado em 10 de outubro de 2026, em duas vias de igual teor.",
    "EMPRESA ALFA TESTE LTDA", "JOSÉ PRESTADOR EXEMPLO",
    "Assinado em 10 de outubro de 2026, em duas vias de igual teor.",
    "EMPRESA ALFA TESTE LTDA", "JOSÉ PRESTADOR EXEMPLO",
    "CLÁUSULA 4ª – DA VIGÊNCIA", "Este contrato vigora por 12 (doze) meses, a partir da assinatura.",
]


class Falso:
    """O modelo de mentira: responde a fila de respostas e guarda o que leu."""

    def __init__(self, respostas: list[str]) -> None:
        self.respostas = list(respostas)
        self.lido: list[list[dict]] = []

    def __call__(self, mensagens, *, json_mode=False, max_tokens=4000, on_token=None):
        self.lido.append(mensagens)
        texto = self.respostas.pop(0) if self.respostas else "{}"
        if on_token:
            on_token(texto)
        return texto


def rodada(chamar, blocos, pedido: str, **k):
    eventos = list(AG.rodar(chamar, blocos, pedido, rodada=1, titulo=k.pop("titulo", "CONTRATO DE TESTE"), **k))
    return eventos, next(d["rodada"] for t, d in eventos if t == "fim")


def teste_esboco() -> None:
    print("o esboço do fim do documento")
    bl = B.ler(html(BAGUNCADO[:5] + ["Parágrafo 1º: O preço é reajustado pelo IPCA a cada 12 meses."] + BAGUNCADO[7:10]))
    partes = [(b.texto, (p.tipo, p.rotulo)) for b, p in zip(bl, E.esboco(bl))]

    def de(comeco: str) -> tuple:
        return next((x for t, x in partes if t.startswith(comeco)), ("", ""))

    checar(de("Parágrafo 1º") == ("paragrafo", "Cláusula 2ª, § 1º"), "“Parágrafo 1º:” é o § 1º da cláusula",
           de("Parágrafo 1º"))
    checar(de("Assinado em")[0] == "fecho", "“Assinado em…, em duas vias” é o fecho", de("Assinado em"))
    checar(de("EMPRESA ALFA")[0] == "assinatura" and de("JOSÉ PRESTADOR")[0] == "assinatura",
           "os nomes em maiúsculas depois dele são as assinaturas, não o corpo da última cláusula")


def teste_limpeza() -> None:
    print("\no rascunho que veio do PDF linha a linha")
    bl = B.ler(html(SUJO))
    marcas = P.marcas_do_pdf(bl)
    checar(marcas["limpar"] and marcas["paginas"] == 3, "a marca: 3 páginas, vale juntar", marcas)
    novos, rel = P.limpar_blocos(bl)
    textos = [b.texto for b in novos]
    checar(rel["paginas"] == 3 and rel["margens"] == 3, "saem as 3 marcas de página e os 3 rodapés repetidos", rel)
    checar(len(novos) == 13, "as 25 linhas viram 13 parágrafos", textos)
    checar("CLÁUSULA 1ª – DO OBJETO DO CONTRATO DE LOCAÇÃO" in textos, "a cabeça partida em duas linhas volta a ser uma")
    checar(any("professora, portadora do RG" in t for t in textos), "a palavra partida pelo hífen é reunida")
    checar(any(t.startswith("O prazo da locação") and t.endswith("deste instrumento.") for t in textos),
           "a frase partida no fim da linha é juntada")
    locador = next(b for b in novos if b.texto.startswith("LOCADOR"))
    checar(locador.corridas[0].marcas == ("b",) and locador.texto.endswith("Belo Horizonte/MG."),
           "o negrito do começo fica no parágrafo juntado")
    letras = lambda lista: "".join(x.texto for x in lista).replace(" ", "").replace("-", "")  # noqa: E731
    sem_margens = [b for b in bl if not (P.RE_PAGINA.match(b.texto) or "página" in b.texto)]
    checar(letras(novos) == letras(sem_margens), "palavra nenhuma muda")
    sugerido = B.ler(html(SUJO))
    B.reescrever(sugerido[2], sugerido[2].texto + " (teste)", "s1", 1)
    try:
        P.limpar_blocos(sugerido)
        checar(False, "com sugestão pendente, não limpa")
    except ValueError as exc:
        checar("sugest" in str(exc), "com sugestão pendente, não limpa", str(exc))
    limpos = B.ler(B.html(novos))
    checar(not P.marcas_do_pdf(limpos)["limpar"], "depois de limpo, nada a juntar")


def teste_conferencia() -> None:
    print("\na conferência da estrutura")
    bl = B.ler(html(BAGUNCADO))
    avisos = {a["titulo"]: a for a in C.conferir(bl)}
    rep = avisos.get("Trecho repetido") or {}
    checar(len(rep.get("blocos", [])) == 3, "o fecho e as assinaturas em dobro: um aviso só, com os 3 parágrafos", rep)
    depois = avisos.get("Cláusula depois do fecho") or {}
    checar(depois.get("rotulo") == "Cláusula 4ª" and len(depois.get("blocos", [])) == 2 and depois.get("antes_de"),
           "a cláusula depois das assinaturas, com o lugar dela", depois)
    itens = avisos.get("Itens com o número de outra cláusula") or {}
    checar(itens.get("itens") and itens["itens"][0]["texto"].startswith("3.2."), "o item 2.2 na Cláusula 3ª seria 3.2",
           itens)
    cabeca = avisos.get("Cabeça com o corpo junto") or {}
    checar(cabeca.get("cabeca") == "CLÁUSULA 3ª – DISPOSIÇÕES GERAIS" and cabeca.get("corpo"),
           "a cabeça que leva o corpo junto", cabeca)
    antes = bancada.documento("locacao")
    depois_ = bancada.documento("locacao")
    cab = next(b for b in depois_ if b.texto.startswith("CLÁUSULA 1ª"))
    B.reescrever(cab, cab.texto + " E DO USO", "s1", 1)
    novos = C.novos(C.conferir(antes), C.conferir(depois_, antes=antes))
    checar(not any(a["titulo"] == "Referência que mudou de cláusula" for a in novos),
           "o título que ganhou palavras é a mesma cláusula: a referência a ela não “mudou de alvo”", novos)


def teste_entender() -> None:
    print("\no que o pedido é")
    bl = bancada.documento("locacao")
    casos = {"De uma revisada de forma visual como o documento está ficando": "revisar",
             "dê uma revisada geral": "revisar", "arrume a formatação do contrato": "revisar",
             "isso mesmo": "confirmar", "pode fazer": "confirmar", "sim, por favor": "confirmar",
             "revise a cláusula 2ª para ficar mais formal": "editar", "Qual é o prazo da locação?": "pergunta"}
    for frase, tipo in casos.items():
        e = AG.entender(bl, frase)
        checar(e.tipo == tipo, f"“{frase}” é {tipo}", e.tipo)
    colado = "\n".join(b.texto for b in bl)
    checar(AG.entender(bl, colado).tipo == "texto_colado", "o documento colado inteiro é texto colado, não pedido")
    checar(AG.entender(bl, "Substitua a cláusula 2ª por: " + colado[:500]).tipo == "editar",
           "texto com instrução na frente é edição")


def teste_revisao() -> None:
    print("\na revisão: corrige o que é seguro, como sugestão, e lê como revisor")
    bl = B.ler(html(BAGUNCADO))
    preco = next(b for b in bl if b.texto.startswith("O preço"))
    leitura = {"pontos": [{"bloco": preco.id, "texto": "O preço não diz como é reajustado; inclua o índice (IPCA) e a "
                           "periodicidade."}, {"bloco": "", "texto": "Nenhum outro ponto."}]}
    falso = Falso([json.dumps(leitura, ensure_ascii=False)])
    eventos, r = rodada(falso, bl, "Dê uma revisada no contrato")
    checar(r.tipo == "revisar" and len(falso.lido) == 1 and "revisor sênior" in falso.lido[0][0]["content"],
           "uma chamada só ao modelo: a leitura de revisor")
    aceito = [b.texto for b in B.aceito(r.blocos)]
    checar(aceito.count("Assinado em 10 de outubro de 2026, em duas vias de igual teor.") == 1
           and aceito.count("EMPRESA ALFA TESTE LTDA") == 1, "a cópia repetida do fecho e das assinaturas sai", aceito)
    i_vig, i_fecho = aceito.index("CLÁUSULA 4ª – DA VIGÊNCIA"), aceito.index(
        "Assinado em 10 de outubro de 2026, em duas vias de igual teor.")
    checar(i_vig < i_fecho and aceito[i_vig + 1].startswith("Este contrato vigora"),
           "a cláusula que estava depois das assinaturas vai para antes do fecho, com o corpo")
    checar("CLÁUSULA 3ª – DISPOSIÇÕES GERAIS" in aceito and any(t.startswith("3.1. Este contrato") for t in aceito)
           and any(t.startswith("3.2. As partes") for t in aceito),
           "a cabeça separada do corpo, e os itens com o número da cláusula", aceito)
    checar(all(b.sug != "ins" or not any(c.sug for c in b.corridas) for b in r.blocos),
           "dentro do que é novo (a cláusula movida) não há risco nem sublinhado")
    checar(r.aplicadas and all(a["sids"] for a in r.aplicadas), "cada correção é uma sugestão, para aceitar ou recusar")
    checar(len(r.leitura) == 1 and r.leitura[0]["rotulo"] == "Cláusula 2ª", "a leitura do revisor, no lugar dela", r.leitura)
    texto = AG.resposta(r, "CONTRATO DE PRESTAÇÃO DE SERVIÇOS")
    checar(texto.startswith("Revisei “Contrato de prestação de serviços”") and "Na leitura, como revisor:" in texto,
           "a resposta: o que corrigi, como sugestão, e o que a leitura achou", texto)
    eventos, r = rodada(Falso([json.dumps({"pontos": []})]), bancada.documento("locacao"), "revise o documento")
    checar(not r.aplicadas and "não achei problema" in AG.resposta(r, "Locação"), "documento em ordem: diz que está em ordem",
           AG.resposta(r, "Locação"))


def teste_colado() -> None:
    print("\no texto colado: comparar e marcar as diferenças")
    bl = bancada.documento("locacao")
    texto = " ".join(b.texto for b in bl if b.tipo != "table")
    alvo = next(b for b in bl if "30 (trinta) meses" in b.texto)
    novo = texto.replace("30 (trinta) meses", "24 (vinte e quatro) meses")
    novo = novo.replace(alvo.texto.split(".")[0], alvo.texto.split(".")[0] + ". A LOCATÁRIA poderá devolver o imóvel "
                        "antes do prazo mediante aviso por escrito com antecedência de trinta dias", 1)
    ops, info = ED.comparar_com_texto(bl, novo)
    checar(info["parecido"] > 0.9 and info["cobre_tudo"] and ops, "o texto colado é uma versão deste documento", info)
    r = ED.aplicar(bl, ops, rodada=1)
    aceito = " ".join(" ".join(b.texto.split()) for b in B.aceito(r.blocos) if b.tipo != "table")
    checar(aceito == " ".join(novo.split()), "aceitas as diferenças, o documento é o texto colado")
    checar(all(a["sids"] for a in r.aplicadas) and len(r.aplicadas) == len(ops), "cada parágrafo mudado é uma sugestão")
    ate = next(i for i, b in enumerate(bl) if "30 (trinta) meses" in b.texto) + 1
    parte = " ".join(b.texto for b in bl[:ate]).replace("30 (trinta) meses", "36 (trinta e seis) meses")
    ops, info = ED.comparar_com_texto(bl, parte)
    checar(not info["cobre_tudo"] and len(ops) == 1 and ops[0]["op"] == "reescrever", "o pedaço colado só mexe no pedaço",
           (info, ops))
    estranho = ("Ata da reunião do conselho de moradores do bairro, realizada na quadra poliesportiva, com pauta de "
                "iluminação pública, coleta seletiva e segurança. Os presentes aprovaram por unanimidade a proposta de "
                "mutirão de limpeza no último sábado do mês e a compra de duas lixeiras novas para a praça central.") * 2
    ops, info = ED.comparar_com_texto(bl, estranho)
    checar(not ops and info["parecido"] < 0.5, "texto de outro documento: nada é marcado", info)
    eventos, r = rodada(Falso([]), bl, novo)
    checar(r.tipo == "texto_colado" and r.aplicadas and "Comparei com o texto que você colou" in AG.resposta(r, "Locação"),
           "na rodada: sem modelo, as diferenças marcadas e a resposta diz isso", AG.resposta(r, "Locação"))


def teste_renumeracao() -> None:
    print("\na renumeração")
    bl = B.ler(html(["CONTRATO", "CLÁUSULA 1ª – DO OBJETO", "Objeto do contrato de teste.", "CLÁUSULA 2ª – DISPOSIÇÕES",
                     "2.1. Primeiro item das disposições.", "2.2. Segundo item das disposições."]))
    um = next(b for b in bl if b.texto.startswith("CLÁUSULA 1ª"))
    r = ED.aplicar(bl, [{"op": "inserir", "depois_de": um.id, "blocos": [
        {"texto": "CLÁUSULA 9ª – DA GARANTIA"}, {"texto": "A garantia é a caução de três aluguéis."}]}], rodada=1)
    feito = ED.renumerar(r.blocos, 1)
    aceito = [b.texto for b in B.aceito(r.blocos)]
    checar(feito and "CLÁUSULA 2ª – DA GARANTIA" in aceito and "CLÁUSULA 3ª – DISPOSIÇÕES" in aceito,
           "a cláusula nova entra na sequência e as seguintes acompanham", aceito)
    checar("3.1. Primeiro item das disposições." in aceito and "3.2. Segundo item das disposições." in aceito,
           "os itens da cláusula que virou 3ª viram 3.1 e 3.2", aceito)
    nova = next(b for b in r.blocos if "GARANTIA" in b.texto)
    checar(nova.sug == "ins" and not any(c.sug for c in nova.corridas) and nova.texto == "CLÁUSULA 2ª – DA GARANTIA",
           "na cláusula que ainda é sugestão, o número novo vai direto (nada de “9ª2ª” riscado)", nova.texto)
    checar("ite" in feito["resumo"], "o resumo conta os itens", feito["resumo"])


def teste_fim_do_documento() -> None:
    print("\no fim do documento")
    bl = bancada.documento("locacao")
    assinatura = [b for b in bl if "MARIANA COSTA RIBEIRO" in b.texto][-1]
    r = ED.aplicar(bl, [{"op": "inserir", "depois_de": assinatura.id, "blocos": [
        {"texto": "CLÁUSULA 8ª – DA VISTORIA"}, {"texto": "A vistoria de entrada integra este contrato."}]}], rodada=1)
    partes = [(b.texto[:20], p.tipo) for b, p in zip(r.blocos, E.esboco(r.blocos))]
    i_nova = next(i for i, (t, _) in enumerate(partes) if t.startswith("CLÁUSULA 8ª"))
    i_fecho = next(i for i, (_, tp) in enumerate(partes) if tp == "fecho")
    checar(i_nova < i_fecho, "cláusula pedida “depois da assinatura” entra antes do fecho", partes[-8:])
    r = ED.aplicar(bl, [{"op": "inserir", "depois_de": assinatura.id, "blocos": [{"texto": "Testemunha: ANA TESTE"}]}],
                   rodada=1)
    checar(B.aceito(r.blocos)[-1].texto == "Testemunha: ANA TESTE", "testemunha pode ir depois das assinaturas")


def teste_limpar_itens() -> None:
    print("\no que o modelo escreve, limpo")
    rot = {"bb9096a": "Cláusula 3ª", "bc0857a": "Cláusula 4ª"}
    itens = ["Não fiz ajustes em outras cláusulas que não foram especificamente mencionadas no pedido",
             "Nenhuma lacuna identificada", "Nada mais foi alterado, apenas a ordem das cláusulas foi modificada",
             "Talvez seja necessário ajustar a CLÁUSULA 3ª – DA ENTREGA para refletir a mudança",
             "Não fiz: o prazo do bloco bb9096a depende de dado que o pedido não trouxe"]
    limpos = AG._limpar_itens(itens, rot)
    checar(limpos == ["Ajustar a CLÁUSULA 3ª – DA ENTREGA para refletir a mudança",
                      "O prazo da Cláusula 3ª depende de dado que o pedido não trouxe"],
           "sem o vazio, sem a justificativa, sem o rótulo repetido e sem nome de bloco", limpos)


def pdf_de_teste() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    from reportlab.lib.styles import getSampleStyleSheet

    saida = io.BytesIO()
    estilo = getSampleStyleSheet()["BodyText"]
    linhas = ["CONTRATO DE LOCAÇÃO RESIDENCIAL", "CLÁUSULA 1ª – DO OBJETO",
              "O presente contrato tem por objeto a locação do imóvel situado na Rua das Acácias, 200.",
              "CLÁUSULA 2ª – DO PRAZO", "O prazo da locação é de 30 (trinta) meses, contados da assinatura."]
    SimpleDocTemplate(saida, pagesize=A4).build([Paragraph(x, estilo) for x in linhas])
    return saida.getvalue()


def eventos_sse(texto: str) -> list[tuple[str, dict]]:
    saida = []
    for bloco in texto.split("\n\n"):
        tipo = next((l[7:] for l in bloco.splitlines() if l.startswith("event: ")), "")
        dado = next((l[6:] for l in bloco.splitlines() if l.startswith("data: ")), "")
        if tipo:
            saida.append((tipo, json.loads(dado) if dado else {}))
    return saida


def teste_api() -> None:
    print("\npela API: limpar, recomeçar, revisar e confirmar")
    import api
    import nuvem
    from fastapi.testclient import TestClient

    nuvem.chave = lambda estado, provedor: ""
    api.plano_mod.liberada = lambda estado: True
    local = TestClient(api.app, headers=api.cabecalho_local())
    tid = local.post("/api/trabalhos", json={"pedido": "contrato de teste"}).json()["id"]
    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    original = pasta / "Locação teste.pdf"
    original.write_bytes(pdf_de_teste())
    did = api.estado.documentos.criar("CONTRATO DE LOCAÇÃO RESIDENCIAL", "texto", html(SUJO), None, trabalho_id=tid,
                                      situacao="conversa", origem={"tipo": "acervo", "nome": original.name,
                                                                   "caminho": str(original), "sha1": ""})
    doc = local.get(f"/api/documentos/{did}").json()
    checar(doc["marcas_pdf"]["limpar"], "a tela sabe que o rascunho veio do PDF linha a linha", doc.get("marcas_pdf"))
    r = local.post(f"/api/documentos/{did}/limpar-pdf", json={"revisao": doc["revisao"]})
    d = r.json()
    checar(r.status_code == 200 and "[pagina" not in d["corpo"] and d["frase"].startswith("Juntei as 25 linhas do PDF em 13"),
           "juntar as linhas: o corpo limpo, e a frase diz o que foi feito", d.get("frase"))
    voltou = local.post(f"/api/documentos/{did}/restaurar", json={"numero": d["versao_antes"]}).json()
    checar("[pagina 1]" in voltou["documento"]["corpo"], "desfazer a limpeza: a versão de antes volta do Histórico")
    r = local.post(f"/api/documentos/{did}/recomecar", json={})
    checar(r.status_code == 200 and "Rua das Acácias" in r.json()["corpo"] and "[pagina" not in r.json()["corpo"]
           and "ficou no Histórico" in r.json()["frase"], "recomeçar do original: o PDF lido limpo", r.text[:200])

    # Revisar o rascunho sujo: junta as linhas antes, e a revisão roda nos parágrafos.
    api.estado.documentos.salvar(did, html(SUJO))
    falso = Falso([json.dumps({"pontos": [{"bloco": "", "texto": "Falta a cláusula de reajuste do aluguel."}]})])
    api._modelo_do_editor = lambda *a, **k: (falso, {"onde": "teste", "modelo": "falso", "provedor": "", "motivo": ""})
    resp = local.post(f"/api/documentos/{did}/editar", json={"pedido": "De uma revisada de forma visual como o documento "
                                                                       "está ficando", "trabalho_id": tid})
    ev = eventos_sse(resp.text)
    tipos = [t for t, _ in ev]
    fim = next((d for t, d in ev if t == "fim"), {})
    checar("documento" in tipos and tipos.index("documento") < tipos.index("fim"),
           "a revisão começa juntando as linhas (o evento “documento” troca a folha)", tipos)
    checar(fim.get("tipo") == "revisar" and fim.get("limpeza") and fim["texto"].startswith("Juntei")
           and "Falta a cláusula de reajuste" in fim["texto"], "e a resposta diz a limpeza e o que a leitura achou",
           fim.get("texto"))
    corpo = api.estado.documentos.obter(did)["corpo"]
    checar("[pagina" not in corpo, "o documento ficou limpo")

    # "Isso mesmo": o que a última resposta deixou para fazer.
    falso.respostas = [json.dumps({"operacoes": []})]
    falso.lido.clear()
    local.post(f"/api/documentos/{did}/editar", json={"pedido": "isso mesmo", "trabalho_id": tid})
    checar(falso.lido and "O advogado confirmou" in falso.lido[0][-1]["content"]
           and "Falta a cláusula de reajuste" in falso.lido[0][-1]["content"],
           "“isso mesmo” vira o pedido do que a revisão apontou")
    checar(falso.lido and "A CONVERSA ATÉ AQUI" in falso.lido[0][-1]["content"], "e o modelo lê a conversa até ali")
    outro = api.estado.documentos.criar("Outro", "texto", "<p>Texto qualquer do outro documento.</p>", None,
                                        trabalho_id=tid, situacao="conversa")
    falso.lido.clear()
    resp = local.post(f"/api/documentos/{outro}/editar", json={"pedido": "isso mesmo", "trabalho_id": tid})
    fim = next((d for t, d in eventos_sse(resp.text) if t == "fim"), {})
    checar(not falso.lido and fim.get("texto", "").startswith("Não ficou nada pendente"),
           "sem nada pendente: diz isso, sem chamar o modelo (e nada de “não entendi a pergunta”)", fim.get("texto"))


def main() -> int:
    print("=" * 60)
    print("  O editor diante do documento de verdade")
    print("=" * 60)
    teste_esboco()
    teste_limpeza()
    teste_conferencia()
    teste_entender()
    teste_revisao()
    teste_colado()
    teste_renumeracao()
    teste_fim_do_documento()
    teste_limpar_itens()
    teste_api()
    print()
    if _falhas:
        print(f"{len(_falhas)} falha(s): " + "; ".join(_falhas))
        return 1
    print("todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
