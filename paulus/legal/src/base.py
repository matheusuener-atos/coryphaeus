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
    ),    (
        "006_documentos",
        """
        -- Documento de texto e planilha moram na mesma tabela: o que muda e o
        -- formato do corpo (HTML para texto, JSON para planilha). Separar em
        -- duas tabelas duplicaria versao, historico e vinculo sem ganho.
        CREATE TABLE documentos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo        TEXT NOT NULL,
            tipo          TEXT NOT NULL DEFAULT 'texto',
            corpo         TEXT NOT NULL DEFAULT '',
            cadastro_id   INTEGER REFERENCES cadastros(id) ON DELETE SET NULL,
            criado_em     TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        );
        CREATE INDEX idx_documentos_tipo ON documentos(tipo);

        -- Uma versao por gravacao com mudanca real. E o que sustenta o
        -- "comparar versoes" e o "voltar para a v6" da tela.
        CREATE TABLE versoes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
            numero       INTEGER NOT NULL,
            corpo        TEXT NOT NULL,
            nota         TEXT DEFAULT '',
            criada_em    TEXT NOT NULL
        );
        CREATE INDEX idx_versoes_doc ON versoes(documento_id, numero);
        """,
    ),    (
        "007_financeiro_e_bem_estar",
        """
        -- Dinheiro em centavos inteiros, nunca em ponto flutuante. Somar
        -- 0,1 + 0,2 em float da 0,30000000000000004; num extrato de honorarios
        -- o erro aparece depois de algumas dezenas de lancamentos, e ninguem
        -- confere extrato somando de cabeca.
        CREATE TABLE lancamentos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo        TEXT NOT NULL,               -- 'recebimento' | 'despesa'
            descricao   TEXT NOT NULL,
            centavos    INTEGER NOT NULL DEFAULT 0,
            categoria   TEXT DEFAULT '',
            cadastro_id INTEGER REFERENCES cadastros(id) ON DELETE SET NULL,
            vencimento  TEXT DEFAULT '',
            liquidado_em TEXT DEFAULT '',            -- vazio = ainda em aberto
            observacao  TEXT DEFAULT '',
            criado_em   TEXT NOT NULL
        );
        CREATE INDEX idx_lanc_venc ON lancamentos(vencimento);
        CREATE INDEX idx_lanc_tipo ON lancamentos(tipo, liquidado_em);

        -- Comprovante fica ligado ao lancamento pelo SHA-1, como os vinculos:
        -- renomear ou mover o arquivo nao quebra a ligacao.
        CREATE TABLE comprovantes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            lancamento_id INTEGER NOT NULL REFERENCES lancamentos(id) ON DELETE CASCADE,
            nome          TEXT NOT NULL,
            sha1          TEXT DEFAULT '',
            caminho       TEXT DEFAULT '',
            criado_em     TEXT NOT NULL
        );
        CREATE INDEX idx_compr_lanc ON comprovantes(lancamento_id);

        -- Bem-estar guarda TOTAIS do dia, nunca o que foi digitado. O que o
        -- programa mede e tempo sem toque no teclado ou mouse; conteudo de
        -- tecla nao passa por aqui em momento nenhum.
        CREATE TABLE bem_estar (
            dia            TEXT PRIMARY KEY,
            minutos_ativos INTEGER NOT NULL DEFAULT 0,
            ciclos         INTEGER NOT NULL DEFAULT 0,
            pausas         INTEGER NOT NULL DEFAULT 0,
            copos_agua     INTEGER NOT NULL DEFAULT 0,
            maior_seguida  INTEGER NOT NULL DEFAULT 0,
            atualizado_em  TEXT NOT NULL
        );

        CREATE TABLE lembretes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo     TEXT NOT NULL,
            cada_min   INTEGER NOT NULL DEFAULT 60,
            meta_dia   INTEGER NOT NULL DEFAULT 0,
            ligado     INTEGER NOT NULL DEFAULT 1,
            feitos_dia INTEGER NOT NULL DEFAULT 0,
            dia        TEXT DEFAULT '',
            ultima_vez TEXT DEFAULT '',
            criado_em  TEXT NOT NULL
        );
        """,
    ),    (
        "008_tarefa_lembrete_e_repeticao",
        """
        -- Hora do aviso e recorrencia. Repetir e comportamento, nao rotulo:
        -- concluir uma tarefa que repete cria a proxima, com o prazo andado.
        ALTER TABLE tarefas ADD COLUMN lembrar_em TEXT DEFAULT '';
        ALTER TABLE tarefas ADD COLUMN repetir TEXT DEFAULT '';
        """,
    ),    (
        "009_leis",
        """
        -- Os codigos oficiais, guardados artigo por artigo. Citar passa a ser
        -- consulta a um indice, nao palpite de modelo.
        CREATE TABLE leis (
            codigo       TEXT PRIMARY KEY,
            nome         TEXT NOT NULL,
            lei          TEXT NOT NULL,
            fonte        TEXT DEFAULT '',
            arquivo      TEXT DEFAULT '',
            artigos      INTEGER NOT NULL DEFAULT 0,
            importado_em TEXT NOT NULL
        );

        CREATE TABLE artigos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo       TEXT NOT NULL,
            numero       TEXT NOT NULL,
            ordem        INTEGER NOT NULL DEFAULT 0,
            texto        TEXT NOT NULL,
            contexto     TEXT DEFAULT '',
            -- O texto compilado mantem os revogados no corpo. Citar um artigo
            -- revogado como se estivesse em vigor e o erro mais caro daqui.
            revogado     INTEGER NOT NULL DEFAULT 0,
            alterado_por TEXT DEFAULT ''
        );
        CREATE UNIQUE INDEX idx_artigo_unico ON artigos(codigo, ordem);
        CREATE INDEX idx_artigo_codigo ON artigos(codigo);

        -- Busca por palavra. FTS5 acompanha o SQLite do Python, entao nao ha
        -- dependencia nova para procurar "boa-fe" em quatro mil artigos.
        CREATE VIRTUAL TABLE artigos_busca USING fts5(
            codigo, numero, texto, tokenize = 'unicode61 remove_diacritics 2'
        );
        """,
    ),
    (
        "010_marcas_da_biblioteca",
        """
        -- O que a pessoa marcou sobre um documento da biblioteca. Fica por
        -- SHA-1, e nao por caminho, porque mover ou renomear o arquivo nao
        -- pode apagar a marca: e o mesmo documento.
        CREATE TABLE marcas_acervo (
            sha1       TEXT PRIMARY KEY,
            fixado     INTEGER NOT NULL DEFAULT 0,
            fixado_em  TEXT DEFAULT '',
            visto_em   TEXT DEFAULT ''
        );
        CREATE INDEX idx_marcas_fixado ON marcas_acervo(fixado);
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
