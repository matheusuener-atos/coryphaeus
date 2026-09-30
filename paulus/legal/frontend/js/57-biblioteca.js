/* ------------------------------------------------------ biblioteca (B1) */
/*
   A Biblioteca: o que o PAULUS consulta para responder, numa tela só do menu.
   Três abas:

   - Obras e lembretes: a seção que morava em Configurações › Biblioteca (o
     material de consulta com a ficha, o mapa "O que eu sei", as chaves, os
     lembretes e as habilidades). É a mesma seção, desenhada aqui:
     mostrarConfig("aprendizado") e desenharConfig() com essa seção abrem
     esta tela (05-configuracoes.js);
   - Leis e súmulas: a Constituição, os códigos e as súmulas do STJ que vêm
     com o PAULUS (src/biblioteca/nativo.py), e a consulta por artigo, por
     palavra e por súmula;
   - Tribunais e fontes: o processo pelo número no DataJud (só o número vai
     ao CNJ) e as buscas do Jusbrasil, do STF, do STJ, do TST e do LexML,
     que abrem no navegador - nenhum deles tem API aberta para programa.
*/

const bibc = {
  aba: "obras", nativo: null, leis: null, achados: null, sumulas: null, processo: null, consultando: false,
  fontes: null, termoFora: "", termoLei: "", termoSumula: "", codigoArtigo: "", numeroArtigo: "", numeroProcesso: "",
};

/* No celular, só a primeira palavra de cada aba cabe (36-biblioteca.css). */
const ABAS_BIB = [["obras", "Obras", " e lembretes"], ["leis", "Leis", " e súmulas"], ["tribunais", "Tribunais", " e fontes"]];

function bibAberta() {
  return $("conversa-titulo").textContent === "Biblioteca" && Boolean($("bib-tela"));
}

async function mostrarBibliotecaContexto(aba) {
  if (aba) bibc.aba = aba;
  if (typeof pararMedicao === "function") pararMedicao();
  abrirTela("Biblioteca", { cheia: true });
  marcarDestino("contexto");
  cabecalhoBib();
  cascaBib('<p class="nota">lendo…</p>');
  await carregarAbaBib();
  desenharBib();
}

function cabecalhoBib() {
  $("conversa-meta").textContent = "O que eu consulto para responder · fica nesta máquina";
  $("nav-tela").innerHTML = '<div class="visoes bib-abas">' + ABAS_BIB.map(([v, r, resto]) =>
    '<button class="' + (v === bibc.aba ? "ativa" : "") + '" data-bib-aba="' + v + '"><span>' + r + '<span class="bib-aba-resto">' + resto + "</span></span></button>").join("") + "</div>";
  $("acoes-tela").innerHTML = "";
  document.querySelectorAll("[data-bib-aba]").forEach((b) => {
    b.onclick = async () => {
      bibc.aba = b.dataset.bibAba;
      cabecalhoBib();
      await carregarAbaBib();
      desenharBib();
    };
  });
}

/* O mesmo invólucro das Configurações (#cfg-tela): os cartões são os de lá, e
   a seção de obras e lembretes se liga como sempre se ligou. */
function cascaBib(html) {
  $("centro").innerHTML = '<div class="acervo sem-painel cfg-tela bib-tela" id="cfg-tela"><div class="acervo-principal sv-principal" id="bib-tela">' +
    '<div class="sv-medida"><div class="cfg-secao">' + html + "</div></div></div></div>";
  atualizarPostura();
}

async function carregarAbaBib() {
  const pega = (url) => fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (bibc.aba === "obras") {
    cfg.secao = "aprendizado";
    await carregarSecao();
  } else if (bibc.aba === "leis") {
    const [nativo, leis] = await Promise.all([pega("/api/biblioteca/acervo-inicial"), pega("/api/leis")]);
    bibc.nativo = nativo;
    bibc.leis = leis;
  }
}

function desenharBib() {
  if (!$("bib-tela") && $("conversa-titulo").textContent !== "Biblioteca") return;
  if (bibc.aba === "obras") {
    cascaBib(secaoAprendizado());
    ligarConfig();
    return;
  }
  if (bibc.aba === "leis") {
    cascaBib(abaLeisBib());
    ligarLeisBib();
    return;
  }
  cascaBib(abaTribunaisBib());
  ligarTribunaisBib();
}

function aberturaBib(titulo, texto) {
  return '<header class="sv-resumo-topo"><div class="sv-resumo-cabeca"><h2>' + esc(titulo) + "</h2></div>" +
    '<p class="sv-resumo-corpo">' + esc(texto) + "</p></header>";
}

/* ---------------------------------------------------- leis e súmulas */

function abaLeisBib() {
  const n = bibc.nativo || { codigos: [], sumulas: [], falta: 0 };
  const leis = (bibc.leis && bibc.leis.codigos) || [];
  const instalados = leis.filter((c) => c.instalado);
  const local = typeof acessoDeFora === "undefined" || acessoDeFora.local;
  const artigos = instalados.reduce((s, c) => s + (c.artigos || 0), 0);
  const enunciados = (n.sumulas || []).filter((s) => s.instalado).reduce((s, x) => s + x.enunciados, 0);

  const falta = n.falta && local
    ? '<div class="bib-falta"><span class="duas-linhas"><b>' + plural(n.falta, "item do acervo está fora", "itens do acervo estão fora") + "</b>" +
      "<small>foram apagados nesta máquina; o PAULUS não os põe de volta sozinho</small></span>" +
      '<button class="primario com-icone" data-bib-por="1">' + ic("add", 16) + "Pôr de volta</button></div>"
    : "";

  const opcoes = instalados.map((c) => '<option value="' + esc(c.codigo) + '"' + (c.codigo === bibc.codigoArtigo ? " selected" : "") + ">" +
    esc(c.nome) + "</option>").join("");
  const consultar = cartaoCfg("Consultar", metaCfg("sem internet, no texto guardado"),
    '<div class="bib-linha-form"><label class="bib-campo"><span>Código</span><select id="bib-codigo">' + opcoes + "</select></label>" +
    '<label class="bib-campo bib-curto"><span>Artigo</span><input type="text" id="bib-artigo" inputmode="numeric" placeholder="5" value="' + esc(bibc.numeroArtigo) + '"></label>' +
    '<button class="com-icone" data-bib-artigo="1">' + ic("article", 16) + "Abrir artigo</button></div>" +
    '<div class="bib-linha-form"><label class="bib-campo cresce"><span>Palavras nos códigos</span><input type="text" id="bib-termo-lei" placeholder="usucapião especial urbana" value="' + esc(bibc.termoLei) + '"></label>' +
    '<button class="com-icone" data-bib-procurar-lei="1">' + ic("search", 16) + "Procurar nos códigos</button></div>" +
    '<div class="bib-linha-form"><label class="bib-campo cresce"><span>Súmula: número ou palavras</span><input type="text" id="bib-termo-sumula" placeholder="297 ou dano moral pessoa jurídica" value="' + esc(bibc.termoSumula) + '"></label>' +
    '<button class="com-icone" data-bib-procurar-sumula="1">' + ic("gavel", 16) + "Procurar súmula</button></div>" +
    '<div id="bib-achados">' + achadosBib() + "</div>");

  const linhasCodigos = leis.map((c) =>
    '<div class="cfg-lei"><span class="duas-linhas"><b>' + esc(c.nome) + "</b><small>" + esc(c.lei) +
    (c.instalado ? " · " + plural(c.artigos, "artigo") + " · " + esc(quandoCurto(c.importado_em)) : " · fora desta máquina") + "</small></span>" +
    (local ? '<button class="com-icone" data-bib-planalto="' + esc(c.codigo) + '" title="' + esc(c.fonte) + '">' + ic("sync", 16) + (c.instalado ? "Atualizar do Planalto" : "Baixar do Planalto") + "</button>" : "") +
    "</div>").join("");
  const codigos = cartaoCfg("A Constituição e os códigos", metaCfg(plural(instalados.length, "código") + " · " + plural(artigos, "artigo")),
    '<div class="cfg-linhas">' + linhasCodigos + "</div>" +
    '<p class="cfg-explica">Vêm com o PAULUS no texto compilado do Planalto, artigo por artigo, com o que foi revogado marcado. ' +
    "A conversa cita o artigo pelo texto guardado, e o editor insere a citação. O Planalto muda o texto quando sai lei nova: " +
    "“Atualizar do Planalto” baixa a página oficial de novo (só a página da lei é pedida; nada desta máquina vai junto).</p>");

  const linhasSumulas = (n.sumulas || []).map((s) =>
    '<div class="cfg-lei"><span class="duas-linhas"><b>' + esc(s.nome) + "</b><small>" + plural(s.enunciados, "enunciado vigente", "enunciados vigentes") +
    (s.instalado ? " · consultados em cada pergunta" : " · fora desta máquina") + "</small></span></div>").join("");
  const sumulas = cartaoCfg("Súmulas", metaCfg(plural(enunciados, "enunciado")),
    '<div class="cfg-linhas">' + linhasSumulas + "</div>" +
    '<p class="cfg-explica">As do STJ vêm do PDF oficial do tribunal, sem as canceladas e as revogadas, um trecho por enunciado: a conversa cita a súmula certa, e não metade de duas. ' +
    "As do STF e do TST não vieram: os sites deles recusam a leitura por programa. Salve a lista em PDF ou TXT e entregue em Obras e lembretes — eu guardo um trecho por enunciado também.</p>");

  const doutrina = cartaoCfg("Doutrina", metaCfg("o livro é do escritório"),
    '<p class="cfg-explica">Lei e decisão judicial não têm direito autoral (Lei 9.610/98, art. 8º, IV), por isso vêm com o PAULUS. Livro de doutrina tem autor e editora: não dá para vir no instalador. ' +
    "Entregue os livros e artigos que o escritório tem em Obras e lembretes: a ficha diz autor, edição e ano, e a resposta cita a página.</p>" +
    '<div class="cfg-botoes"><button class="com-icone" data-bib-ir-obras="1">' + ic("menu_book", 16) + "Ir para Obras e lembretes</button></div>");

  return aberturaBib("Leis e súmulas", "A Constituição, os códigos e as súmulas do STJ vêm com o PAULUS, no texto oficial. " +
      "Tudo fica nesta máquina e é consultado sem internet.") +
    fichaCfg([["Códigos", String(instalados.length)], ["Artigos", artigos.toLocaleString("pt-BR")], ["Súmulas", enunciados.toLocaleString("pt-BR")],
      ["Acervo de", n.montado_em ? dataCurtaMat(n.montado_em) : "—"]]) +
    falta + consultar + codigos + sumulas + doutrina;
}

function achadosBib() {
  if (bibc.achados === "lendo") return '<p class="nota">procurando…</p>';
  if (!bibc.achados) return "";
  const a = bibc.achados;
  if (a.erro) return '<p class="cfg-explica">' + esc(a.erro) + "</p>";
  if (a.tipo === "artigo") {
    const x = a.artigo;
    return '<div class="bib-achados">' + artigoBib(x) +
      ((a.vizinhos || []).length ? '<p class="cfg-explica">Perto dele: ' + a.vizinhos.map((v) =>
        '<button class="bib-link" data-bib-vizinho="' + esc(v.numero) + '">art. ' + esc(v.numero) + "</button>").join(" ") + "</p>" : "") + "</div>";
  }
  if (!a.itens.length) {
    return '<p class="cfg-explica">Não achei com essas palavras. Isso quer dizer que não achei — não que não exista.</p>';
  }
  if (a.tipo === "lei") return '<div class="bib-achados">' + a.itens.map(artigoBib).join("") + "</div>";
  return '<div class="bib-achados">' + a.itens.map((s) =>
    '<div class="artigo"><div class="artigo-topo"><b>' + esc(s.titulo) + "</b></div>" +
    '<p class="artigo-texto">' + esc(s.texto) + "</p></div>").join("") + "</div>";
}

function artigoBib(x) {
  return '<div class="artigo' + (x.revogado ? " revogado" : "") + '"><div class="artigo-topo"><b>' + esc(x.citacao || ("art. " + x.numero)) + "</b>" +
    (x.revogado ? '<span class="etiqueta prazo">revogado</span>' : "") +
    (x.alterado_por ? '<span class="rotulo">' + esc(x.alterado_por) + "</span>" : "") + "</div>" +
    (x.contexto ? '<span class="rotulo">' + esc(x.contexto) + "</span>" : "") +
    '<p class="artigo-texto">' + esc(x.texto.length > 1400 ? x.texto.slice(0, 1400) + "…" : x.texto) + "</p></div>";
}

function redesenharAchadosBib() {
  const alvo = $("bib-achados");
  if (alvo) alvo.innerHTML = achadosBib();
  document.querySelectorAll("[data-bib-vizinho]").forEach((b) => {
    b.onclick = () => { bibc.numeroArtigo = b.dataset.bibVizinho; const c = $("bib-artigo"); if (c) c.value = bibc.numeroArtigo; abrirArtigoBib(); };
  });
}

async function abrirArtigoBib() {
  bibc.codigoArtigo = ($("bib-codigo") || {}).value || "";
  bibc.numeroArtigo = String(($("bib-artigo") || {}).value || "").trim().replace(/^art\.?\s*/i, "").replace(/[º°o]$/, "");
  if (!bibc.codigoArtigo || !bibc.numeroArtigo) return;
  bibc.achados = "lendo";
  redesenharAchadosBib();
  const r = await fetch("/api/leis/artigo?codigo=" + encodeURIComponent(bibc.codigoArtigo) + "&numero=" + encodeURIComponent(bibc.numeroArtigo));
  bibc.achados = r.ok ? Object.assign({ tipo: "artigo" }, await r.json()) : { erro: await erroDe(r) };
  redesenharAchadosBib();
}

async function procurarLeiBib() {
  bibc.termoLei = String(($("bib-termo-lei") || {}).value || "").trim();
  if (!bibc.termoLei) return;
  bibc.achados = "lendo";
  redesenharAchadosBib();
  const r = await fetch("/api/leis/procurar?termo=" + encodeURIComponent(bibc.termoLei));
  const d = r.ok ? await r.json() : null;
  bibc.achados = d ? { tipo: "lei", itens: d.achados || [] } : { erro: await erroDe(r) };
  redesenharAchadosBib();
}

async function procurarSumulaBib() {
  bibc.termoSumula = String(($("bib-termo-sumula") || {}).value || "").trim();
  if (!bibc.termoSumula) return;
  bibc.achados = "lendo";
  redesenharAchadosBib();
  const numero = /^\s*(s[úu]mula\s*)?\d{1,4}\s*$/i.test(bibc.termoSumula) ? bibc.termoSumula.replace(/\D/g, "") : "";
  const r = await fetch("/api/biblioteca/sumulas?" + (numero ? "numero=" + numero : "termo=" + encodeURIComponent(bibc.termoSumula)));
  const d = r.ok ? await r.json() : null;
  bibc.achados = d ? { tipo: "sumula", itens: d.achados || [] } : { erro: await erroDe(r) };
  redesenharAchadosBib();
}

function ligarLeisBib() {
  const raiz = $("bib-tela");
  if (!raiz) return;
  const clique = (sel, fn) => raiz.querySelectorAll(sel).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b); }; });
  const enter = (id, fn) => { const c = $(id); if (c) c.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); fn(); } }; };
  clique("[data-bib-artigo]", abrirArtigoBib);
  clique("[data-bib-procurar-lei]", procurarLeiBib);
  clique("[data-bib-procurar-sumula]", procurarSumulaBib);
  enter("bib-artigo", abrirArtigoBib);
  enter("bib-termo-lei", procurarLeiBib);
  enter("bib-termo-sumula", procurarSumulaBib);
  clique("[data-bib-ir-obras]", () => mostrarBibliotecaContexto("obras"));
  clique("[data-bib-por]", async (b) => {
    b.disabled = true;
    b.textContent = "pondo…";
    const r = await fetch("/api/biblioteca/acervo-inicial", { method: "POST" });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); } else {
      const d = (await r.json()).entraram || {};
      const partes = [];
      if ((d.codigos || []).length) partes.push(plural(d.codigos.length, "código voltou", "códigos voltaram"));
      if ((d.sumulas || []).length) partes.push("as súmulas voltaram");
      avisoCert(partes.join(" · ") || "nada faltava", { tom: (d.erros || []).length ? "erro" : "ok" });
    }
    mostrarBibliotecaContexto("leis");
  });
  /* O texto compilado oficial, direto do endereço do Planalto: só a página
     da lei é pedida, nada desta máquina vai junto. */
  clique("[data-bib-planalto]", async (b) => {
    b.disabled = true;
    b.textContent = "baixando…";
    const r = await fetch("/api/leis/baixar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ codigo: b.dataset.bibPlanalto }) });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); mostrarBibliotecaContexto("leis"); return; }
    const d = await r.json();
    avisoCert(d.nome + ": " + plural(d.artigos, "artigo") + " guardados" + (d.revogados ? ", " + plural(d.revogados, "revogado") : ""), { tom: "ok" });
    mostrarBibliotecaContexto("leis");
  });
  redesenharAchadosBib();
}

/* ------------------------------------------------ tribunais e fontes */

function abaTribunaisBib() {
  const p = bibc.processo;
  let resultado = "";
  if (bibc.consultando) resultado = '<p class="nota">consultando o DataJud… ele costuma levar de 20 segundos a um minuto</p>';
  else if (p && p.erro) resultado = '<p class="cfg-explica bib-erro">' + esc(p.erro) + "</p>";
  else if (p && !p.graus.length) resultado = '<p class="cfg-explica">O DataJud não tem o processo ' + esc(p.numero) + " no " + esc(p.tribunal) +
    ". Processo novo demora a aparecer, e o que corre em segredo de justiça não aparece.</p>";
  else if (p) {
    resultado = p.graus.map((g) =>
      '<div class="bib-processo"><div class="artigo-topo"><b>' + esc(p.numero) + "</b>" +
      '<span class="etiqueta">' + esc(g.tribunal + (g.grau ? " · " + g.grau : "")) + "</span></div>" +
      '<div class="cfg-chaves cfg-chaves-duas">' +
      chaveCfg("Classe", g.classe || "—") + chaveCfg("Órgão julgador", g.orgao || "—") +
      chaveCfg("Ajuizado em", g.ajuizamento ? dataCurtaMat(g.ajuizamento) : "—") + chaveCfg("Sistema", g.sistema || "—") + "</div>" +
      (g.assuntos.length ? '<p class="cfg-explica"><b>Assuntos:</b> ' + esc(g.assuntos.join("; ")) + "</p>" : "") +
      '<div class="bib-movimentos">' + g.movimentos.map((m) =>
        '<div class="bib-movimento"><small>' + esc(dataCurtaMat(m.quando) + " " + m.quando.slice(11, 16)) + "</small><span>" + esc(m.nome) +
        (m.complemento ? " — " + esc(m.complemento) : "") + "</span></div>").join("") + "</div>" +
      (g.total_movimentos > g.movimentos.length ? '<p class="cfg-explica">Os ' + g.movimentos.length + " mais recentes de " + g.total_movimentos + " movimentos.</p>" : "") +
      "</div>").join("") +
      '<p class="cfg-explica">Fonte: ' + esc(p.fonte) + ", consultado agora. O DataJud atualiza com atraso de dias e não traz o teor das decisões: confira no sistema do tribunal antes de contar prazo.</p>";
  }

  const processo = cartaoCfg("Processo pelo número (DataJud, CNJ)", metaCfg("só o número sai desta máquina"),
    '<div class="bib-linha-form"><label class="bib-campo cresce"><span>Número único do processo</span><input type="text" id="bib-processo" placeholder="0000000-00.0000.0.00.0000" value="' + esc(bibc.numeroProcesso) + '"></label>' +
    '<button class="primario com-icone" data-bib-datajud="1"' + (bibc.consultando ? " disabled" : "") + ">" + ic("search", 16) + "Consultar no DataJud</button></div>" +
    '<div id="bib-processo-resultado">' + resultado + "</div>" +
    '<p class="cfg-explica">O DataJud é a base pública do CNJ: classe, órgão julgador, assuntos e movimentos de todos os tribunais, menos o STF. ' +
    "O PAULUS confere o dígito verificador, acha o tribunal pelo número e manda só o número para a API pública do CNJ. Nada é guardado.</p>");

  const links = (bibc.fontes || []).map((l) =>
    '<div class="cfg-lei"><span class="duas-linhas"><b>' + esc(l.nome) + "</b><small>" + esc(l.o_que) + "</small></span>" +
    '<button class="com-icone" data-bib-abrir-fora="' + esc(l.url) + '">' + ic("open_in_new", 16) + "Abrir no navegador</button></div>").join("");
  const fora = cartaoCfg("Jurisprudência e legislação na internet", metaCfg("abre no navegador"),
    '<div class="bib-linha-form"><label class="bib-campo cresce"><span>O que procurar</span><input type="text" id="bib-termo-fora" placeholder="dano moral negativação indevida" value="' + esc(bibc.termoFora) + '"></label>' +
    '<button class="com-icone" data-bib-montar="1">' + ic("search", 16) + "Montar as buscas</button></div>" +
    (links ? '<div class="cfg-linhas">' + links + "</div>" : "") +
    '<p class="cfg-explica">Jusbrasil, STF, STJ, TST e LexML não têm API aberta para programa: os termos de uso do Jusbrasil proíbem a leitura automática, e o LexML e o STF barram robô. ' +
    "Por isso a busca abre no navegador, com o que você escreveu. O acórdão que servir, salve em PDF e entregue em Obras e lembretes: aí eu passo a consultar e citar.</p>");

  return aberturaBib("Tribunais e fontes", "O processo pelo número no DataJud, do CNJ, e as buscas de jurisprudência e legislação dos sites oficiais e do Jusbrasil.") +
    processo + fora;
}

async function consultarDatajudBib() {
  bibc.numeroProcesso = String(($("bib-processo") || {}).value || "").trim();
  if (!bibc.numeroProcesso || bibc.consultando) return;
  bibc.consultando = true;
  bibc.processo = null;
  desenharBib();
  let r = null;
  try {
    r = await fetch("/api/biblioteca/datajud", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ numero: bibc.numeroProcesso }) });
  } catch (err) { r = null; }
  bibc.consultando = false;
  bibc.processo = !r ? { erro: "não consegui falar com o PAULUS" } : (r.ok ? await r.json() : { erro: await erroDe(r) });
  if (bibc.aba === "tribunais" && bibAberta()) desenharBib();
}

function montarBuscasBib() {
  bibc.termoFora = String(($("bib-termo-fora") || {}).value || "").trim();
  if (!bibc.termoFora) return;
  fetch("/api/biblioteca/fontes?termo=" + encodeURIComponent(bibc.termoFora)).then((r) => r.json()).then((d) => {
    bibc.fontes = d.links || [];
    desenharBib();
  }).catch(() => avisoCert("não consegui montar as buscas", { tom: "erro" }));
}

function ligarTribunaisBib() {
  const raiz = $("bib-tela");
  if (!raiz) return;
  const clique = (sel, fn) => raiz.querySelectorAll(sel).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b); }; });
  clique("[data-bib-datajud]", consultarDatajudBib);
  clique("[data-bib-montar]", montarBuscasBib);
  clique("[data-bib-abrir-fora]", (b) => window.open(b.dataset.bibAbrirFora, "_blank"));
  const campo = $("bib-processo");
  if (campo) campo.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); consultarDatajudBib(); } };
  const termo = $("bib-termo-fora");
  if (termo) termo.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); montarBuscasBib(); } };
}
