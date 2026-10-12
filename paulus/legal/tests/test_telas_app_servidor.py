"""
O servidor no formato das telas do App de 12/10/2026 (a entrega juntada no
frontend em 9d6d765). Confere o que mudou ou nasceu no servidor para elas:

  - Notas fiscais: a nota traz `servico` e `emitida_em`; a lista filtra o
    periodo (`de`/`ate`); "Enviar ao cliente" poe o e-mail em Aprovacoes;
    o certificado da Assinatura vira o da nota; o "ja instalado no Windows"
    diz por que nao serve, em vez de fingir que ficou pronto
  - /api/arquivos/bruto e /api/pastas?tipos=: o procurar da nota fiscal
  - Selo: {oab} sai de Meus dados; a posicao nao e mais padrao guardado
  - E-mail: quando_curto "hoje 10:05", "ontem 18:12", "10 out 14:40"
  - Financeiro: o resultado do mes com o sinal separado ("+ R$", "− R$")
  - Acesso de fora: o campo do tunel e so_atos (era so_google)
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-telas-app-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_NFSE_SEM_FILA"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from _nfse_comum import CNPJ_PRESTADOR, CNPJ_TOMADOR, GOIANIA, certificado_a1, checar, falhas  # noqa: E402

SENHA = "senha-do-a1-telas"


def preparar(api) -> int:
    from _sefin_simulada import SefinSimulada

    e = api.estado.nfse
    e.prestador.gravar({
        "documento": CNPJ_PRESTADOR, "razao_social": "Escritório de Teste", "inscricao_municipal": "123456",
        "municipio": GOIANIA, "opcao_simples": "1",
        "servico": {"ctribnac": "171401", "nbs": "113012000", "descricao": "Honorários advocatícios", "aliquota_iss_pct": "5"},
        "retencoes": {"irrf": {"quando": "nunca"}, "pis": {"quando": "nunca"}, "cofins": {"quando": "nunca"},
                      "csll": {"quando": "nunca"}, "cp": {"quando": "nunca"}, "iss": {"quando": "nunca"}},
        "ibscbs": {"enviar": True, "cst": "200", "cclasstrib": "200052", "cindop": "100301"},
    }, quem="teste")
    certificado_a1(TMP / "a1.pfx", senha=SENHA)
    e.instalar_certificado("a1.pfx", (TMP / "a1.pfx").read_bytes(), SENHA, True)
    api.estado.base.escrever("INSERT OR REPLACE INTO nfse_municipio (cmun, ambiente, situacao, consultado_em) "
                             "VALUES (?, 'producao_restrita', 'conveniado', datetime('now'))", (GOIANIA,))
    certificado_a1(TMP / "sefin.pfx", senha="sefin", nome="SEFIN NACIONAL TESTE")
    e.transporte = SefinSimulada(TMP / "sefin.json", "sucesso", (TMP / "sefin.pfx").read_bytes(), "sefin")
    cid = api.estado.cadastros.salvar({"nome": "ACME Ltda", "documento": CNPJ_TOMADOR, "end_logradouro": "Rua 1",
                                       "end_numero": "10", "end_bairro": "Centro", "end_cep": "74000000",
                                       "end_cmun": GOIANIA, "email_nota": "fiscal@acme.com.br"})
    api.estado.contas.salvar_conta({"email": "escritorio@teste.com.br", "nome": "Escritório"})
    api.estado.nfse.ligar(True)
    return cid


def test_notas(api, local, cid) -> int:
    print("\nNotas fiscais: servico, emitida_em, periodo e Enviar ao cliente")
    r = local.post("/api/nfse/notas", json={"origem": "manual", "dados": {"cadastro_id": cid, "valor": "1.200,00",
                                                                          "descricao": "Honorários de outubro"}})
    nota = r.json()
    checar(r.status_code == 200 and nota["servico"] == "Honorários de outubro" and nota["emitida_em"] == "",
           "o rascunho traz o serviço e ainda não tem data de emissão", r.text[:300])
    r = local.post(f"/api/nfse/notas/{nota['id']}/enviar-email")
    checar(r.status_code == 400, "rascunho não vai ao cliente por e-mail", r.text[:200])
    local.post(f"/api/nfse/notas/{nota['id']}/pedir-aprovacao")
    pedido = next(p for p in api.estado.fila.pendentes if p.acao == "nfse.emitir")
    local.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": True})
    emitida = local.get(f"/api/nfse/notas/{nota['id']}").json()
    checar(emitida["estado"] == "emitida" and emitida["emitida_em"][:4].isdigit(), "emitida: a data de emissão aparece",
           (emitida["estado"], emitida.get("emitida_em")))

    hoje = date.today().isoformat()
    lista = local.get(f"/api/nfse/notas?de={hoje}&ate={hoje}").json()["notas"]
    checar(any(n["id"] == nota["id"] for n in lista), "o período de hoje traz a nota emitida hoje")
    lista = local.get("/api/nfse/notas?de=2000-01-01&ate=2000-01-31").json()["notas"]
    checar(not any(n["id"] == nota["id"] for n in lista), "outro período não traz")

    def propostas():
        return [p for p in api.estado.fila.pendentes if p.acao == "correio.enviar" and str(emitida["numero_nfse"]) in p.titulo]

    antes = len(propostas())
    r = local.post(f"/api/nfse/notas/{nota['id']}/enviar-email")
    novas = propostas()
    checar(r.status_code == 200 and "Aprovações" in r.json()["proposta"] and len(novas) == antes + 1,
           "Enviar ao cliente: mais um e-mail em Aprovações, nada enviado", (r.status_code, r.text[:200], antes, len(novas)))
    checar(all(Path(a).exists() for a in novas[-1].dados["anexos"]) and any(a.endswith(".pdf") for a in novas[-1].dados["anexos"]),
           "com o PDF e o XML da nota", novas[-1].dados["anexos"])
    return nota["id"]


def test_certificados(api, local) -> None:
    print("\no certificado da nota: o da Assinatura serve; o do Windows diz por quê")
    r = local.post("/api/nfse/certificado/windows", json={"impressao": "AB12", "senha": "1234"})
    checar(r.status_code == 400 and "Windows" in r.json()["detail"] and ".pfx" in r.json()["detail"],
           "o do Windows responde o motivo, não finge que ficou pronto", r.text[:200])

    cofre = api.estado.cofre
    certificado_a1(TMP / "assina.pfx", senha="senha-da-assinatura", nome="ADVOGADO DA ASSINATURA")
    cofre.guardar_arquivo("assina.pfx", (TMP / "assina.pfx").read_bytes())
    cofre.esquecer_senha()
    r = local.post("/api/nfse/certificado/do-assinador")
    checar(r.status_code == 400 and "senha" in r.json()["detail"], "sem a senha aberta, pede para abrir antes", r.text[:200])
    cofre.lembrar("senha-da-assinatura")
    r = local.post("/api/nfse/certificado/do-assinador")
    titular = ((r.json().get("certificado") or {}).get("certificado") or {}).get("titular", "") if r.status_code == 200 else ""
    checar(r.status_code == 200 and "ADVOGADO DA ASSINATURA" in titular,
           "com a senha aberta, a nota passa a usar o certificado da Assinatura", (r.status_code, r.text[:300]))


def test_arquivos(local) -> None:
    print("\no procurar da nota fiscal: /api/pastas?tipos= e /api/arquivos/bruto")
    pasta = TMP / "procurar"
    pasta.mkdir()
    (pasta / "cert.pfx").write_bytes(b"\x30\x82pfx")
    (pasta / "nota.txt").write_text("x", encoding="utf-8")
    d = local.get("/api/pastas", params={"arquivos": 1, "caminho": str(pasta), "tipos": ".pfx,.p12"}).json()
    nomes = [a["nome"] for a in d.get("arquivos") or []]
    checar(nomes == ["cert.pfx"], "com tipos, o seletor mostra só o certificado", nomes)
    d = local.get("/api/pastas", params={"arquivos": 1, "caminho": str(pasta)}).json()
    checar("cert.pfx" not in [a["nome"] for a in d.get("arquivos") or []], "sem tipos, continua só o que o Acervo lê")
    r = local.get("/api/arquivos/bruto", params={"caminho": str(pasta / "cert.pfx")})
    checar(r.status_code == 200 and r.content == b"\x30\x82pfx", "o .pfx vem inteiro", r.status_code)
    r = local.get("/api/arquivos/bruto", params={"caminho": str(pasta / "nota.txt")})
    checar(r.status_code == 400, "outro tipo de arquivo, não", r.status_code)
    r = local.get("/api/arquivos/bruto", params={"caminho": str(pasta / "nao-existe.pfx")})
    checar(r.status_code == 404, "arquivo que não existe: 404", r.status_code)


def test_selo(api, local) -> None:
    print("\nselo: {oab} de Meus dados; a posição não é padrão guardado")
    import assinatura
    import documento

    class Cert:
        titular, documento, emissor = "FULANO DE TAL", "123.456.789-09", "AC TESTE"

    texto = assinatura.texto_do_selo({"texto": "Assinado por {nome} · OAB {oab}", "oab": "PA 12.345",
                                      "mostrar_data": False, "mostrar_codigo": False, "mostrar_cpf": False},
                                     Cert(), "X", datetime.now())
    checar("OAB PA 12.345" in texto, "{oab} preenchido", texto)
    texto = assinatura.texto_do_selo({"texto": "Por {nome} · OAB {oab}", "mostrar_data": False, "mostrar_codigo": False,
                                      "mostrar_cpf": False}, Cert(), "X", datetime.now())
    checar("{oab}" not in texto, "sem OAB cadastrada, o campo sai vazio (não fica {oab})", texto)

    cofre = api.estado.cofre
    cofre.gravar_selo({"posicao": "topo_direita", "texto": "Assinado por {nome}"})
    checar("posicao" not in cofre.para_tela()["selo"], "o selo guardado não tem posição padrão", cofre.para_tela()["selo"])
    cofre.dados["selo"]["posicao"] = "topo_direita"   # um cofre antigo
    checar("posicao" not in cofre.para_tela()["selo"], "a posição de um cofre antigo não volta como padrão")

    pdf = TMP / "doc.pdf"
    pdf.write_bytes(documento.para_pdf(documento.ler_html("<p>Contrato de teste.</p>"), "Contrato", "teste"))
    d = local.get("/api/assinar/documento", params={"arquivo": str(pdf)}).json()
    checar(d.get("selo", {}).get("posicao") == "rodape_direita" and "senha_na_memoria" in d and d.get("escolhas"),
           "/api/assinar/documento: documento, escolhas, selo (começa no rodapé à direita) e senha_na_memoria",
           {k: d.get(k) for k in ("selo", "senha_na_memoria")})


def test_email_e_financeiro(api) -> None:
    print("\ne-mail: quando_curto; financeiro: o sinal do resultado")
    import correio

    agora = datetime.now().replace(hour=10, minute=5)
    checar(correio._quando_curto(agora) == "hoje 10:05", "hoje", correio._quando_curto(agora))
    ontem = (datetime.now() - timedelta(days=1)).replace(hour=18, minute=12)
    checar(correio._quando_curto(ontem) == "ontem 18:12", "ontem", correio._quando_curto(ontem))
    antes = (datetime.now() - timedelta(days=12)).replace(hour=14, minute=40)
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    esperado = f"{antes.day} {meses[antes.month - 1]} 14:40"
    checar(correio._quando_curto(antes) == esperado, "dia, mês e hora", (correio._quando_curto(antes), esperado))

    fin = api.estado.financeiro
    lid = fin.salvar({"tipo": "despesa", "descricao": "Aluguel", "centavos": 30000, "vencimento": date.today().isoformat()})
    fin.liquidar(lid, date.today().isoformat())
    p = fin.painel()
    checar(p["resultado_mes_texto"].startswith("− R$ ") or p["resultado_mes_texto"].startswith("+ R$ "),
           "o resultado do mês com o sinal separado", p["resultado_mes_texto"])
    entrou = fin._soma("tipo = 'recebimento' AND liquidado_em != '' AND substr(liquidado_em,1,7) = ?", (p["mes"],))
    checar(p["resultado_mes"] == entrou - 30000, "só o que foi pago no mês entra", p["resultado_mes"])


def test_ordens_do_acervo(local) -> None:
    print("\nAcervo: as ordens no formato da tela, a chave antiga ainda vale")
    import acervo

    d = local.get("/api/biblioteca").json()
    checar(d.get("ordens") == {"modificado": "Modificado", "nome": "Nome", "pasta": "Pasta", "analise": "Análise"},
           "ordens com as chaves e os rótulos da tela", d.get("ordens"))
    itens = [{"nome": "b.pdf", "pasta": "C:/Z", "tipo": "contrato", "modificado_em": "2026-10-01"},
             {"nome": "a.pdf", "pasta": "C:/A", "tipo": "", "modificado_em": "2026-09-01"},
             {"nome": "c.pdf", "pasta": "C:/A", "tipo": "contrato", "modificado_em": "2026-10-05"}]
    nomes = lambda o: [i["nome"] for i in acervo.ordenar(itens, o)]  # noqa: E731
    checar(nomes("modificado") == nomes("modificacao") == ["c.pdf", "b.pdf", "a.pdf"], "modificado (e a chave antiga)")
    checar(nomes("pasta") == ["a.pdf", "c.pdf", "b.pdf"], "pasta, e o nome dentro dela", nomes("pasta"))
    checar(nomes("analise") == ["a.pdf", "c.pdf", "b.pdf"], "análise: os sem análise primeiro", nomes("analise"))


def test_tunel(local) -> None:
    print("\nacesso de fora: so_atos no lugar de so_google")
    d = local.get("/api/acesso/tunel").json()
    checar(d.get("so_atos") is True and "so_google" not in d, "o túnel diz so_atos", {k: d.get(k) for k in ("so_atos", "so_google")})


def main() -> int:
    try:
        import api
        from fastapi.testclient import TestClient

        local = TestClient(api.app, headers=api.cabecalho_local())
        cid = preparar(api)
        test_notas(api, local, cid)
        test_certificados(api, local)
        test_arquivos(local)
        test_selo(api, local)
        test_email_e_financeiro(api)
        test_ordens_do_acervo(local)
        test_tunel(local)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s): {falhas}")
        return 1
    print("\ntodos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
