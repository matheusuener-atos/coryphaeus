/* ------------------------------------------- area do cliente (escritorio) */
/*
   O lado do escritorio da Area do cliente (docs/PLANO-AREA-CLIENTE.md,
   src/area_cliente.py), dentro da pasta do servico (js/10-servicos.js):

   - a aba Cliente: quem ve a pasta (compartilhar, copiar o link, reenviar,
     parar), o resumo para o cliente (escrito a mao ou rascunhado pela IA,
     so aparece depois de publicado), a conversa e a atividade do cliente;
   - o olhinho nas etapas e nos compromissos, a etapa "do cliente" (a
     pendencia dele) e o "compartilhar" dos documentos, na propria pasta;
   - "Ver como o cliente": a mesma pagina do cliente (js/cliente.js),
     desenhada a partir da mesma resposta da API, numa moldura de celular.

   As tres regras do que o cliente ve estao escritas na propria aba: o
   advogado nao precisa lembrar delas.
*/

const acp = { dados: null, carregando: false, enviando: false };

function clienteDaPasta() {
  return (sv.aberto && sv.aberto.cliente) || null;
}

function pastaCompartilhada() {
  const c = clienteDaPasta();
  return Boolean(c && c.compartilhado);
}

/* ------------------------------------------------ na propria pasta */

/* O olhinho de uma etapa: aparece so com a pasta compartilhada. */
function olhoDaEtapa(e, i) {
  if (!pastaCompartilhada()) return "";
  // A etapa do cliente ele sempre ve: o botao "cliente" ao lado ja diz isso.
  if (e.cliente) return "";
  const oculta = Boolean(e.oculta_cliente);
  return '<button type="button" class="acp-olho' + (oculta ? " oculto" : "") + '" data-acp-etapa-olho="' + i + '" title="' +
    (oculta ? "O cliente não vê esta etapa — clique para mostrar" : "O cliente vê esta etapa — clique para esconder") + '">' +
    ic(oculta ? "visibility_off" : "visibility", 15) + "</button>";
}

/* O olhinho e o "pedir confirmação" de um compromisso da pasta. */
function olhoDoPrazo(p) {
  const c = clienteDaPasta();
  if (!c || !c.compartilhado || p.origem !== "compromisso" || !(c.compromissos || []).includes(p.id)) return "";
  const oculto = (c.ocultos || []).includes(p.id);
  const conf = (c.confirmacoes || {})[String(p.id)];
  let selo = "";
  if (conf && conf.resposta === "confirmado") selo = '<span class="acp-conf ok" title="O cliente confirmou">' + ic("check_circle", 15) + "</span>";
  else if (conf && conf.resposta === "remarcar") selo = '<span class="acp-conf remarcar" title="' + esc("Pediu para remarcar: " + conf.sugestao) + '">' + ic("schedule", 15) + "</span>";
  else if (conf) selo = '<span class="acp-conf" title="Esperando o cliente confirmar">' + ic("schedule", 15) + "</span>";
  return selo + '<button type="button" class="acp-olho' + (oculto ? " oculto" : "") + '" data-acp-prazo-olho="' + p.id + '" title="' +
    (oculto ? "O cliente não vê este compromisso" : "O cliente vê este compromisso") + ' — clique para mais">' +
    ic(oculto ? "visibility_off" : "visibility", 15) + "</button>";
}

/* O "compartilhar" de um documento, na lista de Arquivos. */
function seloDoDocumento(sha1) {
  const c = clienteDaPasta();
  if (!c) return "";
  const sim = (c.documentos || []).includes(sha1);
  if (!sim && !c.compartilhado) return "";
  return '<button type="button" class="acp-doc' + (sim ? " sim" : "") + '" data-acp-doc="' + esc(sha1) + '" title="' +
    (sim ? "O cliente vê este documento — clique para parar" : "Compartilhar este documento com o cliente") + '">' +
    ic(sim ? "visibility" : "share", 15) + '<span class="corta">' + (sim ? "o cliente vê" : "compartilhar") + "</span></button>";
}

/* O selo de mensagens novas do cliente, no cartão da pasta. */
function seloDoClienteNoCartao(s) {
  const n = Number((sv.clienteNaoLidas || {})[String(s.id)] || 0);
  return n ? '<span class="acp-selo-msg" title="Mensagens novas do cliente">' + ic("forum", 15) + plural(n, "mensagem", "mensagens") + "</span>" : "";
}

async function marcarEtapaParaCliente(i, dados) {
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/cliente/etapas/" + i, { method: "POST", headers: SV_JSON, body: JSON.stringify(dados) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  recarregarServico();
}

function menuDoOlhoDoPrazo(botao, id) {
  const c = clienteDaPasta() || {};
  const oculto = (c.ocultos || []).includes(id);
  const conf = (c.confirmacoes || {})[String(id)];
  const marcar = async (dados, aviso) => {
    const r = await fetch("/api/servicos/" + sv.aberto.id + "/cliente/compromissos/" + id, { method: "POST", headers: SV_JSON, body: JSON.stringify(dados) });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    if (aviso) avisoCert(aviso, { tom: "ok" });
    recarregarServico();
  };
  const itens = [];
  if (conf && conf.resposta === "remarcar") itens.push({ rotulo: "Pediu para remarcar: " + conf.sugestao, acao: () => {} }, "-");
  if (conf && conf.resposta === "confirmado") itens.push({ rotulo: "O cliente confirmou", acao: () => {} }, "-");
  if (!oculto) {
    itens.push(conf
      ? { rotulo: conf.resposta ? "Pedir confirmação de novo" : "Esperando a confirmação…", acao: () => marcar({ confirmar: true }, "o cliente vai ver o pedido em “Para você”") }
      : { rotulo: "Pedir ao cliente que confirme", acao: () => marcar({ confirmar: true }, "o cliente vai ver o pedido em “Para você”") });
    if (conf) itens.push({ rotulo: "Não pedir mais confirmação", acao: () => marcar({ confirmar: false }) });
    itens.push("-", { rotulo: "Esconder do cliente", acao: () => marcar({ oculto: true }) });
  } else {
    itens.push({ rotulo: "Mostrar ao cliente", acao: () => marcar({ oculto: false }) });
  }
  menuNaLinha(botao, itens);
}

async function compartilharDocumentoComCliente(sha1) {
  const c = clienteDaPasta() || {};
  const sim = !(c.documentos || []).includes(sha1);
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/cliente/documentos/" + sha1, { method: "POST", headers: SV_JSON, body: JSON.stringify({ compartilhado: sim }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  avisoCert(sim ? "o cliente passa a ver este documento, com marca d'água" : "o cliente não vê mais este documento", { tom: "ok" });
  recarregarServico();
}

function ligarClienteNaPasta(raiz) {
  const clique = (sel, fn) => raiz.querySelectorAll(sel).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });
  clique("[data-acp-etapa-olho]", (b) => {
    const i = Number(b.dataset.acpEtapaOlho);
    marcarEtapaParaCliente(i, { oculta: !sv.aberto.etapas[i].oculta_cliente });
  });
  clique("[data-acp-prazo-olho]", (b) => menuDoOlhoDoPrazo(b, Number(b.dataset.acpPrazoOlho)));
  clique("[data-acp-doc]", (b) => compartilharDocumentoComCliente(b.dataset.acpDoc));
  clique("[data-acp-ver]", () => verComoOCliente());
  clique("[data-acp-compartilhar]", () => dialogoCompartilhar());
  if (sv.aba === "cliente") ligarAbaDoCliente(raiz);
}

/* ------------------------------------------------- "Ver como o cliente" */

function verComoOCliente() {
  const s = sv.aberto;
  if (!s || !window.AreaCliente) return;
  const pessoas = (acp.dados && acp.dados.pessoas) || [];
  const veu = document.createElement("div");
  veu.className = "acp-previa-veu";
  veu.innerHTML = '<div class="acp-previa" role="dialog" aria-modal="true" aria-label="Ver como o cliente">' +
    '<div class="acp-previa-cabeca"><b>Ver como o cliente</b><small>' + esc(s.nome) + "</small>" +
    '<button type="button" class="botao-icone" data-acp-fechar="1" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>" +
    '<div class="acp-celular"><div class="acp-tela" id="acp-tela"></div></div></div>';
  document.body.appendChild(veu);
  const fechar = () => { document.removeEventListener("keydown", teclas, true); veu.remove(); };
  const teclas = (e) => {
    if (e.key === "Escape" && !document.querySelector(".acp-tela .pcl-visor")) { e.preventDefault(); fechar(); }
  };
  document.addEventListener("keydown", teclas, true);
  veu.onclick = (e) => { if (e.target === veu) fechar(); };
  veu.querySelector("[data-acp-fechar]").onclick = fechar;
  window.AreaCliente.previa(document.getElementById("acp-tela"), s.id, pessoas.length ? pessoas[0].nome : (s.cliente_nome || "o cliente"));
}

/* ------------------------------------------------------- a aba Cliente */

function secaoDoClienteNaPasta() {
  return '<section class="sv-secao acp-aba" id="acp-aba"><p class="nota">abrindo…</p></section>';
}

async function carregarAbaDoCliente() {
  const s = sv.aberto;
  const lugar = document.getElementById("acp-aba");
  if (!s || !lugar) return;
  try {
    const r = await fetch("/api/servicos/" + s.id + "/cliente?ler=1");
    if (!r.ok) throw new Error(await erroDe(r));
    const [d, at] = await Promise.all([r.json(), fetch("/api/servicos/" + s.id + "/cliente/atividade").then((x) => (x.ok ? x.json() : { atividade: [] }))]);
    if (!sv.aberto || sv.aberto.id !== s.id || sv.aba !== "cliente") return;
    acp.dados = Object.assign(d, { atividade: at.atividade || [] });
    if (sv.aberto.cliente) sv.aberto.cliente.nao_lidas = 0;
    if (sv.clienteNaoLidas) delete sv.clienteNaoLidas[String(s.id)];
    desenharAbaDoCliente();
  } catch (err) {
    lugar.innerHTML = '<p class="nota">não consegui abrir: ' + esc(String(err.message || err)) + "</p>";
  }
}

function desenharAbaDoCliente() {
  const lugar = document.getElementById("acp-aba");
  const d = acp.dados;
  if (!lugar || !d) return;
  const rascunho = (lugar.querySelector("[data-acp-resposta]") || {}).value || "";
  lugar.outerHTML = '<div class="acp-aba" id="acp-aba">' + htmlDaAbaDoCliente(d) + "</div>";
  const conversa = document.getElementById("acp-conversa");
  if (conversa) conversa.scrollTop = conversa.scrollHeight;
  const caixa = document.querySelector("[data-acp-resposta]");
  if (caixa && rascunho) caixa.value = rascunho;
  ligarAbaDoCliente(document.getElementById("acp-aba"));
}

function htmlDaAbaDoCliente(d) {
  const s = sv.aberto;
  const titulo = (icone, texto, extra) => '<div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + ic(icone, 16) + esc(texto) + "</span>" + (extra || "") + "</div>";
  if (!d.disponivel) {
    return '<section class="sv-secao">' + titulo("person", "Área do cliente") +
      '<p class="sv-dica">' + esc(d.motivo_plano || "A área do cliente não faz parte do seu plano.") + "</p>" + regrasDoCliente() + "</section>";
  }
  const pessoas = d.pessoas.map((p) =>
    '<div class="acp-pessoa"><span class="cad-avatar">' + esc(iniciaisDoRemetente(p.nome)) + "</span>" +
    '<span class="duas-linhas"><b>' + esc(p.nome) + "</b><small>" + esc(p.email + (p.ultimo_acesso ? " · entrou " + quandoCurtoSv(p.ultimo_acesso) : " · ainda não entrou")) + "</small></span>" +
    '<button type="button" class="mais-linha" data-acp-pessoa="' + p.id + '" title="Mais">' + ic("more_horiz", 18) + "</button></div>").join("");
  const semEndereco = !d.endereco
    ? '<p class="sv-dica acp-alerta">' + ic("info", 15) + "O cliente entra pelo endereço do escritório na internet. Ligue o acesso externo antes, em Configurações › Acesso externo.</p>"
    : "";
  const quem = '<section class="sv-secao">' + titulo("group", "Quem vê esta pasta",
    '<button type="button" class="sv-ligacao" data-acp-compartilhar="1"' + (d.endereco ? "" : " disabled") + ">" + ic("person_add", 15) + "Compartilhar com o cliente</button>") +
    semEndereco + (pessoas ? '<div class="acp-pessoas">' + pessoas + "</div>"
      : '<p class="sv-dica">Ninguém de fora vê esta pasta. Compartilhar manda um e-mail com o link; o cliente entra com um código que chega no e-mail dele.</p>') +
    '<div class="cfg-botoes"><button type="button" class="com-icone" data-acp-ver="1">' + ic("visibility", 16) + "Ver como o cliente</button></div></section>";

  const r = d.resumo || {};
  const resumo = '<section class="sv-secao">' + titulo("article", "Resumo para o cliente",
    r.publicado_em ? '<span class="sv-secao-meta">publicado ' + esc(quandoCurtoSv(r.publicado_em)) + "</span>" : '<span class="sv-secao-meta">não publicado</span>') +
    (r.rascunho ? '<div class="acp-rascunho"><span class="sv-kicker">Rascunho da IA · ' + esc(quandoCurtoSv(r.rascunho_em)) + "</span><p>" + esc(r.rascunho) + "</p>" +
      '<button type="button" class="sv-ligacao" data-acp-usar-rascunho="1">' + ic("edit", 15) + "levar para o texto abaixo</button></div>" : "") +
    '<textarea class="acp-resumo" rows="5" maxlength="3000" data-acp-resumo="1" placeholder="Escreva, em palavras simples, onde o serviço está e o que vem a seguir. O cliente só vê depois de publicar.">' +
    esc(r.texto || "") + "</textarea>" +
    '<div class="cfg-botoes"><button type="button" class="primario com-icone" data-acp-publicar="1">' + ic("send", 16) + "Publicar para o cliente</button>" +
    '<button type="button" class="com-icone" data-acp-sugerir="1"' + (acp.carregando ? " disabled" : "") + ">" + ic("auto_awesome", 16) +
    (acp.carregando ? "escrevendo…" : "Pedir um rascunho à IA") + "</button>" +
    (r.texto ? '<button type="button" class="com-icone" data-acp-tirar-resumo="1">Tirar o resumo</button>' : "") + "</div>" +
    '<p class="sv-dica">A IA lê só o que o cliente vê — nunca as anotações, as horas ou o que está escondido — e o rascunho fica aqui até você publicar.</p></section>';

  const msgs = (d.mensagens || []).map((m) => {
    const minha = m.de === "escritorio";
    const extra = (m.etapa ? '<span class="acp-cita">' + ic("subdirectory_arrow_right", 14) + esc(m.etapa) + "</span>" : "") +
      (m.anexo ? '<span class="acp-cita">' + ic("attach_file", 14) + esc(m.anexo) + " · em Recebidos do cliente</span>" : "");
    return '<div class="acp-msg' + (minha ? " nossa" : "") + '"><p>' + extra + esc(m.texto) + "</p><small>" + esc(m.autor + " · " + quandoCurtoSv(m.quando)) + "</small></div>";
  }).join("");
  const conversa = '<section class="sv-secao">' + titulo("forum", "Conversa com o cliente") +
    '<div class="acp-conversa" id="acp-conversa">' + (msgs || '<p class="sv-dica">Nada ainda. O que o cliente escrever, mandar ou responder sobre um horário aparece aqui — e no aviso do Windows.</p>') + "</div>" +
    '<form class="acp-responder" data-acp-responder="1"><textarea rows="2" maxlength="4000" data-acp-resposta="1" placeholder="Responder ao cliente…  (Ctrl+Enter manda)"></textarea>' +
    '<button class="primario com-icone" type="submit"' + (d.pessoas.length ? "" : " disabled") + ">" + ic("send", 16) + "Responder</button></form>" +
    '<p class="sv-dica">' + (d.pessoas.length ? "Quem vê a pasta recebe um e-mail avisando que há resposta — o texto fica só aqui." : "Compartilhe a pasta para conversar com o cliente.") + "</p></section>";

  const linhas = (d.atividade || []).slice(0, 120).map((a) =>
    '<div class="acp-ativ"><span class="sv-data">' + esc(quandoCurtoSv(a.quando)) + "</span>" +
    '<span class="duas-linhas"><b>' + esc(a.pessoa + " " + a.acao_rotulo) + "</b>" + (a.alvo ? "<small>" + esc(a.alvo) + "</small>" : "") + "</span></div>").join("");
  const atividade = '<section class="sv-secao">' + titulo("history", "Atividade do cliente", '<span class="sv-secao-meta">' + plural((d.atividade || []).length, "registro") + "</span>") +
    (linhas ? '<div class="acp-atividade">' + linhas + "</div>" : '<p class="sv-dica">O cliente ainda não entrou.</p>') +
    '<p class="sv-dica">Só quem está na equipe desta pasta vê esta lista. Fica também em Configurações › Acesso externo › Quem acessou. Print de tela não aparece aqui: o navegador do cliente não avisa — cada página que ele abre leva o nome dele e a hora.</p></section>';

  return quem + regrasDoCliente() + resumo + conversa + atividade;
}

function regrasDoCliente() {
  return '<section class="sv-secao acp-regras"><div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + ic("shield_person", 16) + "O que o cliente vê</span></div>" +
    '<ol><li><b>Nunca:</b> anotações, horas, financeiro, a conversa com o assistente, a trilha e a equipe (só o nome de quem cuida).</li>' +
    "<li><b>Sozinho, com a pasta compartilhada:</b> o status, as etapas e os compromissos da pasta. O olhinho ao lado de cada um esconde do cliente.</li>" +
    "<li><b>Só se você compartilhar:</b> cada documento, na aba Arquivos.</li></ol>" +
    '<p class="sv-dica">Etapa com responsável <b>o cliente</b> vira pendência dele (“enviar o RG”): ele manda o arquivo ou marca como feito. Num compromisso, o olhinho pede que ele confirme o horário.</p></section>';
}

function ligarAbaDoCliente(raiz) {
  if (!raiz) return;
  const d = acp.dados;
  const clique = (sel, fn) => raiz.querySelectorAll(sel).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });
  clique("[data-acp-ver]", () => verComoOCliente());
  clique("[data-acp-compartilhar]", () => dialogoCompartilhar());
  clique("[data-acp-pessoa]", (b) => menuDaPessoaCliente(b, Number(b.dataset.acpPessoa)));
  clique("[data-acp-publicar]", () => publicarResumoDoCliente(raiz.querySelector("[data-acp-resumo]").value));
  clique("[data-acp-tirar-resumo]", () => publicarResumoDoCliente(""));
  clique("[data-acp-sugerir]", () => sugerirResumoDoCliente());
  clique("[data-acp-usar-rascunho]", () => {
    const campo = raiz.querySelector("[data-acp-resumo]");
    campo.value = (d && d.resumo && d.resumo.rascunho) || campo.value;
    campo.focus();
  });
  const form = raiz.querySelector("[data-acp-responder]");
  if (form) {
    const caixa = form.querySelector("textarea");
    caixa.onkeydown = (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); form.requestSubmit(); } };
    form.onsubmit = (e) => { e.preventDefault(); responderAoCliente(caixa.value); };
  }
}

function menuDaPessoaCliente(botao, id) {
  const p = ((acp.dados && acp.dados.pessoas) || []).find((x) => x.id === id);
  if (!p) return;
  menuNaLinha(botao, [
    { rotulo: "Copiar o link", icone: "content_copy", acao: async () => {
      try { await navigator.clipboard.writeText(p.link); avisoCert("link copiado — ele só abre com o código que vai ao e-mail de " + p.nome.split(" ")[0], { tom: "ok" }); }
      catch (err) { avisoCert(p.link); }
    } },
    { rotulo: "Mandar o convite de novo", icone: "mail", acao: async () => {
      const r = await fetch("/api/servicos/" + sv.aberto.id + "/cliente/reenviar", { method: "POST", headers: SV_JSON, body: JSON.stringify({ pessoa_id: id }) });
      if (!r.ok) { avisoCert(await erroDe(r)); return; }
      const d = await r.json();
      avisoCert(d.email_enviado ? "convite mandado para " + p.email : "não consegui mandar o e-mail: " + d.erro_email + " — copie o link e mande por outro caminho", { tom: d.email_enviado ? "ok" : "erro" });
    } },
    "-",
    { rotulo: "Parar de compartilhar", icone: "visibility_off", perigo: true, acao: async () => {
      if (!(await confirmar({ titulo: "Parar de compartilhar?", contexto: "Serviços › " + sv.aberto.nome,
        texto: p.nome + " deixa de ver esta pasta na hora. O que ele já baixou fica com ele. Dá para compartilhar de novo depois.", confirmar: "Parar", perigo: true }))) return;
      const r = await fetch("/api/servicos/" + sv.aberto.id + "/cliente/parar", { method: "POST", headers: SV_JSON, body: JSON.stringify({ pessoa_id: id }) });
      if (!r.ok) { avisoCert(await erroDe(r)); return; }
      avisoCert(p.nome + " não vê mais esta pasta", { tom: "ok" });
      await recarregarServico();
    } },
  ]);
}

async function dialogoCompartilhar() {
  const s = sv.aberto;
  if (!s) return;
  let sug = (acp.dados && acp.dados.sugestao) || null;
  if (!sug) {
    const r = await fetch("/api/servicos/" + s.id + "/cliente");
    if (r.ok) { acp.dados = Object.assign(acp.dados || {}, await r.json()); sug = acp.dados.sugestao; }
  }
  sug = sug || { nome: "", email: "", cadastro_id: null };
  const ja = ((acp.dados && acp.dados.pessoas) || []).length;
  const v = await dialogo({
    titulo: "Compartilhar com o cliente", contexto: "Serviços › " + s.nome, larga: true,
    campos: [
      { rotulo: "Nome", chave: "nome", valor: ja ? "" : sug.nome, icone: "person", max: 80, placeholder: "João da Silva" },
      { rotulo: "E-mail", chave: "email", valor: ja ? "" : sug.email, icone: "mail", tipo: "email", max: 200, obrigatorio: true, placeholder: "cliente@exemplo.com",
        dica: "É para ele que vai o link e, depois, o código de cada entrada." },
    ],
    depois: '<p class="dialogo-dica">O cliente passa a ver o status, as etapas e os compromissos desta pasta — o que estiver com o olhinho fechado, não. Documento, só os que você compartilhar. Anotações, horas e a trilha nunca.</p>',
    confirmar: "Compartilhar e mandar o convite",
  });
  if (!v || !v.ok) return;
  const r = await fetch("/api/servicos/" + s.id + "/cliente/compartilhar", { method: "POST", headers: SV_JSON,
    body: JSON.stringify({ nome: v.valores.nome || v.valor, email: v.valores.email, cadastro_id: sug.email && v.valores.email.toLowerCase() === sug.email.toLowerCase() ? sug.cadastro_id : null }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  if (d.email_enviado) avisoCert("compartilhado: o convite foi para " + d.pessoa.email, { tom: "ok" });
  else avisoCert("compartilhado, mas o e-mail não saiu (" + d.erro_email + "). Copie o link em Quem vê esta pasta e mande por outro caminho.", { tom: "erro", dura: 12000 });
  sv.aba = "cliente";
  await recarregarServico();
}

async function publicarResumoDoCliente(texto) {
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/cliente/resumo", { method: "POST", headers: SV_JSON, body: JSON.stringify({ texto: texto }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  acp.dados.resumo = await r.json();
  avisoCert(texto.trim() ? "o cliente já vê este resumo" : "o resumo saiu da página do cliente", { tom: "ok" });
  desenharAbaDoCliente();
}

async function sugerirResumoDoCliente() {
  if (acp.carregando) return;
  acp.carregando = true;
  desenharAbaDoCliente();
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/cliente/resumo/sugerir", { method: "POST" });
  acp.carregando = false;
  if (!r.ok) avisoCert("sem rascunho agora: " + (await erroDe(r)));
  else acp.dados.resumo = await r.json();
  desenharAbaDoCliente();
}

async function responderAoCliente(texto) {
  if (!texto.trim() || acp.enviando) return;
  acp.enviando = true;
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/cliente/mensagens", { method: "POST", headers: SV_JSON, body: JSON.stringify({ texto: texto.trim() }) });
  acp.enviando = false;
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  acp.dados.mensagens = d.mensagens;
  const caixa = document.querySelector("[data-acp-resposta]");
  if (caixa) caixa.value = "";
  if (d.erro_email) avisoCert("resposta guardada, mas o aviso por e-mail não saiu: " + d.erro_email, { tom: "erro" });
  desenharAbaDoCliente();
}
