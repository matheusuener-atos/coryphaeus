"""
Pensar no aparelho, D2: o motor que escreve no navegador (docs/PROGRESSO-APARELHO.md).

- **A biblioteca** é a wllama (llama.cpp em WebAssembly, com WebGPU), versão
  fixa, servida pelo próprio PAULUS a partir de frontend/vendor/ - nunca de
  CDN. `MOTOR` guarda o SHA-256 de cada arquivo; o servidor recusa arquivo
  que não bate, e o teste confere.
- **Os pesos** saem do Ollama deste escritório: o nome do blob do Ollama é o
  SHA-256 do conteúdo (sha256-<hex>). O servidor confere o hash antes de
  entregar (uma vez por arquivo, guardado em memória) e o aparelho confere de
  novo antes de usar (frontend/motor/trabalhador.js). Hash diferente: recusa.
  Servir daqui, e não de uma origem pública, mantém a página sem origem nova
  na CSP (connect-src 'self').
- **As partes** (D2b): a wllama não lê arquivo acima de ~2 GB, e o 3B tem
  2,02 GB. O modelo é dividido uma vez, neste computador, pelo gguf-split do
  llama.cpp (versão fixa em src/bin/, hashes em `PARTIDOR`), em partes de
  512 MB guardadas em <dados>/aparelho/partes/<sha256 do modelo>/ com o hash
  de cada uma; o aparelho baixa e confere parte por parte.
- **A capacidade**: o aparelho manda só números (WebGPU sim/não, memória,
  tokens por segundo num texto de exemplo). Guardado por conta, para o
  Automático da D4.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

RAIZ = Path(__file__).resolve().parents[1]
VENDOR = RAIZ / "frontend" / "vendor"
MOTOR_DIR = RAIZ / "frontend" / "motor"
MODELO_PADRAO = "llama3.2:3b"
TAMANHO_DA_PARTE = "512M"

# O gguf-split do llama.cpp (b11292, MIT; o libomp é do LLVM, Apache-2.0 com
# a exceção do LLVM): so os arquivos que ele precisa para rodar, com o hash.
PARTIDOR = {
    "versao": "b11292",
    "pasta": RAIZ / "src" / "bin" / "llama-cpp-b11292",
    "exe": "llama-gguf-split.exe",
    "arquivos": {
        "llama-gguf-split.exe": "9ed0d640a567d069396ea6b7aa9f0ce00f92cdfd3dc5afdc84d59d5a657ec85d",
        "ggml-base.dll": "ccdb765182eea769f15d9fa70c3a1e3e63815353ec59331b80cee49b2466ee98",
        "ggml.dll": "50a3668baed68114b67bb4d4ea43849fd747380baf67b67a0b2aab7d893003ac",
        "llama.dll": "22e349cb0f58db6b5c3898b54004ceee98673c95dfbcb64babcc8304a01e97f9",
        "llama-common.dll": "8dacb5279aea9fafbcbf12e35a79682c0fdde09b74582e5b2090cd6b7f9efd27",
        "libomp.dll": "a12116ba72d1d6820407cf30be23da04ce79d6bb8a71a5ee71759c5a1faa6f1c",
    },
}

# A wllama servida por aqui: versão fixa e o SHA-256 de cada arquivo. Trocar
# de versão é trocar a pasta e estes hashes, com o teste (tests/test_d2_motor.py).
MOTOR = {
    "versao": "3.6.1",
    "pasta": "wllama-3.6.1",
    "licenca": "MIT",
    "arquivos": {
        "index.js": ("ee4b31125271a8d525db06d59724ebdb79c3bda5396eb9e3245f64fd531faf6b", "text/javascript"),
        "wllama.wasm": ("6ca9fdd1b6c03206cd3a04e359b52c8f539896d6c5fb5d36243dded4a689f0ad", "application/wasm"),
    },
}
TRABALHADOR = "trabalhador.js"

_conferidos: dict[str, tuple[float, int, str]] = {}
_trava = threading.Lock()


def sha256_do_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def conferido(caminho: Path) -> str:
    """O SHA-256 do arquivo, calculado uma vez por (data, tamanho)."""
    st = caminho.stat()
    chave = str(caminho)
    with _trava:
        visto = _conferidos.get(chave)
        if visto and visto[0] == st.st_mtime and visto[1] == st.st_size:
            return visto[2]
    h = sha256_do_arquivo(caminho)
    with _trava:
        _conferidos[chave] = (st.st_mtime, st.st_size, h)
    return h


# ------------------------------------------------------------ os pesos

def pasta_do_ollama() -> Path:
    return Path(os.environ.get("OLLAMA_MODELS") or (Path.home() / ".ollama" / "models"))


def manifesto(nome: str, pasta: Path | None = None) -> Path:
    """manifests/<registro>/<espaço>/<modelo>/<etiqueta>, como o Ollama guarda."""
    base, _, etiqueta = nome.partition(":")
    partes = base.split("/")
    if len(partes) == 1:
        partes = ["registry.ollama.ai", "library", partes[0]]
    elif len(partes) == 2:
        partes = ["registry.ollama.ai"] + partes
    return (pasta or pasta_do_ollama()) / "manifests" / Path(*partes) / (etiqueta or "latest")


def modelo_do_aparelho(nome: str, pasta: Path | None = None) -> dict:
    """{"nome", "sha256", "bytes", "arquivo"} do GGUF do modelo, ou {"erro"}."""
    pasta = pasta or pasta_do_ollama()
    try:
        dados = json.loads(manifesto(nome, pasta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"nome": nome, "erro": f"o modelo {nome} não está baixado neste computador"}
    camada = next((c for c in dados.get("layers") or [] if c.get("mediaType") == "application/vnd.ollama.image.model"), None)
    if not camada or not str(camada.get("digest", "")).startswith("sha256:"):
        return {"nome": nome, "erro": "o manifesto do modelo não diz qual é o arquivo"}
    sha = camada["digest"].split(":", 1)[1]
    arquivo = pasta / "blobs" / f"sha256-{sha}"
    if not arquivo.exists():
        return {"nome": nome, "erro": "o arquivo do modelo sumiu da pasta do Ollama"}
    return {"nome": nome, "sha256": sha, "bytes": arquivo.stat().st_size, "arquivo": arquivo}


# ------------------------------------------------------------ as partes

_trava_partes = threading.Lock()


def partidor_pronto() -> tuple[bool, str]:
    """O gguf-split está aqui, inteiro? (pronto, motivo)."""
    pasta = PARTIDOR["pasta"]
    for nome, sha in PARTIDOR["arquivos"].items():
        arq = pasta / nome
        if not arq.exists():
            return False, "o divisor do modelo não veio com o programa"
        if conferido(arq) != sha:
            return False, f"o divisor do modelo ({nome}) não confere com a versão fixa"
    return True, ""


def dividir(arquivo: Path, destino: Path) -> list[Path]:
    """Divide o GGUF em partes (modelo-0000N-of-0000M.gguf) com o gguf-split. Levanta RuntimeError."""
    import subprocess

    pronto, motivo = partidor_pronto()
    if not pronto:
        raise RuntimeError(motivo)
    destino.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(PARTIDOR["pasta"] / PARTIDOR["exe"]), "--split", "--split-max-size", TAMANHO_DA_PARTE,
                        str(arquivo), str(destino / "modelo")], capture_output=True, text=True, timeout=1800,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    partes = sorted(destino.glob("modelo-*-of-*.gguf"))
    if r.returncode != 0 or not partes:
        raise RuntimeError("não consegui dividir o modelo: " + (r.stderr or r.stdout or "")[-300:])
    return partes


def partes_do_modelo(m: dict, dados_dir: Path) -> dict:
    """
    As partes do modelo `m` (de `modelo_do_aparelho`), divididas uma vez e
    guardadas com o hash de cada uma: {"partes": [{"nome", "sha256", "bytes"}]}
    ou {"erro"}. O modelo inteiro é conferido antes de dividir.
    """
    pasta = Path(dados_dir) / "aparelho" / "partes" / m["sha256"]
    indice = pasta / "partes.json"
    with _trava_partes:
        try:
            feito = json.loads(indice.read_text(encoding="utf-8"))
            if all((pasta / x["nome"]).exists() and (pasta / x["nome"]).stat().st_size == x["bytes"] for x in feito["partes"]):
                return feito
        except (OSError, ValueError, KeyError):
            pass
        if conferido(m["arquivo"]) != m["sha256"]:
            return {"erro": "o arquivo do modelo não confere com o hash"}
        provisoria = pasta.with_name(pasta.name + ".dividindo")
        shutil.rmtree(provisoria, ignore_errors=True)
        try:
            partes = dividir(m["arquivo"], provisoria)
        except RuntimeError as exc:
            shutil.rmtree(provisoria, ignore_errors=True)
            return {"erro": str(exc)}
        feito = {"origem": m["sha256"], "partidor": PARTIDOR["versao"],
                 "partes": [{"nome": x.name, "sha256": sha256_do_arquivo(x), "bytes": x.stat().st_size} for x in partes]}
        shutil.rmtree(pasta, ignore_errors=True)
        provisoria.rename(pasta)
        indice.write_text(json.dumps(feito, ensure_ascii=False, indent=1), encoding="utf-8")
        return feito


# ---------------------------------------------------------- a capacidade

class Capacidade(BaseModel):
    """Só números: nada do escritório, nada que identifique o aparelho."""

    model_config = ConfigDict(extra="forbid")
    webgpu: bool = False
    memoria_gb: float | None = None
    tokens_por_segundo: float | None = None
    # D4: a velocidade de ler a pergunta (tokens por segundo), para o Automático.
    leitura_tps: float | None = None
    carregou_s: float | None = None


def _capacidades(dados_dir: Path) -> Path:
    return Path(dados_dir) / "aparelho" / "capacidade.json"


def capacidade_de(dados_dir: Path, conta_id) -> dict | None:
    try:
        return json.loads(_capacidades(dados_dir).read_text(encoding="utf-8")).get(str(conta_id))
    except (OSError, ValueError):
        return None


def montar(estado, app, dados_dir: Path) -> None:
    import aparelho as aparelho_mod

    def _pode_baixar(request) -> None:
        from acesso import rotas as rotas_do_acesso

        if rotas_do_acesso.e_local(request):
            return
        pode, motivo = aparelho_mod.pode_escrever(estado, request)
        if not pode:
            raise HTTPException(status_code=403, detail=motivo)

    def _nome_do_modelo() -> str:
        return str((estado.prefs.dados.get("aparelho") or {}).get("modelo") or MODELO_PADRAO)

    @app.get("/motor/" + MOTOR["pasta"] + "/{arquivo}")
    def motor_arquivo(arquivo: str) -> FileResponse:
        """Só os arquivos da lista, e só se o hash bate: um arquivo trocado no disco não chega à página."""
        item = MOTOR["arquivos"].get(arquivo)
        alvo = VENDOR / MOTOR["pasta"] / arquivo
        if not item or not alvo.exists():
            raise HTTPException(status_code=404, detail="arquivo do motor não encontrado")
        if conferido(alvo) != item[0]:
            raise HTTPException(status_code=409, detail="o arquivo do motor não confere com a versão fixa")
        return FileResponse(alvo, media_type=item[1], headers={"Cache-Control": "private, max-age=31536000, immutable"})

    @app.get("/motor/" + TRABALHADOR)
    def motor_trabalhador() -> FileResponse:
        return FileResponse(MOTOR_DIR / TRABALHADOR, media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @app.get("/api/aparelho/modelo")
    def aparelho_modelo(request: Request = None) -> dict:
        """O modelo do aparelho, em partes (a primeira vez divide: alguns segundos)."""
        _pode_baixar(request)
        m = modelo_do_aparelho(_nome_do_modelo())
        if m.get("erro"):
            return {"disponivel": False, "nome": m["nome"], "motivo": m["erro"], "motor": MOTOR["versao"]}
        d = partes_do_modelo(m, dados_dir)
        if d.get("erro"):
            return {"disponivel": False, "nome": m["nome"], "motivo": d["erro"], "motor": MOTOR["versao"]}
        return {"disponivel": True, "nome": m["nome"], "sha256": m["sha256"], "bytes": m["bytes"], "motor": MOTOR["versao"],
                "partes": [{"url": f"/api/aparelho/modelo/{m['sha256']}/parte/{i}", "sha256": x["sha256"], "bytes": x["bytes"]}
                           for i, x in enumerate(d["partes"], 1)]}

    @app.get("/api/aparelho/modelo/{sha}/parte/{n}")
    def aparelho_modelo_parte(sha: str, n: int, request: Request = None) -> FileResponse:
        _pode_baixar(request)
        m = modelo_do_aparelho(_nome_do_modelo())
        if m.get("erro") or m.get("sha256") != sha:
            raise HTTPException(status_code=404, detail="esse modelo não é o do aparelho")
        d = partes_do_modelo(m, dados_dir)
        if d.get("erro") or not 1 <= n <= len(d["partes"]):
            raise HTTPException(status_code=404, detail="essa parte do modelo não existe")
        parte = d["partes"][n - 1]
        arq = Path(dados_dir) / "aparelho" / "partes" / sha / parte["nome"]
        # A parte guardada tem de dizer o hash anotado quando foi dividida.
        if conferido(arq) != parte["sha256"]:
            raise HTTPException(status_code=409, detail="uma parte do modelo não confere com o hash")
        return FileResponse(arq, media_type="application/octet-stream",
                            headers={"Cache-Control": "private, max-age=31536000, immutable"})

    @app.post("/api/aparelho/capacidade")
    def aparelho_capacidade(payload: Capacidade, request: Request = None) -> dict:
        from acesso import rotas as rotas_do_acesso

        pessoa = rotas_do_acesso.pessoa(request) or {}
        chave = str(pessoa.get("conta_id") or "local")
        arq = _capacidades(dados_dir)
        with _trava:
            try:
                todas = json.loads(arq.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                todas = {}
            todas[chave] = payload.model_dump()
            arq.parent.mkdir(parents=True, exist_ok=True)
            arq.write_text(json.dumps(todas, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"guardado": True, "capacidade": todas[chave]}
