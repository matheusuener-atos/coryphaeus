"""
O que cada rota permite a quem esta de fora (R3).

O registro e central, e nao um decorador espalhado pelas 10 mil linhas do
api.py, por dois motivos: a tabela inteira cabe numa leitura, para revisar; e
`tests/test_r3_permissoes.py` percorre `app.routes` e falha se alguma rota nao
estiver aqui. **Rota sem politica declarada e bloqueada para quem esta de
fora** - rota nova nasce fechada ate alguem abri-la de proposito.

As politicas:

    publico    os arquivos da casca (paginas, scripts, folhas, imagens) e o
               login. Sem sessao, desses so passa o que a TELA DE ENTRAR
               carrega (SEM_SESSAO, abaixo); com sessao, tudo
    permitido  qualquer pessoa com sessao
    propor     ver e livre; o que grava vira pedido na fila de Aprovacoes, e
               so acontece depois do sim de quem pode (acesso-remoto/v0, §5:
               agenda, tarefas e cadastros)
    titular    so o papel titular
    download   qualquer pessoa com sessao, um arquivo por requisicao, e
               cada um fica registrado em "quem acessou" (R8)
    bloqueado  "disponivel so no computador do escritorio"
    cliente    a Area do cliente (src/area_cliente.py): sessao propria do
               cliente, conferida pela PortaDoCliente - nunca a do escritorio

O que nao se encaixou com clareza numa linha da tabela do contrato ficou
bloqueado, num grupo proprio no fim, e esta listado no PROGRESSO para
revisao: financeiro, relatorios, foco, servicos (gravar), gravacoes (gravar),
upload de arquivo, importar para o editor.
"""

from __future__ import annotations

PUBLICO = "publico"
PERMITIDO = "permitido"
PROPOR = "propor"
TITULAR = "titular"
DOWNLOAD = "download"
BLOQUEADO = "bloqueado"
CLIENTE = "cliente"
POLITICAS = (PUBLICO, PERMITIDO, PROPOR, TITULAR, DOWNLOAD, BLOQUEADO, CLIENTE)

MENSAGEM_BLOQUEADA = "Disponível só no computador do escritório"

# Aprovar de fora (R3). O que so se faz no computador do escritorio nao se
# aprova de fora nem pelo titular: aprovar ali seria fazer por tabela o que a
# tabela proibe (mover, apagar, exportar em lote, assinar).
ACOES_SO_NO_ESCRITORIO = {"organizar.mover", "acervo.apagar", "acervo.exportar",
                          "assinatura.assinar", "assinatura.lote",
                          # N15: o sim que manda a pergunta a nuvem.
                          "nuvem.enviar"}
# E o que sai desta maquina pede o codigo do autenticador de novo: sessao
# roubada nao manda e-mail nem documento para fora.
ACOES_QUE_SAEM = {"correio.enviar", "google.drive.enviar",
                  # N4-N5: a nota fiscal vai ao Sistema Nacional (emitir, cancelar, substituir).
                  "nfse.emitir", "nfse.cancelar", "nfse.substituir"}

# O que conta como "abriu um documento" em quem acessou (R8): ver o documento
# do editor, a pagina de um arquivo do Acervo e o trecho citado.
ROTAS_DE_VER_DOCUMENTO = {("GET", "/api/documentos/{id_}"), ("GET", "/api/documentos/{id_}/pagina"),
                          ("GET", "/api/biblioteca/pagina"), ("GET", "/api/arquivos/pagina"),
                          ("POST", "/api/biblioteca/citacao"), ("POST", "/api/biblioteca/leitura"),
                          ("POST", "/api/biblioteca/planilha")}

# (metodo, caminho da rota como esta no app) -> politica. Rota que nao esta
# aqui e BLOQUEADO.
REGISTRO: dict[tuple[str, str], str] = {}


def _declarar(politica: str, *rotas: str) -> None:
    for r in rotas:
        metodo, caminho = r.split(" ", 1)
        antes = REGISTRO.get((metodo, caminho))
        if antes and antes != politica:
            raise ValueError(f"{r} declarada duas vezes: {antes} e {politica}")
        REGISTRO[(metodo, caminho)] = politica


# --- a casca do programa e o login
_declarar(PUBLICO,
          "GET /", "GET /css/{arquivo}", "GET /js/{arquivo}", "GET /img/{arquivo}", "GET /img/marcas/{arquivo}",
          "GET /fontes.css", "GET /fontes/{arquivo}", "GET /favicon.ico",
          "GET /api/acesso/eu", "GET /api/acesso/entrar/config", "POST /api/acesso/entrar",
          "POST /api/acesso/entrar/codigo",
          # o convite (E4): quem foi convidado ainda nao tem conta
          "GET /api/acesso/convite/{codigo}", "POST /api/acesso/convite/{codigo}/aceitar",
          "POST /api/acesso/convite/{codigo}/confirmar", "GET /api/acesso/convite/{codigo}/google",
          # entrar com o Google (E3a)
          "POST /api/acesso/google/iniciar", "GET /api/acesso/google/retorno",
          # a frase das telas de entrar (src/saudacao.py): so a hora, o dia e o calendario
          "GET /api/saudacao/entrada")

# Sem sessao, de fora, so isto passa - a tela de entrar e o que ELA carrega
# (acesso-remoto/v0, R2). O resto da casca espera o login: toda rota /api/*
# responde 401, e toda outra pagina e a tela de entrar.
SEM_SESSAO = {("GET", "/"), ("GET", "/fontes.css"), ("GET", "/css/00-tokens.css"),
              ("GET", "/img/paulus-logo.png"), ("GET", "/img/paulus-icone.svg"), ("GET", "/favicon.ico"),
              ("GET", "/api/acesso/entrar/config"), ("POST", "/api/acesso/entrar"),
              ("POST", "/api/acesso/entrar/codigo"),
              # entrar com o Google (E3a): ir ao Google e voltar dele
              ("POST", "/api/acesso/google/iniciar"), ("GET", "/api/acesso/google/retorno"),
              # "Paulus está te esperando." e a frase de baixo (js/entrada-saudacao.js)
              ("GET", "/api/saudacao/entrada"), ("GET", "/js/entrada-saudacao.js")}


# O que a pagina do cliente carrega antes de ele entrar (frontend/cliente.html).
ESTATICOS_DO_CLIENTE = {("GET", "/css/cliente.css"), ("GET", "/js/cliente.js"), ("GET", "/fontes.css"),
                        ("GET", "/favicon.ico"), ("GET", "/img/paulus-logo.png")}


def caminho_do_cliente(caminho: str) -> bool:
    """/cliente/<link> (a pagina) e /api/cliente/* - a Area do cliente."""
    if caminho.startswith("/api/cliente/"):
        return True
    resto = caminho[len("/cliente/"):] if caminho.startswith("/cliente/") else ""
    return bool(resto) and "/" not in resto


def pagina_do_convite(caminho: str) -> bool:
    """/convite/<codigo>: a pagina que o convidado abre (E4, convites.py)."""
    resto = caminho[len("/convite/"):] if caminho.startswith("/convite/") else ""
    return bool(resto) and "/" not in resto


def api_do_convite(metodo: str, caminho: str) -> bool:
    """As tres rotas do convite passam sem sessao: ver, aceitar (senha) e confirmar (o codigo)."""
    if not caminho.startswith("/api/acesso/convite/"):
        return False
    partes = caminho[len("/api/acesso/convite/"):].split("/")
    if metodo == "GET":
        return bool(partes[0]) and (len(partes) == 1 or (len(partes) == 2 and partes[1] == "google"))
    return metodo == "POST" and len(partes) == 2 and bool(partes[0]) and partes[1] in ("aceitar", "confirmar")


def estatico_da_entrada(metodo: str, caminho: str) -> bool:
    """As fontes da tela de entrar (um arquivo por familia e peso)."""
    return metodo == "GET" and caminho.startswith("/fontes/") and "/" not in caminho[len("/fontes/"):]


# --- trocar a propria senha e encerrar as proprias sessoes, de fora: so o
# titular, e a rota pede o codigo do autenticador de novo (R2)
_declarar(TITULAR, "POST /api/acesso/minha-senha", "POST /api/acesso/minhas-sessoes/encerrar")

# --- conversar, perguntar, buscar; ver documento e o trecho citado
_declarar(PERMITIDO,
          "POST /api/acesso/sair",
          "GET /api/status", "GET /api/destinos", "GET /api/novidades", "GET /api/habilidades",
          "GET /api/preferencias", "GET /marca/{tipo}.png",
          # conversas
          "GET /api/trabalhos", "POST /api/trabalhos", "GET /api/trabalhos/{id_}",
          "POST /api/trabalhos/{id_}/renomear", "POST /api/trabalhos/{id_}/grupo", "POST /api/grupos/renomear",
          "POST /api/trabalhos/{id_}/duplicar", "GET /api/agora", "DELETE /api/trabalhos/{id_}",
          "POST /api/trabalhos/{id_}/parar", "POST /api/trabalhos/{id_}/perguntar",
          # C1: a inscricao na resposta que roda sem a janela (src/execucoes.py).
          "GET /api/execucoes/{id_}/eventos", "GET /api/trabalhos/{id_}/execucao",
          # C3: o escopo de cada conversa e a busca no texto delas (src/rotas_conversa.py).
          "POST /api/trabalhos/{id_}/escopo", "GET /api/conversas/buscar",
          # T1: a saudacao da tela inicial (src/saudacao.py).
          "GET /api/saudacao",
          # A2: qual agente a proxima pergunta usaria (so regra, sem modelo).
          "GET /api/agentes/sugerir",
          # C5: as outras chamadas de IA como execucao (src/ia_em_fundo.py).
          # Cada tipo chama a rota de antes, com a politica dela conferida aqui:
          # parecer do Financeiro e e-mail so no escritorio (ver abaixo).
          "POST /api/execucoes/{id_}/parar",
          "POST /api/buscar-agora",
          # o acervo: ver, buscar, o trecho citado, a pagina
          "GET /api/documentos-abertos", "GET /api/biblioteca", "POST /api/biblioteca/citacao",
          # T3: a lupa do visor ao lado da conversa.
          "POST /api/biblioteca/procurar-no-documento", "POST /api/biblioteca/leitura", "POST /api/biblioteca/planilha",
          "GET /api/biblioteca/pagina", "POST /api/biblioteca/fixar", "POST /api/biblioteca/analisar",
          "GET /api/acervo/pastas", "GET /api/acervo/fora", "GET /api/acervo/versao", "GET /api/documents",
          "GET /api/arquivos/pagina",
          # leis: consulta
          "GET /api/leis", "GET /api/leis/procurar", "GET /api/leis/artigo",
          # agenda, tarefas, cadastros: ver (propor esta mais abaixo)
          "GET /api/agenda", "GET /api/agenda/dia", "GET /api/agenda/livres", "GET /api/google",
          "POST /api/google/sincronizar",
          "GET /api/cadastros", "GET /api/cadastros/sugestoes", "POST /api/cadastros/levantamento",
          # o CNPJ digitado na ficha: os dados públicos da Receita (src/cnpj_receita.py)
          "GET /api/cnpj/{cnpj}",
          "GET /api/tarefas", "GET /api/tarefas/sugestoes", "GET /api/tarefas/{id_}/vinculos",
          # a fila: ver (aprovar e do titular)
          "GET /api/aprovacoes",
          # o editor e a planilha: redigir e salvar rascunho versionado
          "GET /api/documentos", "POST /api/documentos", "GET /api/documentos/modelos", "POST /api/documentos/modelos",
          "GET /api/documentos/{id_}", "POST /api/documentos/{id_}", "GET /api/documentos/{id_}/versoes",
          "GET /api/documentos/{id_}/comparar", "POST /api/documentos/{id_}/notas", "POST /api/documentos/{id_}/comentar",
          "POST /api/documentos/{id_}/comentarios", "POST /api/documentos/{id_}/comentarios/{comentario_id}/resolver",
          "DELETE /api/documentos/{id_}/comentarios/{comentario_id}", "POST /api/documentos/{id_}/alteracoes",
          "POST /api/documentos/{id_}/restaurar", "GET /api/documentos/{id_}/pagina",
          "POST /api/documentos/{id_}/paginacao", "POST /api/documentos/{id_}/formato",
          "POST /api/documentos/{id_}/folha/sugerir", "GET /api/documentos/{id_}/conferir",
          "POST /api/documentos/{id_}/clausulas", "GET /api/documentos/{id_}/conferir-clausulas",
          "GET /api/redacao/qualificacao", "POST /api/documentos/{id_}/assistente",
          "GET /api/planilha/{id_}", "POST /api/planilha/{id_}/celula", "POST /api/planilha/{id_}/faixa",
          "POST /api/planilha/{id_}/grafico", "POST /api/planilha/{id_}/lote", "POST /api/planilha/{id_}/estrutura",
          "POST /api/planilha/{id_}/layout", "POST /api/planilha/{id_}/mesclar", "POST /api/planilha/{id_}/congelar",
          "POST /api/planilha/{id_}/selecao", "POST /api/planilha/{id_}/ordenar", "POST /api/planilha/{id_}/filtrar",
          "POST /api/planilha/{id_}/aba", "DELETE /api/planilha/{id_}/aba/{indice}", "POST /api/planilha/{id_}/trazer",
          "POST /api/planilha/{id_}/importar", "POST /api/planilha/{id_}/assistente",
          # e-mail: usar o que ja esta configurado (enviar vai sempre pela fila)
          "GET /api/email/contas", "GET /api/email/caixa", "GET /api/email/mensagem", "POST /api/email/arquivar",
          "POST /api/email/estrela", "POST /api/email/excluir", "POST /api/email/marcar",
          "POST /api/email/caixa/resumo", "GET /api/email/caixa/resumo", "POST /api/email/contexto",
          "GET /api/email/contexto", "POST /api/email/reescrever", "POST /api/email/traduzir",
          "POST /api/email/anexos/conferir", "POST /api/email/anexos/encaminhar", "POST /api/email/rascunho", "POST /api/email/previa",
          "POST /api/email/enviar", "GET /api/email/envios", "GET /api/email/anexaveis",
          # o e-mail aberto e o rascunho na conversa (src/email_pela_conversa.py)
          "GET /api/email/conversa/rascunho", "POST /api/email/conversa/rascunho", "PUT /api/email/conversa/rascunho",
          "POST /api/email/conversa/perguntar", "POST /api/email/conversa/proxima",
          # a ficha aberta na coluna: a frase que corrige um campo (so le)
          "POST /api/fichas/corrigir",
          # Google: enviar ao Drive ja e pedido na fila
          "POST /api/google/drive/enviar",
          # a busca geral (Ctrl+K): filtra pelos modulos que a pessoa ve
          "GET /api/busca",
          # servicos: ver e conversar sobre eles
          "GET /api/servicos", "GET /api/servicos/{id_}", "GET /api/servicos/{id_}/horas", "POST /api/servicos/{id_}/resumo",
          "POST /api/servicos/{id_}/conversar",
          # gravacoes: ver
          "GET /api/gravacoes", "GET /api/gravacoes/{id_}", "GET /api/gravacoes/{id_}/audio/nome")

# --- agenda, tarefas e cadastros: propor. Nada grava direto; vira pedido na
# fila de Aprovacoes, e o sim de quem pode (a janela local ou o titular)
# executa exatamente o pedido guardado.
_declarar(PROPOR,
          "POST /api/agenda", "DELETE /api/agenda/{id_}", "POST /api/agenda/nota", "POST /api/agenda/{id_}/meet",
          "POST /api/cadastros/sugestoes/ignorar", "POST /api/cadastros/sugestoes/desfazer", "POST /api/cadastros",
          "POST /api/cadastros/{id_}/vincular", "DELETE /api/cadastros/{id_}",
          "POST /api/tarefas", "POST /api/tarefas/{id_}/concluir", "POST /api/tarefas/{id_}/importante",
          "POST /api/tarefas/{id_}/meu-dia", "POST /api/tarefas/{id_}/etapas", "POST /api/etapas/{id_}",
          "POST /api/tarefas/{id_}/vincular", "DELETE /api/vinculos/{id_}", "DELETE /api/tarefas/{id_}",
          # o que a conversa entendeu e a pessoa confirmou: compromisso, tarefa, ficha
          "POST /api/trabalhos/{id_}/fazer",
          # corrigir um fato do cartao do documento (I9): grava no metadata
          "POST /api/ajuda/corrigir")

# --- a ajuda sem pergunta (I9): o cartao do documento e propor os prazos em
# Aprovacoes - propor nao grava nada na Agenda.
_declarar(PERMITIDO, "GET /api/ajuda/documento", "POST /api/ajuda/prazos")

# --- aprovar: so o titular (e a rota confere, item por item, o que nao pode
# ser aprovado de fora e o que pede o codigo do autenticador de novo)
_declarar(TITULAR, "POST /api/aprovacoes/decidir")

# --- baixar UM documento: sempre registrado em "quem acessou"
_declarar(DOWNLOAD,
          "GET /api/trabalhos/{id_}/exportar", "GET /api/arquivos/baixar", "GET /api/documentos/{id_}/pdf",
          "POST /api/documentos/{id_}/pdf", "GET /api/documentos/{id_}/docx", "GET /api/planilha/{id_}/exportar",
          "GET /api/email/anexo", "GET /api/gravacoes/{id_}/audio", "GET /api/gravacoes/{id_}/transcricao.docx")

# --- o resto e bloqueado de fora, e declarado assim de proposito.
_declarar(BLOQUEADO,
          # a documentacao automatica do FastAPI: o mapa inteiro da API
          "GET /openapi.json", "GET /api/docs", "GET /docs/oauth2-redirect", "GET /redoc",
          # maquina, modelos, atualizacao, calibracao
          "POST /api/cache/limpar", "POST /api/ollama/ligar", "POST /api/ollama/puxar", "GET /api/ollama/puxar",
          "GET /api/atualizacao", "POST /api/atualizacao/verificar", "POST /api/atualizacao/baixar",
          "POST /api/atualizacao/cancelar", "POST /api/atualizacao/instalar", "POST /api/modelos/usar",
          "GET /api/modelos", "POST /api/modelos/baixar", "GET /api/modelos/baixar", "POST /api/modelos/cancelar",
          "POST /api/modelos/remover", "POST /api/modelos/padrao", "POST /api/modelos/tarefa", "POST /api/modelos/medir",
          "GET /api/calibracao", "POST /api/calibracao", "GET /api/maquina", "POST /api/maquina/testar",
          "GET /api/recursos", "POST /api/config", "GET /api/voz", "POST /api/voz/baixar", "POST /api/voz/modelo",
          # configuracoes, aprendizado, marca, avisos, o proprio acesso de fora
          "POST /api/preferencias", "GET /api/contextos", "POST /api/contextos", "POST /api/contextos/ler",
          "DELETE /api/contextos/{id_}", "GET /api/material", "POST /api/material", "DELETE /api/material/{id_}",
          "POST /api/material/{id_}/abrir", "GET /api/inteligencia", "POST /api/marca/{tipo}", "DELETE /api/marca/{tipo}",
          "POST /api/habilidades/recarregar", "POST /api/habilidades/{id_}", "GET /api/avisos", "POST /api/avisos/teste",
          "POST /api/leis/importar", "POST /api/leis/importar-pasta", "DELETE /api/leis/{codigo}",
          "GET /api/acesso/contas", "POST /api/acesso/contas", "PATCH /api/acesso/contas/{conta_id}",
          "DELETE /api/acesso/contas/{conta_id}", "POST /api/acesso/contas/{conta_id}/senha",
          "POST /api/acesso/contas/{conta_id}/autenticador/confirmar",
          "POST /api/acesso/contas/{conta_id}/autenticador/refazer", "POST /api/acesso/contas/{conta_id}/recuperacao",
          "POST /api/acesso/sessoes/encerrar", "GET /api/acesso/permissoes/modulos",
          "PUT /api/acesso/contas/{conta_id}/permissoes", "PUT /api/acesso/contas/{conta_id}/seguranca",
          "PUT /api/acesso/seguranca-padrao",
          # o vinculo do PAULUS a conta Google (E5): so na janela do servidor
          "GET /api/vinculo", "POST /api/vinculo/entrar", "POST /api/vinculo/cancelar", "POST /api/vinculo/codigo", "POST /api/vinculo/esquecer-codigo",
          "POST /api/vinculo/travar", "POST /api/vinculo/manter-aberto", "POST /api/vinculo/desvincular",
          "POST /api/vinculo/sem-internet", "POST /api/vinculo/sem-internet/ligar",
          "POST /api/vinculo/sem-internet/confirmar", "POST /api/vinculo/sem-internet/desligar",
          "GET /api/acesso/convites", "POST /api/acesso/convites", "DELETE /api/acesso/convites/{id_}",
          "GET /api/acesso/tunel", "POST /api/acesso/tunel/conectar", "POST /api/acesso/tunel/cancelar",
          "POST /api/acesso/tunel/ligar", "POST /api/acesso/tunel/porta", "GET /api/acesso/tunel/disponivel",
          "GET /api/acesso/tunel/sugestao",
          "POST /api/acesso/tunel/remover", "GET /api/acesso/auditoria", "GET /api/acesso/auditoria/pdf",
          "POST /api/acesso/energia/abrir-com-windows",
          # o menu do botao direito no Explorer deste computador
          "GET /api/explorer", "POST /api/explorer",
          # prazos e publicacoes do DJEN (src/prazos.py, src/publicacoes.py): por ora, so no servidor
          "POST /api/prazos/calcular", "GET /api/prazos/feriados", "POST /api/prazos/feriados",
          "GET /api/publicacoes", "POST /api/publicacoes/configurar", "POST /api/publicacoes/consultar",
          "POST /api/publicacoes/{id_}/lida", "POST /api/publicacoes/{id_}/prazo",
          # a saude do PAULUS e o diagnostico (src/saude.py)
          "GET /api/saude", "GET /api/saude/diagnostico",
          # backup e restauracao (src/backup.py): so na janela do servidor
          "GET /api/backup", "POST /api/backup/configurar", "POST /api/backup/agora", "POST /api/backup/listar",
          "POST /api/backup/restaurar", "POST /api/backup/restaurar/cancelar", "POST /api/backup/reabrir",
          # mover, organizar, apagar, exportar em lote, lixeira
          "POST /api/biblioteca/lote/mover", "POST /api/biblioteca/lote/apagar", "POST /api/biblioteca/lote/exportar",
          "POST /api/biblioteca/remover", "POST /api/acervo/pastas", "POST /api/acervo/pastas/tirar",
          "POST /api/acervo/tirar", "POST /api/acervo/devolver", "POST /api/reindex",
          "GET /api/organizar/opcoes", "GET /api/pastas", "POST /api/organizar/cancelar", "POST /api/organizar/escanear",
          "POST /api/organizar/classificar", "POST /api/organizar/so-classificar", "POST /api/organizar/plano",
          "POST /api/organizar/aplicar", "GET /api/organizar/ultima", "POST /api/organizar/desfazer",
          "GET /api/lixeira", "POST /api/lixeira/esvaziar", "POST /api/lixeira/{id_}/restaurar", "DELETE /api/lixeira/{id_}",
          "DELETE /api/documentos/{id_}", "DELETE /api/documentos/modelos/{id_}",
          # o que abre programa ou janela no Windows local, ou le caminho do disco
          "POST /api/biblioteca/abrir-pasta", "POST /api/externo/perguntar", "POST /api/externo/mostrar",
          "POST /api/anexar/caminhos", "POST /api/arquivos/abrir", "POST /api/arquivos/salvar",
          "POST /api/trabalhos/{id_}/exportar", "GET /api/impressoras", "POST /api/documentos/{id_}/imprimir",
          "POST /api/certificado/windows/abrir",
          # assinar e o certificado
          "GET /api/certificado", "GET /api/certificado/windows", "POST /api/certificado/windows/usar",
          "POST /api/certificado/arquivo", "POST /api/certificado/senha", "POST /api/certificado/esquecer",
          "DELETE /api/certificado", "POST /api/certificado/opcoes", "POST /api/certificado/selo",
          "POST /api/certificado/selo/imagem", "POST /api/certificado/selo/restaurar",
          "DELETE /api/certificado/selo/{campo}", "GET /api/certificado/selo/{campo}.png", "POST /api/certificado/teste",
          "GET /api/assinar/documento", "GET /api/assinar/pagina", "GET /api/assinar/pdfs", "POST /api/assinar",
          "POST /api/assinar/lote", "POST /api/assinaturas/conformidade", "GET /api/assinar/baixar",
          "GET /api/assinar/zip", "POST /api/assinar/zip", "POST /api/assinar/copiar", "GET /api/assinaturas",
          "GET /api/assinaturas/conferir",
          # e-mail e Google: configurar contas e conexoes
          "POST /api/email/detectar", "POST /api/email/testar", "POST /api/email/contas", "POST /api/email/contas/senha",
          "POST /api/email/contas/{id_}/usar", "DELETE /api/email/contas/{id_}", "POST /api/email/esquecer-senhas",
          "GET /api/email/oauth", "POST /api/email/oauth/entrar", "GET /api/email/oauth/andamento",
          "POST /api/email/oauth/cancelar", "POST /api/email/oauth/reabrir", "POST /api/google/conectar",
          "POST /api/google/preferencias",
          # o Drive pela internet: escolher pastas do Drive do escritorio
          "GET /api/google/drive/navegar", "GET /api/google/drive/copias", "POST /api/google/drive/copias",
          "POST /api/google/drive/copias/sincronizar", "POST /api/google/drive/copias/tirar",
          "GET /api/conexoes", "POST /api/conexoes/abrir", "POST /api/conexoes/mensagem", "POST /api/conexoes/sessao/apagar",
          "GET /api/conexoes/contatos",
          # nao se encaixam com clareza numa linha da tabela: bloqueadas, e
          # listadas no PROGRESSO para o usuario revisar
          "POST /api/upload", "POST /api/documentos/importar", "POST /api/documentos/{id_}/biblioteca",
          "POST /api/email/anexo/guardar",
          "GET /api/financeiro/folha", "POST /api/financeiro/folha/montar", "POST /api/financeiro/folha/pagar",
          "POST /api/financeiro/folha/recibos", "GET /api/financeiro/papeis", "POST /api/financeiro/papeis",
          "DELETE /api/financeiro/papeis/{id_}", "POST /api/financeiro/papeis/{id_}/pago", "GET /api/financeiro/fechamento",
          "POST /api/financeiro/comprovantes", "DELETE /api/financeiro/comprovantes/{id_}", "POST /api/financeiro/exportar",
          "GET /api/financeiro/exportar", "GET /api/financeiro", "GET /api/financeiro/lancamentos",
          "GET /api/financeiro/extrato", "POST /api/financeiro/banco", "POST /api/financeiro/banco/aplicar",
          "POST /api/financeiro/lancamentos", "POST /api/financeiro/lancamentos/{id_}/liquidar",
          "POST /api/financeiro/lancamentos/{id_}/reabrir", "DELETE /api/financeiro/lancamentos/{id_}",
          "POST /api/financeiro/lancamentos/{id_}/comprovante", "DELETE /api/financeiro/comprovante/{id_}",
          "POST /api/financeiro/cobrar",
          # o lancamento feito pela conversa (src/lancamentos_pela_conversa.py)
          "POST /api/financeiro/lancar-pela-conversa",
          "GET /api/relatorios", "GET /api/relatorios/acoes", "POST /api/relatorios/parecer", "GET /api/relatorios/pdf",
          # o relatorio financeiro do mes pela conversa (src/financeiro_pela_conversa.py)
          "GET /api/relatorios/financeiro", "POST /api/relatorios/financeiro/gerar", "GET /api/relatorios/financeiro/arquivo",
          "POST /api/relatorios/parecer-do-mes",
          "POST /api/relatorios/pdf",
          "GET /api/bemestar", "GET /api/bemestar/semana", "POST /api/bemestar/medir", "POST /api/bemestar/ciclo",
          "POST /api/bemestar/pausa", "POST /api/bemestar/parar", "GET /api/bemestar/ciclo", "POST /api/bemestar/lembretes",
          "POST /api/bemestar/lembretes/restaurar", "POST /api/bemestar/lembretes/{id_}/feito",
          "DELETE /api/bemestar/lembretes/{id_}",
          "POST /api/servicos", "DELETE /api/servicos/{id_}", "POST /api/servicos/{id_}/anexar",
          # horas (src/horas.py): registrar e o cronometro abrem com "faz" em Servicos;
          # o valor da hora e cobrar ficam na janela do servidor
          "POST /api/servicos/{id_}/horas", "DELETE /api/servicos/{id_}/horas/{hid}",
          "POST /api/servicos/{id_}/horas/cronometro", "POST /api/servicos/{id_}/horas/valor",
          "POST /api/servicos/{id_}/horas/cobrar",
          "POST /api/servicos/{id_}/status", "POST /api/servicos/{id_}/etapas",
          "POST /api/servicos/{id_}/etapas/{indice}/editar", "POST /api/servicos/{id_}/etapas/{indice}",
          "DELETE /api/servicos/{id_}/etapas/{indice}", "POST /api/servicos/{id_}/anotacoes",
          "POST /api/servicos/{id_}/anotacoes/{indice}", "DELETE /api/servicos/{id_}/anotacoes/{indice}",
          "POST /api/servicos/{id_}/prazos/{origem}/{item_id}", "POST /api/servicos/{id_}/vincular",
          "DELETE /api/servicos/{id_}/vinculos/{sha1}",
          "POST /api/voz/ao-vivo", "POST /api/voz/ao-vivo/{sid}/audio", "POST /api/voz/ao-vivo/{sid}/fim",
          "DELETE /api/voz/ao-vivo/{sid}", "POST /api/gravacoes", "POST /api/gravacoes/{id_}/transcrever",
          "POST /api/gravacoes/{id_}/resumo", "POST /api/gravacoes/{id_}", "POST /api/gravacoes/{id_}/anotacoes",
          "POST /api/gravacoes/{id_}/anotacoes/{indice}", "DELETE /api/gravacoes/{id_}/anotacoes/{indice}",
          "DELETE /api/gravacoes/{id_}", "POST /api/gravacoes/{id_}/audio/salvar", "POST /api/gravacoes/{id_}/corrigir",
          "POST /api/gravacoes/{id_}/exportar", "POST /api/gravacoes/{id_}/marcadores",
          "DELETE /api/gravacoes/{id_}/marcadores/{indice}",
          # Pacote de telas (`Conversa - Gravando`): as sugestoes e os pontos
          # do caso enquanto a gravacao anda - gravar e coisa do escritorio.
          "POST /api/gravacoes/sugerir", "POST /api/gravacoes/pontos")

# --- a Biblioteca (src/biblioteca, docs/PROGRESSO-BIBLIOTECA.md): montar a
# biblioteca e a configuracao dela ficam na janela do servidor, como o
# material de consulta. Consultar o que ela sabe sobre um artigo e ver, como
# as leis.
_declarar(BLOQUEADO,
          "GET /api/biblioteca-juridica", "PUT /api/material/{id_}/ficha", "POST /api/leis/baixar",
          "GET /api/material/{id_}/arquivo", "GET /api/biblioteca-juridica/mapa",
          "GET /api/material/{id_}/leitura", "POST /api/biblioteca-juridica/ler",
          # o pacote .paulus-material: so na janela do servidor, e nada vai pela rede
          "POST /api/material/{id_}/autoria", "GET /api/material/{id_}/pacote", "POST /api/material/pacote",
          # o acervo que vem com o PAULUS: pôr de novo o que foi apagado
          "GET /api/biblioteca/acervo-inicial", "POST /api/biblioteca/acervo-inicial")
# Consultar vale de fora, como as leis: a súmula guardada, o processo no
# DataJud (só o número vai ao CNJ) e os endereços de busca dos tribunais.
_declarar(PERMITIDO, "GET /api/leis/anotacoes", "GET /api/biblioteca/sumulas", "POST /api/biblioteca/datajud",
          "GET /api/biblioteca/fontes")

# --- F1: a pergunta que espera na conversa (src/fila_de_todos.py). Ver,
# editar e cancelar a propria vale de fora; a rota confere o dono. A fila
# inteira (nomes e origens de todo mundo) so na janela do escritorio.
_declarar(PERMITIDO, "GET /api/trabalhos/{id_}/pendentes", "PUT /api/trabalhos/{id_}/pendentes/{pid}",
          "DELETE /api/trabalhos/{id_}/pendentes/{pid}")
_declarar(BLOQUEADO, "GET /api/fila")

# --- D1: o pacote de escrita (src/aparelho.py). As rotas conferem a sessao e a
# assinatura; o conteudo so sai para a sessao que pediu, uma vez.
# D2: o motor (a biblioteca e o trabalhador, servidos daqui), os pesos (so
# para quem pode escrever no aparelho - a rota confere) e a capacidade (so numeros).
_declarar(PERMITIDO, "GET /motor/wllama-3.6.1/{arquivo}", "GET /motor/trabalhador.js", "GET /api/aparelho/modelo",
          "GET /api/aparelho/modelo/{sha}/parte/{n}", "POST /api/aparelho/capacidade")
_declarar(PERMITIDO, "GET /api/aparelho/estado", "POST /api/aparelho/sugestao", "GET /api/aparelho/pacote/{pid}",
          "POST /api/aparelho/pacote/{pid}/devolver", "POST /api/aparelho/pacote/{pid}/abandonar",
          "POST /api/aparelho/pacote/{pid}/pedaco")
# --- L1: aprender com o uso (src/aprendizado.py). Avaliar a propria resposta vale
# de fora; o caderno de falhas e da janela do escritorio.
_declarar(PERMITIDO, "POST /api/aprendizado/avaliar", "GET /api/aprendizado/da-conversa/{trabalho_id}")
_declarar(BLOQUEADO, "GET /api/aprendizado/caderno", "POST /api/aprendizado/caderno/{id_}/caso",
          "POST /api/aprendizado/caderno/{id_}/resolver")
# --- L2: processos pelo DataJud (src/processos.py). Ver e marcar como visto vale
# de fora (so os de Servicos que a pessoa ve); acompanhar, consultar e mudar sao
# da janela do escritorio - e o que faz o numero sair para o DataJud.
_declarar(PERMITIDO, "GET /api/processos", "GET /api/processos/{id_}", "POST /api/processos/{id_}/vistos")
_declarar(BLOQUEADO, "POST /api/processos", "POST /api/processos/descobrir", "PUT /api/processos/{id_}",
          "DELETE /api/processos/{id_}", "POST /api/processos/{id_}/consultar", "POST /api/processos/acompanhar-agora")
# --- L3: partes e conflito (src/clientes.py). Mudar as partes de um Servico segue
# o modulo Servicos (o "faz" abre, pelo prefixo); a consulta de conflito e a
# visao do cliente cruzam todos os clientes do escritorio: janela do escritorio.
_declarar(BLOQUEADO, "PUT /api/servicos/{id_}/partes", "GET /api/servicos/{id_}/conflitos", "POST /api/clientes/conflitos",
          "GET /api/clientes/{cadastro_id}/visao")
# --- N3: a parte contraria sugerida pelos documentos do Servico, e a dispensa -
# como a conferencia de conflito, da janela do escritorio.
_declarar(BLOQUEADO, "GET /api/servicos/{id_}/partes/sugeridas", "POST /api/servicos/{id_}/partes/dispensar")
# --- N14: desfazer o que um agente fez sozinho - na janela do escritorio.
_declarar(BLOQUEADO, "POST /api/aprovacoes/{id_}/desfazer")
# --- N13: a jurisprudencia do STJ. Procurar e ler sao dados publicos, como as leis;
# baixar, parar e apagar mexem neste computador: janela do escritorio.
_declarar(PERMITIDO, "GET /api/jurisprudencia", "GET /api/jurisprudencia/procurar", "GET /api/jurisprudencia/acordao/{id_}")
_declarar(BLOQUEADO, "POST /api/jurisprudencia/baixar", "POST /api/jurisprudencia/parar", "DELETE /api/jurisprudencia")
# --- N15: a nuvem com a chave do escritorio - guardar a chave, ligar, liberar a
# conversa e ler o registro: tudo na janela do escritorio.
_declarar(BLOQUEADO, "GET /api/nuvem", "POST /api/nuvem/chave", "GET /api/nuvem/modelos", "DELETE /api/nuvem/chave/{provedor}",
          "POST /api/nuvem/configurar", "POST /api/trabalhos/{id_}/nuvem", "GET /api/nuvem/envios", "GET /api/nuvem/envios/{envio}")
# --- N1 (NFS-e): configuracao fiscal, certificado da nota, municipio e tabelas
# oficiais - so na janela do escritorio. De fora nao se configura tributo nem se
# usa o certificado do escritorio.
_declarar(BLOQUEADO, "GET /api/nfse", "POST /api/nfse/ligar", "POST /api/nfse/prestador",
          "POST /api/nfse/certificado", "POST /api/nfse/certificado/senha", "POST /api/nfse/certificado/remover",
          "POST /api/nfse/municipio/consultar", "GET /api/nfse/municipios", "GET /api/nfse/tabelas",
          "POST /api/nfse/tabelas/importar")
# --- N2 (NFS-e): o cartao da nota - criar, editar, conferir e descartar o rascunho, e a
# previa da DPS. Na janela do escritorio; de fora a nota nasce pela conversa (N4).
_declarar(BLOQUEADO, "GET /api/nfse/notas", "POST /api/nfse/notas", "GET /api/nfse/notas/{id_}",
          "POST /api/nfse/notas/{id_}", "GET /api/nfse/notas/{id_}/dps", "POST /api/nfse/notas/{id_}/descartar")
# --- N3 (NFS-e): atualizar a situacao pela consulta e ver a fila de envio - usam o
# certificado do escritorio: janela do escritorio.
_declarar(BLOQUEADO, "POST /api/nfse/notas/{id_}/consultar", "GET /api/nfse/fila", "POST /api/nfse/contrato/conferir")
# --- N4 (NFS-e): o fluxo - pedir aprovacao e mandar a ja aprovada, na janela do escritorio.
# De fora a nota nasce pela conversa (o /fazer e PROPOR) e se aprova em Aprovacoes (com o
# codigo do autenticador de novo: nfse.emitir esta em ACOES_QUE_SAEM).
_declarar(BLOQUEADO, "GET /api/nfse/disponivel", "POST /api/nfse/notas/{id_}/pedir-aprovacao",
          "POST /api/nfse/notas/{id_}/enviar")
# --- N5 (NFS-e): DANFSe, cancelar (vai para Aprovacoes), substituir e atualizar a situacao.
_declarar(BLOQUEADO, "GET /api/nfse/notas/{id_}/danfse", "POST /api/nfse/notas/{id_}/cancelar",
          "POST /api/nfse/notas/{id_}/substituir", "POST /api/nfse/notas/{id_}/situacao")
# --- Tela Notas fiscais (js/93-notas-fiscais.js): o XML da NFS-e emitida, para baixar.
_declarar(BLOQUEADO, "GET /api/nfse/notas/{id_}/xml")
# --- N6 (NFS-e): o relatorio do mes, a exportacao e o envio ao contador (vai para Aprovacoes).
_declarar(BLOQUEADO, "GET /api/nfse/contador", "POST /api/nfse/contador/exportar", "POST /api/nfse/contador/enviar")
# --- N7 (NFS-e): honorarios recorrentes (criam o rascunho e o pedido; nunca emitem).
_declarar(BLOQUEADO, "GET /api/nfse/recorrencias", "POST /api/nfse/recorrencias", "POST /api/nfse/recorrencias/{id_}/desligar")
# --- N8 (NFS-e): a liberacao da producao - so o titular, so na janela do escritorio.
_declarar(BLOQUEADO, "GET /api/nfse/producao", "POST /api/nfse/producao/revisado", "POST /api/nfse/teste", "GET /api/nfse/teste/clientes",
          "POST /api/nfse/producao/liberar", "POST /api/nfse/producao/voltar")
# --- V1-V7 (docs/PLANO-NUVEM.md): o termo, o sim do titular, a conta do PAULUS
# (nuvem), o plano e a recarga - tudo da janela do escritorio. De fora, so a
# situacao que a caixa da pergunta usa (sem chave, sem conta).
_declarar(BLOQUEADO, "GET /api/nuvem/termo", "POST /api/nuvem/consentimento", "POST /api/nuvem/paulus/ativar",
          "GET /api/nuvem/paulus/conta", "POST /api/nuvem/paulus/assinar", "POST /api/nuvem/paulus/plano", "GET /api/consumo", "GET /api/consumo/pessoa/{conta_id}", "POST /api/consumo/limites", "GET /api/nuvem/paulus/assinatura",
          "GET /api/consumo/extrato", "POST /api/consumo/extrato/pdf", "GET /api/consumo/extrato/arquivo",
          "POST /api/nuvem/paulus/cancelar", "POST /api/nuvem/paulus/recarga", "GET /api/nuvem/paulus/recarga/{pedido}",
          "POST /api/nuvem/paulus/adiantar", "POST /api/nuvem/paulus/desistir")
_declarar(PERMITIDO, "GET /api/nuvem/situacao")
# As NFS-e que o PAVLVS emitiu para o escritorio (src/rotas_nfse_recebidas.py):
# como Plano e consumo, so na janela do escritorio.
_declarar(BLOQUEADO, "GET /api/nfse-recebidas", "GET /api/nfse-recebidas/{id_}/pdf", "GET /api/nfse-recebidas/{id_}/xml")
# A IA faz parte da assinatura (src/plano.py): se ela esta liberada, e a frase
# de onde assinar - sem nada da conta. A tela de fora tambem precisa saber.
_declarar(PERMITIDO, "GET /api/plano")
# --- N4: o conflito guardado como pendencia - cruza todos os clientes: janela do escritorio.
_declarar(BLOQUEADO, "GET /api/conflitos", "GET /api/conflitos/{id_}", "POST /api/conflitos/{id_}/resolver",
          "POST /api/conflitos/{id_}/reabrir")
# --- L4: tarefas de varios passos (src/passos.py): criam documento, pedem em
# Aprovacoes e desfazem - por ora, so na janela do escritorio.
_declarar(BLOQUEADO, "GET /api/passos/tipos", "GET /api/passos", "POST /api/passos", "GET /api/passos/{id_}",
          "POST /api/passos/{id_}/parar", "POST /api/passos/{id_}/desfazer")
# --- L5: a Biblioteca ajudando a escrever (src/fundamentacao.py). Ler vale de fora,
# como as leis; escrever a posicao da casa e baixar do STJ sao do escritorio.
_declarar(PERMITIDO, "POST /api/biblioteca/fundamentacao", "GET /api/biblioteca/temas", "GET /api/leis/posicao",
          "GET /api/leis/posicoes")
_declarar(BLOQUEADO, "POST /api/biblioteca/temas/atualizar", "PUT /api/leis/posicao")
# --- L6: o perfil desta maquina (src/perfis.py); ligar o Vulkan mexe no Windows daqui.
_declarar(BLOQUEADO, "GET /api/maquina/perfil", "POST /api/maquina/perfil/vulkan")
# --- L8: conferir a nitidez das fotos antes de guardar (nada fica gravado), como a captura.
_declarar(PERMITIDO, "POST /api/captura/conferir")
# --- L10: a vigencia de um artigo (src/vigencia.py): leitura, como as leis.
_declarar(PERMITIDO, "GET /api/leis/vigencia")
# --- D5: o que o titular controla - so na janela do escritorio (a rota confere de novo).
_declarar(BLOQUEADO, "GET /api/aparelho/so-no-escritorio", "PUT /api/aparelho/so-no-escritorio",
          "GET /api/aparelho/relatorio")

# --- o documento fotografado pelo celular (ideia E do umbrelOS): de fora, a
# rota nao grava no Acervo - guarda a foto a parte e pede em Aprovacoes
# (src/captura.py). Na janela do escritorio, entra direto.
_declarar(PERMITIDO, "POST /api/captura")

# --- o servidor MCP das leis (ideia A do umbrelOS): as conexoes so se criam e
# revogam na janela do escritorio. O /mcp em si nem chega aqui: o porteiro o
# entrega ao src/mcp_leis.py, que recusa o que vem pelo tunel.
# --- W1: o PAVLVS no Word (src/word_suplemento.py). A janela do escritorio
# liga, instala, permite o Word deste computador e revoga: de fora, bloqueado.
# O pareamento (parear, trocar, carregou) e as rotas /api/word/s/* nem chegam
# a esta tabela - o porteiro as entrega a PortaDoWord, com token e tabela
# propria (word_suplemento.ROTAS, padrao "nega"); ficam aqui declaradas
# bloqueadas para o caso de alguem tentar pelo caminho de sempre.
_declarar(BLOQUEADO, "GET /api/word", "POST /api/word/ligar", "POST /api/word/instalar", "POST /api/word/desinstalar",
          "GET /api/word/manifesto", "POST /api/word/abrir-pasta", "GET /api/word/word-aberto", "POST /api/word/abrir",
          "POST /api/word/externo", "POST /api/word/atalhos",
          "POST /api/word/abrir-documento/{id_}", "POST /api/word/pedidos/{id_}/permitir", "POST /api/word/pedidos/{id_}/recusar",
          "DELETE /api/word/conexoes/{id_}",
          "POST /api/word/parear", "POST /api/word/parear/trocar", "POST /api/word/carregou",
          "GET /api/word/s/eu", "PUT /api/word/s/preferencias", "DELETE /api/word/s/eu")
# De fora, a pessoa conecta o Word de outro computador com a sessao dela e o
# codigo do autenticador pedido de novo (a rota confere); a lista de pedidos
# de fora volta vazia (so a janela local ve os pedidos deste computador).
_declarar(PERMITIDO, "POST /api/word/permitir-de-fora", "GET /api/word/pedidos")

_declarar(BLOQUEADO, "GET /api/mcp", "POST /api/mcp/conexoes", "DELETE /api/mcp/conexoes/{id_}",
          # ligar e desligar as chaves da Biblioteca e do umbrelOS (src/rotas_chaves.py)
          "GET /api/chaves", "POST /api/chaves")

# --- A1: os agentes do escritorio (src/rotas_agentes.py). Ver a lista, ler um
# agente e rodar os testes dele e de qualquer pessoa com sessao - no celular a
# lista e o teste funcionam. Criar, editar, ligar e importar mudam o que o
# PAULUS faz para o escritorio inteiro: so a janela local ou o titular.
_declarar(PERMITIDO, "GET /api/agentes", "GET /api/agentes/{slug}", "GET /api/agentes/{slug}/versoes/{n}",
          "POST /api/agentes/{slug}/testar")
_declarar(TITULAR, "POST /api/agentes", "PUT /api/agentes/{slug}", "POST /api/agentes/{slug}/ativar",
          "POST /api/agentes/{slug}/desativar", "POST /api/agentes/importar")

# --- T2: a Central de avisos (src/rotas_avisos.py). Ver e marcar como visto
# e de cada pessoa e nao mexe em nada do escritorio: permitido de fora. O que
# cada um recebe segue a rota de origem (quem nao ve o Financeiro nao recebe
# aviso de conta), e a acao direta chama a rota da tela de origem, com a
# politica dela.
_declarar(PERMITIDO, "GET /api/central-avisos/hoje", "GET /api/central-avisos",
          "POST /api/central-avisos/visto",
          "POST /api/central-avisos/desmarcar", "GET /api/central-avisos/historico")

# --- A3/A4: a tela de agentes (src/agentes_tela.py). As tres rotas so
# conferem e devolvem - o AGENTE.md que o formulario gravaria, a validacao do
# markdown escrito a mao e o rascunho a partir de uma conversa -, mas sao o
# comeco de criar e editar, que ficam no computador do escritorio: de fora, so
# o titular, como as rotas de gravar da A1. A medida (A4) vem na lista, que ja
# e permitida.
_declarar(TITULAR, "POST /api/agentes/formulario", "POST /api/agentes/validar",
          # T3 (`Conversa - Criar agente`): o rascunho por regra e o escrito pelo modelo.
          "POST /api/agentes/rascunho", "POST /api/agentes/rascunho/escrever", "POST /api/agentes/rascunho/mudar",
          "GET /api/agentes/da-conversa/{trabalho_id}", "GET /api/agentes/sugestao/conversa")


# --- a Area do cliente (src/area_cliente.py, docs/PLANO-AREA-CLIENTE.md)
# O cliente: sessao propria, pela PortaDoCliente.
_declarar(CLIENTE,
          "GET /cliente/{token}", "POST /api/cliente/entrar", "POST /api/cliente/codigo", "GET /api/cliente/eu",
          "POST /api/cliente/sair", "GET /api/cliente/pastas/{sid}", "GET /api/cliente/pastas/{sid}/documentos/{sha1}/pagina",
          "GET /api/cliente/pastas/{sid}/documentos/{sha1}/baixar", "POST /api/cliente/evento",
          "POST /api/cliente/pastas/{sid}/mensagens", "POST /api/cliente/pastas/{sid}/enviar",
          "POST /api/cliente/pastas/{sid}/etapas/{indice}/feita", "POST /api/cliente/pastas/{sid}/compromissos/{cid}/responder",
          "GET /api/cliente/pastas/{sid}/compromissos/{cid}/agenda")
# O escritorio, dentro da pasta: ver e livre para quem ve a pasta (a Equipe);
# mexer abre pelo nivel "faz" em Servicos (acesso/permissoes.py).
_declarar(PERMITIDO,
          "GET /api/servicos/{id_}/cliente", "GET /api/servicos/cliente/nao-lidas", "GET /api/servicos/{id_}/cliente/atividade",
          "GET /api/servicos/{id_}/como-cliente", "GET /api/servicos/{id_}/como-cliente/documentos/{sha1}/pagina")
ROTAS_DO_ESCRITORIO_NO_CLIENTE = (
    "POST /api/servicos/{id_}/cliente/compartilhar", "POST /api/servicos/{id_}/cliente/reenviar",
    "POST /api/servicos/{id_}/cliente/parar", "POST /api/servicos/{id_}/cliente/etapas/{indice}",
    "POST /api/servicos/{id_}/cliente/compromissos/{cid}", "POST /api/servicos/{id_}/cliente/documentos/{sha1}",
    "POST /api/servicos/{id_}/cliente/mensagens", "POST /api/servicos/{id_}/cliente/resumo",
    "POST /api/servicos/{id_}/cliente/resumo/sugerir")
_declarar(BLOQUEADO, *ROTAS_DO_ESCRITORIO_NO_CLIENTE)


def de(metodo: str, caminho_da_rota: str | None) -> str:
    """A politica remota de uma rota; sem declaracao, bloqueada."""
    if not caminho_da_rota:
        return BLOQUEADO
    metodo = "GET" if metodo == "HEAD" else metodo
    return REGISTRO.get((metodo, caminho_da_rota), BLOQUEADO)


def rota_de(app, scope):
    """A rota do app que atende este pedido, pelo mesmo casamento do Starlette."""
    from starlette.routing import Match

    for rota in getattr(app, "routes", []):
        try:
            casou, _ = rota.matches(scope)
        except Exception:  # noqa: BLE001 - rota que nao sabe casar nao atende
            continue
        if casou == Match.FULL:
            return rota
    return None

# --- C5: as chamadas de IA em segundo plano (src/ia_em_fundo.py). Cada tipo
# chama uma rota com politica propria (o parecer do Financeiro, o e-mail): para
# nao abrir de fora o que era do escritorio, a rota nova e so da janela local, e
# de fora a tela usa a rota de antes.
_declarar(BLOQUEADO, "POST /api/ia/{tipo}")
