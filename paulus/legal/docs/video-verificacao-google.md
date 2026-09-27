# Vídeo da verificação do Google (app PAVLVS)

Roteiro para gravar o vídeo que o Google pede para o escopo restrito do Gmail
(`https://mail.google.com/`). Conferido com o código em 26/09/2026.

## O que o Google confere no vídeo

- O fluxo completo, do clique em "Entrar com Google" até o uso dos dados.
- A tela de consentimento **em inglês**, com o nome do app (PAVLVS) e os mesmos escopos pedidos.
- O **ID do cliente OAuth** aparecendo na barra de endereço do navegador, na tela de consentimento.
- Cada recurso que usa o escopo pedido, funcionando.
- O vídeo vai para o YouTube como **Não listado**, e o link entra no formulário de verificação.

## Antes de gravar

1. **Use uma conta Gmail de teste**, e não uma caixa com e-mails de clientes. O vídeo fica visível para o revisor do Google.
2. **Mande dois e-mails para essa conta**, de outro endereço:
   - Assunto "Aditivo - prazo", com o corpo "Favor enviar o aditivo assinado até 15/10/2026, prazo final." Com essa frase o PAULUS detecta o prazo. Em inglês a detecção não funciona.
   - Um segundo e-mail qualquer, que você vai arquivar e excluir no vídeo.
3. **Abra o PAULUS na base de demonstração**, para nenhum dado real aparecer. Rode `tools\demo\abrir_demo.bat`.
4. **Prepare o navegador padrão:** deixe a janela maximizada e o zoom em 80%, para caber a URL inteira. O login do Google abre nele.
5. **Tenha o ID do cliente à mão:** Google Cloud › Google Auth Platform › Clientes. Não precisa falar o ID, só mostrar que ele está na URL.
6. **Escolha o gravador:** a Ferramenta de Captura do Windows 11, na opção de gravar vídeo, ou o OBS. Grave a tela inteira em 1080p.

O PAULUS aparece em português. Isso é permitido, mas o revisor precisa entender o que vê. Coloque as legendas em inglês abaixo no YouTube Studio (Legendas › Adicionar › Digitar manualmente) ou narre em inglês.

## Cenas

| # | O que fazer | Legenda em inglês |
|---|---|---|
| 1 | Mostre a janela do PAULUS aberta, com o nome no topo. | PAVLVS (PAULUS Legal) is a local AI legal assistant for Windows. This video shows the Google sign-in flow and how the app uses the Gmail scope https://mail.google.com/. |
| 2 | Abra **E-mail** no menu à esquerda, clique em **Contas**, depois em **Adicionar conta** e em **Entrar com Google**. | The user connects a Gmail account from the E-mail module. The app opens Google sign-in in the default browser. |
| 3 | No navegador, clique na barra de endereço e percorra a URL com as setas até aparecer `client_id=`. Pare dois segundos ali. | The address bar shows our OAuth client ID. |
| 4 | Escolha a conta de teste. Na tela de consentimento, troque o idioma para **English** no menu do canto inferior esquerdo. Mostre o nome **PAVLVS** e as permissões pedidas. Clique em **Continue** ou **Allow**. | The consent screen shows the app name PAVLVS and the requested access: the account email address and full Gmail access, which IMAP/SMTP requires. |
| 5 | Volte ao PAULUS. A caixa de entrada abre sozinha. Mostre a lista. | Use 1, read: the inbox is shown inside the app. Messages travel directly from Gmail to this computer, with no PAULUS server in between. |
| 6 | Abra o e-mail "Aditivo - prazo". Mostre o prazo detectado e clique em **Criar na Agenda**. Mostre o compromisso criado. | The local AI model, running on this computer, detects a deadline in the message and suggests a calendar entry. The user confirms it. |
| 7 | Clique em **Responder**, escreva uma linha e clique em **Enviar para aprovação**. Abra **Aprovações** e clique em **Aprovar**. | Use 2, send: replies are sent only after the user approves them in the Approvals queue. |
| 8 | Na caixa, ponha **estrela** num e-mail. Abra o segundo e-mail (abrir marca como lida), clique em **Arquivar** e, em outro, em **Excluir**, confirmando. | Use 3, organize: star, mark as read, archive and delete (moved to Gmail trash), always started by the user. |
| 9 | Em **E-mail › Contas**, abra o menu da conta, clique em **Remover** e confirme. Depois abra myaccount.google.com/permissions e mostre o PAVLVS na lista. | The user can disconnect at any time. The stored authorization is deleted from this computer, and access can be revoked in the Google Account. |
| 10 | Mostre paulus.ia.br/politica-de-privacidade no navegador. | Privacy policy: https://paulus.ia.br/politica-de-privacidade |

Não mostre recursos que o vídeo não precisa, como tradução ou "Contexto IA". Quanto mais curto, melhor. Três a cinco minutos bastam.

## Depois de gravar

1. Envie ao YouTube Studio com a visibilidade **Não listado**.
2. Cole o link na verificação: Google Cloud › Google Auth Platform › Central de verificação.

## Se o Google pedir a justificativa do escopo

O Google pergunta por que um escopo mais restrito não basta. Texto sugerido, que é o que o código faz:

> PAVLVS is a desktop email client. It reads, sends and organizes the user's mail over IMAP and SMTP with XOAUTH2 (Python imaplib/smtplib), directly between the user's computer and Gmail. Google only authorizes IMAP and SMTP access with the https://mail.google.com/ scope; the narrower Gmail API scopes (gmail.readonly, gmail.send, gmail.modify) do not grant IMAP/SMTP access. The "openid email" scopes only identify which account is connected. All processing, including the local AI model, happens on the user's computer; no Google user data is sent to our servers, used for advertising, sold, or used to train AI models.

## Agenda e Meet (escopo `calendar.events`, sensível)

Quando os escopos novos entrarem na verificação (docs/google-servicos.md), grave mais estas cenas, na mesma sessão ou num vídeo à parte:

1. **Configurações › Conexões › Conta Google**: mostre a linha "Agenda e Meet" e clique em **Conectar**.
2. **Tela do Google**: com a URL à vista (client_id e o escopo `calendar.events`), marque a caixa da Agenda e continue.
3. **Uso 1 — compromisso vai para a Agenda do Google**: marque um compromisso no PAULUS e mostre o evento aparecendo em calendar.google.com. Ele tem título, horário e lugar, e não tem a anotação.
4. **Uso 2 — sala do Meet**: abra o compromisso online, clique em **Criar sala no Meet** e mostre o link no compromisso e no evento.
5. **Uso 3 — eventos de lá na Agenda do PAULUS**: mostre um evento criado direto no Google aparecendo na Agenda do programa, só para ver.
6. **Desligar**: desligue "Sincronizar os compromissos com o Google" em Conexões.

Justificativa sugerida:

> PAVLVS copies to the user's primary Google Calendar the appointments the user creates in the app (title, start, end and location only), creates a Google Meet link for online appointments through the event's conferenceData, deletes the event when the user deletes the appointment, and lists the user's events to show them read-only in the app's calendar. calendar.events is the narrowest scope that allows creating and deleting events; calendar.readonly cannot create them, and calendar.app.created would hide the user's own events from the app's calendar. The Google Drive integration uses only drive.file (files the app itself creates).
