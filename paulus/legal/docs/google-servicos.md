# Agenda, Meet e Drive do Google

A mesma conta Google que entra no e-mail (veja `email-oauth.md`) ganha, quando a pessoa pede em **Configurações › Conexões › Conta Google**, mais uma permissão. É a autorização incremental do Google (`include_granted_scopes`): a tela do Google abre no navegador, a pessoa marca a caixa do serviço, e a permissão nova se soma às que já existem. Quem só usa o e-mail não vê nada diferente.

O código está em `src/google_servicos.py`, e as rotas em `/api/google*` e `/api/agenda/{id}/meet`.

## O que cada serviço pede, e por quê

| Serviço | Escopo | Classificação no Google | O que o PAULUS faz |
|---|---|---|---|
| Agenda e Meet | `https://www.googleapis.com/auth/calendar.events` | sensível (verificação sem avaliação paga) | cria, atualiza e apaga os eventos dos compromissos; lê os eventos para mostrar na Agenda; cria a sala do Meet dentro do evento |
| Drive | `https://www.googleapis.com/auth/drive.file` | não sensível | cria a pasta PAULUS e envia para ela os documentos que a pessoa aprova; só enxerga o que ele mesmo criou |

- **Meet sem escopo próprio.** A sala nasce do evento da Agenda (`conferenceData`, com `conferenceDataVersion=1`), e o link vem na resposta.
- **Drive sem ler o Drive inteiro.** Ler tudo pediria `drive.readonly` ou `drive`, que são restritos: exigem a avaliação de segurança paga (CASA), a mesma do Gmail. O caminho sem custo para o Acervo ler o Drive é o **Google Drive para computador**. Ele vira uma pasta do Windows (`G:\Meu Drive`), e o Acervo vigia pastas. A tela de Conexões acha essa pasta e oferece "vigiar no Acervo".

## O que sai desta máquina

- **Agenda:** só com "Sincronizar os compromissos com o Google" ligado. O título, a data, a hora, a duração e o lugar (online, escritório, telefone) de cada compromisso, de uma semana atrás a um ano à frente. A anotação e o cliente ficam aqui.
  - Salvar um compromisso manda na hora, em segundo plano. Apagar aqui apaga lá.
  - Os eventos que já existiam no Google aparecem na Agenda só para ver, com "Mostrar os eventos do Google na Agenda" ligado. Editar é no Google.
- **Drive:** só o documento que a pessoa manda (menu "…" do documento, no Acervo). O pedido vai para a fila de **Aprovações** e nada sai antes do sim.

## Passos no Google Cloud (quem publica o PAULUS, uma vez)

No mesmo projeto do login do Gmail:

1. **APIs e serviços › Biblioteca:** ative a **Google Calendar API** e a **Google Drive API**. Sem isso, o PAULUS diz "a API … não está ligada no projeto do PAULUS no Google Cloud".
2. **Google Auth Platform › Acesso a dados** (ou "Escopos", na tela de consentimento): adicione `https://www.googleapis.com/auth/calendar.events` e `https://www.googleapis.com/auth/drive.file`, além do `https://mail.google.com/` que já está lá.
3. **Modo Teste:** continua valendo a lista de usuários de teste e o vencimento de 7 dias do refresh token. O aviso "O Google não verificou este app" aparece de novo na primeira vez que alguém conecta a Agenda.
4. **Verificação:** o `calendar.events` é sensível, e a verificação do app precisa incluir esse escopo.
   - Grave um vídeo mostrando: conectar a Agenda em Conexões, a tela de consentimento com o escopo, um compromisso indo para o Google Agenda, a sala do Meet criada e a sincronização desligada.
   - Justificativa: "o PAULUS copia para a Agenda do Google os compromissos que o usuário marca no app e cria a sala do Meet deles; lê os eventos para mostrar na agenda do app".
   - O `drive.file` não pede justificativa de escopo restrito.
5. **Política de privacidade** (`site/politica-de-privacidade/`): os dois escopos novos precisam estar descritos antes de o Google revisar. O texto está pronto no site, e **só vai ao ar com o push**.

## Limites reais

- O PAULUS não edita eventos que nasceram no Google. Só mostra.
- A sincronização é de ida (compromisso do PAULUS → Google) mais a leitura. Mudar no Google um evento que o PAULUS criou não muda o compromisso aqui, e a próxima sincronização volta com a versão do PAULUS.
- Não há permissão por serviço para revogar no Google: tirar a permissão de vez é em myaccount.google.com/permissions, e isso tira o Gmail junto.
- Convite para outras pessoas continua pelo e-mail do PAULUS, pela fila de Aprovações. O Google não manda convite em nome do escritório.
