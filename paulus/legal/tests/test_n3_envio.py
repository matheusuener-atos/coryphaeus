"""
Portão da N3 do emissor de NFS-e — assinar, enviar e não emitir duas vezes.

Com a Sefin simulada (tests/_sefin_simulada.py), que reproduz as respostas
documentadas: sucesso, rejeição, tempo esgotado depois de gerar, tempo
esgotado antes de gerar, erro 500 depois de gerar e servidor fora.

  - ZERO nota duplicada em todos os cenários (a Sefin simulada conta);
  - a assinatura vale na verificação independente (o SignedXml do .NET);
  - o processo morto no meio do envio retoma pela consulta ao abrir;
  - a senha do certificado não aparece em log nem em arquivo;
  - produção recusada sem a liberação; nenhum pedido sai para produção;
  - a rejeição chega traduzida (código + frase + campo).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n3_envio.py
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n3-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_NFSE_SEM_FILA"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from _nfse_comum import CNPJ_PRESTADOR, CNPJ_TOMADOR, GOIANIA, certificado_a1, checar, falhas  # noqa: E402

SENHA = "senha-secreta-do-a1-7731"
LOG = TMP / "paulus.log"


def preparar(api) -> None:
    e = api.estado.nfse
    e.ligar(True)
    e.prestador.gravar({
        "documento": CNPJ_PRESTADOR, "razao_social": "Escritório de Teste", "inscricao_municipal": "123456",
        "municipio": GOIANIA, "opcao_simples": "1",
        "servico": {"ctribnac": "171401", "nbs": "113012000", "descricao": "Honorários advocatícios", "aliquota_iss_pct": "5"},
        "retencoes": {"irrf": {"quando": "tomador_pj", "aliquota_pct": "1,5"}, "pis": {"quando": "nunca"},
                      "cofins": {"quando": "nunca"}, "csll": {"quando": "nunca"}, "cp": {"quando": "nunca"},
                      "iss": {"quando": "nunca"}},
        "ibscbs": {"enviar": True, "cst": "200", "cclasstrib": "200052", "cindop": "100301"},
    }, quem="teste")
    certificado_a1(TMP / "a1.pfx", senha=SENHA)
    e.instalar_certificado("a1.pfx", (TMP / "a1.pfx").read_bytes(), SENHA, False)
    api.estado.base.escrever("INSERT OR REPLACE INTO nfse_municipio (cmun, ambiente, situacao, consultado_em) "
                             "VALUES (?, 'producao_restrita', 'conveniado', datetime('now'))", (GOIANIA,))


def nota_aprovada(api, valor: str = "5.000,00") -> dict:
    e = api.estado.nfse
    cid = api.estado.cadastros.salvar({"nome": "ACME Ltda", "documento": CNPJ_TOMADOR, "end_logradouro": "Rua 1",
                                       "end_numero": "10", "end_bairro": "Centro", "end_cep": "74000000", "end_cmun": GOIANIA})
    n = e.notas.criar({"cadastro_id": cid, "valor": valor, "descricao": "Honorários de setembro",
                       "competencia": "2026-09-30"}, origem="teste")
    assert not n["erros"], n["erros"]
    return e.notas.mudar_estado(n["id"], "aprovada", "teste", "aprovada (teste)")


def sefin(nome: str, modos):
    from _sefin_simulada import SefinSimulada

    certificado_a1(TMP / "sefin.pfx", senha="sefin", nome="SEFIN NACIONAL TESTE")
    return SefinSimulada(TMP / f"sefin-{nome}.json", modos, (TMP / "sefin.pfx").read_bytes(), "sefin")


def test_sucesso_e_assinatura(api) -> None:
    print("\nsucesso: assina, envia, recebe a NFS-e; a assinatura vale no .NET")
    from nfse import assinatura

    e = api.estado.nfse
    s = sefin("sucesso", "sucesso")
    e.transporte = s
    n = nota_aprovada(api)
    n = e.envio.emitir(n["id"], "teste")
    checar(n["estado"] == "emitida" and n["chave"] and n["numero_nfse"], "emitida, com chave e número", (n["estado"], n["ultimo_erro"]))
    checar(s.recebidas(n["id_dps"]) == 1 and len(s.geradas()) == 1, "uma DPS recebida, uma nota gerada")
    dps = Path(n["xml_dps"]).read_bytes()
    nfse = Path(n["xml_nfse"]).read_bytes()
    checar(assinatura.verificar(dps)[0], "a DPS assinada confere aqui", assinatura.verificar(dps))
    checar(assinatura.verificar(nfse)[0], "a assinatura da NFS-e devolvida confere", assinatura.verificar(nfse))
    import hashlib

    checar(hashlib.sha256(dps).hexdigest() == n["hash_enviado"] and hashlib.sha256(nfse).hexdigest() == n["hash_recebido"],
           "o hash do XML enviado e do recebido ficam guardados")
    from nfse import conferencia

    checar(not conferencia.validar_xsd(dps, "producao_restrita"), "a DPS assinada valida no XSD (com a Signature)",
           conferencia.validar_xsd(dps, "producao_restrita")[:2])
    checar(not conferencia.validar_xsd(nfse, "producao_restrita", "NFSe_v1.01.xsd"), "a NFS-e simulada valida no XSD da NFS-e",
           conferencia.validar_xsd(nfse, "producao_restrita", "NFSe_v1.01.xsd")[:2])
    sefin_vals = n["conta"].get("sefin") or {}
    checar(sefin_vals.get("v_liq") == 492500, "o valor líquido calculado pela Sefin fica na nota", sefin_vals)

    # A verificação independente: o SignedXml do .NET (o motor do lado de lá).
    ps = (
        "Add-Type -AssemblyName System.Security; $d = New-Object System.Xml.XmlDocument; $d.PreserveWhitespace = $true; "
        "$d.Load($env:ARQ); $s = New-Object System.Security.Cryptography.Xml.SignedXml($d); "
        "$n = $d.GetElementsByTagName('Signature', 'http://www.w3.org/2000/09/xmldsig#')[0]; $s.LoadXml($n); $s.CheckSignature()"
    )
    if shutil.which("powershell"):
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                           env={**os.environ, "ARQ": n["xml_dps"]}, timeout=60)
        checar(r.stdout.strip() == "True", "a assinatura da DPS vale no SignedXml do .NET (verificação independente)",
               (r.stdout.strip(), r.stderr.strip()[:200]))
        adulterado = TMP / "adulterado.xml"
        adulterado.write_bytes(dps.replace(b"<vServ>5000.00</vServ>", b"<vServ>5000.01</vServ>"))
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                           env={**os.environ, "ARQ": str(adulterado)}, timeout=60)
        checar(r.stdout.strip() == "False", "e um centavo mudado depois de assinar o .NET recusa", r.stdout.strip())
    else:
        print("  pulado: sem PowerShell para a verificação independente")


def test_rejeicao(api) -> None:
    print("\nrejeição: traduzida; corrigida, volta com a MESMA identidade de DPS")
    e = api.estado.nfse
    s = sefin("rejeicao", ["rejeicao", "sucesso"])
    e.transporte = s
    n = nota_aprovada(api)
    n = e.envio.emitir(n["id"], "teste")
    checar(n["estado"] == "rejeitada", "rejeitada", n["estado"])
    r = (n["rejeicao"] or [{}])[0]
    checar(r.get("codigo") == "E0595" and "Campo: alíquota do ISS" in r.get("frase", "") and r.get("campo") == "pAliq",
           "código oficial + frase + campo a corrigir", r)
    ident = n["id_dps"]
    n = e.notas.atualizar(n["id"], {"descricao": "Honorários de setembro (corrigido)"})
    checar(n["estado"] == "rejeitada" and not n["erros"], "a rejeitada se edita e confere de novo", n["erros"])
    e.notas.mudar_estado(n["id"], "aprovada", "teste", "aprovada de novo (teste)")
    n = e.envio.emitir(n["id"], "teste")
    checar(n["estado"] == "emitida" and n["id_dps"] == ident, "emitida com a mesma identidade de DPS", (n["estado"], n["id_dps"], ident))
    checar(len(s.geradas()) == 1, "uma nota só")
    metodos = [m for m, u in s.pedidos]
    checar("HEAD" in metodos[metodos.index("POST") + 1:], "antes do reenvio, consultou (HEAD /dps)", metodos)


def test_timeout_depois(api) -> None:
    print("\ntempo esgotado DEPOIS de gerar: consulta e acha; não reenvia")
    e = api.estado.nfse
    s = sefin("timeout-depois", ["timeout_depois", "sucesso"])
    e.transporte = s
    n = nota_aprovada(api)
    n = e.envio.emitir(n["id"], "teste")
    checar(n["estado"] == "emitida", "emitida pela consulta", (n["estado"], n["ultimo_erro"]))
    checar(s.recebidas(n["id_dps"]) == 1 and len(s.geradas()) == 1, "a DPS foi enviada UMA vez; uma nota só",
           (s.recebidas(n["id_dps"]), len(s.geradas())))
    checar(any("confirmada pela consulta" in p["detalhe"] for p in e.notas.passos(n["id"])), "o passo diz que veio da consulta")


def test_timeout_antes(api) -> None:
    print("\ntempo esgotado ANTES de gerar: consulta diz que não existe; reenvia a mesma DPS")
    e = api.estado.nfse
    s = sefin("timeout-antes", ["timeout_antes", "sucesso"])
    e.transporte = s
    n = nota_aprovada(api)
    n = e.envio.emitir(n["id"], "teste")
    checar(n["estado"] == "na_fila" and n["proxima_tentativa"], "na fila, com a próxima tentativa marcada", (n["estado"], n["proxima_tentativa"]))
    checar(not s.geradas(), "nenhuma nota gerada ainda")
    e.envio.processar_fila("teste")
    checar(e.notas.obter(n["id"])["estado"] == "na_fila", "a fila respeita a espera (não tenta antes da hora)")
    api.estado.base.escrever("UPDATE nfse_notas SET proxima_tentativa = '2000-01-01T00:00:00' WHERE id = ?", (n["id"],))
    e.envio.processar_fila("teste")
    n = e.notas.obter(n["id"])
    checar(n["estado"] == "emitida", "na hora, consulta (não existe) e reenvia: emitida", (n["estado"], n["ultimo_erro"]))
    checar(s.recebidas(n["id_dps"]) == 2 and len(s.geradas()) == 1, "duas chegadas, uma nota só",
           (s.recebidas(n["id_dps"]), len(s.geradas())))


def test_fora(api) -> None:
    print("\nservidor fora: fica na fila, com espera crescente, e nunca some")
    e = api.estado.nfse
    s = sefin("fora", ["fora"])
    e.transporte = s
    n = nota_aprovada(api)
    n = e.envio.emitir(n["id"], "teste")
    checar(n["estado"] == "na_fila", "na fila", n["estado"])
    esperas = []
    for _ in range(3):
        api.estado.base.escrever("UPDATE nfse_notas SET proxima_tentativa = '2000-01-01T00:00:00' WHERE id = ?", (n["id"],))
        e.envio.processar_fila("teste")
        x = e.notas.obter(n["id"])
        esperas.append(x["ultimo_erro"])
    checar(e.notas.obter(n["id"])["estado"] in ("na_fila", "aguardando_confirmacao"), "continua esperando, sem sumir")
    checar(not s.geradas(), "e nada foi gerado")
    s.modos = ["sucesso"]
    api.estado.base.escrever("UPDATE nfse_notas SET proxima_tentativa = '2000-01-01T00:00:00' WHERE id = ?", (n["id"],))
    e.envio.processar_fila("teste")
    n = e.notas.obter(n["id"])
    checar(n["estado"] == "emitida" and len(s.geradas()) == 1, "voltou o servidor: emitida, uma nota só", n["estado"])
    passos = [p["detalhe"] for p in e.notas.passos(n["id"])]
    checar(any("nova tentativa em 1 min" in p for p in passos) and any("nova tentativa em 2 min" in p for p in passos),
           "espera crescente (1 min, 2 min, …)", [p for p in passos if "tentativa" in p][:4])


def test_erro500(api) -> None:
    print("\nerro 500 DEPOIS de gerar: consulta e acha")
    e = api.estado.nfse
    s = sefin("500", ["erro500_depois", "sucesso"])
    e.transporte = s
    n = nota_aprovada(api)
    n = e.envio.emitir(n["id"], "teste")
    checar(n["estado"] == "emitida" and s.recebidas(n["id_dps"]) == 1 and len(s.geradas()) == 1,
           "emitida pela consulta; uma chegada, uma nota", (n["estado"], s.recebidas(n["id_dps"])))


def test_e0014(api) -> None:
    print("\nreenvio que esbarra em E0014: vira consulta, nunca segunda nota")
    e = api.estado.nfse
    s = sefin("e0014", "sucesso")
    e.transporte = s
    n = nota_aprovada(api)
    n = e.envio.emitir(n["id"], "teste")
    # Força o caminho errado: alguém pôs a nota de volta em "assinada, nunca tentada".
    api.estado.base.escrever("UPDATE nfse_notas SET estado = 'assinada', tentativas = 0 WHERE id = ?", (n["id"],))
    n2 = e.envio.emitir(n["id"], "teste")
    checar(n2["estado"] == "emitida" and n2["chave"] == n["chave"] and len(s.geradas()) == 1,
           "E0014: consultou e ficou com a mesma nota", (n2["estado"], len(s.geradas())))


def test_processo_morto(api) -> None:
    print("\no processo morre no meio do envio: ao abrir, consulta antes de qualquer reenvio")
    e = api.estado.nfse
    s = sefin("morto", "sucesso")
    n = nota_aprovada(api)
    e.transporte = s
    n = e.envio.assinar(n["id"], "teste")
    codigo = (
        "import os, sys\n"
        "sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])\n"
        "os.environ['PAULUS_NFSE_SEM_FILA'] = '1'\n"
        "from base import Base\nfrom config import Preferencias\nfrom nfse.servico import Emissor\n"
        "from _sefin_simulada import SefinSimulada\n"
        "e = Emissor(Base(sys.argv[3]), Preferencias(sys.argv[4]), sys.argv[5])\n"
        "e.transporte = SefinSimulada(sys.argv[6], 'trava')\n"
        "e.envio.emitir(int(sys.argv[7]), 'processo que vai morrer')\n"
    )
    import api as api_mod

    filho = subprocess.Popen([sys.executable, "-c", codigo, str(RAIZ / "src"), str(RAIZ / "tests"),
                              str(api.estado.base.caminho), str(api_mod.PREFERENCIAS_PATH), str(api_mod.DADOS_DIR),
                              str(s.arquivo), str(n["id"])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    fim = time.time() + 60
    while time.time() < fim and not s.geradas():
        time.sleep(0.2)
    checar(bool(s.geradas()), "a Sefin gerou a nota e o processo ficou sem resposta")
    checar(e.notas.obter(n["id"])["estado"] == "enviando", "o estado gravado antes do passo: “enviando”",
           e.notas.obter(n["id"])["estado"])
    filho.kill()
    filho.wait(timeout=30)
    e.transporte = sefin("morto", "sucesso")
    e.envio.retomar("abertura (teste)")
    n = e.notas.obter(n["id"])
    checar(n["estado"] == "emitida", "ao abrir: consultou e achou a nota", (n["estado"], n["ultimo_erro"]))
    checar(e.transporte.recebidas(n["id_dps"]) == 1 and len(e.transporte.geradas()) == 1,
           "não reenviou: uma chegada, uma nota", e.transporte.recebidas(n["id_dps"]))
    passos = [p["detalhe"] for p in e.notas.passos(n["id"])]
    checar(any("fechou durante o envio" in p for p in passos), "o passo conta o que houve", passos[-4:])


def test_producao_trancada(api) -> None:
    print("\nprodução trancada sem a liberação; nada sai para produção")
    from nfse.cliente import Cliente, ProducaoBloqueada

    try:
        Cliente("producao", transporte=lambda *a: None)
        checar(False, "o cliente recusa produção sem a liberação")
    except ProducaoBloqueada as exc:
        checar("não foi liberada" in str(exc), "o cliente recusa produção sem a liberação", str(exc))
    e = api.estado.nfse
    s = sefin("prod", "sucesso")
    e.transporte = s
    n = nota_aprovada(api)
    api.estado.base.escrever("UPDATE nfse_notas SET ambiente = 'producao' WHERE id = ?", (n["id"],))
    try:
        e.envio.emitir(n["id"], "teste")
        checar(False, "nota de produção sem liberação não sai")
    except ProducaoBloqueada:
        checar(True, "nota de produção sem liberação não sai")
    checar(not s.pedidos, "nenhum pedido chegou ao servidor", s.pedidos)
    checar(not e.producao_liberada(), "sem liberação registrada")


def test_contrato(api) -> None:
    print("\nos nomes do JSON conferidos no Swagger oficial; divergência trava o envio")
    import json

    from nfse.cliente import CAMPOS, Cliente, Resposta

    swagger = {"paths": {"/nfse": {}}, "components": {"schemas": {k: {} for k in CAMPOS.values()}}}

    def com_swagger(metodo, url, corpo):
        return Resposta(200, swagger) if url.endswith("swagger.json") else Resposta(404, None)

    r = Cliente("producao_restrita", transporte=com_swagger).conferir_contrato()
    checar(r["ok"] and not r["faltam"], "Swagger com todos os nomes: ok", r)
    swagger["components"]["schemas"].pop("dpsXmlGZipB64")
    r = Cliente("producao_restrita", transporte=com_swagger).conferir_contrato()
    checar(not r["ok"] and r["faltam"] == ["dpsXmlGZipB64"], "Swagger sem um nome: diz qual falta", r)

    e = api.estado.nfse
    e.transporte = None
    (e.pasta / "contrato.json").write_text(json.dumps({"fonte": ["https://sefin/x"], "faltam": ["dpsXmlGZipB64"]}), encoding="utf-8")
    n = nota_aprovada(api)
    try:
        e.envio.emitir(n["id"], "teste")
        checar(False, "com divergência no contrato, o envio real trava")
    except ValueError as exc:
        checar("Swagger oficial não tem os campos dpsXmlGZipB64" in str(exc), "com divergência no contrato, o envio real trava", str(exc))
    checar(e.notas.obter(n["id"])["estado"] == "assinada" and not e.notas.obter(n["id"])["tentativas"],
           "e a nota fica assinada, sem tentativa", e.notas.obter(n["id"])["estado"])
    (e.pasta / "contrato.json").unlink()


def test_senha_fora_de_log_e_arquivo(api) -> None:
    print("\na senha do certificado não aparece em log nem em arquivo")
    for h in logging.getLogger().handlers:
        h.flush()
    achados = []
    for p in TMP.rglob("*"):
        if p.is_file() and p.name != "a1.pfx":
            try:
                conteudo = p.read_bytes()
            except OSError:
                continue
            if SENHA.encode() in conteudo or SENHA.encode("utf-16-le") in conteudo:
                achados.append(str(p))
    checar(LOG.exists() and LOG.stat().st_size > 0, "houve log do envio (para a busca valer)")
    checar(not achados, "a senha não está em nenhum arquivo nem no log", achados)
    texto = LOG.read_text(encoding="utf-8", errors="replace")
    checar("dpsXmlGZipB64" not in texto and "<infDPS" not in texto, "o log não traz o conteúdo da DPS")


def main() -> int:
    logging.basicConfig(filename=str(LOG), level=logging.DEBUG, encoding="utf-8")
    try:
        import api

        preparar(api)
        test_sucesso_e_assinatura(api)
        test_rejeicao(api)
        test_timeout_depois(api)
        test_timeout_antes(api)
        test_fora(api)
        test_erro500(api)
        test_e0014(api)
        test_processo_morto(api)
        test_producao_trancada(api)
        test_contrato(api)
        test_senha_fora_de_log_e_arquivo(api)
        from _sefin_simulada import SefinSimulada  # noqa: F401
    finally:
        logging.shutdown()
        shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s): {falhas}")
        return 1
    print("\ntodos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
