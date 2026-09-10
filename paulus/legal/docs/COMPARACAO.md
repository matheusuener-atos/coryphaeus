# Comparação com os wireframes

Levantamento de 10 de setembro de 2026. As 21 telas com wireframe correspondente
foram abertas num navegador de verdade, com dados de demonstração, e comparadas
lado a lado com o desenho original.

O método importa para ler o que vem depois. Cada rótulo de seção e cada texto de
botão do wireframe foi cruzado com o que a nossa tela mostra, e cada divergência
foi classificada em três caixas:

- **Falta** — o componente não existe em lugar nenhum do programa
- **Existe, outro estado** — está no código e aparece com o dado certo
  (o "Nº DE SÉRIE" só aparece com certificado instalado)
- **Dado de exemplo** — nome, valor ou arquivo inventado no wireframe

Só a primeira caixa é trabalho pendente. As outras duas somavam a maior parte
das divergências brutas, e é por isso que o número que interessa é menor do que
a primeira contagem sugere.

---

## O que já está idêntico

Paleta, tipografia, espaçamento e a estrutura de cabeçalho, painéis e rodapé
batem com o desenho aprovado nas 21 telas. O menu lateral tem os 20 destinos na
ordem do manual. O tema escuro é o padrão.

Três telas estão praticamente completas em relação ao wireframe: **Aprovações**,
**Aprendizado** e **Desempenho** — a última com uma ressalva de medição, abaixo.

---

## O que falta, por tela

Ordenado por quanto muda o uso, não por tamanho da lista.

### Tarefas — a maior diferença estrutural

O wireframe tem **três colunas**: filtros e listas à esquerda, tarefas no meio,
detalhe à direita. A nossa tela é uma coluna só, com os filtros como pastilhas e
o detalhe abrindo abaixo da lista.

O detalhe em si está quase todo lá (prazo, lista, cliente, anotação, etapas com
acrescentar, excluir, salvar). Falta:

- coluna de listas com contagem por lista e **+ nova lista**
- **Lembrar-me** (hora do aviso) e **Repetir** (recorrência)
- **Ligado a** — o documento vinculado à tarefa; o vínculo existe na base
  (tabela `vinculos`), mas a ficha não mostra
- **Ordenar por prazo**
- seção **Concluídas · N** dentro da lista, com texto riscado
- link **Ver no calendário →**

### Calendário — falta a coluna do dia e o preparo de reunião

O wireframe põe o mês à esquerda e o painel do dia à direita, lado a lado. Na
nossa tela o painel do dia fica **abaixo** do mês, e é preciso rolar.

Falta:

- alternador **Mês / Semana / Agenda**
- **Tarefas do dia** com caixas de marcar dentro do painel do dia, e **+ nova tarefa**
- bloco **Reunião**: criar link de Meet, Zoom, Teams ou só link
- **Anexos** do dia
- fim de semana com coluna esmaecida na grade

### Financeiro — quatro blocos inteiros

Os cartões do topo, o fluxo de caixa, o "precisa de você" e as listas de a
receber e a pagar estão. Falta:

- **Folha de pagamento**: total, número de pessoas, quebra em salários,
  encargos e estagiários, ver detalhamento e gerar recibos
- **Documentos e comprovantes** como painel do mês, com arrastar-e-soltar
  (hoje o comprovante se anexa lançamento a lançamento)
- **Notas fiscais** — registro do que foi emitido; a emissão continua na
  prefeitura, como o próprio wireframe diz
- **Boletos** — acompanhamento de vencimento; o boleto sai do banco
- **Contratos concluídos** do mês, para arquivar e encerrar pastas
- seletor de mês, botão **Exportar**, e "fechamento em N dias" no subtítulo
- caixas **Entradas no mês / Saídas no mês** ao lado do gráfico

### Biblioteca — a barra de ações em lote

Falta:

- **busca por nome, pasta ou trecho** com atalho de teclado
- filtros **Fixados** e **Sem análise**, e **Ordenar por modificação**
- seleção múltipla com barra de ações: **assinar, mover para pasta, fixar,
  exportar, apagar**
- ações por documento: **tomar vista de novo, perguntar sobre este,
  apagar da biblioteca**
- coluna **Nome e pasta** mostrando a pasta de origem
- **Adicionar pasta** direto da tela

### Editor de texto — a barra de ferramentas jurídica

O editor, o assistente lateral, as versões, a conferência e a exportação estão.
Falta:

- **alinhar, recuo e tabela** na barra (negrito, itálico, sublinhado, riscado,
  listas e alinhamento por botão já existem; o menu de alinhamento não)
- escolha de **fonte e corpo**
- **controlar alterações** no estilo do Word
- **régua** e indicador "página N de M · A4 · margens 2,5 cm"
- **numerar cláusulas**, **referência cruzada**, **qualificação das partes**
- **comentário do assistente ancorado no trecho**, dentro do texto
- barra de **códigos (CC, CPC, CP, CLT), jurisprudência e súmulas** — declinada
  de propósito, ver a seção final

### Pré-visualização

- **comparar versões** lado a lado dentro da tela (a comparação existe no
  editor, no histórico)
- **duas páginas**, **tela cheia** e **ajustar à página**
- **imprimir** e **enviar por WhatsApp**
- **proteger o PDF com senha** e **guardar na biblioteca ao sair** como opções
  da própria tela (a proteção por senha existe na tela de assinar)
- cabeçalho e rodapé do escritório no PDF (logotipo, OAB, cidade)

### Planilha

- **mesclar, bordas, congelar linha, filtrar e ordenar**
- **gráfico** a partir da seleção
- barra de status com **soma e média da seleção** (o resumo existe, mas da aba
  inteira, não do que está selecionado)
- atalhos do assistente: **explicar esta fórmula, achar erros, criar aba de
  resumo**
- **aviso na planilha** — apontar a célula cuja fórmula conflita com um contrato

### Agendamento

- visão de **semana em grade**, com os dias lado a lado
- alternador **Semana / Dia / Lista**
- escolha de **tipo** (compromisso, pagamento, prazo interno) no formulário

### Certificado digital

- **testar assinatura** com um documento de exemplo
- **arrastar o arquivo do certificado** para dentro da tela
- aviso de **alterações não salvas** no selo, com descartar
- link para o **registro de assinaturas**

### Assinar documento

- **compartilhar depois de assinar**: baixar, e-mail, WhatsApp, imprimir
- **repetir o selo em todo canto igual**
- **ver a prévia** antes de assinar
- voltar direto para a biblioteca

### Conexões

- **navegador embutido dentro da tela**, com barra de endereço travada
  (hoje abre em janela separada, e no navegador abre em aba)
- **gerar novo código** e **encerrar sessão** sem apagar os dados
- **expira em N dias** — não temos como saber sem ler a sessão do WhatsApp

### Contas de e-mail

- lista com **estado por conta**: sincronizado há quanto tempo, senha recusada,
  **reconectar**
- **assinatura por conta**, editável na própria tela
- registro de acessos

### Configurações

- **foto do perfil**
- **documentos e anexos** do titular (carteira da OAB, comprovante de endereço)
- **descartar alterações**

### Organizar pastas

- **salvar como rotina** — repetir a mesma varredura depois
- **começar de novo** no meio do fluxo

### Desempenho

- **disco, rede e temperatura** — hoje medimos processador, memória e vídeo
- **gráfico dos últimos 60 segundos**
- **espaço em disco** por unidade
- **pausar leitura** direto da tela

---

## O que não vamos implementar, e por quê

Estava no wireframe, foi decidido não fazer, e a tela diz isso em vez de fingir.

| No wireframe | Por que não |
|---|---|
| Códigos CC, CPC, CP, CLT · jurisprudência · súmulas | O programa não carrega o texto das leis. Pedir o artigo a um modelo de 3B produz número plausível e errado dentro de um contrato |
| Plano, cobrança, cartão, licenças | Não existe. O programa roda para uma pessoa, nesta máquina, sem servidor |
| Equipe, níveis de permissão, "atribuídas a mim", "quem pode aprovar em seu lugar" | Mesmo motivo. Entra quando houver equipe |
| Enviar mensagem pelo WhatsApp sem você apertar enviar | Automatizar o WhatsApp Web é dirigir a tela de um site de terceiro: quebra a cada mudança de layout e derruba a conta do escritório |
| Assinatura por token A3 | Exige driver PKCS#11 por fabricante |
| OAuth de e-mail (Google, Microsoft) | Semanas de revisão e custo antes da primeira linha funcionar |

---

## Diferenças de comportamento que não são falta

- **Estado vazio.** Os wireframes mostram sempre a tela cheia. As nossas contam
  quando não há dado — e isso é regra do manual, não limitação
- **Números.** Todo número da nossa tela sai de dado que existe. Onde o
  wireframe mostra "R$ 84.320" e nós mostramos zero, é porque não há lançamento
- **Ícones.** Os wireframes usam Material Icons por CDN; nós desenhamos os
  ícones em SVG, porque o programa roda sem internet

---

## Bugs achados neste levantamento

Todos corrigidos, e todos com teste em `tests/test_tela.py`.

1. A lista de conversas ficava com **12 pixels** de altura numa tela de 900 px —
   as conversas sumiam da barra lateral
2. A página não declarava ícone: todo carregamento pedia `/favicon.ico` e levava 404
3. Abria no tema claro, e o desenho aprovado é escuro
4. Na planilha, o valor de uma coluna encostava no texto da vizinha
5. O campo de pergunta da conversa aparecia nas 20 telas
6. **O gráfico de fluxo de caixa não desenhava barra nenhuma**: `align-items:
   flex-end` impedia a coluna de esticar, e a área das barras ficava com dois
   pixels. O mesmo padrão estava no gráfico da semana em Foco e bem-estar
