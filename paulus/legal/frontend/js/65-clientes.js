/* ------------------------------------------ visão por cliente e muralha (L3) */
/*
   "Tudo sobre o cliente" (a partir da ficha), a seção Partes de cada Serviço
   com a parte contrária, e o aviso de conflito de interesse (src/clientes.py).
   O aviso não bloqueia: diz onde a mesma pessoa ou empresa aparece do outro
   lado, e quem está na equipe dos dois lados. Quem decide é o advogado.
*/

const cli = { visao: null };

function listaDeConflitos(lista) {
  return '<div class="cli-conflitos">' + lista.map((c) =>
    '<div class="cli-conflito' + (c.tipo === "muralha" ? " muralha" : "") + '">' + ic(c.tipo === "muralha" ? "groups" : "flag", 16) +
    "<span>" + esc(c.texto) + (c.parte ? ' <small>· por “' + esc(c.parte) + "”</small>" : "") + "</span></div>").join("") + "</div>";
}

async function avisarConflitos(lista, contexto) {
  if (!lista || !lista.length) return;
  await dialogo({ titulo: "Possível conflito de interesse", contexto: contexto,
    html: '<p class="cfg-explica">A mesma pessoa ou empresa aparece do outro lado. O PAULUS reconhece o nome sem acento, sem a forma jurídica ' +
      "(Ltda., S/A, ME…) e, com os dois documentos, pelo CPF ou pela raiz do CNPJ. Confira antes de seguir.</p>" + listaDeConflitos(lista),
    confirmar: "Entendi", semCancelar: true });
}

/* Depois de gravar a ficha de um cliente (js/06-cadastros.js). */
async function avisarConflitosDoCliente(ficha) {
  if (!acessoDeFora.local || !ficha || ficha.tipo !== "cliente") return;
  try {
    const r = await fetch("/api/clientes/conflitos", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome: ficha.nome, documento: ficha.documento || "", papel: "cliente", cadastro_id: ficha.id }) });
    if (r.ok) await avisarConflitos((await r.json()).conflitos, "Cadastros › " + ficha.nome);
  } catch (err) { /* sem a conferência, a ficha fica gravada como sempre */ }
}

/* ------------------------------------------ as partes do Serviço */

function secaoDasPartes(s) {
  const partes = (s.partes || []).map((p, i) =>
    '<div class="sv-prazo-linha"><span class="duas-linhas"><b>' + esc(p.nome) + "</b><small>" +
    esc((p.papel === "interessado" ? "interessado" : "parte contrária") + (p.documento ? " · " + p.documento : "")) + "</small></span>" +
    (acessoDeFora.local ? '<button type="button" class="mais-linha" data-cli-tirar="' + i + '" title="Remover">' + ic("close", 15) + "</button>" : "") +
    "</div>").join("");
  return '<section class="sv-secao cli-partes"><div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + ic("gavel", 16) + "Partes</span>" +
    (acessoDeFora.local ? '<button type="button" class="sv-ligacao" data-cli-parte="1">' + ic("add", 15) + "parte contrária</button>" : "") + "</div>" +
    partes + '<div id="cli-conflitos-sv"></div>' +
    '<p class="sv-dica">' + (partes ? "" : "Nenhuma parte contrária anotada. ") +
    "A parte contrária é conferida contra os clientes do escritório: a mesma empresa com outro nome também é reconhecida.</p></section>";
}

async function carregarConflitosDoServico(s) {
  const alvo = $("cli-conflitos-sv");
  if (!alvo || !acessoDeFora.local) return;
  try {
    const d = await (await fetch("/api/servicos/" + s.id + "/conflitos")).json();
    alvo.innerHTML = (d.conflitos || []).length ? '<p class="cli-alerta">' + ic("flag", 16) + " Possível conflito de interesse</p>" + listaDeConflitos(d.conflitos) : "";
  } catch (err) { alvo.innerHTML = ""; }
}

async function guardarPartes(s, partes) {
  const r = await fetch("/api/servicos/" + s.id + "/partes", { method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ partes: partes }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  return r.json();
}

document.addEventListener("click", async (e) => {
  const alvo = e.target.closest && e.target.closest("[data-cli-parte], [data-cli-tirar], [data-cad-visao], [data-cli-abrir]");
  if (!alvo) return;
  e.preventDefault();
  if (alvo.dataset.cadVisao !== undefined) {
    const f = typeof cad !== "undefined" ? cad.aberta : null;
    if (dialogoAberto) dialogoAberto.fechar(null);
    if (f) mostrarVisaoDoCliente(f.id);
    return;
  }
  if (alvo.dataset.cliAbrir !== undefined) { mostrarVisaoDoCliente(Number(alvo.dataset.cliAbrir)); return; }
  const s = typeof sv !== "undefined" ? sv.aberto : null;
  if (!s) return;
  if (alvo.dataset.cliTirar !== undefined) {
    const i = Number(alvo.dataset.cliTirar);
    if (await guardarPartes(s, (s.partes || []).filter((_, k) => k !== i))) recarregarServico();
    return;
  }
  const r = await dialogo({ titulo: "Parte contrária", contexto: "Serviços › " + s.nome,
    texto: "O nome como aparece nos documentos; o CPF ou o CNPJ, se tiver, deixa a conferência de conflito certa.",
    campos: [{ chave: "nome", rotulo: "Nome", placeholder: "Empresa X Ltda.", obrigatorio: true },
      { chave: "documento", rotulo: "CPF ou CNPJ", placeholder: "opcional" }], confirmar: "Anotar" });
  if (!r || !r.ok) return;
  const d = await guardarPartes(s, (s.partes || []).concat([{ nome: r.valores.nome, documento: r.valores.documento || "", papel: "contraria" }]));
  if (!d) return;
  await avisarConflitos((d.conflitos || []).filter((c) => c.parte === r.valores.nome.trim()), "Serviços › " + s.nome);
  recarregarServico();
});

/* ------------------------------------------ tudo sobre o cliente */

function blocoDoCliente(titulo, icone, linhas, vazio) {
  return '<section class="sv-secao cli-bloco"><div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + ic(icone, 16) + esc(titulo) + "</span></div>" +
    (linhas || '<p class="sv-dica">' + esc(vazio) + "</p>") + "</section>";
}

function linhaDoCliente(texto, sub, atributos) {
  return '<div class="sv-prazo-linha cli-linha"' + (atributos || "") + '><span class="duas-linhas"><b>' + esc(texto) + "</b>" +
    (sub ? "<small>" + esc(sub) + "</small>" : "") + "</span></div>";
}

function htmlDaVisao(v) {
  const dataBR = (iso) => (iso ? String(iso).slice(0, 10).split("-").reverse().join("/") : "");
  const conflitos = (v.conflitos || []).length
    ? '<section class="sv-secao cli-bloco cli-atencao"><div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + ic("flag", 16) +
      "Possível conflito de interesse</span></div>" + listaDeConflitos(v.conflitos) + "</section>" : "";
  return conflitos + '<div class="sv-duas">' +
    blocoDoCliente("Serviços", "work", v.servicos.map((s) => linhaDoCliente(s.nome, s.status, ' data-cli-servico="' + s.id + '"')).join(""), "Nenhum Serviço deste cliente.") +
    blocoDoCliente("Processos", "gavel", v.processos.map((p) => linhaDoCliente(p.numero_fmt, [p.classe, p.servico_nome, p.novas ? p.novas + " novas" : ""].filter(Boolean).join(" · "),
      ' data-cli-processo="' + p.id + '"')).join(""), "Nenhum processo acompanhado nos Serviços dele.") + "</div>" +
    '<div class="sv-duas">' +
    blocoDoCliente("Prazos e compromissos", "event",
      v.prazos.map((t) => linhaDoCliente(t.titulo, [t.prazo ? "vence " + dataBR(t.prazo) : "sem data", t.lista].filter(Boolean).join(" · "))).join("") +
      v.compromissos.map((c) => linhaDoCliente(c.titulo, dataBR(c.data) + (c.hora ? " · " + c.hora : ""))).join(""), "Nada em aberto.") +
    blocoDoCliente("Parte contrária", "gavel", v.partes_contrarias.map((p) => linhaDoCliente(p.nome, [p.documento, "em " + p.servico].filter(Boolean).join(" · "))).join(""),
      "Nenhuma parte contrária anotada nos Serviços dele.") + "</div>" +
    blocoDoCliente("Documentos", "description", v.documentos.map((d) => linhaDoCliente(d.nome, d.como, ' data-cli-doc="' + esc(d.nome) + '"')).join(""),
      "Nenhum documento ligado ou em que ele apareça como parte.") +
    (v.outros_nomes.length ? blocoDoCliente("Também aparece como", "person", v.outros_nomes.map((n) => linhaDoCliente(n.nome, n.grau === "igual" ? "o mesmo nome, escrito de outro jeito" : "parece ser o mesmo")).join(""), "") : "");
}

async function mostrarVisaoDoCliente(id) {
  abrirTela("Cliente", { cheia: true });
  marcarDestino("cadastros");
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal sv-principal"><div class="sv-medida" id="cli-visao"><p class="nota">abrindo…</p></div></div></div>';
  atualizarPostura();
  let v;
  try {
    const r = await fetch("/api/clientes/" + id + "/visao");
    if (!r.ok) throw new Error(await erroDe(r));
    v = await r.json();
  } catch (err) {
    $("cli-visao").innerHTML = '<p class="nota">não consegui abrir: ' + esc(String(err.message || err)) + "</p>";
    return;
  }
  cli.visao = v;
  $("conversa-titulo").textContent = v.cliente.nome;
  $("conversa-meta").textContent = "tudo sobre o cliente" + (v.cliente.documento ? " · " + v.cliente.documento : "");
  $("cli-visao").innerHTML = htmlDaVisao(v);
  const tela = $("cli-visao");
  tela.querySelectorAll("[data-cli-servico]").forEach((el) => { el.onclick = () => abrirServico(Number(el.dataset.cliServico)); });
  tela.querySelectorAll("[data-cli-processo]").forEach((el) => { el.onclick = () => abrirProcesso(Number(el.dataset.cliProcesso)); });
  tela.querySelectorAll("[data-cli-doc]").forEach((el) => { el.onclick = () => verNoAcervo(el.dataset.cliDoc); });
}
