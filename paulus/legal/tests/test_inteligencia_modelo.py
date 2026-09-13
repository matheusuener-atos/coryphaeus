"""
Os extratores que usam o modelo - e o que impede o modelo de mandar sozinho.

Aqui entram as secoes que regra nenhuma resolve: quem e autor e quem e reu
depende de ler a frase. O desenho e sempre o mesmo, e e ele que se testa:

    o modelo aponta  ->  a aritmetica confere a citacao  ->  o conferidor le
    se o trecho sustenta a afirmacao  ->  so entao aquilo vira fato

O modelo destes testes e falso de proposito. Um modelo de verdade demora um
minuto por chamada e responde diferente a cada versao; o que precisa ser
verificado aqui nao e se ele acerta - e se o programa se comporta direito
quando ele acerta, quando ele erra o trecho, e quando ele inverte o papel de
uma parte citando uma frase que existe de verdade.

Rodar: venv\\Scripts\\python.exe tests\\test_inteligencia_modelo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import base as base_mod  # noqa: E402
from inteligencia import portas, roteador  # noqa: E402
from inteligencia.catalogo import Catalogo  # noqa: E402
from inteligencia.guarda import Biblioteca  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:300]}")
        _falhas.append(descricao)


PECA = (
    "[pagina 1]\n"
    "EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 3ª VARA CÍVEL DA COMARCA DE "
    "SÃO PAULO — TJSP\n"
    "CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS\n"
    "COOPERATIVA BRASILEIRA LTDA., pessoa jurídica de direito privado, doravante "
    "denominada CONTRATANTE, e MARIA VASCONCELOS, advogada, doravante CONTRATADA, "
    "celebram o presente instrumento.\n\n"
    "[pagina 2]\n"
    "CLÁUSULA QUARTA — Os honorários são de R$ 15.000,00, pagos em doze parcelas.\n"
)


class ClienteFalso:
    """
    Um modelo de mentira, que responde o que o teste mandou responder.

    Existe para que o teste meça o PROGRAMA e não o modelo: as respostas ficam
    escritas aqui, iguais a cada execução, e assim dá para testar o caso em que
    o modelo erra - que é justamente o que não se consegue provocar de
    propósito num modelo de verdade.
    """

    model = "modelo-de-teste"
    num_ctx = 8192

    def __init__(self, json_=None, textos=None, veredito="SIM") -> None:
        self.json_ = json_
        self.textos = list(textos or [])
        self.veredito = veredito
        self.chamadas: list[str] = []

    def ask(self, pergunta: str, contexto: str = "", *, sistema: str = "",
            ensinado: str = "", **resto) -> str:
        self.chamadas.append(pergunta[:60])
        if "SIM ou NAO" in pergunta or "SIM ou NAO" in sistema:
            alvo = self.veredito
            return alvo(pergunta) if callable(alvo) else alvo
        return self.textos.pop(0) if self.textos else "resposta qualquer"

    def ask_json(self, instrucao: str, contexto: str = "", forma: str = ""):
        self.chamadas.append("json:" + instrucao[:40])
        return self.json_


def biblioteca_nova(tmp: Path):
    bd = base_mod.Base(tmp / "teste.db")
    bd.migrar()
    return bd, Biblioteca(tmp / "conhecimento", bd), Catalogo.carregar()


def test_juizo_por_regra() -> None:
    """Tribunal, vara e comarca estao escritos no alto da folha ha decadas."""
    print("\nde que juizo veio o documento (regra)")
    from inteligencia.extratores import regras_juizo
    from inteligencia.extratores.base import Pedido
    from inteligencia.texto import mapa_de_paginas

    objeto = regras_juizo.extrair(Pedido(texto=PECA, version_id="v",
                                         paginas=mapa_de_paginas(PECA))).objeto
    checar(objeto.get("court") == "TJSP", "o tribunal sai da sigla", objeto)
    checar(objeto.get("state_name") == "São Paulo", "e a sigla diz o estado", objeto)
    checar(objeto.get("court_division", "").startswith("3ª Vara"), "a vara tambem", objeto)
    checar(objeto.get("county") == "São Paulo", "e a comarca", objeto)
    checar(objeto.get("verified") and objeto.get("source", {}).get("page") == 1,
           "com a pagina de onde isso foi lido", objeto.get("source"))

    # Contrato particular nao tem juizo: a secao fica vazia, em vez de inventar.
    vazio = regras_juizo.extrair(Pedido(texto="CONTRATO PARTICULAR DE LOCAÇÃO entre as partes."))
    checar(vazio.objeto == {}, "documento sem juizo nao ganha comarca inventada", vazio.objeto)


def test_partes_com_modelo() -> None:
    print("\nas partes: o modelo aponta, a conferencia decide")
    with tempfile.TemporaryDirectory() as tmp:
        bd, biblioteca, catalogo = biblioteca_nova(Path(tmp))
        arquivo = Path(tmp) / "peca.txt"
        arquivo.write_text(PECA, encoding="utf-8")

        cliente = ClienteFalso(json_=[
            # 1. certa: o trecho existe no documento
            {"nome": "Cooperativa Brasileira Ltda.", "papel": "contratante", "tipo": "empresa",
             "trecho": "COOPERATIVA BRASILEIRA LTDA., pessoa jurídica de direito privado"},
            # 2. inventada: o trecho nao existe em lugar nenhum
            {"nome": "João da Silva", "papel": "reu", "tipo": "pessoa",
             "trecho": "JOÃO DA SILVA, brasileiro, casado, conforme fls. 3 dos autos"},
            # 3. o trecho existe, mas o papel esta invertido - so lendo se pega
            {"nome": "Maria Vasconcelos", "papel": "contratante", "tipo": "pessoa",
             "trecho": "MARIA VASCONCELOS, advogada, doravante CONTRATADA"},
        ])
        # O conferidor reprova a terceira: o trecho fala em CONTRATADA.
        cliente.veredito = lambda pedido: "NAO" if "Maria Vasconcelos é contratante" in pedido else "SIM"

        analise = portas.analisar_documento(biblioteca, catalogo, arquivo, texto=PECA,
                                            paginas=2, secoes=["parties"], client=cliente)
        meta = analise.metadata
        por_nome = {i.dados["name"]: i for i in meta.parties}
        checar(len(meta.parties) == 3, "os tres itens do modelo continuam no metadata", len(meta.parties))

        boa = por_nome.get("Cooperativa Brasileira Ltda.")
        checar(boa and boa.verified and boa.pode_virar_fato,
               "a parte com trecho de verdade vira fato", boa and boa.to_dict())
        checar(boa and boa.source.page == 1 and boa.dados["role"] == "contracting_party",
               "com pagina e papel normalizado", boa and boa.dados)

        inventada = por_nome.get("João da Silva")
        checar(inventada and not inventada.verified,
               "a parte inventada NAO vira fato", inventada and inventada.to_dict())
        checar(inventada and inventada.certainty == "inferred",
               "e cai de explicita para deduzida")

        invertida = por_nome.get("Maria Vasconcelos")
        checar(invertida and not invertida.verified,
               "o papel invertido e reprovado pelo conferidor, mesmo com trecho real",
               invertida and invertida.to_dict())
        checar(invertida and "não sustenta" in invertida.dados.get("verification_note", ""),
               "e o motivo fica escrito", invertida and invertida.dados)

        ficha = meta.secao("parties")
        checar(ficha.item_count == 3 and ficha.unverified_count == 2,
               "a ficha da secao conta quantos nao passaram", ficha.to_dict())
        checar(ficha.model == "modelo-de-teste", "e guarda qual modelo produziu aquilo", ficha.to_dict())

        # E o que o roteador faz com isso: uma parte conferida responde.
        pacote = roteador.resolver("quem são as partes?", [meta], em_foco=True)
        checar(pacote.responde_sozinho and len(pacote.fatos) == 1,
               "so a parte conferida entra na resposta", pacote.porque)
        checar(pacote.fatos[0].valor == "Cooperativa Brasileira Ltda.",
               "e e a certa", pacote.fatos[0].to_dict())
        bd.fechar()


def test_resumo_e_nivel_1() -> None:
    print("\no resumo: a unica secao que nao e fato")
    with tempfile.TemporaryDirectory() as tmp:
        bd, biblioteca, catalogo = biblioteca_nova(Path(tmp))
        arquivo = Path(tmp) / "peca.txt"
        arquivo.write_text(PECA, encoding="utf-8")

        cliente = ClienteFalso(textos=[
            "Contrato de prestação de serviços advocatícios entre a Cooperativa Brasileira e a advogada Maria Vasconcelos.",
            "Contrato de honorários. A cooperativa contrata a advogada. O valor é de R$ 15.000,00 em doze parcelas.",
        ])
        analise = portas.analisar_documento(biblioteca, catalogo, arquivo, texto=PECA,
                                            paginas=2, secoes=["summary"], client=cliente)
        meta = analise.metadata
        checar(meta.summary.get("one_line", "").startswith("Contrato de prestação"),
               "o resumo de uma linha ficou guardado", meta.summary)
        checar(meta.summary.get("extraction_method") == "model-inference",
               "declarado como leitura do modelo, nao trecho do documento", meta.summary)
        checar(meta.summary.get("verified") is False, "e nunca como conferido")

        pacote = roteador.resolver("do que se trata este documento?", [meta], em_foco=True)
        checar(pacote.nivel == roteador.METADATA_E_RESUMO, "a pergunta pelo assunto vira nivel 1",
               pacote.trace)
        checar(pacote.inferencia, "e o pacote avisa que aquilo e leitura, nao fato")
        checar("leitura do assistente" in pacote.prompt("do que se trata?"),
               "o proprio prompt diz isso ao modelo", pacote.prompt("x")[:120])

        # Sem documento em foco, resumir nao e resposta de metadata.
        aberto = roteador.resolver("resuma", [meta, meta], em_foco=False)
        checar(aberto.fallback, "com o acervo inteiro, resumir escala", aberto.porque)
        bd.fechar()


def test_sem_assistente_ligado() -> None:
    """A camada tem de continuar util com o modelo desligado."""
    print("\ncom o assistente desligado")
    with tempfile.TemporaryDirectory() as tmp:
        bd, biblioteca, catalogo = biblioteca_nova(Path(tmp))
        arquivo = Path(tmp) / "peca.txt"
        arquivo.write_text(PECA, encoding="utf-8")

        analise = portas.analisar_documento(biblioteca, catalogo, arquivo, texto=PECA, paginas=2)
        meta = analise.metadata
        checar("parties" in analise.puladas and "summary" in analise.puladas,
               "partes e resumo ficam para quando o modelo estiver ligado", analise.puladas)
        checar(meta.secao("parties").status == "missing",
               "a secao fica faltando, e nao falhada - faltando o roteador escala")
        checar("case" in analise.rodadas and "jurisdiction" in analise.rodadas,
               "as secoes de regra rodam do mesmo jeito", analise.rodadas)
        # Este texto de teste e ambiguo de proposito: tem cabecalho de peticao
        # E titulo de contrato. A regra empata, e empate vira "nao sei" - com o
        # modelo desligado, ninguem desempata, e o programa diz isso.
        checar(meta.classification.get("document_type") == "other"
               and meta.classification.get("certainty") == "unknown",
               "texto ambiguo sem modelo fica sem tipo, em vez de chutar", meta.classification)
        checar(meta.classification.get("origem") == "regra", "dizendo que foi a regra que tentou")

        from inteligencia.extratores import llm_classificador
        from inteligencia.extratores.base import Pedido

        claro = llm_classificador.extrair(Pedido(
            texto="CONTRATO DE COMPRA E VENDA DE IMÓVEL, entre as partes abaixo qualificadas.")).objeto
        checar(claro["document_type"] == "contract" and claro["document_type_br"] == "compra_e_venda",
               "e um documento sem ambiguidade e classificado sem modelo nenhum", claro)
        checar(claro["verified"], "com evidencia: foi o vocabulario do proprio documento que decidiu")

        pacote = roteador.resolver("quem são as partes?", [meta], em_foco=True)
        checar(pacote.fallback and "metadata" in pacote.porque,
               "perguntar pelas partes cai no caminho de hoje", pacote.porque)
        bd.fechar()


def test_conferidor_nao_promove() -> None:
    """O conferidor so pode rebaixar - nunca dar segunda chance a alucinacao."""
    print("\no conferidor so rebaixa")
    from inteligencia.esquema import Item
    from inteligencia.extratores import verificador

    reprovado = Item(id="x", dados={"name": "Fulano", "role_br": "autor"},
                     quote="nada disto existe no documento", certainty="inferred",
                     verified=False, produced_by="teste")
    cliente = ClienteFalso(veredito="SIM")
    rebaixados = verificador.conferir_todos(cliente, [reprovado], "parties")
    checar(rebaixados == 0 and not reprovado.verified,
           "item ja reprovado pela aritmetica continua reprovado, mesmo com o conferidor dizendo SIM")
    checar(not cliente.chamadas, "e nem se gasta uma chamada de modelo com ele")

    sem_cliente = Item(id="y", dados={"name": "Beltrano"}, quote="um trecho qualquer do documento",
                       certainty="explicit", verified=True, produced_by="teste")
    verificador.conferir_todos(None, [sem_cliente], "parties")
    checar(sem_cliente.verified, "sem conferidor, o que a aritmetica aceitou continua aceito")



def test_trocar_o_modelo_envelhece_so_o_que_ele_fez() -> None:
    """
    Trocar de modelo nao pode obrigar a reanalisar o acervo inteiro.

    O que o modelo produziu envelhece; o que a regra produziu, nao - ela nao
    mudou. E o caso silencioso importa: `ollama pull` no mesmo nome traz pesos
    diferentes com o mesmo rotulo, e sem o digest o extraido pelo modelo
    antigo passaria por atual para sempre.
    """
    print("\ntrocar o modelo envelhece so o que ele fez")
    with tempfile.TemporaryDirectory() as tmp:
        bd, biblioteca, catalogo = biblioteca_nova(Path(tmp))
        arquivo = Path(tmp) / "peca.txt"
        arquivo.write_text(PECA, encoding="utf-8")

        class ComDigest(ClienteFalso):
            impressao = "digest-antigo"

            def digest(self, model: str = "") -> str:
                return self.impressao

        cliente = ComDigest(json_=[], textos=["uma linha", "tres linhas"])
        primeira = portas.analisar_documento(biblioteca, catalogo, arquivo, texto=PECA,
                                             paginas=2, client=cliente)
        checar("summary" in primeira.rodadas and "case" in primeira.rodadas,
               "a primeira analise roda tudo", sorted(primeira.rodadas))
        checar(primeira.metadata.secao("summary").model_digest == "digest-antigo",
               "e grava o digest de quem produziu cada secao",
               primeira.metadata.secao("summary").to_dict())
        checar(primeira.metadata.secao("case").model is None,
               "secao de regra nao anota modelo nenhum", primeira.metadata.secao("case").to_dict())

        segunda = portas.analisar_documento(biblioteca, catalogo, arquivo, texto=PECA,
                                            paginas=2, client=cliente)
        checar(segunda.rodadas == [], "nada mudou, nada e refeito", segunda.rodadas)

        cliente.impressao = "digest-novo"     # ollama pull, mesmo nome
        terceira = portas.analisar_documento(biblioteca, catalogo, arquivo, texto=PECA,
                                             paginas=2, client=cliente)
        checar(sorted(terceira.rodadas) == ["parties", "summary"],
               "trocar os pesos refaz so o que o modelo tinha feito", terceira.rodadas)
        checar(terceira.metadata.secao("dates").status == "ok"
               and terceira.metadata.secao("dates").generated_at
               == primeira.metadata.secao("dates").generated_at,
               "as secoes de regra ficam intactas, inclusive a hora")
        bd.fechar()


def main() -> int:
    print("=" * 55)
    print("  PAULUS - extratores com modelo (passo 5)")
    print("=" * 55)
    test_juizo_por_regra()
    test_partes_com_modelo()
    test_resumo_e_nivel_1()
    test_sem_assistente_ligado()
    test_conferidor_nao_promove()
    test_trocar_o_modelo_envelhece_so_o_que_ele_fez()

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
