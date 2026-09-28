"""
Testes dos campos de CPF, CNPJ e telefone (frontend/js/39-campos.js).

O JavaScript roda no Node e e comparado com uma conta de referencia feita
aqui, em Python, a parte: os digitos verificadores do CPF e do CNPJ (o
numerico e o alfanumerico da Receita, IN RFB 2.229/2024), em documentos
gerados com os verificadores certos e com um deles trocado. E confere a
formatacao enquanto se digita.

E o servidor (src/campos_br.py): as mesmas respostas da tela para as mesmas
entradas, o cadastro e as preferencias gravando formatado e recusando o que
nao fecha, a busca pelos digitos, a qualificacao, a conferencia do documento
e o timbre. O que abre o servidor usa uma pasta temporaria (PAULUS_DADOS).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_campos.py
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
JS = RAIZ / "frontend" / "js" / "39-campos.js"
_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


# ----------------------------------------------------- a conta de referencia

def dv_cpf(nove: str) -> str:
    d = [int(c) for c in nove]
    for n in (9, 10):
        soma = sum(d[i] * (n + 1 - i) for i in range(n))
        d.append((soma * 10) % 11 % 10)
    return "".join(map(str, d[9:]))


def dv_cnpj(doze: str) -> str:
    v = [ord(c) - 48 for c in doze]
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        resto = sum(a * b for a, b in zip(v, pesos)) % 11
        v.append(0 if resto < 2 else 11 - resto)
    return "".join(str(x) for x in v[12:])


def rodar_js(chamadas: list[list]) -> list:
    """Cada chamada e [funcao, argumento]; devolve o resultado de cada uma."""
    codigo = JS.read_text(encoding="utf-8") + "\n;const __c = " + json.dumps(chamadas) + ";\n" \
        "process.stdout.write(JSON.stringify(__c.map(([f, a]) => eval(f)(a))));"
    # Pela entrada padrao: com muitas chamadas, a linha de comando do
    # Windows nao comporta o codigo.
    r = subprocess.run(["node", "-"], input=codigo, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])
    return json.loads(r.stdout)


def test_verificadores() -> None:
    print("\nos digitos verificadores, contra a conta de referencia")
    sorte = random.Random(27)
    casos, esperado = [], []
    for _ in range(40):
        nove = "".join(sorte.choice("0123456789") for _ in range(9))
        certo = nove + dv_cpf(nove)
        errado = certo[:10] + str((int(certo[10]) + 1) % 10)
        casos += [["cpfValido", certo], ["cpfValido", errado]]
        esperado += [len(set(certo)) > 1, False]
    for alfabeto in ("0123456789", "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        for _ in range(40):
            doze = "".join(sorte.choice(alfabeto) for _ in range(12))
            certo = doze + dv_cnpj(doze)
            errado = certo[:13] + str((int(certo[13]) + 1) % 10)
            casos += [["cnpjValido", certo], ["cnpjValido", errado]]
            esperado += [len(set(certo)) > 1, False]
    obtido = rodar_js(casos)
    erros = [(c, o, e) for c, o, e in zip(casos, obtido, esperado) if o != e]
    checar(not erros, f"{len(casos)} CPFs e CNPJs (numericos e alfanumericos) batem com a referencia", erros[:3])
    checar(rodar_js([["cpfValido", "111.111.111-11"], ["cnpjValido", "00.000.000/0000-00"]]) == [False, False],
           "sequencia repetida nao passa, mesmo com a conta fechando")
    exemplo = "12ABC34501DE"
    checar(rodar_js([["cnpjValido", exemplo + dv_cnpj(exemplo)]]) == [True] and dv_cnpj(exemplo) == "35",
           "o exemplo da Receita (12.ABC.345/01DE-35) fecha")


def test_formatacao() -> None:
    print("\na formatacao enquanto se digita")
    casos = [
        ("formatarCpf", "52998224725", "529.982.247-25"),
        ("formatarCpf", "5299", "529.9"),
        ("formatarCpf", "529.982.247-2599", "529.982.247-25"),
        ("formatarCnpj", "11222333000181", "11.222.333/0001-81"),
        ("formatarCnpj", "12abc34501de35", "12.ABC.345/01DE-35"),
        ("formatarCpfOuCnpj", "52998224725", "529.982.247-25"),
        ("formatarCpfOuCnpj", "112223330001", "11.222.333/0001"),
        ("formatarCpfOuCnpj", "12ABC", "12.ABC"),
        ("formatarTelefone", "62999998888", "(62) 99999-8888"),
        ("formatarTelefone", "6232221111", "(62) 3222-1111"),
        ("formatarTelefone", "+55 62 99999-8888", "(62) 99999-8888"),
        ("formatarTelefone", "629999", "(62) 9999"),
        ("formatarTelefone", "08007271234", "0800 727 1234"),
        ("formatarTelefone", "+1 415 555 0100", "+1 415 555 0100"),
    ]
    obtido = rodar_js([[f, a] for f, a, _ in casos])
    for (f, a, e), o in zip(casos, obtido):
        checar(o == e, f"{f}({a!r}) = {e!r}", o)


def test_problemas() -> None:
    print("\no aviso de cada campo")
    casos = [
        (["cpf", ""], ""),
        (["cpf", "529.982.247-25"], ""),
        (["cpf", "529.982.247-26"], "CPF inválido: confira os números"),
        (["cpf", "529.982"], "CPF incompleto: são 11 números"),
        (["cnpj", "11.222.333/0001-81"], ""),
        (["cpf-cnpj", "11.222.333/0001-80"], "CNPJ inválido: confira os caracteres"),
        (["telefone", "(62) 99999-8888"], ""),
        (["telefone", "(62) 3222-1111"], ""),
        (["telefone", "(62) 8999-88888"], "telefone incompleto: DDD e número, como (62) 99999-8888"),
        (["telefone", "(62) 9999"], "telefone incompleto: DDD e número, como (62) 99999-8888"),
    ]
    codigo_chamadas = [["(a) => problemaDoCampo(a[0], a[1])", c] for c, _ in casos]
    obtido = rodar_js(codigo_chamadas)
    for (c, e), o in zip(casos, obtido):
        checar(o == e, f"{c[0]} {c[1]!r} -> {e or 'certo'}", o)


def test_avisa_a_tela() -> None:
    print("\nantes de salvar, o campo reformatado avisa a tela (uma vez so)")
    # Um campo de mentira: o bastante para camposInvalidos rodar no Node.
    teste = (
        "(a) => { globalThis.document = { activeElement: null }; const eventos = [];"
        " const el = { dataset: { campo: a[0] }, value: a[1], selectionStart: null,"
        "   dispatchEvent: (e) => { eventos.push(e.type + (e.bubbles ? '+' : '')); },"
        "   classList: { toggle() {}, contains() { return false; } }, setAttribute() {},"
        "   closest() { return null; }, parentElement: null };"
        " const errado = camposInvalidos({ querySelectorAll: () => [el] });"
        " return [el.value, eventos, errado ? 'invalido' : ''] }"
    )
    casos = [
        (["cpf", "52998224725"], ["529.982.247-25", ["input+"], ""]),
        (["cpf", "529.982.247-25"], ["529.982.247-25", [], ""]),
        (["telefone", "62999998888"], ["(62) 99999-8888", ["input+"], ""]),
        (["cpf-cnpj", "11222333000180"], ["11.222.333/0001-80", ["input+"], "invalido"]),
    ]
    obtido = rodar_js([[teste, c] for c, _ in casos])
    for (c, e), o in zip(casos, obtido):
        checar(o == e, f"{c[0]} {c[1]!r} -> {e[0]!r}, {len(e[1])} aviso(s)", o)


# ------------------------------------------------ o servidor (src/campos_br.py)

def _campos_br():
    sys.path.insert(0, str(RAIZ / "src"))
    import campos_br
    return campos_br


def _recusa(funcao, *args) -> str:
    try:
        funcao(*args)
    except ValueError as exc:
        return str(exc) or "recusado"
    return ""


def _entradas_de_paridade() -> list[str]:
    sorte = random.Random(91)
    entradas = [
        "", "  ", "5", "529", "5299", "529982", "52998224725", "529.982.247-25", "529.982.247-26",
        "111.111.111-11", "11222333000181", "11.222.333/0001-81", "11.222.333/0001-80",
        "12abc34501de35", "12.ABC.345/01DE-35", "12.ABC.345/01DE-36", "12ABC", "CPF 529.982.247-25",
        "62999998888", "6232221111", "+55 62 99999-8888", "5562999998888", "629999", "(62) 8999-88888",
        "08007271234", "0800 727 1234", "03001234567", "+1 415 555 0100", "+44 20", "0629999988",
        "6209999888", "(62) 9", "(62) 99999-888", "abc", "0055 62 99999-8888", "ß12.345",
    ]
    for _ in range(60):
        n = sorte.randint(1, 16)
        entradas.append("".join(sorte.choice("0123456789.-/() +ABZ") for _ in range(n)))
    return entradas


def test_servidor_igual_a_tela() -> None:
    print("\no servidor (src/campos_br.py) responde igual a tela")
    cb = _campos_br()
    entradas = _entradas_de_paridade()
    pares = [
        ("formatarCpf", cb.mascara_cpf), ("formatarCnpj", cb.mascara_cnpj),
        ("formatarCpfOuCnpj", cb.mascara_cpf_ou_cnpj), ("formatarTelefone", cb.mascara_telefone),
        ("cpfValido", cb.cpf_valido), ("cnpjValido", cb.cnpj_valido), ("telefoneValido", cb.telefone_valido),
        ("limparDocumento", cb.normalizado), ("soDigitos", cb.so_digitos),
    ]
    chamadas = [[js, e] for js, _ in pares for e in entradas]
    obtido = rodar_js(chamadas)
    esperado = [py(e) for _, py in pares for e in entradas]
    erros = [(c, o, e) for c, o, e in zip(chamadas, obtido, esperado) if o != e]
    checar(not erros, f"{len(chamadas)} mascaras e conferencias iguais nas duas pontas", erros[:4])

    tipos = ["cpf", "cnpj", "cpf-cnpj", "telefone"]
    chamadas = [["(a) => problemaDoCampo(a[0], a[1])", [t, e]] for t in tipos for e in entradas]
    obtido = rodar_js(chamadas)
    esperado = [cb.problema(t, e) for t in tipos for e in entradas]
    erros = [(c[1], o, e) for c, o, e in zip(chamadas, obtido, esperado) if o != e]
    checar(not erros, f"{len(chamadas)} avisos iguais nas duas pontas", erros[:4])

    # A conta de referencia, tambem no servidor: numerico e alfanumerico.
    sorte = random.Random(5)
    ruins = []
    for alfabeto in ("0123456789", "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        for _ in range(40):
            doze = "".join(sorte.choice(alfabeto) for _ in range(12))
            certo = doze + dv_cnpj(doze)
            errado = certo[:13] + str((int(certo[13]) + 1) % 10)
            if cb.cnpj_valido(certo) != (len(set(certo)) > 1) or cb.cnpj_valido(errado):
                ruins.append(certo)
    checar(not ruins, "CNPJs numericos e alfanumericos batem com a referencia no servidor", ruins[:3])


def test_formatar_no_servidor() -> None:
    print("\nformatar para gravar: formata o que fecha, recusa o que nao fecha")
    cb = _campos_br()
    checar(cb.formatar_documento("52998224725") == "529.982.247-25", "CPF corrido ganha a mascara")
    checar(cb.formatar_documento("11222333000181") == "11.222.333/0001-81", "CNPJ numerico ganha a mascara")
    checar(cb.formatar_documento("12abc34501de35") == "12.ABC.345/01DE-35", "CNPJ alfanumerico ganha a mascara")
    checar(cb.formatar_documento("") == "" and cb.formatar_telefone("  ") == "", "vazio continua vazio")
    checar(_recusa(cb.formatar_documento, "529.982.247-26") == "CPF inválido: confira os números",
           "CPF com digito errado e recusado com o aviso da tela")
    checar(_recusa(cb.formatar_documento, "12.ABC.345/01DE-36") == "CNPJ inválido: confira os caracteres",
           "CNPJ alfanumerico com digito errado e recusado")
    checar(_recusa(cb.formatar_documento, "529.982") == "CPF incompleto: são 11 números", "CPF curto e recusado")
    checar(cb.formatar_telefone("62999998888") == "(62) 99999-8888", "celular")
    checar(cb.formatar_telefone("6232221111") == "(62) 3222-1111", "fixo")
    checar(cb.formatar_telefone("+55 62 99999-8888") == "(62) 99999-8888", "com +55")
    checar(cb.formatar_telefone("08007271234") == "0800 727 1234", "0800")
    checar(cb.formatar_telefone("+1 415 555 0100") == "+1 415 555 0100", "de fora fica como veio")
    checar(bool(_recusa(cb.formatar_telefone, "(62) 8999-88888")), "11 digitos sem o 9 e recusado")
    checar(bool(_recusa(cb.formatar_telefone, "99999-8888")), "sem DDD e recusado")
    checar(cb.exibir_documento("529.982.247-26") == "529.982.247-26", "exibir nao mexe no que nao fecha")
    checar(cb.e_cnpj("12.ABC.345/01DE-35") and cb.e_cnpj("11222333000181") and not cb.e_cnpj("52998224725"),
           "e_cnpj reconhece o alfanumerico e o numerico")

    import ferramentas
    checar(ferramentas.cpf_ou_cnpj("12ABC34501DE35") == "12.ABC.345/01DE-35", "a conversa aceita o CNPJ alfanumerico")
    checar(ferramentas.telefone("0800 727 1234") == "0800 727 1234", "a conversa aceita 0800, como a tela")
    checar(bool(_recusa(ferramentas.cpf_ou_cnpj, "")) and bool(_recusa(ferramentas.telefone, "")),
           "a conversa continua recusando vazio")

    import conexoes
    casos = [("(62) 99999-8888", "5562999998888"), ("+55 62 3222-1111", "556232221111"),
             ("+1 415 555 0100", "14155550100"), ("+1 919 555 1234", "19195551234"), ("123", ""), ("(62) 8999-88888", ""), ("0800 727 1234", "")]
    for bruto, esperado in casos:
        checar(conexoes.numero_whatsapp(bruto) == esperado, f"WhatsApp {bruto!r} -> {esperado!r}",
               conexoes.numero_whatsapp(bruto))


def test_cadastros() -> None:
    print("\ncadastros: grava formatado, recusa o torto, acha pelos digitos")
    _campos_br()
    import tempfile
    from base import Base
    from cadastros import Cadastros

    with tempfile.TemporaryDirectory() as tmp:
        b = Base(Path(tmp) / "p.db")
        # Fichas de antes da conferencia, gravadas direto na base.
        for nome, doc, tel in (("Antiga Corrida", "52998224725", "62999998888"),
                               ("Antiga Torta", "529.982.247-26", "123"),
                               ("Antiga Alfa", "12abc34501de35", "")):
            b.escrever("INSERT INTO cadastros (tipo, nome, documento, telefone, criado_em, atualizado_em) "
                       "VALUES ('cliente', ?, ?, ?, '', '')", (nome, doc, tel))
        c = Cadastros(b)
        por_nome = {f["nome"]: f for f in c.listar()}
        checar(por_nome["Antiga Corrida"]["documento"] == "529.982.247-25"
               and por_nome["Antiga Corrida"]["telefone"] == "(62) 99999-8888",
               "a ficha antiga com numero corrido ganha a mascara ao abrir")
        checar(por_nome["Antiga Torta"]["documento"] == "529.982.247-26" and por_nome["Antiga Torta"]["telefone"] == "123",
               "a ficha antiga que nao fecha fica como estava")
        checar(por_nome["Antiga Alfa"]["documento"] == "12.ABC.345/01DE-35", "o CNPJ alfanumerico antigo tambem")
        checar(c.formatar_antigos() == 0, "abrir de novo nao muda nada")

        i = c.salvar({"nome": "Nova Cliente", "documento": "11222333000181", "telefone": "6232221111"})
        f = c.obter(i)
        checar(f["documento"] == "11.222.333/0001-81" and f["telefone"] == "(62) 3222-1111", "salvar grava formatado")
        checar(_recusa(c.salvar, {"nome": "Errada", "documento": "11.222.333/0001-80"})
               == "CNPJ inválido: confira os caracteres", "salvar recusa CNPJ torto com o aviso da tela")
        checar(bool(_recusa(c.salvar, {"nome": "Errada", "telefone": "9999"})), "salvar recusa telefone torto")
        checar(c.obter(c.salvar({"nome": "Sem Nada"}))["documento"] == "", "vazio continua vazio")

        achou = lambda termo: sorted(x["nome"] for x in c.listar(termo=termo))  # noqa: E731
        checar(achou("52998224725") == ["Antiga Corrida"], "CPF corrido acha a ficha pontuada", achou("52998224725"))
        checar(achou("529.982.247-25") == ["Antiga Corrida"], "CPF pontuado acha tambem")
        checar(achou("62999998888") == ["Antiga Corrida"], "telefone corrido acha a ficha", achou("62999998888"))
        checar(achou("3222-1111") == ["Nova Cliente"], "pedaco do telefone acha")
        checar(achou("12abc345") == ["Antiga Alfa"], "CNPJ alfanumerico acha sem mascara e em minuscula",
               achou("12abc345"))
        checar(achou("nova") == ["Nova Cliente"], "a busca por nome continua")
        b.fechar()

        # A rota devolve 400 com o aviso (api com PAULUS_DADOS temporario, main).
        import api
        from fastapi import HTTPException
        b2 = Base(Path(tmp) / "api.db")
        guardado = api.estado.cadastros
        try:
            api.estado.cadastros = Cadastros(b2)
            try:
                api.cadastros_salvar(api.FichaCadastro(dados={"nome": "X", "documento": "529.982.247-26"}))
                status, detalhe = 200, ""
            except HTTPException as exc:
                status, detalhe = exc.status_code, exc.detail
            checar(status == 400 and "CPF inválido" in detalhe, "POST /api/cadastros com CPF torto -> 400", (status, detalhe))
        finally:
            api.estado.cadastros = guardado
            b2.fechar()


def test_preferencias() -> None:
    print("\npreferencias: CPF, telefone e CNPJ conferidos")
    _campos_br()
    import json as _json
    import tempfile
    from config import Preferencias

    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "preferencias.json"
        caminho.write_text(_json.dumps({"pessoa": {"cpf": "52998224725", "telefone": "62999998888"},
                                        "escritorio": {"cnpj": "123"}}), encoding="utf-8")
        p = Preferencias(caminho)
        checar(p.dados["pessoa"]["cpf"] == "529.982.247-25" and p.dados["pessoa"]["telefone"] == "(62) 99999-8888",
               "o que foi gravado corrido volta com a mascara")
        checar(p.dados["escritorio"]["cnpj"] == "123", "o que nao fecha fica como estava")

        p.atualizar({"pessoa": {"cpf": "52998224725"}, "escritorio": {"cnpj": "123"}, "devagar": True})
        checar(p.dados["pessoa"]["cpf"] == "529.982.247-25" and p.dados["devagar"] is True,
               "o CNPJ antigo torto, sem mudanca, nao trava o resto")
        p.atualizar({"escritorio": {"cnpj": "12abc34501de35"}})
        checar(p.dados["escritorio"]["cnpj"] == "12.ABC.345/01DE-35", "CNPJ alfanumerico entra formatado")

        erro = _recusa(p.atualizar, {"pessoa": {"cpf": "529.982.247-26", "nome": "Nao Grava"}})
        checar("CPF inválido" in erro and p.dados["pessoa"]["nome"] == "" and p.dados["pessoa"]["cpf"] == "529.982.247-25",
               "CPF novo torto e recusado e nada da mesma chamada e gravado", erro)
        checar(bool(_recusa(p.atualizar, {"pessoa": {"telefone": "9999"}})), "telefone torto e recusado")
        p.atualizar({"pessoa": {"telefone": ""}})
        checar(p.dados["pessoa"]["telefone"] == "", "apagar o telefone pode")
        salvo = _json.loads(caminho.read_text(encoding="utf-8"))
        checar(salvo["escritorio"]["cnpj"] == "12.ABC.345/01DE-35", "o arquivo guarda formatado")

        import api
        from fastapi import HTTPException
        guardado = api.estado.prefs
        try:
            api.estado.prefs = p
            try:
                api.preferencias_gravar({"escritorio": {"cnpj": "11.222.333/0001-80"}})
                status, detalhe = 200, ""
            except HTTPException as exc:
                status, detalhe = exc.status_code, exc.detail
            checar(status == 400 and "CNPJ inválido" in detalhe, "POST /api/preferencias com CNPJ torto -> 400",
                   (status, detalhe))
        finally:
            api.estado.prefs = guardado


def test_documentos() -> None:
    print("\nqualificacao, conferencia e timbre")
    _campos_br()
    import documento as D
    import redacao

    q = redacao.qualificar({"nome": "Empresa Alfa", "documento": "12abc34501de35", "endereco": "Rua A"})
    checar("CNPJ sob o nº 12.ABC.345/01DE-35" in q and "EMPRESA ALFA" in q,
           "CNPJ alfanumerico qualifica como pessoa juridica, formatado", q)
    q = redacao.qualificar({"nome": "Joao", "documento": "52998224725"})
    checar("CPF sob o nº 529.982.247-25" in q, "CPF corrido entra formatado na qualificacao", q)
    checar("estado civil" not in redacao.o_que_falta({"documento": "12.ABC.345/01DE-35", "endereco": "x"}),
           "pessoa juridica alfanumerica nao pede estado civil")

    def blocos(*textos):
        return [D.Bloco(trechos=[D.Trecho(texto=t)]) for t in textos]

    texto = "CONTRATANTE: Cooperativa Vale Verde, CNPJ 11.222.333/0001-81, com sede em Goiania."
    ficha = {"nome": "Cooperativa Vale Verde", "documento": "11222333000181"}
    avisos = D.conferir(blocos(texto), [ficha])
    checar(not [a for a in avisos if a["titulo"] == "Documento diferente do cadastro"],
           "ficha sem mascara e texto com mascara: e o mesmo documento", avisos)
    texto2 = "CONTRATANTE: Cooperativa Vale Verde, inscrita no CNPJ sob o nº 11222333000181."
    ficha2 = {"nome": "Cooperativa Vale Verde", "documento": "11.222.333/0001-81"}
    avisos = D.conferir(blocos(texto2), [ficha2])
    checar(not avisos, "texto sem mascara e ficha com mascara: e o mesmo documento", avisos)
    texto3 = "CONTRATANTE: Empresa Alfa Nova, CNPJ 12.ABC.345/01DE-35."
    avisos = D.conferir(blocos(texto3), [{"nome": "Empresa Alfa Nova", "documento": "12abc34501de35"}])
    checar(not avisos, "CNPJ alfanumerico no texto bate com a ficha", avisos)
    avisos = D.conferir(blocos("Empresa Alfa Nova, CNPJ 12.ABC.345/01DE-36."), [])
    checar([a["titulo"] for a in avisos] == ["CNPJ não confere"], "CNPJ alfanumerico torto no texto e apontado", avisos)
    avisos = D.conferir(blocos("inscrito no CPF sob o nº 52998224726, residente"), [])
    checar([a["titulo"] for a in avisos] == ["CPF não confere"], "CPF sem mascara, com rotulo, e conferido", avisos)
    avisos = D.conferir(blocos("Telefone 62999998888, protocolo 12345678901."), [])
    checar(not avisos, "numero corrido sem rotulo (telefone, protocolo) nao vira aviso falso", avisos)
    avisos = D.conferir(blocos(texto), [{"nome": "Cooperativa Vale Verde", "documento": "52998224725"}])
    diferente = [a for a in avisos if a["titulo"] == "Documento diferente do cadastro"]
    checar(len(diferente) == 1 and "CPF 529.982.247-25" in diferente[0]["detalhe"],
           "documento diferente de verdade continua apontado, com a mascara", diferente)
    checar(D.cnpj_valido("12.ABC.345/01DE-35") and not D.cnpj_valido("12.ABC.345/01DE-36"),
           "cnpj_valido do documento aceita o alfanumerico")

    linhas = D._linhas_do_timbre({"nome": "Dra. Ana", "oab": "GO 1", "cpf": "52998224725", "telefone": "62999998888"})
    checar(linhas == ["Dra. Ana", "OAB GO 1 · 529.982.247-25", "(62) 99999-8888"], "o timbre sai formatado", linhas)

    import classify
    achados = classify.detectar_documentos("CNPJ 12.ABC.345/01DE-35 e 12.ABC.345/01DE-36, CPF 529.982.247-25")
    checar(achados == ["12.ABC.345/01DE-35", "529.982.247-25"],
           "a classificacao acha o CNPJ alfanumerico que fecha e ignora o que nao fecha", achados)


def main() -> int:
    # Tudo o que abrir o servidor (import api) fica numa pasta temporaria:
    # nada daqui toca os dados de verdade.
    import os
    import tempfile
    os.environ["PAULUS_DADOS"] = tempfile.mkdtemp(prefix="paulus-campos-")
    print("=" * 55)
    print("  CPF, CNPJ e telefone")
    print("=" * 55)
    test_formatar_no_servidor()
    test_cadastros()
    test_preferencias()
    test_documentos()
    if not shutil.which("node"):
        print("\n  pulado (a parte da tela): Node nao instalado")
    else:
        test_verificadores()
        test_formatacao()
        test_problemas()
        test_avisa_a_tela()
        test_servidor_igual_a_tela()
    shutil.rmtree(os.environ["PAULUS_DADOS"], ignore_errors=True)
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
