/* ------------------------------------------------------------ agentes (A3/A4) */
/*
   A tela "Agentes" (docs/prompt-conversa-agentes-v0.md, §2.6 e A3/A4). Um
   agente e um AGENTE.md que o escritorio escreve; a tela e o jeito de fazer
   isso sem abrir arquivo:

   - a lista (ativo, versao, origem, com problema, precisa de revisao) e a
     medida de cada um (A4): o ultimo resultado dos testes, as vezes usado, as
     vezes que a pessoa escolheu "nao usar" e - como o programa nao avalia
     resposta - "sem avaliação" no lugar das respostas ruins;
   - o formulario que grava o AGENTE.md (src/agentes_tela.py monta o YAML) e
     a visao do markdown para quem quer editar direto. A validacao da A1
     aparece em portugues ANTES de salvar, e salvar fica travado enquanto ha
     erro;
   - "Criar agente a partir desta conversa": o servidor sugere por regra (as
     perguntas viram exemplos, as palavras mais repetidas viram palavras, o
     titulo vira o nome) e o formulario abre preenchido. Nada e gravado ate a
     pessoa clicar em "Criar agente";
   - "Testar": os testes do agente pela conversa, com as instrucoes dele e sem
     ferramenta nenhuma; passou ou falhou, com o que faltou;
   - editar mostra a versao atual e as anteriores, cada uma legivel.

   De fora (acesso pela internet, o celular) a lista e o teste funcionam;
   criar, editar, ligar e importar ficam no computador do escritorio - as
   rotas ja recusam de fora (TITULAR), e a tela nem oferece.
*/

const agt = {
  lista: null, ligado: true, catalogos: null, contagem: null, pasta: "",
  vista: "lista", aberto: null, testes: {}, rodando: "",
  // a edicao
  editando: "", form: null, markdown: "", modo: "formulario", formMudou: false, validacao: null,
  daConversa: null, validarTimer: null, versaoBase: 0,
};

const FRASE_AGENTES_SO_NO_ESCRITORIO = "Criar, editar e ligar agentes fica no computador do escritório.";
const ONDE_PROCURA = { acervo: "Todo o Acervo", documento_em_foco: "Só o documento em foco da conversa", pastas: "Só estas pastas do Acervo" };
const FORMATO_SAIDA = { texto: "Texto corrido", lista: "Lista", tabela: "Tabela", modelo_de_documento: "Modelo de documento" };
const ORIGEM_AGENTE = { escritorio: "do escritório", importado: "importado", produto: "exemplo do PAULUS" };

function agentesSoLeitura() {
  return !acessoDeFora.local;
}

/* A conversa oferece "Criar agente desta conversa" so com a chave ligada e
   no computador do escritorio (01-conversas.js, menu da conversa). */
function agentesNaConversa() {
  return Boolean((window.PAULUS_CONVERSA || {}).agentes) && acessoDeFora.local;
}

async function mostrarAgentes(abrir) {
  abrirTela("Agentes", { cheia: true });
  marcarDestino("agentes");
  $("conversa-meta").textContent = "Especialistas escritos pelo escritório";
  cascaAgentes('<p class="nota">lendo…</p>');
  await carregarAgentes();
  if (abrir && abrir.conversa) return agenteDaConversa(abrir.conversa);
  if (abrir && abrir.slug) return abrirAgente(abrir.slug);
  agt.vista = "lista";
  desenharAgentes();
}

async function carregarAgentes() {
  try {
    const r = await fetch("/api/agentes");
    const d = r.ok ? await r.json() : null;
    agt.lista = d ? d.agentes : [];
    agt.ligado = d ? d.ligado !== false : false;
    agt.catalogos = d ? d.catalogos : null;
    agt.contagem = d ? d.contagem : null;
    agt.pasta = d ? d.pasta : "";
  } catch (err) {
    agt.lista = [];
  }
}

function cascaAgentes(html) {
  $("centro").innerHTML = '<div class="acervo sem-painel agt-tela" id="agt-tela"><div class="acervo-principal sv-principal">' +
    '<div class="sv-medida">' + html + "</div></div></div>";
  atualizarPostura();
}

function desenharAgentes() {
  if ($("conversa-titulo").textContent !== "Agentes") return;
  if (agt.vista === "agente") return desenharAgente();
  if (agt.vista === "editar") return desenharEdicao();
  return desenharListaDeAgentes();
}

/* ------------------------------------------------------------ pecas */

function etiquetasDoAgente(a) {
  const e = [];
  if (a.problema) e.push('<span class="etiqueta prazo"><i></i>com problema</span>');
  else if (a.ativo) e.push('<span class="etiqueta ok"><i></i>ativo</span>');
  else e.push('<span class="etiqueta"><i></i>desativado</span>');
  if (a.precisa_revisao) e.push('<span class="etiqueta atencao" data-agt-revisao="1">precisa de revisão</span>');
  if (a.precisa_aprovar) e.push('<span class="etiqueta atencao">falta aprovar o importado</span>');
  if (!a.problema) e.push('<span class="etiqueta">versão ' + esc(a.versao) + "</span>");
  e.push('<span class="etiqueta tipo">' + esc(ORIGEM_AGENTE[a.origem] || a.origem) + "</span>");
  return '<span class="agt-etiquetas">' + e.join("") + "</span>";
}

/* A medida em uma linha (A4): o que ha, e "sem avaliação" onde nao ha. */
function linhaDaMedida(a) {
  const m = a.medida || {};
  const t = m.testes;
  const partes = [];
  if (t) partes.push("testes " + t.passaram + "/" + t.total + (t.da_versao_atual ? "" : " (da versão " + t.versao + ")"));
  else partes.push((a.testes || []).length ? "testes ainda não rodados" : "sem testes");
  partes.push("usado " + (m.usado || 0) + "×");
  partes.push("“não usar” " + (m.nao_usar || 0) + "×");
  partes.push("sem avaliação");
  return partes.join(" · ");
}

/* A volta de dentro de um agente: a migalha acima do titulo, como a dos
   grupos de conversa - a seta do cabecalho continua levando ao inicio. */
function migalhaDeAgentes(atributo, rotulo) {
  return '<button class="sv-ligacao agt-migalha" ' + atributo + '="1">' + ic("chevron_left", 16) + esc(rotulo) + "</button>";
}

function dataCurtaAgt(iso) {
  const s = String(iso || "");
  return s.length >= 16 ? s.slice(8, 10) + "/" + s.slice(5, 7) + " às " + s.slice(11, 16) : "";
}

/* ------------------------------------------------------------ a lista */

function desenharListaDeAgentes() {
  const lista = agt.lista || [];
  const so = agentesSoLeitura();
  $("conversa-titulo").textContent = "Agentes";
  $("nav-tela").innerHTML = "";
  $("acoes-tela").innerHTML = so || !agt.ligado ? "" :
    '<button class="com-icone" data-agt-importar="1">' + ic("upload", 16) + "Importar</button>" +
    '<button class="com-icone" data-agt-da-conversa="1">' + ic("forum", 16) + "A partir de uma conversa</button>" +
    '<button class="primario com-icone" data-agt-novo="1">' + ic("add", 16) + "Novo agente</button>";
  const c = agt.contagem || {};
  const desligados = lista.filter((a) => !a.ativo && !a.problema).length;
  const topo = '<header class="sv-resumo-topo"><div class="sv-resumo-cabeca"><h2>Agentes do escritório</h2></div>' +
    '<p class="sv-resumo-corpo">Especialistas que o escritório escreve em linguagem simples. Um agente usa as capacidades e as ferramentas do PAULUS ' +
    "dentro dos limites que declara: não amplia a permissão de ninguém, e cada ferramenta continua pedindo confirmação.</p></header>";
  const ficha = '<div class="sv-ficha cfg-ficha">' + [
    ["Agentes", String(lista.length)], ["Em uso", String(c.em_uso || 0)], ["Desativados", String(desligados)],
    ["Com problema", String(c.com_problema || 0)], ["Precisam de revisão", String(c.precisa_revisao || 0)],
  ].map(([r, v]) => '<div class="sv-ficha-item"><span class="sv-kicker">' + esc(r) + "</span><b>" + esc(v) + "</b></div>").join("") + "</div>";
  const avisos = [];
  if (!agt.ligado) avisos.push('<div class="agt-aviso">' + ic("pause", 18) + "<span>Os agentes estão desligados nesta máquina (chave <b>conversa.agentes</b>): dá para ver a lista, mas não criar, testar nem usar.</span></div>");
  if (so) avisos.push('<div class="agt-aviso" data-agt-so-leitura="1">' + ic("lan", 18) + "<span>" + esc(FRASE_AGENTES_SO_NO_ESCRITORIO) + " Daqui dá para ver cada agente e rodar os testes dele.</span></div>");
  const linhas = lista.length ? lista.map((a) =>
    '<div class="cfg-servico agt-linha" data-agt-linha="' + esc(a.slug) + '">' +
      '<span class="caixa-tipo">' + ic(a.problema ? "error" : "school", 18) + "</span>" +
      '<span class="duas-linhas"><b>' + esc(a.nome || a.slug) + "</b><small>" + esc(a.problema || a.descricao || "") + "</small>" +
      '<small class="agt-medida-linha">' + esc(linhaDaMedida(a)) + "</small>" + etiquetasDoAgente(a) + "</span>" +
      '<span class="cfg-botoes"><button data-agt-abrir="' + esc(a.slug) + '">Abrir</button></span></div>').join("")
    : '<p class="cfg-texto">Nenhum agente ainda. Crie um pelo formulário, ou a partir de uma conversa que deu certo.</p>';
  cascaAgentes(topo + ficha + avisos.join("") +
    cartaoCfg("Agentes", metaCfg(plural(lista.length, "agente")), linhas) +
    (so ? "" : '<p class="cfg-explica">Os arquivos ficam em ' + esc(agt.pasta || "data/agentes") + ", um AGENTE.md por pasta. Nada sai desta máquina.</p>"));
  ligarListaDeAgentes();
}

function ligarListaDeAgentes() {
  const raiz = $("centro");
  raiz.querySelectorAll("[data-agt-abrir]").forEach((b) => { b.onclick = () => abrirAgente(b.dataset.agtAbrir); });
  raiz.querySelectorAll("[data-agt-linha]").forEach((l) => {
    l.ondblclick = () => abrirAgente(l.dataset.agtLinha);
  });
  const acoes = $("acoes-tela");
  const novo = acoes.querySelector("[data-agt-novo]");
  if (novo) novo.onclick = () => novoAgente();
  const conv = acoes.querySelector("[data-agt-da-conversa]");
  if (conv) conv.onclick = () => escolherConversaParaAgente();
  const imp = acoes.querySelector("[data-agt-importar]");
  if (imp) imp.onclick = () => importarAgente();
}

/* ------------------------------------------------------------ um agente */

async function abrirAgente(slug) {
  try {
    const r = await fetch("/api/agentes/" + encodeURIComponent(slug));
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    agt.aberto = await r.json();
  } catch (err) {
    avisoCert("não consegui ler o agente", { tom: "erro" });
    return;
  }
  agt.vista = "agente";
  desenharAgentes();
}

function voltarParaAgentes() {
  agt.vista = "lista";
  agt.aberto = null;
  carregarAgentes().then(desenharAgentes);
}

function desenharAgente() {
  const d = agt.aberto;
  if (!d) return voltarParaAgentes();
  const a = d.ficha;
  const so = agentesSoLeitura();
  $("conversa-titulo").textContent = "Agentes";
  $("nav-tela").innerHTML = "";
  const botoes = [];
  if (!a.problema && agt.ligado) botoes.push('<button class="com-icone" data-agt-testar="1"' + (agt.rodando ? " disabled" : "") + ">" + ic("task_alt", 16) + "Testar</button>");
  if (!so && agt.ligado) {
    botoes.push('<button class="com-icone" data-agt-editar="1">' + ic("edit", 16) + "Editar</button>");
    if (!a.problema) botoes.push(a.ativo
      ? '<button data-agt-desativar="1">Desativar</button>'
      : '<button class="primario com-icone" data-agt-ativar="1">' + ic("check", 16) + "Ativar</button>");
  }
  $("acoes-tela").innerHTML = botoes.join("");

  const topo = migalhaDeAgentes("data-agt-voltar", "Agentes") +
    '<header class="sv-resumo-topo"><div class="sv-resumo-cabeca"><h2>' + esc(a.nome || a.slug) + "</h2></div>" +
    '<p class="sv-resumo-corpo">' + esc(a.descricao || "") + "</p>" + etiquetasDoAgente(a) + "</header>";
  const avisos = [];
  if (a.problema) avisos.push('<div class="agt-aviso erro">' + ic("error", 18) + "<span><b>Com problema:</b> " + esc(a.problema) + "</span></div>");
  if (a.precisa_revisao) avisos.push('<div class="agt-aviso atencao" data-agt-aviso-revisao="1">' + ic("rule", 18) + "<span><b>Precisa de revisão:</b> " + esc(a.revisao_motivo) + "</span></div>");
  if (a.precisa_aprovar) avisos.push('<div class="agt-aviso atencao">' + ic("shield_person", 18) + "<span><b>Importado:</b> é tratado como dado até o titular ler o conteúdo inteiro e as ferramentas que ele pede. Ativar mostra tudo antes.</span></div>");
  (a.suspeitas || []).forEach((s) => avisos.push('<div class="agt-aviso atencao">' + ic("flag", 18) + "<span>Parece ordem ao assistente no texto importado: " + esc(s) + "</span></div>"));
  (a.avisos || []).forEach((s) => avisos.push('<div class="agt-aviso">' + ic("info", 18) + "<span>" + esc(s) + "</span></div>"));
  if (so) avisos.push('<div class="agt-aviso" data-agt-so-leitura="1">' + ic("lan", 18) + "<span>" + esc(FRASE_AGENTES_SO_NO_ESCRITORIO) + "</span></div>");

  const qu = a.quando_usar || {};
  const acervo = (a.fontes || {}).acervo;
  const onde = acervo && typeof acervo === "object" ? ONDE_PROCURA.pastas + ": " + (acervo.pastas || []).join(", ") : (ONDE_PROCURA[acervo] || acervo || "—");
  const ferr = (a.ferramentas || []).length ? a.ferramentas.join(", ") : "nenhuma (só responde)";
  const quando = a.problema ? "" : cartaoCfg("Quando usar", "",
    '<div class="agt-par"><span class="sv-kicker">Exemplos de pedido</span>' +
      ((qu.exemplos || []).length ? "<ul>" + qu.exemplos.map((x) => "<li>" + esc(x) + "</li>").join("") + "</ul>" : '<p class="cfg-texto">nenhum</p>') + "</div>" +
    '<div class="agt-par"><span class="sv-kicker">Palavras</span><p class="cfg-texto">' + esc((qu.palavras || []).join(", ") || "nenhuma") + "</p></div>" +
    '<div class="agt-par"><span class="sv-kicker">Onde procura</span><p class="cfg-texto">' + esc(onde) + "</p></div>" +
    '<div class="agt-par"><span class="sv-kicker">Formato da resposta</span><p class="cfg-texto">' + esc(FORMATO_SAIDA[(a.saida || {}).formato] || (a.saida || {}).formato || "texto") + "</p></div>" +
    '<div class="agt-par"><span class="sv-kicker">Ferramentas</span><p class="cfg-texto">' + esc(ferr) +
      ((a.ferramentas || []).length ? " — cada uma pede confirmação antes de agir, e o pedido também vai para Aprovações." : "") + "</p></div>" +
    '<p class="cfg-explica">Na conversa: pelo nome (“@' + esc((a.nome || "").split(" ")[0]) + "” ou o seletor acima do campo) ou, ativo, quando o pedido parece com os exemplos ou tem as palavras.</p>");

  const instr = a.problema ? "" : cartaoCfg("Instruções", metaCfg("vão ao modelo abaixo das regras do produto"),
    '<div class="agt-pre">' + esc(a.instrucoes || "") + "</div>");
  cascaAgentes(topo + avisos.join("") + '<div class="agt-grade"><div class="agt-coluna">' + quando + instr + blocoDeTestes(a) +
    "</div><div class=\"agt-coluna\">" + blocoDaMedida(a) + blocoDeVersoes(a, d) + "</div></div>");
  ligarAgente();
}

/* A medida do agente (A4): o painel por agente. */
function blocoDaMedida(a) {
  const m = a.medida || {};
  const t = m.testes;
  const linhas = [];
  linhas.push(["Acerto nos testes", t ? t.passaram + " de " + t.total + " · versão " + t.versao + (t.da_versao_atual ? "" : " (a atual é " + a.versao + ")") +
    (t.em ? " · " + dataCurtaAgt(t.em) : "") + (t.origem === "medir" ? " · pela medição" : "") : ((a.testes || []).length ? "ainda não testado" : "sem testes")]);
  linhas.push(["Vezes usado", String(m.usado || 0) + (m.usado_em ? " · a última em " + dataCurtaAgt(m.usado_em) : "")]);
  linhas.push(["Vezes “não usar”", String(m.nao_usar || 0) + " — a regra sugeria o agente e a pessoa escolheu sem agente"]);
  linhas.push(["Respostas avaliadas como ruins", "sem avaliação — o programa ainda não avalia respostas"]);
  return cartaoCfg("Medida", "", '<div class="propriedades agt-medida">' + linhas.map(([k, v]) =>
    "<div><span>" + esc(k) + '</span><span class="valor-prop">' + esc(v) + "</span></div>").join("") + "</div>");
}

function blocoDeTestes(a) {
  if (a.problema) return "";
  const testes = a.testes || [];
  const r = agt.testes[a.slug];
  const rodando = agt.rodando === a.slug;
  let corpo;
  if (!testes.length) corpo = '<p class="cfg-texto">Sem testes. Acrescente em Editar: uma pergunta e as palavras que a resposta certa tem.</p>';
  else {
    corpo = testes.map((t, i) => {
      const res = r && r.resultados ? r.resultados[i] : null;
      const estadoT = res ? (res.passou ? '<span class="etiqueta ok"><i></i>passou</span>' : '<span class="etiqueta prazo"><i></i>falhou</span>') : "";
      const motivo = res && !res.passou ? '<p class="agt-motivo">' + esc(res.erro ? "deu erro: " + res.erro : "faltou: " + (res.faltou || []).join(", ")) + "</p>" : "";
      const resposta = res && res.resposta ? '<details class="agt-resposta"><summary>ver a resposta (' + esc(String(res.segundos).replace(".", ",")) + " s)</summary><div class=\"agt-pre\">" + esc(res.resposta) + "</div></details>" : "";
      return '<div class="agt-teste" data-agt-teste="' + i + '"><div class="agt-teste-cabeca"><b>' + esc(t.pergunta) + "</b>" + estadoT + "</div>" +
        '<small>deve conter: ' + esc((t.deve_conter || []).join(", ")) + "</small>" + motivo + resposta + "</div>";
    }).join("");
  }
  const meta = rodando ? '<small class="agt-rodando"><span class="indicador"><i></i></span>rodando ' + plural(testes.length, "pergunta") + "…</small>"
    : (r ? metaCfg(r.passaram + " de " + r.total + " passaram") : "");
  const nota = testes.length
    ? '<p class="cfg-explica">Testar roda cada pergunta pela conversa, com as instruções deste agente e o perfil de modelo dele, e nenhuma ferramenta é executada. Cada pergunta entra na fila do modelo como uma pergunta da conversa.</p>'
    : "";
  return cartaoCfg("Testes", meta, corpo + nota, "agt-testes");
}

function blocoDeVersoes(a, d) {
  const anteriores = (a.versoes || []).slice().reverse();
  const corpo = '<div class="cfg-servico"><span class="duas-linhas"><b>Versão ' + esc(a.versao) + " · atual</b><small>" +
    esc(a.atualizado_em ? "gravada em " + dataCurtaAgt(a.atualizado_em) : "") + "</small></span>" +
    '<span class="cfg-botoes"><button data-agt-ver-md="1">Ver o markdown</button></span></div>' +
    (anteriores.length ? anteriores.map((n) => '<div class="cfg-servico"><span class="duas-linhas"><b>Versão ' + esc(n) + "</b><small>anterior</small></span>" +
      '<span class="cfg-botoes"><button data-agt-versao="' + esc(n) + '">Ler</button></span></div>').join("")
      : '<p class="cfg-texto">Nenhuma versão anterior: cada edição salva guarda a de antes aqui.</p>') +
    (d.original ? '<div class="cfg-servico"><span class="duas-linhas"><b>Original importado</b><small>como veio, antes da conversão</small></span>' +
      '<span class="cfg-botoes"><button data-agt-original="1">Ler</button></span></div>' : "");
  return cartaoCfg("Versões", metaCfg(plural(anteriores.length, "anterior", "anteriores")), corpo, "agt-versoes");
}

function ligarAgente() {
  const a = agt.aberto.ficha;
  const nav = $("centro").querySelector("[data-agt-voltar]");
  if (nav) nav.onclick = voltarParaAgentes;
  const acoes = $("acoes-tela");
  const t = acoes.querySelector("[data-agt-testar]");
  if (t) t.onclick = () => testarAgente(a.slug);
  const e = acoes.querySelector("[data-agt-editar]");
  if (e) e.onclick = () => editarAgente();
  const on = acoes.querySelector("[data-agt-ativar]");
  if (on) on.onclick = () => ativarAgente(a);
  const off = acoes.querySelector("[data-agt-desativar]");
  if (off) off.onclick = () => desativarAgente(a);
  const raiz = $("centro");
  raiz.querySelectorAll("[data-agt-versao]").forEach((b) => { b.onclick = () => lerVersao(a.slug, Number(b.dataset.agtVersao)); });
  const md = raiz.querySelector("[data-agt-ver-md]");
  if (md) md.onclick = () => mostrarMarkdown("Versão " + a.versao + " · atual", agt.aberto.markdown);
  const orig = raiz.querySelector("[data-agt-original]");
  if (orig) orig.onclick = () => mostrarMarkdown("Original importado", agt.aberto.original);
}

function mostrarMarkdown(titulo, texto) {
  return dialogo({
    titulo: titulo, contexto: "Agentes › " + ((agt.aberto && agt.aberto.ficha.nome) || ""), larga: true,
    html: '<pre class="agt-md-leitura" data-agt-leitura="1">' + esc(texto || "") + "</pre>", confirmar: "Fechar", semCancelar: true,
  });
}

async function lerVersao(slug, n) {
  const r = await fetch("/api/agentes/" + encodeURIComponent(slug) + "/versoes/" + n);
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  mostrarMarkdown("Versão " + n + " · anterior", d.markdown);
}

async function testarAgente(slug) {
  if (agt.rodando) return;
  agt.rodando = slug;
  delete agt.testes[slug];
  desenharAgentes();
  try {
    const r = await fetch("/api/agentes/" + encodeURIComponent(slug) + "/testar", { method: "POST" });
    if (!r.ok) { avisoCert("o teste não rodou: " + (await erroDe(r)), { tom: "erro" }); return; }
    const d = await r.json();
    agt.testes[slug] = d;
    avisoCert(d.passaram === d.total ? "os " + plural(d.total, "teste") + " passaram" : d.passaram + " de " + d.total + " testes passaram" +
      (d.precisa_revisao ? " — o agente precisa de revisão" : ""), { tom: d.passaram === d.total ? "ok" : "" });
  } catch (err) {
    avisoCert("o teste não rodou: " + err, { tom: "erro" });
  } finally {
    agt.rodando = "";
    // A medida mudou (A4): relê o agente, e a lista na volta.
    if (agt.vista === "agente" && agt.aberto && agt.aberto.ficha.slug === slug) await abrirAgente(slug);
    else desenharAgentes();
  }
}

async function ativarAgente(a) {
  let corpo = {};
  if (a.precisa_aprovar) {
    const d = agt.aberto;
    const r = await dialogo({
      titulo: "Ativar um agente importado", contexto: "Agentes › " + a.nome, larga: true,
      texto: "Um agente importado é tratado como dado até você ler o conteúdo inteiro. Ferramentas que ele pede: " +
        ((a.ferramentas || []).join(", ") || "nenhuma") + ".",
      html: '<pre class="agt-md-leitura">' + esc(d.original || d.markdown || "") + "</pre>",
      marcar: { rotulo: "Li o conteúdo inteiro e as ferramentas que ele pede", marcada: false },
      confirmar: "Ativar",
    });
    if (!r || !r.ok) return;
    if (!r.marcada) { avisoCert("marque que leu o conteúdo inteiro para ativar"); return; }
    corpo = { vi_o_conteudo: true };
  }
  const r = await fetch("/api/agentes/" + encodeURIComponent(a.slug) + "/ativar", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  avisoCert("“" + a.nome + "” ativo: a conversa já pode usá-lo", { tom: "ok" });
  abrirAgente(a.slug);
}

async function desativarAgente(a) {
  const r = await fetch("/api/agentes/" + encodeURIComponent(a.slug) + "/desativar", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  avisoCert("“" + a.nome + "” desativado: a conversa não o usa mais", { tom: "ok" });
  abrirAgente(a.slug);
}

function importarAgente() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".md,text/markdown,text/plain";
  input.onchange = async () => {
    const f = input.files && input.files[0];
    if (!f) return;
    const texto = await f.text();
    const r = await fetch("/api/agentes/importar", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ markdown: texto, nome_arquivo: f.name }),
    });
    if (!r.ok) { avisoCert("não consegui importar: " + (await erroDe(r)), { tom: "erro" }); return; }
    const d = await r.json();
    avisoCert("importado desativado: leia o conteúdo antes de ativar", { tom: "ok" });
    await carregarAgentes();
    abrirAgente(d.slug);
  };
  input.click();
}

/* ------------------------------------------------------------ criar e editar */

function camposVazios() {
  return { nome: "", descricao: "", exemplos: "", palavras: "", acervo: "acervo", pastas: "", formato: "texto",
    ferramentas: [], capacidades: ["perguntar"], modelo: "conversa", instrucoes: "## Como trabalhar\n", testes: [], versao: 1 };
}

/* Os campos do formulario a partir da ficha (ou do rascunho da conversa). */
function camposDaFicha(f) {
  const qu = f.quando_usar || {};
  const fontes = f.fontes || {};
  const acervo = fontes.acervo && typeof fontes.acervo === "object" ? "pastas" : (fontes.acervo || f.acervo || "acervo");
  const lista = (v) => (Array.isArray(v) ? v : String(v || "").split("\n")).filter(Boolean);
  return {
    nome: f.nome || "", descricao: f.descricao || "",
    exemplos: lista(qu.exemplos || f.exemplos).join("\n"), palavras: lista(qu.palavras || f.palavras).join(", "),
    acervo: acervo, pastas: lista(acervo === "pastas" ? (fontes.acervo.pastas || f.pastas) : f.pastas).join("\n"),
    biblioteca: fontes.biblioteca || [], leis: fontes.leis || [],
    formato: (f.saida || {}).formato || f.formato || "texto", saida_modelo: (f.saida || {}).modelo || "",
    ferramentas: (f.ferramentas || []).slice(), capacidades: (f.capacidades || ["perguntar"]).slice(),
    modelo: f.modelo || "conversa", instrucoes: f.instrucoes || "",
    testes: (f.testes || []).map((t) => ({ pergunta: t.pergunta || "", deve_conter: (t.deve_conter || []).join(", ") })),
    versao: f.versao || 1,
  };
}

function comecarEdicao(campos, opcoes) {
  const o = opcoes || {};
  agt.vista = "editar";
  agt.editando = o.slug || "";
  agt.form = campos;
  agt.markdown = o.markdown || "";
  agt.formMudou = !o.markdown;
  agt.modo = o.modo || "formulario";
  agt.daConversa = o.daConversa || null;
  agt.versaoBase = o.versao || 0;
  agt.validacao = null;
  desenharAgentes();
  validarEdicao();
}

function novoAgente() {
  if (agentesSoLeitura()) { avisoCert(FRASE_AGENTES_SO_NO_ESCRITORIO); return; }
  comecarEdicao(camposVazios());
}

function editarAgente() {
  const d = agt.aberto;
  if (!d || agentesSoLeitura()) return;
  // Com problema, o formulario nao tem de onde ler: abre no markdown.
  comecarEdicao(d.ficha.problema ? camposVazios() : camposDaFicha(d.ficha),
    { slug: d.ficha.slug, markdown: d.markdown, versao: d.ficha.versao, modo: d.ficha.problema ? "markdown" : "formulario" });
}

/* "Criar agente a partir desta conversa": o rascunho vem por regra do
   servidor (src/agentes_tela.py) e o formulario abre preenchido. Nada foi
   gravado - quem grava e o "Criar agente". */
async function agenteDaConversa(id) {
  if (agentesSoLeitura()) { avisoCert(FRASE_AGENTES_SO_NO_ESCRITORIO); return; }
  const r = await fetch("/api/agentes/da-conversa/" + encodeURIComponent(id));
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); agt.vista = "lista"; desenharAgentes(); return; }
  const d = await r.json();
  comecarEdicao(camposDaFicha(d.campos), { daConversa: { id: d.conversa.id, titulo: d.conversa.titulo, perguntas: d.perguntas } });
}

async function escolherConversaParaAgente() {
  if (!estado.recentes || !estado.recentes.length) await carregarTrabalhos();
  const conversas = (estado.recentes || []).slice(0, 12);
  if (!conversas.length) { avisoCert("nenhuma conversa ainda"); return; }
  const r = await dialogo({
    titulo: "Criar agente a partir de uma conversa", contexto: "Agentes",
    texto: "As perguntas da conversa viram os exemplos, as palavras que mais se repetem viram as palavras e o título vira o nome. Você revisa no formulário antes de salvar.",
    html: '<div class="dialogo-campo"><label for="agt-conversa">Conversa</label><div class="dialogo-caixa"><select id="agt-conversa">' +
      conversas.map((c) => '<option value="' + esc(c.id) + '">' + esc(c.titulo) + "</option>").join("") + "</select></div></div>",
    confirmar: "Sugerir",
  });
  if (!r || !r.ok) return;
  const sel = document.getElementById("agt-conversa");
  agenteDaConversa(sel ? sel.value : conversas[0].id);
}

function desenharEdicao() {
  const f = agt.form || camposVazios();
  const criando = !agt.editando;
  $("conversa-titulo").textContent = "Agentes";
  $("nav-tela").innerHTML = "";
  $("acoes-tela").innerHTML = '<button data-agt-cancelar="1">Cancelar</button>' +
    '<button class="primario com-icone" data-agt-salvar="1" disabled>' + ic("check", 16) +
    (criando ? "Criar agente" : "Salvar versão " + (agt.versaoBase + 1)) + "</button>";
  const titulo = criando ? (agt.daConversa ? "Novo agente a partir da conversa" : "Novo agente") : "Editar “" + esc(f.nome || agt.editando) + "”";
  const avisos = [];
  if (agt.daConversa) {
    avisos.push('<div class="agt-aviso atencao" data-agt-sugerido="1">' + ic("lightbulb", 18) + "<span>Sugerido pela conversa “" +
      esc(agt.daConversa.titulo) + "”, por regra: " + plural(agt.daConversa.perguntas, "pergunta") + " viraram os exemplos, as palavras que mais se repetem viraram as palavras e o título virou o nome. <b>Nada foi salvo</b> — revise e clique em Criar agente.</span></div>");
  }
  if (!criando) {
    avisos.push('<div class="agt-aviso">' + ic("history", 18) + "<span>Salvar guarda a versão " + agt.versaoBase + " como anterior (dá para ler em Versões) e grava a " +
      (agt.versaoBase + 1) + ". O formulário reescreve o cabeçalho: comentários escritos no markdown só ficam se você salvar pelo Markdown.</span></div>");
  }
  const topo = migalhaDeAgentes("data-agt-cancelar", criando ? "Agentes" : (f.nome || agt.editando)) +
    '<header class="sv-resumo-topo"><div class="sv-resumo-cabeca"><h2>' + titulo + "</h2>" +
    '<span class="visoes agt-modos"><button data-agt-modo="formulario" class="' + (agt.modo === "formulario" ? "ativa" : "") + '">Formulário</button>' +
    '<button data-agt-modo="markdown" class="' + (agt.modo === "markdown" ? "ativa" : "") + '">Markdown</button></span></div></header>';
  const corpo = agt.modo === "markdown" ? blocoMarkdown() : blocoFormulario(f);
  cascaAgentes(topo + avisos.join("") + corpo + '<div id="agt-validacao" class="agt-validacao">' + htmlDaValidacao() + "</div>");
  ligarEdicao();
}

function blocoMarkdown() {
  return cartaoCfg("AGENTE.md", metaCfg("o cabeçalho entre as linhas ---, as instruções embaixo"),
    '<textarea class="agt-md" id="agt-md" spellcheck="false">' + esc(agt.markdown) + "</textarea>" +
    '<p class="cfg-explica">Os campos e o que cada um aceita estão no formulário. Nome desconhecido (uma ferramenta que não existe, um campo com erro de digitação) é erro, e o agente não é salvo.</p>');
}

function blocoFormulario(f) {
  const cat = agt.catalogos || {};
  const opcoes = (mapa, atual) => Object.keys(mapa).map((k) => '<option value="' + k + '"' + (k === atual ? " selected" : "") + ">" + esc(mapa[k]) + "</option>").join("");
  const ferramentas = (cat.ferramentas || []).map((x) => {
    const marcada = (f.ferramentas || []).includes(x.id);
    return '<label class="agt-ferramenta"><input type="checkbox" data-agt-ferr="' + esc(x.id) + '"' + (marcada ? " checked" : "") + ">" +
      '<span class="duas-linhas"><b>' + esc(x.id) + "</b><small>" + esc(x.descricao || "") + (x.disponivel === false ? " · ainda não faz o trabalho de verdade" : "") + "</small></span></label>";
  }).join("");
  const testes = (f.testes || []).map((t, i) =>
    '<div class="agt-teste-form" data-agt-teste-form="' + i + '"><div class="ag-duas">' +
      '<div class="ag-campo"><label>Pergunta</label><input type="text" data-agt-teste-pergunta="' + i + '" value="' + esc(t.pergunta) + '" placeholder="qual a multa do contrato X?"></div>' +
      '<div class="ag-campo"><label>A resposta certa contém</label><input type="text" data-agt-teste-deve="' + i + '" value="' + esc(t.deve_conter) + '" placeholder="2%, multa (separadas por vírgula)"></div>' +
    '</div><button class="fantasma" data-agt-teste-tirar="' + i + '">Tirar este teste</button></div>').join("");
  return '<div class="agt-form">' +
    cartaoCfg("O agente", "",
      '<div class="cfg-campos">' +
        '<div class="ag-campo"><label for="agt-nome">Nome</label><input type="text" id="agt-nome" data-agt-campo="nome" maxlength="80" value="' + esc(f.nome) + '" placeholder="Revisor de contratos"></div>' +
        '<div class="ag-campo"><label for="agt-descricao">Para que serve</label><textarea id="agt-descricao" data-agt-campo="descricao" rows="2" placeholder="Compara um contrato com o padrão da casa e aponta o que falta.">' + esc(f.descricao) + "</textarea></div>" +
        '<div class="ag-duas"><div class="ag-campo"><label for="agt-exemplos">Exemplos de pedido</label><textarea id="agt-exemplos" data-agt-campo="exemplos" rows="4" placeholder="um por linha: revise este contrato">' + esc(f.exemplos) + "</textarea></div>" +
        '<div class="ag-campo"><label for="agt-palavras">Palavras</label><input type="text" id="agt-palavras" data-agt-campo="palavras" value="' + esc(f.palavras) + '" placeholder="revisar, cláusula (separadas por vírgula)">' +
        '<span class="dialogo-dica">Uma palavra destas no pedido já sugere o agente. Os exemplos pedem pedidos parecidos.</span></div></div>' +
      "</div>") +
    cartaoCfg("Onde procurar e como responder", "",
      '<div class="cfg-campos"><div class="ag-duas">' +
        '<div class="ag-campo"><label for="agt-acervo">Onde procurar</label><select id="agt-acervo" data-agt-campo="acervo">' + opcoes(ONDE_PROCURA, f.acervo) + "</select></div>" +
        '<div class="ag-campo"><label for="agt-formato">Formato da resposta</label><select id="agt-formato" data-agt-campo="formato">' + opcoes(FORMATO_SAIDA, f.formato) + "</select></div></div>" +
        '<div class="ag-campo" id="agt-pastas-campo"' + (f.acervo === "pastas" ? "" : " hidden") + '><label for="agt-pastas">Pastas</label><textarea id="agt-pastas" data-agt-campo="pastas" rows="2" placeholder="uma por linha: Cooperativa Vale Verde">' + esc(f.pastas) + "</textarea></div>" +
        '<p class="cfg-explica">Onde procurar só restringe: o agente nunca lê o que quem pergunta não leria.</p>' +
      "</div>") +
    cartaoCfg("Ferramentas", metaCfg("só as do catálogo"),
      '<div class="agt-ferramentas">' + (ferramentas || '<p class="cfg-texto">O catálogo de ferramentas não carregou.</p>') + "</div>" +
      '<p class="cfg-explica">Cada ferramenta continua pedindo a sua confirmação antes de agir, e o pedido vai também para Aprovações. Sem nenhuma marcada, o agente só responde.</p>') +
    cartaoCfg("Instruções", metaCfg("o jeito do escritório de fazer este trabalho"),
      '<textarea class="agt-instrucoes" id="agt-instrucoes" data-agt-campo="instrucoes" rows="12">' + esc(f.instrucoes) + "</textarea>" +
      '<p class="cfg-explica">Vão ao modelo cercadas e rotuladas, abaixo das regras do produto: citar a fonte, não inventar, confirmar antes de agir e respeitar as permissões valem sempre.</p>') +
    cartaoCfg("Testes", metaCfg(plural((f.testes || []).length, "teste")),
      (testes || '<p class="cfg-texto">Sem testes, o Testar não tem o que rodar e a medida não sabe se o agente acerta.</p>') +
      '<div class="cfg-botoes"><button class="com-icone" data-agt-teste-mais="1">' + ic("add", 16) + "Acrescentar teste</button></div>") +
    "</div>";
}

function htmlDaValidacao() {
  const v = agt.validacao;
  if (!v) return '<p class="nota">conferindo…</p>';
  if (!v.valido) {
    return '<div class="agt-aviso erro" data-agt-erro="1">' + ic("error", 18) + "<span><b>Ainda não dá para salvar:</b> " +
      esc(v.erro).split("; ").join("<br>") + "</span></div>";
  }
  const frase = (t) => esc(String(t).charAt(0).toUpperCase() + String(t).slice(1)) + ".";
  return '<div class="agt-aviso ok" data-agt-valido="1">' + ic("check_circle", 18) + "<span>Pronto para salvar." +
    ((v.avisos || []).length ? " " + (v.avisos || []).map(frase).join(" ") : "") + "</span></div>";
}

function lerFormulario() {
  const raiz = $("centro");
  const f = agt.form;
  raiz.querySelectorAll("[data-agt-campo]").forEach((el) => { f[el.dataset.agtCampo] = el.value; });
  f.ferramentas = [...raiz.querySelectorAll("[data-agt-ferr]")].filter((c) => c.checked).map((c) => c.dataset.agtFerr);
  f.testes = (f.testes || []).map((t, i) => {
    const p = raiz.querySelector('[data-agt-teste-pergunta="' + i + '"]');
    const d = raiz.querySelector('[data-agt-teste-deve="' + i + '"]');
    return { pergunta: p ? p.value : t.pergunta, deve_conter: d ? d.value : t.deve_conter };
  });
}

function ligarEdicao() {
  document.querySelectorAll("[data-agt-cancelar]").forEach((b) => { b.onclick = cancelarEdicao; });
  const salvar = $("acoes-tela").querySelector("[data-agt-salvar]");
  if (salvar) {
    salvar.onclick = salvarEdicao;
    salvar.disabled = !(agt.validacao && agt.validacao.valido);
  }
  const raiz = $("centro");
  raiz.querySelectorAll("[data-agt-modo]").forEach((b) => { b.onclick = () => trocarModo(b.dataset.agtModo); });
  const md = $("agt-md");
  if (md) md.oninput = () => { agt.markdown = md.value; validarDepois(); };
  raiz.querySelectorAll("[data-agt-campo], [data-agt-ferr], [data-agt-teste-pergunta], [data-agt-teste-deve]").forEach((el) => {
    const mudou = () => {
      lerFormulario();
      agt.formMudou = true;
      if (el.dataset.agtCampo === "acervo") $("agt-pastas-campo").hidden = el.value !== "pastas";
      validarDepois();
    };
    el.addEventListener("input", mudou);
    el.addEventListener("change", mudou);
  });
  const mais = raiz.querySelector("[data-agt-teste-mais]");
  if (mais) mais.onclick = () => { lerFormulario(); agt.form.testes.push({ pergunta: "", deve_conter: "" }); agt.formMudou = true; desenharEdicao(); validarEdicao(); };
  raiz.querySelectorAll("[data-agt-teste-tirar]").forEach((b) => {
    b.onclick = () => { lerFormulario(); agt.form.testes.splice(Number(b.dataset.agtTesteTirar), 1); agt.formMudou = true; desenharEdicao(); validarEdicao(); };
  });
  raiz.querySelectorAll("select").forEach((s) => { if (typeof melhorarSelect === "function") melhorarSelect(s); });
}

function validarDepois() {
  clearTimeout(agt.validarTimer);
  agt.validarTimer = setTimeout(validarEdicao, 350);
}

/* O markdown que vai ser gravado: o escrito a mao, ou o que o formulario
   monta no servidor. Com o formulario sem mudanca, vale o arquivo como esta
   (com os comentarios dele). */
async function markdownDaEdicao() {
  if (agt.modo === "markdown" || (!agt.formMudou && agt.markdown)) return { markdown: agt.markdown };
  const r = await fetch("/api/agentes/formulario", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ campos: agt.form }),
  });
  if (!r.ok) return { erro: await erroDe(r) };
  return r.json();
}

async function validarEdicao() {
  const vez = (agt.vezValidacao || 0) + 1;
  agt.vezValidacao = vez;
  let v;
  try {
    const m = await markdownDaEdicao();
    if (m.erro) v = { valido: false, erro: m.erro };
    else if ("valido" in m) v = m;
    else {
      const r = await fetch("/api/agentes/validar", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ markdown: m.markdown }),
      });
      v = r.ok ? await r.json() : { valido: false, erro: await erroDe(r) };
      v.markdown = m.markdown;
    }
  } catch (err) {
    v = { valido: false, erro: "não consegui conferir: " + err };
  }
  if (vez !== agt.vezValidacao || agt.vista !== "editar") return;
  agt.validacao = v;
  const caixa = $("agt-validacao");
  if (caixa) caixa.innerHTML = htmlDaValidacao();
  const salvar = $("acoes-tela").querySelector("[data-agt-salvar]");
  if (salvar) salvar.disabled = !v.valido;
}

async function trocarModo(modo) {
  if (modo === agt.modo) return;
  if (modo === "markdown") {
    lerFormulario();
    const m = await markdownDaEdicao();
    if (m.markdown) agt.markdown = m.markdown;
    agt.modo = "markdown";
  } else {
    // Do markdown para o formulario: so com o markdown valido - o formulario
    // se preenche da ficha que a validacao devolve.
    const r = await fetch("/api/agentes/validar", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ markdown: agt.markdown }),
    });
    const v = r.ok ? await r.json() : { valido: false, erro: await erroDe(r) };
    if (!v.valido) {
      agt.validacao = v;
      const caixa = $("agt-validacao");
      if (caixa) caixa.innerHTML = htmlDaValidacao();
      avisoCert("corrija o markdown para voltar ao formulário");
      return;
    }
    agt.form = camposDaFicha(v.ficha);
    agt.formMudou = false;
    agt.modo = "formulario";
  }
  desenharEdicao();
  validarEdicao();
}

function cancelarEdicao() {
  const slug = agt.editando;
  agt.form = null;
  agt.daConversa = null;
  if (slug) abrirAgente(slug);
  else voltarParaAgentes();
}

async function salvarEdicao() {
  if (agt.modo === "formulario") lerFormulario();
  const m = await markdownDaEdicao();
  if (m.erro || !m.markdown) { avisoCert(m.erro || "nada para salvar", { tom: "erro" }); return; }
  const criando = !agt.editando;
  const r = await fetch(criando ? "/api/agentes" : "/api/agentes/" + encodeURIComponent(agt.editando), {
    method: criando ? "POST" : "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ markdown: m.markdown }),
  });
  if (!r.ok) {
    agt.validacao = { valido: false, erro: await erroDe(r) };
    const caixa = $("agt-validacao");
    if (caixa) caixa.innerHTML = htmlDaValidacao();
    return;
  }
  const a = await r.json();
  avisoCert(criando ? "agente criado, desativado: teste e ative quando quiser" : "versão " + a.versao + " salva; a " + agt.versaoBase + " ficou em Versões", { tom: "ok" });
  agt.form = null;
  agt.daConversa = null;
  await carregarAgentes();
  abrirAgente(a.slug);
}
