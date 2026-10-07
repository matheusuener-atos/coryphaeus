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
    "Desligar um serviço revoga só esse acesso no Google, na hora.": "Turning a service off revokes only that access in Google, right away.",
    "Desvincular a conta Google": "Unlink the Google account", "Revoga todas as permissões de uma vez.": "Revokes every permission at once.", "Desvincular": "Unlink",
    "Quem entra em Minha conta": "Who can open My account", "Convidar": "Invite", "titular": "owner", "financeiro": "finance", "convite enviado": "invite sent", "Tirar o acesso": "Remove access",
    "O financeiro vê o resumo, o consumo, as faturas e a forma de pagamento. Trocar de plano, cancelar e mexer no escritório são só do titular.": "Finance sees the summary, usage, invoices and payment method. Changing the plan, cancelling and office settings are for the owner only.",
    "← Voltar": "← Back", "Trocar o cartão": "Change card", "Cartão novo": "New card", "Número do cartão": "Card number", "Código de segurança": "Security code",
    "3 dígitos": "3 digits", "4 dígitos": "4 digits", "MM/AA": "MM/YY", "Nome impresso no cartão": "Name as printed on the card", "CPF ou CNPJ do titular do cartão": "Cardholder's CPF or CNPJ",
    "Cancelar": "Cancel", "Salvar cartão": "Save card", "Campos seguros do Mercado Pago": "Mercado Pago secure fields",
    "O número, a validade e o código vão direto para o Mercado Pago. O PAVLVS guarda só a bandeira e os 4 últimos dígitos.": "The number, expiry and code go straight to Mercado Pago. PAVLVS keeps only the card brand and the last 4 digits.",
    "Fechar": "Close", "Hoje": "Today", "Novo": "New", "Tokens": "Tokens",
    "Por que você quer cancelar?": "Why do you want to cancel?", "Está caro para o escritório": "It's too expensive for the office", "Não estamos usando o bastante": "We're not using it enough",
    "Falta algo de que precisamos": "Something we need is missing", "Outro motivo": "Another reason", "Quer contar mais? (opcional)": "Want to tell us more? (optional)", "Continuar": "Continue",
    "Antes de sair: 20 M de tokens por nossa conta": "Before you go: 20 M tokens on us", "Antes de sair: 30% a menos por 2 meses": "Before you go: 30% off for 2 months",
    "Entram agora no ciclo, sem custo, para você testar o que ainda não usou. O plano continua igual.": "They're added to this cycle now, at no cost, so you can try what you haven't used yet. The plan stays the same.",
    "Cancelar mesmo assim": "Cancel anyway", "Aceitar a oferta": "Accept the offer", "Cancelar a assinatura?": "Cancel the subscription?", "Voltar": "Back",
    ". Depois disso, o Paulus abre só com os arquivos: sem respostas da IA, sem NFS-e e sem os demais serviços. Ao assinar de novo, volta tudo, sem reinstalar.": ". After that, Paulus opens with your files only: no AI answers, no NFS-e and none of the other services. Subscribe again and everything comes back, no reinstall.",
    "Alterar o endereço": "Change the address", "Endereço novo": "New address", "Túnel do Cloudflare": "Cloudflare tunnel", "conexão protegida": "protected connection", "Alterar": "Change",
    "use pelo menos 3 letras": "use at least 3 letters", "não comece nem termine com hífen": "don't start or end with a hyphen", "só letras minúsculas, números e hífen": "only lowercase letters, numbers and hyphens",
    "é o endereço de agora": "that's the current address", "conferindo…": "checking…", "disponível": "available", "já em uso": "already in use", "não consegui conferir agora": "couldn't check right now",
    "Convidar para Minha conta": "Invite to My account", "E-mail Google da pessoa": "The person's Google email", "Entra como": "Joins as", "Enviar convite": "Send invite",
    ": vê o resumo, o consumo, as faturas e a forma de pagamento. Ela recebe um e-mail com o link, válido por 7 dias.": ": sees the summary, usage, invoices and payment method. They get an email with the link, valid for 7 days.",
    "Tirar este computador?": "Remove this computer?", "Tirar": "Remove", "Desvincular a conta Google?": "Unlink the Google account?", "Cancelar o convite?": "Cancel the invite?", "Tirar o acesso?": "Remove access?", "Cancelar convite": "Cancel invite",
    "Entre com a conta Google da assinatura, ou com a que o titular autorizou. Nenhuma senha a mais.": "Sign in with the subscription's Google account, or with the one the owner authorized. No extra password.",
    "Entrar com o Google": "Sign in with Google", "Ainda não assina?": "Not subscribed yet?", "Conheça os planos": "See the plans",
    "Código do Pix copiado": "Pix code copied", "Copie o código no campo": "Copy the code from the field", "As próximas cobranças saem no Pix": "Next charges go through Pix", "As próximas cobranças saem no cartão": "Next charges go to the card",
    "20 M de tokens entraram no ciclo": "20 M tokens added to the cycle", "As duas próximas cobranças saem com 30% a menos": "The next two charges are 30% off", "Cadastro salvo": "Details saved",
    "Computador tirado": "Computer removed", "Conta Google desvinculada": "Google account unlinked", "Acesso tirado": "Access removed", "O .zip com as NFS-e do ano está sendo preparado": "The .zip with the year's NFS-e is being prepared",
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
    [/^A NFS-e sai em até 2 dias úteis depois do pagamento, em nome de (.+)\.$/, "The NFS-e is issued within 2 business days of payment, in the name of $1."],
    [/^Se a cota do ciclo acabar, a recarga é no Pix, no preço do seu plano: (.+) a cada (.+) tokens\.$/, "If the cycle's quota runs out, top up with Pix at your plan's price: $1 for every $2 tokens."],
    [/^Gerar Pix de (.+)$/, "Generate a $1 Pix"],
    [/^(\d+)% a menos que 12 meses$/, "$1% less than 12 months"], [/^(.+) tokens por mês$/, "$1 tokens per month"], [/^(.+) por mês$/, "$1 per month"],
    [/^(Claude .+) e (Claude .+)$/, "$1 and $2"],
    [/^Cancelar a assinatura mantém o plano até (.+)\. Depois, o Paulus abre só com os arquivos\.$/, "Cancelling keeps the plan until $1. After that, Paulus opens with your files only."],
    [/^versão (.+) · último acesso (.+)$/, function (_, v, u) { return "version " + v + " · last seen " + (u === "agora" ? "now" : u.replace(/^ontem/, "yesterday")); }],
    [/^Tirar (.+)$/, "Remove $1"],
    [/^Hoje as cobranças saem no$/, "Today you're charged on"], [/^\. A próxima, em (.+), já sai no cartão novo\.$/, ". The next one, on $1, goes to the new card."],
    [/^Trocar para o (.+)\?$/, function (_, p) { return "Switch to " + pl(p) + "?"; }], [/^Plano · (anual|mensal)$/, function (_, x) { return "Plan · " + (x === "anual" ? "yearly" : "monthly"); }],
    [/^A troca vale a partir de hoje\. A diferença deste ciclo é calculada pelos dias que faltam e entra na próxima cobrança, em (.+)\.$/, "The change applies from today. This cycle's difference is prorated by the days left and added to the next charge, on $1."],
    [/^(Advogado|Escritório Plus|Escritório) · (.+)$/, function (_, p, r) { return pl(p) + " · " + r.replace("/mês", "/mo").replace("/ano", "/yr"); }],
    [/^As duas próximas cobranças do (.+) saem por (.+)\. Depois, volta ao preço do plano\.$/, function (_, p, v) { return "The next two " + pl(p) + " charges are " + v + ". Then it goes back to the plan price."; }],
    [/^O (.+) fica ativo até$/, function (_, p) { return "The " + pl(p) + " plan stays active until"; }],
    [/^O endereço atual, (.+)\.paulus\.ia\.br, deixa de funcionar na hora\. Avise a equipe e os clientes\.$/, "The current address, $1.paulus.ia.br, stops working right away. Let the team and clients know."],
    [/^(.+)\.paulus\.ia\.br está livre\.$/, "$1.paulus.ia.br is available."],
    [/^(.+) deixa de abrir o Paulus do escritório\. Para usar de novo, é preciso entrar com a conta Google no programa\.$/, "$1 will no longer open the office's Paulus. To use it again, sign in with the Google account in the app."],
    [/^O Paulus perde o acesso ao Gmail, à Agenda e ao Drive de (.+)\. Para ligar de novo, faça o consentimento no programa\.$/, "Paulus loses access to Gmail, Calendar and Drive for $1. To connect again, give consent in the app."],
    [/^(.+) não vai mais poder usar o link\.$/, "$1 won't be able to use the link anymore."], [/^(.+) deixa de entrar em Minha conta\.$/, "$1 will no longer open My account."],
    [/^Cartão trocado\. As próximas cobranças saem no final (\d+)$/, "Card changed. Next charges go to the card ending $1"],
    [/^Plano trocado para o (.+)$/, function (_, p) { return "Plan changed to " + pl(p); }],
    [/^Assinatura cancelada\. O plano fica ativo até (.+)$/, "Subscription cancelled. The plan stays active until $1"],
    [/^Endereço alterado para (.+)$/, "Address changed to $1"], [/^Convite enviado para (.+)$/, "Invite sent to $1"],
    [/^(.+) (ligado|desligado)$/, function (_, s, x) { return (T[s] || s) + (x === "ligado" ? " on" : " off"); }],
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
