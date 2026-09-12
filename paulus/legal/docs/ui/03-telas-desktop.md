# 03 — Telas do desktop

Referência: 1440×900. Cada tela abaixo traz propósito, estrutura, colunas de
tabela quando houver, conteúdo do painel direito, estados e as ligações com as
outras telas. Onde o texto cita uma frase entre aspas, ela é literal: veio do
aplicativo atual ou foi aprovada no desenho, e não deve ser reescrita.

O mapa inteiro: 26 telas antigas → 11 destinos + Serviços, Gravações e Apoiar.
A fusão acontece pelo **seletor de visões** no cabeçalho.

---

## A0a — Boas-vindas (quem cria o escritório)

Primeira execução. Seis passos, todos puláveis e revisíveis depois em
Configurações. Sem casca: tela inteira, conteúdo em coluna de 520px centralizada
(ou duas colunas `minmax(0,1.1fr) minmax(0,1fr)` quando há tabela ao lado).

1. **Boas-vindas** — estado da instalação: Ollama encontrado, modelo baixado,
   espaço em disco. Cada item com ponto de estado e ação de correção quando falha.
2. **Escritório** — duas opções em cartão: criar um novo (quem cria vira usuário
   master) ou entrar em um existente com código de vínculo pela rede local.
3. **Seus dados** — os mesmos campos de Configurações › Meus dados: nome, CPF,
   OAB, telefone, e-mail, endereço, foto.
4. **Como a IA funciona** — afirmação categórica de que o modelo roda nesta
   máquina, com a tabela "onde cada coisa fica" (documento, índice, conversa,
   modelo, atualização) em duas colunas.
5. **Conexões** (opcional) — conta Google (Gmail, Drive), Microsoft (Outlook,
   OneDrive), IMAP/SMTP. Cada uma é um cartão com estado e botão conectar.
6. **Atualizações** — frequência e o aviso de que é a única saída para a internet.

Rodapé fixo: "Pular" à esquerda, passo atual no centro (pontos), "Continuar" à
direita. No último passo, "Abrir o PAULUS" leva ao Assistente.

## A0b — Entrar no escritório (quem digita o código)

Passos 1 e 2 iguais. Ao marcar "Entrar em um escritório existente":

3. **Seus dados** — idem A0a.
4. **Códigos** — a pessoa digita o código do responsável e recebe o seu próprio,
   em Fira Code, tamanho grande, com botão copiar. Sem escolha de rede: o
   vínculo acontece pela rede local em que a máquina já está.

Depois disso ela entra no PAULUS em **modo limitado** (ver `01-shell.md`): usa
tudo que é local, e o que depende da rede fica bloqueado até o responsável
validar em Configurações › Escritório e vínculos.

---

## A1 — Assistente

O destino padrão. Três estados na mesma tela, não três telas.

### inicio
Área central em coluna de 760px. De cima para baixo:

- Saudação em Garamond 30–34px, por dia e hora ("Boa tarde, Matheus").
- **Caixa de pedido** (ver `02`), sempre visível.
- **Acontecendo agora** — grade `repeat(auto-fit, minmax(min(100%,250px),1fr))`
  com o que exige atenção hoje: prazo que vence, aprovação parada, e-mail
  aguardando. Cada cartão leva à tela de origem.
- **Recentes** — últimas conversas e documentos, lista simples, 13px.
- Rodapé de garantia: "nenhuma requisição à internet".

### conversa
Grade `minmax(0,1fr) 320px`: conversa à esquerda, painel de trechos à direita.

- **Plano de execução**: etapas com estado (feito, em andamento, esperando). Ao
  terminar, recolhe numa linha só ("4 etapas · 12 s"), clicável para reabrir.
- **Resposta** com citações numeradas. Clicar na citação abre, no painel, o
  documento, a página e o trecho, com o cabeçalho "Por que este trecho".
- **Blocos de resultado**: quando a resposta produz dados (lista de prazos,
  lista de arquivos, valores), eles chegam como cartão dentro da conversa, com
  ações próprias — "Criar na Agenda", "Abrir no Acervo".
- Caixa de pedido fixa embaixo.

### editor
Grade `400px minmax(0,1fr)` ou `minmax(0,1fr) 640px`: chat à esquerda, documento
à direita, lado a lado.

- A alteração proposta aparece no documento como **controle de alterações real**:
  trecho riscado em `--ink3` e inserção sublinhada em `--acc`.
- Sobre a alteração, a dupla **Manter / Descartar**.
- O documento continua rolável e editável durante a conversa.

**Modo limitado:** no lugar de "Acontecendo agora", o cartão de espera — seu
código, o do responsável, e a lista do que já funciona.

---

## A4 — Agenda

Seletor: **Mês · Semana · Tarefas**. Botão "Novo ▾" cria compromisso, pagamento,
prazo ou tarefa. Hoje = sexta, 11 de setembro (coerente com o resto do desenho).

- **Mês**: grade `repeat(7, minmax(0,1fr))`, célula com no máximo 3 marcas e
  "+2". Prazo em vinho (`--acc`), compromisso em grafite (`--ink`), pedido
  pendente com borda tracejada. Painel: o dia selecionado, hora a hora.
- **Semana**: grade `64px repeat(5, minmax(0,1fr))`, faixa de hora à esquerda,
  altura de hora fixa, só a grade rola. Painel: novo compromisso (título,
  quando, com quem, local ou link de reunião — Meet, Teams).
- **Tarefas**: listas à esquerda, detalhe no painel: etapas, lembrete,
  "ligado a" (serviço, cliente, documento) e anotação.

Pedidos por link chegam como cartão no painel do dia, com **Aceitar** e
**Propor outro horário**. Convite por e-mail passa por Aprovações. Prazo criado
a partir do Acervo chega com a cláusula de origem anexada.

---

## A5 — Acervo

Seletor: **Documentos · Organizar · Prazos**. Coluna esquerda de 260px com a
árvore de pastas; painel direito de 400px.

### documentos
Tabela `20px minmax(0,1fr) 110px 170px 28px`: seleção, nome, tipo, estado da
análise, menu. Estados de análise, cada um com etiqueta própria: analisado ·
tomando vista · mudou desde então · sem análise.

Barra de seleção (substitui o cabeçalho ao marcar): **Tomar vista · Mover ·
Fixar · Exportar · Apagar**, com a contagem à esquerda.

Painel: ficha do documento — cliente, pasta, tamanho, data, resumo da IA,
prazos extraídos (levam à visão Prazos) e "Perguntar sobre estes", que abre o
Assistente com o contexto já preenchido.

### organizar
Quatro fases em fita: **Escolher → Ler → Conferir → Mover**. No centro, a
conferência da classificação, linha a linha, com a certeza em etiqueta
(Alta / Média / Baixa) e o destino proposto. No painel, o plano de pastas, com
o destino `Documentos\Acervo PAULUS` e a frase, literal: "nada é apagado nem
sobrescrito, dá para desfazer".

### prazos
Tabela `minmax(0,2fr) minmax(0,1.6fr) 100px 150px 150px`: prazo, documento de
origem, certeza, data, ações. Painel: a cláusula de origem citada e "como
calculei", com **Confirmar · Criar tarefa · Ignorar** e "Levar para a Agenda".

---

## A6 — Documentos

Abas de documentos abertos no topo (DOCX, XLSX, PDF só leitura). Seletor:
**Editor · Planilha · Pré-visualização**. Folha em `--paper`, largura 640px
(editor) ou 1100px (planilha). Painel de 400px.

- **Editor**: duas barras de ferramentas. A primeira, formatação. A segunda,
  jurídica: Códigos (CC, CPC, CP, CLT), citação, jurisprudência, súmulas,
  cláusulas do escritório, conferir prazos, qualificação das partes.
  O comentário do assistente aparece ancorado no corpo do texto (ex.: 48 h × 72 h)
  com ação direta: **Trocar para 72 h / Manter**.
- **Planilha**: grade com cabeçalho de coluna, barra `fx` com a fórmula escrita
  em português, total e abas na base. A fórmula proposta aparece na barra antes
  de ser aplicada, com **Manter / Desfazer**.
- **Pré-visualização**: papel timbrado com a logo, miniaturas das páginas à
  esquerda. Painel: "O que fazer agora", "Confira antes de sair" e o histórico
  de versões.

---

## A7 — E-mail

Três colunas (`240px` pastas e contas · conversas · mensagem) + painel de 400px.
Seletor: **Caixa de entrada · Novo e-mail · Contas**.

- Filtros em chips: **Tudo · Não lidos · Com anexo · De clientes**.
- Painel da caixa: "o que o assistente entendeu", prazo detectado e o rascunho
  preparado, com **Aprovar e enviar** (que cria o pedido em Aprovações).
- **Novo e-mail**: composição no mesmo lugar; painel com as conferências do
  assistente (anexo citado e ausente, valor divergente, prazo).
- **Contas**: lista de contas com estado; painel com o formulário IMAP/SMTP.
  Senha recusada vira estado "Reconectar". Frases literais: "a senha fica nesta
  máquina" e "leio só o que você abre".

Enviar é sempre **"Enviar para aprovação"**. Prazo detectado vira sugestão para
a Agenda, nunca compromisso direto.

---

## A8 — Assinatura

Seletor: **Assinar documento · Certificado digital**.

- **assinar**: visor do PDF (560–680px) com o selo arrastável sobre a página.
  Painel: páginas (Todas as 12 · Só a última · Primeira e última · Intervalo),
  posição (rodapé à direita como padrão), certificado em uso com atalho para
  trocar, o que fazer depois (baixar, guardar, manter original, proteger com
  senha) e o cartão "Pronto para assinar". A miniatura da página 12 mostra onde
  o selo cai. Frase literal: "vou pedir sua confirmação antes de gravar".
- **certificado**: cadastro do e-CPF — arquivo `.pfx`/`.p12` até 8 MB, ou usar
  um já instalado no Windows; senha (vale por 15 minutos); emissor, validade,
  nº de série, guardado em. Painel: prévia do selo em tamanho real, com logo,
  código de verificação e QR, e a lista do que entra nele.

Compartilhar depois (e-mail, WhatsApp) passa por Aprovações.

---

## A9 — Financeiro

Seletor: **Visão geral · Lançamentos · Relatórios**. Coluna de painel fixa, sem alça.

- **geral**: quatro números no topo (saldo, a receber, a pagar, em atraso) em
  28–34px `tabular-nums`; fluxo de caixa de 6 meses em grade
  `repeat(6, minmax(0,1fr))`; recebimentos; folha. Painel "Precisa de você":
  folha, cobranças, nota fiscal.
- **lancamentos**: tabela `110px minmax(0,2fr) minmax(0,1.2fr) 120px 130px 140px`
  — data, descrição, categoria, cliente, valor, estado. Entradas e saídas na
  mesma tabela, sinal pela cor do valor. Painel: detalhe do lançamento, com o
  contrato ligado.
- **relatorios**: extrato, por categoria, parecer do mês com sugestões e
  "Não foi útil", e as abas Tarefas do dia / Financeiro / Ações de IA aprovadas.

Pagar, cobrar e enviar relatório passam por Aprovações. O atraso do Fornecedor A
liga à notificação pronta e ao contrato no Acervo.

---

## A10 — Cadastros

Seletor: **Clientes · Equipe · Despesas fixas**. Contexto no cabeçalho:
"42 clientes · 6 colaboradores · 2 sócios · 11 despesas fixas".

- **clientes**: tabela `minmax(0,2.4fr) minmax(0,1.4fr) minmax(0,1.2fr) 120px 28px`
  — nome, contato, ligado a, em aberto, menu. Painel: ficha com razão social,
  CNPJ/CPF, telefone, e-mail para cobrança, endereço, honorário padrão, dia de
  vencimento, documentos no Acervo, contratos e prazos.
- **equipe**: tabela `minmax(0,2fr) minmax(0,1.2fr) minmax(0,1.6fr) 130px 28px`
  — pessoa, papel, acesso por pasta, folha, menu. Painel: ficha da pessoa e
  "o que este papel pode" (matriz de papéis). Alterar papel passa por Aprovações.
- **despesas**: tabela `minmax(0,2fr) minmax(0,1.2fr) 100px 130px 130px 28px`
  — despesa, fornecedor, dia, valor, estado do mês, menu. Detalhe ligado ao
  contrato de locação e ao Financeiro.

---

## A11 — Aprovações

Seletor: **Fila · Histórico · Regras de alçada**. Contexto: "5 esperando você ·
nada sai sem aprovação". Coluna fixa, sem alça.

- **fila**: tabela `20px minmax(0,2.6fr) minmax(0,1.1fr) minmax(0,1.1fr) 170px`
  — seleção, pedido, quem pediu, tipo, quando. Filtro por tipo em chips e
  seleção em lote (**Aprovar / Recusar selecionadas**). Painel do pedido:
  o que vai sair (com a citação literal do rascunho), conferências do
  assistente, regra aplicada, efeito e se é reversível.
- **historico**: decisões do mês em linha do tempo; cada entrada marcada como
  aprovado, recusado ou desfeito.
- **regras**: quem aprova o quê, limite de valor e o que acontece se ninguém
  decidir dentro do prazo.

Os cinco pedidos do desenho: três respostas de e-mail, assinar a procuração,
mover arquivos, pagar a folha, dar acesso à pasta Jurídico.

---

## A12 — Foco e bem-estar

Seletor: **Hoje · Semana**. Coluna fixa.

- **hoje**: anel de progresso do ciclo ("Ciclo 3 de 4 · 17:24"), foco 25 min /
  pausa 5 min, "silenciar avisos durante o foco", "tarefa deste ciclo: enviar
  aviso de não renovação". Lembretes: beber água (3 de 8 copos, atrasado
  40 min), levantar, fruta, alongar. Painel: ritmo por hora
  (`repeat(11, minmax(0,1fr))`), números do dia ("ativo há 3 h 40 min · última
  pausa às 08:10 · sem pausa há 2 h"), sugestão para agora e os interruptores
  dos lembretes.
- **semana**: horas de foco por dia (`repeat(7, minmax(0,1fr))`) e hábitos em
  grade. Painel: parecer da semana, com sugestões que vão para a Agenda.

Tudo calculado só com uso local. Modo foco segura e-mail, WhatsApp e Aprovações
até a pausa.

---

## A13 — Configurações

Menu interno de 232px à esquerda (`232px minmax(0,1fr)`), nove seções. Cada
seção são dois cartões lado a lado; Desempenho ocupa a largura toda.
Salvar / Descartar no cabeçalho, ativos só quando há mudança.

1. **Meus dados** — foto, CPF, OAB, endereço, anexos.
2. **Assistente e modelo** — Ollama, `llama3.2:3b` e alternativas, trechos,
   temperatura, limites da IA, cache e índice.
3. **Desempenho** — processador 36% · 2,4 GHz, memória 11,8/15,7 GB, discos,
   vídeo, "ao vivo · últimos 60 segundos".
4. **Conexões** — Google, Microsoft, IMAP/SMTP, WhatsApp Web no navegador
   embutido, com envio só com aprovação.
5. **Aprendizado** — ensinar com arquivos (`manual_de_estilo_uener.pdf`,
   18 de 34 p.) e com suas palavras ("Prazo padrão de aviso").
6. **Aparência e atalhos** — tema claro/escuro, densidade, atalhos.
7. **Escritório e vínculos** — pedidos pendentes, vinculados, cargo e alçada,
   moderação. É aqui que o responsável digita o código de quem pediu para entrar.
8. **Feedback** — enviar impressão sobre o programa; nada sai sem revisão.
9. **Plano e apoio** — software livre, apoio mensal ou doação única,
   apoiadores, atualizações como única saída para a internet.

Registro fixo em Conexões: **"O que sai desta máquina"**, com data, destino e
tamanho de cada saída.

---

## A14 — Apoiar o projeto

Aberto pelo `favorite` do trilho. Duas visões: **contribuir** e **quem já apoia**.

- Copy sobre software livre e o que a contribuição paga.
- Recorrência: Mensal / Anual / Única. Valores: R$ 20 · 40 · 100 · Outro
  (`repeat(4, minmax(0,1fr))`).
- Pagamento: Pix (QR e código copia-e-cola; recorrência aprovada uma vez) ou
  Cartão.
- Lista de apoiadores: "Deseja aparecer na lista de apoiadores? Sim / Não" e
  "Como deseja aparecer: meu nome / meu escritório", com nome, cidade opcional
  e prévia de como fica na próxima atualização. Só nome e cidade são publicados.

Recibo por e-mail; lançamento automático no Financeiro; cancelar a qualquer momento.

---

## A15 — Serviços

Seletor implícito por filtros: **Em andamento · Todos · Concluídos**.
Botão "Novo serviço" (também criável pelo Assistente).

- **pastas**: grade `repeat(3, minmax(0,1fr))` de cartões. Cada cartão: nome
  próprio do serviço, cliente, descrição, status e progresso, equipe (avatares),
  contagem de arquivos, prazos e o próximo compromisso.
- **trabalho** (dentro do serviço): grade `minmax(0,1.4fr) minmax(0,1fr)`.
  Resumo da IA com "o que falta"; status para conclusão em etapas; arquivos do
  serviço, ligados ao Acervo. Painel: equipe, prazos e agendamentos, anotações
  e a trilha do serviço. "Perguntar sobre este" abre a conversa com o contexto
  do serviço.

---

## A16 — Gravações

Seletor: **Lista · Ao vivo · Gravação**.

- **lista**: tabela `40px minmax(0,2.4fr) minmax(0,1.4fr) 80px 150px 28px` —
  tipo (reunião, atendimento, audiência, nota de voz), título, participantes,
  duração, estado, menu.
- **live**: gravador com tempo, transcrição literal por falante rolando
  (`52px 28px minmax(0,1fr)`: hora, avatar, fala) e o painel **"Contexto ao
  vivo"** — cláusulas, valores, prazos e anotações relevantes ao que está sendo
  dito, com respostas prontas.
- **gravacao**: player, transcrição pesquisável e o Resumo da IA (decisões,
  pendências, onde foi arquivado).

Áudio, transcrição e resumo ficam na máquina e são arquivados no Acervo e na
trilha do Serviço. Aviso permanente para informar os participantes.
Compartilhar o resumo passa por Aprovações.
