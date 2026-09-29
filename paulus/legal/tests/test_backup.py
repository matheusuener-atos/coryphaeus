"""
Backup e restauracao (src/backup.py, docs/PLANO-PRODUTO.md P1).

  - fazer e restaurar devolve os mesmos dados (banco aberto incluido);
  - o que e desta maquina (sessao do navegador, indices, logs) fica fora;
  - senha errada, arquivo cortado, bloco alterado ou arquivo que nao e backup:
    recusados, sem restaurar nada;
  - a restauracao so troca a pasta ao abrir: os dados de antes ficam guardados;
  - manter so os N mais novos;
  - pela API: a senha fica protegida (nao em texto), o backup roda em segundo
    plano, restaurar deixa pronto; de fora, as rotas nao existem.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_backup.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-backup-teste-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []
SENHA = "senha-do-backup-123"


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _dados_de_exemplo(raiz: Path) -> None:
    (raiz / "test_contracts" / "Cliente A").mkdir(parents=True)
    (raiz / "test_contracts" / "Cliente A" / "contrato.txt").write_text("Contrato do cliente A.", encoding="utf-8")
    (raiz / "gravacoes").mkdir()
    (raiz / "gravacoes" / "audio.webm").write_bytes(os.urandom(300_000))
    (raiz / "preferencias.json").write_text(json.dumps({"pessoa": {"nome": "Dona"}}), encoding="utf-8")
    (raiz / "sessoes").mkdir()
    (raiz / "sessoes" / "Cookies").write_text("de outra maquina", encoding="utf-8")
    (raiz / "indice").mkdir()
    (raiz / "indice" / "lexico.db").write_text("refaz sozinho", encoding="utf-8")
    (raiz / "logs").mkdir()
    (raiz / "logs" / "tunel.log").write_text("log", encoding="utf-8")
    banco = sqlite3.connect(raiz / "paulus.db")
    banco.execute("PRAGMA journal_mode=WAL")
    banco.execute("CREATE TABLE t (x TEXT)")
    banco.execute("INSERT INTO t VALUES ('antes do backup')")
    banco.commit()
    return banco


def test_modulo() -> None:
    print("\no modulo")
    import backup

    dados = TMP / "escritorio" / "dados"
    dados.mkdir(parents=True)
    banco = _dados_de_exemplo(dados)  # fica aberto, como o PAULUS aberto
    pasta = TMP / "hd-externo"
    r = None
    try:
        backup.fazer(dados, pasta, "curta")
    except backup.ErroBackup as exc:
        r = str(exc)
    checar(r and "caracteres" in r, "senha curta: recusada", r)
    try:
        backup.fazer(dados, dados / "backups", SENHA)
        dentro = False
    except backup.ErroBackup:
        dentro = True
    checar(dentro, "a pasta do backup nao pode ficar dentro dos dados")

    feito = backup.fazer(dados, pasta, SENHA, versao="0.0.0")
    arq = Path(feito["arquivo"])
    checar(arq.is_file() and arq.suffix == ".paulusbak", "o backup e um arquivo so", feito)
    bruto = arq.read_bytes()
    checar(b"Contrato do cliente A" not in bruto and b"antes do backup" not in bruto, "cifrado: nada legivel no arquivo")

    print("  restaurar")
    manifesto = backup.preparar_restauracao(arq, SENHA, dados)
    alvo = backup.pasta_de_restaurar(dados)
    checar(manifesto.get("paulus") == "0.0.0" and (alvo / ".restaurar-pronto").is_file(), "a restauracao fica pronta ao lado", manifesto)
    checar((alvo / "test_contracts" / "Cliente A" / "contrato.txt").read_text(encoding="utf-8") == "Contrato do cliente A.",
           "os documentos voltam")
    checar((alvo / "gravacoes" / "audio.webm").read_bytes() == (dados / "gravacoes" / "audio.webm").read_bytes(),
           "as gravacoes voltam iguais, byte a byte")
    copia = sqlite3.connect(alvo / "paulus.db")
    checar(copia.execute("SELECT x FROM t").fetchone() == ("antes do backup",), "o banco aberto volta consistente")
    copia.close()
    checar(not (alvo / "sessoes").exists() and not (alvo / "indice").exists() and not (alvo / "logs").exists(),
           "o que e desta maquina fica fora")
    checar((dados / "paulus.db").exists(), "e nada foi trocado ainda (o programa esta aberto)")
    banco.close()
    antes = backup.aplicar_restauracao_pendente(dados)
    checar(antes and Path(antes).is_dir() and (Path(antes) / "sessoes" / "Cookies").exists(),
           "ao abrir: os dados de antes ficam guardados", antes)
    checar((dados / "test_contracts").is_dir() and not alvo.exists(), "e os restaurados entram no lugar")
    checar(backup.aplicar_restauracao_pendente(dados) == "", "sem restauracao pronta, nada acontece")

    print("  o que nao passa")
    ruins = {}
    try:
        backup.preparar_restauracao(arq, "senha-errada-123", dados)
    except backup.ErroBackup as exc:
        ruins["senha"] = str(exc)
    cortado = pasta / "cortado.paulusbak"
    cortado.write_bytes(bruto[: len(bruto) // 2])
    try:
        backup.preparar_restauracao(cortado, SENHA, dados)
    except backup.ErroBackup as exc:
        ruins["cortado"] = str(exc)
    alterado = pasta / "alterado.paulusbak"
    b = bytearray(bruto)
    b[len(b) // 2] ^= 0xFF
    alterado.write_bytes(bytes(b))
    try:
        backup.preparar_restauracao(alterado, SENHA, dados)
    except backup.ErroBackup as exc:
        ruins["alterado"] = str(exc)
    outro = pasta / "outro.paulusbak"
    outro.write_bytes(b"nao sou backup")
    try:
        backup.preparar_restauracao(outro, SENHA, dados)
    except backup.ErroBackup as exc:
        ruins["outro"] = str(exc)
    checar("senha errada" in ruins.get("senha", ""), "senha errada: recusada", ruins.get("senha"))
    checar(ruins.get("cortado"), "arquivo cortado: recusado", ruins.get("cortado"))
    checar(ruins.get("alterado"), "arquivo alterado: recusado", ruins.get("alterado"))
    checar("não é um backup" in ruins.get("outro", ""), "arquivo que nao e backup: recusado", ruins.get("outro"))
    checar(not backup.pasta_de_restaurar(dados).exists(), "e nada ficou pronto para restaurar")

    print("  manter os mais novos")
    for f in (cortado, alterado, outro):
        f.unlink()
    for i in range(3):
        time.sleep(1.1)
        backup.fazer(dados, pasta, SENHA, manter=2)
    checar(len(backup.listar(pasta)) == 2, "so os dois mais novos ficam", [x["nome"] for x in backup.listar(pasta)])


def test_api() -> None:
    print("\npela API")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows)")
        return
    from fastapi.testclient import TestClient

    import api

    local = TestClient(api.app, headers=api.cabecalho_local())
    pasta = TMP / "pasta-do-backup"
    r = local.post("/api/backup/agora")
    checar(r.status_code == 400, "sem pasta nem senha: pede antes")
    r = local.post("/api/backup/configurar", json={"pasta": str(api.DADOS_DIR / "sub")})
    checar(r.status_code == 400, "pasta dentro dos dados: recusada")
    r = local.post("/api/backup/configurar", json={"pasta": str(pasta), "senha": SENHA})
    checar(r.status_code == 200 and r.json()["tem_senha"], "pasta e senha guardadas", r.text[:160])
    guardada = api.estado.prefs.dados["backup"]["senha"]
    checar(guardada and SENHA not in guardada, "a senha fica protegida, nao em texto")
    r = local.post("/api/backup/agora")
    checar(r.status_code == 200, "o backup comeca em segundo plano", r.text[:160])
    for _ in range(120):
        e = local.get("/api/backup").json()
        if not e["andamento"]["fazendo"]:
            break
        time.sleep(0.25)
    checar(e["ultimo"] and e["backups"] and not e["ultimo_erro"], "e termina, com o arquivo na lista", e)
    r = local.post("/api/backup/restaurar", json={"arquivo": e["backups"][0]["caminho"], "senha": "outra-senha-123"})
    checar(r.status_code == 400 and "senha" in r.json().get("detail", ""), "restaurar com a senha errada: nao", r.text[:160])
    r = local.post("/api/backup/restaurar", json={"arquivo": e["backups"][0]["caminho"], "senha": SENHA})
    checar(r.status_code == 200 and r.json()["restauracao_pronta"], "restaurar deixa pronto para a proxima abertura", r.text[:160])
    r = local.post("/api/backup/restaurar/cancelar")
    checar(not r.json()["restauracao_pronta"], "e da para desistir")
    r = local.post("/api/backup/listar", json={"pasta": str(pasta)})
    checar(r.status_code == 200 and r.json()["backups"], "listar os backups de uma pasta (computador novo)")
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    try:
        fora = TestClient(api.app, base_url="https://x.paulus.ia.br")
        checar(fora.get("/api/backup").status_code in (401, 403) and fora.post("/api/backup/agora").status_code in (401, 403),
               "de fora: nao existe")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False


def main() -> int:
    test_modulo()
    test_api()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
