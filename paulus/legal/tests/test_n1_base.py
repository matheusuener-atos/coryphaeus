"""
Portão da N1 do emissor de NFS-e — a base fiscal (docs/PROGRESSO-NFSE.md).

  - mudar o regime cria versão e não altera a nota simulada antiga;
  - município sem convênio deixa a emissão indisponível, com a frase certa
    (e com convênio, a frase de que dá para emitir);
  - tabelas oficiais carregadas, cada uma com versão e fonte; planilha
    importada mais nova vale por cima da embutida;
  - colaborador e acesso de fora não alcançam a configuração;
  - o cadastro ganha os campos da nota sem perder o que existia quando é
    salvo pela tela antiga;
  - o certificado da nota instala, confere a senha e não aceita A3/Windows;
  - percentual e dinheiro da tela viram inteiro sem float.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n1_base.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n1-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from _nfse_comum import (CNPJ_PRESTADOR, GOIANIA, certificado_a1, checar, falhas,  # noqa: E402
                         sessoes_de_fora)


def configurar_basico(api) -> dict:
    return api.estado.nfse.prestador.gravar({
        "documento": CNPJ_PRESTADOR, "razao_social": "Escritório de Teste", "inscricao_municipal": "123456",
        "municipio": GOIANIA, "opcao_simples": "1", "regime_especial": "0",
        "servico": {"ctribnac": "171401", "nbs": "113012000", "descricao": "Honorários advocatícios",
                    "aliquota_iss_pct": "5"},
        "ibscbs": {"enviar": True, "cst": "200", "cclasstrib": "200052", "cindop": "100301"},
    }, quem="teste")


def test_versoes(api) -> None:
    print("\nconfiguração com histórico: mudar o regime não reescreve a nota antiga")
    p = api.estado.nfse.prestador
    v1 = configurar_basico(api)
    checar(v1["id"] > 0 and v1["mudou"], "primeira gravação cria a versão 1", v1.get("id"))
    checar(v1["dados"]["servico"]["aliquota_iss_bp"] == 500, "5% vira 500 pontos-base (inteiro)", v1["dados"]["servico"])
    nota_antiga = {"prestador_versao": v1["id"], "centavos": 500000}
    igual = p.gravar({"municipio": GOIANIA}, quem="teste")
    checar(not igual["mudou"] and igual["id"] == v1["id"], "gravar o mesmo não cria versão", igual["id"])
    v2 = p.gravar({"opcao_simples": "3", "regime_apuracao_sn": "1"}, quem="teste", motivo="entrou no Simples")
    checar(v2["id"] > v1["id"], "mudar o regime cria versão nova", v2["id"])
    checar(p.atual()["dados"]["opcao_simples"] == "3", "a versão em vigor é a nova")
    antiga = p.versao(nota_antiga["prestador_versao"])
    checar(antiga["dados"]["opcao_simples"] == "1", "a nota antiga continua apontando para o regime de antes",
           antiga["dados"]["opcao_simples"])
    checar(len(p.historico()) == 2, "histórico com as duas versões", len(p.historico()))
    v3 = p.gravar({"opcao_simples": "1"}, quem="teste")
    checar(v3["dados"]["regime_apuracao_sn"] == "", "fora do Simples ME/EPP o regime de apuração some (E0162)",
           v3["dados"]["regime_apuracao_sn"])
    # Regras que a própria Sefin aplicaria: barradas já na configuração.
    for dados, nome in (({"regime_especial": "6", "retencoes": {"iss": {"quando": "sempre"}}}, "regime especial + ISS retido (E0588)"),
                        ({"documento": "11222333000182"}, "CNPJ com dígito errado"),
                        ({"municipio": "9999999"}, "município fora da tabela do IBGE"),
                        ({"servico": {"ctribnac": "999999"}}, "código de serviço fora da lista nacional"),
                        ({"serie": "50000"}, "série fora da faixa de aplicativo próprio (E0010)"),
                        ({"servico": {"aliquota_iss_pct": "6"}}, "alíquota de ISS acima de 5% (E0595)")):
        try:
            p.gravar(dados, quem="teste")
            checar(False, f"recusa: {nome}")
        except ValueError:
            checar(True, f"recusa: {nome}")
    try:
        p.gravar({"ambiente": "producao"}, quem="teste")
        checar(p.atual()["dados"]["ambiente"] == "producao_restrita", "a tela não troca o ambiente para produção")
    except ValueError as exc:
        checar(False, "a tela não troca o ambiente para produção", str(exc))
    sem_saber = p.atual()["dados"]["retencoes"]["irrf"]
    checar(sem_saber["quando"] == "nao_sei", "retenção começa em “não sei, perguntar ao contador”", sem_saber)


def test_dinheiro() -> None:
    print("\npercentual e dinheiro em inteiros")
    from nfse import dinheiro
    from nfse.prestador import percentual_para_bp

    casos = (("5", 500), ("5,00", 500), ("2,5", 250), ("0,65", 65), ("1,5%", 150), ("", 0))
    for texto, esperado in casos:
        checar(percentual_para_bp(texto) == esperado, f"“{texto}” -> {esperado} pontos-base", percentual_para_bp(texto))
    checar(dinheiro.centavos_de_texto("5.000,00") == 500000, "R$ 5.000,00 -> 500000 centavos")
    checar(dinheiro.centavos_de_texto("1.234,5") == 123450, "1.234,5 -> 123450")
    checar(dinheiro.centavos_de_texto("0,07") == 7, "0,07 -> 7")
    checar(dinheiro.decimal_xml(500000) == "5000.00" and dinheiro.decimal_xml(0) == "0", "XML: 5000.00 e 0")
    checar(dinheiro.aplicar(12345, 150) == 185, "1,5% de R$ 123,45 = R$ 1,85 (half-even de 185,175)")
    checar(dinheiro.dividir_half_even(5, 2) == 2 and dinheiro.dividir_half_even(7, 2) == 4, "empate vai para o par")
    import inspect

    fonte = inspect.getsource(dinheiro) + inspect.getsource(__import__("nfse.prestador", fromlist=["x"]))
    checar("float(" not in fonte, "nenhum float( no caminho do dinheiro da nota")


def test_tabelas(api) -> None:
    print("\ntabelas oficiais com versão")
    from nfse import tabelas

    vs = {t["nome"]: t for t in tabelas.versoes()}
    for nome in ("municipios", "servicos", "nbs", "indop", "correlacao", "dominios"):
        t = vs.get(nome) or {}
        checar(t.get("versao") and t.get("itens", 0) > 0 and t.get("fonte", "").startswith("https://www.gov.br/nfse"),
               f"{nome}: versão {t.get('versao')}, {t.get('itens')} itens, com a fonte oficial", t)
    checar(vs["municipios"]["itens"] >= 5570, "os 5.570 municípios do IBGE", vs["municipios"]["itens"])
    checar((tabelas.municipio(GOIANIA) or {}).get("uf") == "GO", "Goiânia é GO pelo código IBGE")
    checar((tabelas.servico("171401") or {}).get("descricao") == "Advocacia", "171401 é Advocacia")
    checar(tabelas.nbs("1.1301.20.00") is not None, "NBS com pontos acha a sem pontos")
    checar(tabelas.dominio("motivo_cancelamento") == {"1": "Erro na Emissão", "2": "Serviço não Prestado", "9": "Outros"},
           "motivos de cancelamento do XSD")
    checar(tabelas.dominio("regime_especial").get("6") == "Sociedade de Profissionais", "regime 6 = Sociedade de Profissionais")

    # Uma planilha "nova" importada vale por cima da embutida (versão maior).
    import openpyxl

    pasta = TMP / "planilha"
    pasta.mkdir()
    arq = pasta / "anexo-c-indop-ibscbs-snnfse-v9-99.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "IndOp"
    ws.append(["Art. 11", "Tipo", "Local", "Característica", "", "", "Código indOp", "Local do fornecimento"])
    ws.append(["Inc. X", "Demais serviços (teste)", "domicílio", "x", "1003", "01", "100301", "Domicílio do adquirente"])
    wb.save(arq)
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    with open(arq, "rb") as f:
        r = local.post("/api/nfse/tabelas/importar", files={"arquivo": (arq.name, f.read())})
    checar(r.status_code == 200, "importar planilha oficial pela tela", r.text[:200])
    checar(tabelas.carregar("indop")["versao"] == "9.99", "a versão importada (9.99) passa a valer",
           tabelas.carregar("indop")["versao"])
    with open(arq, "rb") as f:
        r = local.post("/api/nfse/tabelas/importar", files={"arquivo": ("qualquer.xlsx", f.read())})
    checar(r.status_code == 400, "planilha com nome que não é do portal é recusada", r.status_code)
    shutil.rmtree(api.estado.nfse.pasta / "tabelas", ignore_errors=True)
    tabelas.usar_pasta_de_dados(api.estado.nfse.pasta / "tabelas")


class Simulado:
    """O Sistema Nacional de mentira para a consulta do convênio."""

    def __init__(self, status: int, corpo) -> None:
        self.status, self.corpo, self.pedidos = status, corpo, []

    def __call__(self, metodo, url, corpo):
        from nfse.cliente import Resposta

        self.pedidos.append((metodo, url))
        return Resposta(self.status, self.corpo)


def test_municipio(api) -> None:
    print("\no município: com e sem convênio")
    from nfse import municipio

    e = api.estado.nfse
    e.ligar(True)
    certificado_a1(TMP / "cert.pfx")
    e.instalar_certificado("cert.pfx", (TMP / "cert.pfx").read_bytes(), "segredo-de-teste", False)

    antes = e.situacao_municipio()
    checar(antes["situacao"] == municipio.NAO_CONSULTADO and not antes["pode_emitir"], "sem consulta, não emite")
    checar("Ainda não consultei" in antes["frase"], "e diz que ainda não consultou", antes["frase"])

    e.transporte = Simulado(404, {"mensagem": "Convênio não encontrado"})
    sit = e.consultar_municipio()
    checar(sit["situacao"] == municipio.SEM_CONVENIO and not sit["pode_emitir"], "404: sem convênio, emissão indisponível", sit)
    checar("Goiânia/GO não emite pelo Sistema Nacional" in sit["frase"]
           and "continua só registrando" in sit["frase"], "frase: não emite daqui e o PAULUS continua registrando", sit["frase"])
    pode, motivos = e.pode_emitir()
    checar(not pode and any("não emite pelo Sistema Nacional" in m for m in motivos), "pode_emitir diz por quê", motivos)
    checar(e.transporte.pedidos and e.transporte.pedidos[0][1].endswith(f"/parametros_municipais/{GOIANIA}/convenio")
           and "producaorestrita" in e.transporte.pedidos[0][1], "consulta a API de parâmetros da produção restrita",
           e.transporte.pedidos)

    e.transporte = Simulado(200, {"codigoMunicipio": GOIANIA, "situacao": "Inativo"})
    checar(e.consultar_municipio()["situacao"] == municipio.SEM_CONVENIO, "convênio inativo: não emite")
    e.transporte = Simulado(200, {"codigoMunicipio": GOIANIA, "permiteEmissorNacional": False})
    checar(e.consultar_municipio()["situacao"] == municipio.SEM_CONVENIO, "emissor público não permitido: não emite")
    e.transporte = Simulado(500, None)
    checar(e.consultar_municipio()["situacao"] == municipio.INDEFINIDO, "erro do servidor: não confirmado, não emite")

    e.transporte = Simulado(200, {"codigoMunicipio": GOIANIA, "situacaoConvenio": "Ativo",
                                  "prazoCancelamentoDias": 30, "permiteEmissorNacional": True})
    sit = e.consultar_municipio()
    checar(sit["situacao"] == municipio.CONVENIADO and sit["pode_emitir"], "convênio ativo: emite", sit)
    checar(sit["frase"].startswith("Dá para emitir pelo padrão nacional daqui: Goiânia/GO"), "frase de que dá para emitir", sit["frase"])
    checar(sit["prazo_cancelamento_dias"] == 30, "o prazo de cancelamento vem dos parâmetros", sit["prazo_cancelamento_dias"])
    pode, motivos = e.pode_emitir()
    checar(pode, "configurado, com certificado e convênio: pode emitir", motivos)
    e.transporte = None


def test_certificado(api) -> None:
    print("\no certificado da nota")
    e = api.estado.nfse
    tela = e.certificado_para_tela()
    checar(tela["instalado"] and tela["certificado"]["documento"].replace(".", "").replace("/", "").replace("-", "") == CNPJ_PRESTADOR,
           "instalado, com o CNPJ lido do certificado", tela.get("certificado"))
    try:
        e.instalar_certificado("cert.pfx", (TMP / "cert.pfx").read_bytes(), "senha-errada", False)
        checar(False, "senha errada recusa")
    except ValueError:
        checar(True, "senha errada recusa")
    checar(e.cofre.instalado, "e o certificado que funcionava continua lá")
    try:
        e.instalar_certificado("token.cer", b"x", "", False)
        checar(False, "só .pfx/.p12 (A1 em arquivo)")
    except ValueError as exc:
        checar("A1" in str(exc), "só .pfx/.p12 (A1 em arquivo)", str(exc))
    certificado_a1(TMP / "vence.pfx", dias=10)
    e.instalar_certificado("vence.pfx", (TMP / "vence.pfx").read_bytes(), "segredo-de-teste", False)
    avisos = e.certificado_para_tela()["avisos"]
    checar(any("vence em" in a for a in avisos), "aviso de certificado a menos de 30 dias de vencer", avisos)
    e.instalar_certificado("cert.pfx", (TMP / "cert.pfx").read_bytes(), "segredo-de-teste", False)
    senha_no_disco = any(b"segredo-de-teste" in p.read_bytes() for p in (e.pasta).rglob("*") if p.is_file())
    checar(not senha_no_disco, "a senha não aparece em arquivo nenhum da pasta da nota")


def test_cadastro(api) -> None:
    print("\no cadastro ganha os campos da nota sem quebrar o que existe")
    c = api.estado.cadastros
    id_ = c.salvar({"nome": "ACME Ltda", "documento": "45.997.418/0001-53", "tipo": "cliente",
                    "end_logradouro": "Rua 1", "end_numero": "10", "end_bairro": "Centro", "end_cep": "74000-000",
                    "end_cmun": GOIANIA, "email_nota": "fiscal@acme.com.br"})
    f = c.obter(id_)
    checar(f["end_uf"] == "GO" and f["end_cep"] == "74000000", "UF pelo município e CEP só com dígitos", (f["end_uf"], f["end_cep"]))
    c.salvar({"nome": "ACME Ltda", "documento": "45.997.418/0001-53", "tipo": "cliente", "telefone": "62999998888"}, id_)
    f = c.obter(id_)
    checar(f["end_logradouro"] == "Rua 1" and f["email_nota"] == "fiscal@acme.com.br",
           "salvar pela tela antiga (sem os campos novos) não apaga o endereço da nota", f["end_logradouro"])
    try:
        c.salvar({"nome": "X", "end_cmun": "123"}, None)
        checar(False, "município fora da tabela é recusado")
    except ValueError:
        checar(True, "município fora da tabela é recusado")


def test_de_fora(api) -> None:
    print("\nde fora e colaborador não alcançam a configuração")
    from fastapi.testclient import TestClient

    sem_chave = TestClient(api.app)
    for metodo, url in (("GET", "/api/nfse"), ("POST", "/api/nfse/prestador"), ("POST", "/api/nfse/ligar"),
                        ("POST", "/api/nfse/certificado/remover"), ("POST", "/api/nfse/municipio/consultar")):
        r = sem_chave.request(metodo, url, json={})
        checar(r.status_code in (401, 403), f"sem a chave da janela: {metodo} {url} recusado", r.status_code)
    sessoes = sessoes_de_fora(api)
    if not sessoes:
        print("  pulado: sem DPAPI, o acesso de fora fica indisponível")
        return
    titular, colab = sessoes
    for quem, f in (("titular de fora", titular), ("colaborador", colab)):
        r = f.get("/api/nfse")
        checar(r.status_code == 403, f"{quem}: não lê a configuração fiscal", r.status_code)
        r = f.post("/api/nfse/prestador", json={"dados": {"opcao_simples": "3"}})
        checar(r.status_code == 403, f"{quem}: não muda o regime", r.status_code)
        r = f.post("/api/nfse/certificado/remover")
        checar(r.status_code == 403, f"{quem}: não mexe no certificado", r.status_code)
    checar(api.estado.nfse.prestador.atual()["dados"]["opcao_simples"] == "1", "a configuração ficou como estava")


def test_politica_declarada(api) -> None:
    print("\nas rotas novas têm política (test_r3)")
    from acesso import politicas

    rotas = [(m, r.path) for r in api.app.routes if getattr(r, "path", "").startswith("/api/nfse")
             for m in getattr(r, "methods", []) if m != "HEAD"]
    checar(rotas and all(politicas.REGISTRO.get(par) == politicas.BLOQUEADO for par in rotas),
           f"{len(rotas)} rotas /api/nfse, todas só na janela do escritório", [p for p in rotas if politicas.REGISTRO.get(p) != politicas.BLOQUEADO])


def main() -> int:
    try:
        import api

        checar(not api.estado.nfse.ligado, "a emissão vem desligada de fábrica")
        test_dinheiro()
        test_versoes(api)
        test_tabelas(api)
        test_municipio(api)
        test_certificado(api)
        test_cadastro(api)
        test_politica_declarada(api)
        test_de_fora(api)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s): {falhas}")
        return 1
    print("\ntodos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
