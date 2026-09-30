# Agenda, Meet e Drive do Google

A mesma conta Google que entra no e-mail (veja `email-oauth.md`) ganha, quando a pessoa pede em **Configurações › Conexões › Conta Google**, mais uma permissão. É a autorização incremental do Google (`include_granted_scopes`): a tela do Google abre no navegador, a pessoa marca a caixa do serviço, e a permissão nova se soma às que já existem. Quem só usa o e-mail não vê nada diferente.

O código está em `src/google_servicos.py`, e as rotas em `/api/google*`, `/api/agenda/{id}/meet` e o `meet: true` do `POST /api/agenda` (a sala criada ao salvar).

## O que cada serviço pede, e por quê

| Serviço | Escopo | Classificação no Google | O que o PAULUS faz |
|---|---|---|---|
| Agenda e Meet | `https://www.googleapis.com/auth/calendar.events` | sensível (verificação sem avaliação paga) | cria, atualiza e apaga os eventos dos compromissos; lê os eventos para mostrar na Agenda; cria a sala do Meet dentro do evento |
| Drive (enviar) | `https://www.googleapis.com/auth/drive.file` | não sensível | cria a pasta PAULUS e envia para ela os documentos que a pessoa aprova; só enxerga o que ele mesmo criou |
| Drive (ler) | `https://www.googleapis.com/auth/drive.readonly` | **restrito** (verificação + avaliação de segurança CASA) | navega no Drive inteiro para a pessoa escolher pastas; baixa as escolhidas como cópia no Acervo e confere as mudanças a cada 15 minutos (`src/drive_online.py`) |

- **Meet sem escopo próprio.** A sala nasce do evento da Agenda (`conferenceData`, com `conferenceDataVersion=1`), e o link vem na resposta.
- **Ler o Drive pela internet (29/09/2026).** A permissão à parte `drive.readonly`, só leitura, pedida em **Acervo › Incluir pasta › Google Drive** ou em Conexões ("Autorizar leitura"). A pessoa navega no Meu Drive, em "Compartilhados comigo" e nos drives compartilhados, e escolhe pastas.
  - Cada pasta escolhida vira uma cópia em `Acervo/Google Drive/<nome>`, com as subpastas. A vigia do Acervo lê a cópia como qualquer pasta; nenhuma pergunta vai ao Drive.
  - A cada 15 minutos (e em "Conferir agora"), o que mudou lá desce de novo; o que saiu de lá sai da cópia. Só desce o que o Acervo lê (PDF, Word, Excel, texto), até 200 MB cada; Docs, Planilhas e Apresentações do Google saem convertidos (.docx, .xlsx, .pdf).
  - Parar de acompanhar (Conexões, no "x" da pasta) deixa a cópia no Acervo, a não ser que se marque "Apagar também a cópia".
  - O outro caminho, sem permissão nenhuma, continua: o **Google Drive para computador** vira uma pasta do Windows (`G:\Meu Drive`), e o Acervo vigia pastas.

## O que sai desta máquina

- **Agenda:** só com "Sincronizar os compromissos com o Google" ligado. O título, a data, a hora, a duração e o lugar (online, escritório, telefone) de cada compromisso, de uma semana atrás a um ano à frente. A anotação e o cliente ficam aqui.
  - Salvar um compromisso manda na hora, em segundo plano. Apagar aqui apaga lá.
  - Os eventos que já existiam no Google aparecem na Agenda só para ver, com "Mostrar os eventos do Google na Agenda" ligado. Editar é no Google.
- **Meet:** a sala nasce do evento. Quando a pessoa pede a sala ("Criar sala no Google Meet" no formulário do compromisso ou no agendar de Serviços, ou "Criar sala no Meet" no compromisso já marcado), o evento daquele compromisso vai à Agenda do Google na hora, com os mesmos campos acima, mesmo com a sincronização desligada. Com a sincronização ligada, a opção já vem marcada nas reuniões online; desligada, vem desmarcada e a tela diz o que vai.
  - O link da sala fica no compromisso e entra no convite por e-mail.
- **Drive:** só o documento que a pessoa manda (menu "…" do documento, no Acervo). O pedido vai para a fila de **Aprovações** e nada sai antes do sim.
- **Ler o Drive:** nada sai. O PAULUS só lista e baixa as pastas escolhidas.

## Passos no Google Cloud (quem publica o PAULUS, uma vez)

No mesmo projeto do login do Gmail:

1. **APIs e serviços › Biblioteca:** ative a **Google Calendar API** e a **Google Drive API**. Sem isso, o PAULUS diz "a API … não está ligada no projeto do PAULUS no Google Cloud".
2. **Google Auth Platform › Acesso a dados** (ou "Escopos", na tela de consentimento): adicione `https://www.googleapis.com/auth/calendar.events`, `https://www.googleapis.com/auth/drive.file` e `https://www.googleapis.com/auth/drive.readonly`, além do `https://mail.google.com/` que já está lá.
3. **Modo Teste:** continua valendo a lista de usuários de teste e o vencimento de 7 dias do refresh token. O aviso "O Google não verificou este app" aparece de novo na primeira vez que alguém conecta a Agenda.
4. **Verificação:** o `calendar.events` é sensível, e a verificação do app precisa incluir esse escopo.
   - Grave um vídeo mostrando: conectar a Agenda em Conexões, a tela de consentimento com o escopo, um compromisso indo para o Google Agenda, a sala do Meet criada e a sincronização desligada.
   - Justificativa: "o PAULUS copia para a Agenda do Google os compromissos que o usuário marca no app e cria a sala do Meet deles; lê os eventos para mostrar na agenda do app".
   - O `drive.file` não pede justificativa de escopo restrito.
   - O `drive.readonly` é **restrito**, como o `https://mail.google.com/`: entra na mesma verificação de escopos restritos e na mesma avaliação de segurança CASA (anual). Justificativa: "o usuário escolhe pastas do próprio Drive para o app manter uma cópia local delas e pesquisar os documentos no computador, sem enviar o conteúdo a servidores; o app não grava no Drive com este escopo". Vídeo: autorizar a leitura no Incluir pasta, navegar, copiar uma pasta, o documento aparecendo no Acervo, parar de acompanhar.
   - **Até a verificação sair**, só as contas da lista de usuários de teste conseguem autorizar a leitura do Drive (até 100). Para os outros, o Google recusa na tela de consentimento, e o PAULUS continua mostrando o botão de autorizar e o caminho do Drive para computador.
5. **Política de privacidade** (`site/politica-de-privacidade/`): os escopos novos precisam estar descritos antes de o Google revisar. O texto está pronto no site (o `drive.readonly` entrou em 29/09/2026), e **só vai ao ar com o push**.

## Limites reais

- O PAULUS não edita eventos que nasceram no Google. Só mostra.
- A sincronização é de ida (compromisso do PAULUS → Google) mais a leitura. Mudar no Google um evento que o PAULUS criou não muda o compromisso aqui, e a próxima sincronização volta com a versão do PAULUS.
- Não há permissão por serviço para revogar no Google: tirar a permissão de vez é em myaccount.google.com/permissions, e isso tira o Gmail junto.
- Convite para outras pessoas continua pelo e-mail do PAULUS, pela fila de Aprovações. O Google não manda convite em nome do escritório.
