/* N15 — a nuvem com a chave do escritório (src/nuvem.py, src/rotas_nuvem.py).

   - Configurações › Modelos: o cartão "Nuvem (chave do escritório)" - guardar
     e testar a chave, o modelo, mascarar, ligar, e o registro de envios.
   - A caixa da pergunta: a pílula "Nuvem", só na janela do escritório e com a
     nuvem ligada. Marcada, a próxima pergunta pede para ir à nuvem.
   - A conversa: o cartão do pedido, com o que vai sair, "Mandar", "Responder
     aqui" e "Liberar nesta conversa"; e a linha de onde a resposta foi escrita.

   Nada aqui manda nada sozinho: cada envio espera o sim (o cartão ou
   Aprovações), a não ser que a pessoa libere a conversa ou ligue a regra de
   alçada "Mandar à nuvem sem pedir a cada pergunta". */

const nuvemTela = { dados: null, modelos: [], envios: [], marcada: false, guardando: false };

async function carregarNuvem() {
  try {
    const r = await fetch("/api/nuvem");
    nuvemTela.dados = r.ok ? await r.json() : null;
  } catch (err) {
    nuvemTela.dados = null;
  }
  desenharPilulaNuvem();
  return nuvemTela.dados;
}

/* ------------------------------------------------------------ Configurações › Modelos */

function cartaoNuvem() {
  const d = nuvemTela.dados;
  if (!d) return "";
  const prov = (d.provedores || []).find((p) => p.id === d.provedor) || (d.provedores || [])[0] || {};
  const opProv = (d.provedores || []).map((p) =>
    '<option value="' + esc(p.id) + '"' + (p.id === d.provedor ? " selected" : "") + ">" + esc(p.nome) + (p.tem_chave ? " · chave guardada" : "") + "</option>").join("");
  const lista = nuvemTela.modelos.length ? nuvemTela.modelos : (d.modelo ? [d.modelo] : []);
  const opMod = lista.map((m) => '<option value="' + esc(m) + '"' + (m === d.modelo ? " selected" : "") + ">" + esc(m) + "</option>").join("");
  const estadoTxt = d.ligada ? "ligada · cada pergunta marcada “Nuvem” " + (d.sem_pedir ? "vai sem pedir (regra de alçada)" : "espera o seu sim")
    : (d.ligado ? "falta a chave ou o modelo" : "desligada");
  const envios = nuvemTela.envios.slice(0, 8).map((e) =>
    '<div class="cfg-servico"><span class="caixa-tipo">' + ic("upload", 18) + '</span><span class="duas-linhas cresce"><b>' +
    esc((e.titulo || "pergunta").slice(0, 80)) + "</b><small>" + esc(dataHoraCurta(e.quando)) + " · " + esc(e.modelo) + " · " +
    milhar(e.caracteres || 0) + " caracteres" + (e.tokens_entrada ? " · " + milhar(e.tokens_entrada) + " + " + milhar(e.tokens_saida || 0) + " tokens" : "") +
    " · " + esc(e.como || "") + "</small></span>" +
    '<button data-nuvem-envio="' + esc(e.envio) + '">Ver o que saiu</button></div>').join("");
  const corpo =
    '<p class="cfg-texto">A resposta da conversa sobre os documentos pode ser escrita por um modelo da Anthropic ou da OpenAI, ' +
    "com a <b>chave de API do próprio escritório</b> (paga pelo escritório, direto no provedor). A assinatura de consumidor " +
    "(ChatGPT Plus, Claude Pro) não serve: os termos dos dois proíbem usar o login dela num programa.</p>" +
    '<p class="cfg-explica">O que sai: a pergunta e os trechos que a busca achou — os mesmos que iriam ao modelo daqui. A busca, as regras, ' +
    "a conferência e o resto do programa continuam neste computador. Nunca sai: o anexo guardado do e-mail (desta versão em diante), a cópia das pastas do Drive que o PAULUS faz e o caso " +
    "marcado só no escritório. De fora (acesso remoto), não há nuvem. Cada envio fica no registro abaixo, com o texto exato que saiu.</p>" +
    '<div class="cfg-linhas">' +
    '<div class="cfg-servico"><span class="duas-linhas cresce"><b>Provedor</b><small>' + esc(estadoTxt) + "</small></span>" +
    '<select id="nuvem-provedor" aria-label="Provedor">' + opProv + "</select></div>" +
    '<div class="linha-form"><input type="password" id="nuvem-chave" autocomplete="off" spellcheck="false" placeholder="' +
    (prov.tem_chave ? "chave guardada · cole outra para trocar" : (d.provedor === "openai" ? "sk-…" : "sk-ant-…")) + '">' +
    '<button data-nuvem-guardar="1"' + (nuvemTela.guardando ? " disabled" : "") + ">" + (nuvemTela.guardando ? "testando…" : "Guardar e testar") + "</button>" +
    (prov.tem_chave ? '<button class="perigo" data-nuvem-apagar="1">Apagar a chave</button>' : "") + "</div>" +
    (d.dpapi ? "" : '<p class="cfg-explica mod-erro">Este Windows não guarda segredo cifrado (DPAPI): a chave não pode ser guardada.</p>') +
    '<div class="cfg-servico"><span class="duas-linhas cresce"><b>Modelo</b><small>a lista é a que a chave enxerga; cobra por token, na conta do escritório</small></span>' +
    (lista.length ? '<select id="nuvem-modelo" aria-label="Modelo da nuvem">' + opMod + "</select>" : "<small>guarde a chave para ver</small>") + "</div>" +
    '<label class="cfg-servico"><span class="duas-linhas cresce"><b>Mascarar antes de sair</b><small>CPF, CNPJ, número de processo, e-mail e telefone viram ' +
    "“[CPF 1]”… e voltam na resposta. Reduz a exposição, não anonimiza: o nome, o endereço e o resto do texto vão como estão.</small></span>" +
    '<input type="checkbox" id="nuvem-mascarar"' + (d.mascarar ? " checked" : "") + "></label>" +
    '<label class="cfg-servico"><span class="duas-linhas cresce"><b>Ligar a nuvem</b><small>desligada de fábrica; ligada, a caixa da pergunta ganha a pílula “Nuvem”</small></span>' +
    '<input type="checkbox" id="nuvem-ligado"' + (d.ligado ? " checked" : "") + (prov.tem_chave && d.modelo ? "" : " disabled") + "></label>" +
    "</div>" +
    (envios ? '<p class="sv-kicker">Registro de envios · ' + plural(d.envios || 0, "envio") + '</p><div class="cfg-linhas">' + envios + "</div>" : "");
  return cartaoCfg("Nuvem (chave do escritório)", metaCfg(d.ligada ? "ligada" : "desligada"), corpo, "nuvem-cartao");
}

async function nuvemPost(url, corpo, metodo) {
  const r = await fetch(url, { method: metodo || "POST", headers: { "Content-Type": "application/json" }, body: corpo ? JSON.stringify(corpo) : undefined });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  return r.json();
}

async function carregarNuvemNaConfig() {
  await carregarNuvem();
  try {
    const r = await fetch("/api/nuvem/envios?limite=8");
    nuvemTela.envios = r.ok ? (await r.json()).envios || [] : [];
  } catch (err) { nuvemTela.envios = []; }
}

function ligarNuvemNaConfig(raiz, redesenhar) {
  desenharPilulaNuvem();
  if (!raiz || !nuvemTela.dados) return;
  const d = nuvemTela.dados;
  const prov = raiz.querySelector("#nuvem-provedor");
  if (prov) prov.onchange = async () => {
    nuvemTela.modelos = [];
    const novo = await nuvemPost("/api/nuvem/configurar", { provedor: prov.value, modelo: "", ligado: false });
    if (novo) { nuvemTela.dados = novo; redesenhar(); }
  };
  const guardar = raiz.querySelector("[data-nuvem-guardar]");
  if (guardar) guardar.onclick = async () => {
    const chave = (raiz.querySelector("#nuvem-chave").value || "").trim();
    if (!chave) { avisoCert("Cole a chave de API do provedor.", { tom: "erro" }); return; }
    nuvemTela.guardando = true; redesenhar();
    const r = await nuvemPost("/api/nuvem/chave", { provedor: (prov && prov.value) || d.provedor, chave: chave });
    nuvemTela.guardando = false;
    if (r) {
      nuvemTela.dados = r; nuvemTela.modelos = r.modelos || [];
      avisoCert("Chave guardada e testada: a conta enxerga " + plural(nuvemTela.modelos.length, "modelo") + ".", { tom: "ok" });
    }
    redesenhar();
  };
  const apagar = raiz.querySelector("[data-nuvem-apagar]");
  if (apagar) apagar.onclick = async () => {
    const r = await nuvemPost("/api/nuvem/chave/" + encodeURIComponent(d.provedor), null, "DELETE");
    if (r) { nuvemTela.dados = r; nuvemTela.modelos = []; avisoCert("Chave apagada deste computador.", { tom: "ok" }); }
    redesenhar();
  };
  const modelo = raiz.querySelector("#nuvem-modelo");
  if (modelo) {
    modelo.onfocus = async () => {
      if (nuvemTela.modelos.length) return;
      const r = await fetch("/api/nuvem/modelos?provedor=" + encodeURIComponent(d.provedor));
      if (r.ok) { nuvemTela.modelos = (await r.json()).modelos || []; redesenhar(); }
    };
    modelo.onchange = async () => { const r = await nuvemPost("/api/nuvem/configurar", { modelo: modelo.value }); if (r) { nuvemTela.dados = r; redesenhar(); } };
  }
  const mascarar = raiz.querySelector("#nuvem-mascarar");
  if (mascarar) mascarar.onchange = async () => { const r = await nuvemPost("/api/nuvem/configurar", { mascarar: mascarar.checked }); if (r) nuvemTela.dados = r; redesenhar(); };
  const ligado = raiz.querySelector("#nuvem-ligado");
  if (ligado) ligado.onchange = async () => { const r = await nuvemPost("/api/nuvem/configurar", { ligado: ligado.checked }); if (r) nuvemTela.dados = r; redesenhar(); };
  raiz.querySelectorAll("[data-nuvem-envio]").forEach((b) => {
    b.onclick = async () => {
      const r = await fetch("/api/nuvem/envios/" + encodeURIComponent(b.dataset.nuvemEnvio));
      if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
      const e = await r.json();
      dialogo({ titulo: "O que saiu neste envio", contexto: "Configurações › Modelos › Nuvem", classe: "dialogo-ver", larga: true, confirmar: "Fechar",
        html: '<pre class="nuvem-texto">' + esc(e.texto) + "</pre>" });
    };
  });
}

/* ------------------------------------------------------------ a caixa da pergunta */

function desenharPilulaNuvem() {
  const d = nuvemTela.dados;
  const pode = Boolean(d && d.ligada) && (typeof acessoDeFora === "undefined" || acessoDeFora.local);
  let b = document.getElementById("pilula-nuvem");
  if (!pode) { if (b) b.remove(); nuvemTela.marcada = false; return; }
  if (!b) {
    const ditar = document.getElementById("ditar");
    if (!ditar) return;
    b = document.createElement("button");
    b.type = "button";
    b.id = "pilula-nuvem";
    b.className = "pilula pilula-nuvem";
    b.onclick = () => { nuvemTela.marcada = !nuvemTela.marcada; desenharPilulaNuvem(); const p = document.getElementById("pedido"); if (p) p.focus(); };
    ditar.parentNode.insertBefore(b, ditar);
  }
  const prov = ((d.provedores || []).find((p) => p.id === d.provedor) || {}).nome || "nuvem";
  b.classList.toggle("ativa", nuvemTela.marcada);
  b.setAttribute("aria-pressed", nuvemTela.marcada ? "true" : "false");
  b.title = nuvemTela.marcada
    ? "A próxima pergunta pede para ir à " + prov + " (" + d.modelo + ")" + (d.sem_pedir ? ", sem pedir" : ": o texto que sai aparece antes")
    : "Marcar para a próxima pergunta ir à " + prov + ", com a chave do escritório";
  b.innerHTML = ic("cloud_upload", 18) + '<span class="rotulo-botao">Nuvem</span>';
}

/* O que vai junto da pergunta: a marca vale para uma pergunta só. */
function nuvemDoEnvio() {
  if (!nuvemTela.marcada) return {};
  nuvemTela.marcada = false;
  desenharPilulaNuvem();
  return { nuvem: true };
}

/* ------------------------------------------------------------ a conversa */

function cartaoPedidoNuvem(d) {
  const masc = Object.entries(d.mascarados || {}).map(([t, n]) => n + " " + t).join(", ");
  return '<div class="proposta nuvem-pedido" data-nuvem-pedido="' + esc(d.pedido_id || "") + '">' +
    '<div class="proposta-topo"><span class="rotulo">sai desta máquina</span><b>Mandar à ' + esc(d.provedor) + "?</b></div>" +
    '<p class="explica">Vai para o modelo ' + esc(d.modelo) + ": a pergunta e os trechos de " + plural((d.documentos || []).length, "documento") +
    (d.documentos && d.documentos.length ? " (" + esc(d.documentos.slice(0, 4).join(", ")) + (d.documentos.length > 4 ? "…" : "") + ")" : "") +
    ", " + milhar(d.caracteres || 0) + " caracteres (~" + milhar(d.tokens_aprox || 0) + " tokens, cobrados na conta do escritório). " +
    (d.mascarar ? (masc ? "Mascarados: " + esc(masc) + "." : "Nada para mascarar.") : "Sem mascarar.") +
    " O pedido também está em Aprovações; responder aqui não manda nada.</p>" +
    '<div class="linha-form"><button class="primario com-icone" data-nuvem-mandar="1">' + ic("cloud_upload", 15) + "Mandar</button>" +
    '<button data-nuvem-aqui="1">Responder aqui</button>' +
    '<button data-nuvem-ver="1">Ver o texto exato</button>' +
    '<label class="nuvem-liberar"><input type="checkbox" data-nuvem-liberar="1"> liberar nesta conversa</label></div></div>';
}

async function decidirNuvem(pedidoId, aprovar) {
  const r = await fetch("/api/aprovacoes/decidir", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [pedidoId], aprovar: aprovar }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return false; }
  return true;
}

function ligarPedidoNuvem(caixa, d, conversaId) {
  const id = d.pedido_id;
  const fechar = (txt) => {
    caixa.querySelectorAll("button, input").forEach((b) => { b.disabled = true; });
    const ex = caixa.querySelector(".explica");
    if (ex && txt) ex.insertAdjacentHTML("afterend", '<p class="nota">' + esc(txt) + "</p>");
  };
  const mandar = caixa.querySelector("[data-nuvem-mandar]");
  if (mandar) mandar.onclick = async () => {
    const lib = caixa.querySelector("[data-nuvem-liberar]");
    if (lib && lib.checked && conversaId) await nuvemPost("/api/trabalhos/" + encodeURIComponent(conversaId) + "/nuvem", { liberada: true });
    if (await decidirNuvem(id, true)) fechar(lib && lib.checked ? "Mandado. As próximas perguntas desta conversa marcadas “Nuvem” vão sem pedir." : "Mandado.");
  };
  const aqui = caixa.querySelector("[data-nuvem-aqui]");
  if (aqui) aqui.onclick = async () => { if (await decidirNuvem(id, false)) fechar("Nada saiu: a resposta é escrita neste computador."); };
  const ver = caixa.querySelector("[data-nuvem-ver]");
  if (ver) ver.onclick = async () => {
    const r = await fetch("/api/aprovacoes");
    const lista = r.ok ? ((await r.json()).pendentes || []) : [];
    const p = lista.find((x) => x.id === id);
    dialogo({ titulo: "O texto exato que vai sair", contexto: "Conversa › Nuvem", classe: "dialogo-ver", larga: true, confirmar: "Fechar",
      html: '<pre class="nuvem-texto">' + esc(p ? (p.dados || {}).texto_exato || "" : "o pedido já foi decidido") + "</pre>" });
  };
}

/* Os eventos da resposta (js/03-assistente.js). */
function eventoDaNuvem(tipo, d, v) {
  if (tipo === "nuvem_pedido") {
    if (v.anotar) v.anotar("a pergunta espera o seu sim para ir à " + d.provedor + " (" + d.modelo + ")");
    if (v.linha) v.linha("Esperando o seu sim para mandar à " + d.provedor + "…");
    if (d.precisa_aprovar && v.resposta) {
      v.resposta.insertAdjacentHTML("afterbegin", cartaoPedidoNuvem(d));
      ligarPedidoNuvem(v.resposta.querySelector(".nuvem-pedido"), d, v.conversaId);
    }
  } else if (tipo === "nuvem_mandando") {
    const c = v.resposta && v.resposta.querySelector(".nuvem-pedido");
    if (c) c.remove();
    if (v.anotar) v.anotar("mandei à " + d.provedor + " (" + d.modelo + ")" + (d.como ? " · " + d.como : ""));
    if (v.linha) v.linha("A " + d.provedor + " está escrevendo…");
  } else if (tipo === "nuvem_fim") {
    const c = v.resposta && v.resposta.querySelector(".nuvem-pedido");
    if (c) c.remove();
    if (d.onde === "computador") {
      if (v.anotar) v.anotar("escrevi neste computador: " + (d.motivo || ""), "atencao");
      if (v.linha) v.linha("Escrevendo neste computador…");
    } else if (v.anotar) {
      v.anotar("a " + (d.provedor || "nuvem") + " escreveu" + (d.tokens_entrada ? " · " + milhar(d.tokens_entrada) + " + " + milhar(d.tokens_saida || 0) + " tokens" : "") +
        (d.incompleta ? " · parou no meio: " + (d.motivo || "") : ""), d.incompleta ? "atencao" : "");
    }
  }
}

/* A linha de "como" da resposta guardada: onde foi escrita. */
function fraseDaNuvem(como) {
  const n = (como || {}).nuvem;
  if (!n) return "";
  if (n.onde === "nuvem") return "escrita pela " + n.provedor + " (" + n.modelo + ")" + (Object.keys(n.mascarados || {}).length ? ", com dados mascarados" : "");
  return "escrita neste computador: " + (n.motivo || "");
}

document.addEventListener("DOMContentLoaded", () => { setTimeout(carregarNuvem, 400); });
