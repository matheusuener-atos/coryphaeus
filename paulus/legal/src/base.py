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
    ),
    (
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
    (
        "011_folha_e_papelada",
        """
        -- Quanto cada pessoa recebe fica no cadastro dela. Uma segunda lista
        -- de gente seria duas verdades sobre a mesma pessoa, e a hora de
        -- descobrir que divergiram e a hora de pagar.
        ALTER TABLE cadastros ADD COLUMN vinculo TEXT DEFAULT '';
        ALTER TABLE cadastros ADD COLUMN salario_centavos INTEGER DEFAULT 0;
        ALTER TABLE cadastros ADD COLUMN encargos_centavos INTEGER DEFAULT 0;

        -- A folha de um mes, com o valor de cada pessoa NAQUELE mes. E copia,
        -- e nao referencia: aumentar o salario hoje nao pode reescrever a
        -- folha de agosto, que ja foi paga por um valor que foi aquele.
        CREATE TABLE folha (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            mes               TEXT NOT NULL,
            cadastro_id       INTEGER,
            nome              TEXT NOT NULL,
            vinculo           TEXT DEFAULT '',
            salario_centavos  INTEGER NOT NULL DEFAULT 0,
            encargos_centavos INTEGER NOT NULL DEFAULT 0,
            observacao        TEXT DEFAULT '',
            lancamento_id     INTEGER,
            criado_em         TEXT NOT NULL
        );
        CREATE UNIQUE INDEX idx_folha_mes_pessoa ON folha(mes, cadastro_id);
        CREATE INDEX idx_folha_mes ON folha(mes);

        -- Nota fiscal e boleto: o registro do que existe FORA daqui. A emissao
        -- da nota e da prefeitura e o boleto sai do banco - guardar o numero e
        -- a data e o que da para fazer com verdade nesta maquina.
        CREATE TABLE papeis_fiscais (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo          TEXT NOT NULL,
            numero        TEXT DEFAULT '',
            cadastro_id   INTEGER,
            lancamento_id INTEGER,
            centavos      INTEGER NOT NULL DEFAULT 0,
            data          TEXT DEFAULT '',
            situacao      TEXT DEFAULT '',
            observacao    TEXT DEFAULT '',
            criado_em     TEXT NOT NULL
        );
        CREATE INDEX idx_papel_tipo ON papeis_fiscais(tipo, data);
        CREATE INDEX idx_papel_lancamento ON papeis_fiscais(lancamento_id);
        """,
    ),
    (
        "012_formato_do_documento",
        """
        -- Fonte, corpo, recuo de primeira linha e entrelinhas, por documento.
        -- Nao e preferencia do escritorio: uma peticao e um contrato pedem
        -- recuos diferentes, e quem escreve os dois no mesmo dia nao pode ter
        -- que trocar a configuracao entre um e outro.
        --
        -- Vazio significa "o padrao" - documento antigo continua saindo
        -- exatamente como saia antes desta coluna existir.
        ALTER TABLE documentos ADD COLUMN formato TEXT DEFAULT '';
        """,
    ),
    (
        "013_comentarios",
        """
        -- Observacao presa a um trecho do documento - a nota de margem que se
        -- faz lendo contrato do outro lado.
        --
        -- A ancora e o TEXTO do paragrafo, e nao o numero dele. Numero de
        -- paragrafo muda toda vez que alguem insere uma linha acima, e o
        -- comentario passaria a apontar para o paragrafo errado calado - o que
        -- e pior que nao ter comentario. Pelo texto, ou acha o paragrafo certo,
        -- ou diz que o trecho nao existe mais.
        CREATE TABLE comentarios (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            -- Em cascata, como as versoes: apagar o documento tem que levar os
            -- comentarios dele. Comentario orfao nao aparece em tela nenhuma e
            -- fica no banco para sempre.
            documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
            trecho       TEXT NOT NULL DEFAULT '',
            texto        TEXT NOT NULL,
            origem       TEXT NOT NULL DEFAULT 'assistente',
            resolvido    INTEGER NOT NULL DEFAULT 0,
            criado_em    TEXT NOT NULL
        );
        CREATE INDEX idx_comentarios_doc ON comentarios(documento_id, resolvido);
        """,
    ),
    (
        "014_servicos",
        """
        -- Servicos: a pasta de trabalho de um assunto (docs/ui, A15). Etapas,
        -- equipe, anotacoes e trilha ficam em JSON: sao listas curtas que so
        -- fazem sentido dentro do servico. Os arquivos sao vinculos ao Acervo
        -- (tabela vinculos, tipo 'servico'); prazos e compromissos vem do
        -- cliente, pela Agenda.
        CREATE TABLE servicos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nome          TEXT NOT NULL,
            cadastro_id   INTEGER REFERENCES cadastros(id) ON DELETE SET NULL,
            descricao     TEXT DEFAULT '',
            status        TEXT NOT NULL DEFAULT 'andamento',
            etapas        TEXT NOT NULL DEFAULT '[]',
            equipe        TEXT NOT NULL DEFAULT '[]',
            anotacoes     TEXT NOT NULL DEFAULT '[]',
            trilha        TEXT NOT NULL DEFAULT '[]',
            resumo        TEXT DEFAULT '',
            resumo_em     TEXT DEFAULT '',
            criado_em     TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            concluido_em  TEXT DEFAULT ''
        );
        CREATE INDEX idx_servicos_status ON servicos(status);
        """,
    ),
    (
        "015_gravacoes",
        """
        -- Gravacoes (docs/ui, A16): o audio fica em data/gravacoes; aqui so o
        -- que se sabe dele. Transcricao e resumo entram quando houver modelo
        -- de voz local - ate la a tela diz que faltam.
        CREATE TABLE gravacoes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo        TEXT NOT NULL,
            tipo          TEXT NOT NULL DEFAULT 'reuniao',
            cadastro_id   INTEGER REFERENCES cadastros(id) ON DELETE SET NULL,
            servico_id    INTEGER REFERENCES servicos(id) ON DELETE SET NULL,
            participantes TEXT DEFAULT '',
            arquivo       TEXT DEFAULT '',
            duracao_s     INTEGER NOT NULL DEFAULT 0,
            bytes         INTEGER NOT NULL DEFAULT 0,
            origem        TEXT NOT NULL DEFAULT 'gravada',
            marcadores    TEXT NOT NULL DEFAULT '[]',
            notas         TEXT DEFAULT '',
            criado_em     TEXT NOT NULL
        );
        CREATE INDEX idx_gravacoes_tipo ON gravacoes(tipo);
        """,
    ),
    (
        "016_transcricoes",
        """
        -- A transcricao (Whisper nesta maquina) e o resumo escrito pelo
        -- modelo local ficam na propria gravacao: sao um por gravacao e
        -- nascem dela. O estado diz onde a fila esta: '' (nao pedida),
        -- fila, transcrevendo, pronta, erro.
        ALTER TABLE gravacoes ADD COLUMN transcricao TEXT NOT NULL DEFAULT '[]';
        ALTER TABLE gravacoes ADD COLUMN transcricao_estado TEXT NOT NULL DEFAULT '';
        ALTER TABLE gravacoes ADD COLUMN transcricao_em TEXT DEFAULT '';
        ALTER TABLE gravacoes ADD COLUMN transcricao_modelo TEXT DEFAULT '';
        ALTER TABLE gravacoes ADD COLUMN transcricao_erro TEXT DEFAULT '';
        ALTER TABLE gravacoes ADD COLUMN transcricao_tempo REAL NOT NULL DEFAULT 0;
        ALTER TABLE gravacoes ADD COLUMN resumo TEXT DEFAULT '';
        ALTER TABLE gravacoes ADD COLUMN resumo_em TEXT DEFAULT '';
        """,
    ),
    (
        "017_lixeira",
        """
        -- A lixeira (docs/ui/05): o que foi apagado fica 30 dias com tudo
        -- que precisa para voltar - a linha e as filhas em JSON, e os
        -- arquivos movidos para data/lixeira. Ver src/lixeira.py.
        CREATE TABLE lixeira (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo       TEXT NOT NULL,
            alvo_id    TEXT NOT NULL,
            titulo     TEXT NOT NULL,
            detalhe    TEXT DEFAULT '',
            dados      TEXT NOT NULL,
            arquivos   TEXT NOT NULL DEFAULT '[]',
            apagado_em TEXT NOT NULL
        );
        CREATE INDEX idx_lixeira_apagado ON lixeira(apagado_em);
        """,
    ),
    (
        "018_contextos",
        """
        -- O que o escritorio ensinou ao assistente com as proprias palavras
        -- (docs/ui/03-telas-desktop.md, A13 > Aprendizado). Poucas linhas que
        -- valem em toda pergunta, ao contrario do Acervo, onde a busca
        -- escolhe o trecho. Ver src/contextos.py.
        CREATE TABLE contextos (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo    TEXT NOT NULL,
            texto     TEXT NOT NULL,
            gaveta    TEXT NOT NULL DEFAULT 'Regras de redação',
            criado_em TEXT NOT NULL
        );
        """,
    ),
    (
        "019_conhecimento",
        """
        -- A camada de inteligencia de documentos (legal-document/v0): o que ja
        -- foi entendido de cada documento, para nao entender de novo a cada
        -- pergunta. O metadata mora em data/conhecimento; estas tabelas sao o
        -- espelho para achar rapido. Ver src/inteligencia/.
        CREATE TABLE meta_documentos (
            id            TEXT PRIMARY KEY,
            titulo        TEXT NOT NULL DEFAULT '',
            caminho       TEXT NOT NULL DEFAULT '',
            versao_atual  TEXT NOT NULL DEFAULT '',
            criado_em     TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        );
        CREATE INDEX idx_meta_doc_caminho ON meta_documentos(caminho);

        -- Uma versao por conteudo: o sha256 e que decide. A anterior fica,
        -- porque e ela que sustenta as citacoes ja escritas.
        CREATE TABLE meta_versoes (
            id           TEXT PRIMARY KEY,
            documento_id TEXT NOT NULL REFERENCES meta_documentos(id) ON DELETE CASCADE,
            sha256       TEXT NOT NULL,
            sha1         TEXT DEFAULT '',
            caminho      TEXT DEFAULT '',
            mtime        TEXT DEFAULT '',
            mime         TEXT DEFAULT '',
            paginas      INTEGER DEFAULT 0,
            caracteres   INTEGER DEFAULT 0,
            criado_em    TEXT NOT NULL
        );
        CREATE INDEX idx_meta_versao_sha ON meta_versoes(sha256);
        CREATE INDEX idx_meta_versao_sha1 ON meta_versoes(sha1);
        CREATE INDEX idx_meta_versao_doc ON meta_versoes(documento_id);

        -- Quem produziu cada secao, com que modelo e em que versao de prompt:
        -- trocar o extrator marca so a secao dele como velha.
        CREATE TABLE meta_secoes (
            versao_id       TEXT NOT NULL REFERENCES meta_versoes(id) ON DELETE CASCADE,
            secao           TEXT NOT NULL,
            extrator        TEXT DEFAULT '',
            modelo          TEXT DEFAULT '',
            digest          TEXT DEFAULT '',
            prompt_versao   TEXT DEFAULT '',
            esquema_versao  TEXT DEFAULT '',
            estado          TEXT NOT NULL DEFAULT 'missing',
            itens           INTEGER DEFAULT 0,
            nao_verificados INTEGER DEFAULT 0,
            ms              INTEGER DEFAULT 0,
            quando          TEXT DEFAULT '',
            PRIMARY KEY (versao_id, secao)
        );

        -- Os fatos conferidos, um por linha: e daqui que sai a resposta de
        -- nivel 0, sem abrir o documento.
        CREATE TABLE meta_fatos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            versao_id    TEXT NOT NULL REFERENCES meta_versoes(id) ON DELETE CASCADE,
            documento_id TEXT NOT NULL DEFAULT '',
            secao        TEXT NOT NULL,
            item_id      TEXT NOT NULL DEFAULT '',
            chave        TEXT NOT NULL DEFAULT '',
            valor        TEXT NOT NULL DEFAULT '',
            mostrar      TEXT NOT NULL DEFAULT '',
            numero       REAL,
            pagina       INTEGER,
            verificado   INTEGER NOT NULL DEFAULT 0,
            certeza      TEXT DEFAULT ''
        );
        CREATE INDEX idx_meta_fato_busca ON meta_fatos(secao, chave, verificado);
        CREATE INDEX idx_meta_fato_versao ON meta_fatos(versao_id);
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
