"""
N3 - a parte contrária sugerida pelos documentos do Serviço (src/clientes.py, js/65-clientes.js).

  - nos documentos da pasta do Serviço e nos ligados a ele: onde o cliente
    aparece, a parte do papel oposto é sugerida como parte contrária, com o
    CNPJ escrito perto do nome e o porquê;
  - a mesma empresa com outro nome junta numa sugestão só, com os dois
    documentos;
  - o fiador do outro lado é interessado; o do cliente, não entra; advogado
    e testemunha, também não;
  - documento em que o cliente não aparece: não dá para saber o lado, e diz
    quantos; documento de outro Serviço fica de fora;
  - anotada, sai da sugestão; "não é", também (e não volta com outro jeito
    de escrever); Serviço sem cliente diz por quê;
  - no Edge: a sugestão na seção Partes, "Anotar" e "Não é".

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n3_parte_contraria.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n3-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def main() -> int:
    print("=" * 55)
    print("  N3 — a parte contrária pelos documentos")
    print("=" * 55)
    import api
    from extract import Document
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    base = api.estado.base
    alfa = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "Construtora Alfa Ltda",
                                                                    "documento": "11.444.777/0001-61"}}).json()["id"]
    s1 = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Locação da sede", "cadastro_id": alfa}}).json()["id"]
    s2 = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Outro assunto", "cadastro_id": alfa}}).json()["id"]
    s3 = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Sem cliente"}}).json()["id"]
    pasta = api.estado.servicos.pasta_de(s1, criar=True)
    pasta2 = api.estado.servicos.pasta_de(s2, criar=True)
    docs = []

    def doc(i, caminho, texto, partes, sha1=""):
        base.escrever("INSERT INTO meta_documentos (id, titulo, caminho, versao_atual, criado_em, atualizado_em) VALUES (?,?,?,?,?,?)",
                      (f"d{i}", Path(caminho).name, str(caminho), f"v{i}", "2026-09-30", "2026-09-30"))
        base.escrever("INSERT INTO meta_versoes (id, documento_id, sha256, criado_em) VALUES (?,?,?,?)", (f"v{i}", f"d{i}", f"s{i}", "2026-09-30"))
        for j, (papel, nome) in enumerate(partes):
            base.escrever("INSERT INTO meta_fatos (versao_id, documento_id, secao, item_id, chave, valor, mostrar, verificado)"
                          " VALUES (?,?,?,?,?,?,?,1)", (f"v{i}", f"d{i}", "parties", f"p{j}", papel, nome.lower(), nome))
        docs.append(Document(name=Path(caminho).name, path=str(caminho), text=texto, sha1=sha1 or f"sha{i}"))

    doc(1, pasta / "contrato-locacao.pdf",
        "CONTRATO DE LOCAÇÃO. LOCADORA: IMOBILIÁRIA BETA S/A, inscrita no CNPJ sob o nº 11.222.333/0001-81, com sede em Goiânia. "
        "LOCATÁRIA: CONSTRUTORA ALFA LTDA. FIADOR: João Pereira, CPF 529.982.247-25. Testemunha: Carla Dias.",
        [("lessor", "IMOBILIÁRIA BETA S/A"), ("lessee", "CONSTRUTORA ALFA LTDA."), ("guarantor", "João Pereira"),
         ("witness", "Carla Dias"), ("lawyer", "Dr. Paulo Advogado")])
    fora = TMP / "fora"
    fora.mkdir()
    doc(2, fora / "notificacao.pdf", "NOTIFICAÇÃO. Construtora Alfa, notificante, e Beta Imobiliária, notificada.",
        [("plaintiff", "Construtora Alfa"), ("defendant", "Beta Imobiliária")], sha1="shaligado")
    base.escrever("INSERT INTO vinculos (tipo, alvo_id, sha1, nome, criado_em) VALUES ('servico', ?, 'shaligado', 'notificacao.pdf', '2026-09-30')", (s1,))
    doc(3, pasta / "laudo.pdf", "LAUDO. Perito: Marcos Lima. Interessada: Prefeitura de Itu.", [("plaintiff", "Prefeitura de Itu"), ("defendant", "Estado de SP")])
    doc(4, pasta / "sublocacao.pdf",
        "SUBLOCAÇÃO. SUBLOCADORA: Construtora Alfa Ltda. SUBLOCATÁRIO: Pedro Souza, CPF 111.444.777-35. FIADORA: Ana Lima.",
        [("lessor", "Construtora Alfa Ltda"), ("lessee", "Pedro Souza"), ("guarantor", "Ana Lima")])
    doc(5, pasta2 / "outro.pdf", "Outro. Autor: Construtora Alfa. Réu: Empresa Gama.", [("plaintiff", "Construtora Alfa"), ("defendant", "Empresa Gama")])
    api.estado.searcher.documents = list(api.estado.searcher.documents) + docs

    print("\na sugestão")
    d = local.get(f"/api/servicos/{s1}/partes/sugeridas").json()
    por_nome = {x["nome"]: x for x in d["sugeridas"]}
    beta = por_nome.get("IMOBILIÁRIA BETA S/A") or {}
    checar(beta.get("papel") == "contraria" and beta.get("documento") == "11.222.333/0001-81" and "locatário" in beta.get("porque", "")
           and "locador" in beta.get("porque", ""), "a parte do papel oposto, com o CNPJ escrito perto e o porquê", beta)
    checar(sorted(beta.get("documentos", [])) == ["contrato-locacao.pdf", "notificacao.pdf"] and "Beta Imobiliária" in beta.get("outros_nomes", []),
           "a mesma empresa com outro nome junta, com os dois documentos (o da pasta e o ligado)", beta)
    checar(por_nome.get("Pedro Souza", {}).get("papel") == "contraria" and por_nome.get("Pedro Souza", {}).get("documento") == "111.444.777-35",
           "onde o cliente é locador, o locatário é a parte contrária", por_nome.get("Pedro Souza"))
    checar(por_nome.get("Ana Lima", {}).get("papel") == "interessado", "o fiador do outro lado é interessado", por_nome.get("Ana Lima"))
    checar("João Pereira" not in por_nome and "Carla Dias" not in por_nome and "Dr. Paulo Advogado" not in por_nome,
           "o fiador do cliente, a testemunha e o advogado não entram", list(por_nome))
    checar(not any("ALFA" in n.upper() for n in por_nome) and "Empresa Gama" not in por_nome,
           "o próprio cliente não é sugerido, e o documento de outro Serviço fica de fora", list(por_nome))
    checar(d["sem_lado"] == ["laudo.pdf"] and d["lidos"] == 4, "documento sem o cliente: não dá para saber o lado", (d["sem_lado"], d["lidos"]))

    print("\nanotar e dispensar")
    local.put(f"/api/servicos/{s1}/partes", json={"partes": [{"nome": beta["nome"], "documento": beta["documento"], "papel": "contraria"}]})
    local.post(f"/api/servicos/{s1}/partes/dispensar", json={"nome": "pedro souza"})
    d = local.get(f"/api/servicos/{s1}/partes/sugeridas").json()
    nomes = [x["nome"] for x in d["sugeridas"]]
    checar(nomes == ["Ana Lima"], "anotada e dispensada saem da sugestão (e a outra grafia da anotada também)", nomes)
    d = local.get(f"/api/servicos/{s3}/partes/sugeridas").json()
    checar(not d["sugeridas"] and "não tem cliente" in d["motivo"], "Serviço sem cliente diz por quê", d)
    checar(local.get("/api/servicos/99999/partes/sugeridas").status_code == 404, "Serviço que não existe: 404")

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        base.escrever("UPDATE servicos SET partes = '[]', partes_dispensadas = '[]' WHERE id = ?", (s1,))
        porta = _porta_livre()
        _subir_servidor(porta)
        # Ao subir, o servidor recarrega o Acervo do disco: os documentos do teste voltam depois.
        import time

        time.sleep(1.5)
        api.estado.searcher.documents = [x for x in api.estado.searcher.documents if x.sha1 not in {d.sha1 for d in docs}] + docs
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                pag = nav.new_context(viewport={"width": 1280, "height": 900}).new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof abrirServico === 'function' && typeof carregarPartesSugeridas === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate(f"() => {{ abrirServico({s1}); }}")
                pag.wait_for_selector(".cli-sugerida", timeout=15000)
                texto = pag.inner_text(".cli-sugeridas")
                checar("IMOBILIÁRIA BETA S/A" in texto and "11.222.333/0001-81" in texto and "Pedro Souza" in texto and "laudo" not in texto
                       and "o cliente não aparece" in texto, "a seção Partes mostra as sugeridas e o documento sem lado", texto[:300])
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n3-sugeridas.png"))
                pag.click(".cli-sugerida:has-text('IMOBILIÁRIA BETA') [data-cli-aceitar]")
                pag.wait_for_timeout(1200)
                if pag.locator("#veu-dialogo [data-dialogo='confirmar']").count():
                    pag.click("#veu-dialogo [data-dialogo='confirmar']")
                    pag.wait_for_timeout(600)
                partes = (base.um("SELECT partes FROM servicos WHERE id = ?", (s1,)) or {}).get("partes", "")
                checar("IMOBILIÁRIA BETA" in partes and "11.222.333/0001-81" in partes, "“Anotar” põe a parte, com o CNPJ", partes)
                pag.wait_for_selector(".cli-sugerida:has-text('Pedro Souza')", timeout=15000)
                pag.click(".cli-sugerida:has-text('Pedro Souza') [data-cli-dispensar]")
                pag.wait_for_timeout(1200)
                checar(pag.locator(".cli-sugerida:has-text('Pedro Souza')").count() == 0, "“Não é” tira a sugestão")
                pag.set_viewport_size({"width": 390, "height": 844})
                pag.wait_for_timeout(400)
                largura = pag.evaluate("() => document.documentElement.scrollWidth")
                checar(largura <= 392, "no celular (390 px), nada vaza para o lado", largura)
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
                nav.close()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for x in _falhas:
            print(f"    - {x}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
