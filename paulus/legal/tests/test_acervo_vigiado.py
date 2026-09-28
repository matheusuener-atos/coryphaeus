"""
Testes do Acervo que vigia pastas (src/api.py, /api/acervo/*; extract.listar_arquivos).

  - incluir uma pasta a lê onde está: nada é movido nem copiado;
  - o que não entra: pasta que não existe, disco inteiro, a pasta do
    usuário inteira, pasta de sistema, pasta já vigiada; pasta que contém
    uma vigiada passa a valer no lugar dela;
  - a leitura pula pasta de sistema (node_modules), oculta e o temporário
    do Word (~$);
  - tirar documento do Acervo não apaga: o arquivo fica, sai da leitura,
    aparece em "fora do Acervo" e volta pelo devolver;
  - a vigia pega o arquivo novo e o apagado sem ninguém pedir;
  - tirar a pasta: os arquivos ficam; a pasta do PAULUS não sai;
  - apagar do disco continua pela fila, e a fila sabe que não desfaz.

Tudo numa pasta temporária (PAULUS_DADOS).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_acervo_vigiado.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-vigia-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def escrever(p: Path, texto: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(texto, encoding="utf-8")
    return p


def esperar(cond, limite=15.0) -> bool:
    fim = time.time() + limite
    while time.time() < fim:
        if cond():
            return True
        time.sleep(0.3)
    return cond()


def main() -> int:
    print("=" * 55)
    print("  o Acervo que vigia pastas")
    print("=" * 55)
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app, headers=api.cabecalho_local())
    programa = Path(api.estado.pasta)
    escrever(programa / "da casa.txt", "Documento da pasta do PAULUS: procuração da Cooperativa.")
    # Fora do AppData/Local/Temp: pasta dentro de AppData e "de sistema" para o
    # Acervo, e com razao. data/extractions ja e ignorada pelo git.
    fora_do_appdata = Path(tempfile.mkdtemp(prefix="_vigia-", dir=str(RAIZ / "data" / "extractions")))
    clientes = fora_do_appdata / "Clientes"
    contrato = escrever(clientes / "Silva" / "contrato Silva.txt", "Contrato de locação do Silva, aluguel de R$ 2.000,00.")
    recibo = escrever(clientes / "recibo.txt", "Recibo de honorários do mês de setembro.")
    escrever(clientes / "~$contrato.txt", "temporário do Word")
    escrever(clientes / "node_modules" / "lixo.txt", "nada de cliente aqui")
    escrever(clientes / ".oculta" / "x.txt", "pasta oculta")
    api.estado.recarregar()

    def nomes() -> set[str]:
        return {d.name for d in api.estado.searcher.documents}

    def pronto() -> bool:
        return not api.estado.lendo.get("andando")

    print("\nincluir")
    for caminho, parte in ((TMP / "nao-existe", "não existe"), (Path("C:/"), "disco inteiro"),
                           (Path.home(), "pasta do usuário"), (Path("C:/Windows/System32"), "sistema")):
        r = c.post("/api/acervo/pastas", json={"caminho": str(caminho)})
        checar(r.status_code == 400 and parte in r.json()["detail"], f"recusa {caminho}", r.json())
    r = c.post("/api/acervo/pastas", json={"caminho": str(clientes / "Silva")})
    checar(r.status_code == 200 and r.json()["arquivos"] == 1, "inclui uma subpasta", r.json())
    esperar(pronto)
    r = c.post("/api/acervo/pastas", json={"caminho": str(clientes / "Silva")})
    checar(r.status_code == 400 and "já está" in r.json()["detail"], "a mesma pasta não entra duas vezes")
    r = c.post("/api/acervo/pastas", json={"caminho": str(clientes)})
    d = r.json()
    checar(r.status_code == 200 and d["arquivos"] == 2, "a pasta de cima entra e conta 2 documentos (sem ~$, node_modules, oculta)", d)
    vigiadas = [p["caminho"] for p in d["pastas"]]
    checar(str(clientes.resolve()) in vigiadas and str((clientes / "Silva").resolve()) not in vigiadas,
           "a pasta de cima vale no lugar da subpasta", vigiadas)
    esperar(pronto)
    checar({"contrato Silva.txt", "recibo.txt", "da casa.txt"} <= nomes() and "lixo.txt" not in nomes() and "x.txt" not in nomes(),
           "lê os documentos onde estão, e pula o que não é de cliente", nomes())
    checar(contrato.exists() and recibo.exists(), "nada foi movido nem copiado")
    itens = {x["nome"]: x for x in c.get("/api/biblioteca?filtro=todos&limite=0").json()["documentos"]}
    checar(itens["contrato Silva.txt"]["raiz"] == str(clientes.resolve()) and not itens["contrato Silva.txt"]["do_programa"],
           "o documento sabe de que pasta vigiada vem, e que não é do PAULUS", itens["contrato Silva.txt"].get("raiz"))
    checar(itens["da casa.txt"]["do_programa"], "o da pasta do PAULUS é do programa")

    print("\ntirar e devolver documento")
    r = c.post("/api/acervo/tirar", json={"caminhos": [itens["recibo.txt"]["caminho"]]})
    checar(r.status_code == 200 and r.json()["tirados"] == 1, "tira do Acervo", r.json())
    checar(recibo.exists() and "recibo.txt" not in nomes(), "o arquivo fica no disco e sai da leitura")
    fora = c.get("/api/acervo/fora").json()["itens"]
    checar(len(fora) == 1 and fora[0]["nome"] == "recibo.txt", "aparece em fora do Acervo", fora)
    from config import Preferencias

    reaberta = Preferencias(api.estado.prefs.caminho)
    checar(len(reaberta.dados.get("acervo_fora") or []) == 1, "e continua fora depois de fechar e abrir o programa",
           reaberta.dados.get("acervo_fora"))
    c.post("/api/acervo/devolver", json={"caminhos": [fora[0]["caminho"]]})
    checar("recibo.txt" in nomes() and not c.get("/api/acervo/fora").json()["itens"], "devolver traz de volta")

    print("\ntirar e excluir (a caixa marcada)")
    import lixeira_windows

    original = lixeira_windows.mandar_para_lixeira
    lixo = escrever(clientes / "rascunho velho.txt", "Rascunho que pode ir para a lixeira.")
    preso = escrever(clientes / "preso.txt", "Arquivo que o Windows não deixa excluir.")
    api.estado.recarregar()

    def lixeira_de_mentira(caminho):
        # a de verdade foi conferida a mão: o arquivo aparece na Lixeira do Windows
        if Path(caminho).name == "preso.txt":
            return "o Windows não deixou (código 32); o arquivo pode estar aberto em outro programa"
        Path(caminho).unlink()
        return ""

    lixeira_windows.mandar_para_lixeira = lixeira_de_mentira
    try:
        r = c.post("/api/acervo/tirar", json={"caminhos": [str(lixo), str(preso)], "excluir": True})
        d = r.json()
    finally:
        lixeira_windows.mandar_para_lixeira = original
    checar(r.status_code == 200 and d["excluidos"] == [str(lixo)] and not lixo.exists(), "marcado: vai para a lixeira", d.get("excluidos"))
    checar(len(d["nao_excluidos"]) == 1 and "código 32" in d["nao_excluidos"][0]["motivo"] and preso.exists(),
           "o que o Windows não deixa excluir fica, com o motivo", d.get("nao_excluidos"))
    checar("preso.txt" not in nomes() and d["caminhos"] == [str(preso)],
           "e sai do Acervo do mesmo jeito, podendo voltar", d.get("caminhos"))
    c.post("/api/acervo/devolver", json={"caminhos": [str(preso)]})
    preso.unlink()

    print("\na vigia")
    api.VIGIA_SEGUNDOS = 0.5
    threading.Thread(target=api.estado._vigiar, daemon=True).start()
    novo = escrever(clientes / "Silva" / "aditivo Silva.txt", "Aditivo ao contrato do Silva: novo valor de R$ 2.200,00.")
    checar(esperar(lambda: "aditivo Silva.txt" in nomes()), "arquivo novo na pasta entra sozinho")
    # O Windows (antivírus, indexador) segura arquivo recém-criado por um
    # instante; a trava não pode ser do PAULUS - por isso o limite curto.
    comeco = time.time()
    while True:
        try:
            novo.unlink()
            break
        except PermissionError:
            if time.time() - comeco > 5:
                raise
            time.sleep(0.2)
    print(f"  (o arquivo ficou preso {time.time() - comeco:.1f} s)")
    checar(esperar(lambda: "aditivo Silva.txt" not in nomes()), "arquivo apagado no Windows sai sozinho")
    versao = c.get("/api/acervo/versao").json()
    checar(versao["versao"] > 0 and "lendo" in versao, "a tela tem a versão para saber que mudou", versao)

    print("\ntirar a pasta")
    r = c.post("/api/acervo/pastas/tirar", json={"caminho": str(programa)})
    checar(r.status_code == 400, "a pasta do PAULUS não sai")
    r = c.post("/api/acervo/pastas/tirar", json={"caminho": str(clientes)})
    checar(r.status_code == 200 and "contrato Silva.txt" not in nomes() and contrato.exists(),
           "tirar a pasta: sai da leitura, e os arquivos ficam", sorted(nomes()))

    print("\norganizar: só classificar")
    from classify import CacheClassificacao, Classificacao
    from extract import file_sha1

    escritorio = fora_do_appdata / "Escritório antigo"
    procuracao = escrever(escritorio / "procuracao.txt", "Procuração da Cooperativa Vale Verde para a Dra. Helena.")
    api.estado.classificacoes = {str(procuracao): Classificacao(arquivo=str(procuracao), nome=procuracao.name,
                                                                sha1=file_sha1(procuracao), tipo="procuracao", cliente="Cooperativ")}
    r = c.post("/api/organizar/so-classificar", json={
        "pastas": [str(escritorio), "C:/Windows/System32"],
        "ajustes": [{"arquivo": str(procuracao), "cliente": "Cooperativa Vale Verde"}],
    })
    d = r.json()
    checar(r.status_code == 200 and d["classificados"] == 1, "guarda a classificação conferida", d)
    checar(d["vigiadas"] == [str(escritorio.resolve())] and d["nao_vigiadas"] and "sistema" in d["nao_vigiadas"][0]["motivo"],
           "vigia a pasta onde procurou, e diz por que não vigia a de sistema", d)
    guardada = CacheClassificacao(api.CLASSIFICACAO_PATH).obter(file_sha1(procuracao))
    checar(guardada and guardada.cliente == "Cooperativa Vale Verde", "a correção de quem conferiu é o que fica guardado",
           guardada and guardada.cliente)
    checar(procuracao.exists() and esperar(lambda: pronto() and "procuracao.txt" in nomes()),
           "nenhum arquivo sai do lugar, e ele entra no Acervo onde está", sorted(nomes()))

    print("\napagar do disco")
    r = c.post("/api/biblioteca/lote/apagar", json={"caminhos": [str(programa / "da casa.txt")]})
    pedido = (r.json() or {}).get("pedido") or {}
    checar(pedido and pedido.get("reversivel") is False, "o pedido na fila diz que não dá para desfazer", pedido.get("reversivel"))

    shutil.rmtree(TMP, ignore_errors=True)
    shutil.rmtree(fora_do_appdata, ignore_errors=True)
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
