# 06 — Ordem de implantação

Ordem de trabalho **da interface**. Não toca em empacotamento, build nem
fronteira HTTP: isso já está decidido fora deste pacote. O que segue é a ordem
em que as telas devem entrar para que cada etapa termine em algo utilizável.

## Fase 0 — Fundamento (bloqueia todo o resto)

1. Variáveis de `00-fundamentos.md` declaradas em um só lugar, claro e escuro,
   com o alternador gravando a escolha.
2. Fontes empacotadas localmente (`.woff2`): EB Garamond, Manrope, Fira Code,
   Material Symbols Outlined. O aplicativo roda sem internet — nenhuma fonte
   pode vir do Google em tempo de execução.
3. Casca de `01-shell.md`: barra de título arrastável, trilho, menu sobreposto,
   cabeçalho de página, painel direito com alça, rodapé de garantia.
4. Componentes de `02-componentes.md`, na ordem: botão, campo, seletor de
   visões, etiqueta, cartão, tabela, par chave-valor, diálogo, aviso.

**Aceite da fase 0:** uma tela qualquer renderiza com a casca completa nos dois
temas, em 1440×900, sem rolagem de página; o menu abre por passagem do mouse
sem deslocar o conteúdo; `Ctrl+K` foca a caixa de pedido.

## Fase 1 — O caminho que vende o produto

Assistente → Acervo → Aprovações. É a demonstração inteira: pergunta, resposta
com citação, prazo extraído, pedido aprovado.

| Ordem | Tela | Por quê |
|---|---|---|
| 1 | **A1 Assistente** (inicio, conversa) | Destino padrão; exercita citação, plano, blocos de resultado |
| 2 | **A5 Acervo** (documentos, prazos) | Origem das citações e dos prazos |
| 3 | **A11 Aprovações** (fila) | Regra central do produto; sem ela nenhuma outra tela pode enviar nada |
| 4 | **A0a/A0b Boas-vindas** | Primeira execução e o vínculo por código |

## Fase 2 — Trabalho do dia

| Ordem | Tela |
|---|---|
| 5 | **A15 Serviços** (pastas, trabalho) |
| 6 | **A4 Agenda** (mes, semana, tarefas) |
| 7 | **A6 Documentos** (editor, previa) |
| 8 | **A1 Assistente** (editor, lado a lado) |
| 9 | **A7 E-mail** (caixa, novo, contas) |

## Fase 3 — Escritório

| Ordem | Tela |
|---|---|
| 10 | **A8 Assinatura** |
| 11 | **A9 Financeiro** |
| 12 | **A10 Cadastros** |
| 13 | **A13 Configurações** (nove seções) |
| 14 | **A11 Aprovações** (historico, regras) |
| 15 | **A5 Acervo** (organizar) |

## Fase 4 — O que amplia

| Ordem | Tela |
|---|---|
| 16 | **A16 Gravações** |
| 17 | **A12 Foco e bem-estar** |
| 18 | **A14 Apoiar** |
| 19 | **A6 Documentos** (planilha) |

## Fase 5 — Celular

Só depois que a casca do desktop estiver estável, pelos motivos de `04`: a
adaptação reusa os mesmos componentes com outras medidas. Ordem: M1 → M11 →
M4 → M5 → M15 → M13 → resto.

---

## O que cada tela precisa do backend

Não estou nomeando rotas: as 197 já existem e o mapeamento correto sai da
leitura do `api.py`. O que segue é a **necessidade de dados** de cada tela, para
que o mapeamento seja conferido tela a tela e o que faltar apareça cedo.

| Tela | Precisa |
|---|---|
| A1 Assistente | conversa em fluxo, etapas do plano, trechos com documento/página/texto, itens de "acontecendo agora", recentes |
| A5 Acervo | árvore de pastas, lista com estado de análise, ficha do documento, prazos extraídos com cláusula e cálculo |
| A11 Aprovações | fila com tipo/autor/efeito/reversibilidade, decisão em lote, histórico, regras de alçada |
| A0a/A0b | estado da instalação (Ollama, modelo, disco), criar escritório, gerar e validar código de vínculo |
| A15 Serviços | serviços com cliente, progresso, equipe, arquivos, prazos, trilha |
| A4 Agenda | compromissos, prazos, tarefas, pedidos por link, criação de reunião |
| A6 Documentos | abrir DOCX/XLSX/PDF, salvar versão, comentários do assistente, fórmula proposta |
| A7 E-mail | contas IMAP/SMTP, conversas, mensagem, rascunho do assistente, envio por aprovação |
| A8 Assinatura | certificado (arquivo ou do Windows), validade, assinar com posição e páginas, selo |
| A9 Financeiro | saldos, lançamentos, fluxo de 6 meses, folha, parecer do mês |
| A10 Cadastros | clientes, equipe com papel e acesso, despesas fixas |
| A13 Configurações | perfil, modelo, métricas de máquina ao vivo, conexões, aprendizado, vínculos |
| A16 Gravações | gravar, transcrever por falante, contexto ao vivo, resumo, arquivar |
| A12 Foco | ciclos, lembretes, uso local por hora e por dia |

## Critérios de aceite, tela a tela

Vale para qualquer tela. Só passa quando todos forem verdadeiros:

1. Cabe em 1440×900 sem rolagem da página; rolam apenas as áreas previstas.
2. Existe nos dois temas, sem cor literal fora das variáveis.
3. Tem os quatro estados de `05`: vazio inicial, vazio por filtro, carregando, erro.
4. Todo alvo de clique ≥ 28px no desktop, ≥ 44px no celular.
5. Números em `tabular-nums`; datas no formato do desenho.
6. Nenhuma ação com efeito externo dispara sem passar por Aprovações.
7. Toda ação concluída gera aviso, com Desfazer quando reversível.
8. Percorrível só com teclado; foco visível; `Esc` fecha o que estiver aberto.
9. Rótulos e frases iguais aos do mockup. Texto não se reescreve na implantação.
10. Lado a lado com o mockup no mesmo tamanho, as diferenças são explicáveis.

## Quando o desenho estiver errado

Vai acontecer: o mockup não conhece dado real. A regra é não improvisar no
código — anote o caso, escolha a saída mais conservadora (o componente que já
existe, o estado mais próximo) e traga a divergência. Desenho novo sai em nova
versão do mockup, não em CSS solto na tela.
