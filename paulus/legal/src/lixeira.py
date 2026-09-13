"""
PAULUS - Lixeira.

Apagar nunca e definitivo na hora (docs/ui/05-interacoes-e-estados.md): o
que sai da tela vai para a lixeira por 30 dias, com tudo que precisa para
voltar - a linha do banco, as filhas (etapas, versoes, comentarios,
comprovantes, vinculos), as ligacoes por cadastro_id que o banco zeraria e
os arquivos no disco (o audio de uma gravacao, o JSON de uma conversa).

"Desfazer" no aviso e "Restaurar" em Configuracoes > Lixeira chamam o mesmo
restaurar(). Depois de 30 dias a entrada e os arquivos somem sozinhos.
"""

from __future__ import annotations

import json
import math
import shutil
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

DIAS = 30

# O que cada tipo leva junto ao sair e ao voltar. As filhas sao apagadas por
# aqui mesmo antes da linha, para a lixeira guardar uma copia (com o banco em
# cascata, elas sumiriam antes de serem lidas).
TIPOS = {
    "conversa": {"rotulo": "Conversa"},
    "tarefa": {"rotulo": "Tarefa", "tabela": "tarefas",
               "filhos": [("etapas", "tarefa_id", ""), ("vinculos", "alvo_id", "tipo = 'tarefa'")]},
    "compromisso": {"rotulo": "Compromisso", "tabela": "compromissos", "filhos": []},
    "servico": {"rotulo": "Serviço", "tabela": "servicos",
                "filhos": [("vinculos", "alvo_id", "tipo = 'servico'")]},
    "gravacao": {"rotulo": "Gravação", "tabela": "gravacoes", "filhos": []},
    "documento": {"rotulo": "Documento", "tabela": "documentos",
                  "filhos": [("versoes", "documento_id", ""), ("comentarios", "documento_id", "")]},
    "lancamento": {"rotulo": "Lançamento", "tabela": "lancamentos",
                   "filhos": [("comprovantes", "lancamento_id", "")]},
    "cadastro": {"rotulo": "Cadastro", "tabela": "cadastros",
                 "filhos": [("vinculos", "alvo_id", "tipo = 'cadastro'")]},
}
# Tabelas que apontam para um cadastro: ao apagar a ficha o banco zera a
# ligacao (ON DELETE SET NULL); a lixeira anota quem apontava para religar.
LIGACOES_DE_CADASTRO = ("tarefas", "compromissos", "lancamentos", "servicos", "gravacoes", "documentos")


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Lixeira:
    def __init__(self, base, pasta: Path) -> None:
        self.base = base
        self.pasta = Path(pasta)

    # ---------------------------------------------------------------- entrar

    def apagar_linha(self, tipo: str, id_: int, titulo: str, detalhe: str = "",
                     arquivos: list | None = None) -> dict | None:
        """Tira do banco (a linha, as filhas, os arquivos) e guarda tudo na lixeira."""
        spec = TIPOS[tipo]
        tabela = spec["tabela"]
        linha = self.base.um(f"SELECT * FROM {tabela} WHERE id = ?", (id_,))
        if not linha:
            return None
        filhos = {}
        for tf, coluna, condicao in spec["filhos"]:
            sql = f"SELECT * FROM {tf} WHERE {coluna} = ?" + (f" AND {condicao}" if condicao else "")
            filhos[tf] = self.base.buscar(sql, (id_,))
        ligacoes = {}
        if tipo == "cadastro":
            for t in LIGACOES_DE_CADASTRO:
                ligacoes[t] = [int(r["id"]) for r in self.base.buscar(f"SELECT id FROM {t} WHERE cadastro_id = ?", (id_,))]
        movidos = [self.mover_arquivo(Path(a)) for a in (arquivos or []) if a and Path(a).exists()]
        for tf, coluna, condicao in spec["filhos"]:
            self.base.escrever(f"DELETE FROM {tf} WHERE {coluna} = ?" + (f" AND {condicao}" if condicao else ""), (id_,))
        self.base.escrever(f"DELETE FROM {tabela} WHERE id = ?", (id_,))
        return self.guardar(tipo, str(id_), titulo, detalhe, {"linha": linha, "filhos": filhos, "ligacoes": ligacoes}, movidos)

    def guardar(self, tipo: str, alvo_id: str, titulo: str, detalhe: str, dados: dict, arquivos: list | None = None) -> dict:
        if tipo not in TIPOS:
            raise ValueError("tipo desconhecido: " + tipo)
        novo = self.base.escrever(
            "INSERT INTO lixeira (tipo, alvo_id, titulo, detalhe, dados, arquivos, apagado_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tipo, alvo_id, titulo, detalhe, json.dumps(dados, ensure_ascii=False), json.dumps(arquivos or [], ensure_ascii=False), _agora()),
        )
        return self.obter(novo)

    def mover_arquivo(self, caminho: Path) -> dict:
        """Leva o arquivo para data/lixeira com um nome que nao colide; devolve de onde veio."""
        self.pasta.mkdir(parents=True, exist_ok=True)
        destino = self.pasta / (uuid.uuid4().hex[:8] + "_" + caminho.name)
        shutil.move(str(caminho), str(destino))
        return {"de": str(caminho), "para": str(destino)}

    # ------------------------------------------------------------------ ver

    def _enfeitar(self, e: dict) -> dict:
        e["tipo_rotulo"] = TIPOS.get(e["tipo"], {}).get("rotulo", e["tipo"])
        try:
            apagado = datetime.fromisoformat(e["apagado_em"])
        except ValueError:
            apagado = datetime.now()
        vence = apagado + timedelta(days=DIAS)
        e["vence_em"] = vence.isoformat(timespec="seconds")
        # Arredonda para cima: apagado agora "some em 30 dias", nao em 29.
        e["dias_restantes"] = max(0, math.ceil((vence - datetime.now()).total_seconds() / 86400))
        e["arquivos"] = json.loads(e.get("arquivos") or "[]")
        return e

    def listar(self) -> list[dict]:
        linhas = self.base.buscar("SELECT id, tipo, alvo_id, titulo, detalhe, arquivos, apagado_em FROM lixeira ORDER BY apagado_em DESC")
        return [self._enfeitar(l) for l in linhas]

    def obter(self, id_: int) -> dict | None:
        e = self.base.um("SELECT * FROM lixeira WHERE id = ?", (id_,))
        if not e:
            return None
        self._enfeitar(e)
        e["dados"] = json.loads(e.get("dados") or "{}")
        return e

    def contagem(self) -> int:
        return self.base.contar("lixeira")

    # ---------------------------------------------------------------- voltar

    def restaurar(self, id_: int) -> dict:
        """Poe de volta a linha, as filhas, as ligacoes e os arquivos. Devolve a entrada restaurada."""
        e = self.obter(id_)
        if not e:
            raise ValueError("essa entrada não está mais na lixeira")
        spec = TIPOS[e["tipo"]]
        dados = e["dados"]
        if "tabela" in spec:
            linha = dados.get("linha") or {}
            if self.base.um(f"SELECT id FROM {spec['tabela']} WHERE id = ?", (linha.get("id"),)):
                raise ValueError("já existe um registro no lugar deste")
            try:
                self._repor(spec["tabela"], linha)
                for tf, _coluna, _cond in spec["filhos"]:
                    for filha in dados.get("filhos", {}).get(tf, []):
                        self._repor(tf, filha)
            except sqlite3.IntegrityError as exc:
                raise ValueError("não consegui repor: " + str(exc)) from exc
            for t, ids in (dados.get("ligacoes") or {}).items():
                for alvo in ids:
                    self.base.escrever(f"UPDATE {t} SET cadastro_id = ? WHERE id = ? AND cadastro_id IS NULL", (linha["id"], alvo))
        for a in e["arquivos"]:
            de, para = Path(a["de"]), Path(a["para"])
            if para.exists():
                de.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(para), str(de))
        self.base.escrever("DELETE FROM lixeira WHERE id = ?", (id_,))
        return e

    def _repor(self, tabela: str, linha: dict) -> None:
        colunas = list(linha.keys())
        marcas = ", ".join("?" for _ in colunas)
        self.base.escrever(f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({marcas})", tuple(linha[c] for c in colunas))

    # ---------------------------------------------------------------- sumir

    def tirar(self, id_: int) -> bool:
        """Apaga de vez: a entrada e os arquivos que ela guardava."""
        e = self.obter(id_)
        if not e:
            return False
        for a in e["arquivos"]:
            try:
                Path(a["para"]).unlink(missing_ok=True)
            except OSError:
                pass
        self.base.escrever("DELETE FROM lixeira WHERE id = ?", (id_,))
        return True

    def esvaziar(self) -> int:
        return sum(1 for e in self.listar() if self.tirar(e["id"]))

    def esvaziar_vencidos(self) -> int:
        """O que passou de 30 dias some sozinho; chamado ao abrir o programa e ao abrir a lista."""
        limite = (datetime.now() - timedelta(days=DIAS)).isoformat(timespec="seconds")
        vencidos = self.base.buscar("SELECT id FROM lixeira WHERE apagado_em < ?", (limite,))
        return sum(1 for v in vencidos if self.tirar(int(v["id"])))
