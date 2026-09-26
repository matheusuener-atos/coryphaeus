# Entrar no e-mail com Google ou Microsoft

O PAULUS entra no e-mail de dois jeitos:

- **senha ou senha de app** no IMAP e no SMTP — o que a hospedagem do escritório oferece e o que o Gmail aceita com senha de app;
- **login do Google ou da Microsoft** (OAuth 2.0) — a pessoa entra na página do próprio provedor, no navegador, e o PAULUS recebe só uma autorização para ler e enviar e-mail. A senha da conta nunca passa pelo PAULUS.

As contas Outlook, Hotmail, Live e Microsoft 365 **só** entram pelo login: a Microsoft desligou a senha no IMAP e no SMTP delas.

O login usa **o aplicativo PAULUS**, registrado uma vez no Google Cloud e/ou no Azure por quem publica o programa — de graça. Os IDs vão no arquivo `oauth_app.json`, na pasta do programa (modelo: `oauth_app.exemplo.json`), e seguem com o programa para toda instalação. Esse arquivo está no repositório, que é **privado**; se um dia o repositório ficar público, tire o arquivo antes e gere uma chave nova no Google Cloud — um client secret publicado deixa qualquer um usar o registro em nome do PAULUS. Com ele no lugar, quem instala o PAULUS só clica em "Entrar com…" e faz login. Não há nada para configurar na máquina de cada escritório. O PAULUS não usa ID de outro programa; provedor sem ID não aparece na tela.

O client secret do Google vai no código de propósito: em aplicativo de computador, o próprio Google diz que ele não é tratado como confidencial (a proteção do login é o PKCE). Para testar com outro registro sem mexer no código, use as variáveis de ambiente `PAULUS_GOOGLE_CLIENT_ID`, `PAULUS_GOOGLE_CLIENT_SECRET` e `PAULUS_MICROSOFT_CLIENT_ID`.

## Como funciona, em uma linha

O PAULUS abre um servidor temporário em `127.0.0.1` numa porta livre, abre o navegador padrão na página de login, recebe o código de volta (conferindo o `state` e usando PKCE S256), troca por um *access token* (vale cerca de 1 hora, fica só na memória) e um *refresh token* (guardado nesta máquina pela DPAPI do Windows, como a senha). O access token é renovado sozinho antes de vencer. O IMAP e o SMTP entram com XOAUTH2. Se ninguém voltar do navegador em 5 minutos, o login é cancelado e nada é guardado.

---

## Google (Gmail)

1. Entre em <https://console.cloud.google.com/> com a conta Google do escritório e **crie um projeto** (por exemplo, "PAULUS escritório").
2. Vá em **APIs e serviços › Tela de consentimento OAuth** (em versões novas do console: **Google Auth Platform › Branding / Público-alvo / Acesso a dados**):
   - tipo de usuário **Externo**;
   - nome do app e e-mail de suporte (o seu);
   - deixe o status de publicação em **Teste**;
   - em **Usuários de teste**, adicione **o seu próprio e-mail** (e o de cada pessoa do escritório que vai entrar);
   - em **Escopos / Acesso a dados**, adicione `https://mail.google.com/` (aparece como "Ler, escrever, enviar e excluir permanentemente todos os seus e-mails do Gmail"). Os escopos `openid` e `email` são básicos.
3. **Ativar a Gmail API não é necessário**: o PAULUS usa IMAP e SMTP, não a API. O que precisa estar certo é o escopo `https://mail.google.com/` na tela de consentimento.
4. Vá em **Credenciais › Criar credenciais › ID do cliente OAuth** e escolha o tipo **App para computador** (Desktop app). Não é preciso informar endereço de redirecionamento: para app de computador, o Google aceita `http://127.0.0.1` em qualquer porta.
5. Copie o **ID do cliente** (termina em `.apps.googleusercontent.com`) e a **chave secreta do cliente** (começa com `GOCSPX-`) para o `oauth_app.json` (`google_client_id` e `google_client_secret`).

A chave secreta de um "App para computador" não é segredo de verdade (o próprio Google diz isso, porque ela vai junto do programa), mas mesmo assim o PAULUS a guarda protegida pela DPAPI e nunca a mostra de volta na tela.

### Limites reais do Google

- **Modo Teste**: até **100 usuários de teste**, e só quem está na lista consegue entrar. O Google mostra um aviso "O Google não verificou este app" — é esperado; clique em *Continuar*.
- **Em modo Teste, o refresh token vence em 7 dias.** Depois disso a conta aparece como "precisa entrar de novo" no PAULUS, e basta clicar para refazer o login.
- **Produção** (tirar do modo Teste, para qualquer pessoa entrar sem ser usuária de teste e sem o vencimento de 7 dias) exige a **verificação do Google**. O escopo `https://mail.google.com/` é **restrito**: a verificação inclui uma **avaliação de segurança paga, feita por empresa terceirizada** (CASA), renovada todo ano. Para um escritório que usa o próprio app, o modo Teste costuma bastar.
- Se a conta Google é de um Google Workspace com políticas do administrador, ele pode bloquear apps não verificados — nesse caso, o administrador precisa liberar o app (ou o escritório usa senha de app).

---

## Microsoft (Outlook, Hotmail, Microsoft 365)

1. Entre em <https://portal.azure.com/> (ou <https://entra.microsoft.com/>) e abra **Registros de aplicativo › Novo registro** (App registrations › New registration).
2. Nome: por exemplo "PAULUS escritório". Em **Tipos de conta com suporte**, escolha **Contas em qualquer diretório organizacional e contas pessoais da Microsoft** (o PAULUS usa o endpoint `common`, que atende os dois tipos).
3. Em **URI de redirecionamento**, escolha a plataforma **Cliente público/nativo (móvel e desktop)** — "Mobile and desktop applications" — e digite `http://localhost`. A Microsoft aceita qualquer porta nesse endereço, que é o que o PAULUS usa.
4. Depois de criar, vá em **Permissões de API › Adicionar permissão**:
   - em **APIs que minha organização usa**, procure **Office 365 Exchange Online** e adicione, como permissões delegadas, `IMAP.AccessAsUser.All` e `SMTP.Send`;
   - em **Microsoft Graph › Delegadas**, confirme `offline_access`, `openid` e `email`.
5. Não crie segredo de cliente: o PAULUS entra como **cliente público**, só com o ID.
6. Na página **Visão geral**, copie o **ID do aplicativo (cliente)** — "Application (client) ID", no formato `00000000-0000-0000-0000-000000000000` — para o `oauth_app.json` (`microsoft_client_id`).

### Limites reais da Microsoft

- Contas **pessoais** (outlook.com, hotmail.com, live.com) entram sem mais nada.
- Contas **Microsoft 365 de empresa** podem exigir **consentimento do administrador** do diretório para o app. Se a página de login pedir aprovação do administrador, é ele quem precisa conceder.
- O administrador também pode ter desligado o **IMAP** ou o **envio autenticado (SMTP AUTH)** da caixa. Nesse caso o login funciona, mas o PAULUS mostra qual das duas pontas (ler ou enviar) não conectou.
- Se o registro do app ficar sem uso por muito tempo, ou se o ID for apagado no Azure, a renovação passa a ser recusada e a conta aparece como "precisa entrar de novo".

---

## Depois de cadastrar os IDs

Em **E-mail › Contas**, clique **Entrar com Google** ou **Entrar com Microsoft**. O navegador abre na página do provedor; entre, autorize e volte ao PAULUS. A conta aparece ligada, e o PAULUS diz se ler (IMAP) e enviar (SMTP) funcionaram.

- Contas antigas, que entram por senha, continuam como estão.
- "Apagar todas as senhas desta máquina" apaga também as autorizações do login; essas contas passam a pedir para entrar de novo.
- Remover a conta no PAULUS não revoga a autorização no provedor. Para revogar: Google em <https://myaccount.google.com/permissions>; Microsoft em <https://account.live.com/consent/Manage> (conta pessoal) ou pelo administrador (Microsoft 365).
