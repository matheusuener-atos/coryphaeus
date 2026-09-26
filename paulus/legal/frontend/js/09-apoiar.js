/* ------------------------------------------------------------- apoiar */
/*
   Apoiar o projeto (docs/ui/03-telas-desktop.md, A14): Contribuir e Quem ja
   apoia. O pagamento e o do Mercado Pago, sempre pelo site: o programa pede
   a /api/apoio (src/apoio.py), que repassa ao Worker do paulus.ia.br - so
   ele tem a chave do Mercado Pago.
     Pix     pagamento unico: o QR aparece aqui e a tela acompanha ate cair
     cartao  assinatura mensal ou anual: a pagina do Mercado Pago abre no
             navegador e o cartao e digitado la, nunca aqui
   A lista publicada ainda nao existe. Abre pelo coracao do trilho.
*/

const apoio = {
  visao: "contribuir", valor: 40, outro: "", recorrencia: "mensal", forma: "pix",
  aparecer: true, como: "escritorio", nome: "", cidade: "", confirmado: "",
  email: "", pago: "", assinado: "", gerando: false,
  // O que ainda espera confirmacao do Mercado Pago: o Pix gerado e nao pago,
  // a assinatura criada e ainda sem cartao. `ativa` e a data da confirmacao.
  pixId: "", assinaturaId: "", ativa: "",
  filtro: "todos", termo: "", prefs: null, lido: false,
};

function lerApoioGuardado() {
  if (apoio.lido) return;
  apoio.lido = true;
  try {
    const g = JSON.parse(localStorage.getItem("paulus.apoio") || "null");
    if (g && typeof g === "object") {
      ["valor", "outro", "recorrencia", "forma", "aparecer", "como", "nome", "cidade", "confirmado", "email", "pago", "assinado", "pixId", "assinaturaId", "ativa"].forEach((k) => {
        if (g[k] !== undefined) apoio[k] = g[k];
      });
    }
  } catch (err) { /* sem memoria do navegador, tudo bem */ }
  acertarRecorrencia();
}

function guardarApoio() {
  try {
    localStorage.setItem("paulus.apoio", JSON.stringify({
      valor: apoio.valor, outro: apoio.outro, recorrencia: apoio.recorrencia, forma: apoio.forma,
      aparecer: apoio.aparecer, como: apoio.como, nome: apoio.nome, cidade: apoio.cidade, confirmado: apoio.confirmado,
      email: apoio.email, pago: apoio.pago, assinado: apoio.assinado,
      pixId: apoio.pixId, assinaturaId: apoio.assinaturaId, ativa: apoio.ativa,
    }));
  } catch (err) { /* sem memoria do navegador, tudo bem */ }
}

function mostrarApoiar(visao) {
  if (visao) apoio.visao = visao;
  lerApoioGuardado();
  abrirTela("Apoiar o projeto", { cheia: true });
  marcarDestino("apoiar");
  desenharApoiar();
  apoioConferirPendentes();
  // O nome sugerido vem das preferencias; a tela nao espera por elas, porque
  // ler as preferencias pode levar segundos com o Ollama desligado.
  if (!apoio.prefs) {
    fetch("/api/preferencias").then((r) => (r.ok ? r.json() : null)).then((p) => {
      if (!p) return;
      apoio.prefs = p.preferencias || {};
      if (!apoio.nome && $("apoio-tela")) desenharApoiar();
    }).catch(() => null);
  }
}

function nomeSugeridoDoApoio() {
  const p = apoio.prefs || {};
  const escritorio = ((p.escritorio || {}).nome) || "";
  const pessoa = ((p.pessoa || {}).nome) || "";
  if (apoio.como === "escritorio") return escritorio || pessoa;
  return pessoa || escritorio;
}

function emailDoApoio() {
  return (apoio.email || (((apoio.prefs || {}).pessoa || {}).email) || "").trim();
}

/* Pix e pagamento unico; o que se repete sozinho e so no cartao. */
function acertarRecorrencia() {
  if (apoio.forma === "pix") apoio.recorrencia = "unica";
  else if (apoio.recorrencia === "unica") apoio.recorrencia = "mensal";
}

function nomeNaLista() {
  return (apoio.nome || nomeSugeridoDoApoio() || "").trim();
}

function valorDoApoio() {
  if (apoio.valor) return apoio.valor;
  return centavosDe(apoio.outro) / 100;
}

function rotuloDoValor() {
  const v = valorDoApoio();
  if (!v) return "valor a definir";
  const texto = emReais(Math.round(v * 100));
  if (apoio.recorrencia === "mensal") return texto + " por mês";
  if (apoio.recorrencia === "anual") return texto + " por ano";
  return texto + " uma vez";
}

function desenharApoiar() {
  cabecalhoApoiar();
  const miolo = apoio.visao === "lista" ? corpoDaLista() : corpoDeContribuir();
  // O molde editorial das outras telas: uma coluna de 1080px (12-servicos.css).
  $("centro").innerHTML = '<div class="acervo sem-painel apoio-tela" id="apoio-tela"><div class="acervo-principal sv-principal"><div class="sv-medida">' +
    miolo + "</div></div></div>";
  ligarApoiar();
  atualizarPostura();
}

function cabecalhoApoiar() {
  $("conversa-titulo").textContent = apoio.visao === "lista" ? "Quem já apoia" : "Apoiar o projeto";
  $("conversa-meta").textContent = "Software livre · sua contribuição mantém o PAULUS gratuito";
  const botao = (v, r) => {
    const classe = v === apoio.visao ? "ativa" : "";
    return '<button class="' + classe + '" data-apoio-visao="' + v + '">' + r + "</button>";
  };
  $("acoes-tela").innerHTML = '<div class="visoes">' + botao("contribuir", "Contribuir") + botao("lista", "Quem já apoia") + "</div>";
  $("nav-tela").innerHTML = "";
}

/* ---------------------------------------------------------- contribuir */

/* A abertura no desenho de Servicos: o titulo na serifa, o texto curto e a
   faixa com a escolha de agora. O pagamento ainda nao existe - a faixa diz. */
function aberturaDoApoio() {
  const nome = nomeNaLista();
  const item = (rotulo, valor) => '<div class="sv-ficha-item"><span class="sv-kicker">' + rotulo + "</span>" + valor + "</div>";
  return '<header class="sv-abertura"><div class="sv-resumo-topo"><div class="sv-resumo-cabeca"><h2>Ajude o PAULUS a continuar gratuito</h2></div>' +
    '<p class="sv-resumo-corpo">O PAULUS roda na sua máquina, sem assinatura nem cobrança por uso. Quem usa e pode contribuir paga o desenvolvimento e mantém o programa livre para todos. Qualquer valor ajuda; a recorrência ajuda mais.</p></div>' +
    '<div class="sv-ficha">' +
    item("Valor", "<b>" + esc(rotuloDoValor()) + "</b>") +
    item("Forma", "<b>" + (apoio.forma === "pix" ? "Pix" : "Cartão") + "</b>") +
    item("Na lista", '<b class="corta">' + esc(apoio.aparecer ? (nome || "falta o nome") : "anônimo") + "</b>") +
    item("Situação", "<b>" + (apoio.ativa ? "assinatura ativa desde " + esc(apoio.ativa) : apoio.pago ? "Pix recebido em " + esc(apoio.pago)
      : apoio.assinaturaId ? "assinatura esperando o cartão" : "nenhum pagamento ainda") + "</b>") +
    "</div></header>";
}

function corpoDeContribuir() {
  const valor = (v, rotulo) => {
    const classe = "cfg-valor" + (apoio.valor === v ? " on" : "");
    return '<button class="' + classe + '" data-apoio-valor="' + v + '"><b>' + (v ? "R$ " + v : "Outro") + "</b><small>" + rotulo + "</small></button>";
  };
  const seg = (chave, opcoes) => '<div class="cfg-segmento">' + opcoes.map(([v, r]) => {
    const classe = apoio[chave] === v ? "ativa" : "";
    return '<button class="' + classe + '" data-apoio-escolha="' + chave + ":" + v + '">' + r + "</button>";
  }).join("") + "</div>";
  const radio = (chave, v, rotulo) => {
    const classe = "as-radio" + (String(apoio[chave]) === String(v) ? " on" : "");
    return '<label class="' + classe + '" data-apoio-radio="' + chave + ":" + v + '"><i></i><span>' + rotulo + "</span></label>";
  };
  const nome = nomeNaLista();
  const agora = new Date();
  const desde = MESES_CURTOS[agora.getMonth()] + " " + agora.getFullYear();

  const contribuicao = '<div class="ag-campo"><label>Valor</label><div class="cfg-valores">' +
    valor(20, "um café por semana") + valor(40, "mais escolhido") + valor(100, "escritório pequeno") + valor(0, "você define") + "</div>" +
    (apoio.valor ? "" : '<div class="apoio-outro"><input type="text" data-apoio-outro="1" value="' + esc(apoio.outro) + '" placeholder="R$ 0,00"><span class="cfg-explica">qualquer valor ajuda</span></div>') + "</div>" +
    '<div class="ag-duas"><div class="ag-campo"><label>Forma de pagamento</label>' + seg("forma", [["pix", "Pix · uma vez"], ["cartao", "Cartão · assinatura"]]) + "</div>" +
    (apoio.forma === "cartao"
      ? '<div class="ag-campo"><label>Repetir</label>' + seg("recorrencia", [["mensal", "Todo mês"], ["anual", "Todo ano"]]) + "</div>"
      : '<div class="ag-campo"><label>Repetir</label><p class="apoio-nota">O Pix é pago uma vez. Para repetir sozinho, escolha o cartão.</p></div>') + "</div>" +
    '<div class="ag-campo"><label>E-mail para o recibo</label><input type="email" data-apoio-campo="email" value="' + esc(apoio.email) + '" placeholder="' + esc(emailDoApoio() || "nome@exemplo.com.br") + '"></div>' +
    '<p class="cfg-explica">' + (apoio.forma === "pix"
      ? "O QR do Pix aparece aqui, vale por 30 minutos, e a tela avisa quando o pagamento cair. O recibo vem do Mercado Pago."
      : "A página do Mercado Pago abre no navegador: o cartão é digitado lá, nunca aqui. Cancele quando quiser, pelo Mercado Pago.") + "</p>";

  const previa = apoio.aparecer
    ? '<div class="apoio-previa-linha">' + ic("favorite", 18) + "<b>" + esc(nome || "seu nome aqui") + "</b><small>" + esc((apoio.cidade ? apoio.cidade + " · " : "") + "apoiador desde " + desde) + "</small></div>"
    : '<div class="apoio-previa-linha">' + ic("favorite", 18) + "<b>Apoiador anônimo</b><small>conta no total, não é listado</small></div>";
  const lista = '<div class="ag-campo"><label>Aparecer na lista de apoiadores</label><div class="apoio-radios">' +
    radio("aparecer", true, "Sim") + radio("aparecer", false, "Não, prefiro anônimo") + "</div></div>" +
    (apoio.aparecer
      ? '<div class="ag-campo"><label>Como</label><div class="apoio-radios">' + radio("como", "nome", "Meu nome") + radio("como", "escritorio", "Meu escritório") + "</div></div>" +
        '<div class="ag-duas"><div class="ag-campo"><label>Nome na lista</label><input type="text" data-apoio-campo="nome" value="' + esc(apoio.nome) + '" placeholder="' + esc(nomeSugeridoDoApoio() || "como quer aparecer") + '"></div>' +
        '<div class="ag-campo"><label>Cidade (opcional)</label><input type="text" data-apoio-campo="cidade" value="' + esc(apoio.cidade) + '" placeholder="Goiânia"></div></div>'
      : "") +
    '<div class="apoio-previa"><span class="cfg-explica">Como vai aparecer</span>' + previa + "</div>" +
    '<p class="cfg-explica">A lista entra na tela “Sobre” e no site a partir da primeira atualização pública. Só o nome e a cidade aparecem; valor e forma de pagamento nunca.</p>';

  return aberturaDoApoio() +
    '<div class="cfg-grade larga">' +
    cartaoCfg("Sua contribuição", metaCfg("valor, recorrência e forma"), contribuicao) +
    cartaoCfg("Lista de apoiadores", metaCfg(apoio.aparecer ? "com o seu nome" : "anônimo"), lista) +
    "</div>" +
    '<div class="apoio-acao"><span class="cfg-explica">pelo Mercado Pago · ' + esc(rotuloDoValor()) + "</span>" +
    '<button class="primario com-icone" data-apoio-pagar="1"' + (apoio.gerando ? " disabled" : "") + ">" + ic("favorite", 16) +
    (apoio.gerando ? "Abrindo…" : apoio.forma === "pix" ? "Gerar o Pix" : "Assinar no cartão") + "</button></div>";
}

/* ------------------------------------------------------------- a lista */

function corpoDaLista() {
  const chip = (v, r) => {
    const classe = v === apoio.filtro ? "ativa" : "";
    return '<button class="' + classe + '" data-apoio-filtro="' + v + '">' + r + "</button>";
  };
  const nome = nomeNaLista();
  const voce = !!(apoio.pago || apoio.ativa) && apoio.aparecer && nome && (apoio.filtro === "todos" || (apoio.filtro === "escritorios") === (apoio.como === "escritorio")) &&
    (!apoio.termo || nome.toLowerCase().indexOf(apoio.termo.toLowerCase()) >= 0);
  const agora = new Date();
  const desde = MESES_CURTOS[agora.getMonth()] + " " + agora.getFullYear();
  const linhaVoce = '<div class="apoio-nome"><span class="cad-avatar">' + esc(iniciaisDoRemetente(nome)) + '</span><span class="duas-linhas"><b>' + esc(nome) +
    ' <small>· você</small></b><small>' + esc((apoio.cidade ? apoio.cidade + " · " : "") + "entra na próxima atualização · desde " + desde) + "</small></span>" +
    '<span class="cfg-pill">' + (apoio.recorrencia === "mensal" ? "Mantenedor" : (apoio.recorrencia === "unica" ? "Contribuição única" : "Apoiador")) + "</span></div>";
  const secao = (titulo, sub, mostraVoce, vazio) =>
    '<div class="apoio-secao"><div class="apoio-secao-cabeca"><span>' + titulo + "</span><small>" + esc(sub) + "</small></div>" +
    (mostraVoce ? linhaVoce : '<p class="apoio-vazio">' + esc(vazio) + "</p>") + "</div>";
  return '<div class="sv-resumo-topo apoio-lista-topo"><div class="sv-resumo-cabeca"><h2>Quem mantém o PAULUS gratuito</h2></div>' +
    '<p class="sv-resumo-corpo">A lista nasce com a primeira atualização pública, na tela “Sobre” e no site, só com o nome que cada um escolheu. Até lá, ninguém está listado.</p></div>' +
    '<div class="cfg-cartao"><div class="apoio-barra"><label class="busca-tela">' + ic("search", 18) + '<input type="text" data-apoio-termo="1" value="' + esc(apoio.termo) + '" placeholder="Buscar um nome…"></label>' +
    '<div class="visoes">' + chip("todos", "Todos") + chip("escritorios", "Escritórios") + chip("pessoas", "Pessoas") + "</div></div>" +
    secao("Fundadores", "quem apoiar desde o início", false, "Ainda ninguém: os fundadores são os primeiros a apoiar.") +
    secao("Mantenedores", "apoio mensal", voce && apoio.recorrencia === "mensal", "Ainda ninguém com apoio mensal.") +
    secao("Apoiadores", "anual ou contribuição única", voce && apoio.recorrencia !== "mensal", "Ainda ninguém com apoio anual ou único.") +
    '<button class="apoio-mais" data-apoio-visao="contribuir">' + ic("favorite", 18) + '<span class="duas-linhas"><b>' + (nome && apoio.aparecer ? "Alterar como meu nome aparece" : "Seu nome pode ser o primeiro") +
    "</b><small>o seu entra na próxima atualização</small></span></button></div>";
}

/* ------------------------------------------------------------ as acoes */

function ligarApoiar() {
  const cada = (seletor, fn) => document.querySelectorAll(seletor).forEach(fn);
  const clique = (seletor, fn) => cada(seletor, (b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });
  clique("[data-apoio-visao]", (b) => { apoio.visao = b.dataset.apoioVisao; desenharApoiar(); });
  clique("[data-apoio-valor]", (b) => { apoio.valor = Number(b.dataset.apoioValor); guardarApoio(); desenharApoiar(); });
  clique("[data-apoio-escolha]", (b) => { const [chave, v] = b.dataset.apoioEscolha.split(":"); apoio[chave] = v; acertarRecorrencia(); guardarApoio(); desenharApoiar(); });
  clique("[data-apoio-pagar]", () => (apoio.forma === "pix" ? apoioPagarPix() : apoioAssinar()));
  clique("[data-apoio-radio]", (b) => {
    const [chave, v] = b.dataset.apoioRadio.split(":");
    apoio[chave] = chave === "aparecer" ? v === "true" : v;
    guardarApoio();
    desenharApoiar();
  });
  cada("[data-apoio-outro]", (el) => {
    el.oninput = () => { apoio.outro = el.value; guardarApoio(); const r = document.querySelector(".apoio-pix-texto b"); if (r) r.textContent = "Pix " + (apoio.recorrencia === "mensal" ? "recorrente" : "") + " · " + rotuloDoValor(); };
  });
  cada("[data-apoio-campo]", (el) => {
    el.oninput = () => {
      apoio[el.dataset.apoioCampo] = el.value;
      guardarApoio();
      const previa = document.querySelector(".apoio-previa-linha b");
      if (previa) previa.textContent = nomeNaLista() || "seu nome aqui";
      const sub = document.querySelector(".apoio-previa-linha small");
      const agora = new Date();
      if (sub) sub.textContent = (apoio.cidade ? apoio.cidade + " · " : "") + "apoiador desde " + MESES_CURTOS[agora.getMonth()] + " " + agora.getFullYear();
    };
  });
  clique("[data-apoio-filtro]", (b) => { apoio.filtro = b.dataset.apoioFiltro; desenharApoiar(); });
  cada("[data-apoio-termo]", (el) => {
    let t;
    el.oninput = () => { clearTimeout(t); const v = el.value; t = setTimeout(() => { apoio.termo = v.trim(); desenharApoiar(); const campo = document.querySelector("[data-apoio-termo]"); if (campo) { campo.focus(); campo.setSelectionRange(campo.value.length, campo.value.length); } }, 250); };
  });
}

/* ------------------------------------------------------------ pagar */

function apoioConferirAntes() {
  const valor = valorDoApoio();
  if (!valor) { avisoCert("escolha um valor primeiro"); return null; }
  if (valor < 5) { avisoCert("o valor mínimo é R$ 5"); return null; }
  const email = emailDoApoio();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { avisoCert("diga o e-mail para o recibo"); return null; }
  if (apoio.aparecer && !nomeNaLista()) { avisoCert("diga como quer aparecer na lista, ou escolha ficar anônimo"); return null; }
  return { valor: valor, email: email };
}

async function apoioPedir(caminho, corpo) {
  apoio.gerando = true;
  desenharApoiar();
  let r = null;
  try {
    r = await fetch(caminho, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
  } catch (err) { r = null; }
  apoio.gerando = false;
  desenharApoiar();
  if (!r || !r.ok) { avisoCert(r ? await erroDe(r) : "não consegui falar com o programa", { tom: "erro" }); return null; }
  return r.json();
}

/* O Pix: o QR e o copia e cola num pop-up, que pergunta ao site a cada
   5 segundos se o pagamento caiu. Fechar nao cancela o Pix: ele continua
   valendo ate vencer. */
async function apoioPagarPix() {
  const c = apoioConferirAntes();
  if (!c) return;
  const d = await apoioPedir("/api/apoio/pix", c);
  if (!d) return;
  apoio.pixId = d.id;
  guardarApoio();
  const html = '<div class="apoio-pix">' +
    (d.qr_code_base64 ? '<img class="apoio-qr" alt="QR code do Pix" src="data:image/png;base64,' + esc(d.qr_code_base64) + '">' : "") +
    '<div class="apoio-pix-texto"><b>R$ ' + esc(String(d.valor).replace(".", ",")) + " · vale por " + (d.vence_em_minutos || 30) + " minutos</b>" +
    "<p>Abra o app do banco, escolha pagar com Pix e aponte a câmera para o QR — ou copie o código.</p>" +
    '<div class="apoio-codigo"><span>' + esc(d.qr_code || "") + '</span><button type="button" class="sv-ligacao" data-apoio-copiar="1">copiar código</button></div>' +
    '<p class="apoio-estado" id="apoio-pix-estado"><span class="indicador"></span>esperando o pagamento…</p></div></div>';
  let pago = false;
  const conferir = async () => {
    try {
      const r = await fetch("/api/apoio/pix/" + encodeURIComponent(d.id));
      if (!r.ok) return false;
      const s = await r.json();
      if (!s.pago) return false;
    } catch (err) { return false; }
    pago = true;
    apoio.pago = new Date().toLocaleDateString("pt-BR");
    apoio.pixId = "";
    guardarApoio();
    const estado = document.getElementById("apoio-pix-estado");
    if (estado) { estado.classList.add("ok"); estado.innerHTML = ic("check_circle", 16) + "Pix recebido — obrigado por manter o PAULUS gratuito!"; }
    return true;
  };
  let relogio = null;
  const girar = () => { relogio = setTimeout(async () => { if (!(await conferir())) girar(); }, 5000); };
  setTimeout(() => {
    const copiar = document.querySelector("[data-apoio-copiar]");
    if (copiar) copiar.onclick = () => copiarTexto(d.qr_code || "", "código do Pix copiado");
  }, 0);
  girar();
  await dialogo({
    titulo: "Pix de apoio", contexto: "Apoiar o projeto", html: html, larga: true,
    cancelar: "Fechar", confirmar: "Já paguei",
    aoConfirmar: async () => {
      if (pago) { const f = document.querySelector('#veu-dialogo [data-dialogo="cancelar"]'); if (f) f.click(); return; }
      if (!(await conferir())) avisoCert("o pagamento ainda não caiu — às vezes leva alguns segundos");
    },
  });
  clearTimeout(relogio);
  desenharApoiar();
}

/* O cartao: a assinatura e criada no Mercado Pago e a pagina dele abre no
   navegador. O PAULUS nao ve o cartao - e so fica sabendo pelo recibo. */
async function apoioAssinar() {
  const c = apoioConferirAntes();
  if (!c) return;
  const d = await apoioPedir("/api/apoio/assinatura", Object.assign({ frequencia: apoio.recorrencia }, c));
  if (!d) return;
  if (!d.link) { avisoCert("o Mercado Pago não devolveu a página da assinatura", { tom: "erro" }); return; }
  window.open(d.link, "_blank");
  apoio.assinado = new Date().toLocaleDateString("pt-BR");
  apoio.assinaturaId = d.id;
  apoio.ativa = "";
  guardarApoio();
  desenharApoiar();
  await dialogo({
    titulo: "Termine no navegador", contexto: "Apoiar o projeto",
    texto: "A página do Mercado Pago abriu no navegador. Ponha o cartão lá para ativar a assinatura de " + rotuloDoValor() + ".\n" +
      "Quando o Mercado Pago confirmar, esta tela mostra a assinatura ativa. O recibo chega por e-mail, e é por lá que se cancela quando quiser.",
    cancelar: "Fechar", confirmar: "Abrir de novo",
    aoConfirmar: () => window.open(d.link, "_blank"),
  });
}

/* Ao abrir a tela: o Pix gerado e nao pago, e a assinatura criada e ainda
   sem cartao, sao conferidos no site (que guarda o que o Mercado Pago
   confirmou pelo aviso). Sem internet, fica como estava. */
async function apoioConferirPendentes() {
  let mudou = false;
  if (apoio.pixId) {
    try {
      const r = await fetch("/api/apoio/pix/" + encodeURIComponent(apoio.pixId));
      if (r.ok) {
        const d = await r.json();
        if (d.pago) { apoio.pago = new Date().toLocaleDateString("pt-BR"); apoio.pixId = ""; mudou = true; }
      }
    } catch (err) { /* sem internet: confere na proxima vez */ }
  }
  if (apoio.assinaturaId && !apoio.ativa) {
    try {
      const r = await fetch("/api/apoio/assinatura/" + encodeURIComponent(apoio.assinaturaId));
      if (r.ok) {
        const d = await r.json();
        if (d.ativa) { apoio.ativa = new Date().toLocaleDateString("pt-BR"); mudou = true; }
        else if (d.situacao === "cancelled") { apoio.assinaturaId = ""; mudou = true; }
      }
    } catch (err) { /* sem internet: confere na proxima vez */ }
  }
  if (!mudou) return;
  guardarApoio();
  if ($("apoio-tela")) desenharApoiar();
}
