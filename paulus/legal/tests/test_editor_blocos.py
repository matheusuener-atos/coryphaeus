"""
O documento em blocos com identidade, o esboço e as operações de edição
(docs/PLANO-EDITOR.md, E2 e E3).

  - blocos: o HTML do editor lido e escrito de volta com o mesmo nome em cada
    bloco; nome repetido (o Enter do navegador copia o parágrafo) e bloco sem
    nome ganham nome; o que não é documento (script, estilo colado) sai, o
    texto nunca; a marca antiga do assistente (mark.ed-novo) vira sugestão;
  - a mudança marcada palavra por palavra, o negrito preservado, a sugestão
    sobre sugestão pendente coerente ("30 → 60" e depois "60 → 90" é "30 →
    90"), aceitar e recusar por nome e por rodada;
  - os remendos (só os pedaços que mudaram, listas inteiras) e a recusa do
    remendo cujo bloco mudou enquanto o modelo escrevia;
  - achar o trecho com aspas curvas, travessão, caixa e acento trocados;
  - o esboço de um contrato de locação e de uma petição, e "a alínea a do
    inciso II da cláusula 3ª" achada por regra;
  - cada operação (substituir, em todo o documento, reescrever, inserir no
    lugar certo, apagar e mover a cláusula inteira, comentar, renumerar) e cada
    recusa (bloco que não existe, trecho que não está lá, fora da seleção,
    troca em tudo não pedida). Recusar tudo devolve o documento de antes.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_editor_blocos.py
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import blocos as B  # noqa: E402
import edicao as ED  # noqa: E402
import esboco as E  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


LOCACAO = """<h1>CONTRATO DE LOCAÇÃO RESIDENCIAL</h1>
<p>Pelo presente instrumento, JOÃO DA SILVA, doravante denominado LOCADOR, e MARIA SOUZA, doravante denominada LOCATÁRIA, contratam:</p>
<p><b>CLÁUSULA PRIMEIRA – DO OBJETO</b></p>
<p>O LOCADOR dá em locação à LOCATÁRIA o imóvel situado na Rua das Flores, nº 100.</p>
<p><b>CLÁUSULA SEGUNDA – DO PRAZO</b></p>
<p>O prazo da locação é de 30 (trinta) meses.</p>
<p>Parágrafo único. Findo o prazo, a locação prorroga-se por prazo indeterminado.</p>
<p><b>CLÁUSULA TERCEIRA – DO ALUGUEL</b></p>
<p>O aluguel mensal é de R$ 2.000,00 (dois mil reais), pago pela LOCATÁRIA.</p>
<p>§ 1º O pagamento será feito até o dia 5 de cada mês, conforme a cláusula 2.</p>
<p>§ 2º O atraso implica:</p>
<p>I – multa de 10%;</p>
<p>II – juros de 1% ao mês;</p>
<p>a) calculados pro rata die;</p>
<p><b>CLÁUSULA QUARTA – DO FORO</b></p>
<p>Fica eleito o foro da Comarca de Belo Horizonte.</p>
<p>E, por estarem assim justas e contratadas, as partes assinam o presente.</p>
<p>Belo Horizonte, 13 de outubro de 2026.</p>
<p>______________________</p>
<p>LOCADOR</p>"""

PETICAO = """<p>EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA VARA CÍVEL DA COMARCA DE BELO HORIZONTE</p>
<p>MARIA SOUZA, brasileira, vem propor AÇÃO DE COBRANÇA em face de JOÃO DA SILVA, pelos fatos a seguir.</p>
<p>I – DOS FATOS</p>
<p>A autora emprestou ao réu a quantia de R$ 5.000,00.</p>
<p>II – DO DIREITO</p>
<p>O art. 586 do Código Civil dispõe sobre o mútuo.</p>
<p>III – DOS PEDIDOS</p>
<p>Requer a condenação do réu ao pagamento.</p>
<p>Nestes termos, pede deferimento.</p>"""


def teste_ler_e_escrever() -> None:
    print("blocos: ler e escrever")
    h = ('<p data-b="a1b2c3">Um <b>dois</b> três<br>quatro</p><p data-b="a1b2c3">copiado pelo Enter</p>'
         'texto solto<div>linha div</div><ul><li>um<ul><li>dentro</li></ul></li><li>dois</li></ul>'
         '<table><tr><th>Parcela</th><td>Valor</td></tr></table><script>alert(1)</script>'
         '<p style="color:red;text-align: justify">justificado <span style="font-weight:700">forte</span></p>'
         '<blockquote style="margin:0 0 0 40px"><p>recuado</p></blockquote><p><mark class="ed-novo">do assistente</mark></p>'
         '<p><font face="Arial">fonte</font> <a href="x">link</a> <img src="x"> fim</p>')
    bs = B.ler(h)
    ids = [b.id for b in bs]
    checar(len(ids) == len(set(ids)), "todo bloco com nome único")
    checar(bs[0].id == "a1b2c3" and bs[1].id != "a1b2c3", "o nome repetido fica no primeiro; o segundo ganha outro")
    checar(bs[0].texto == "Um dois três\nquatro", "texto visível com a quebra", bs[0].texto)
    checar([c.marcas for c in bs[0].corridas][1] == ("b",), "negrito preservado")
    tipos = [b.tipo for b in bs]
    checar(tipos == ["p", "p", "p", "p", "li", "li", "li", "table", "p", "blockquote", "p", "p"], "tipos lidos", tipos)
    checar([b.nivel for b in bs if b.tipo == "li"] == [0, 1, 0], "lista aninhada guarda o nível")
    saida = B.html(bs)
    checar("script" not in saida and "alert" not in saida, "script sai")
    checar("color" not in saida and 'style="text-align: justify;"' in saida, "estilo colado sai; alinhamento fica")
    checar("<b>forte</b>" in saida, "span com font-weight vira negrito")
    checar('data-s="s-legado"' in saida and "<ins" in saida, "mark.ed-novo antigo vira sugestão de inserir")
    checar("fonte link fim" in B.texto_puro(bs), "marcação desconhecida vira texto, nada some", B.texto_puro(bs))
    de_novo = B.ler(saida)
    checar([b.id for b in de_novo] == ids and B.html(de_novo) == saida, "ler o que escreveu dá o mesmo (ida e volta)")
    checar(B.normalizar("") == "" and "<br>" in B.normalizar("<p></p>"), "vazio e parágrafo vazio")


def teste_reescrever_marcado() -> None:
    print("blocos: mudança marcada palavra por palavra")
    bs = B.ler('<p data-b="x">O <b>VENDEDOR</b> vende o imóvel situado na Rua A, nº 10.</p>')
    b = bs[0]
    checar(B.reescrever(b, "O VENDEDOR vende o imóvel situado na Rua B, nº 12, nesta cidade.", "s1", 1),
           "reescrever devolve True quando muda")
    h = B.html(bs)
    checar("<b>VENDEDOR</b>" in h, "o negrito do que não mudou fica", h)
    checar('<del data-s="s1" data-r="1">A</del><ins data-s="s1" data-r="1">B</ins>' in h, "só a palavra que mudou é marcada", h)
    checar(b.texto.endswith("nº 12, nesta cidade.") and b.texto_original().endswith("nº 10."), "texto visível e original")
    checar(not B.reescrever(b, b.texto, "s9", 2), "reescrever com o mesmo texto não muda nada")

    bs = B.ler('<p data-b="a">O prazo é de 30 dias.</p>')
    B.reescrever(bs[0], "O prazo é de 60 dias corridos.", "s1", 1)
    B.reescrever(bs[0], "O prazo é de 90 dias.", "s2", 2)
    h = B.html(bs)
    checar('<del data-s="s2" data-r="2">30</del><ins data-s="s2" data-r="2">90</ins>' in h,
           "sugestão sobre sugestão pendente: “30 → 60” e “60 → 90” vira “30 → 90”", h)
    checar("s1" not in h, "o que só entrava na sugestão anterior some")
    checar(B.html(B.decidir(bs, True, sids={"s2"})).count("90") == 1 and "30" not in B.html(B.decidir(bs, True, sids={"s2"})),
           "aceitar a nova deixa 90")
    checar("30 dias" in B.texto_puro(B.decidir(bs, False, sids={"s2"})), "recusar a nova volta a 30")

    bs = B.ler('<p data-b="y">Texto a sair.</p><p data-b="z">fica</p>')
    B.reescrever(bs[0], "", "s3", 1)
    checar(bs[0].texto == "" and "<del" in B.html(bs), "apagar o texto todo marca tudo como saindo")
    checar([b.id for b in B.aceito(bs)] == ["z"], "aceitar apaga o bloco que ficou vazio")
    checar([b.id for b in B.recusado(bs)] == ["y", "z"], "recusar devolve o bloco")

    bs = B.ler('<p data-b="r">um</p><p data-b="s">dois</p>')
    B.reescrever(bs[0], "UM", "sa", 1)
    B.reescrever(bs[1], "DOIS", "sb", 2)
    so_r1 = B.decidir(bs, False, rodada=1)
    checar(B.texto_puro(so_r1) == "um\nDOIS" and B.tem_sugestoes(so_r1), "recusar por rodada mexe só nela")
    checar(len(B.sugestoes(bs)) == 2 and B.sugestoes(bs)[0]["entra"] == "UM", "lista de sugestões pendentes")


def teste_remendos() -> None:
    print("blocos: remendos")
    antes = B.ler('<p data-b="a">um</p><p data-b="b">dois</p><ul><li data-b="c">três</li></ul><p data-b="d">quatro</p>')
    depois = copy.deepcopy(antes)
    B.reescrever(depois[0], "UM", "s1", 1)
    depois.insert(3, B.bloco_novo("li", "três e meio", {b.id for b in depois}, "s1", 1, lista="ul"))
    lista = B.remendos(antes, depois)
    checar(len(lista) == 2, "dois pedaços mudaram", [r["ids"] for r in lista])
    checar(lista[0]["ids"] == ["a"] and lista[0]["antes"] == {"a": "um"}, "remendo do bloco trocado leva o texto de antes")
    checar(lista[1]["ids"] == ["c"] and lista[1]["html"].startswith("<ul>"), "a lista vai inteira", lista[1])
    aplicado, conflitos = B.aplicar_remendos(antes, lista)
    checar(B.html(aplicado) == B.html(depois) and not conflitos, "aplicar os remendos chega ao mesmo documento")
    mexido = copy.deepcopy(antes)
    mexido[0].corridas = [B.Corrida("um e meio")]
    _, conflitos = B.aplicar_remendos(mexido, lista)
    checar([c["ids"] for c in conflitos] == [["a"]], "bloco que a pessoa mudou enquanto isso não é sobrescrito")
    novo = B.ler('<p data-b="n">primeiro</p>') + copy.deepcopy(antes)
    lista = B.remendos(antes, novo)
    checar(lista and lista[0]["ids"] == ["a"] and "primeiro" in lista[0]["html"], "inserção no começo ancora no seguinte")


def teste_achar() -> None:
    print("blocos: achar o trecho")
    texto = "O “LOCATÁRIO” pagará  R$ 1.000,00 – mensais"
    checar(B.achar(texto, '"LOCATARIO" pagara R$ 1.000,00 - mensais') == (2, len(texto)), "aspas, travessão, acento, espaço")
    checar(B.achar(texto, "mensais") == (len(texto) - 7, len(texto)), "trecho exato")
    checar(B.achar(texto, "anuais") is None, "o que não está lá não é achado")
    checar(B.ocorrencias("SEMA e SEMAS e SEMA", "SEMA") == [(0, 4), (15, 19)], "palavra inteira: SEMA não casa em SEMAS")


def teste_esboco() -> None:
    print("esboço")
    bs = B.ler(LOCACAO)
    rot = [p.rotulo for p in E.esboco(bs)]
    esperado = ["Título", "Preâmbulo", "Cláusula 1ª", "Cláusula 1ª", "Cláusula 2ª", "Cláusula 2ª",
                "Cláusula 2ª, parágrafo único", "Cláusula 3ª", "Cláusula 3ª", "Cláusula 3ª, § 1º", "Cláusula 3ª, § 2º",
                "Cláusula 3ª, § 2º, inciso I", "Cláusula 3ª, § 2º, inciso II", "Cláusula 3ª, § 2º, inciso II, alínea a",
                "Cláusula 4ª", "Cláusula 4ª", "Fecho", "Local e data", "Assinaturas", "Assinaturas"]
    checar(rot == esperado, "rótulos do contrato de locação", [r for r, e in zip(rot, esperado) if r != e])
    ids = [b.id for b in bs]
    casos = {
        "mude a cláusula segunda": ids[4:7], "no parágrafo único": [ids[6]], "o § 2º da cláusula terceira": [ids[10]],
        "inciso II da cláusula 3": [ids[12]], "alínea a do inciso II da cláusula 3ª": [ids[13]],
        "na 4ª cláusula": ids[14:16], "no preâmbulo": [ids[1]], "o fecho": [ids[16]], "reescreva o título": [ids[0]],
        "o último parágrafo": [ids[16]],
    }
    for frase, alvo in casos.items():
        achado = E.localizar(bs, frase)
        checar(achado["ids"] == alvo, f"localizar “{frase}”", achado)
    checar(E.localizar(bs, "a cláusula décima")["como"] == "nao_existe", "cláusula que não existe é dita")
    checar(E.localizar(bs, "deixe mais formal")["ids"] == [], "frase sem lugar não aponta lugar")
    resumo = E.resumo(bs)
    checar("Cláusula 3ª: CLÁUSULA TERCEIRA – DO ALUGUEL" in resumo and "(7 blocos)" in resumo, "resumo do esboço", resumo)

    pt = B.ler(PETICAO)
    rot = [p.rotulo for p in E.esboco(pt)]
    checar(rot[0] == "Endereçamento" and rot[2] == "I – DOS FATOS" and rot[3] == "I – DOS FATOS", "petição: seções", rot)
    checar(E.localizar(pt, "nos pedidos")["ids"] == [pt[6].id, pt[7].id], "petição: “nos pedidos”")
    checar(rot[-1] == "Fecho", "petição: fecho", rot[-1])


def teste_operacoes() -> None:
    print("operações de edição")
    bs = B.ler(LOCACAO)
    ids = [b.id for b in bs]
    r = ED.aplicar(bs, [
        {"op": "substituir", "bloco": ids[5], "de": "30 (trinta)", "para": "24 (vinte e quatro)"},
        {"op": "inserir", "depois_de": ids[7], "blocos": [{"texto": "CLÁUSULA QUARTA – DA MULTA"},
                                                          {"texto": "O atraso implica multa de 10% sobre o aluguel."}]},
        {"op": "substituir_em_tudo", "de": "LOCATÁRIA", "para": "INQUILINA"},
        {"op": "reescrever", "bloco": ids[15], "texto": "Fica eleito o foro da Comarca de Belo Horizonte/MG."},
        {"op": "comentar", "bloco": ids[8], "texto": "Falta o índice de reajuste."},
        {"op": "substituir", "bloco": ids[3], "de": "Rua dos Lírios", "para": "x"},
        {"op": "apagar", "bloco": "b000000"},
        {"op": "desconhecida"},
    ], rodada=1)
    resumos = [a["resumo"] for a in r.aplicadas]
    checar(resumos[0] == "Cláusula 2ª: “30 (trinta)” → “24 (vinte e quatro)”", "resumo da troca", resumos[0])
    checar(resumos[1] == "Inseri a cláusula “CLÁUSULA QUARTA – DA MULTA” depois da Cláusula 3ª", "resumo da inserção",
           resumos[1])
    novo = B.por_id(r.blocos)[r.aplicadas[1]["ids"][0]]
    posicao = B.indice(r.blocos, novo.id)
    checar(r.blocos[posicao - 1].id == ids[13], "a cláusula nova entra depois do ÚLTIMO bloco da 3ª (a alínea)")
    checar(novo.corridas[0].marcas == ("b",), "a cabeça nova copia o negrito das outras cabeças")
    checar("em 3 lugares" in resumos[2], "troca de termo em todo o documento", resumos[2])
    checar(resumos[3] == "Reescrevi Cláusula 4ª" and resumos[4] == "Comentei Cláusula 3ª", "reescrever e comentar")
    checar(r.comentarios and r.comentarios[0]["texto"] == "Falta o índice de reajuste.", "comentário devolvido à parte")
    motivos = [f["motivo"] for f in r.falhas]
    checar(len(motivos) == 3 and "não achei “Rua dos Lírios”" in motivos[0], "trecho que não está lá é recusado", motivos)
    checar("não existe" in motivos[1] and "desconhecida" in motivos[2], "bloco inexistente e operação desconhecida")
    checar(ED.precisa_renumerar(r.blocos), "duas cláusulas quartas: precisa renumerar")
    rn = ED.renumerar(r.blocos, 1)
    aceito = B.texto_puro(B.aceito(r.blocos))
    checar(rn and "CLÁUSULA QUINTA – DO FORO" in aceito, "a renumeração faz da antiga quarta a quinta", rn)
    checar(B.texto_puro(B.recusado(r.blocos)) == B.texto_puro(bs), "recusar tudo devolve o documento de antes")

    bs = B.ler(LOCACAO)
    ids = [b.id for b in bs]
    r = ED.aplicar(bs, [{"op": "inserir", "depois_de": ids[7], "blocos": [{"texto": "CLÁUSULA QUARTA – DA MULTA"}]},
                        {"op": "apagar", "bloco": "Cláusula 4ª"}], rodada=1)
    checar(r.aplicadas[1]["ids"] == [ids[14], ids[15]], "“a cláusula 4ª” é a do documento lido, e a cláusula inteira",
           r.aplicadas[1])

    bs = B.ler(LOCACAO)
    ids = [b.id for b in bs]
    r = ED.aplicar(bs, [{"op": "mover", "bloco": "cláusula 1ª", "depois_de": "Cláusula 2ª"}], rodada=1)
    aceito = [b.texto for b in B.aceito(r.blocos)]
    checar(aceito.index("CLÁUSULA PRIMEIRA – DO OBJETO") == aceito.index(
        "Parágrafo único. Findo o prazo, a locação prorroga-se por prazo indeterminado.") + 1,
        "mover a cláusula inteira para depois do último bloco da outra")

    bs = B.ler(LOCACAO)
    ids = [b.id for b in bs]
    r = ED.aplicar(bs, [{"op": "substituir", "bloco": ids[3], "de": "30 (trinta)", "para": "36"}], rodada=1)
    checar(r.aplicadas and r.aplicadas[0]["ids"] == [ids[5]] and "estava em" in r.aplicadas[0]["resumo"],
           "bloco errado com o trecho num bloco só: vai para o bloco certo e diz")
    r = ED.aplicar(bs, [{"op": "substituir", "bloco": ids[5], "de": "30", "para": "36"}], rodada=1, escopo=[ids[3]])
    checar(r.falhas and "fora do trecho" in r.falhas[0]["motivo"], "fora do escopo é recusado")
    r = ED.aplicar(bs, [{"op": "substituir_em_tudo", "de": "prazo", "para": "período"}], rodada=1)
    checar(r.falhas and "não foi pedido" in r.falhas[0]["motivo"], "troca em tudo de palavra comum sem pedido: recusa")
    r = ED.aplicar(bs, [{"op": "substituir_em_tudo", "de": "prazo", "para": "período"}], rodada=1, em_tudo=True)
    checar(r.aplicadas and "3 lugares (2 blocos)" in r.aplicadas[0]["resumo"], "com “em todo o documento”, troca",
           r.aplicadas)
    sel = {"bloco": ids[3], "texto": "Rua das Flores, nº 100"}
    r = ED.aplicar(bs, [{"op": "substituir", "bloco": ids[3], "de": "LOCATÁRIA", "para": "X"}], rodada=1,
                   escopo=[ids[3]], selecao=sel)
    checar(r.falhas, "troca fora do pedaço selecionado do bloco é recusada")
    r = ED.aplicar(bs, [{"op": "reescrever", "bloco": ids[3], "texto": "Avenida Brasil, nº 200"}], rodada=1,
                   escopo=[ids[3]], selecao=sel)
    checar(r.aplicadas and B.por_id(r.blocos)[ids[3]].texto.endswith("Avenida Brasil, nº 200.") and
           "LOCATÁRIA" in B.por_id(r.blocos)[ids[3]].texto, "reescrever com seleção troca só o pedaço selecionado")


if __name__ == "__main__":
    teste_ler_e_escrever()
    teste_reescrever_marcado()
    teste_remendos()
    teste_achar()
    teste_esboco()
    teste_operacoes()
    print()
    if _falhas:
        print(f"{len(_falhas)} falha(s): " + "; ".join(_falhas))
        sys.exit(1)
    print("todos os testes passaram")
