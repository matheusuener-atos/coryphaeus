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

O que nao se encaixou com clareza numa linha da tabela do contrato ficou
bloqueado, num grupo proprio no fim, e esta listado no PROGRESSO para
revisao: financeiro, relatorios, foco, servicos (gravar), gravacoes (gravar),
upload de arquivo, importar para o editor, apoio.
"""

from __future__ import annotations

PUBLICO = "publico"
PERMITIDO = "permitido"
PROPOR = "propor"
TITULAR = "titular"
DOWNLOAD = "download"
BLOQUEADO = "bloqueado"
POLITICAS = (PUBLICO, PERMITIDO, PROPOR, TITULAR, DOWNLOAD, BLOQUEADO)

MENSAGEM_BLOQUEADA = "Disponível só no computador do escritório"

# Aprovar de fora (R3). O que so se faz no computador do escritorio nao se
# aprova de fora nem pelo titular: aprovar ali seria fazer por tabela o que a
# tabela proibe (mover, apagar, exportar em lote, assinar).
ACOES_SO_NO_ESCRITORIO = {"organizar.mover", "acervo.apagar", "acervo.exportar",
                          "assinatura.assinar", "assinatura.lote"}
# E o que sai desta maquina pede o codigo do autenticador de novo: sessao
# roubada nao manda e-mail nem documento para fora.
ACOES_QUE_SAEM = {"correio.enviar", "google.drive.enviar"}

# O que conta como "abriu um documento" em quem acessou (R8): ver o documento
# do editor, a pagina de um arquivo do Acervo e o trecho citado.
ROTAS_DE_VER_DOCUMENTO = {("GET", "/api/documentos/{id_}"), ("GET", "/api/documentos/{id_}/pagina"),
                          ("GET", "/api/biblioteca/pagina"), ("GET", "/api/arquivos/pagina"),
                          ("POST", "/api/biblioteca/citacao")}

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
          "POST /api/acesso/google/iniciar", "GET /api/acesso/google/retorno")

# Sem sessao, de fora, so isto passa - a tela de entrar e o que ELA carrega
# (acesso-remoto/v0, R2). O resto da casca espera o login: toda rota /api/*
# responde 401, e toda outra pagina e a tela de entrar.
SEM_SESSAO = {("GET", "/"), ("GET", "/fontes.css"), ("GET", "/css/00-tokens.css"),
              ("GET", "/img/paulus-logo.png"), ("GET", "/img/paulus-icone.svg"), ("GET", "/favicon.ico"),
              ("GET", "/api/acesso/entrar/config"), ("POST", "/api/acesso/entrar"),
              ("POST", "/api/acesso/entrar/codigo"),
              # entrar com o Google (E3a): ir ao Google e voltar dele
              ("POST", "/api/acesso/google/iniciar"), ("GET", "/api/acesso/google/retorno")}


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
          "GET /api/preferencias", "GET /marca/{tipo}.png", "GET /api/publico/{qual}",
          # conversas
          "GET /api/trabalhos", "POST /api/trabalhos", "GET /api/trabalhos/{id_}",
          "POST /api/trabalhos/{id_}/renomear", "POST /api/trabalhos/{id_}/grupo", "POST /api/grupos/renomear",
          "POST /api/trabalhos/{id_}/duplicar", "GET /api/agora", "DELETE /api/trabalhos/{id_}",
          "POST /api/trabalhos/{id_}/parar", "POST /api/trabalhos/{id_}/perguntar",
          "POST /api/buscar-agora",
          # o acervo: ver, buscar, o trecho citado, a pagina
          "GET /api/documentos-abertos", "GET /api/biblioteca", "POST /api/biblioteca/citacao",
          "GET /api/biblioteca/pagina", "POST /api/biblioteca/fixar", "POST /api/biblioteca/analisar",
          "GET /api/acervo/pastas", "GET /api/acervo/fora", "GET /api/acervo/versao", "GET /api/documents",
          "GET /api/arquivos/pagina",
          # leis: consulta
          "GET /api/leis", "GET /api/leis/procurar", "GET /api/leis/artigo",
          # agenda, tarefas, cadastros: ver (propor esta mais abaixo)
          "GET /api/agenda", "GET /api/agenda/dia", "GET /api/agenda/livres", "GET /api/google",
          "POST /api/google/sincronizar",
          "GET /api/cadastros", "GET /api/cadastros/sugestoes", "POST /api/cadastros/levantamento",
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
          "POST /api/email/anexos/conferir", "POST /api/email/rascunho", "POST /api/email/previa",
          "POST /api/email/enviar", "GET /api/email/envios", "GET /api/email/anexaveis",
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
          "GET /api/vinculo", "POST /api/vinculo/entrar", "POST /api/vinculo/cancelar", "POST /api/vinculo/codigo",
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
          "GET /api/relatorios", "GET /api/relatorios/acoes", "POST /api/relatorios/parecer", "GET /api/relatorios/pdf",
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
          "POST /api/apoio/pix", "POST /api/apoio/pix/recuperar", "GET /api/apoio/pix/{id_}",
          "GET /api/apoio/assinatura/{id_}", "POST /api/apoio/extrato", "POST /api/apoio/assinatura/{id_}/valor",
          "POST /api/apoio/assinatura/{id_}/interromper", "POST /api/apoio/assinatura")


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
