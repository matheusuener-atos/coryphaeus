"""
Portão da N9 do emissor de NFS-e — os textos dizem a verdade.

Em três estados — emissão desligada, ligada com o município SEM convênio e
ligada com convênio — confere o que a pessoa lê:

  - no mapa do programa (o que a conversa responde sobre as telas);
  - na tela, num Edge de verdade: o Financeiro, a lista e o registro de notas,
    o cartão da NFS-e na conversa e Configurações › Nota fiscal;
  - na resposta de confirmar o cartão da conversa.

Falha se aparecer "não emite nota fiscal" (ou "a nota é emitida no sistema
da prefeitura") com a emissão ligada, ou se aparecer que emite ("Emitir
nota", "a nota sai daqui pelo Padrão Nacional", "Dá para emitir") com o
município sem convênio ou a emissão desligada. E o manual cobre cada tela.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n9_textos.py
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n9-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_NFSE_SEM_FILA"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from _nfse_comum import CNPJ_PRESTADOR, CNPJ_TOMADOR, GOIANIA, certificado_a1, checar, falhas  # noqa: E402

NAO_EMITE = (re.compile(r"n[ãa]o emite nota fiscal", re.I), re.compile(r"a nota é emitida no sistema da prefeitura", re.I))
EMITE = (re.compile(r"\bEmitir nota\b"), re.compile(r"a nota sai daqui pelo Padrão Nacional", re.I),
         re.compile(r"Dá para emitir pelo padrão nacional", re.I), re.compile(r"Emite NFS-e pelo Padrão Nacional", re.I),
         re.compile(r"O sim cria só o rascunho", re.I))


def estado(api, nome: str) -> None:
    e = api.estado.nfse
    if nome == "desligada":
        e.ligar(False)
        sit = "conveniado"
    else:
        e.ligar(True)
        sit = "sem_convenio" if nome == "sem_convenio" else "conveniado"
    api.estado.base.escrever("INSERT OR REPLACE INTO nfse_municipio (cmun, ambiente, situacao, detalhes, consultado_em) "
                             "VALUES (?, 'producao_restrita', ?, '', datetime('now'))", (GOIANIA, sit))


def textos_do_mapa() -> str:
    import programa

    partes = []
    for t in programa.mapa_para(True).values():
        partes += t.faz + t.nao_faz
    return "\n".join(partes)


def _porta() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _subir(api, porta: int) -> None:
    import uvicorn

    api.estado.porta = porta
    servidor = uvicorn.Server(uvicorn.Config(api.app, host="127.0.0.1", port=porta, log_level="error"))
    threading.Thread(target=servidor.run, daemon=True).start()
    limite = time.time() + 40
    while time.time() < limite:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                return
        time.sleep(0.3)
    raise RuntimeError("o servidor não subiu")


def textos_da_tela(pag) -> dict:
    """O que a pessoa lê, por lugar."""
    t: dict[str, str] = {}
    pag.evaluate("() => { nfseDisponivel = null; mostrarFinanceiro('visao'); }")
    pag.wait_for_timeout(2500)
    t["financeiro"] = pag.evaluate("() => document.getElementById('centro').innerText")
    pag.evaluate("() => { finVerPapeis('nota'); }")
    pag.wait_for_timeout(800)
    t["lista de notas"] = pag.evaluate("() => (document.querySelector('.veu-dialogo') || {}).innerText || ''")
    pag.evaluate("() => { if (dialogoAberto) dialogoAberto.fechar(null); }")
    pag.wait_for_timeout(400)
    pag.evaluate("() => { finFormPapel('nota', null); }")
    pag.wait_for_timeout(800)
    t["registrar nota"] = pag.evaluate("() => (document.querySelector('.veu-dialogo') || {}).innerText || ''")
    pag.evaluate("() => { if (dialogoAberto) dialogoAberto.fechar(null); }")
    pag.wait_for_timeout(400)
    t["cartão da conversa"] = pag.evaluate(
        "async () => { const r = await fetch('/api/nfse/disponivel'); const d = await r.json();"
        " const div = document.createElement('div');"
        " div.innerHTML = cartaoFerramenta({tipo: 'nota', campos: {}, porque: 'emita a NFS-e',"
        "   disponivel: d.ligado && d.motivos.every((m) => !/Sistema Nacional/.test(m))});"
        " return div.innerText; }")
    pag.evaluate("() => { mostrarConfig('nfse'); }")
    pag.wait_for_timeout(2500)
    t["configurações"] = pag.evaluate("() => document.getElementById('centro').innerText")
    return t


def conferir_textos(nome: str, textos: dict, emite: bool) -> None:
    for lugar, texto in textos.items():
        if emite:
            achado = [p.pattern for p in NAO_EMITE if p.search(texto)]
            checar(not achado, f"{nome}: {lugar} não diz que não emite", achado)
        else:
            achado = [p.pattern for p in EMITE if p.search(texto)]
            checar(not achado, f"{nome}: {lugar} não diz que emite", achado)


def main() -> int:
    try:
        import api

        e = api.estado.nfse
        e.prestador.gravar({
            "documento": CNPJ_PRESTADOR, "razao_social": "Escritório de Teste", "inscricao_municipal": "123456",
            "municipio": GOIANIA, "opcao_simples": "1",
            "servico": {"ctribnac": "171401", "nbs": "113012000", "descricao": "Honorários advocatícios", "aliquota_iss_pct": "5"},
            "retencoes": {k: {"quando": "nunca"} for k in ("irrf", "pis", "cofins", "csll", "cp", "iss")},
            "ibscbs": {"enviar": True, "cst": "200", "cclasstrib": "200052", "cindop": "100301"},
        }, quem="teste")
        certificado_a1(TMP / "a1.pfx", senha="s-n9")
        e.instalar_certificado("a1.pfx", (TMP / "a1.pfx").read_bytes(), "s-n9", True)
        cid = api.estado.cadastros.salvar({"nome": "ACME Ltda", "documento": CNPJ_TOMADOR, "end_logradouro": "Rua 1",
                                           "end_numero": "1", "end_bairro": "Centro", "end_cep": "74000000", "end_cmun": GOIANIA})
        from datetime import date

        hoje = date.today().isoformat()
        lid = api.estado.financeiro.salvar({"tipo": "recebimento", "descricao": "Honorários", "centavos": 100000,
                                            "cadastro_id": cid, "vencimento": hoje})
        api.estado.financeiro.liquidar(lid, hoje)

        print("\no mapa do programa")
        for nome, emite in (("desligada", False), ("sem_convenio", False), ("ligada", True)):
            estado(api, nome)
            texto = textos_do_mapa()
            if emite:
                checar(not any(p.search(texto) for p in NAO_EMITE), f"{nome}: o mapa não diz que não emite",
                       [l for l in texto.splitlines() if any(p.search(l) for p in NAO_EMITE)])
                checar("Emite NFS-e pelo Padrão Nacional" in texto, f"{nome}: o mapa diz que o Financeiro emite")
            else:
                checar(not any(p.search(texto) for p in EMITE), f"{nome}: o mapa não diz que emite",
                       [l for l in texto.splitlines() if any(p.search(l) for p in EMITE)])
                checar("Não emite nota fiscal" in texto, f"{nome}: o mapa diz que não emite")

        print("\na resposta de confirmar o cartão da conversa")
        from fastapi.testclient import TestClient

        local = TestClient(api.app, headers=api.cabecalho_local())
        for nome, emite in (("desligada", False), ("sem_convenio", False), ("ligada", True)):
            estado(api, nome)
            tid = local.post("/api/trabalhos", json={"pedido": f"nota {nome}"}).json()["id"]
            r = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "nota", "campos": {"cliente": "ACME Ltda", "valor": "R$ 100,00"}})
            resumo = r.json().get("resumo", "")
            if emite:
                checar("Preparei o rascunho" in resumo and "nada foi enviado ainda" in resumo, f"{nome}: prepara o rascunho", resumo)
            else:
                checar("não está disponível" in resumo and "nada foi enviado nem gravado" in resumo, f"{nome}: só confere", resumo)

        print("\nna tela (Edge)")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("  pulado: playwright não instalado")
            sync_playwright = None
        if sync_playwright:
            porta = _porta()
            _subir(api, porta)
            base = f"http://127.0.0.1:{porta}"
            with sync_playwright() as p:
                try:
                    nav = p.chromium.launch(channel="msedge")
                except Exception as exc:  # noqa: BLE001
                    print(f"  pulado: sem o Edge ({str(exc)[:60]})")
                    nav = None
                if nav:
                    pag = nav.new_page(viewport={"width": 1440, "height": 900})
                    pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                    erros: list[str] = []
                    pag.on("pageerror", lambda ex: erros.append(str(ex)))
                    pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="networkidle")
                    pag.wait_for_timeout(2000)
                    for nome, emite in (("desligada", False), ("sem_convenio", False), ("ligada", True)):
                        estado(api, nome)
                        textos = textos_da_tela(pag)
                        conferir_textos(nome, textos, emite)
                        if nome == "ligada":
                            checar("Emitir nota" in textos["financeiro"], "ligada: o Financeiro oferece Emitir nota",
                                   textos["financeiro"][:300])
                            checar("Dá para emitir pelo padrão nacional" in textos["configurações"],
                                   "ligada: Configurações diz que dá para emitir")
                        if nome == "sem_convenio":
                            checar("não emite pelo Sistema Nacional" in textos["configurações"]
                                   and "continua só registrando" in textos["configurações"],
                                   "sem convênio: Configurações diz a verdade", textos["configurações"][:300])
                            checar("Registrar a nota" in textos["financeiro"] or "Registrar" in textos["lista de notas"],
                                   "sem convênio: o Financeiro oferece só registrar")
                    checar(not erros, "nenhum erro de JavaScript", erros[:3])
                    nav.close()

        print("\no manual cobre cada tela")
        manual = (RAIZ / "docs" / "nfse.md").read_text(encoding="utf-8")
        for tela in ("Configurações › **Nota fiscal**", "**Emitir nota**", "**Emitir nota dos honorários**", "**Preparar a nota**",
                     "**Pedir aprovação**", "**Cancelar a nota**", "**Substituir**", "**Atualizar situação**",
                     "**Abrir o DANFSe**", "**Abrir o relatório do mês**", "**Exportar para o contador:**",
                     "**Mandar ao contador:**", "**Nota todo mês**", "**Produção**", "**Liberar a produção**",
                     "**Voltar para\nprodução restrita**", "Aguardando confirmação", "Rejeições comuns", "procurar o contador"):
            checar(tela.replace("\n", " ") in manual.replace("\n", " "), f"o manual fala de {tela.strip('*')}")
        js = "\n".join(f.read_text(encoding="utf-8") for f in (RAIZ / "frontend" / "js").glob("*.js"))
        for rotulo in ("Emitir nota", "Emitir nota dos honorários", "Preparar a nota", "Pedir aprovação", "Cancelar a nota",
                       "Substituir", "Atualizar situação", "Abrir o DANFSe", "Abrir o relatório do mês", "Exportar para o contador",
                       "Mandar ao contador", "Nota todo mês", "Liberar a produção", "Voltar para produção restrita",
                       "Consultar e mandar", "Registrar a revisão do contador"):
            checar(rotulo in js, f"o botão “{rotulo}” do manual existe na tela")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s): {falhas}")
        return 1
    print("\ntodos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
