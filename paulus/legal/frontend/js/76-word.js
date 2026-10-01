/* ------------------------------------------ O PAVLVS no Word (W1) */
/*
   Configurações › Word: ligar, instalar no Word deste computador (registro
   do usuário, sem administrador), abrir o Word com o PAVLVS, os Words
   conectados com "revogar" e, de fora, o manifesto para o Word na web
   (src/word_suplemento.py, src/word_instalar.py).

   No Word 2021 a aba PAVLVS só aparece no documento que traz o PAVLVS
   (medido em 01/10/2026): por isso o PAULUS abre o Word com um documento
   seu, e todo .docx que ele gera leva o PAVLVS.

   Na janela do escritório, um Word pedindo para conectar abre um diálogo com
   o código e "Permitir". De fora, a pessoa conecta o Word dela em Minha conta,
   com o código do painel e o do autenticador.
*/

async function carregarWord() {
  try {
    const r = await fetch("/api/word");
    cfg.word = r.ok ? await r.json() : null;
  } catch (err) { cfg.word = null; }
}

function linhaWord(rotulo, valor, tom) {
  return '<div class="word-linha"><span>' + esc(rotulo) + '</span><b class="' + (tom || "") + '">' + esc(valor) + "</b></div>";
}

function secaoWord() {
  const w = cfg.word;
  if (!w) return aberturaCfg() + '<p class="cfg-explica">Não consegui ler o estado do Word agora.</p>';
  const i = w.instalacao || {};
  const cert = i.certificado || {};
  const instalado = Boolean(i.instalado && i.registrado && cert.confiado);
  const ficha = fichaCfg([
    ["PAVLVS no Word", w.ligado ? "ligado" : "desligado", w.ligado ? "ok" : ""],
    ["Neste computador", i.carregado ? "abriu no Word" : (instalado ? "instalado, falta abrir" : "não instalado"), i.carregado ? "ok" : ""],
    ["Words conectados", String((w.conexoes || []).length)],
  ]);

  const ligar = cartaoCfg("Ligar", "",
    '<div class="ag-toggle' + (w.ligado ? " on" : "") + '" data-word-acao="ligar" role="switch" tabindex="0" aria-checked="' + w.ligado + '">' +
    '<span class="duas-linhas"><b>O PAVLVS dentro do Word</b><small>o painel no Word confere citações, insere lei e qualificação e responde sobre o documento; ' +
    "o texto do documento vai só para este PAULUS</small></span><i></i></div>");

  let corpo;
  if (!w.ligado) {
    corpo = '<p class="cfg-explica">Ligue acima para instalar.</p>';
  } else {
    const carregou = i.carregou;
    corpo = (i.word_no_computador ? "" : '<p class="cfg-explica"><b>Não achei o Word neste computador.</b> Instale o Microsoft Office para usar o PAVLVS aqui; em outro computador, o Word usa pelo acesso de fora.</p>') +
      linhaWord("Certificado deste computador", cert.existe ? (cert.confiado ? "confiado pelo Windows · vale até " + cert.vence : "gerado, ainda não confiado") : "ainda não gerado",
        cert.confiado ? "ok" : "") +
      linhaWord("Endereço do painel", i.endereco || "escolhido na instalação") +
      linhaWord("No Word deste usuário", i.registrado ? "registrado" : "não registrado", i.registrado ? "ok" : "") +
      linhaWord("Abriu no Word", i.carregado && carregou ? carregou.quando.slice(0, 16).replace("T", " ") + " · Word " + (carregou.word || "") : "ainda não",
        i.carregado ? "ok" : "") +
      (instalado && (i.atalhos || {}).disponivel
        ? linhaWord("Atalho Word com PAVLVS", [i.atalhos.area_de_trabalho ? "na área de trabalho" : "", i.atalhos.menu_iniciar ? "no menu Iniciar" : ""]
            .filter(Boolean).join(" e ") || "nenhum", i.atalhos.area_de_trabalho ? "ok" : "") +
          linhaWord("Botão direito dos .docx", i.atalhos.botao_direito ? "Abrir no Word com o PAVLVS" : "desligado", i.atalhos.botao_direito ? "ok" : "")
        : "") +
      '<p class="cfg-explica">' + (instalado
        ? "O Word abre com o PAVLVS (a aba e o painel) pelo atalho <b>Word com PAVLVS</b>, pelo botão direito de qualquer arquivo .docx (<b>Abrir no Word com o PAVLVS</b>; no Windows 11, em Mostrar mais opções), pelo <b>Abrir no Word</b> do Editor e em todo documento Word que o PAULUS gera. Depois que o arquivo abriu com o PAVLVS, ele continua lá, e o duplo clique já abre com ele. Fixar o atalho na barra de tarefas o Windows só deixa você mesmo: botão direito no atalho › Mostrar mais opções › Fixar na barra de tarefas."
        : "O Windows vai perguntar se confia no certificado do PAULUS: clique em Sim. Ele só vale para este computador (localhost) e não pede administrador. Depois, o Word abre sozinho com o PAVLVS.") + "</p>" +
      '<div class="word-acoes">' +
      (instalado ? '<button class="primario" data-word-acao="abrir">' + ic("description", 16) + "Abrir o Word com o PAVLVS</button>" : "") +
      (instalado && (i.atalhos || {}).disponivel && !(i.atalhos.area_de_trabalho && i.atalhos.menu_iniciar && i.atalhos.botao_direito)
        ? '<button data-word-acao="atalhos">Criar os atalhos</button>' : "") +
      '<button' + (instalado ? "" : ' class="primario"') + ' data-word-acao="instalar">' + ic("download", 16) + (instalado ? "Instalar de novo" : "Instalar no Word") + "</button>" +
      (i.registrado ? '<button data-word-acao="desinstalar">Tirar do Word</button>' : "") +
      (instalado ? '<button data-word-acao="pasta">' + ic("folder_open", 16) + "Manifesto e pasta</button>" : "") + "</div>";
  }
  const instalar = cartaoCfg("Instalar no Word deste computador", metaCfg("sem administrador"), corpo);

  const fora = !w.ligado ? "" : cartaoCfg("Word em outro computador ou no navegador", metaCfg("pelo acesso de fora"),
    i.endereco_de_fora
      ? '<p class="cfg-explica">O painel abre pelo endereço do escritório (' + esc(i.endereco_de_fora) + "). Cada pessoa conecta o Word dela com a própria conta e o código do autenticador.</p>" +
        '<ol class="word-passos"><li>Clique em <b>Manifesto e pasta</b> e mande o arquivo <b>PAVLVS-word-de-fora.xml</b> para a pessoa.</li>' +
        "<li>Word na web: Inserir › Suplementos › Meus Suplementos › Carregar Meu Suplemento › escolher o arquivo.</li>" +
        "<li>No painel, Conectar ao PAULUS mostra um código; a pessoa entra no PAULUS de fora e confirma em Minha conta › Conectar o Word.</li></ol>"
      : '<p class="cfg-explica">Precisa do acesso de fora ligado e conectado (Configurações › Acesso de fora). Sem ele, o PAVLVS funciona só no Word deste computador.</p>');

  const conexoes = (w.conexoes || []);
  const lista = conexoes.length
    ? conexoes.map((c) => '<div class="word-conexao"><span class="duas-linhas"><b>' + esc(c.pessoa) + " · " + (c.origem === "fora" ? "de fora" : "este computador") + "</b>" +
        "<small>Word " + esc(c.word || "sem versão") + " · conectado em " + esc(c.criada_em) + (c.ultimo_uso ? " · último uso " + esc(c.ultimo_uso) : " · ainda não usado") +
        " · " + plural(c.chamadas || 0, "chamada") + "</small></span>" +
        '<button class="perigo" data-word-acao="revogar" data-word-id="' + esc(c.id) + '">Revogar</button></div>').join("")
    : '<p class="cfg-explica">Nenhum Word conectado. Revogar desconecta na hora: o painel pede para conectar de novo.</p>';
  const conectados = cartaoCfg("Words conectados", "", lista);

  return aberturaCfg() + ficha + ligar + instalar + fora + conectados;
}

async function acaoWord(acao, alvo) {
  const posta = async (url, corpo, metodo) => {
    const r = await fetch(url, { method: metodo || "POST", headers: { "Content-Type": "application/json" }, body: corpo ? JSON.stringify(corpo) : undefined });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
    return r.json();
  };
  let d = null;
  if (acao === "ligar") d = await posta("/api/word/ligar", { ligado: !(cfg.word && cfg.word.ligado) });
  else if (acao === "instalar") {
    avisoCert("instalando… se o Windows perguntar sobre o certificado do PAULUS, clique em Sim", { tom: "info" });
    d = await posta("/api/word/instalar");
    if (d) { cfg.word = d; desenharConfig(); await perguntarAtalhosDoWord(d); await abrirWordComPavlvs("/api/word/abrir"); await carregarWord(); d = cfg.word; }
  } else if (acao === "abrir") { await abrirWordComPavlvs("/api/word/abrir"); return; }
  else if (acao === "atalhos") {
    d = await posta("/api/word/atalhos", { area_de_trabalho: true, menu_iniciar: true, botao_direito: true });
    if (d) avisoCert("atalhos criados: " + (d.feitos || []).join(", "), { tom: "ok" });
  }
  else if (acao === "desinstalar") d = await posta("/api/word/desinstalar");
  else if (acao === "pasta") { await posta("/api/word/abrir-pasta"); return; }
  else if (acao === "revogar") {
    const c = ((cfg.word || {}).conexoes || []).find((x) => x.id === alvo);
    const ok = await dialogo({ titulo: "Revogar este Word?", contexto: "Configurações › Word",
      texto: "O Word de " + ((c && c.pessoa) || "alguém") + " perde a conexão agora. Para usar de novo, a pessoa conecta outra vez.", confirmar: "Revogar", perigo: true });
    if (!ok || !ok.ok) return;
    d = await posta("/api/word/conexoes/" + encodeURIComponent(alvo), null, "DELETE");
  }
  if (d) { cfg.word = d; desenharConfig(); }
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-word-acao]");
  if (!b) return;
  acaoWord(b.dataset.wordAcao, b.dataset.wordId);
});
document.addEventListener("keydown", (e) => {
  const b = e.target.closest && e.target.closest('[data-word-acao="ligar"]');
  if (b && (e.key === " " || e.key === "Enter")) { e.preventDefault(); acaoWord("ligar"); }
});

/* Um Word deste computador pedindo para conectar: o diálogo com o código.
   Só na janela do escritório; de fora a lista volta vazia. */
const wordPedidosVistos = new Set();
let wordDialogoAberto = false;
async function vigiarPedidosDoWord() {
  if (wordDialogoAberto || (typeof acessoDeFora !== "undefined" && acessoDeFora.pessoa)) return;
  let pedidos = [];
  try {
    const r = await fetch("/api/word/pedidos");
    pedidos = r.ok ? ((await r.json()).pedidos || []) : [];
  } catch (err) { return; }
  const novo = pedidos.find((p) => !wordPedidosVistos.has(p.id));
  if (!novo) return;
  wordPedidosVistos.add(novo.id);
  wordDialogoAberto = true;
  const r = await dialogo({
    titulo: "Um Word quer se conectar", contexto: "PAVLVS no Word",
    html: '<p>Confira se o painel do Word mostra este mesmo código:</p><div class="word-codigo">' + esc(novo.codigo) + "</div>" +
      "<p>Word " + esc(novo.word || "sem versão") + ", neste computador. Permitir dá a ele acesso ao PAULUS como titular, até alguém revogar em Configurações › Word.</p>",
    confirmar: "Permitir", cancelar: "Recusar",
  });
  wordDialogoAberto = false;
  const url = "/api/word/pedidos/" + encodeURIComponent(novo.id) + (r && r.ok ? "/permitir" : "/recusar");
  const resp = await fetch(url, { method: "POST" });
  if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
  if (r && r.ok) avisoCert("Word conectado", { tom: "ok" });
  if (cfg && cfg.secao === "word") { cfg.word = await resp.json(); desenharConfig(); }
}
setInterval(vigiarPedidosDoWord, 3000);

/* A novidade, ao entrar no Editor: uma vez, só na janela do escritório, só
   com Word neste computador e só enquanto o Word nunca abriu com o PAVLVS.
   Dois textos: "ativar" (ainda não instalado) e "abrir" (instalado na 0.9.23,
   que só registrava - no Word 2021 isso não mostra a aba). Diz o que esta
   versão faz e o que vem depois: as funções aparecem marcadas "em breve". A
   chave mudou de nome na 0.9.24 para quem já tinha visto ver uma vez de novo. */
const NOVIDADE_DO_WORD = "paulus.novidade.word.2";
let novidadeDoWordAberta = false;
async function novidadeDoWord() {
  if (novidadeDoWordAberta || (typeof acessoDeFora !== "undefined" && acessoDeFora.pessoa)) return;
  // Navegador controlado por teste (Playwright) não vê a novidade: o diálogo
  // ficaria na frente da tela que o teste está clicando.
  if (navigator.webdriver) return;
  try { if (localStorage.getItem(NOVIDADE_DO_WORD)) return; } catch (err) { return; }
  let w = null;
  try {
    const r = await fetch("/api/word");
    w = r.ok ? await r.json() : null;
  } catch (err) { w = null; }
  // O servidor decide se há novidade: Word aqui, PAVLVS não instalado.
  if (!w || !w.novidade) return;
  const lembrar = () => { try { localStorage.setItem(NOVIDADE_DO_WORD, new Date().toISOString()); } catch (err) { /* sem armazenamento: pode aparecer de novo */ } };
  novidadeDoWordAberta = true;
  if (w.novidade_tipo === "abrir") {
    const a = await dialogo({
      titulo: "O PAVLVS já está no seu Word", contexto: "PAVLVS no Word",
      html: "<p>O PAVLVS está instalado neste computador. Agora o PAULUS abre o Word com ele: a aba <b>PAVLVS</b> lá em cima e o painel ao lado do documento.</p>" +
        "<p>Para isso, crio o atalho <b>Word com PAVLVS</b> na área de trabalho (um documento novo com o PAVLVS) e o <b>Abrir no Word com o PAVLVS</b> no botão direito de todo arquivo .docx. Depois que um arquivo abriu com o PAVLVS, o duplo clique já abre com ele. O <b>Abrir no Word</b> do Editor e todo documento Word que o PAULUS gera também abrem com o PAVLVS.</p>" +
        "<p>Nesta versão, o painel se conecta ao PAULUS; conferir citações, inserir lei e qualificação e o resto chegam nas próximas versões, marcados “em breve”.</p>",
      confirmar: "Abrir o Word com o PAVLVS", cancelar: "Agora não",
    });
    novidadeDoWordAberta = false;
    lembrar();
    if (a && a.ok) {
      const resp = await fetch("/api/word/atalhos", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ area_de_trabalho: true, botao_direito: true }) });
      if (resp.ok) await perguntarAtalhosDoWord(await resp.json());
      await abrirWordComPavlvs("/api/word/abrir");
    }
    return;
  }
  const r = await dialogo({
    titulo: "Novidade: o PAULUS dentro do Word", contexto: "PAVLVS no Word",
    html: '<p>Agora o PAULUS pode ficar no Word que você já usa: uma aba <b>PAVLVS</b> e um painel ao lado do documento, ligados a este computador. O texto do documento vai só para este PAULUS.</p>' +
      "<p>Nesta versão, o painel se instala e se conecta ao PAULUS. Conferir citações, inserir lei e qualificação, perguntar sobre o documento, revisar com agente e guardar no Acervo chegam nas próximas versões; os botões já aparecem no Word, marcados “em breve”.</p>" +
      "<p>Para instalar, o Windows vai perguntar se confia no certificado do PAULUS, que só vale para este computador: clique em <b>Sim</b>. Depois o Word abre sozinho, já com o PAVLVS. Daí em diante, o <b>Abrir no Word</b> do Editor e todo documento Word que o PAULUS gera abrem com ele.</p>" +
      '<p class="cfg-explica">Também fica em Configurações › Word, para ativar depois ou tirar.</p>',
    confirmar: "Ativar no Word", cancelar: "Agora não",
  });
  novidadeDoWordAberta = false;
  lembrar();
  if (!r || !r.ok) return;
  const posta = (url, corpo) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: corpo ? JSON.stringify(corpo) : undefined });
  let resp = await posta("/api/word/ligar", { ligado: true });
  if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
  avisoCert("instalando… se o Windows perguntar sobre o certificado do PAULUS, clique em Sim", { tom: "info" });
  resp = await posta("/api/word/instalar");
  if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
  wordEstado = await resp.json();
  await perguntarAtalhosDoWord(wordEstado);
  await abrirWordComPavlvs("/api/word/abrir");
}

/* Depois de instalar: o atalho na área de trabalho e o botão direito dos
   .docx já foram criados; o menu Iniciar, a pessoa escolhe. Fixar na barra
   de tarefas o Windows 11 não deixa programa nenhum fazer - a tela diz. */
async function perguntarAtalhosDoWord(situacao) {
  const a = ((situacao || {}).instalacao || {}).atalhos || {};
  if (!a.disponivel) return;
  const feitos = [a.area_de_trabalho ? "o atalho <b>Word com PAVLVS</b> na área de trabalho" : "",
    a.botao_direito ? "<b>Abrir no Word com o PAVLVS</b> no botão direito de todo arquivo .docx (no Windows 11, em Mostrar mais opções)" : ""]
    .filter(Boolean);
  const r = await dialogo({
    titulo: "Atalhos do PAVLVS", contexto: "PAVLVS no Word",
    html: (feitos.length ? "<p>Criei " + feitos.join(" e ") + ".</p>" : "") +
      "<p>Quer o atalho <b>Word com PAVLVS</b> também no menu Iniciar?</p>" +
      '<p class="cfg-explica">Fixar na barra de tarefas ou no topo do Iniciar o Windows só deixa você mesmo fazer: botão direito no atalho › Mostrar mais opções › Fixar.</p>',
    confirmar: "Pôr no menu Iniciar", cancelar: "Não",
  });
  if (!r || !r.ok) return;
  const resp = await fetch("/api/word/atalhos", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ menu_iniciar: true }) });
  if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
  avisoCert("Word com PAVLVS está no menu Iniciar", { tom: "ok" });
}

/* Abrir o Word com o PAVLVS ("comece aqui" ou um documento do Editor). Um
   Word aberto desde antes da instalação não conhece o PAVLVS (ele lê o
   registro só ao abrir): o PAULUS pede para fechar e abre sozinho quando ele
   fechar. */
let wordEsperandoFechar = false;
async function abrirWordComPavlvs(url) {
  const pedir = async () => {
    const r = await fetch(url, { method: "POST" });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
    return r.json();
  };
  let d = await pedir();
  if (!d) return;
  if (d.precisa_fechar) {
    if (wordEsperandoFechar) return;
    const ok = await dialogo({
      titulo: "Feche o Word para continuar", contexto: "PAVLVS no Word",
      texto: "O Word está aberto desde antes de o PAVLVS ser instalado, e só o conhece quando abre de novo.\n" +
        "Salve o que estiver fazendo e feche o Word. Assim que ele fechar, o PAULUS abre o Word com o PAVLVS.",
      confirmar: "Esperar o Word fechar", cancelar: "Agora não",
    });
    if (!ok || !ok.ok) return;
    wordEsperandoFechar = true;
    avisoCert("esperando o Word fechar…", { tom: "info" });
    const fim = Date.now() + 15 * 60 * 1000;
    while (Date.now() < fim) {
      await new Promise((res) => setTimeout(res, 2000));
      try {
        const e = await (await fetch("/api/word/word-aberto")).json();
        if (!e.precisa_fechar) break;
      } catch (err) { /* tenta de novo */ }
    }
    wordEsperandoFechar = false;
    d = await pedir();
    if (!d || d.precisa_fechar) {
      avisoCert("o Word continua aberto: feche e clique em Abrir o Word com o PAVLVS, em Configurações › Word", { tom: "erro" });
      return;
    }
  }
  if (d.aberto) avisoCert("abrindo o Word com o PAVLVS…", { tom: "ok" });
}

/* O Editor pergunta uma vez por entrada se o PAVLVS está instalado: é o que
   mostra o "Abrir no Word" na pré-visualização (js/19-documentos.js). */
let wordEstado = null;
async function atualizarWordDoEditor() {
  if (typeof acessoDeFora !== "undefined" && acessoDeFora.pessoa) { wordEstado = null; return; }
  try {
    const r = await fetch("/api/word");
    wordEstado = r.ok ? await r.json() : null;
  } catch (err) { wordEstado = null; }
}
function wordInstaladoAqui() {
  return Boolean(wordEstado && wordEstado.ligado && wordEstado.instalacao && wordEstado.instalacao.instalado);
}

/* De fora: conectar o Word desta pessoa (montagem C), em Minha conta. */
async function conectarWordDeFora() {
  const r = await dialogo({
    titulo: "Conectar o Word", contexto: "Minha conta",
    texto: "No Word, o painel do PAVLVS mostra um código depois de Conectar ao PAULUS. Digite o código e o do autenticador.",
    campos: [{ chave: "codigo", rotulo: "Código do painel", placeholder: "XXXX-XXXX", max: 9, obrigatorio: true },
      { chave: "autenticador", rotulo: "Código do autenticador", placeholder: "000000", max: 8, obrigatorio: true,
        dica: "os 6 números do Google Authenticator, ou um código de recuperação" }],
    confirmar: "Permitir",
  });
  if (!r || !r.ok) return;
  const resp = await window.fetch("/api/word/permitir-de-fora", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ codigo: r.valores.codigo, codigo_autenticador: r.valores.autenticador }) });
  if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
  avisoCert("Word conectado · o painel já pode usar o PAULUS", { tom: "ok" });
}
