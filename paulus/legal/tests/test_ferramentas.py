"""
Testes das ferramentas da conversa: catálogo, contrato JSON e confirmação.

A conversa passa a cadastrar cliente, anotar compromisso e preparar NFS-e.
O que pode dar errado aqui custa caro — uma ficha com o nome que ninguém
disse, um CPF torto gravado, uma nota "emitida" sem o sim —, então os testes
cobrem as garantias, não só o caminho feliz:

  - o catálogo declara as quatro ferramentas, e todas exigem confirmação
  - o JSON do modelo é conferido: tipo, ferramenta e parâmetros; o que não
    segue o contrato é recusado, parâmetro desconhecido cai
  - CPF e CNPJ pelo dígito verificador; valor em centavos; data em ISO
  - a regra acha a ação e os campos inequívocos; o modelo só é chamado quando
    falta um obrigatório e a frase tem com o que preencher
  - o que o modelo devolve e não está na frase é invenção e não entra
  - pela API: a proposta não grava nada; só o sim grava; a NFS-e confere e
    não emite; com a regra bastando, o modelo nem é chamado
  - depois de uma resposta tirada de um ou dois documentos, a conversa
    oferece mostrá-los — uma vez por documento — e só mostra com o clique

Não precisa do Ollama: o modelo é trocado por respostas prontas. Tudo que o
teste cria é apagado no fim.

    python tests/test_ferramentas.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import ferramentas  # noqa: E402
import intencao  # noqa: E402

HOJE = date(2026, 9, 11)  # sexta-feira
CPF_BOM = "529.982.247-25"
CNPJ_BOM = "11.222.333/0001-81"

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe="") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe != "":
            print(f"         {str(detalhe)[:400]}")
        _falhas.append(descricao)


def recusa(funcao, *args) -> str:
    """A mensagem do ValueError, ou vazio quando não recusou."""
    try:
        funcao(*args)
    except ValueError as exc:
        return str(exc) or "recusou"
    return ""


# ---------------------------------------------------------------- catálogo


def test_catalogo() -> None:
    print("\no catálogo")
    cat = ferramentas.CATALOGO_FERRAMENTAS
    checar(set(cat) == {"cadastrar_cliente", "criar_compromisso", "emitir_nfse", "exibir_documento"},
           "as quatro ferramentas", list(cat))
    checar(cat["exibir_documento"]["modulo"] == "acervo", "exibir_documento -> acervo")
    checar(cat["cadastrar_cliente"]["modulo"] == "cadastros", "cadastrar_cliente -> cadastros")
    checar(cat["criar_compromisso"]["modulo"] == "agenda", "criar_compromisso -> agenda")
    checar(cat["emitir_nfse"]["modulo"] == "escritorio", "emitir_nfse -> escritorio")
    checar(cat["emitir_nfse"]["exige_confirmacao"] is True, "emitir_nfse exige confirmação")
    checar(all(f["exige_confirmacao"] for f in cat.values()), "e todas as outras também")
    checar(cat["emitir_nfse"]["disponivel"] is False, "a NFS-e ainda não emite de verdade")
    checar(ferramentas.POR_PROPOSTA == {"cadastro": "cadastrar_cliente", "agenda": "criar_compromisso",
                                        "nota": "emitir_nfse", "exibir": "exibir_documento"},
           "cada proposta da tela aponta uma ferramenta")


def test_prompt() -> None:
    print("\no prompt das ferramentas")
    p = ferramentas.obter_prompt_ferramentas(HOJE)
    checar(all(nome in p for nome in ferramentas.CATALOGO_FERRAMENTAS), "nomeia cada ferramenta")
    checar(all(par in p for f in ferramentas.CATALOGO_FERRAMENTAS.values() for par in f["parametros"]),
           "e cada parâmetro")
    checar('"tipo": "acao"' in p and '"tipo": "resposta"' in p and '"parametros"' in p and '"mensagem"' in p,
           "ensina o contrato JSON")
    checar("2026-09-11" in p and "sexta-feira" in p, "diz que dia é hoje, para datas relativas")
    checar("invente" in p, "proíbe inventar")


# ---------------------------------------------------------------- contrato


def test_contrato_json() -> None:
    print("\no contrato JSON")
    bom = json.dumps({"tipo": "acao", "ferramenta": "cadastrar_cliente",
                      "parametros": {"nome": " Maria   Souza ", "documento": "52998224725", "cor": "azul"},
                      "mensagem": "Cadastrar Maria"})
    c = ferramentas.interpretar_resposta(bom)
    checar(c.tipo == "acao" and c.ferramenta == "cadastrar_cliente", "ação lida", c)
    checar(c.parametros.get("nome") == "Maria Souza", "texto com espaço normalizado", c.parametros)
    checar(c.parametros.get("documento") == CPF_BOM, "CPF formatado", c.parametros)
    checar("cor" not in c.parametros, "parâmetro desconhecido cai")

    c = ferramentas.interpretar_resposta("Claro! Aqui está:\n" + bom + "\nEspero ter ajudado.")
    checar(c.ferramenta == "cadastrar_cliente", "JSON com texto em volta ainda é lido")

    c = ferramentas.interpretar_resposta({"tipo": "resposta", "ferramenta": None, "parametros": {},
                                          "mensagem": "Isso não é uma ação."})
    checar(c.tipo == "resposta" and c.mensagem == "Isso não é uma ação.", "resposta sem ferramenta")

    for bruto, porque in (
        ('{"tipo": "executar", "ferramenta": "cadastrar_cliente"}', "tipo fora do contrato"),
        ('{"tipo": "acao", "ferramenta": "apagar_tudo", "parametros": {}}', "ferramenta que não existe"),
        ('{"tipo": "acao", "ferramenta": "cadastrar_cliente", "parametros": ["nome"]}', "parametros que não é objeto"),
        ("não sei", "texto sem JSON"),
        ("[1, 2]", "JSON que não é objeto"),
        ("", "nada"),
    ):
        checar(bool(recusa(ferramentas.interpretar_resposta, bruto)), f"recusa: {porque}")
    checar(isinstance(ferramentas.ContratoInvalido("x"), ValueError), "contrato inválido é ValueError")

    c = ferramentas.interpretar_resposta({"tipo": "acao", "ferramenta": "cadastrar_cliente",
                                          "parametros": {"nome": "Ana", "documento": "111.111.111-11"}})
    checar("documento" not in c.parametros and "documento" in c.erros, "CPF que não confere vai para erros", c)

    c = ferramentas.interpretar_resposta({"tipo": "acao", "ferramenta": "emitir_nfse",
                                          "parametros": {"cliente": "Ana", "valor": 1500, "data": "2026-09-20"}})
    checar(c.parametros.get("valor") == 150000, "1500 do modelo são reais, não centavos", c.parametros)
    checar(c.parametros.get("data") == "2026-09-20", "data ISO")


def test_normalizar() -> None:
    print("\nnormalizar")
    checar(ferramentas.cpf_ou_cnpj("529.982.247-25") == CPF_BOM, "CPF válido")
    checar(bool(recusa(ferramentas.cpf_ou_cnpj, "529.982.247-26")), "CPF com dígito errado é recusado")
    checar(bool(recusa(ferramentas.cpf_ou_cnpj, "000.000.000-00")), "CPF de números repetidos é recusado")
    checar(ferramentas.cpf_ou_cnpj("11222333000181") == CNPJ_BOM, "CNPJ válido")
    checar(bool(recusa(ferramentas.cpf_ou_cnpj, "11.222.333/0001-82")), "CNPJ com dígito errado é recusado")
    checar(bool(recusa(ferramentas.cpf_ou_cnpj, "1234")), "número curto é recusado")

    for bruto, esperado in (("R$ 1.500,00", 150000), ("1500", 150000), ("1.500", 150000),
                            ("1500.50", 150050), ("1500,5", 150050), ("2 mil", 200000),
                            ("1,500.00", 150000), (150000, 150000), ("R$ 0,99", 99)):
        checar(ferramentas.centavos_de(bruto) == esperado, f"valor {bruto!r} -> {esperado}",
               ferramentas.centavos_de(bruto))
    checar(bool(recusa(ferramentas.centavos_de, "sem valor")), "valor sem número é recusado")

    checar(ferramentas.telefone("11987654321") == "(11) 98765-4321", "celular com DDD")
    checar(ferramentas.telefone("+55 (11) 3333-4444") == "(11) 3333-4444", "fixo com +55")
    checar(bool(recusa(ferramentas.telefone, "98765-4321")), "telefone sem DDD é recusado")
    checar(ferramentas.email("Joao@Exemplo.com.br") == "joao@exemplo.com.br", "e-mail em minúscula")
    checar(bool(recusa(ferramentas.email, "joao@")), "e-mail torto é recusado")
    checar(ferramentas.data_iso("20/09/2026") == "2026-09-20", "data com barra")
    checar(ferramentas.data_iso("amanhã", HOJE) == "2026-09-12", "data por extenso, a partir de hoje")
    checar(bool(recusa(ferramentas.data_iso, "2026-02-30")), "data que não existe é recusada")
    checar(ferramentas.hora("9h") == "09:00" and ferramentas.hora("13:40") == "13:40", "horas")

    limpos, erros = ferramentas.normalizar("criar_compromisso", {"titulo": "Reunião", "data": "20/09/2026",
                                                                 "hora": "25:00", "xyz": 1})
    checar(limpos == {"titulo": "Reunião", "data": "2026-09-20"} and "hora" in erros,
           "normalizar separa o que passou do que não passou", (limpos, erros))
    checar(ferramentas.faltando("emitir_nfse", {"cliente": "Ana"}) == ["valor"], "faltando aponta o obrigatório")


# ------------------------------------------------------------ a regra primeiro


def test_regra_le_o_cadastro() -> None:
    print("\ncadastro por regra")
    l = intencao.ler("cadastre o cliente João da Silva, CPF 529.982.247-25, telefone (11) 98765-4321, "
                     "email joao@exemplo.com", HOJE)
    checar(l.tipo == "cadastro", "a frase vira cadastro", l.tipo)
    checar(l.campos == {"nome": "João da Silva", "documento": CPF_BOM, "telefone": "(11) 98765-4321",
                        "email": "joao@exemplo.com", "endereco": "", "observacao": ""}, "todos os campos", l.campos)
    checar(not l.precisa_modelo and not l.falta, "a regra bastou: sem modelo")

    l = intencao.ler("novo cliente: Cooperativa Agro Ltda, CNPJ 11.222.333/0001-81, endereço Rua das Flores, 120", HOJE)
    checar(l.tipo == "cadastro" and l.campos["nome"] == "Cooperativa Agro Ltda", "\"novo cliente:\" com CNPJ", l.campos)
    checar(l.campos["documento"] == CNPJ_BOM and l.campos["endereco"] == "Rua das Flores, 120", "CNPJ e endereço", l.campos)

    l = intencao.ler("cadastre a cliente maria souza", HOJE)
    checar(l.campos["nome"] == "Maria Souza", "nome em minúscula ganha maiúscula", l.campos)

    l = intencao.ler("cadastre o Pedro Alves com cpf 111.111.111-11", HOJE)
    checar(l.tipo == "cadastro" and "não confere" in l.falta, "CPF torto aparece como problema no cartão", l.falta)

    l = intencao.ler("cadastre um cliente", HOJE)
    checar(l.falta and not l.precisa_modelo, "sem nome e sem mais nada: diz o que falta, sem chamar o modelo", l)
    l = intencao.ler("cadastre um cliente com cpf 529.982.247-25 que se chama bruno", HOJE)
    checar(not l.campos["nome"] and l.precisa_modelo, "nome que a regra não lê: vale chamar o modelo", l.campos)

    for pergunta in ("o cliente cadastrado tem CPF?", "como cadastrar um cliente?",
                     "cadastre uma reunião amanhã às 10h", "quais clientes têm CNPJ?"):
        checar(intencao.ler(pergunta, HOJE).tipo != "cadastro", f"não é cadastro: {pergunta!r}",
               intencao.ler(pergunta, HOJE).tipo)


def test_regra_le_a_nota() -> None:
    print("\nNFS-e por regra")
    l = intencao.ler("emita uma NFS-e para a Cooperativa Agro de R$ 1.500,00 referente à consultoria de março",
                     HOJE, cadastros=["Cooperativa Agro"])
    checar(l.tipo == "nota", "a frase vira nota", l.tipo)
    checar(l.campos["cliente"] == "Cooperativa Agro" and l.campos["valor"] == 150000, "cliente e valor", l.campos)
    checar(l.campos["descricao"] == "consultoria de março", "descrição", l.campos)

    l = intencao.ler("emita uma nota fiscal para João da Silva no valor de 2.300 reais", HOJE)
    checar(l.campos["cliente"] == "João da Silva" and l.campos["valor"] == 230000,
           "cliente fora de Cadastros e \"no valor de ... reais\"", l.campos)

    l = intencao.ler("gere uma nfse de R$ 800", HOJE)
    checar(l.tipo == "nota" and "cliente" in l.falta and not l.precisa_modelo, "sem cliente: diz o que falta", l)

    checar(intencao.ler("crie uma nota sobre a reunião de ontem", HOJE).tipo != "nota",
           "\"nota\" sem valor é anotação, não nota fiscal")
    checar(intencao.ler("qual nota fiscal foi emitida em março?", HOJE).tipo != "nota",
           "pergunta sobre nota não vira emissão")


def test_regra_da_agenda() -> None:
    print("\nagenda: quando o modelo é chamado")
    l = intencao.ler("marque uma reunião às 14h", HOJE)
    checar(l.falta and not l.precisa_modelo, "só a hora, sem dia: não pergunta ao modelo (ele inventaria)", l)
    l = intencao.ler("marque uma reunião com o cliente", HOJE)
    checar(not l.precisa_modelo, "sem indício de data: não pergunta")
    l = intencao.ler("marque uma reunião daqui a duas semanas", HOJE)
    checar(l.falta and l.precisa_modelo, "data que a regra não lê: pergunta", l)
    l = intencao.ler("anote uma reunião dia 20/09 às 13:40", HOJE)
    checar(l.campos.get("data") == "2026-09-20" and not l.precisa_modelo, "com data: a regra basta")


# ------------------------------------------------------------ com o modelo


def test_completar_com_modelo() -> None:
    print("\no modelo completa, e não inventa")
    frase = "cadastre um cliente com cpf 529.982.247-25 que se chama bruno pereira"

    def modelo(resposta):
        chamadas = []

        def perguntar(instrucao, sistema):
            chamadas.append((instrucao, sistema))
            if isinstance(resposta, Exception):
                raise resposta
            return resposta
        return perguntar, chamadas

    l = intencao.ler(frase, HOJE)
    perguntar, chamadas = modelo({"tipo": "acao", "ferramenta": "cadastrar_cliente",
                                  "parametros": {"nome": "Bruno Pereira", "documento": "529.982.247-25"}})
    ajuda = ferramentas.completar_com_modelo(l, frase, perguntar, HOJE)
    checar(ajuda == ["nome"] and l.campos["nome"] == "Bruno Pereira", "o nome que estava na frase entra", (ajuda, l.campos))
    checar(not l.falta, "e o que faltava deixa de faltar", l.falta)
    checar(chamadas and "cadastrar_cliente" in chamadas[0][1], "o modelo recebeu o prompt das ferramentas")

    l = intencao.ler(frase, HOJE)
    perguntar, _ = modelo({"tipo": "acao", "ferramenta": "cadastrar_cliente",
                           "parametros": {"nome": "Carlos Andrade", "email": "carlos@x.com"}})
    ajuda = ferramentas.completar_com_modelo(l, frase, perguntar, HOJE)
    checar(ajuda == [] and not l.campos["nome"] and not l.campos["email"], "nome e e-mail inventados não entram", l.campos)
    checar(l.falta, "e o cartão continua dizendo o que falta")

    l = intencao.ler(frase, HOJE)
    perguntar, _ = modelo({"tipo": "acao", "ferramenta": "emitir_nfse", "parametros": {"cliente": "bruno pereira"}})
    checar(ferramentas.completar_com_modelo(l, frase, perguntar, HOJE) == [], "o modelo não troca a ferramenta da regra")

    for resposta, porque in ((ConnectionError("Ollama fechado"), "modelo fora do ar"),
                             ("isso não é JSON", "JSON torto"),
                             ({"tipo": "resposta", "mensagem": "não entendi"}, "o modelo diz que não é ação")):
        l = intencao.ler(frase, HOJE)
        perguntar, _ = modelo(resposta)
        checar(ferramentas.completar_com_modelo(l, frase, perguntar, HOJE) == [] and l.falta,
               f"{porque}: o cartão fica como a regra fez")

    frase = "marque uma reunião daqui a duas semanas"
    l = intencao.ler(frase, HOJE)
    perguntar, _ = modelo('{"tipo": "acao", "ferramenta": "criar_compromisso", '
                          '"parametros": {"titulo": "Reunião", "data": "2026-09-25"}, "mensagem": "ok"}')
    ajuda = ferramentas.completar_com_modelo(l, frase, perguntar, HOJE)
    checar(ajuda == ["data"] and l.campos["data"] == "2026-09-25" and not l.falta,
           "a data que a regra não leu vem do modelo", (ajuda, l.campos, l.falta))


# ------------------------------------------------------- exibir documento


class _Doc:
    def __init__(self, name, path, text="", pages=0):
        self.name, self.path, self.text, self.pages = name, path, text, pages


def test_oferta_de_exibir() -> None:
    print("\nquer ver o documento? (a regra da oferta)")
    docs = [_Doc("A.docx", "A.docx"), _Doc("B.pdf", "B.pdf"), _Doc("C.docx", "C.docx")]

    def trechos(*nomes):
        return [{"documento": n, "texto": f"trecho de {n}"} for n in nomes]

    o = ferramentas.oferta_de_exibir(trechos("A.docx", "A.docx"), docs)
    checar(o and o["tipo"] == "exibir" and o["nomes"] == ["A.docx"], "um documento: oferece ele", o)
    checar(o and o["campos"] == {"nome": "A.docx"} and o["trechos"]["A.docx"], "com os trechos, para marcar no visor", o)
    o = ferramentas.oferta_de_exibir(trechos("A.docx", "B.pdf", "A.docx"), docs)
    checar(o and o["nomes"] == ["A.docx", "B.pdf"], "dois documentos: oferece os dois", o)
    o = ferramentas.oferta_de_exibir(trechos("A.docx", "B.pdf", "C.docx"), docs)
    checar(o is None, "três documentos sem nenhum dominante: não oferece", o)
    o = ferramentas.oferta_de_exibir(trechos("A.docx", "A.docx", "A.docx", "B.pdf", "C.docx"), docs)
    checar(o and o["nomes"] == ["A.docx"], "três, com um dando mais da metade: oferece esse", o)
    checar(ferramentas.oferta_de_exibir(trechos("A.docx"), docs, ja_oferecidos={"A.docx"}) is None,
           "já oferecido nesta conversa: não oferece de novo")
    checar(ferramentas.oferta_de_exibir(trechos("Sumiu.docx"), docs) is None, "arquivo que saiu do Acervo: não oferece")
    checar(ferramentas.oferta_de_exibir([], docs) is None, "sem trechos: não oferece")
    o = ferramentas.oferta_de_exibir([{"documento": "B.pdf", "texto": "x", "pagina": 4}], docs)
    checar(o and o["paginas"]["B.pdf"] == 4, "PDF abre na página citada, quando se sabe", o)

    leitura = ferramentas.leitura(_Doc("A.docx", "c:/x/A.docx", "Primeiro.\n\n  Segundo parágrafo.  \n"))
    checar(leitura["tipo"] == "texto" and leitura["paragrafos"] == ["Primeiro.", "Segundo parágrafo."],
           "texto: parágrafos, sem linhas vazias", leitura)
    grande = ferramentas.leitura(_Doc("G.docx", "G.docx", "\n".join(f"p{i}" for i in range(2000))))
    checar(len(grande["paragrafos"]) == ferramentas.LIMITE_DE_PARAGRAFOS and grande["cortado"],
           "documento enorme: corta e avisa")
    checar(ferramentas.leitura(_Doc("B.pdf", "c:/x/B.PDF", "", 7)) == {"nome": "B.pdf", "tipo": "pdf", "paginas": 7},
           "PDF: páginas desenhadas, sem texto")


# ---------------------------------------------------------------- pela API


def test_pela_api() -> None:
    print("\npela API: proposta não grava, só o sim grava")
    from test_gravacoes import Cliente, _porta_livre, _subir_servidor

    import api

    porta = _porta_livre()
    servidor = _subir_servidor(porta)
    c = Cliente(porta)
    criados = {"cadastros": [], "trabalhos": []}

    chamadas: list[tuple] = []
    original = api.estado.client.ask_json

    def falso_ask_json(instrucao, context="", schema_hint="", sistema=""):
        chamadas.append((instrucao, sistema))
        return {"tipo": "acao", "ferramenta": "cadastrar_cliente",
                "parametros": {"nome": "Teste Ferramentas Bruno"}, "mensagem": "ok"}

    api.estado.client.ask_json = falso_ask_json
    nome = "Teste Ferramentas Cliente Silva"
    try:
        st, t = c.pedir("POST", "/api/trabalhos", {"pedido": "cadastro"})
        criados["trabalhos"].append(t["id"])
        tid = t["id"]

        def fichas(termo):
            return c.pedir("GET", "/api/cadastros?termo=" + termo.replace(" ", "%20"))[1].get("fichas", [])

        frase = f"cadastre o cliente {nome}, CPF {CPF_BOM}, email teste.ferramentas@exemplo.com"
        eventos = c.conversar(f"/api/trabalhos/{tid}/perguntar", {"pergunta": frase})
        propostas = [d for tipo, d in eventos if tipo == "proposta"]
        checar(len(propostas) == 1 and propostas[0]["tipo"] == "cadastro", "a frase vira proposta de cadastro",
               [tipo for tipo, _ in eventos])
        if not propostas:
            return
        p = propostas[0]
        checar(p["ferramenta"] == "cadastrar_cliente" and p["campos"]["documento"] == CPF_BOM, "com a ferramenta e o CPF", p)
        checar(not chamadas and p["ajuda_do_modelo"] == [], "a regra bastou: o modelo não foi chamado", chamadas)
        checar(not fichas(nome), "antes do sim, nenhuma ficha foi gravada")

        st, erro = c.pedir("POST", f"/api/trabalhos/{tid}/fazer",
                           {"tipo": "cadastro", "campos": {**p["campos"], "documento": "529.982.247-26"}})
        checar(st == 400 and "não confere" in erro.get("detail", ""), "CPF corrigido errado na tela: recusado", (st, erro))
        checar(not fichas(nome), "e nada foi gravado")

        st, feito = c.pedir("POST", f"/api/trabalhos/{tid}/fazer", {"tipo": "cadastro", "campos": p["campos"]})
        checar(st == 200 and feito.get("id") and feito.get("onde") == "cadastros", "o sim grava a ficha", (st, feito))
        if feito.get("id"):
            criados["cadastros"].append(feito["id"])
        gravada = fichas(nome)
        checar(len(gravada) == 1 and gravada[0]["documento"] == CPF_BOM and gravada[0]["tipo"] == "cliente",
               "ficha de cliente, com o CPF formatado", gravada)

        # Modelo só quando a regra não basta.
        frase = f"cadastre um cliente com cpf {CPF_BOM} que se chama teste ferramentas bruno"
        eventos = c.conversar(f"/api/trabalhos/{tid}/perguntar", {"pergunta": frase})
        tipos = [tipo for tipo, _ in eventos]
        p = next((d for tipo, d in eventos if tipo == "proposta"), {})
        checar(len(chamadas) == 1, "nome que a regra não lê: o modelo é chamado uma vez", len(chamadas))
        checar("etapas" in tipos and tipos.index("etapas") < tipos.index("proposta"),
               "a etapa \"Entender o pedido\" aparece antes do cartão", tipos)
        checar(p.get("campos", {}).get("nome") == "Teste Ferramentas Bruno" and p.get("ajuda_do_modelo") == ["nome"],
               "o cartão traz o nome e diz que veio do modelo", p)
        checar(tid not in api.estado.andamento, "o andamento é solto depois")

        # NFS-e: só a rota.
        antes = len(api.estado.papeis.listar("nota"))
        frase = "emita uma NFS-e para Teste Ferramentas Cliente Silva de R$ 1.234,56 referente à consultoria"
        eventos = c.conversar(f"/api/trabalhos/{tid}/perguntar", {"pergunta": frase})
        p = next((d for tipo, d in eventos if tipo == "proposta"), {})
        checar(p.get("tipo") == "nota" and p["campos"]["valor"] == 123456 and p["disponivel"] is False,
               "a frase vira proposta de NFS-e, marcada como ainda não disponível", p)
        st, feito = c.pedir("POST", f"/api/trabalhos/{tid}/fazer",
                            {"tipo": "nota", "campos": {**p.get("campos", {}), "valor": "R$ 1.234,56"}})
        checar(st == 200 and feito.get("pendente") is True and feito.get("id") == 0,
               "confirmar a NFS-e responde pendente", (st, feito))
        checar("nada foi enviado" in feito.get("resumo", ""), "e diz que nada foi enviado", feito.get("resumo"))
        checar(len(api.estado.papeis.listar("nota")) == antes, "nenhuma nota foi gravada")
        st, erro = c.pedir("POST", f"/api/trabalhos/{tid}/fazer", {"tipo": "nota", "campos": {"cliente": "Ana", "valor": "0"}})
        checar(st == 400, "nota sem valor é recusada mesmo sem emitir", (st, erro))

        st, erro = c.pedir("POST", f"/api/trabalhos/{tid}/fazer", {"tipo": "apagar_tudo", "campos": {}})
        checar(st == 400, "tipo fora do catálogo continua recusado", st)

        # Quer ver o documento? A habilidade de perguntar é trocada por uma
        # que responde de um documento de verdade do Acervo, sem Ollama.
        print("\npela API: a oferta de mostrar o documento")
        documentos = api.estado.searcher.documents
        checar(bool(documentos), "há documento no Acervo para o teste")
        if not documentos:
            return
        doc = documentos[0]
        habilidade = api.estado.registro.obter("perguntar")
        guardado = (habilidade.executar, habilidade.estado)

        def responde(ctx, pergunta="", top=6, apenas=None):
            trecho = {"documento": doc.name, "trecho": 1, "score": 1.0, "texto": doc.text[:300]}
            yield "fontes", {"consultados": [doc.name], "ignorados": [], "total_contratos": 1,
                             "trechos": [trecho, dict(trecho, trecho=2)], "apenas": []}
            yield "escrevendo", {"lendo_segundos": 0}
            yield "token", {"t": "Resposta de teste."}
            yield "fim", {}

        habilidade.executar, habilidade.estado = responde, "pronta"
        try:
            st, t2 = c.pedir("POST", "/api/trabalhos", {"pedido": "oferta"})
            criados["trabalhos"].append(t2["id"])
            eventos = c.conversar(f"/api/trabalhos/{t2['id']}/perguntar", {"pergunta": "o que diz a cláusula primeira?"})
            tipos = [tipo for tipo, _ in eventos]
            oferta = next((d for tipo, d in eventos if tipo == "oferta"), None)
            checar(bool(oferta) and oferta["nomes"] == [doc.name], "a resposta termina oferecendo o documento", tipos)
            checar("fim" in tipos and "oferta" in tipos and tipos.index("fim") < tipos.index("oferta"),
                   "a oferta vem depois do fim da resposta", tipos)
            checar(not any(tipo == "proposta" for tipo in tipos), "e não é uma proposta de ação")

            eventos = c.conversar(f"/api/trabalhos/{t2['id']}/perguntar", {"pergunta": "e a cláusula segunda?"})
            checar(not any(tipo == "oferta" for tipo, _ in eventos), "o mesmo documento não é oferecido duas vezes",
                   [tipo for tipo, _ in eventos])

            st, mostrado = c.pedir("POST", f"/api/trabalhos/{t2['id']}/fazer",
                                   {"tipo": "exibir", "campos": {"nome": doc.name}})
            reg = mostrado.get("registro") or {}
            checar(st == 200 and reg.get("nome") == doc.name and reg.get("tipo") in ("pdf", "texto"),
                   "o clique em Mostrar aqui devolve o que o visor desenha", (st, mostrado))
            checar(mostrado.get("id") == 0 and mostrado.get("onde") == "", "mostrar não grava nada")
            st, erro = c.pedir("POST", f"/api/trabalhos/{t2['id']}/fazer",
                               {"tipo": "exibir", "campos": {"nome": "Nao Existe Aqui.docx"}})
            checar(st == 400, "documento que não está no Acervo é recusado", (st, erro))
        finally:
            habilidade.executar, habilidade.estado = guardado
    finally:
        api.estado.client.ask_json = original
        for cid in criados["cadastros"]:
            st, r = c.pedir("DELETE", f"/api/cadastros/{cid}")
            if isinstance(r, dict) and r.get("lixeira"):
                c.pedir("DELETE", f"/api/lixeira/{r['lixeira']}")
        for tid in criados["trabalhos"]:
            st, r = c.pedir("DELETE", f"/api/trabalhos/{tid}")
            if isinstance(r, dict) and r.get("lixeira"):
                c.pedir("DELETE", f"/api/lixeira/{r['lixeira']}")
        sobrou = c.pedir("GET", "/api/cadastros?termo=Teste%20Ferramentas")[1].get("fichas", [])
        checar(not sobrou, "nada de teste sobrou em Cadastros", sobrou)
        servidor.should_exit = True


def main() -> int:
    print("=" * 55)
    print("PAULUS - as ferramentas da conversa")
    print("=" * 55)

    test_catalogo()
    test_prompt()
    test_contrato_json()
    test_normalizar()
    test_regra_le_o_cadastro()
    test_regra_le_a_nota()
    test_regra_da_agenda()
    test_completar_com_modelo()
    test_oferta_de_exibir()
    test_pela_api()

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
