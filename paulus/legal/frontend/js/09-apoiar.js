/* ------------------------------------------------------------- apoiar */
/*
   Apoiar o projeto (docs/ui/03-telas-desktop.md, A14): Contribuir e Quem ja
   apoia. O pagamento por Pix ou cartao e a lista publicada ainda nao existem;
   a tela mostra a moldura inteira com o texto certo, guarda as escolhas
   nesta maquina e diz o que falta, sem numero inventado. Abre pelo coracao
   do trilho.
*/

const apoio = {
  visao: "contribuir", valor: 40, outro: "", recorrencia: "mensal", forma: "pix",
  aparecer: true, como: "escritorio", nome: "", cidade: "", confirmado: "",
  filtro: "todos", termo: "", prefs: null, lido: false,
};

function lerApoioGuardado() {
  if (apoio.lido) return;
  apoio.lido = true;
  try {
    const g = JSON.parse(localStorage.getItem("paulus.apoio") || "null");
    if (g && typeof g === "object") {
      ["valor", "outro", "recorrencia", "forma", "aparecer", "como", "nome", "cidade", "confirmado"].forEach((k) => {
        if (g[k] !== undefined) apoio[k] = g[k];
      });
    }
  } catch (err) { /* sem memoria do navegador, tudo bem */ }
}

function guardarApoio() {
  try {
    localStorage.setItem("paulus.apoio", JSON.stringify({
      valor: apoio.valor, outro: apoio.outro, recorrencia: apoio.recorrencia, forma: apoio.forma,
      aparecer: apoio.aparecer, como: apoio.como, nome: apoio.nome, cidade: apoio.cidade, confirmado: apoio.confirmado,
    }));
  } catch (err) { /* sem memoria do navegador, tudo bem */ }
}

function mostrarApoiar(visao) {
  if (visao) apoio.visao = visao;
  lerApoioGuardado();
  abrirTela("Apoiar o projeto", { cheia: true });
  marcarDestino("apoiar");
  desenharApoiar();
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
  $("centro").innerHTML = '<div class="acervo sem-painel apoio-tela" id="apoio-tela"><div class="acervo-principal">' + miolo + "</div></div>";
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
  $("acoes-tela").innerHTML = '<div class="visoes">' + botao("contribuir", "Contribuir") + botao("lista", "Quem já apoia") + "</div>" +
    '<button class="com-icone" data-apoio-codigo="1">' + ic("code", 16) + "Ver o código</button>" +
    '<button class="com-icone" data-apoio-visao="lista">' + ic("group", 16) + "Quem já apoia</button>";
  $("nav-tela").innerHTML = "";
}

/* ---------------------------------------------------------- contribuir */

function corpoDeContribuir() {
  const d = NOVOS_DESTINOS.apoiar || { precisa: [] };
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
  const pagamento = apoio.forma === "pix"
    ? '<div class="apoio-pix"><div class="apoio-qr">QR do Pix entra quando o pagamento existir</div>' +
      '<div class="apoio-pix-texto"><b>Pix ' + (apoio.recorrencia === "mensal" ? "recorrente" : "") + " · " + esc(rotuloDoValor()) + "</b>" +
      "<p>" + (apoio.recorrencia === "unica"
        ? "Aponte a câmera do app do banco e pague uma vez. Recibo por e-mail."
        : "Aponte a câmera do app do banco. A recorrência é aprovada uma vez e renova no mesmo dia; cancele quando quiser.") + "</p>" +
      '<div class="apoio-codigo"><span>a chave Pix copia-e-cola entra aqui quando o pagamento existir</span><button class="em-ligacao" disabled>copiar código</button></div></div></div>'
    : '<div class="apoio-pix"><div class="apoio-qr">Cartão em breve</div><div class="apoio-pix-texto"><b>Cartão · ' + esc(rotuloDoValor()) + "</b>" +
      "<p>O pagamento por cartão vai abrir no navegador, sem guardar o número aqui. Ainda não existe.</p></div></div>";
  const contribuicao = '<div class="ag-campo"><label>Valor</label><div class="cfg-valores">' +
    valor(20, "um café por semana") + valor(40, "mais escolhido") + valor(100, "escritório pequeno") + valor(0, "você define") + "</div>" +
    (apoio.valor ? "" : '<div class="apoio-outro"><input type="text" data-apoio-outro="1" value="' + esc(apoio.outro) + '" placeholder="R$ 0,00"><span class="cfg-explica">qualquer valor ajuda</span></div>') + "</div>" +
    '<div class="ag-duas"><div class="ag-campo"><label>Recorrência</label>' + seg("recorrencia", [["mensal", "Mensal"], ["anual", "Anual"], ["unica", "Única"]]) + "</div>" +
    '<div class="ag-campo"><label>Forma de pagamento</label>' + seg("forma", [["pix", "Pix"], ["cartao", "Cartão"]]) + "</div></div>" +
    pagamento +
    '<div class="apoio-banco"><div class="apoio-banco-topo">' + ic("payments", 18) + '<span class="duas-linhas"><b>Transferência bancária</b><small>os dados do banco entram com o pagamento · em breve</small></span></div>' +
    '<div class="cfg-chaves">' + chaveCfg("Banco", "—", "mute") + chaveCfg("Agência e conta", "—", "mute") + chaveCfg("Titular", "—", "mute") + "</div></div>" +
    '<p class="cfg-explica">Falta: ' + esc((d.precisa || []).join(", ") || "o pagamento") + ". Recibo por e-mail e lançamento automático no Financeiro entram junto.</p>";

  const lista = '<p class="cfg-texto">O nome de quem apoia entra na lista de apoiadores da próxima atualização do PAULUS — na tela “Sobre” do programa e no site. Só se você quiser.</p>' +
    '<div class="ag-campo"><label>Deseja aparecer na lista de apoiadores?</label><div class="apoio-radios">' +
    radio("aparecer", true, "Sim") + radio("aparecer", false, "Não, prefiro anônimo") + "</div></div>" +
    (apoio.aparecer
      ? '<div class="ag-campo"><label>Como deseja aparecer</label><div class="apoio-radios">' + radio("como", "nome", "Meu nome") + radio("como", "escritorio", "Meu escritório") + "</div></div>" +
        '<div class="ag-duas"><div class="ag-campo"><label>Nome na lista</label><input type="text" data-apoio-campo="nome" value="' + esc(apoio.nome) + '" placeholder="' + esc(nomeSugeridoDoApoio() || "como quer aparecer") + '"></div>' +
        '<div class="ag-campo"><label>Cidade (opcional)</label><input type="text" data-apoio-campo="cidade" value="' + esc(apoio.cidade) + '" placeholder="Goiânia"></div></div>' +
        '<div class="apoio-previa"><span class="cfg-explica">Prévia</span><div class="apoio-previa-linha">' + ic("favorite", 18) + "<b>" + esc(nome || "seu nome aqui") + "</b><small>" +
        esc((apoio.cidade ? apoio.cidade + " · " : "") + "apoiador desde " + desde) + "</small></div></div>"
      : '<div class="apoio-previa"><span class="cfg-explica">Prévia</span><div class="apoio-previa-linha">' + ic("favorite", 18) + "<b>Apoiador anônimo</b><small>conta no total, não é listado</small></div></div>") +
    '<span class="cfg-explica">Só o nome escolhido e a cidade aparecem. Valor e forma de pagamento nunca são publicados. Recibo por e-mail; cancele quando quiser.</span>';

  const resumo = rotuloDoValor() + " · " + (apoio.forma === "pix" ? "Pix" : "Cartão") + " · " + (apoio.aparecer ? "na lista como " + (nome || "…") : "anônimo") +
    (apoio.confirmado ? " · escolha guardada em " + apoio.confirmado : "");
  return '<div class="cfg-chamada"><h3>Ajude o PAULUS a continuar gratuito.</h3>' +
    "<p>O PAULUS é software livre: roda na sua máquina, sem assinatura nem cobrança por uso. O que mantém o projeto vivo é a contribuição de quem usa — ela paga o desenvolvimento, os modelos locais e o suporte. Qualquer valor ajuda; a recorrência ajuda mais.</p>" +
    '<p class="cfg-explica">Meta do mês e apoiadores aparecem aqui quando o pagamento existir. Enquanto isso, o que você escolher fica guardado nesta máquina.</p></div>' +
    '<div class="apoio-grade">' +
    '<div class="fin-cartao apoio-cartao"><div class="fin-cartao-cabeca"><span>Sua contribuição</span><small>escolha o valor e a forma</small></div><div class="apoio-corpo">' + contribuicao + "</div></div>" +
    '<div class="fin-cartao apoio-cartao"><div class="fin-cartao-cabeca"><span>Lista de apoiadores</span><small>na próxima atualização</small></div><div class="apoio-corpo">' + lista + "</div>" +
    '<div class="apoio-rodape"><span>' + esc(resumo) + '</span><button class="primario" data-apoio-confirmar="1">' + ic("favorite", 16) + "Confirmar apoio</button></div></div>" +
    "</div>";
}

/* ------------------------------------------------------------- a lista */

function corpoDaLista() {
  const chip = (v, r) => {
    const classe = v === apoio.filtro ? "ativa" : "";
    return '<button class="' + classe + '" data-apoio-filtro="' + v + '">' + r + "</button>";
  };
  const nome = nomeNaLista();
  const voce = apoio.aparecer && nome && (apoio.filtro === "todos" || (apoio.filtro === "escritorios") === (apoio.como === "escritorio")) &&
    (!apoio.termo || nome.toLowerCase().indexOf(apoio.termo.toLowerCase()) >= 0);
  const agora = new Date();
  const desde = MESES_CURTOS[agora.getMonth()] + " " + agora.getFullYear();
  const linhaVoce = '<div class="apoio-nome"><span class="cad-avatar">' + esc(iniciaisDoRemetente(nome)) + '</span><span class="duas-linhas"><b>' + esc(nome) +
    ' <small>· você</small></b><small>' + esc((apoio.cidade ? apoio.cidade + " · " : "") + "entra na próxima atualização · desde " + desde) + "</small></span>" +
    '<span class="cfg-pill">' + (apoio.recorrencia === "mensal" ? "Mantenedor" : (apoio.recorrencia === "unica" ? "Contribuição única" : "Apoiador")) + "</span></div>";
  const secao = (titulo, sub, mostraVoce, vazio) =>
    '<div class="apoio-secao"><div class="apoio-secao-cabeca"><span>' + titulo + "</span><small>" + esc(sub) + "</small></div>" +
    (mostraVoce ? linhaVoce : '<p class="apoio-vazio">' + esc(vazio) + "</p>") + "</div>";
  return '<div class="fin-cartao apoio-cartao">' +
    '<div class="apoio-lista-topo"><h3>Quem mantém o PAULUS gratuito</h3>' +
    "<p>A lista nasce com a primeira atualização pública: entra na tela “Sobre” e no site, só com o nome que cada um escolheu, nunca com valores. Até lá, ninguém está listado — quem preferir não aparecer conta no total, mas não é listado.</p></div>" +
    '<div class="apoio-barra"><label class="busca-tela">' + ic("search", 18) + '<input type="text" data-apoio-termo="1" value="' + esc(apoio.termo) + '" placeholder="Buscar um nome…"></label>' +
    '<div class="visoes">' + chip("todos", "Todos") + chip("escritorios", "Escritórios") + chip("pessoas", "Pessoas") + "</div></div>" +
    secao("Fundadores", "quem apoiar desde o início", false, "Ainda ninguém: os fundadores são os primeiros a apoiar quando o pagamento existir.") +
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
  clique("[data-apoio-codigo]", () => avisoCert("o código abre no site do projeto quando a primeira versão for publicada — por enquanto ele está nesta máquina, na pasta do programa"));
  clique("[data-apoio-valor]", (b) => { apoio.valor = Number(b.dataset.apoioValor); guardarApoio(); desenharApoiar(); });
  clique("[data-apoio-escolha]", (b) => { const [chave, v] = b.dataset.apoioEscolha.split(":"); apoio[chave] = v; guardarApoio(); desenharApoiar(); });
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
  clique("[data-apoio-confirmar]", () => {
    if (!valorDoApoio()) { avisoCert("escolha um valor primeiro"); return; }
    if (apoio.aparecer && !nomeNaLista()) { avisoCert("diga como quer aparecer na lista, ou escolha ficar anônimo"); return; }
    apoio.confirmado = new Date().toLocaleDateString("pt-BR");
    guardarApoio();
    desenharApoiar();
    avisoCert("escolha guardada nesta máquina — o pagamento por Pix ou cartão ainda não existe; quando existir, a confirmação sai daqui");
  });
  clique("[data-apoio-filtro]", (b) => { apoio.filtro = b.dataset.apoioFiltro; desenharApoiar(); });
  cada("[data-apoio-termo]", (el) => {
    let t;
    el.oninput = () => { clearTimeout(t); const v = el.value; t = setTimeout(() => { apoio.termo = v.trim(); desenharApoiar(); const campo = document.querySelector("[data-apoio-termo]"); if (campo) { campo.focus(); campo.setSelectionRange(campo.value.length, campo.value.length); } }, 250); };
  });
}

