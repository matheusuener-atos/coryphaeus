"""
PAULUS - Gravacoes.

O audio de reunioes, atendimentos, audiencias e notas de voz, guardado nesta
maquina (docs/ui/03-telas-desktop.md, A16). O que existe hoje: gravar pelo
microfone ou importar um arquivo, marcar momentos, anotar e ligar a um
cliente e a um servico. Transcrever por falante e resumir precisam de um
modelo de voz local que ainda nao esta aqui - e a tela diz isso em vez de
fingir uma transcricao.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

TIPOS = {
    "reuniao": "Reunião",
    "atendimento": "Atendimento",
    "audiencia": "Audiência",
    "nota": "Nota de voz",
}

# O que o navegador grava (webm/opus) e o que costuma vir de fora.
SUFIXOS = {".webm", ".ogg", ".opus", ".mp3", ".m4a", ".wav", ".aac", ".mp4", ".flac"}
MEDIA_TYPES = {
    ".webm": "audio/webm", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".wav": "audio/wav", ".aac": "audio/aac", ".flac": "audio/flac",
}

CAMPOS = ("titulo", "tipo", "cadastro_id", "servico_id", "participantes", "notas", "duracao_s")


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def duracao_texto(segundos: int) -> str:
    s = max(0, int(segundos or 0))
    h, resto = divmod(s, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class Gravacoes:
    def __init__(self, base, pasta: Path) -> None:
        self.base = base
        self.pasta = Path(pasta)

    # ---------------------------------------------------------------- leitura

    def listar(self, tipo: str = "", termo: str = "") -> list[dict]:
        sql = ("SELECT g.*, c.nome AS cliente_nome, s.nome AS servico_nome FROM gravacoes g "
               "LEFT JOIN cadastros c ON c.id = g.cadastro_id "
               "LEFT JOIN servicos s ON s.id = g.servico_id WHERE 1=1")
        parametros: list = []
        if tipo in TIPOS:
            sql += " AND g.tipo = ?"
            parametros.append(tipo)
        if termo:
            sql += " AND (g.titulo LIKE ? OR g.participantes LIKE ? OR g.notas LIKE ? OR c.nome LIKE ? OR s.nome LIKE ?)"
            like = f"%{termo}%"
            parametros += [like] * 5
        sql += " ORDER BY g.criado_em DESC"
        itens = self.base.buscar(sql, tuple(parametros))
        for g in itens:
            self._enfeitar(g)
        return itens

    def obter(self, id_: int) -> dict | None:
        g = self.base.um(
            "SELECT g.*, c.nome AS cliente_nome, s.nome AS servico_nome FROM gravacoes g "
            "LEFT JOIN cadastros c ON c.id = g.cadastro_id "
            "LEFT JOIN servicos s ON s.id = g.servico_id WHERE g.id = ?", (id_,))
        if g:
            self._enfeitar(g)
        return g

    def _enfeitar(self, g: dict) -> None:
        g["tipo_rotulo"] = TIPOS.get(g.get("tipo", ""), g.get("tipo", ""))
        g["duracao_texto"] = duracao_texto(g.get("duracao_s", 0))
        g["mb"] = round((g.get("bytes") or 0) / (1024 * 1024), 1)
        try:
            g["marcadores"] = json.loads(g.get("marcadores") or "[]")
        except json.JSONDecodeError:
            g["marcadores"] = []
        g["participantes_lista"] = [p.strip() for p in str(g.get("participantes") or "").split(",") if p.strip()]
        g["existe"] = bool(g.get("arquivo")) and (self.pasta / g["arquivo"]).exists()

    def total_segundos(self) -> int:
        linha = self.base.um("SELECT COALESCE(SUM(duracao_s), 0) AS s FROM gravacoes")
        return int(linha["s"]) if linha else 0

    def caminho(self, id_: int) -> Path | None:
        g = self.base.um("SELECT arquivo FROM gravacoes WHERE id = ?", (id_,))
        if not g or not g["arquivo"]:
            return None
        alvo = self.pasta / g["arquivo"]
        return alvo if alvo.exists() else None

    # ---------------------------------------------------------------- escrita

    def guardar(self, dados: dict, conteudo: bytes, nome_original: str) -> int:
        sufixo = Path(nome_original or "").suffix.lower() or ".webm"
        if sufixo not in SUFIXOS:
            raise ValueError("formato de áudio não reconhecido: " + sufixo)
        titulo = " ".join(str(dados.get("titulo", "")).split()) or ("Gravação de " + datetime.now().strftime("%d/%m %H:%M"))
        tipo = dados.get("tipo") if dados.get("tipo") in TIPOS else "reuniao"
        id_ = self.base.escrever(
            "INSERT INTO gravacoes (titulo, tipo, cadastro_id, servico_id, participantes, arquivo, duracao_s, bytes, "
            "origem, marcadores, notas, criado_em) VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, ?, '', ?)",
            (titulo, tipo, dados.get("cadastro_id") or None, dados.get("servico_id") or None,
             str(dados.get("participantes", "")).strip(), int(dados.get("duracao_s") or 0), len(conteudo),
             dados.get("origem") if dados.get("origem") in ("gravada", "importada") else "gravada",
             json.dumps(dados.get("marcadores") or [], ensure_ascii=False), _agora()),
        )
        self.pasta.mkdir(parents=True, exist_ok=True)
        nome = f"gravacao-{id_:05d}{sufixo}"
        (self.pasta / nome).write_bytes(conteudo)
        self.base.escrever("UPDATE gravacoes SET arquivo = ? WHERE id = ?", (nome, id_))
        return id_

    def atualizar(self, id_: int, dados: dict) -> bool:
        atual = self.base.um("SELECT * FROM gravacoes WHERE id = ?", (id_,))
        if not atual:
            return False
        novo = {c: dados.get(c, atual[c]) for c in CAMPOS}
        novo["titulo"] = " ".join(str(novo["titulo"] or "").split()) or atual["titulo"]
        novo["tipo"] = novo["tipo"] if novo["tipo"] in TIPOS else atual["tipo"]
        novo["cadastro_id"] = novo["cadastro_id"] or None
        novo["servico_id"] = novo["servico_id"] or None
        novo["duracao_s"] = int(novo["duracao_s"] or 0)
        self.base.escrever(
            "UPDATE gravacoes SET titulo = ?, tipo = ?, cadastro_id = ?, servico_id = ?, participantes = ?, "
            "notas = ?, duracao_s = ? WHERE id = ?",
            (novo["titulo"], novo["tipo"], novo["cadastro_id"], novo["servico_id"], str(novo["participantes"] or ""),
             str(novo["notas"] or ""), novo["duracao_s"], id_),
        )
        return True

    def marcar(self, id_: int, segundo: int, texto: str) -> list[dict]:
        g = self.obter(id_)
        if not g:
            raise ValueError("gravação não encontrada")
        marcadores = g["marcadores"]
        marcadores.append({"t": max(0, int(segundo or 0)), "texto": " ".join(str(texto or "").split())})
        marcadores.sort(key=lambda m: m["t"])
        self.base.escrever("UPDATE gravacoes SET marcadores = ? WHERE id = ?",
                           (json.dumps(marcadores, ensure_ascii=False), id_))
        return marcadores

    def tirar_marcador(self, id_: int, indice: int) -> list[dict]:
        g = self.obter(id_)
        if not g:
            raise ValueError("gravação não encontrada")
        marcadores = g["marcadores"]
        if 0 <= indice < len(marcadores):
            marcadores.pop(indice)
        self.base.escrever("UPDATE gravacoes SET marcadores = ? WHERE id = ?",
                           (json.dumps(marcadores, ensure_ascii=False), id_))
        return marcadores

    def apagar(self, id_: int) -> bool:
        caminho = self.caminho(id_)
        apagou = self.base.escrever("DELETE FROM gravacoes WHERE id = ?", (id_,)) > 0
        if apagou and caminho:
            try:
                caminho.unlink()
            except OSError:
                pass
        return apagou
