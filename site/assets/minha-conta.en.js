/* My account (paulus.ia.br/en/my-account/): the same minha-conta.js, translated on screen.
   Load BEFORE minha-conta.js. Every text node, placeholder, title and aria-label that minha-conta.js
   writes passes through here: an exact phrase goes by the table; a phrase with values goes by the rules.
   A new phrase in minha-conta.js that is not here shows in Portuguese until it is added. */
(function () {
  "use strict";
  var PLANO = { "Advogado": "Lawyer", "Escritório": "Office", "Escritório Plus": "Office Plus" };
  var MES = { jan: "Jan", fev: "Feb", mar: "Mar", abr: "Apr", mai: "May", jun: "Jun", jul: "Jul", ago: "Aug", set: "Sep", out: "Oct", nov: "Nov", dez: "Dec" };
  function pl(n) { return PLANO[n] || n; }
  var T = {
    "Minha conta": "My account", "Carregando…": "Loading…", "não foi possível agora": "not possible right now",
    "Resumo": "Summary", "Consumo": "Usage", "Faturas": "Invoices", "Pagamento": "Payment", "Plano": "Plan", "Cadastro": "Billing details", "Escritório": "Office", "Pessoas": "People",
    "Advogado": "Lawyer", "Escritório Plus": "Office Plus",
    "Assinatura": "Subscription", "mensal": "monthly", "anual": "yearly", "Situação": "Status", "Ativa": "Active", "Próxima cobrança": "Next charge", "Cobrança em": "Charged to", "Assinante desde": "Subscriber since",
    "Trocar de plano": "Change plan", "Ver faturas": "View invoices", "Uso do ciclo": "Cycle usage", "Restam": "Left", "Renova em": "Renews on", "Recargas no ciclo": "Top-ups this cycle",
    "Ver consumo": "View usage", "Recarga no Pix": "Top up with Pix", "Últimas faturas": "Latest invoices", "Ver todas": "View all",
    "tokens usados no dia": "tokens used that day", "dias que ainda não chegaram": "days still ahead", "Tokens por dia no ciclo": "Tokens per day in the cycle",
    "No ciclo": "This cycle", "Média por dia": "Daily average", "Maior dia": "Busiest day", "Por pessoa": "By person",
    "Este ciclo": "This cycle", "Ciclo anterior": "Previous cycle", "Outro ciclo": "Other cycle", "Escolher o mês": "Pick the month", "Anterior": "Previous", "Próximo": "Next", "sem assinatura neste mês": "no subscription this month",
    "Data": "Date", "Descrição": "Description", "Forma": "Method", "Valor": "Amount", "Arquivos": "Files", "Paga": "Paid", "Pendente": "Pending", "Estornada": "Refunded",
    "NFS-e em PDF": "NFS-e as PDF", "Baixar a NFS-e em PDF": "Download the NFS-e as PDF", "NFS-e em XML": "NFS-e as XML", "Baixar o XML da NFS-e": "Download the NFS-e XML",
    "Todas": "All", "Pagas": "Paid", "Pendentes": "Pending", "Outro período": "Other period", "Tirar o período": "Clear the period",
    "Nenhuma fatura com esse filtro.": "No invoices for this filter.", "Baixar as NFS-e do ano (.zip)": "Download the year's NFS-e (.zip)",
    "Forma de pagamento": "Payment method", "Cartão de crédito": "Credit card", "cobrança automática todo mês": "charged automatically every month",
    "o QR chega por e-mail 3 dias antes de cada cobrança": "the QR code arrives by email 3 days before each charge",
    "Cartão": "Card", "Validade": "Expiry", "Nome no cartão": "Name on card", "Pagamentos pelo Mercado Pago": "Payments by Mercado Pago", "Trocar cartão": "Change card", "Cadastrar cartão": "Add card",
    "Recarga de créditos": "Credit top-up", "Pix copia e cola": "Pix copy and paste", "Copiar": "Copy", "Escolher outro valor": "Choose another amount", "QR Code do Pix": "Pix QR code",
    "Vale por 30 minutos. Os créditos entram assim que o pagamento cair, e não vencem na renovação.": "Valid for 30 minutes. The credits arrive as soon as the payment clears, and they don't expire at renewal.",
    "Mensal": "Monthly", "Anual": "Yearly", "plano atual": "current plan", "por ano": "per year", "por mês": "per month", "1 pessoa": "1 person",
    "É o que você tem hoje": "This is what you have today", "Trocar para este": "Switch to this one", "Cancelar assinatura": "Cancel subscription",
    "Nome ou razão social": "Name or company name", "CPF ou CNPJ": "CPF or CNPJ", "OAB": "OAB", "Telefone": "Phone", "E-mail das faturas": "Invoice email",
    "Endereço": "Address", "CEP": "Postal code", "Logradouro": "Street", "Número": "Number", "Complemento": "Unit", "Bairro": "District", "Cidade": "City", "UF": "State",
    "As próximas NFS-e saem com estes dados.": "The next NFS-e will carry these details.", "Salvar": "Save", "Dados do cadastro": "Billing details",
    "no ar": "online", "fora do ar": "offline", "Abrir": "Open", "Alterar endereço": "Change address", "Endereço do escritório": "Office address",
    "É por este endereço que a equipe e os clientes entram no Paulus do escritório, pelo túnel do Cloudflare.": "This is the address the team and clients use to reach the office's Paulus, through the Cloudflare tunnel.",
    "Instalações": "Installations", "principal": "main", "Tirar este computador": "Remove this computer",
    "Permissões Google": "Google permissions", "Conta": "Account", "conectado": "connected", "O que autorizar": "What to allow", "Agenda": "Calendar",
    "ler e enviar, com Aprovações": "read and send, with Approvals", "ler e criar eventos": "read and create events", "criar reuniões nos eventos": "create meetings in events",
    "só os arquivos que o Paulus envia": "only the files Paulus sends", "ler as pastas escolhidas": "read the chosen folders", "Vem com a Agenda: a mesma permissão": "Comes with Calendar: the same permission",
    "Desvincular a conta Google": "Unlink the Google account", "Revoga todas as permissões de uma vez.": "Revokes every permission at once.", "Desvincular": "Unlink",
    "Quem entra em Minha conta": "Who can open My account", "Convidar": "Invite", "titular": "owner", "financeiro": "finance", "convite enviado": "invite sent", "Tirar o acesso": "Remove access",
    "O financeiro vê o resumo, o consumo, as faturas e a forma de pagamento. Trocar de plano, cancelar e mexer no escritório são só do titular.": "Finance sees the summary, usage, invoices and payment method. Changing the plan, cancelling and office settings are for the owner only.",
    "← Voltar": "← Back", "Trocar o cartão": "Change card", "Cartão novo": "New card", "Número do cartão": "Card number", "Código de segurança": "Security code",
    "3 dígitos": "3 digits", "4 dígitos": "4 digits", "MM/AA": "MM/YY", "Nome impresso no cartão": "Name as printed on the card", "CPF ou CNPJ do titular do cartão": "Cardholder's CPF or CNPJ",
    "Cancelar": "Cancel", "Salvar cartão": "Save card", "Campos seguros do Mercado Pago": "Mercado Pago secure fields",
    "O número, a validade e o código vão direto para o Mercado Pago. O PAVLVS guarda só a bandeira, os 4 últimos dígitos, a validade e o nome impresso.": "The number, expiry and code go straight to Mercado Pago. PAVLVS keeps only the card brand, the last 4 digits, the expiry and the printed name.",
    "Fechar": "Close", "Hoje": "Today", "Novo": "New", "Tokens": "Tokens",
    "Por que você quer cancelar?": "Why do you want to cancel?", "Está caro para o escritório": "It's too expensive for the office", "Não estamos usando o bastante": "We're not using it enough",
    "Falta algo de que precisamos": "Something we need is missing", "Outro motivo": "Another reason", "Quer contar mais? (opcional)": "Want to tell us more? (optional)", "Continuar": "Continue",
    "Antes de sair: 20 M de tokens por nossa conta": "Before you go: 20 M tokens on us", "Antes de sair: 30% a menos por 2 meses": "Before you go: 30% off for 2 months",
    "Entram agora no ciclo, sem custo, para você testar o que ainda não usou. O plano continua igual.": "They're added to this cycle now, at no cost, so you can try what you haven't used yet. The plan stays the same.",
    "Cancelar mesmo assim": "Cancel anyway", "Aceitar a oferta": "Accept the offer", "Cancelar a assinatura?": "Cancel the subscription?", "Voltar": "Back",
    ". Depois disso, o Paulus abre só com os arquivos: sem respostas da IA, sem NFS-e e sem os demais serviços. Ao assinar de novo, volta tudo, sem reinstalar.": ". After that, Paulus opens with your files only: no AI answers, no NFS-e and none of the other services. Subscribe again and everything comes back, no reinstall.",
    "Alterar o endereço": "Change the address", "Endereço novo": "New address", "Túnel do Cloudflare": "Cloudflare Tunnel", "conexão protegida": "protected connection", "Alterar": "Change",
    "use pelo menos 3 letras": "use at least 3 letters", "não comece nem termine com hífen": "don't start or end with a hyphen", "só letras minúsculas, números e hífen": "only lowercase letters, numbers and hyphens",
    "é o endereço de agora": "that's the current address", "conferindo…": "checking…", "disponível": "available", "já em uso": "already in use", "não consegui conferir agora": "couldn't check right now",
    "Convidar para Minha conta": "Invite to My account", "E-mail da pessoa": "The person's email", "Entra como": "Joins as", "Enviar convite": "Send invite",
    ": vê o resumo, o consumo, as faturas e a forma de pagamento. Ela recebe um e-mail com o link, válido por 7 dias.": ": sees the summary, usage, invoices and payment method. They get an email with the link, valid for 7 days.",
    "Tirar este computador?": "Remove this computer?", "Tirar": "Remove", "Desvincular a conta Google?": "Unlink the Google account?", "Cancelar o convite?": "Cancel the invite?", "Tirar o acesso?": "Remove access?", "Cancelar convite": "Cancel invite",
    "Entre com a conta da assinatura, ou com a que o titular autorizou: pelo Google ou com e-mail e senha.": "Sign in with the subscription's account, or with the one the owner authorized: with Google or with email and password.",
    "Ainda não assina?": "Not subscribed yet?", "Conheça os planos": "See the plans",
    "Código do Pix copiado": "Pix code copied", "Copie o código no campo": "Copy the code from the field", "As próximas cobranças saem no Pix": "Next charges go through Pix",
    "20 M de tokens entraram no ciclo": "20 M tokens added to the cycle", "As duas próximas cobranças saem com 30% a menos": "The next two charges are 30% off", "Cadastro salvo": "Details saved",
    "Computador tirado": "Computer removed", "Conta Google desvinculada": "Google account unlinked", "Acesso tirado": "Access removed",
    // Ligado ao servidor (07/10): estados da assinatura, entrar e sair, cartao, Pix, plano, escritorio e Google.
    "Cortesia": "Courtesy", "Cancelada": "Cancelled", "Vencida": "Expired", "Pausada no Mercado Pago": "Paused at Mercado Pago", "Esperando o Mercado Pago": "Waiting for Mercado Pago",
    "Cobrança": "Billing", "sem cobrança": "no charge", "nenhuma": "none", "Próximo Pix": "Next Pix", "Pago até": "Paid until", "Termina em": "Ends on", "Créditos de recarga": "Top-up credits",
    "Nenhuma fatura ainda.": "No invoices yet.", "Não há um ciclo aberto agora.": "There's no open cycle right now.",
    "Não há um ciclo aberto agora. O plano venceu: assine de novo na aba Plano.": "There's no open cycle right now. The plan expired: subscribe again in the Plan tab.",
    "Não há consumo para mostrar neste período.": "No usage to show for this period.", "Por dia": "Per day",
    "Quem perguntou fica no Paulus do escritório: a nuvem recebe só o total de cada dia, sem saber de quem foi a pergunta.": "Who asked stays in the office's Paulus: the cloud only receives each day's total, without knowing whose question it was.",
    "O plano de cortesia não tem cobrança.": "The courtesy plan has no charges.", "Mês pago até": "Month paid until", "O Pix chega em": "Pix sent to",
    "A recarga é para quem tem o plano em dia.": "Top-ups are for accounts with the plan up to date.",
    "O Pix mensal manda o QR por e-mail, e o e-mail do Paulus ainda não está ligado": "Monthly Pix sends the QR code by email, and Paulus email isn't set up yet",
    "O plano pago de uma vez não tem cobrança mensal": "A plan paid at once has no monthly charge", "É preciso a assinatura mensal ativa": "It needs the active monthly subscription",
    "O Pix pede o CPF ou CNPJ do cadastro": "Pix needs the CPF or CNPJ in Billing details", "Há uma cobrança com valor ajustado em curso": "There's a charge with an adjusted amount in progress",
    "Assinar este": "Subscribe to this one", "Ficar neste plano": "Stay on this plan", "próximo": "next", "Ver os planos": "See the plans",
    "O plano de cortesia não tem cobrança. Para mudar de plano, escreva para contato@paulus.ia.br.": "The courtesy plan has no charges. To change plans, write to contato@paulus.ia.br.",
    "O plano venceu. Para voltar, escolha um plano: tudo volta assim que o pagamento entrar, sem reinstalar.": "The plan expired. To come back, choose a plan: everything comes back as soon as the payment clears, no reinstall.",
    "desligado": "disabled",
    "Este escritório ainda não tem endereço. Ele nasce no Paulus do escritório, em Configurações › Acesso externo; depois de ligado, aparece aqui.": "This office has no address yet. It's created in the office's Paulus, under Settings › External access; once it's on, it shows here.",
    "Nenhum computador entrou com esta conta no Paulus ainda.": "No computer has signed in to Paulus with this account yet.",
    "Nenhum serviço do Google ligado — ou o Paulus do escritório ainda não contou. Ele conta quando está aberto e ligado à internet.": "No Google service on — or the office's Paulus hasn't reported yet. It reports when it's open and online.",
    "Desligar um serviço faz o Paulus do escritório parar de usá-lo. O Google não tira uma permissão sozinha: para revogar tudo no Google, use Desvincular. Para ligar um serviço que nunca foi autorizado, entre com o Google no Paulus do escritório.":
      "Turning a service off makes the office's Paulus stop using it. Google doesn't remove a single permission: to revoke everything in Google, use Unlink. To turn on a service that was never authorized, sign in with Google in the office's Paulus.",
    "O Paulus do escritório revoga no Google o acesso ao Gmail, à Agenda e ao Drive, da próxima vez que estiver aberto e ligado à internet. Para ligar de novo, é preciso entrar com o Google no programa.":
      "The office's Paulus revokes Gmail, Calendar and Drive access in Google the next time it's open and online. To connect again, sign in with Google in the app.",
    "O convite vai por e-mail, e o e-mail do Paulus ainda não está ligado": "The invite goes by email, and Paulus email isn't set up yet",
    "Conferindo os valores…": "Checking the amounts…", "Ir para o pagamento": "Go to payment", "Passar para o Pix": "Switch to Pix", "Pagar todo mês no Pix?": "Pay every month with Pix?",
    "Voltar ao cartão": "Back to card", "Sair": "Sign out",
    "Você recebeu um convite para a Minha conta de um escritório. Entre com o e-mail que recebeu o convite, pelo Google ou com senha.": "You've been invited to an office's My account. Sign in with the email that got the invite, with Google or with a password.",
    "O botão do Google não carregou. Confira a internet ou o bloqueador de anúncios e recarregue a página.": "The Google button didn't load. Check your connection or ad blocker and reload the page.",
    "Procurando o CEP…": "Looking up the postal code…", "Não achei esse CEP agora. Confira o número ou preencha o endereço à mão.": "Couldn't find that postal code right now. Check the number or fill in the address by hand.",
    "Convite cancelado": "Invite cancelled", "Ordem de desvincular enviada": "Unlink order sent", "Cartão trocado": "Card changed",
    "Confira o número, a validade e o código do cartão": "Check the card number, expiry and security code",
    "Use um cartão de crédito: a assinatura não aceita cartão de débito nem pré-pago": "Use a credit card: the subscription doesn't take debit or prepaid cards",
    "Não dá para trocar o cartão por aqui agora: escreva para contato@paulus.ia.br": "The card can't be changed here right now: write to contato@paulus.ia.br",
    "O formulário do cartão não carregou (um bloqueador de anúncios pode ter barrado o Mercado Pago). Recarregue a página para tentar de novo": "The card form didn't load (an ad blocker may have blocked Mercado Pago). Reload the page to try again",
    "Não foi possível agora": "Not possible right now", "Muitas tentativas seguidas - espere um minuto": "Too many attempts in a row - wait a minute",
    "Esta conta não tem assinatura do Paulus: assine em paulus.ia.br/assinatura, ou peça um convite ao titular": "This account has no Paulus subscription: subscribe at paulus.ia.br/assinatura, or ask the owner for an invite",
    "A sua entrada venceu: entre de novo": "Your sign-in expired: sign in again",
    "Este convite venceu ou já foi usado: peça outro ao titular": "This invite expired or was already used: ask the owner for another one",
    "Este convite não abre: peça outro ao titular": "This invite doesn't open: ask the owner for another one",
    "Mensalidade do plano": "Monthly plan fee", "Plano anual": "Yearly plan", "Um mês no Pix": "One month with Pix",
  };
  var R = [
    [/\b(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\/(\d{4})\b/g, function (_, m, y) { return MES[m] + "/" + y; }],
    [/^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)$/, function (_, m) { return MES[m]; }],
    [/^Ciclo de (.+)$/, "$1 cycle"],
    [/^(.+) · plano (.+?) · (.+?)( \(financeiro\))?$/, function (_, a, p, e, f) { return a + " · " + pl(p) + " plan · " + e + (f ? " (finance)" : ""); }],
    [/^(.+) de (.+) tokens$/, "$1 of $2 tokens"],
    [/ · (\d+) dias$/, " · $1 days"], [/ · 1 dia$/, " · 1 day"],
    [/^ritmo da cota: (.+) por dia$/, "quota pace: $1 per day"],
    [/^Por dia · /, "Per day · "], [/^Faturas · (\d+)$/, "Invoices · $1"],
    [/^(\d+) pessoas$/, "$1 people"], [/^até (\d+) pessoas$/, "up to $1 people"], [/^(\d+) computadores$/, "$1 computers"], [/^1 computador$/, "1 computer"],
    [/^Assinatura (.+?)( · ciclo atual)?$/, function (_, p, c) { return pl(p) + " subscription" + (c ? " · current cycle" : ""); }],
    [/^Recarga de créditos · (.+)$/, "Credit top-up · $1"],
    [/^A NFS-e de cada pagamento sai em nome de (.+)\. Quando ela sai, o PDF e o XML aparecem nesta lista\.$/, function (_, n) { return "Each payment's NFS-e is issued in the name of " + (n === "quem está no Cadastro" ? "whoever is in Billing details" : n) + ". Once it's issued, the PDF and XML show up in this list."; }],
    [/^Se a cota do ciclo acabar, a recarga é no Pix, no preço do seu plano: (.+) a cada (.+) tokens\.$/, "If the cycle's quota runs out, top up with Pix at your plan's price: $1 for every $2 tokens."],
    [/^Gerar Pix de (.+)$/, "Generate a $1 Pix"],
    [/^(\d+)% a menos que 12 meses$/, "$1% less than 12 months"], [/^(.+) tokens por mês$/, "$1 tokens per month"], [/^(.+) por mês$/, "$1 per month"],
    [/^(Claude .+) e (Claude .+)$/, "$1 and $2"],
    [/^Cancelar a assinatura mantém o plano até (.+)\. Depois, o Paulus abre só com os arquivos\.$/, "Cancelling keeps the plan until $1. After that, Paulus opens with your files only."],
    [/^versão (.+) · último acesso (.+)$/, function (_, v, u) { return "version " + v + " · last seen " + (u === "agora" ? "now" : u.replace(/^ontem/, "yesterday")); }],
    [/^Computador (\d+)$/, "Computer $1"], [/^Tirar Computador (\d+)$/, "Remove Computer $1"],
    [/^Tirar (.+)$/, "Remove $1"],
    [/^Hoje as cobranças saem no$/, "Today you're charged on"], [/^\. A próxima, em (.+), já sai no cartão novo\.$/, ". The next one, on $1, goes to the new card."],
    [/^Trocar para o (.+)\?$/, function (_, p) { return "Switch to " + pl(p) + "?"; }], [/^Plano · (anual|mensal)$/, function (_, x) { return "Plan · " + (x === "anual" ? "yearly" : "monthly"); }],
    [/^A troca vale a partir de hoje\. A diferença deste ciclo é calculada pelos dias que faltam e entra na próxima cobrança, em (.+)\.$/, "The change applies from today. This cycle's difference is prorated by the days left and added to the next charge, on $1."],
    [/^(Advogado|Escritório Plus|Escritório) · (.+)$/, function (_, p, r) { return pl(p) + " · " + r.replace("/mês", "/mo").replace("/ano", "/yr"); }],
    [/^As duas próximas cobranças do (.+) saem por (.+)\. Depois, volta ao preço do plano\.$/, function (_, p, v) { return "The next two " + pl(p) + " charges are " + v + ". Then it goes back to the plan price."; }],
    [/^O (.+) fica ativo até$/, function (_, p) { return "The " + pl(p) + " plan stays active until"; }],
    [/^O endereço atual, (.+)\.paulus\.ia\.br, deixa de funcionar na hora\. Avise a equipe e os clientes\.$/, "The current address, $1.paulus.ia.br, stops working right away. Let the team and clients know."],
    [/^(.+)\.paulus\.ia\.br está livre\.$/, "$1.paulus.ia.br is available."],
    [/^Computador (\d+) deixa de usar a assinatura: a IA e os serviços da nuvem param nele até alguém entrar de novo com a conta PAVLVS no programa\.$/, "Computer $1 stops using the subscription: the AI and the cloud services stop on it until someone signs in again with the PAVLVS account in the app."],
    [/^(.+) não vai mais poder usar o link\.$/, "$1 won't be able to use the link anymore."], [/^(.+) deixa de entrar em Minha conta\.$/, "$1 will no longer open My account."],
    [/^Cartão trocado\. As próximas cobranças saem no final (\d+)$/, "Card changed. Next charges go to the card ending $1"],
    [/^Plano trocado para o (.+)$/, function (_, p) { return "Plan changed to " + pl(p); }],
    [/^Assinatura cancelada\. O plano fica ativo até (.+)$/, "Subscription cancelled. The plan stays active until $1"],
    [/^Endereço alterado para (.+)$/, "Address changed to $1"], [/^Convite enviado para (.+)$/, "Invite sent to $1"],
    [/^(.+) (ligado|desligado)$/, function (_, s, x) { return (T[s] || s) + (x === "ligado" ? " on" : " off"); }],
    // Ligado ao servidor (07/10).
    [/^Cancelada · vale até (.+)$/, "Cancelled · valid until $1"], [/^A partir de (.+)$/, "From $1"], [/^plano (.+)$/, function (_, p) { return pl(p) + " plan"; }],
    [/^(.+) tokens · não vencem na renovação$/, "$1 tokens · don't expire at renewal"],
    [/^As de (\d{4})$/, "The $1 ones"], [/^Ainda não há NFS-e em (\d{4})$/, "No NFS-e in $1 yet"],
    [/^O plano anual foi pago de uma vez e vale até (.+)\. Ele não renova sozinho\.$/, "The yearly plan was paid at once and is valid until $1. It doesn't renew on its own."],
    [/^Vale a partir de (.+)$/, "Starts on $1"],
    [/^A assinatura foi cancelada( em .+?)?\. O plano vale até (.+)\. Para continuar depois disso, assine de novo\.$/, function (_, em, ate) { return "The subscription was cancelled" + (em ? " on" + em.slice(3) : "") + ". The plan is valid until " + ate + ". To keep going after that, subscribe again."; }],
    [/^A troca vale a partir de hoje: a cota deste ciclo cresce na proporção dos dias que faltam\. A diferença deste ciclo, (.+), entra na próxima cobrança, em (.+), que sai por (.+)\. Depois, (.+) por mês\.$/,
      "The change applies from today: this cycle's quota grows in proportion to the days left. This cycle's difference, $1, is added to the next charge, on $2, which comes to $3. After that, $4 per month."],
    [/^A troca vale a partir de hoje\. A próxima cobrança, em (.+), sai por (.+)\.$/, "The change applies from today. The next charge, on $1, comes to $2."],
    [/^O ciclo pago continua no (.+) até (.+)\. A partir da próxima cobrança, nessa data, o plano passa a ser o (.+), por (.+) por mês\.$/, function (_, a, d, b, v) { return "The paid cycle stays on " + pl(a) + " until " + d + ". From the next charge, on that date, the plan becomes " + pl(b) + ", at " + v + " per month."; }],
    [/^Ficar no (.+)\?$/, function (_, p) { return "Stay on " + pl(p) + "?"; }],
    [/^A troca para o (.+), marcada para (.+), sai\. A próxima cobrança continua no (.+), (.+) por mês\.$/, function (_, a, d, b, v) { return "The change to " + pl(a) + ", set for " + d + ", is dropped. The next charge stays on " + pl(b) + ", " + v + " per month."; }],
    [/^Passar para o (.+) anual\?$/, function (_, p) { return "Switch to " + pl(p) + " yearly?"; }],
    [/^O ano é pago de uma vez, (.+), na página de pagamento \(Pix ou cartão\)\. Quando o pagamento entra, a assinatura mensal sai do Mercado Pago e o ano começa\.$/, "The year is paid at once, $1, on the payment page (Pix or card). Once the payment clears, the monthly subscription leaves Mercado Pago and the year starts."],
    [/^A troca marcada saiu: o plano continua o (.+)$/, function (_, p) { return "The scheduled change was dropped: the plan stays " + pl(p); }],
    [/^O (.+) vale a partir de (.+)$/, function (_, p, d) { return pl(p) + " starts on " + d; }],
    [/^A assinatura no cartão sai do Mercado Pago, e o mês já pago vale até (.+)\. Três dias antes de cada mês novo, o Pix \(QR e copia e cola\) chega em (.+)\. Para voltar ao cartão, é pela página de pagamento, quando o mês pago vencer\.$/,
      "The card subscription leaves Mercado Pago, and the month already paid is valid until $1. Three days before each new month, the Pix (QR code and copy and paste) goes to $2. To go back to the card, use the payment page when the paid month ends."],
    [/^O mês pago no Pix vale até (.+); a assinatura no cartão começa depois dele, na página de pagamento\.$/, "The month paid with Pix is valid until $1; the card subscription starts after it, on the payment page."],
    [/^(.+): ordem de (ligar|desligar) enviada$/, function (_, s, x) { return (T[s] || s) + ": order to turn " + (x === "ligar" ? "on" : "off") + " sent"; }],
    [/^Ordem enviada em (.+)\. O Paulus do escritório cumpre quando estiver aberto e ligado à internet\.$/, "Order sent on $1. The office's Paulus carries it out when it's open and online."],
    [/^Conferido pelo Paulus do escritório em (.+)\.$/, "Checked by the office's Paulus on $1."],
    [/^Este convite é para (.+): entre com esse e-mail$/, "This invite is for $1: sign in with that email"],
    [/^(Gmail|Agenda|Agenda e Meet|Meet|Drive), (.+)$/, function (_, s, d) { return (T[s] || s) + ", " + (T[d] || d); }],
  ];
  function traduz(s) {
    var core = s.trim(); if (!core) return s;
    if (Object.prototype.hasOwnProperty.call(T, core)) return s.replace(core, T[core]);
    var out = core;
    for (var i = 0; i < R.length; i++) { if (R[i][0].test(out)) { R[i][0].lastIndex = 0; out = out.replace(R[i][0], R[i][1]); if (!R[i][0].global) break; } R[i][0].lastIndex = 0; }
    return out === core ? s : s.replace(core, out);
  }
  var ATRS = ["placeholder", "title", "aria-label"];
  function no(n) {
    if (n.nodeType === 3) { var v = traduz(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v; return; }
    if (n.nodeType !== 1 || n.tagName === "SCRIPT" || n.tagName === "STYLE") return;
    ATRS.forEach(function (a) { if (n.hasAttribute(a)) { var v = n.getAttribute(a), t = traduz(v); if (t !== v) n.setAttribute(a, t); } });
    if (n.tagName === "INPUT" && n.type !== "text" && n.type !== "email" && n.value) return;
    for (var c = n.firstChild; c; c = c.nextSibling) no(c);
  }
  var alvo = function () { return [document.getElementById("mc-raiz"), document.getElementById("mc-camada"), document.getElementById("mc-toast")].filter(Boolean); };
  var obs = new MutationObserver(function (ms) {
    ms.forEach(function (m) {
      if (m.type === "characterData") no(m.target);
      else if (m.type === "attributes") no(m.target);
      else m.addedNodes.forEach(no);
    });
  });
  function ligar() { obs.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATRS }); alvo().forEach(no); }
  if (document.body) ligar(); else document.addEventListener("DOMContentLoaded", ligar);
  window.MC_IDIOMA = "en";
})();
