/* ------------------------------------------ O PAVLVS no Word (W1) */
/*
   Configurações › Word: ligar, instalar no Word deste computador (registro
   do usuário, sem administrador; o catálogo em pasta compartilhada como
   segunda via), os Words conectados com "revogar" e, de fora, o manifesto
   para o Word de outro computador (src/word_suplemento.py, src/word_instalar.py).

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
  const instalado = Boolean(i.registrado && cert.confiado);
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
      '<p class="cfg-explica">' + (instalado
        ? (i.carregado ? "Pronto. No Word, a aba PAVLVS tem os comandos; o painel pede para conectar na primeira vez."
          : "Feche e abra o Word. A aba PAVLVS aparece; clique em Painel. Quando o painel abrir, esta tela mostra “abriu no Word”.")
        : "O Windows vai perguntar se confia no certificado do PAULUS: clique em Sim. Ele só vale para este computador (localhost) e não pede administrador.") + "</p>" +
      '<div class="word-acoes">' +
      '<button class="primario" data-word-acao="instalar">' + ic("download", 16) + (instalado ? "Instalar de novo" : "Instalar no Word") + "</button>" +
      (i.registrado ? '<button data-word-acao="desinstalar">Tirar do Word</button>' : "") +
      (instalado ? '<button data-word-acao="pasta">' + ic("folder_open", 16) + "Manifesto e pasta</button>" : "") + "</div>";
  }
  const instalar = cartaoCfg("Instalar no Word deste computador", metaCfg("sem administrador"), corpo);

  const catalogo = !w.ligado ? "" : cartaoCfg("Se o Word não mostrar a aba PAVLVS", metaCfg("segunda via"),
    '<p class="cfg-explica">Alguns escritórios bloqueiam o registro do usuário por política do Windows. O caminho oficial da Microsoft é um catálogo numa pasta compartilhada da rede (criar o compartilhamento pede administrador uma vez):</p>' +
    '<ol class="word-passos"><li>Clique em <b>Manifesto e pasta</b> e copie o arquivo <b>PAVLVS-word.xml</b> para uma pasta compartilhada, por exemplo <code>\\\\SERVIDOR\\PAVLVS</code>.</li>' +
    "<li>No Word: Arquivo › Opções › Central de Confiabilidade › Configurações da Central de Confiabilidade › Catálogos de Suplementos Confiáveis.</li>" +
    "<li>Em <b>URL do Catálogo</b>, cole o endereço da pasta, clique em Adicionar catálogo, marque <b>Mostrar no Menu</b> e OK.</li>" +
    "<li>Feche e abra o Word. Inserir › Meus Suplementos › PASTA COMPARTILHADA › PAVLVS › Adicionar.</li></ol>");

  const fora = !w.ligado ? "" : cartaoCfg("Word em outro computador ou no navegador", metaCfg("pelo acesso de fora"),
    i.endereco_de_fora
      ? '<p class="cfg-explica">O painel abre pelo endereço do escritório (' + esc(i.endereco_de_fora) + "). Cada pessoa conecta o Word dela com a própria conta e o código do autenticador.</p>" +
        '<ol class="word-passos"><li>Clique em <b>Manifesto e pasta</b> e mande o arquivo <b>PAVLVS-word-de-fora.xml</b> para a pessoa.</li>' +
        "<li>Word na web: Inserir › Suplementos › Meus Suplementos › Carregar Meu Suplemento › escolher o arquivo.</li>" +
        "<li>Word no Windows de outro computador: o catálogo em pasta compartilhada, como acima.</li>" +
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

  return aberturaCfg() + ficha + ligar + instalar + catalogo + fora + conectados;
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
    if (d) avisoCert("instalado · feche e abra o Word para ver a aba PAVLVS", { tom: "ok" });
  } else if (acao === "desinstalar") d = await posta("/api/word/desinstalar");
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
   com Word neste computador e só se o PAVLVS ainda não está instalado. Diz o
   que esta versão faz (instalar e conectar) e o que vem depois - as funções
   aparecem no Word marcadas "em breve" até chegarem. */
const NOVIDADE_DO_WORD = "paulus.novidade.word";
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
  const r = await dialogo({
    titulo: "Novidade: o PAULUS dentro do Word", contexto: "PAVLVS no Word",
    html: '<p>Agora o PAULUS pode ficar no Word que você já usa: uma aba <b>PAVLVS</b> e um painel ao lado do documento, ligados a este computador. O texto do documento vai só para este PAULUS.</p>' +
      "<p>Nesta versão, o painel se instala e se conecta ao PAULUS. Conferir citações, inserir lei e qualificação, perguntar sobre o documento, revisar com agente e guardar no Acervo chegam nas próximas versões; os botões já aparecem no Word, marcados “em breve”.</p>" +
      "<p>Para instalar, o Windows vai perguntar se confia no certificado do PAULUS, que só vale para este computador: clique em <b>Sim</b>. Depois, feche e abra o Word.</p>" +
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
  avisoCert("pronto · feche e abra o Word: a aba PAVLVS aparece", { tom: "ok" });
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
