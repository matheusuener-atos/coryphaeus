"""
O que a bateria de 30 perguntas na IA da nuvem pegou (02/10/2026), sem
modelo e sem nuvem: o que é regra e conferência, em código.

  - a instrução da nuvem é a dela: a data de hoje, o direito em tese
    liberado, e nunca dizer que fez o que não fez;
  - a triagem só vale com o que existe: nome de documento da lista e artigo
    que está na base de leis;
  - a conferência vai à base de leis: o artigo que existe fica e vira fonte;
    o que não existe, o parágrafo que o artigo não tem e o texto entre aspas
    que o artigo não diz levam a frase inteira;
  - CPF com a pontuação do documento sai mascarado mesmo com o dígito errado;
  - pedido de mudança em qualquer posição do verbo, "X está errado, o certo é
    Y", a ação depois da pergunta, "e salve no editor", o que fica fora do
    alcance e "você consegue...?";
  - "crie uma tarefa" não chama o agente de cadastro;
  - "envie a procuração por e-mail para..." é e-mail com anexo;
  - a troca dita na frase é feita por regra no editor, palavra inteira.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_bateria_nuvem.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-bateria-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _leis():
    """Os códigos que vêm com o PAULUS, numa base de teste."""
    import leis as leis_mod
    import material as material_mod
    from base import Base
    from biblioteca import nativo

    base = Base(TMP / "leis.db")
    L = leis_mod.Leis(base)
    m = material_mod.Material(TMP / "material")
    antes = os.environ.pop("PAULUS_SEM_AVISOS", None)
    try:
        nativo.instalar(L, m, TMP / "leis")
    finally:
        if antes is not None:
            os.environ["PAULUS_SEM_AVISOS"] = antes
    return L, base


def test_instrucao() -> None:
    print("\na instrução da nuvem")
    import instrucao_nuvem

    texto = instrucao_nuvem.instrucao(date(2026, 10, 2))
    checar("sexta-feira, 2 de outubro de 2026 (02/10/2026)" in texto, "diz a data de hoje", texto[:200])
    checar("consultoria" not in texto and "NÃO conhece a tela" not in texto, "sem as travas do 3B")
    checar("nunca diga que fez" in texto, "nunca dizer que fez o que não fez")
    checar("Editor de texto" in texto, "conhece as telas do programa")
    m = instrucao_nuvem.montar_mensagens("qual o prazo?", "LEI — ...", ensinado="Regra da casa X", dia=date(2026, 10, 2))
    checar(m[0]["role"] == "system" and "Regra da casa X" in m[0]["content"] and "Pergunta: qual o prazo?" in m[-1]["content"],
           "o que o escritório ensinou vai na instrução, a pergunta no fim")


def test_triagem(L) -> None:
    print("\na triagem, conferida")
    import triagem

    nomes = ["COMPRA E VENDA - WANDERSON X VALTER UENER R$ 200.000,00.pdf", "Procuraçao COOBRAMEX x Matheus.docx"]
    t = triagem.conferir({"assunto": "documentos", "documentos": ["compra e venda - wanderson x valter uener r$ 200.000,00.pdf",
                                                                  "Contrato que não existe.pdf"],
                          "dispositivos": [{"codigo": "cpc", "artigo": "335"}, {"codigo": "cpc", "artigo": "99999"},
                                           {"codigo": "xyz", "artigo": "1"}]}, nomes, L)
    checar(t["documentos"] == [nomes[0]], "o nome vale pela lista (sem caixa); o que não existe some", t["documentos"])
    checar(t["dispositivos"] == [("cpc", "335")], "o artigo que não está na base some", t["dispositivos"])
    t = triagem.conferir({"assunto": "lei", "documentos": [nomes[1]], "dispositivos": [{"codigo": "cc", "artigo": "art. 205"}]},
                         nomes, L)
    checar(t["assunto"] == "lei" and t["documentos"] == [] and t["dispositivos"] == [("cc", "205")],
           "pergunta de lei não lê documento; 'art. 205' vira 205", t)
    checar(triagem.conferir({"assunto": "outra coisa"}, nomes, L)["assunto"] == "documentos",
           "assunto desconhecido vira 'documentos' (o caminho de sempre)")


def test_conferencia(L) -> None:
    print("\na conferência na base de leis")
    import citacoes

    resposta = ("O Código Civil de 2002, em seu art. 205, estabelece que a prescrição ocorre em dez anos. "
                "O CPC de 2015, em seu artigo 183, § 2º, estabelece que \"Quando a lei não fixar prazo especial, o "
                "prazo será de 5 dias para a Fazenda\". Já o art. 9999 do CPC diz outra coisa. "
                "A contestação vai no prazo do art. 335 do CPC.")
    rev = citacoes.revisar(resposta, [], leis=L, pergunta="prazo de prescrição")
    checar("art. 205" in rev.texto and "em seu, estabelece" not in rev.texto, "o artigo que existe fica, inteiro", rev.texto)
    checar("9999" not in rev.texto and "5 dias para a Fazenda" not in rev.texto,
           "artigo que não existe e aspas que o artigo não diz levam a frase", rev.texto)
    checar(sorted((a["codigo"], a["numero"]) for a in rev.conferidas) == [("cc", "205"), ("cpc", "335")],
           "os conferidos viram fonte", [(a["codigo"], a["numero"]) for a in rev.conferidas])
    rev = citacoes.revisar("O prazo está no art. 1.003, § 9º, do CPC.", [], leis=L)
    checar(not rev.texto.strip() and rev.removidas, "parágrafo que o artigo não tem leva a frase", rev.removidas)
    rev = citacoes.revisar("Conforme a Lei 8.038/1990, o prazo é de cinco dias.", [], leis=L)
    checar("8.038" in rev.texto, "lei que a base não tem fica: não dá para dizer que não existe", rev.texto)
    rev = citacoes.revisar("Diz o art. 205 do CC.", [], leis=None)
    checar("205" not in rev.texto, "sem a base (o 3B daqui), a regra de antes vale", rev.texto)


def test_camada_lei(L) -> None:
    print("\na camada LEI com os artigos da triagem")
    import material as material_mod
    from biblioteca import camadas

    m = material_mod.Material(TMP / "material")
    feitas = camadas.montar(m, L, "qual o prazo para contestar?", [], dispositivos=[("cpc", "335"), ("cpc", "231")],
                            generoso=True)
    checar(len(feitas.trechos) == 2 and "15 (quinze) dias" in feitas.texto, "os artigos entram com o texto", feitas.texto[:200])
    pouco = camadas.montar(m, L, "qual o prazo para contestar?", [], dispositivos=[("cpc", "335"), ("cpc", "231"),
                                                                                   ("cpc", "219")])
    checar(len(pouco.trechos) <= camadas.MAX_ARTIGOS, "no 3B, os tetos de antes", len(pouco.trechos))


def test_mascara() -> None:
    print("\na máscara")
    import nuvem

    m = nuvem.Mascara()
    t = m.aplicar("cadastrado no CPF/MF nº 057.648.816-38, e o número 12345678901 solto")
    checar("057.648.816-38" not in t and "[CPF 1]" in t, "CPF com a pontuação do documento sai, mesmo com dígito errado", t)
    checar("12345678901" in t, "número solto, sem pontuação nem rótulo, fica", t)


def test_regras() -> None:
    print("\nas regras da conversa")
    import email_pela_conversa
    import intencao as i

    pedido = "SEMA está errado. O certo é SEMAS - corrija no documento pra mim"
    checar(i.pedido_de_mudanca(pedido) and i.trocas_do_pedido(pedido) == [("SEMA", "SEMAS")],
           "o verbo no fim, e o 'X está errado, o certo é Y'", i.trocas_do_pedido(pedido))
    checar(i.trocas_do_pedido("troque “Sr. João” por “Dr. João”") == [("Sr. João", "Dr. João")], "troque X por Y, com aspas")
    checar(not i.pedido_de_mudanca("Você consegue alterar documentos pra mim?"), "pergunta de capacidade não é pedido")
    checar(not i.pedido_de_mudanca("A multa muda depois de 30 dias?"), "'muda' numa pergunta é 3a pessoa")
    acao, resto = i.acao_anexa("A procuração da COOBRAMEX está vencida? Se estiver, crie uma tarefa para renovar.")
    checar(acao is not None and acao.tipo == "tarefa" and resto == "A procuração da COOBRAMEX está vencida?"
           and "COOBRAMEX" in acao.titulo, "a ação depois da pergunta vira cartão; a pergunta segue sem ela",
           (acao and acao.titulo, resto))
    checar(i.acao_anexa("Qual o valor do contrato?")[0] is None, "pergunta sem ação, nada")
    checar(i.salvar_no_editor("resuma a procuração da COOBRAMEX e salve no editor") == (True, "resuma a procuração da COOBRAMEX"),
           "'e salve no editor' sai da pergunta")
    checar(bool(i.fora_do_alcance("Rode o script tools/demo/roteiro.py e me mostre a tabela")), "rodar script: fora do alcance")
    checar(i.capacidade_perguntada("Você consegue alterar documentos pra mim?").startswith("Sim."),
           "'você consegue alterar documentos?' responde a pergunta")
    checar(i.capacidade_perguntada("O que você consegue fazer?") == "", "a pergunta geral fica com a lista")
    checar(i.ler("você consegue me dizer qual o valor do contrato?").tipo == "documentos",
           "'você consegue me dizer qual...' é pedido, não pergunta sobre o programa")
    checar(i.cita_lei("Quais poderes precisam constar na procuração, segundo o art. 105 do CPC?")
           and not i.cita_lei("qual o valor do contrato?"), "a frase que cita lei")
    e = email_pela_conversa.ler_pedido("envie a procuração da COOBRAMEX por e-mail para teste@exemplo.com")
    checar(e and e["acao"] == "escrever" and e["email"] == "teste@exemplo.com" and e["documento"] == "a procuração da COOBRAMEX",
           "enviar documento por e-mail: o e-mail novo com o documento", e)
    checar(i.ler("envie a procuração da COOBRAMEX por e-mail para teste@exemplo.com").tipo == "email", "e a conversa lê como e-mail")


def test_agente() -> None:
    print("\na escolha do agente")
    import agente_na_conversa as ag

    class Agente:
        slug = "extrator"
        nome = "Extrator de dados para cadastro"
        descricao = ""
        precisa_revisao = False
        quando_usar = {"exemplos": ["Cadastre o Sr. *"], "palavras": ["cadastrar", "crie", "cadastro"]}

    checar(ag.escolher("crie uma tarefa: renovar a procuração da COOBRAMEX", [Agente()]).agente is None,
           "'crie' sozinho não chama o agente")
    checar(ag.escolher("crie o cadastro e depois vamos cadastrar o João", [Agente()]).agente is not None,
           "duas palavras dele, sim")


def test_editor_por_regra() -> None:
    print("\no editor troca por regra, palavra inteira")
    import api

    id_ = api.estado.documentos.criar("Procuração", "texto",
                                      "<p>Secretaria Estadual de Meio Ambiente – SEMA do estado do Pará; SEMAS já certa; "
                                      "e de novo a SEMA.</p>", None)
    r = api.documentos_assistente(id_, api.PedidoAoAssistente(pedido="SEMA está errado. O certo é SEMAS - corrija no documento"))
    checar(r.get("trocas") == [{"de": "SEMA", "para": "SEMAS"}] and r.get("ocorrencias") == 2,
           "duas ocorrências de SEMA, e SEMAS não conta", r)
    checar(api._ocorrencias("a SEMA e a SEMAS", "SEMA") == 1, "a contagem é por palavra inteira")


def main() -> int:
    print("=" * 55)
    print("  Bateria da nuvem: o que é regra e conferência")
    print("=" * 55)
    base = None
    try:
        test_instrucao()
        L, base = _leis()
        test_triagem(L)
        test_conferencia(L)
        test_camada_lei(L)
        test_mascara()
        test_regras()
        test_agente()
        test_editor_por_regra()
    finally:
        if base is not None:
            try:
                base.fechar()
            except Exception:  # noqa: BLE001
                pass
        shutil.rmtree(TMP, ignore_errors=True)
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
