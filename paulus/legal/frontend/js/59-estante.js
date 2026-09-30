/* ------------------------------------------------- a estante (B2, A21) */
/*
   A primeira aba da Biblioteca (docs/ui: "Biblioteca - referencia", A21): as
   estantes por área, o nível, os próximos passos e os artigos que as obras
   comentam. Tudo sai dos dados - /api/biblioteca-juridica/mapa, /api/material
   e as chaves da Biblioteca -, nada é inventado.

   - Nível: pelo número de áreas com obra do escritório. Lei em casa e as
     súmulas que vêm com o PAULUS não contam: não são livro de ninguém.
   - Cada item abre a faixa da ficha no pé das estantes; na obra, o "···"
     é o menu de sempre (js/35-material.js: conferir a ficha, glossário,
     exportar, abrir, remover).
   - Próximos passos: no máximo 4, nesta ordem - ficha a conferir, área com
     lei e sem obra, obra mais velha que a lei, leitura das obras desligada.
     O que termina fica esmaecido, com ✓, e o aviso diz o que mudou.
   - Arrastar arquivos para a tela inteira entrega, como "Entregar um livro".

   Com o mapa desligado (biblioteca.mapa), a aba mostra só a lista de material.
*/

const est = { mapa: null, material: null, chaves: null, areasBase: [], sel: "", feitos: {}, pendente: null, nivel: -1 };
// A cor da área sai da ordem fixa das áreas da ficha (src/biblioteca/ficha.py),
// e não da ordem da tela: a cor não muda de um dia para o outro.
const CORES_AREA = ["#b78a52", "#6f8fb8", "#7fa383", "#b36f6a", "#9a7fb3", "#6fa8a3"];
const SIGLA_LEI = { cc: "CC", cpc: "CPC", cp: "CP", clt: "CLT", cdc: "CDC", cf: "CF", ctn: "CTN", eca: "ECA",
  inquilinato: "Inquilinato", cpp: "CPP", ctb: "CTB" };
const ICONE_OBRA = { doutrina: "menu_book", artigo: "menu_book", manual: "list", tabela: "table",
  modelo_de_peca: "description", outro: "menu_book" };
const NIVEIS_ESTANTE = [[0, "Estante de bolso"], [3, "Sala de leitura"], [5, "Biblioteca de consulta"], [8, "Biblioteca de referência"]];

async function carregarEstante() {
  const pega = (url) => fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  const [mapa, material, chaves, listas] = await Promise.all([
    pega("/api/biblioteca-juridica/mapa"), pega("/api/material"), pega("/api/chaves"), pega("/api/biblioteca-juridica")]);
  est.mapa = mapa;
  est.material = material || { itens: [] };
  est.chaves = chaves;
  est.areasBase = (listas && listas.areas) || [];
  // As funções do material (js/35-material.js) leem e redesenham por aqui.
  cfg.material = est.material;
  if (chaves) cfg.chaves = chaves;
  if (listas) cfg.biblioteca = listas;
  cfg.secao = "aprendizado";
}

function maiusculaEst(t) {
  const s = String(t || "");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function itemDoMaterial(id) {
  return ((est.material || {}).itens || []).find((m) => m.id === id) || null;
}

function oficial(item) {
  return Boolean(item && item.ficha && item.ficha.origem === "oficial");
}

function areasDaEstante() {
  const linhas = ((est.mapa || {}).areas || []).map((a) => {
    const todas = (a.obras || []).map((o) => Object.assign({}, o, { item: itemDoMaterial(o.id) }));
    const oficiais = todas.filter((o) => oficial(o.item));
    const obras = todas.filter((o) => !oficial(o.item));
    const i = est.areasBase.indexOf(a.area);
    return { area: a.area, nome: maiusculaEst(a.area), leis: a.leis || [], oficiais: oficiais, obras: obras,
      cor: CORES_AREA[(i < 0 ? 0 : i) % CORES_AREA.length] };
  });
  // As áreas com obra primeiro; dentro de cada grupo, a ordem fixa das áreas.
  return linhas.filter((a) => a.obras.length).concat(linhas.filter((a) => !a.obras.length));
}

function nivelDaEstante(areas) {
  const cobertas = areas.filter((a) => a.obras.length).length;
  const total = Math.max(1, areas.length);
  // O último nível é ter obra em todas as áreas do mapa (e nunca menos de 6).
  const niveis = NIVEIS_ESTANTE.map(([n, nome], i) => [i === NIVEIS_ESTANTE.length - 1 ? Math.max(6, areas.length) : n, nome]);
  let idx = 0;
  niveis.forEach((nv, i) => { if (cobertas >= nv[0]) idx = i; });
  const prox = niveis[idx + 1];
  const falta = prox ? prox[0] - cobertas : 0;
  return { idx: idx, nome: niveis[idx][1], feitas: cobertas, graus: Math.round(Math.min(1, cobertas / total) * 360),
    curto: prox ? "faltam " + falta + " para o próximo" : "completa",
    longo: prox ? "Mais " + falta + (falta === 1 ? " área com obra" : " áreas com obra") + " e você chega a " + prox[1]
      : "Todas as áreas têm obra" };
}

function resumoDaArea(a) {
  const partes = [];
  if (a.leis.length) partes.push(plural(a.leis.length, "lei", "leis"));
  if (a.oficiais.length) partes.push("súmulas do STJ");
  partes.push(a.obras.length ? plural(a.obras.length, "obra") : "nenhuma obra");
  return partes.join(" · ");
}

function itemDaEstante(chave, icone, rotulo, titulo, cor, tinta) {
  const classe = "est-item" + (est.sel === chave ? " escolhido" : "");
  return '<button type="button" class="' + classe + '" data-est-sel="' + esc(chave) + '" title="' + esc(titulo) + '">' +
    '<span class="est-item-marca" style="background:' + cor + ";color:" + tinta + '">' + ic(icone, 17) + "</span>" +
    "<span>" + esc(rotulo) + "</span></button>";
}

function linhaDaEstante(a) {
  const itens = a.leis.map((l) => itemDaEstante("lei:" + l.codigo, "gavel", SIGLA_LEI[l.codigo] || l.nome, "Lei em casa: " + l.nome,
      "var(--fill2)", "var(--ink2)"))
    .concat(a.oficiais.map((o) => itemDaEstante("obra:" + o.id, "gavel", "Súmulas STJ", o.titulo, "var(--fill2)", "var(--ink2)")))
    .concat(a.obras.map((o) => itemDaEstante("obra:" + o.id, ICONE_OBRA[((o.item || {}).ficha || {}).tipo] || "menu_book",
      o.titulo, o.titulo, a.cor, "#171716")));
  const vazio = a.obras.length ? "" :
    '<button type="button" class="est-item-mais" data-est-entregar="1" title="Entregar uma obra desta área">' + ic("add", 18) + "</button>";
  const n = a.obras.length;
  const chip = n >= 2 ? ["bem servida", "star", "ok"] : n === 1 ? ["com obra", "check", "ok"] : ["só a lei", "info", "atencao"];
  return '<div class="est-linha"><div class="est-area"><b>' + esc(a.nome) + "</b><small>" + esc(resumoDaArea(a)) + "</small></div>" +
    '<div class="est-itens">' + itens.join("") + vazio + "</div>" +
    '<span class="est-chip ' + chip[2] + '">' + ic(chip[1], 14) + esc(chip[0]) + "</span></div>";
}

function linhaSemArea() {
  const sem = ((est.mapa || {}).sem_area || []).map((o) => Object.assign({}, o, { item: itemDoMaterial(o.id) })).filter((o) => !oficial(o.item));
  if (!sem.length) return "";
  return '<div class="est-linha"><div class="est-area"><b>Sem área</b><small>' + esc(plural(sem.length, "obra") + " sem área na ficha") + "</small></div>" +
    '<div class="est-itens">' + sem.map((o) => itemDaEstante("obra:" + o.id, ICONE_OBRA[((o.item || {}).ficha || {}).tipo] || "menu_book",
      o.titulo, o.titulo, "var(--fill2)", "var(--ink2)")).join("") + "</div>" +
    '<span class="est-chip atencao">' + ic("info", 14) + "conferir a ficha</span></div>";
}

/* A faixa no pé das estantes: o que é o item escolhido, de verdade. */
function faixaDaEstante(areas) {
  if (!est.sel) return "";
  const [tipo, id] = est.sel.split(":");
  let f = null;
  if (tipo === "lei") {
    const lei = areas.flatMap((a) => a.leis).find((l) => l.codigo === id);
    if (lei) {
      f = { icone: "gavel", cor: "var(--fill2)", tinta: "var(--ink2)", titulo: "Lei em casa: " + lei.nome,
        sub: "Texto do Planalto, artigo por artigo · " + plural(lei.artigos || 0, "artigo"),
        nota: "A lei vem do endereço oficial e é guardada nesta máquina." };
    }
  } else {
    const item = itemDoMaterial(id);
    if (item) {
      const ficha = item.ficha || {};
      const area = areas.find((a) => a.obras.some((o) => o.id === id));
      if (oficial(item)) {
        f = { icone: "gavel", cor: "var(--fill2)", tinta: "var(--ink2)", titulo: ficha.titulo || item.nome,
          sub: "Súmulas · " + (ficha.autor || "tribunal") + " · vêm com o PAULUS",
          nota: "Do PDF oficial do tribunal, sem as canceladas. Eu cito a súmula pelo número.", mais: id };
      } else {
        const sub = [ROTULO_TIPO_MAT[ficha.tipo] || "Material", ficha.autor || "", [ficha.edicao ? ficha.edicao + " ed." : "", ficha.ano || ""].filter(Boolean).join(", ")]
          .filter(Boolean).join(" · ") + (ficha.confirmada ? "" : " · ficha a conferir");
        f = { icone: ICONE_OBRA[ficha.tipo] || "menu_book", cor: area ? area.cor : "var(--fill2)", tinta: area ? "#171716" : "var(--ink2)",
          titulo: ficha.titulo || item.nome, sub: sub, mais: id,
          nota: ficha.aviso || (ficha.confirmada ? "Entra nas respostas com o autor e a página."
            : "Li a ficha pelas primeiras páginas. Confira para eu citar certo.") };
      }
    }
  }
  if (!f) return "";
  return '<div class="est-faixa"><span class="est-faixa-marca" style="background:' + f.cor + ";color:" + f.tinta + '">' + ic(f.icone, 20) + "</span>" +
    '<div class="est-faixa-texto"><b>' + esc(f.titulo) + "</b><small>" + esc(f.sub) + "</small></div>" +
    '<span class="est-faixa-nota">' + esc(f.nota) + "</span>" +
    (f.mais ? '<button type="button" class="mais-linha" data-est-mais="' + esc(f.mais) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button>" : "") +
    '<button type="button" class="mais-linha" data-est-fechar="1" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>";
}

/* ------------------------------------------------------ próximos passos */

function passosDaEstante(areas) {
  const passos = [];
  const itens = ((est.material || {}).itens || []).filter((m) => !oficial(m));
  const conferir = itens.find((m) => m.ficha && !m.ficha.confirmada);
  if (conferir) {
    const titulo = conferir.ficha.titulo || conferir.nome;
    passos.push({ chave: "ficha:" + conferir.id, icone: "verified", titulo: "Confira a ficha de “" + titulo + "”",
      texto: "Li pelas primeiras páginas e deixei em branco o que não achei.", ganho: "cito com autor e página", acao: "Conferir",
      fazer: () => dialogoDaFicha(conferir),
      pronto: () => { const m = itemDoMaterial(conferir.id); return !m || Boolean(m.ficha && m.ficha.confirmada); },
      frase: "Ficha conferida: agora cito “" + titulo + "” com autor e página" });
  }
  const semObra = areas.find((a) => a.leis.length && !a.obras.length);
  if (semObra) {
    const siglas = semObra.leis.map((l) => SIGLA_LEI[l.codigo] || l.nome).join(" e ");
    passos.push({ chave: "area:" + semObra.area, icone: "auto_stories", titulo: "Dê um livro à estante " + semObra.nome,
      texto: siglas + (semObra.leis.length > 1 ? " já estão" : " já está") + " em casa, mas nenhuma obra comenta os artigos.",
      ganho: "+1 área com obra", acao: "Entregar", fazer: () => escolherMaterial(),
      pronto: () => areasDaEstante().some((a) => a.area === semObra.area && a.obras.length),
      frase: "Nova obra na estante " + semObra.nome });
  }
  const antiga = itens.find((m) => m.ficha && m.ficha.aviso);
  if (antiga) {
    passos.push({ chave: "aviso:" + antiga.id, icone: "history", titulo: "Uma obra ficou mais velha que a lei",
      texto: antiga.ficha.aviso, ganho: "aviso na resposta", acao: "Ver artigo", fazer: () => mostrarBibliotecaContexto("leis"),
      pronto: () => false, frase: "" });
  }
  const leitura = ((est.chaves || {}).biblioteca || {});
  if (est.chaves && !leitura.leitura) {
    passos.push({ chave: "leitura", icone: "menu_book", titulo: "Deixe eu ler as obras com calma",
      texto: "Em segundo plano, monto o glossário e as teses de cada autor, com a página.", ganho: "glossário e teses", acao: "Ligar",
      fazer: ligarLeituraDaEstante, pronto: () => Boolean(((est.chaves || {}).biblioteca || {}).leitura),
      frase: "Vou ler as obras em segundo plano" });
  }
  return passos;
}

async function ligarLeituraDaEstante() {
  const d = await ligarChave("biblioteca", "leitura", true);
  if (!d) return;
  try { await fetch("/api/biblioteca-juridica/ler", { method: "POST" }); } catch (err) { /* a chave já vale */ }
  recarregarEstante();
}

function cartaoDoPasso(p, feito) {
  return '<div class="est-passo' + (feito ? " feito" : "") + '">' +
    '<span class="est-passo-marca">' + ic(feito ? "check" : p.icone, 19) + "</span>" +
    '<div class="est-passo-texto"><b>' + esc(p.titulo) + "</b><small>" + esc(p.texto) + "</small>" +
    '<div class="est-passo-pe"><span class="est-ganho">' + esc(p.ganho) + "</span>" +
    (feito ? '<span class="est-passo-feito">Feito</span>'
      : '<button type="button" data-est-passo="' + esc(p.chave) + '">' + esc(p.acao) + "</button>") + "</div></div></div>";
}

/* Os feitos (desta vez que a tela está aberta) ficam esmaecidos; o resto
   sai dos dados de agora. No máximo quatro. */
function passosParaTela(areas) {
  const feitos = Object.values(est.feitos);
  const chaves = new Set(feitos.map((p) => p.chave));
  const novos = passosDaEstante(areas).filter((p) => !chaves.has(p.chave));
  return feitos.map((p) => ({ p: p, feito: true })).concat(novos.map((p) => ({ p: p, feito: false }))).slice(0, 4);
}

function artigosComentados() {
  const todos = [];
  ((est.mapa || {}).codigos || []).forEach((c) => (c.mais_comentados || []).forEach((m) =>
    todos.push({ a: (SIGLA_LEI[c.codigo] || c.nome) + " " + m.artigo, n: m.anotacoes || 0 })));
  todos.sort((x, y) => y.n - x.n);
  const total = ((est.mapa || {}).codigos || []).reduce((s, c) => s + (c.anotados || 0), 0);
  return { total: total, lista: todos.slice(0, 6) };
}

/* ------------------------------------------------------------ desenhar */

function cascaEstante(html) {
  $("centro").innerHTML = '<div class="acervo sem-painel cfg-tela bib-tela est-tela" id="cfg-tela">' +
    // Na coluna editorial de todas as telas sem painel (--fio, a do Financeiro).
    '<div class="acervo-principal sv-principal" id="bib-tela"><div class="sv-medida">' + html + "</div></div></div>";
  atualizarPostura();
}

function desenharEstante() {
  if (!est.mapa || !est.mapa.ligada) {
    // Sem o mapa: só a lista de material, sem nível nem estantes.
    cascaEstante('<div class="cfg-secao">' + cartaoMaterial() + "</div>");
    ligarMaterial();
    ligarSoltarNaEstante();
    return;
  }
  const areas = areasDaEstante();
  const nivel = nivelDaEstante(areas);
  const passos = passosParaTela(areas);
  const artigos = artigosComentados();
  const lendo = mat.enviando.length
    ? '<p class="est-lendo">lendo ' + (mat.enviando.length === 1 ? "“" + esc(mat.enviando[0]) + "”" : plural(mat.enviando.length, "arquivo")) + "…</p>" : "";
  const html =
    '<div class="est">' +
    '<header class="est-cabeca"><div class="est-titulo"><h1>Sua estante está crescendo</h1>' +
    "<p>Cada livro que você me entrega vira fonte nas respostas, com autor e página. Veja o que já sei e onde ainda falta.</p>" + lendo + "</div>" +
    '<div class="est-acoes"><div class="est-nivel" title="' + esc(nivel.longo) + '">' +
    '<span class="est-anel" style="--graus:' + nivel.graus + 'deg"><b>' + nivel.feitas + "</b></span>" +
    "<span><b>" + esc(nivel.nome) + "</b><small>" + esc(nivel.curto) + "</small></span></div>" +
    (((est.chaves || {}).biblioteca || {}).pacote
      ? '<button type="button" class="com-icone est-pacote" data-est-pacote="1" title="Um material que outro PAULUS exportou">' +
        ic("download", 16) + "Importar pacote</button>" : "") +
    '<button type="button" class="primario com-icone" data-est-entregar="1"' + (mat.enviando.length ? " disabled" : "") + ">" +
    ic("add", 18) + "Entregar um livro</button></div></header>" +
    '<div class="est-corpo">' +
    '<section class="est-estantes"><div class="est-estantes-cabeca"><span>Estantes por área</span>' +
    '<span class="est-legenda"><span><i class="lei"></i>lei em casa</span><span><i class="obra" style="background:' + CORES_AREA[0] + '"></i>obra do escritório</span></span></div>' +
    '<div class="est-linhas">' + (areas.map(linhaDaEstante).join("") + linhaSemArea() ||
      '<p class="nota est-vazio">Nenhuma estante ainda: entregue um livro ou um manual, ou instale um código em Leis e súmulas.</p>') + "</div>" +
    faixaDaEstante(areas) + "</section>" +
    '<aside class="est-lado">' +
    (passos.length ? '<section class="est-passos"><div class="est-lado-cabeca"><span>Próximos passos</span><small>' +
      passos.filter((x) => x.feito).length + " de " + passos.length + "</small></div>" +
      passos.map((x) => cartaoDoPasso(x.p, x.feito)).join("") + "</section>" : "") +
    '<section class="est-artigos"><div class="est-lado-cabeca"><span>Artigos que suas obras comentam</span><small>' + artigos.total + "</small></div>" +
    (artigos.lista.length
      ? '<div class="est-art-lista">' + artigos.lista.map((x) => '<span class="est-art"><b>' + esc(x.a) + "</b><span>" + x.n + "</span></span>").join("") + "</div>" +
        "<small>Ao citar um desses artigos, eu mostro a página da obra junto.</small>"
      : "<small>Quando uma obra do escritório comentar um artigo de lei, ele aparece aqui, com a página.</small>") +
    "</section></aside></div></div>";
  cascaEstante(html);
  ligarEstante(areas, passos);
}

function ligarEstante(areas, passos) {
  const raiz = $("bib-tela");
  if (!raiz) return;
  raiz.querySelectorAll("[data-est-entregar]").forEach((b) => { b.onclick = () => escolherMaterial(); });
  const pacote = raiz.querySelector("[data-est-pacote]");
  if (pacote) pacote.onclick = () => importarPacote();
  raiz.querySelectorAll("[data-est-sel]").forEach((b) => {
    b.onclick = () => { est.sel = est.sel === b.dataset.estSel ? "" : b.dataset.estSel; desenharEstante(); };
  });
  const fechar = raiz.querySelector("[data-est-fechar]");
  if (fechar) fechar.onclick = () => { est.sel = ""; desenharEstante(); };
  const mais = raiz.querySelector("[data-est-mais]");
  if (mais) mais.onclick = (e) => { e.stopPropagation(); menuDoMaterial(mais, mais.dataset.estMais); };
  raiz.querySelectorAll("[data-est-passo]").forEach((b) => {
    b.onclick = () => {
      const p = passos.map((x) => x.p).find((x) => x.chave === b.dataset.estPasso);
      if (!p) return;
      est.pendente = p;
      p.fazer();
    };
  });
  ligarSoltarNaEstante();
}

function ligarSoltarNaEstante() {
  const raiz = $("bib-tela");
  if (!raiz) return;
  raiz.ondragover = (e) => { e.preventDefault(); raiz.classList.add("sobre"); };
  raiz.ondragleave = (e) => { if (e.target === raiz) raiz.classList.remove("sobre"); };
  raiz.ondrop = (e) => {
    e.preventDefault();
    raiz.classList.remove("sobre");
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) enviarMaterial(e.dataTransfer.files);
  };
}

/* Depois de entregar, conferir uma ficha ou ligar a leitura, a tela lê de
   novo: o passo que terminou vira ✓, e o anel sobe - com aviso, se subiu. */
async function recarregarEstante() {
  await carregarEstante();
  if (bibc.aba !== "obras" || !$("bib-tela")) return;
  const areas = est.mapa && est.mapa.ligada ? areasDaEstante() : [];
  if (est.pendente && est.pendente.pronto()) {
    est.feitos[est.pendente.chave] = est.pendente;
    if (est.pendente.frase) avisoCert(est.pendente.frase, { tom: "ok" });
    est.pendente = null;
  }
  if (areas.length) {
    const nivel = nivelDaEstante(areas);
    if (est.nivel >= 0 && nivel.idx > est.nivel) avisoCert("Sua estante subiu: agora é " + nivel.nome, { tom: "ok" });
    est.nivel = nivel.idx;
  }
  desenharEstante();
}
