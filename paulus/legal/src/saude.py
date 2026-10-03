"""
A saude do PAULUS (docs/PLANO-PRODUTO.md, P2): o que pode estar atrapalhando
agora, com o que fazer em cada caso, e um diagnostico para o suporte.

O PAULUS roda na maquina do escritorio, muitas vezes com pouca memoria e
varias coisas pesadas disputando (o modelo de IA, a transcricao, o Acervo).
Quando algo falha, a pessoa precisa ver o motivo em portugues - e o suporte,
um retrato do estado sem documento nem dado de cliente.

Os erros do servidor ficam num anel na memoria: a hora, a rota (o molde, com
{id}, nunca o endereco de verdade), o tipo da excecao e onde no codigo (so o
nome do arquivo e a linha). A mensagem da excecao NAO entra: ela pode trazer
nome de cliente ou de arquivo.
"""

from __future__ import annotations

import platform
import shutil
import sys
import time
import traceback
from collections import deque
from pathlib import Path

ERROS: deque = deque(maxlen=200)


def anotar_erro(rota: str, exc: BaseException) -> None:
    onde = ""
    for quadro in reversed(traceback.extract_tb(exc.__traceback__)):
        if "site-packages" not in quadro.filename:
            onde = f"{Path(quadro.filename).name}:{quadro.lineno}"
            break
    ERROS.append({"quando": time.strftime("%Y-%m-%dT%H:%M:%S"), "rota": rota, "tipo": type(exc).__name__, "onde": onde})


def erros_recentes(horas: float = 24) -> list[dict]:
    limite = time.time() - horas * 3600
    saida = []
    for e in ERROS:
        try:
            if time.mktime(time.strptime(e["quando"], "%Y-%m-%dT%H:%M:%S")) >= limite:
                saida.append(e)
        except ValueError:
            continue
    return saida


def _item(chave, rotulo, estado, valor, dica="") -> dict:
    return {"chave": chave, "rotulo": rotulo, "estado": estado, "valor": valor, "dica": dica}


def _gb(bytes_: float) -> str:
    return f"{bytes_ / 1e9:.1f}".replace(".", ",") + " GB"


def verificar(*, dados: Path, modelo_ok: tuple[bool, str], backup: dict, acesso: dict, sem_internet: dict | None,
              anuncio: dict | None, versao: str) -> list[dict]:
    """A lista do que conferir, cada item com estado ok | aviso | erro | neutro e o que fazer."""
    itens = []
    try:
        import psutil

        livre = psutil.virtual_memory().available
        estado = "ok" if livre >= 2e9 else ("aviso" if livre >= 1e9 else "erro")
        itens.append(_item("memoria", "Memória livre", estado, _gb(livre),
                           "" if estado == "ok" else "Feche programas pesados (navegador com muitas abas, jogos). "
                           "A transcrição precisa de uns 2 GB livres, e o modelo de IA, do tamanho dele."))
    except Exception:  # noqa: BLE001
        pass
    try:
        livre = shutil.disk_usage(dados).free
        estado = "ok" if livre >= 5e9 else ("aviso" if livre >= 1e9 else "erro")
        itens.append(_item("disco", "Espaço em disco", estado, _gb(livre) + " livres",
                           "" if estado == "ok" else "Libere espaço: com o disco cheio, o PAULUS não grava documentos nem backups."))
    except OSError:
        pass
    ok, msg = modelo_ok
    itens.append(_item("modelo", "Modelo de IA", "ok" if ok else "erro", "pronto" if ok else "não responde",
                       "" if ok else "Abra o Ollama (ou reinicie o computador) e confira o modelo em Configurações › Modelos."))
    ultimo = backup.get("ultimo") or ""
    if backup.get("ultimo_erro"):
        itens.append(_item("backup", "Backup", "erro", "falhou", "O último backup falhou: " + backup["ultimo_erro"] +
                           ". Veja em Configurações › Backup."))
    elif not (backup.get("pasta") and backup.get("senha")):
        itens.append(_item("backup", "Backup", "aviso", "não configurado",
                           "Tudo do escritório mora neste computador. Ligue o backup em Configurações › Backup."))
    else:
        try:
            dias = (time.time() - time.mktime(time.strptime(ultimo, "%Y-%m-%dT%H:%M:%S"))) / 86400 if ultimo else None
        except ValueError:
            dias = None
        if dias is None:
            itens.append(_item("backup", "Backup", "aviso", "ainda não fez", "Faça o primeiro em Configurações › Backup."))
        elif dias > 2:
            itens.append(_item("backup", "Backup", "aviso", f"há {int(dias)} dias",
                               "O backup automático só roda com o PAULUS aberto. Faça um agora em Configurações › Backup."))
        else:
            itens.append(_item("backup", "Backup", "ok", "em dia"))
    if acesso.get("ligado"):
        conectado = acesso.get("estado") == "conectado"
        itens.append(_item("acesso", "Acesso de fora", "ok" if conectado else "aviso",
                           acesso.get("hostname") or ("conectado" if conectado else acesso.get("estado", "")),
                           "" if conectado else "O túnel não está conectado: confira a internet deste computador."))
    else:
        itens.append(_item("acesso", "Acesso de fora", "neutro", "desligado"))
    if sem_internet is not None:
        pronto = bool(sem_internet.get("pronto"))
        itens.append(_item("sem_internet", "Entrar sem internet", "ok" if pronto else "aviso", "ligado" if pronto else "desligado",
                           "" if pronto else "Sem internet, o PAULUS travado não abre. Ligue em Configurações › Escritório e equipe."))
    if anuncio and anuncio.get("nova"):
        itens.append(_item("versao", "Versão", "aviso", f"{versao} · a {anuncio.get('versao')} está disponível",
                           "Atualize em Configurações › Versão."))
    else:
        itens.append(_item("versao", "Versão", "ok", versao))
    recentes = erros_recentes()
    itens.append(_item("erros", "Erros nas últimas 24 h", "ok" if not recentes else "aviso", str(len(recentes)),
                       "" if not recentes else "Se algo parou de funcionar, gere o diagnóstico abaixo e mande ao suporte."))
    return itens


def diagnostico(itens: list[dict], *, versao: str, extras: dict) -> str:
    """O texto que o escritorio manda ao suporte: estado e erros, sem dado de cliente."""
    linhas = [f"PAULUS {versao} — diagnóstico de {time.strftime('%d/%m/%Y %H:%M')}", "",
              f"Windows: {platform.platform()}", f"Python: {sys.version.split()[0]}"]
    try:
        import psutil

        linhas.append(f"Memória: {_gb(psutil.virtual_memory().total)} no total")
        linhas.append(f"Processador: {psutil.cpu_count(logical=True)} núcleos")
    except Exception:  # noqa: BLE001
        pass
    for k, v in extras.items():
        linhas.append(f"{k}: {v}")
    linhas += ["", "Saúde:"]
    for i in itens:
        linhas.append(f"  [{i['estado']}] {i['rotulo']}: {i['valor']}")
    linhas += ["", "Erros recentes (hora · rota · tipo · onde):"]
    recentes = list(ERROS)[-50:]
    if not recentes:
        linhas.append("  nenhum")
    for e in recentes:
        linhas.append(f"  {e['quando']} · {e['rota']} · {e['tipo']} · {e['onde']}")
    linhas += ["", "Este arquivo não tem documentos, nomes de clientes nem conteúdo de conversa."]
    return "\n".join(linhas) + "\n"
