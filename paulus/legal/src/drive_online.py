"""
O Google Drive pela internet, no Acervo (29/09/2026).

A pessoa autoriza a leitura do Drive (google_servicos "drive_leitura", o
escopo drive.readonly) e escolhe pastas. Cada pasta escolhida vira uma copia
dentro do Acervo do PAULUS - "Acervo/Google Drive/<nome>" -, e a vigia do
Acervo le a copia como le qualquer pasta. Nada e lido do Drive a cada
pergunta, e nada vai daqui para o Drive: so se baixa.

A copia acompanha o Drive:

- a cada SINC_MINUTOS (e quando a pessoa pede), o que mudou la desce de novo
  (a versao de cada arquivo fica no manifesto, .paulus-drive.json);
- o que saiu do Drive sai da copia - so o que o PAULUS baixou, e so dentro da
  pasta da copia; arquivo que alguem pos a mao ali fica;
- so desce o que o Acervo le (PDF, Word, Excel, texto; Docs, Planilhas e
  Apresentacoes do Google saem convertidos), ate TAMANHO_MAXIMO cada.

Tirar a pasta do Acervo para de acompanhar; apagar a copia e escolha a parte.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from google_servicos import EXPORTAR, PASTA, ErroGoogle

SINC_MINUTOS = 15
TAMANHO_MAXIMO = 200 * 1024 * 1024
MAXIMO_DE_ARQUIVOS = 10000
PROFUNDIDADE = 20
MANIFESTO = ".paulus-drive.json"
NOME_DA_RAIZ = "Google Drive"
LIDOS = {".pdf", ".docx", ".txt", ".md", ".xlsx"}
_PROIBIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVADOS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def nome_no_windows(nome: str) -> str:
    """O nome do Drive como o Windows aceita: sem / : * ? etc., sem ponto no fim."""
    n = _PROIBIDOS.sub("_", str(nome or "")).strip().rstrip(". ")
    if not n:
        n = "sem nome"
    if n.split(".")[0].upper() in _RESERVADOS:
        n = "_" + n
    return n[:120]


def sufixo_do(arquivo: dict) -> str:
    """Com que extensao o arquivo chega ao Acervo - vazio se o Acervo nao le."""
    exportar = EXPORTAR.get(arquivo.get("mimeType", ""))
    if exportar:
        return exportar[1]
    s = Path(arquivo.get("name", "")).suffix.lower()
    return s if s in LIDOS else ""


def versao_do(arquivo: dict) -> str:
    return str(arquivo.get("md5Checksum") or arquivo.get("version") or arquivo.get("modifiedTime") or "")


class EspelhoDoDrive:
    """
    As pastas do Drive copiadas para o Acervo. `google` e o google_servicos.Google
    da conta do escritorio; `raiz_do_acervo()` a pasta do Acervo do PAULUS;
    `prefs` as Preferencias (chave "drive_online").
    """

    def __init__(self, google, raiz_do_acervo, prefs, *, ao_mudar=None, relogio=time.time) -> None:
        self.google = google
        self.raiz_do_acervo = raiz_do_acervo
        self.prefs = prefs
        self.ao_mudar = ao_mudar or (lambda: None)
        self.relogio = relogio
        self._trava = threading.Lock()
        self.andando: dict = {}

    # ------------------------------------------------------------ as pastas

    def raiz(self) -> Path:
        return Path(self.raiz_do_acervo()) / NOME_DA_RAIZ

    def pastas(self) -> list[dict]:
        return [dict(p) for p in (self.prefs.dados.get("drive_online") or {}).get("pastas") or []]

    def _guardar(self, pastas: list[dict]) -> None:
        self.prefs.dados.setdefault("drive_online", {})["pastas"] = pastas
        self.prefs.atualizar({})

    def _atualizar(self, pasta_id: str, **campos) -> None:
        pastas = self.pastas()
        for p in pastas:
            if p["id"] == pasta_id:
                p.update(campos)
        self._guardar(pastas)

    def local(self, pasta: dict) -> Path:
        return self.raiz() / pasta["local"]

    def incluir(self, pasta_id: str, nome: str) -> dict:
        pasta_id = str(pasta_id or "").strip()
        if not pasta_id or not re.fullmatch(r"[A-Za-z0-9_\-]{1,200}", pasta_id):
            raise ValueError("pasta do Drive inválida")
        pastas = self.pastas()
        ja = next((p for p in pastas if p["id"] == pasta_id), None)
        if ja:
            raise ValueError(f"“{ja['nome']}” já está no Acervo")
        nome = str(nome or "").strip() or "Meu Drive"
        base = nome_no_windows(nome)
        usados = {p["local"].lower() for p in pastas}
        local, n = base, 2
        while local.lower() in usados:
            local, n = f"{base} ({n})", n + 1
        nova = {"id": pasta_id, "nome": nome, "local": local, "ultimo": "", "erro": "", "arquivos": 0, "ignorados": 0}
        self._guardar(pastas + [nova])
        return nova

    def tirar(self, pasta_id: str, apagar_copia: bool = False) -> dict:
        pastas = self.pastas()
        saiu = next((p for p in pastas if p["id"] == pasta_id), None)
        if not saiu:
            raise ValueError("essa pasta do Drive não está no Acervo")
        self._guardar([p for p in pastas if p["id"] != pasta_id])
        if apagar_copia:
            alvo = self.local(saiu).resolve()
            # So a copia, e so dentro de "Acervo/Google Drive".
            if self.raiz().resolve() in alvo.parents and alvo.is_dir():
                shutil.rmtree(alvo, ignore_errors=True)
            self.ao_mudar()
        return saiu

    # ------------------------------------------------------ a sincronizacao

    def sincronizar(self, pasta_id: str = "") -> list[dict]:
        """Traz o que mudou no Drive, pasta por pasta. Uma de cada vez."""
        if not self._trava.acquire(blocking=False):
            return []
        feitas = []
        try:
            for p in self.pastas():
                if pasta_id and p["id"] != pasta_id:
                    continue
                self.andando = {"id": p["id"], "nome": p["nome"], "baixados": 0}
                try:
                    r = self._sincronizar_uma(p)
                    self._atualizar(p["id"], ultimo=datetime.now().isoformat(timespec="seconds"), erro="",
                                    arquivos=r["arquivos"], ignorados=r["ignorados"])
                    feitas.append({"id": p["id"], **r})
                    if r["baixados"] or r["removidos"]:
                        self.ao_mudar()
                except ErroGoogle as exc:
                    self._atualizar(p["id"], erro=str(exc))
                    feitas.append({"id": p["id"], "erro": str(exc)})
        finally:
            self.andando = {}
            self._trava.release()
        return feitas

    def _arvore(self, pasta_id: str) -> list[tuple[str, dict]]:
        """(caminho relativo, arquivo) de tudo o que ha abaixo da pasta."""
        saida: list[tuple[str, dict]] = []
        fila = [(pasta_id, "", 0)]
        vistas = set()
        while fila:
            atual, prefixo, nivel = fila.pop(0)
            if atual in vistas or nivel > PROFUNDIDADE:
                continue
            vistas.add(atual)
            nomes: dict[str, int] = {}
            for item in self.google.drive_listar(atual):
                eh_pasta = item.get("mimeType") == PASTA
                sufixo = "" if eh_pasta else sufixo_do(item)
                base = nome_no_windows(item.get("name", ""))
                if sufixo and not base.lower().endswith(sufixo):
                    base += sufixo
                # Dois arquivos com o mesmo nome na mesma pasta (o Drive deixa):
                # o segundo ganha " (2)" antes da extensao.
                chave = base.lower()
                nomes[chave] = nomes.get(chave, 0) + 1
                if nomes[chave] > 1:
                    raiz_, ext = (base[: -len(sufixo)], sufixo) if sufixo else (base, "")
                    base = f"{raiz_} ({nomes[chave]}){ext}"
                caminho = f"{prefixo}{base}"
                if eh_pasta:
                    fila.append((item["id"], caminho + "/", nivel + 1))
                else:
                    saida.append((caminho, item))
                if len(saida) >= MAXIMO_DE_ARQUIVOS:
                    return saida
        return saida

    def _sincronizar_uma(self, pasta: dict) -> dict:
        destino = self.local(pasta)
        destino.mkdir(parents=True, exist_ok=True)
        manifesto_p = destino / MANIFESTO
        try:
            manifesto = json.loads(manifesto_p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifesto = {}
        novo: dict[str, dict] = {}
        baixados = ignorados = 0
        for caminho, item in self._arvore(pasta["id"]):
            if not sufixo_do(item) or int(item.get("size") or 0) > TAMANHO_MAXIMO:
                ignorados += 1
                continue
            alvo = destino / caminho
            antes = manifesto.get(item["id"]) or {}
            versao = versao_do(item)
            if antes.get("versao") == versao and antes.get("caminho") == caminho and alvo.is_file():
                novo[item["id"]] = antes
                continue
            self.google.drive_baixar(item, alvo)
            baixados += 1
            self.andando["baixados"] = baixados
            # Renomeado no Drive: a copia com o nome antigo sai.
            if antes.get("caminho") and antes["caminho"] != caminho:
                self._apagar_da_copia(destino, antes["caminho"])
            novo[item["id"]] = {"caminho": caminho, "versao": versao}
            # O manifesto vai sendo gravado: caiu no meio, o que ja desceu nao desce de novo.
            if baixados % 20 == 0:
                manifesto_p.write_text(json.dumps({**manifesto, **novo}, ensure_ascii=False), encoding="utf-8")
        removidos = 0
        ficam = {v["caminho"] for v in novo.values()}
        for arquivo_id, antes in manifesto.items():
            if arquivo_id not in novo and antes.get("caminho") not in ficam:
                removidos += self._apagar_da_copia(destino, antes.get("caminho", ""))
        manifesto_p.write_text(json.dumps(novo, ensure_ascii=False), encoding="utf-8")
        return {"arquivos": len(novo), "baixados": baixados, "removidos": removidos, "ignorados": ignorados}

    @staticmethod
    def _apagar_da_copia(destino: Path, caminho: str) -> int:
        if not caminho:
            return 0
        alvo = (destino / caminho).resolve()
        if destino.resolve() not in alvo.parents or not alvo.is_file():
            return 0
        try:
            alvo.unlink()
        except OSError:
            return 0
        # Pastas que ficaram vazias saem junto, ate a raiz da copia.
        pai = alvo.parent
        while pai != destino.resolve() and destino.resolve() in pai.parents:
            try:
                pai.rmdir()
            except OSError:
                break
            pai = pai.parent
        return 1

    def para_tela(self) -> dict:
        pastas = []
        for p in self.pastas():
            pastas.append({**p, "caminho": str(self.local(p)), "sincronizando": self.andando.get("id") == p["id"],
                           "baixados_agora": self.andando.get("baixados", 0) if self.andando.get("id") == p["id"] else 0})
        return {"pastas": pastas, "sinc_minutos": SINC_MINUTOS}
