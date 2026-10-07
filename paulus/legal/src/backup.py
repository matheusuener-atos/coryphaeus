"""
Backup e restauracao do PAULUS (docs/PLANO-PRODUTO.md, P1).

Tudo do escritorio mora num computador so: um disco perdido e o escritorio
perdido. O backup e um arquivo so, `PAULUS-backup-<data>.paulusbak`, numa
pasta que o escritorio escolhe (HD externo, pasta de rede, pasta sincronizada
pelo Google Drive para computador), cifrado com uma senha que so o escritorio
sabe: quem achar o arquivo nao le nada sem ela.

O que entra: tudo da pasta de dados (banco, preferencias, contas de acesso,
o Acervo do PAULUS, gravacoes, conversas, conhecimento, marca), menos o que e
desta maquina ou se refaz sozinho (a sessao do navegador embutido, indices,
logs, anuncio de atualizacao). As pastas do computador que o Acervo so vigia
continuam onde estao: sao do escritorio, e o backup delas e o do Windows.

O formato: `PAULUSBK1` + sal + nonce base, e o .zip cifrado em blocos de
4 MiB com AES-GCM (a chave sai da senha pelo scrypt). Cada bloco leva o
numero dele e, o ultimo, a marca de fim no dado autenticado: bloco trocado,
repetido ou arquivo cortado nao passa.

Restaurar nao sobrescreve nada com o programa aberto: o conteudo vai para uma
pasta ao lado (`dados.restaurar`), e a troca acontece quando o PAULUS abre de
novo (desktop.py) - os dados de antes ficam em `dados.antes-<data>`.

O que e protegido pela protecao de dados do Windows (tokens do e-mail, o
segredo do tunel) so abre no mesmo usuario do mesmo computador: restaurado
em outro, pede entrar de novo nessas contas.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import struct
import tempfile
import time
import zipfile
from pathlib import Path

MAGICO = b"PAULUSBK1\n"
EXTENSAO = ".paulusbak"
BLOCO = 4 * 1024 * 1024
SENHA_MINIMA = 10
# O que e desta maquina ou se refaz: fica fora do backup.
FORA = {"sessoes", "logs", "indice", "atualizacao", "instancia.json", "maquina.json", "extractions",
        "modelos", "__pycache__"}
SUFIXOS_FORA = ("-wal", "-shm", ".tmp", ".parcial")


class ErroBackup(RuntimeError):
    """O que impede o backup ou a restauracao; a frase vai para a tela."""


# ------------------------------------------------------------ a cifra

def _chave(senha: str, sal: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    return Scrypt(salt=sal, length=32, n=2 ** 15, r=8, p=1).derive(senha.encode("utf-8"))


def _aad(cabecalho: bytes, numero: int, ultimo: bool) -> bytes:
    return cabecalho + struct.pack(">I", numero) + (b"F" if ultimo else b"-")


def cifrar_arquivo(origem: Path, destino: Path, senha: str) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    sal, base = os.urandom(16), os.urandom(8)
    cabecalho = MAGICO + sal + base
    aes = AESGCM(_chave(senha, sal))
    tamanho = origem.stat().st_size
    with open(origem, "rb") as ent, open(destino, "wb") as sai:
        sai.write(cabecalho)
        numero, lidos = 0, 0
        while True:
            pedaco = ent.read(BLOCO)
            lidos += len(pedaco)
            ultimo = lidos >= tamanho
            cifrado = aes.encrypt(base + struct.pack(">I", numero), pedaco, _aad(cabecalho, numero, ultimo))
            sai.write(struct.pack(">I", len(cifrado)) + cifrado)
            numero += 1
            if ultimo:
                break


def decifrar_arquivo(origem: Path, destino: Path, senha: str) -> None:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    with open(origem, "rb") as ent, open(destino, "wb") as sai:
        magico = ent.read(len(MAGICO))
        if magico != MAGICO:
            raise ErroBackup("este arquivo não é um backup do Paulus")
        sal, base = ent.read(16), ent.read(8)
        cabecalho = MAGICO + sal + base
        aes = AESGCM(_chave(senha, sal))
        numero, fim = 0, False
        while not fim:
            tam = ent.read(4)
            if len(tam) < 4:
                raise ErroBackup("o arquivo do backup está incompleto (cortado)")
            cifrado = ent.read(struct.unpack(">I", tam)[0])
            nonce = base + struct.pack(">I", numero)
            for ultimo in (False, True):
                try:
                    sai.write(aes.decrypt(nonce, cifrado, _aad(cabecalho, numero, ultimo)))
                    fim = ultimo
                    break
                except InvalidTag:
                    continue
            else:
                raise ErroBackup("senha errada, ou o arquivo do backup foi alterado")
            numero += 1
        if ent.read(1):
            raise ErroBackup("o arquivo do backup tem sobra depois do fim")


# ------------------------------------------------------------ fazer

def _entra(relativo: Path) -> bool:
    partes = relativo.parts
    if not partes or partes[0] in FORA or partes[0].startswith("dados."):
        return False
    return not relativo.name.endswith(SUFIXOS_FORA)


def _copiar_banco(origem: Path, destino: Path) -> None:
    """Copia de um SQLite aberto sem pegar a escrita pela metade (a API de backup do SQLite)."""
    fonte = sqlite3.connect(f"file:{origem}?mode=ro", uri=True)
    alvo = sqlite3.connect(destino)
    try:
        fonte.backup(alvo)
    finally:
        alvo.close()
        fonte.close()


def fazer(dados: Path, pasta: Path, senha: str, *, versao: str = "", manter: int = 10, andamento=None) -> dict:
    """Faz o backup de `dados` em `pasta`. Devolve {arquivo, bytes, arquivos}."""
    if len(senha or "") < SENHA_MINIMA:
        raise ErroBackup(f"a senha do backup precisa de pelo menos {SENHA_MINIMA} caracteres")
    pasta = Path(pasta)
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ErroBackup(f"não consegui usar a pasta do backup ({exc.strerror or exc})") from exc
    dados = Path(dados).resolve()
    if pasta.resolve() == dados or dados in pasta.resolve().parents:
        raise ErroBackup("a pasta do backup não pode ficar dentro da pasta de dados do Paulus")
    arquivos = [p for p in dados.rglob("*") if p.is_file() and _entra(p.relative_to(dados))]
    agora = time.strftime("%Y%m%d-%H%M%S")
    nome = f"PAULUS-backup-{agora}{EXTENSAO}"
    with tempfile.TemporaryDirectory(prefix="paulus-backup-") as tmp:
        zip_tmp = Path(tmp) / "backup.zip"
        total = 0
        with zipfile.ZipFile(zip_tmp, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for i, p in enumerate(arquivos):
                rel = p.relative_to(dados).as_posix()
                try:
                    if p.suffix == ".db":
                        copia = Path(tmp) / "banco.db"
                        copia.unlink(missing_ok=True)
                        _copiar_banco(p, copia)
                        z.write(copia, rel)
                        total += copia.stat().st_size
                    else:
                        z.write(p, rel)
                        total += p.stat().st_size
                except (OSError, sqlite3.Error):
                    continue  # arquivo aberto por outro programa: entra no proximo
                if andamento:
                    andamento(i + 1, len(arquivos))
            z.writestr("manifesto.json", json.dumps({
                "paulus": versao, "criado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "computador": os.environ.get("COMPUTERNAME", ""), "arquivos": len(arquivos), "bytes": total,
            }, ensure_ascii=False))
        parcial = pasta / (nome + ".parcial")
        cifrar_arquivo(zip_tmp, parcial, senha)
        final = pasta / nome
        os.replace(parcial, final)
    for velho in listar(pasta)[manter:]:
        try:
            Path(velho["caminho"]).unlink()
        except OSError:
            pass
    return {"arquivo": str(final), "bytes": final.stat().st_size, "arquivos": len(arquivos)}


def listar(pasta: Path) -> list[dict]:
    """Os backups da pasta, do mais novo para o mais velho."""
    try:
        achados = [p for p in Path(pasta).glob("PAULUS-backup-*" + EXTENSAO) if p.is_file()]
    except OSError:
        return []
    achados.sort(key=lambda p: p.name, reverse=True)
    return [{"caminho": str(p), "nome": p.name, "bytes": p.stat().st_size,
             "quando": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(p.stat().st_mtime))} for p in achados]


# ------------------------------------------------------------ restaurar

def pasta_de_restaurar(dados: Path) -> Path:
    dados = Path(dados).resolve()
    return dados.parent / (dados.name + ".restaurar")


def preparar_restauracao(arquivo: Path, senha: str, dados: Path) -> dict:
    """
    Decifra e confere o backup e deixa o conteudo em `dados.restaurar`: a troca
    so acontece quando o PAULUS abre de novo (aplicar_restauracao_pendente).
    """
    arquivo = Path(arquivo)
    if not arquivo.is_file():
        raise ErroBackup("arquivo de backup não encontrado")
    alvo = pasta_de_restaurar(dados)
    with tempfile.TemporaryDirectory(prefix="paulus-restaurar-") as tmp:
        zip_tmp = Path(tmp) / "backup.zip"
        decifrar_arquivo(arquivo, zip_tmp, senha)
        try:
            with zipfile.ZipFile(zip_tmp) as z:
                manifesto = json.loads(z.read("manifesto.json").decode("utf-8"))
                if alvo.exists():
                    shutil.rmtree(alvo)
                alvo.mkdir(parents=True)
                base = alvo.resolve()
                for info in z.infolist():
                    destino = (alvo / info.filename).resolve()
                    if base not in destino.parents or info.filename == "manifesto.json":
                        continue  # nada de sair da pasta
                    if info.is_dir():
                        destino.mkdir(parents=True, exist_ok=True)
                        continue
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(info) as ent, open(destino, "wb") as sai:
                        shutil.copyfileobj(ent, sai)
        except (zipfile.BadZipFile, KeyError, ValueError) as exc:
            shutil.rmtree(alvo, ignore_errors=True)
            raise ErroBackup("o backup está danificado") from exc
    (alvo / ".restaurar-pronto").write_text(json.dumps(manifesto, ensure_ascii=False), encoding="utf-8")
    return manifesto


def aplicar_restauracao_pendente(dados: Path) -> str:
    """
    Ao abrir, antes de qualquer coisa ler a pasta de dados: se ha restauracao
    pronta, os dados de agora vao para `dados.antes-<data>` e os restaurados
    entram no lugar. Devolve a pasta de antes ("" quando nao havia nada).
    """
    dados = Path(dados).resolve()
    alvo = pasta_de_restaurar(dados)
    if not (alvo / ".restaurar-pronto").is_file():
        return ""
    antes = dados.parent / f"{dados.name}.antes-{time.strftime('%Y%m%d-%H%M%S')}"
    if dados.exists():
        os.replace(dados, antes)
    os.replace(alvo, dados)
    try:
        (dados / ".restaurar-pronto").unlink()
    except OSError:
        pass
    return str(antes)
