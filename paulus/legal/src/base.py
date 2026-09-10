"""
PAULUS - Base local.

Ate aqui o programa guardava arquivo e conversa. Cinco telas do manual
precisam da mesma coisa que nao existia: um lugar para guardar registro -
cadastros, tarefas, compromissos, lancamentos.

SQLite, no proprio disco. Sem servidor para instalar, sem processo extra
rodando, e o arquivo inteiro cabe num backup que a pessoa entende: um arquivo.

O esquema evolui por migracoes numeradas. Trocar o formato de uma tabela num
programa que ja rodou na maquina de alguem significa perder o que estava la;
migracao aplicada em ordem e a diferenca entre acrescentar campo e perder
cadastro.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

# Cada entrada roda uma vez, na ordem, e nunca mais. Acrescentar coluna e
# acrescentar migracao - nunca editar uma que ja rodou.
MIGRACOES: list[tuple[str, str]] = [
    (
        "001_cadastros",
        """
        CREATE TABLE cadastros (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo           TEXT NOT NULL DEFAULT 'cliente',
            nome           TEXT NOT NULL,
            documento      TEXT DEFAULT '',
            telefone       TEXT DEFAULT '',
            email          TEXT DEFAULT '',
            endereco       TEXT DEFAULT '',
            honorario      TEXT DEFAULT '',
            dia_vencimento INTEGER DEFAULT 0,
            avisar_dias    INTEGER DEFAULT 0,
            observacao     TEXT DEFAULT '',
            criado_em      TEXT NOT NULL,
            atualizado_em  TEXT NOT NULL
        );
        CREATE INDEX idx_cadastros_nome ON cadastros(nome);
        CREATE INDEX idx_cadastros_tipo ON cadastros(tipo);
        """,
    ),
    (
        "002_tarefas",
        """
        CREATE TABLE tarefas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo       TEXT NOT NULL,
            lista        TEXT DEFAULT '',
            importante   INTEGER NOT NULL DEFAULT 0,
            prazo        TEXT DEFAULT '',
            concluida    INTEGER NOT NULL DEFAULT 0,
            concluida_em TEXT DEFAULT '',
            cadastro_id  INTEGER REFERENCES cadastros(id) ON DELETE SET NULL,
            anotacao     TEXT DEFAULT '',
            criada_em    TEXT NOT NULL
        );
        CREATE INDEX idx_tarefas_prazo ON tarefas(prazo);
        CREATE INDEX idx_tarefas_concluida ON tarefas(concluida);

        CREATE TABLE etapas (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            tarefa_id INTEGER NOT NULL REFERENCES tarefas(id) ON DELETE CASCADE,
            titulo    TEXT NOT NULL,
            feita     INTEGER NOT NULL DEFAULT 0,
            ordem     INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX idx_etapas_tarefa ON etapas(tarefa_id);
        """,
    ),
    (
        "003_vinculos",
        """
        -- Liga um registro a um documento da biblioteca, pelo SHA-1: assim
        -- renomear ou mover o arquivo nao quebra o vinculo.
        CREATE TABLE vinculos (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo     TEXT NOT NULL,          -- 'cadastro' | 'tarefa'
            alvo_id  INTEGER NOT NULL,
            sha1     TEXT NOT NULL,
            nome     TEXT DEFAULT '',
            criado_em TEXT NOT NULL
        );
        CREATE UNIQUE INDEX idx_vinculo_unico ON vinculos(tipo, alvo_id, sha1);
        """,
    ),
    (
        "004_meu_dia",
        """
        -- "Meu dia" e escolha da pessoa, nao consequencia da data: o wireframe
        -- tem "Adicionar ao Meu dia" como acao. Derivar so do prazo faria a
        -- lista mudar sozinha durante o dia de trabalho.
        ALTER TABLE tarefas ADD COLUMN meu_dia INTEGER NOT NULL DEFAULT 0;
        """,
    ),
    (
        "005_agenda",
        """
        CREATE TABLE compromissos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo      TEXT NOT NULL,
            tipo        TEXT NOT NULL DEFAULT 'compromisso',
            data        TEXT NOT NULL,
            hora        TEXT NOT NULL DEFAULT '09:00',
            duracao     INTEGER NOT NULL DEFAULT 60,
            onde        TEXT DEFAULT '',
            cadastro_id INTEGER REFERENCES cadastros(id) ON DELETE SET NULL,
            anotacao    TEXT DEFAULT '',
            avisar_min  INTEGER NOT NULL DEFAULT 0,
            criado_em   TEXT NOT NULL
        );
        CREATE INDEX idx_compromissos_data ON compromissos(data);

        -- Uma nota por dia: o wireframe tem "NOTAS DO DIA", nao notas soltas.
        CREATE TABLE notas_dia (
            dia           TEXT PRIMARY KEY,
            texto         TEXT NOT NULL DEFAULT '',
            atualizado_em TEXT NOT NULL
        );
        """,
    ),
]


class Base:
    """
    Conexao unica, protegida por trava.

    O programa e de uma pessoa numa maquina, mas o servidor responde em varias
    threads. Uma conexao com `check_same_thread=False` mais uma trava e mais
    simples de acertar do que uma conexao por thread, e o volume aqui nunca
    justifica o contrario.
    """

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._trava = threading.Lock()
        self.con = sqlite3.connect(str(self.caminho), check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.execute("PRAGMA journal_mode = WAL")
        self.migrar()

    # ------------------------------------------------------------ migracoes

    def migrar(self) -> list[str]:
        """Aplica o que ainda nao rodou. Devolve o que aplicou agora."""
        with self._trava:
            self.con.execute(
                "CREATE TABLE IF NOT EXISTS migracoes ("
                " nome TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)"
            )
            ja = {l["nome"] for l in self.con.execute("SELECT nome FROM migracoes")}

            aplicadas: list[str] = []
            for nome, sql in MIGRACOES:
                if nome in ja:
                    continue
                self.con.executescript(sql)
                self.con.execute(
                    "INSERT INTO migracoes (nome, aplicada_em) VALUES (?, datetime('now','localtime'))",
                    (nome,),
                )
                aplicadas.append(nome)

            self.con.commit()
            return aplicadas

    # --------------------------------------------------------------- acesso

    def buscar(self, sql: str, parametros: tuple = ()) -> list[dict]:
        with self._trava:
            return [dict(l) for l in self.con.execute(sql, parametros)]

    def um(self, sql: str, parametros: tuple = ()) -> dict | None:
        linhas = self.buscar(sql, parametros)
        return linhas[0] if linhas else None

    def escrever(self, sql: str, parametros: tuple = ()) -> int:
        """Executa e devolve o id da linha inserida (ou o numero de alteradas)."""
        with self._trava:
            cursor = self.con.execute(sql, parametros)
            self.con.commit()
            return cursor.lastrowid or cursor.rowcount

    def contar(self, tabela: str, onde: str = "", parametros: tuple = ()) -> int:
        sql = f"SELECT COUNT(*) AS n FROM {tabela}"
        if onde:
            sql += f" WHERE {onde}"
        linha = self.um(sql, parametros)
        return int(linha["n"]) if linha else 0

    def fechar(self) -> None:
        with self._trava:
            self.con.close()
