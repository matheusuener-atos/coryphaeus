"""
Publica uma versao nova do PAULUS, do instalador ao site, num comando so.

    venv/Scripts/python.exe tools/publicar.py            # tudo, na proxima versao (0.9.3 -> 0.9.4)
    venv/Scripts/python.exe tools/publicar.py preparar   # passos 1 a 4 (uns 5 min)
    venv/Scripts/python.exe tools/publicar.py enviar     # passos 5 e 6, com o que o preparar provou
    venv/Scripts/python.exe tools/publicar.py --versao 1.0.0 --novidade "texto" --novidade "outro"

Em duas etapas cada comando fica abaixo dos 10 minutos que um agente pode
esperar por um comando (o agente "publicar", em .claude/agents na raiz).

O que faz, e para no primeiro erro:
 1. confere que nao ha mudanca sem commit (so .claude/ e versao.py podem estar sujos);
 2. escolhe a versao e as novidades (os assuntos dos commits desde a ultima
    release, tirando os do site e os de versao);
 3. sobe src/versao.py e monta o instalador (construir.py);
 4. instala calado numa pasta temporaria, com PAULUS_CASA temporaria,
    confere a versao e desinstala - e confere que a instalacao de verdade
    desta maquina nao foi tocada;
 5. commit "Versao X.Y.Z", push, release no GitHub, baixa o arquivo
    publicado e confere o SHA-256;
 6. troca link, versao, tamanho e hash no site/index.html, escreve o
    site/atualizacao.json, commit, push, e espera o site responder a versao nova.

Imprime pouco: uma linha por passo e o resumo. Num erro, as ultimas linhas
da saida do comando que falhou.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parent.parent          # paulus/legal
REPO = APP.parent.parent                               # coryphaeus
VERSAO_PY = APP / "src" / "versao.py"
CONSTRUCAO = APP / "tools" / "instalador" / "_construcao"
SITE = REPO / "site"
REPOSITORIO = "matheusuener-atos/coryphaeus"
ANUNCIO = "https://paulus.ia.br/atualizacao.json"
ASSINATURA = "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
INSTALADO = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "PAULUS"


class Falha(Exception):
    pass


def passo(texto: str) -> None:
    print("-", texto, flush=True)


def rodar(cmd: list[str], cwd: Path = REPO, env: dict | None = None, tempo: int = 1800) -> str:
    r = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, encoding="utf-8", errors="replace",
                       capture_output=True, timeout=tempo)
    if r.returncode != 0:
        saida = (r.stdout + "\n" + r.stderr).strip().splitlines()
        raise Falha(f"{' '.join(cmd[:3])} saiu com {r.returncode}:\n" + "\n".join(saida[-25:]))
    return r.stdout


def numeros(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def versao_atual() -> str:
    return re.search(r'^VERSAO = "([\d.]+)"', VERSAO_PY.read_text(encoding="utf-8"), re.M).group(1)


def sha256_de(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def conferir_arvore() -> None:
    sujos = []
    for linha in rodar(["git", "status", "--porcelain"]).splitlines():
        caminho = linha[3:].strip().strip('"')
        if caminho.startswith(".claude") or caminho == "paulus/legal/src/versao.py":
            continue
        sujos.append(caminho)
    if sujos:
        raise Falha("há mudança sem commit (faça o commit antes de publicar): " + ", ".join(sujos[:8]))


def ultima_release() -> str:
    dados = json.loads(rodar(["gh", "release", "list", "-R", REPOSITORIO, "--limit", "1", "--json", "tagName"]))
    if not dados:
        raise Falha("nenhuma release no GitHub para comparar")
    return dados[0]["tagName"].lstrip("v")


def novidades_desde(tag: str) -> list[str]:
    rodar(["git", "fetch", "--tags", "--quiet", "origin"])
    # So o que muda o programa de quem usa: commit que so mexe em tools,
    # docs, testes ou no site nao e novidade para ninguem.
    programa = ("paulus/legal/src/", "paulus/legal/frontend/")
    novidades = []
    for linha in rodar(["git", "log", f"v{tag}..HEAD", "--format=%H%x09%s"]).splitlines():
        sha, _, assunto = linha.partition("\t")
        if not assunto.strip() or assunto.startswith(("Site:", "Versão ", "Merge ")):
            continue
        arquivos = rodar(["git", "show", "--name-only", "--format=", sha]).split()
        if any(a.startswith(programa) and not a.endswith("versao.py") for a in arquivos):
            novidades.append(assunto.strip())
    return novidades[:12]


def trocar_versao(v: str) -> None:
    texto = VERSAO_PY.read_text(encoding="utf-8")
    VERSAO_PY.write_text(re.sub(r'^VERSAO = "[\d.]+"', f'VERSAO = "{v}"', texto, count=1, flags=re.M), encoding="utf-8")


def marca_da_instalacao_real() -> float | None:
    alvo = INSTALADO / "Desinstalar.exe"
    return alvo.stat().st_mtime if alvo.exists() else None


def esperar(condicao, segundos: int, oque: str) -> None:
    fim = time.time() + segundos
    while time.time() < fim:
        if condicao():
            return
        time.sleep(2)
    raise Falha(f"passou de {segundos} s esperando {oque}")


def provar_instalador(exe: Path, v: str) -> None:
    antes = marca_da_instalacao_real()
    pasta = Path(tempfile.mkdtemp(prefix="paulus_publicar_"))
    prog, casa = pasta / "prog", pasta / "casa"
    env = dict(os.environ, PAULUS_CASA=str(casa))
    try:
        rodar([str(exe), "/silencioso", f"/pasta={prog}", "/sem-ollama", "/sem-atalho", "/sem-iniciar"], env=env, tempo=600)
        esperar(lambda: (prog / "Desinstalar.exe").exists() and (prog / "app" / "src" / "versao.py").exists(), 300,
                "a instalação de teste")
        instalada = re.search(r'VERSAO = "([\d.]+)"', (prog / "app" / "src" / "versao.py").read_text(encoding="utf-8")).group(1)
        if instalada != v:
            raise Falha(f"o instalador de teste instalou {instalada}, não {v}")
        rodar([str(prog / "Desinstalar.exe"), "/desinstalar", "/silencioso", "/apagar-dados"], env=env, tempo=300)
        esperar(lambda: not (prog / "PAULUS.exe").exists(), 180, "a desinstalação de teste")
    finally:
        time.sleep(3)
        shutil.rmtree(pasta, ignore_errors=True)
    if marca_da_instalacao_real() != antes:
        raise Falha(f"a instalação de verdade em {INSTALADO} mudou durante o teste - confira antes de seguir")


def notas_da_release(v: str, novidades: list[str], sha: str) -> str:
    itens = "\n".join(f"- {n}" for n in novidades)
    return (
        f"**Para atualizar:** quem tem o PAULUS 0.9.2 ou mais novo recebe esta versão pelo próprio programa "
        f"(Configurações › Versão). Para instalar do zero, baixe `PAULUS-{v}-instalador.exe` e abra; os dados "
        f"do escritório ficam.\n\n**O que mudou**\n{itens}\n\n"
        "**Aviso do Windows:** o instalador ainda não tem assinatura digital. Na primeira vez, o Windows pode mostrar "
        "\"O Windows protegeu o computador\": clique em **Mais informações** e depois em **Executar assim mesmo**.\n\n"
        f"**Conferir o arquivo (SHA-256):**\n`{sha}`\n\nNo PowerShell: `Get-FileHash .\\PAULUS-{v}-instalador.exe`\n\n"
        "Contato: contato@paulus.ia.br\n"
    )


def baixar_sha(url: str) -> str:
    # Tres tentativas: um download de 100 MB que trava no meio (02/10) nao
    # derruba a publicacao com a release ja criada.
    for tentativa in range(3):
        h = hashlib.sha256()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "PAULUS-publicar"}), timeout=300) as r:
                for bloco in iter(lambda: r.read(1 << 20), b""):
                    h.update(bloco)
            return h.hexdigest()
        except (TimeoutError, OSError):
            if tentativa == 2:
                raise
            time.sleep(10)
    return ""


def atualizar_site(v: str, url: str, sha: str, tamanho: int, novidades: list[str]) -> None:
    index = SITE / "index.html"
    html = index.read_text(encoding="utf-8")
    trocas = [
        (r"releases/download/v[\d.]+/PAULUS-[\d.]+-instalador\.exe", f"releases/download/v{v}/PAULUS-{v}-instalador.exe"),
        (r"versão [\d.]+ · \d+ MB", f"versão {v} · {round(tamanho / 2**20)} MB"),
        (r"releases/tag/v[\d.]+", f"releases/tag/v{v}"),
    ]
    anuncio_path = SITE / "atualizacao.json"
    antigo = json.loads(anuncio_path.read_text(encoding="utf-8")).get("sha256", "") if anuncio_path.exists() else ""
    if antigo:
        trocas.append((antigo, sha))
    for padrao, novo in trocas:
        html, n = re.subn(padrao, novo, html)
        if n == 0:
            raise Falha(f"não achei no site/index.html: {padrao}")
    index.write_text(html, encoding="utf-8")
    anuncio = {
        "versao": v, "url": url, "sha256": sha, "tamanho": tamanho, "publicada": date.today().isoformat(),
        "notas": f"https://github.com/{REPOSITORIO}/releases/tag/v{v}",
        "novidades": [n[:300] for n in novidades],
    }
    anuncio_path.write_text(json.dumps(anuncio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def commit_e_push(arquivos: list[Path], mensagem: str) -> None:
    rodar(["git", "add", *[str(a) for a in arquivos]])
    rodar(["git", "commit", "-q", "-m", mensagem, "-m", ASSINATURA])
    rodar(["git", "push", "-q", "origin", "HEAD:main"])


ESTADO = CONSTRUCAO / "publicar.json"


def preparar(a) -> dict:
    """Versao, instalador e o teste de instalar. Guarda o estado para o enviar."""
    passo("conferindo commits")
    conferir_arvore()
    # Um envio que caiu no meio (02/10: a conferencia do download passou do
    # tempo, com a release ja criada) deixa o estado e o instalador provados.
    # O mesmo instalador, na versao que esta no codigo, e retomado - montar
    # outro daria "nada novo" contra a release que ficou pela metade.
    if ESTADO.exists():
        e = json.loads(ESTADO.read_text(encoding="utf-8"))
        exe = Path(e.get("exe", ""))
        if e.get("versao") == versao_atual() and exe.exists() and sha256_de(exe) == e.get("sha256"):
            passo(f"retomando a {e['versao']} já preparada")
            return e
    anterior = ultima_release()
    atual = versao_atual()
    if a.versao:
        v = a.versao
    elif numeros(atual) > numeros(anterior):
        v = atual
    else:
        n = list(numeros(anterior))
        n[-1] += 1
        v = ".".join(map(str, n))
    if numeros(v) <= numeros(anterior):
        raise Falha(f"a versão {v} não é mais nova que a publicada ({anterior})")
    novidades = a.novidade or novidades_desde(anterior)
    if not novidades and not a.forcar:
        raise Falha(f"nada novo desde a {anterior} (use --forcar para publicar assim mesmo)")
    novidades = novidades or ["Correções e melhorias."]

    passo(f"montando o instalador {v}")
    trocar_versao(v)
    rodar([sys.executable, str(APP / "tools" / "instalador" / "construir.py")], cwd=APP, tempo=3600)
    exe = CONSTRUCAO / f"PAULUS-{v}-instalador.exe"
    if not exe.exists():
        raise Falha(f"o construir.py não gerou {exe.name}")

    passo("instalando e desinstalando numa pasta temporária")
    provar_instalador(exe, v)
    estado = {"versao": v, "exe": str(exe), "sha256": sha256_de(exe), "tamanho": exe.stat().st_size,
              "novidades": novidades}
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    return estado


def enviar() -> dict:
    """Commit da versao, release, site e anuncio - com o instalador que o preparar provou."""
    if not ESTADO.exists():
        raise Falha("rode antes: publicar.py preparar")
    e = json.loads(ESTADO.read_text(encoding="utf-8"))
    v, exe, sha = e["versao"], Path(e["exe"]), e["sha256"]
    if versao_atual() != v or not exe.exists() or sha256_de(exe) != sha:
        raise Falha("o instalador preparado não é mais o mesmo: rode o preparar de novo")

    passo("commit da versão e release no GitHub")
    if rodar(["git", "status", "--porcelain", "--", str(VERSAO_PY)]).strip():
        commit_e_push([VERSAO_PY], f"Versão {v}")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as f:
        f.write(notas_da_release(v, e["novidades"], sha))
    try:
        # Retomada: a release ja criada nao e criada de novo; sem o instalador
        # nela, ele sobe agora.
        existe = subprocess.run(["gh", "release", "view", f"v{v}", "-R", REPOSITORIO, "--json", "assets"],
                                capture_output=True, text=True, encoding="utf-8")
        if existe.returncode == 0:
            nomes = [x.get("name") for x in json.loads(existe.stdout or "{}").get("assets", [])]
            if exe.name not in nomes:
                rodar(["gh", "release", "upload", f"v{v}", str(exe), "-R", REPOSITORIO, "--clobber"], tempo=1800)
        else:
            rodar(["gh", "release", "create", f"v{v}", str(exe), "-R", REPOSITORIO, "--target", "main",
                   "--title", f"PAULUS {v}", "--notes-file", f.name], tempo=1800)
    finally:
        os.unlink(f.name)
    url = f"https://github.com/{REPOSITORIO}/releases/download/v{v}/{exe.name}"
    if baixar_sha(url) != sha:
        raise Falha("o arquivo publicado no GitHub não bate com o SHA-256 do instalador")

    passo("site e anúncio de versão")
    atualizar_site(v, url, sha, e["tamanho"], e["novidades"])
    commit_e_push([SITE / "index.html", SITE / "atualizacao.json"], f"Site: PAULUS {v}")
    ESTADO.unlink(missing_ok=True)

    def no_ar() -> bool:
        try:
            with urllib.request.urlopen(f"{ANUNCIO}?v={v}&t={int(time.time())}", timeout=20) as r:
                return json.loads(r.read().decode("utf-8")).get("versao") == v
        except Exception:  # noqa: BLE001 - o site ainda publicando
            return False

    try:
        esperar(no_ar, 240, "o site")
        e["site"] = "no ar"
    except Falha:
        e["site"] = "enviado, ainda publicando"
    return e


def main() -> int:
    p = argparse.ArgumentParser(description="Publica uma versão nova do PAULUS.")
    p.add_argument("etapa", nargs="?", choices=["preparar", "enviar", "tudo"], default="tudo",
                   help="preparar (instalador e teste), enviar (release e site) ou tudo")
    p.add_argument("--versao", help="a versão a publicar (padrão: a próxima)")
    p.add_argument("--novidade", action="append", default=[], help="uma linha do que mudou (repita)")
    p.add_argument("--forcar", action="store_true", help="publica mesmo sem commit novo desde a última release")
    a = p.parse_args()
    try:
        if a.etapa in ("preparar", "tudo"):
            e = preparar(a)
            if a.etapa == "preparar":
                print(f"PREPARADO {e['versao']} · SHA-256 {e['sha256'][:12]}… · agora: publicar.py enviar")
                return 0
        e = enviar()
    except Falha as exc:
        print("FALHOU:", exc)
        return 1
    print(f"PUBLICADO {e['versao']} · SHA-256 {e['sha256'][:12]}… · {len(e['novidades'])} novidade(s) · site {e['site']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
