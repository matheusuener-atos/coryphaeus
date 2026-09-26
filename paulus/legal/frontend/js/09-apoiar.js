/* ------------------------------------------------------------- apoiar */
/*
   Apoiar o projeto (docs/ui/03-telas-desktop.md, A14): Contribuir e o
   mural de quem apoia. O pagamento e o do Mercado Pago, sempre pelo site: o
   programa pede a /api/apoio (src/apoio.py), que repassa ao Worker do
   paulus.ia.br - so ele tem a chave do Mercado Pago.
     Pix     pagamento unico: o QR aparece aqui e a tela acompanha ate cair
     cartao  assinatura mensal: a pagina do Mercado Pago abre no navegador e o
             cartao e digitado la, nunca aqui. Enquanto ela existir, a tela
             mostra o botao de interromper - que antes sugere diminuir.
   A categoria no mural vem do que foi PAGO e confirmado, nunca do que esta
   escolhido no formulario agora. O mural publico ainda nao existe. Abre
   pelo coracao do trilho.
*/

const apoio = {
  visao: "contribuir", valor: 50, outro: "", recorrencia: "mensal", forma: "pix",
  aparecer: true, como: "escritorio", nome: "", cidade: "",
  email: "", gerando: false, editandoLista: null,
  // O que o Mercado Pago confirmou: a data do ultimo Pix pago (e o valor), a
  // data em que a assinatura ficou ativa (e o valor mensal dela).
  pago: "", pagoValor: 0, ativa: "", ativaValor: 0,
  // O Pix gerado e ainda nao pago; a assinatura (criada ou ativa), a chave
  // dela - so com ela se diminui ou interrompe - e o valor pedido.
  pixId: "", assinaturaId: "", assinaturaChave: "", assinaturaValor: 0,
  // Para o extrato: cada Pix confirmado aqui, e as assinaturas ja
  // interrompidas (as cobrancas delas continuam no extrato).
  historico: [], assinaturasAntigas: [],
  lido: false,
};

const APOIO_GUARDADO = ["valor", "outro", "forma", "aparecer", "como", "nome", "cidade", "email",
  "pago", "pagoValor", "ativa", "ativaValor", "pixId", "assinaturaId", "assinaturaChave", "assinaturaValor",
  "historico", "assinaturasAntigas"];
const APOIO_MINIMO = 5;
const APOIO_MAXIMO = 50000;
// Os valores da tabela; 0 e o "Outro valor", que ja vem com R$ 1.000,00.
const APOIO_VALORES = [25, 50, 100, 500];
const APOIO_OUTRO_PADRAO = "1.000,00";

function lerApoioGuardado() {
  if (apoio.lido) return;
  apoio.lido = true;
  try {
    const g = JSON.parse(localStorage.getItem("paulus.apoio") || "null");
    if (g && typeof g === "object") APOIO_GUARDADO.forEach((k) => { if (g[k] !== undefined) apoio[k] = g[k]; });
    // Valor guardado de uma tabela antiga (20, 40...) volta para o mais escolhido.
    if (apoio.valor && APOIO_VALORES.indexOf(apoio.valor) < 0) apoio.valor = 50;
    // O Pix confirmado antes de existir o historico entra nele uma vez.
    if (!Array.isArray(apoio.historico)) apoio.historico = [];
    if (!Array.isArray(apoio.assinaturasAntigas)) apoio.assinaturasAntigas = [];
    if (apoio.pago && !apoio.historico.length) apoio.historico.push({ data: apoio.pago, valor: apoio.pagoValor || 0, id: "" });
  } catch (err) { /* sem memoria do navegador, tudo bem */ }
  acertarRecorrencia();
}

function guardarApoio() {
  try {
    const g = {};
    APOIO_GUARDADO.forEach((k) => { g[k] = apoio[k]; });
    localStorage.setItem("paulus.apoio", JSON.stringify(g));
  } catch (err) { /* sem memoria do navegador, tudo bem */ }
}

function mostrarApoiar(visao) {
  if (visao) apoio.visao = visao;
  lerApoioGuardado();
  abrirTela("Apoiar o projeto", { cheia: true });
  marcarDestino("apoiar");
  desenharApoiar();
  apoioConferirPendentes();
}

/* Pix e pagamento unico; o cartao e sempre mensal. */
function acertarRecorrencia() {
  apoio.recorrencia = apoio.forma === "pix" ? "unica" : "mensal";
}

function nomeNaLista() { return (apoio.nome || "").trim(); }

function valorDoApoio() {
  if (apoio.valor) return apoio.valor;
  return centavosDe(apoio.outro) / 100;
}

function rotuloDoValor() {
  const v = valorDoApoio();
  if (!v) return "valor a definir";
  const texto = emReais(Math.round(v * 100));
  return apoio.recorrencia === "mensal" ? texto + " por mês" : texto + " uma vez";
}

/* A categoria de quem apoia, pelo que foi confirmado. Sem nada confirmado,
   nenhuma - mesmo que o formulario esteja no cartao. */
function categoriaDoApoio() {
  if (apoio.ativa) return "mensal";
  if (apoio.pago) return "unica";
  return "";
}

function assinaturaPendente() { return !!apoio.assinaturaId && !apoio.ativa; }

function desenharApoiar() {
  cabecalhoApoiar();
  const miolo = apoio.visao === "lista" ? corpoDoMural() : corpoDeContribuir();
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

function aberturaDoApoio() {
  const pix = apoio.pago && !apoio.ativa
    ? '<p class="apoio-situacao">' + ic("favorite", 16) + "Seu Pix de apoio chegou em " + esc(apoio.pago) + ". Obrigado por manter o PAULUS gratuito.</p>"
    : "";
  return '<header class="sv-resumo-topo"><div class="sv-resumo-cabeca"><h2>Ajude o PAULUS a continuar gratuito</h2></div>' +
    '<p class="sv-resumo-corpo">O PAULUS roda na sua máquina, sem assinatura nem cobrança por uso. Quem usa e pode contribuir paga o desenvolvimento e mantém o programa livre para todos. Todo valor ajuda; a recorrência ajuda mais.</p>' +
    pix + extratoDoApoio() + "</header>";
}

/* O extrato em PDF, assim que houver algum pagamento ou assinatura. */
function extratoDoApoio() {
  if (!apoio.historico.length && !apoio.assinaturaId && !apoio.assinaturasAntigas.length) return "";
  return '<div class="apoio-extrato"><button class="com-icone" data-apoio-extrato="1">' + ic("download", 16) + "Baixar extrato de apoio</button>" +
    "<small>cada pagamento, a natureza do apoio e o que a lei diz — em PDF</small></div>";
}

/* A assinatura, enquanto existir: o valor, desde quando, e o botao de
   interromper sempre a vista. */
function cartaoDaAssinatura() {
  if (!apoio.assinaturaId) return "";
  const valor = apoio.ativa ? apoio.ativaValor : apoio.assinaturaValor;
  const corpo = '<div class="apoio-assinatura">' +
    '<span class="apoio-assinatura-coracao">' + ic("favorite", 20) + "</span>" +
    '<span class="duas-linhas"><b>' + emReais(Math.round((valor || 0) * 100)) + " por mês</b><small>" +
    (apoio.ativa ? "ativa desde " + esc(apoio.ativa) + " · no cartão, pelo Mercado Pago"
      : "esperando o cartão na página do Mercado Pago · esta tela confere sozinha") + "</small></span>" +
    '<button class="com-icone apoio-interromper" data-apoio-interromper="1">' + ic("pause", 16) + "Interromper assinatura</button></div>";
  return cartaoCfg("Sua assinatura", metaCfg(apoio.ativa ? "ativa" : "esperando o cartão"), corpo);
}

function corpoDeContribuir() {
  const valor = (v, rotulo) => {
    const classe = "cfg-valor" + (apoio.valor === v ? " on" : "");
    return '<button class="' + classe + '" data-apoio-valor="' + v + '"><b>' + (v ? "R$ " + v : "Outro") + "</b><small>" + rotulo + "</small></button>";
  };
  const forma = (v, titulo, sub) => {
    const classe = "cfg-valor apoio-forma" + (apoio.forma === v ? " on" : "");
    return '<button class="' + classe + '" data-apoio-escolha="forma:' + v + '"><b>' + titulo + "</b><small>" + sub + "</small></button>";
  };

  // A forma primeiro, em destaque.
  const contribuicao = '<div class="ag-campo"><label>Como você quer apoiar</label><div class="cfg-valores apoio-formas">' +
    forma("pix", "Pix · uma vez", "QR code na hora, pago pelo app do banco") +
    forma("cartao", "Cartão · todo mês", "repete sozinho; interrompa quando quiser") + "</div></div>" +
    '<div class="ag-campo"><label>Valor' + (apoio.forma === "cartao" ? " por mês" : "") + '</label><div class="cfg-valores">' +
    valor(25, "um almoço") + valor(50, "mais escolhido") + valor(100, "escritório pequeno") + valor(500, "escritório parceiro") + valor(0, "você define") + "</div>" +
    (apoio.valor ? "" : '<div class="apoio-outro"><span class="apoio-moeda">R$</span><input type="text" inputmode="decimal" data-apoio-outro="1" value="' + esc(apoio.outro) +
      '" placeholder="' + APOIO_OUTRO_PADRAO + '" maxlength="10"><span class="cfg-explica">Digite o valor que quiser, a partir de R$ 5,00.</span></div>') + "</div>" +
    '<div class="ag-campo"><label>E-mail para o recibo</label><input type="email" data-apoio-campo="email" value="' + esc(apoio.email) + '" placeholder="email@email.com"></div>' +
    '<p class="cfg-explica">' + (apoio.forma === "pix"
      ? "O QR do Pix aparece aqui, vale por 30 minutos, e a tela avisa quando o pagamento cair. O recibo vem do Mercado Pago."
      : "A página do Mercado Pago abre no navegador: o cartão é digitado lá, nunca aqui. A cobrança se repete todo mês; o botão de interromper fica nesta tela.") + "</p>";

  // Com uma assinatura ja existindo, o cartao de novo nao cria outra.
  const cartaoBloqueado = apoio.forma === "cartao" && !!apoio.assinaturaId;
  return aberturaDoApoio() +
    '<div class="cfg-grade larga">' +
    cartaoDaAssinatura() +
    cartaoCfg("Sua contribuição", metaCfg("forma, valor e recibo"), contribuicao) +
    cartaoDaLista() +
    "</div>" +
    '<div class="apoio-acao"><span class="cfg-explica">' + (cartaoBloqueado ? "você já tem uma assinatura — mude ou interrompa por ela, acima" : "pelo Mercado Pago · " + esc(rotuloDoValor())) + "</span>" +
    '<button class="primario com-icone" data-apoio-pagar="1"' + (apoio.gerando || cartaoBloqueado ? " disabled" : "") + ">" + ic("favorite", 16) +
    (apoio.gerando ? "Abrindo…" : apoio.forma === "pix" ? "Gerar o Pix" : "Assinar no cartão") + "</button></div>";
}

/* Como aparece no mural: so leitura, com "Editar"; editando, os campos e
   "Pronto". Sem nome ainda (e querendo aparecer), abre editando. */
function cartaoDaLista() {
  const nome = nomeNaLista();
  if (apoio.editandoLista === null) apoio.editandoLista = apoio.aparecer && !nome;
  const agora = new Date();
  const desde = MESES_CURTOS[agora.getMonth()] + " " + agora.getFullYear();
  const previa = apoio.aparecer
    ? '<div class="apoio-previa-linha">' + ic("favorite", 18) + "<b>" + esc(nome || "Exemplo") + "</b><small>" + esc((apoio.cidade ? apoio.cidade + " · " : "") + "apoiador desde " + desde) + "</small></div>"
    : '<div class="apoio-previa-linha">' + ic("favorite", 18) + "<b>Apoiador anônimo</b><small>conta no total, não aparece no mural</small></div>";
  const rodape = '<p class="cfg-explica">O mural entra na tela “Sobre” e no site a partir da primeira atualização pública. Só o nome e a cidade aparecem; valor e forma de pagamento nunca.</p>';

  if (!apoio.editandoLista) {
    const corpo = '<div class="apoio-previa"><span class="cfg-explica">Como você aparece</span>' + previa + "</div>" +
      '<div class="cfg-botoes"><button class="com-icone" data-apoio-editar-lista="1">' + ic("edit", 16) + "Editar como apareço</button></div>" + rodape;
    return cartaoCfg("Mural de apoiadores", metaCfg(apoio.aparecer ? "com o seu nome" : "anônimo"), corpo);
  }
  const radio = (chave, v, rotulo) => {
    const classe = "as-radio" + (String(apoio[chave]) === String(v) ? " on" : "");
    return '<label class="' + classe + '" data-apoio-radio="' + chave + ":" + v + '"><i></i><span>' + rotulo + "</span></label>";
  };
  const corpo = '<div class="ag-campo"><label>Aparecer no mural de apoiadores</label><div class="apoio-radios">' +
    radio("aparecer", true, "Sim") + radio("aparecer", false, "Não, prefiro anônimo") + "</div></div>" +
    (apoio.aparecer
      ? '<div class="ag-campo"><label>Como</label><div class="apoio-radios">' + radio("como", "nome", "Meu nome") + radio("como", "escritorio", "Meu escritório") + "</div></div>" +
        '<div class="ag-duas"><div class="ag-campo"><label>Nome no mural</label><input type="text" data-apoio-campo="nome" value="' + esc(apoio.nome) + '" placeholder="Exemplo" maxlength="60"></div>' +
        '<div class="ag-campo"><label>Cidade (opcional)</label><input type="text" data-apoio-campo="cidade" value="' + esc(apoio.cidade) + '" placeholder="Goiânia" maxlength="40"></div></div>'
      : "") +
    '<div class="apoio-previa"><span class="cfg-explica">Como vai aparecer</span>' + previa + "</div>" +
    '<div class="cfg-botoes"><button class="primario com-icone" data-apoio-pronto-lista="1">' + ic("check", 16) + "Pronto</button></div>" + rodape;
  return cartaoCfg("Mural de apoiadores", metaCfg("editando"), corpo);
}

/* ------------------------------------------------------------- o mural */

/* Um mural so, sem divisoes: cada apoiador e um cartaz com as iniciais, o
   nome, a cidade e desde quando. Enquanto o mural publico nao existe, so o
   seu (quando o pagamento foi confirmado) e o convite. */
function corpoDoMural() {
  const nome = nomeNaLista();
  const categoria = categoriaDoApoio();
  const voce = !!categoria && apoio.aparecer && nome;
  const desde = apoio.ativa || apoio.pago || "";
  const cartaz = voce
    ? '<article class="apoio-cartaz voce"><span class="apoio-cartaz-iniciais">' + esc(iniciaisDoRemetente(nome)) + "</span>" +
      '<b class="apoio-cartaz-nome">' + esc(nome) + "</b>" +
      (apoio.cidade ? '<span class="apoio-cartaz-cidade">' + esc(apoio.cidade) + "</span>" : "") +
      '<span class="apoio-cartaz-desde">' + (categoria === "mensal" ? "apoia todo mês" : "apoiou com Pix") + (desde ? " · desde " + esc(desde) : "") + "</span>" +
      '<span class="apoio-cartaz-voce">você</span></article>'
    : "";
  const convite = '<button class="apoio-cartaz convite" data-apoio-editar-lista="1"><span class="apoio-cartaz-iniciais">' + ic(voce ? "edit" : "favorite", 22) + "</span>" +
    '<b class="apoio-cartaz-nome">' + (voce ? "Mudar como apareço" : "Seu nome aqui") + "</b>" +
    '<span class="apoio-cartaz-desde">' + (voce ? "nome, cidade ou anônimo" : "apoie e entre no mural") + "</span></button>";
  const anonimo = categoria && !apoio.aparecer
    ? '<p class="apoio-situacao">' + ic("favorite", 16) + "Você apoia sem aparecer no mural — e conta no total. Obrigado.</p>" : "";
  return '<header class="sv-resumo-topo"><div class="sv-resumo-cabeca"><h2>Quem mantém o PAULUS gratuito</h2></div>' +
    '<p class="sv-resumo-corpo">Cada nome aqui ajuda a pagar o desenvolvimento de um programa que roda de graça na máquina de qualquer escritório. O mural público nasce na primeira atualização, na tela “Sobre” e no site.</p>' +
    anonimo + "</header>" +
    '<div class="apoio-mural">' + cartaz + convite + "</div>";
}

/* ------------------------------------------------------------ as acoes */

/* "Outro valor": so numeros, ponto de milhar e virgula dos centavos - nada
   de sinal, letra ou valor negativo. Ao sair do campo, fica formatado. */
function limparValorDigitado(texto) {
  const so = String(texto || "").replace(/[^\d,.]/g, "");
  const [inteiro, ...resto] = so.split(",");
  return resto.length ? inteiro + "," + resto.join("").slice(0, 2) : inteiro;
}

function formatarValorDigitado(texto) {
  const c = centavosDe(texto);
  return c ? emReais(c).replace("R$ ", "") : "";
}

function ligarApoiar() {
  const cada = (seletor, fn) => document.querySelectorAll(seletor).forEach(fn);
  const clique = (seletor, fn) => cada(seletor, (b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });
  clique("[data-apoio-visao]", (b) => { apoio.visao = b.dataset.apoioVisao; desenharApoiar(); });
  clique("[data-apoio-valor]", (b) => {
    apoio.valor = Number(b.dataset.apoioValor);
    if (!apoio.valor && !centavosDe(apoio.outro)) apoio.outro = APOIO_OUTRO_PADRAO;
    guardarApoio();
    desenharApoiar();
    const campo = document.querySelector("[data-apoio-outro]");
    if (campo) { campo.focus(); campo.select(); }
  });
  clique("[data-apoio-escolha]", (b) => { const [chave, v] = b.dataset.apoioEscolha.split(":"); apoio[chave] = v; acertarRecorrencia(); guardarApoio(); desenharApoiar(); });
  clique("[data-apoio-pagar]", () => (apoio.forma === "pix" ? apoioPagarPix() : apoioAssinar()));
  clique("[data-apoio-interromper]", () => apoioInterromper());
  clique("[data-apoio-extrato]", () => apoioBaixarExtrato());
  clique("[data-apoio-editar-lista]", () => { apoio.visao = "contribuir"; apoio.editandoLista = true; desenharApoiar(); });
  clique("[data-apoio-pronto-lista]", () => {
    if (apoio.aparecer && !nomeNaLista()) { avisoCert("diga o nome para o mural, ou escolha ficar anônimo"); return; }
    apoio.editandoLista = false;
    guardarApoio();
    desenharApoiar();
  });
  clique("[data-apoio-radio]", (b) => {
    const [chave, v] = b.dataset.apoioRadio.split(":");
    apoio[chave] = chave === "aparecer" ? v === "true" : v;
    guardarApoio();
    desenharApoiar();
  });
  cada("[data-apoio-outro]", (el) => {
    el.oninput = () => {
      const limpo = limparValorDigitado(el.value);
      if (limpo !== el.value) el.value = limpo;
      apoio.outro = limpo;
      guardarApoio();
      const rotulo = document.querySelector(".apoio-acao .cfg-explica");
      if (rotulo) rotulo.textContent = "pelo Mercado Pago · " + rotuloDoValor();
    };
    el.onblur = () => { el.value = formatarValorDigitado(el.value); apoio.outro = el.value; guardarApoio(); };
  });
  cada("[data-apoio-campo]", (el) => {
    el.oninput = () => {
      apoio[el.dataset.apoioCampo] = el.value;
      guardarApoio();
      const previa = document.querySelector(".apoio-previa-linha b");
      if (previa && apoio.aparecer) previa.textContent = nomeNaLista() || "Exemplo";
      const sub = document.querySelector(".apoio-previa-linha small");
      const agora = new Date();
      if (sub && apoio.aparecer) sub.textContent = (apoio.cidade ? apoio.cidade + " · " : "") + "apoiador desde " + MESES_CURTOS[agora.getMonth()] + " " + agora.getFullYear();
    };
  });
}

/* ------------------------------------------------------------ pagar */

function apoioConferirAntes() {
  const valor = valorDoApoio();
  if (!valor) { avisoCert("escolha um valor primeiro"); return null; }
  if (!(valor >= APOIO_MINIMO)) { avisoCert("o valor precisa ser a partir de R$ 5,00"); return null; }
  if (valor > APOIO_MAXIMO) { avisoCert("para apoiar com mais de R$ 50.000,00, fale com a gente pelo site"); return null; }
  const email = (apoio.email || "").trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { avisoCert("diga o e-mail para o recibo"); return null; }
  if (apoio.aparecer && !nomeNaLista()) {
    apoio.editandoLista = true;
    desenharApoiar();
    avisoCert("diga como quer aparecer no mural, ou escolha ficar anônimo");
    return null;
  }
  return { valor: valor, email: email };
}

async function apoioPedir(caminho, corpo, redesenhar) {
  if (redesenhar !== false) { apoio.gerando = true; desenharApoiar(); }
  let r = null;
  try {
    r = await fetch(caminho, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
  } catch (err) { r = null; }
  if (redesenhar !== false) { apoio.gerando = false; desenharApoiar(); }
  if (!r || !r.ok) { avisoCert(r ? await erroDe(r) : "não consegui falar com o programa", { tom: "erro" }); return null; }
  return r.json();
}

/* O Pix: o QR e o copia e cola num pop-up, que pergunta ao site a cada
   5 segundos se o pagamento caiu. Caiu, o pop-up fecha sozinho e vem o
   agradecimento. Fechar antes nao cancela o Pix: ele vale ate vencer, e a
   tela confere de novo na proxima vez que abrir. */
async function apoioPagarPix() {
  const c = apoioConferirAntes();
  if (!c) return;
  const d = await apoioPedir("/api/apoio/pix", c);
  if (!d) return;
  apoio.pixId = d.id;
  guardarApoio();
  const html = '<div class="apoio-pix">' +
    (d.qr_code_base64 ? '<img class="apoio-qr" alt="QR code do Pix" src="data:image/png;base64,' + esc(d.qr_code_base64) + '">' : "") +
    '<div class="apoio-pix-texto"><b>' + emReais(Math.round(Number(d.valor) * 100)) + " · vale por " + (d.vence_em_minutos || 30) + " minutos</b>" +
    "<p>Abra o app do banco, escolha pagar com Pix e aponte a câmera para o QR — ou copie o código.</p>" +
    '<div class="apoio-codigo"><span>' + esc(d.qr_code || "") + '</span><button type="button" class="sv-ligacao" data-apoio-copiar="1">copiar código</button></div>' +
    '<p class="apoio-estado" id="apoio-pix-estado"><span class="indicador"></span>esperando o pagamento…</p></div></div>';
  let pago = false;
  const fecharPopup = () => { const f = document.querySelector('#veu-dialogo [data-dialogo="cancelar"]'); if (f) f.click(); };
  const conferir = async () => {
    try {
      const r = await fetch("/api/apoio/pix/" + encodeURIComponent(d.id));
      if (!r.ok) return false;
      const s = await r.json();
      if (!s.pago) return false;
    } catch (err) { return false; }
    pago = true;
    apoioRegistrarPix(Number(d.valor), d.id);
    const estado = document.getElementById("apoio-pix-estado");
    if (estado) { estado.classList.add("ok"); estado.innerHTML = ic("check_circle", 16) + "Pix recebido!"; }
    setTimeout(fecharPopup, 1400);
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
      if (pago) { fecharPopup(); return; }
      if (!(await conferir())) avisoCert("o pagamento ainda não caiu — às vezes leva alguns segundos");
    },
  });
  clearTimeout(relogio);
  desenharApoiar();
  if (pago) apoioAgradecer("pix", Number(d.valor));
}

function apoioRegistrarPix(valor, id) {
  apoio.pago = new Date().toLocaleDateString("pt-BR");
  apoio.pagoValor = valor;
  if (!apoio.historico.some((h) => id && h.id === id)) apoio.historico.push({ data: new Date().toISOString(), valor: valor, id: id || "" });
  apoio.pixId = "";
  guardarApoio();
}

/* O extrato: o programa junta os Pix daqui e as cobrancas do cartao (que o
   site busca no Mercado Pago) num PDF, e salva onde a pessoa escolher. */
async function apoioBaixarExtrato() {
  const assinaturas = [];
  if (apoio.assinaturaId && apoio.assinaturaChave) {
    assinaturas.push({ id: apoio.assinaturaId, chave: apoio.assinaturaChave, valor: apoio.ativa ? apoio.ativaValor : apoio.assinaturaValor, atual: true });
  }
  apoio.assinaturasAntigas.forEach((a) => assinaturas.push(a));
  avisoCert("montando o extrato…");
  // Um Pix de versao antiga (sem numero nem valor) e completado antes.
  if (await apoioRecuperarPixAntigos()) { guardarApoio(); desenharApoiar(); }
  const d = await apoioPedir("/api/apoio/extrato", {
    nome: nomeNaLista(), email: apoio.email, pix: apoio.historico, assinaturas: assinaturas,
  }, false);
  if (!d) return;
  await baixarArquivo(d.caminho);
}

/* O agradecimento, depois que o Mercado Pago confirmou. */
async function apoioAgradecer(tipo, valor) {
  const nome = nomeNaLista();
  const oque = tipo === "pix"
    ? "Seu Pix de " + emReais(Math.round(valor * 100)) + " chegou."
    : "Sua assinatura de " + emReais(Math.round(valor * 100)) + " por mês está ativa.";
  const lista = apoio.aparecer && nome
    ? "<p>Seu nome — <b>" + esc(nome) + "</b> — entra no mural de apoiadores na próxima atualização do PAULUS.</p>"
    : "<p>Você apoia sem aparecer no mural, e conta no total de apoiadores.</p>";
  const ver = await confirmar({
    titulo: "Obrigado!", contexto: "Apoiar o projeto",
    html: '<div class="apoio-obrigado"><span class="apoio-obrigado-coracao">' + ic("favorite", 28) + "</span>" +
      "<p><b>" + esc(oque) + "</b></p>" +
      "<p>É com apoio assim que o PAULUS continua livre e gratuito, e roda na máquina de cada escritório sem cobrar por uso. De verdade: muito obrigado.</p>" +
      lista + "<p class=\"cfg-explica\">O recibo chega por e-mail, pelo Mercado Pago.</p></div>",
    cancelar: "Fechar", confirmar: "Ver o mural", sucesso: true,
  });
  if (ver) { apoio.visao = "lista"; desenharApoiar(); }
}

/* O cartao: a assinatura mensal e criada no Mercado Pago e a pagina dele
   abre no navegador. Ela so conta (no mural, na categoria) depois que o
   Mercado Pago confirma que o cartao foi posto - "criada" nao e "ativa". */
async function apoioAssinar() {
  if (apoio.assinaturaId) { avisoCert("você já tem uma assinatura — mude ou interrompa por ela"); return; }
  const c = apoioConferirAntes();
  if (!c) return;
  const d = await apoioPedir("/api/apoio/assinatura", c);
  if (!d) return;
  if (!d.link) { avisoCert("o Mercado Pago não devolveu a página da assinatura", { tom: "erro" }); return; }
  window.open(d.link, "_blank");
  apoio.assinaturaId = d.id;
  apoio.assinaturaChave = d.chave || "";
  apoio.assinaturaValor = c.valor;
  apoio.ativa = "";
  guardarApoio();
  desenharApoiar();
  await dialogo({
    titulo: "Termine no navegador", contexto: "Apoiar o projeto",
    texto: "A página do Mercado Pago abriu no navegador. Ponha o cartão lá para ativar o apoio de " + rotuloDoValor() + ".\n" +
      "Quando o Mercado Pago confirmar, esta tela mostra a assinatura ativa. Para interromper, o botão fica aqui mesmo, no cartão “Sua assinatura”.",
    cancelar: "Fechar", confirmar: "Abrir de novo",
    aoConfirmar: () => window.open(d.link, "_blank"),
  });
}

/* ------------------------------------------------------ interromper */

/* Quantos meses desde uma data "dd/mm/aaaa" (pelo menos 1). */
function mesesDesde(data) {
  const [d, m, a] = String(data || "").split("/").map(Number);
  if (!a) return 0;
  const hoje = new Date();
  return Math.max(1, (hoje.getFullYear() - a) * 12 + (hoje.getMonth() + 1 - m) + (hoje.getDate() >= d ? 0 : -1) + 1);
}

/* Interromper: primeiro, com carinho, a sugestao de diminuir - o campo ja
   vem 10% menor. So se a pessoa insistir, interrompe; e agradece pelo tempo
   em que apoiou (ou, se nem chegou a comecar, convida a voltar um dia). */
async function apoioInterromper() {
  const atual = apoio.ativa ? apoio.ativaValor : apoio.assinaturaValor;
  const sugerido = Math.max(APOIO_MINIMO, Math.floor(atual * 0.9 * 100) / 100);
  let interromperMesmo = false;
  setTimeout(() => {
    const b = document.querySelector("[data-apoio-interromper-mesmo]");
    if (!b) return;
    b.onclick = () => { interromperMesmo = true; const f = document.querySelector('#veu-dialogo [data-dialogo="cancelar"]'); if (f) f.click(); };
  }, 0);
  const podeDiminuir = !!apoio.ativa && atual > APOIO_MINIMO;
  const r = await dialogo({
    titulo: "Antes de ir…", contexto: "Sua assinatura", larga: true,
    html: '<div class="apoio-obrigado apoio-antes"><span class="apoio-obrigado-coracao">' + ic("favorite", 28) + "</span>" +
      (apoio.ativa
        ? "<p>Desde " + esc(apoio.ativa) + ", o seu apoio ajuda a pagar cada linha do PAULUS — um programa que roda de graça na máquina de muitos escritórios.</p>" +
          (podeDiminuir ? "<p><b>Se o valor pesou, que tal diminuir em vez de parar?</b> A partir de R$ 5,00 por mês, continua fazendo diferença.</p>" : "")
        : "<p>Sua assinatura ainda espera o cartão, e nada foi cobrado. Tem certeza de que quer desistir dela?</p>") + "</div>",
    campo: podeDiminuir ? { rotulo: "Novo valor por mês", valor: emReais(Math.round(sugerido * 100)).replace("R$ ", ""), icone: "payments", dica: "já vem 10% menor — mude como quiser, a partir de R$ 5,00" } : null,
    rodape: '<button type="button" class="apoio-interromper-mesmo" data-apoio-interromper-mesmo="1">Interromper mesmo assim</button>',
    cancelar: "Manter como está", confirmar: podeDiminuir ? "Diminuir o valor" : "Manter a assinatura", sucesso: true,
  });
  if (r && r.ok && podeDiminuir) return apoioDiminuir(centavosDe(r.valor) / 100, atual);
  if (interromperMesmo) return apoioInterromperDeVez();
}

async function apoioDiminuir(novo, atual) {
  if (!(novo >= APOIO_MINIMO)) { avisoCert("o valor precisa ser a partir de R$ 5,00"); return; }
  if (novo >= atual) { avisoCert("o novo valor precisa ser menor que " + emReais(Math.round(atual * 100))); return; }
  const d = await apoioPedir("/api/apoio/assinatura/" + encodeURIComponent(apoio.assinaturaId) + "/valor",
    { chave: apoio.assinaturaChave, valor: novo }, false);
  if (!d) return;
  apoio.ativaValor = novo;
  guardarApoio();
  desenharApoiar();
  await confirmar({
    titulo: "Obrigado por continuar!", contexto: "Sua assinatura",
    html: '<div class="apoio-obrigado"><span class="apoio-obrigado-coracao">' + ic("favorite", 28) + "</span>" +
      "<p><b>Seu apoio agora é de " + emReais(Math.round(novo * 100)) + " por mês.</b></p>" +
      "<p>Ficar, mesmo com menos, faz toda a diferença. O próximo mês já vem com o valor novo, pelo Mercado Pago.</p></div>",
    cancelar: "Fechar", confirmar: "Ver o mural", sucesso: true,
  }).then((ver) => { if (ver) { apoio.visao = "lista"; desenharApoiar(); } });
}

async function apoioInterromperDeVez() {
  const ativa = apoio.ativa;
  if (apoio.assinaturaChave) {
    const d = await apoioPedir("/api/apoio/assinatura/" + encodeURIComponent(apoio.assinaturaId) + "/interromper",
      { chave: apoio.assinaturaChave }, false);
    if (!d) return;
  }
  // A interrompida continua no extrato (as cobrancas que ja teve).
  if (ativa && apoio.assinaturaChave) apoio.assinaturasAntigas.push({ id: apoio.assinaturaId, chave: apoio.assinaturaChave });
  // Sem chave (assinatura de uma versao antiga, nunca ativada): so esquece aqui.
  apoio.assinaturaId = "";
  apoio.assinaturaChave = "";
  apoio.assinaturaValor = 0;
  apoio.ativa = "";
  apoio.ativaValor = 0;
  guardarApoio();
  desenharApoiar();
  const meses = mesesDesde(ativa);
  await confirmar({
    titulo: ativa ? "Obrigado por cada mês" : "Tudo bem", contexto: "Sua assinatura",
    html: '<div class="apoio-obrigado"><span class="apoio-obrigado-coracao">' + ic("favorite", 28) + "</span>" +
      (ativa
        ? "<p><b>Sua assinatura foi interrompida. Nada mais será cobrado.</b></p>" +
          "<p>Você apoiou o PAULUS desde " + esc(ativa) + (meses > 1 ? " — foram " + meses + " meses" : "") +
          ". Esse tempo ajudou a manter o programa livre e gratuito para todo mundo. Muito obrigado, de coração.</p>" +
          "<p>Se um dia quiser voltar, a porta está sempre aberta.</p>"
        : "<p><b>A assinatura foi desfeita antes de começar — nada foi cobrado.</b></p>" +
          "<p>Quando fizer sentido, considere ser apoiador do PAULUS no futuro. Todo apoio ajuda a manter o programa livre e gratuito.</p>") + "</div>",
    cancelar: "Fechar", confirmar: "Tudo bem", sucesso: true,
  });
}

/* Ao abrir a tela: o Pix gerado e nao pago, e a assinatura, sao conferidos
   no site (que guarda o que o Mercado Pago confirmou pelo aviso). Ativou
   agora, vem o agradecimento; foi cancelada fora daqui, a tela acompanha.
   Sem internet, fica como estava. */
/* "dd/mm/aaaa" de uma data guardada (ja nesse formato, ou ISO). */
function dataDoHistorico(d) {
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(d || "")) return d;
  const t = new Date(d || "");
  return isNaN(t) ? "" : t.toLocaleDateString("pt-BR");
}

/* O Pix pago numa versao antiga do programa ficou so com a data, sem numero
   nem valor. O site acha no Mercado Pago - pelo e-mail E pela data, os dois
   juntos - e o historico fica completo (e o extrato, certo). */
async function apoioRecuperarPixAntigos() {
  const antigos = apoio.historico.filter((h) => !h.id);
  if (!antigos.length) return false;
  const emails = [apoio.email];
  try {
    const p = await (await fetch("/api/preferencias")).json();
    emails.push((((p || {}).preferencias || {}).pessoa || {}).email);
  } catch (err) { /* so o e-mail digitado */ }
  const datas = [...new Set(antigos.map((h) => dataDoHistorico(h.data)).filter(Boolean))];
  let d = null;
  try {
    const r = await fetch("/api/apoio/pix/recuperar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ emails: emails.filter(Boolean), datas: datas }),
    });
    d = r.ok ? await r.json() : null;
  } catch (err) { d = null; }
  if (!d || !(d.pix || []).length) return false;
  apoio.historico = apoio.historico.filter((h) => h.id);
  d.pix.forEach((p) => {
    if (!apoio.historico.some((h) => h.id === p.id)) apoio.historico.push({ data: p.data, valor: Number(p.valor) || 0, id: p.id });
  });
  apoio.historico.sort((a, b) => String(a.data).localeCompare(String(b.data)));
  const ultimo = apoio.historico[apoio.historico.length - 1];
  if (ultimo && !apoio.pagoValor) apoio.pagoValor = ultimo.valor;
  return true;
}

async function apoioConferirPendentes() {
  let mudou = await apoioRecuperarPixAntigos();
  let agradecer = null;
  if (apoio.pixId) {
    try {
      const r = await fetch("/api/apoio/pix/" + encodeURIComponent(apoio.pixId));
      if (r.ok) {
        const d = await r.json();
        if (d.pago) { apoioRegistrarPix(valorDoApoio(), apoio.pixId); mudou = true; agradecer = ["pix", apoio.pagoValor]; }
      }
    } catch (err) { /* sem internet: confere na proxima vez */ }
  }
  if (apoio.assinaturaId) {
    try {
      const r = await fetch("/api/apoio/assinatura/" + encodeURIComponent(apoio.assinaturaId));
      if (r.ok) {
        const d = await r.json();
        if (d.ativa && !apoio.ativa) {
          apoio.ativa = new Date().toLocaleDateString("pt-BR");
          apoio.ativaValor = Number(d.valor) || apoio.assinaturaValor || valorDoApoio();
          mudou = true;
          agradecer = ["cartao", apoio.ativaValor];
        } else if (d.situacao === "cancelled") {
          apoio.assinaturaId = ""; apoio.assinaturaChave = ""; apoio.ativa = ""; apoio.ativaValor = 0;
          mudou = true;
        }
      }
    } catch (err) { /* sem internet: confere na proxima vez */ }
  }
  if (!mudou) return;
  guardarApoio();
  if ($("apoio-tela")) desenharApoiar();
  if (agradecer) apoioAgradecer(agradecer[0], agradecer[1]);
}
