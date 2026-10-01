"""
L5 - a Biblioteca ajudando a escrever (src/fundamentacao.py, js/67-fundamentacao.js).

  - os artigos que um texto cita: "art. 206 do CC e art. 85 do CPC" acha os
    dois; o CPC/73 e o CC/1916 ficam de fora;
  - os temas do STJ que vêm no instalador (Portal de Dados Abertos, CC-BY):
    entram na abertura, uma vez; sem cancelados nem controvérsias; ligados
    aos artigos que citam; "atualizar pelo STJ" com arquivo ruim não troca
    nada;
  - a posição da casa: escrever, ler, apagar em branco; só na janela do
    escritório;
  - a fundamentação de um trecho: o artigo citado nele primeiro, os achados
    pelas palavras, súmulas, temas, a posição da casa junto do artigo;
  - no Edge: "Fundamentar" no editor e inserir a citação.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_l5_fundamentacao.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-l5-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []
CAB = ("sequencialPrecedente,tipoPrecedente,numeroPrecedente,dataPrimeiraAfetacao,dataJulgamento,dataPublicacaoAcordao,situacao,"
       "informacoesComplementares,questaoSubmetidaAJulgamento,teseFirmada,anotacoesNUGEPNAC,delimitacaoJulgado,entendimentoAnterior,"
       "referenciaLegislativa,referenciaSumular,sumulaOriginada,audienciaPublica,dataAudienciaPublica,orgaoJulgador,Assuntos,"
       "numeroRepercussaoGeralSTF,descricaoRepercussaoGeral\n")


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def linha(tipo, n, situacao, questao, tese):
    return f'{n},{tipo},{n},,2020-01-01,,{situacao},,"{questao}","{tese}",,,,,,,,,S2,"Direito Civil",,\n'


def main() -> int:
    print("=" * 55)
    print("  L5 — a Biblioteca ajudando a escrever")
    print("=" * 55)
    import fundamentacao as f

    print("\nos artigos citados")
    checar(f.artigos_citados("nos termos do art. 206, § 3º, V, do Código Civil e do art. 85 do CPC/2015") == ["cc:206", "cpc:85"],
           "art. 206 do CC e art. 85 do CPC: os dois")
    checar(f.artigos_citados("o art. 20 do CPC/73 e o art. 1.228 do CC/1916") == [], "o CPC/73 e o CC/1916 ficam de fora")
    checar(f.artigos_citados("conforme art. 51, IV, do CDC") == ["cdc:51"], "com inciso no meio")
    csv = CAB + linha("Tema", 1, "Trânsito em Julgado", "Prazo do art. 206 do CC.", "É trienal a pretensão do art. 206 do Código Civil.") + \
        linha("Tema", 2, "Cancelado", "x", "y") + linha("Controvérsia", 3, "Pendente", "q", "") + linha("IAC", 4, "Afetado", "Questão do IAC", "")
    ls = f._linhas_do_csv(csv)
    checar([(x["tipo"], x["numero"]) for x in ls] == [("Tema Repetitivo", "1"), ("IAC", "4")],
           "do CSV do STJ: sem cancelados nem controvérsias", ls)

    import api
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    temas = api.estado.temas

    print("\nos temas do instalador")
    import threading
    import time

    for th in threading.enumerate():
        if th.name == "temas-stj":
            th.join(60)
    import gzip
    import json

    unicos = {(x["tipo"], x["numero"]) for x in (json.loads(l) for l in list(gzip.open(f.ARQUIVO, "rt", encoding="utf-8"))[1:])}
    checar(temas.quantos("STJ") == len(unicos) > 1200, f"os temas do instalador entram na abertura, em segundo plano ({len(unicos)}; o STJ repete o número dos revisados)",
           temas.quantos("STJ"))
    checar(temas.instalar() == 0, "e só uma vez")
    t = local.get("/api/biblioteca/temas?numero=1016").json()
    checar(t["temas"] and t["temas"][0]["rotulo"] == "Tema Repetitivo 1016/STJ" and "CC-BY" in t["licenca"], "procurar pelo número", t["temas"][:1])
    t = local.get("/api/biblioteca/temas?termo=plano de saúde faixa etária").json()["temas"]
    checar(t and any("faixa" in (x["tese"] + x["questao"]).lower() for x in t[:3]), "procurar pelas palavras", [x["rotulo"] for x in t[:3]])
    ligados = api.estado.base.um("SELECT COUNT(*) AS n FROM temas WHERE artigos != '[]'")["n"]
    checar(ligados > 150, f"temas ligados a artigos ({ligados})")
    checar(temas.do_artigo("cc", "206") and all("cc:206" in x["artigos"] for x in temas.do_artigo("cc", "206")),
           "os temas de um artigo (cc 206)", len(temas.do_artigo("cc", "206")))
    try:
        temas.atualizar_do_stj(baixar=lambda url: CAB + linha("Tema", 9, "Afetado", "a", "b"))
        checar(False, "arquivo do STJ ruim: não troca")
    except ValueError:
        checar(temas.quantos("STJ") == len(unicos), "arquivo do STJ ruim: nada trocado")

    print("\na posição da casa")
    r = local.put("/api/leis/posicao", json={"codigo": "cdc", "numero": "51", "texto": "Multa acima de 2% em relação de consumo é abusiva."})
    checar(r.status_code == 200 and local.get("/api/leis/posicao?codigo=cdc&numero=51").json()["posicao"]["texto"].startswith("Multa"),
           "escrever e ler")
    local.put("/api/leis/posicao", json={"codigo": "cc", "numero": "413", "texto": "provisória"})
    local.put("/api/leis/posicao", json={"codigo": "cc", "numero": "413", "texto": ""})
    checar(local.get("/api/leis/posicao?codigo=cc&numero=413").json()["posicao"] is None, "em branco, sai")

    print("\na fundamentação")
    from biblioteca import nativo

    nativo.instalar(api.estado.leis, api.estado.material, Path(os.environ["PAULUS_DADOS"]) / "leis", forcar=True)
    checar(local.post("/api/biblioteca/fundamentacao", json={"trecho": "curto"}).status_code == 400, "trecho curto: recusa")
    trecho = ("A multa moratória prevista no contrato de locação residencial é abusiva, nos termos do art. 51 do CDC, "
              "e deve ser reduzida, com a revisão da cláusula penal.")
    d = local.post("/api/biblioteca/fundamentacao", json={"trecho": trecho}).json()
    arts = d["artigos"]
    checar(arts and arts[0]["codigo"] == "cdc" and arts[0]["numero"] == "51" and arts[0]["porque"] == "citado no trecho",
           "o artigo citado no trecho vem primeiro", [a["citacao"] for a in arts[:3]])
    checar(arts[0]["posicao"].startswith("Multa acima de 2%"), "com a posição da casa")
    checar(len(arts) > 1 and all(a["porque"].startswith("tem ") for a in arts[1:]), "e os achados pelas palavras, com o porquê",
           [(a["citacao"], a["porque"]) for a in arts[1:4]])
    checar(any(a["codigo"] == "cc" and a["numero"] in ("408", "409", "411", "412", "413") for a in arts),
           "“cláusula penal” traz os artigos da cláusula penal do CC", [a["citacao"] for a in arts])
    checar("multa" in d["palavras"] or "moratória" in d["palavras"], "as palavras do trecho", d["palavras"])
    checar(isinstance(d["sumulas"], list) and isinstance(d["temas"], list) and d["temas"], "súmulas e temas sugeridos",
           ([s["titulo"] for s in d["sumulas"]], [t["rotulo"] for t in d["temas"]]))

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        doc = api.estado.documentos.criar("Contestação", "texto", "<p>" + trecho + "</p>")
        porta = _porta_livre()
        _subir_servidor(porta)
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                pag = nav.new_context(viewport={"width": 1360, "height": 900}).new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof abrirDocumento === 'function' && typeof fundamentarNoEditor === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate(f"() => abrirDocumento({doc})")
                pag.wait_for_selector("[data-ed-fundamentar]", timeout=15000)
                pag.click("#ed-folha p")
                pag.click("[data-ed-fundamentar]")
                pag.wait_for_selector(".fun-item", timeout=20000)
                texto = pag.inner_text(".dialogo")
                checar("Fundamentação sugerida" in texto and "citado no trecho" in texto and "Posição da casa" in texto,
                       "o diálogo com o artigo citado e a posição da casa", texto[:200])
                pag.screenshot(path=str(TMP / "l5-fundamentacao.png"))
                pag.click("[data-fun-art='0'][data-com='0']")
                pag.wait_for_timeout(400)
                checar("art. 51" in pag.inner_text("#ed-folha") or "Art. 51" in pag.inner_text("#ed-folha"),
                       "inserir a citação no documento", pag.inner_text("#ed-folha")[-120:])
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (foto em {TMP})")
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
