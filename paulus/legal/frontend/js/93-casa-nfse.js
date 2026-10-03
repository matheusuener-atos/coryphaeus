/* ------------------------------------------------- notas do PAVLVS */
/*
   A tela "Notas do PAVLVS" (src/casa_nfse.py): a NFS-e que o PAVLVS emite
   para quem assina o PAULUS. Só existe no PAULUS da casa (o do servidor do
   dono, com PAULUS_CASA_PAVLVS=1); nos escritórios o botão do trilho nem
   aparece. Pelo túnel, só o titular.

   No alto: Emitir NFS-e, Clientes, Parâmetros e Testar comunicação. Depois o
   certificado numa linha (arquivo + senha) e o cartão dele; por fim a lista
   das notas, com Baixar, Imprimir, XML e Enviar ao cliente (vira aviso no
   app dele: "Sua NFS-e de … chegou", com Download e XML).
*/

const cn = { dados: null, teste: null, clientes: null, pagamentos: null };
const CN_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

async function casaNfseDisponivel() {
  try {
    const r = await fetch("/api/casa-nfse/disponivel");
    const d = r.ok ? await r.json() : {};
    document.querySelectorAll('[data-destino="pavlvs"]').forEach((b) => { b.hidden = !d.ligada; });
  } catch (err) { /* sem a tela */ }
}

async function mostrarNotasPavlvs() {
  abrirTela("Notas do PAVLVS", { cheia: true });
  marcarDestino("pavlvs");
  $("conversa-meta").textContent = "A NFS-e que o PAVLVS emite para quem assina o PAULUS";
  cascaCasaNfse('<p class="nota">lendo…</p>');
  await carregarCasaNfse();
}

function cascaCasaNfse(html) {
  $("centro").innerHTML = '<div class="acervo sem-painel cn-tela" id="cn-tela"><div class="acervo-principal sv-principal">' +
    '<div class="sv-medida">' + html + "</div></div></div>";
  atualizarPostura();
}

async function cnPedir(url, opcoes) {
  const r = await fetch(url, opcoes);
  if (!r.ok) throw new Error(await erroDe(r));
  return r.json();
}

async function cnPost(url, corpo) {
  return cnPedir(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) });
}

async function carregarCasaNfse() {
  try { cn.dados = await cnPedir("/api/casa-nfse"); } catch (err) {
    cascaCasaNfse('<p class="nota">Não consegui ler as notas do PAVLVS: ' + esc(err.message) + "</p>");
    return;
  }
  desenharCasaNfse();
}

function cnData(iso) {
  const s = String(iso || "");
  return s.length >= 10 ? s.slice(8, 10) + "/" + s.slice(5, 7) + "/" + s.slice(0, 4) : (s || "—");
}

function cnCompetencia(c) {
  const m = /^(\d{4})-(\d{2})/.exec(c || "");
  return m ? CN_MESES[Number(m[2]) - 1] + "/" + m[1] : "—";
}

function cnDoc(d) {
  const x = String(d || "").replace(/\D/g, "");
  if (x.length === 14) return x.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
  if (x.length === 11) return x.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4");
  return d || "";
}

function cnLinha(rotulo, valor, tom) {
  return '<div class="word-linha"><span>' + esc(rotulo) + '</span><b class="' + (tom || "") + '">' + esc(valor) + "</b></div>";
}

function desenharCasaNfse() {
  const d = cn.dados;
  const cert = d.certificado || {};
  const c = cert.certificado || {};
  const p = (d.prestador || {}).dados || {};
  const producao = d.ambiente === "producao";

  const topo = '<header class="cn-topo"><div><p class="cfg-explica">' +
    (producao ? '<span class="cn-selo producao">produção</span> as notas valem de verdade.'
      : '<span class="cn-selo">ambiente de testes</span> produção restrita, sem valor fiscal. Para valer, Parâmetros › Produção.') +
    "</p></div><div class=\"cn-acoes\">" +
    '<button class="primario" data-cn="emitir">' + ic("receipt_long", 16) + "Emitir NFS-e</button>" +
    '<button data-cn="clientes">' + ic("contacts", 16) + "Clientes</button>" +
    '<button data-cn="parametros">' + ic("tune", 16) + "Parâmetros</button>" +
    '<button data-cn="testar">' + ic("lan", 16) + "Testar comunicação</button></div></header>";

  const faltas = (d.motivos || []).length
    ? '<p class="cn-falta"><b>Ainda não dá para emitir:</b> ' + esc(d.motivos.join("; ")) + ".</p>" : "";

  const linhaCert = '<div class="cn-cert-linha">' +
    '<input type="file" id="cn-pfx" accept=".pfx,.p12" aria-label="Certificado A1 (.pfx ou .p12)">' +
    '<input type="password" id="cn-senha" placeholder="senha do certificado" autocomplete="off" aria-label="Senha do certificado">' +
    '<button data-cn="certificado">' + ic("upload", 16) + (cert.instalado ? "Trocar" : "Instalar") + "</button></div>";

  const dias = c.dias_restantes;
  const cartaoCert = cert.instalado
    ? '<div class="cn-cert-cartao">' + cnLinha("Nome", (c.titular || "—").split(":")[0]) + cnLinha("CNPJ", c.documento || "—") +
      cnLinha("Vencimento", c.valido_ate ? cnData(c.valido_ate) + (dias != null ? " · " + (dias < 0 ? "vencido" : dias + " dias") : "") : "—",
        c.vencido || (dias != null && dias <= 30) ? "erro" : "") +
      (cert.avisos || []).map((a) => '<p class="cfg-explica"><b>' + esc(a) + "</b></p>").join("") + "</div>"
    : '<p class="cfg-explica">Nenhum certificado ainda. Use o A1 (.pfx ou .p12) do CNPJ do PAVLVS; o CNPJ e o nome vêm dele.</p>';

  const t = cn.teste;
  const teste = t ? '<div class="cn-teste ' + (t.ok ? "ok" : "erro") + '"><b>' + (t.ok ? "Comunicação ok" : "A comunicação falhou") + "</b>" +
    t.etapas.map((e) => cnLinha((e.ok ? "✓ " : "✗ ") + e.titulo, e.detalhe || "", e.ok ? "ok" : "erro")).join("") + "</div>" : "";

  const certificado = '<section class="cfg-cartao cn-bloco"><h3>Certificado digital</h3>' + linhaCert + cartaoCert + "</section>";

  const linhas = (d.notas || []).map((n) => {
    const ok = n.estado === "emitida";
    const acoes = ok
      ? '<a class="cn-mini" href="/api/casa-nfse/notas/' + n.id + '/pdf?baixar=1" title="Baixar o PDF">' + ic("download", 16) + "PDF</a>" +
        '<button class="cn-mini" data-cn="imprimir" data-id="' + n.id + '" title="Imprimir">' + ic("print", 16) + "</button>" +
        '<a class="cn-mini" href="/api/casa-nfse/notas/' + n.id + '/xml" title="Baixar o XML">' + ic("code", 16) + "XML</a>" +
        '<button class="cn-mini" data-cn="enviar" data-id="' + n.id + '"' + (n.conta ? "" : ' disabled title="nota sem conta de assinante"') + ">" +
        ic("send", 16) + (n.enviada_em ? "Reenviar" : "Enviar ao cliente") + "</button>" +
        '<button class="cn-mini" data-cn="substituir" data-id="' + n.id + '" title="Emitir uma nota que substitui esta">' + ic("swap_horiz", 16) + "Substituir</button>" +
        '<button class="cn-mini perigo" data-cn="cancelar" data-id="' + n.id + '" title="Cancelar no Sistema Nacional">' + ic("block", 16) + "Cancelar</button>"
      : (n.estado === "cancelada" || n.estado === "substituida"
        ? '<a class="cn-mini" href="/api/casa-nfse/notas/' + n.id + '/xml" title="Baixar o XML">' + ic("code", 16) + "XML</a>"
        : '<span class="cfg-explica">' + esc(n.erro || "") + "</span>");
    return "<tr><td>" + esc(n.numero || "—") + "</td><td><b>" + esc(n.cliente) + "</b><small>" + esc(cnDoc(n.documento)) + "</small></td><td>" +
      esc(cnCompetencia(n.competencia)) + '</td><td class="cn-num">' + esc(n.valor) + "</td><td>" + esc(n.estado_rotulo) +
      (n.ambiente !== "producao" ? " <small>(testes)</small>" : "") + (n.enviada_em ? "<small>enviada " + esc(cnData(n.enviada_em)) + (n.email ? " · e-mail: " + esc(n.email) : "") + "</small>" : "") +
      '</td><td class="cn-acoes-linha">' + acoes + "</td></tr>";
  }).join("");
  const lista = '<section class="cfg-cartao cn-bloco"><h3>Notas emitidas</h3>' + (linhas
    ? '<div class="cn-rolagem"><table class="cn-tabela"><thead><tr><th>Nº</th><th>Cliente</th><th>Competência</th><th>Valor</th><th>Situação</th><th></th></tr></thead><tbody>' +
      linhas + "</tbody></table></div>"
    : '<p class="cfg-explica">Nenhuma nota ainda. Comece por “Emitir NFS-e”.</p>') + "</section>";

  cascaCasaNfse(topo + faltas + teste + certificado + lista);
}

/* ----------------------------------------------------------- ações */

async function cnAcao(acao, el) {
  try {
    if (acao === "certificado") {
      const f = $("cn-pfx");
      if (!f || !f.files || !f.files[0]) { avisoCert("escolha o arquivo .pfx ou .p12", { tom: "erro" }); return; }
      const fd = new FormData();
      fd.append("arquivo", f.files[0]);
      fd.append("senha", ($("cn-senha") || {}).value || "");
      cn.dados = await cnPedir("/api/casa-nfse/certificado", { method: "POST", body: fd });
      avisoCert("certificado instalado", { tom: "ok" });
      desenharCasaNfse();
    } else if (acao === "testar") {
      el.disabled = true;
      el.textContent = "Testando…";
      cn.teste = await cnPost("/api/casa-nfse/testar");
      await carregarCasaNfse();
    } else if (acao === "imprimir") {
      cnImprimir(el.dataset.id);
    } else if (acao === "enviar") {
      await cnPost("/api/casa-nfse/notas/" + el.dataset.id + "/enviar");
      avisoCert("enviada: o cliente recebe o aviso no PAULUS dele", { tom: "ok" });
      await carregarCasaNfse();
    } else if (acao === "emitir") {
      await cnDialogoEmitir();
    } else if (acao === "clientes") {
      await cnDialogoClientes();
    } else if (acao === "parametros") {
      await cnDialogoParametros();
    } else if (acao === "cancelar") {
      await cnDialogoCancelar(Number(el.dataset.id));
    } else if (acao === "substituir") {
      await cnDialogoSubstituir(Number(el.dataset.id));
    }
  } catch (err) {
    avisoCert(err.message, { tom: "erro" });
    if (acao === "testar") desenharCasaNfse();
  }
}

/* O PDF num quadro escondido, e a impressão do navegador. */
function cnImprimir(id) {
  const antigo = $("cn-impressao");
  if (antigo) antigo.remove();
  const q = document.createElement("iframe");
  q.id = "cn-impressao";
  q.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
  q.src = "/api/casa-nfse/notas/" + id + "/pdf";
  q.onload = () => { try { q.contentWindow.focus(); q.contentWindow.print(); } catch (err) { window.open(q.src, "_blank"); } };
  document.body.appendChild(q);
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-cn]");
  if (!b || !b.closest("#cn-tela")) return;
  cnAcao(b.dataset.cn, b);
});

/* ------------------------------------------------- campos dos pop-ups */

function cnCampo(chave, rotulo, valor, extra) {
  return '<div class="dialogo-campo"><label>' + esc(rotulo) + '</label><div class="dialogo-caixa"><input data-cn-campo="' + chave +
    '" value="' + esc(valor == null ? "" : String(valor)) + '"' + (extra || "") + ' autocomplete="off"></div></div>';
}

function cnEscolha(chave, rotulo, opcoes, valor) {
  return '<div class="dialogo-campo"><label>' + esc(rotulo) + '</label><div class="dialogo-caixa"><select data-cn-campo="' + chave + '">' +
    Object.entries(opcoes).map(([k, v]) => '<option value="' + esc(k) + '"' + (String(k) === String(valor) ? " selected" : "") + ">" + esc(v) + "</option>").join("") +
    "</select></div></div>";
}

function cnDuas(a, b) { return '<div class="dialogo-duas">' + a + b + "</div>"; }

/* Os campos com data-cn-campo viram objeto ("endereco.cep" -> {endereco: {cep}}). */
function cnValores(raiz) {
  const dados = {};
  raiz.querySelectorAll("[data-cn-campo]").forEach((el) => {
    const partes = el.dataset.cnCampo.split(".");
    let alvo = dados;
    partes.slice(0, -1).forEach((k) => { alvo[k] = alvo[k] || {}; alvo = alvo[k]; });
    alvo[partes[partes.length - 1]] = el.type === "checkbox" ? el.checked : el.value;
  });
  return dados;
}

function cnErroNoDialogo(msg) {
  const caixa = document.querySelector("#veu-dialogo .cn-erro-dialogo");
  if (caixa) { caixa.textContent = msg; caixa.hidden = !msg; }
}

const CN_TOMADOR = [["nome", "Nome ou razão social"], ["documento", "CPF ou CNPJ"], ["email", "E-mail"], ["telefone", "Telefone"],
  ["cep", "CEP"], ["logradouro", "Rua"], ["numero", "Número"], ["complemento", "Complemento"], ["bairro", "Bairro"],
  ["cmun", "Município (código IBGE)"], ["inscricao_municipal", "Inscrição municipal (se houver)"]];

function cnCamposTomador(t, prefixo) {
  const c = CN_TOMADOR.map(([k, r]) => cnCampo(prefixo + k, r, (t || {})[k], k === "cmun" ? ' list="cn-municipios" data-cn-busca="1" placeholder="digite o nome da cidade"' : ""));
  let html = "";
  for (let i = 0; i < c.length; i += 2) html += cnDuas(c[i], c[i + 1] || "<span></span>");
  return html + '<datalist id="cn-municipios"></datalist>';
}

let cnRelogioBusca = 0;
document.addEventListener("input", (e) => {
  const el = e.target;
  if (!el.matches || !el.matches("[data-cn-busca]")) return;
  const q = el.value.trim();
  if (q.length < 3 || /^\d{7}$/.test(q)) return;
  clearTimeout(cnRelogioBusca);
  cnRelogioBusca = setTimeout(async () => {
    const r = await fetch("/api/casa-nfse/municipios?q=" + encodeURIComponent(q)).catch(() => null);
    if (!r || !r.ok) return;
    const lista = $("cn-municipios");
    if (lista) lista.innerHTML = ((await r.json()).itens || []).map((m) => '<option value="' + esc(m.codigo) + '">' + esc(m.nome + "/" + m.uf) + "</option>").join("");
  }, 250);
});

/* --------------------------------------------------------- emitir */

async function cnDialogoEmitir() {
  let clientes = [], pagamentos = [], semPonte = "";
  try {
    [clientes, pagamentos] = await Promise.all([
      cnPedir("/api/casa-nfse/clientes").then((x) => x.clientes || []),
      cnPedir("/api/casa-nfse/pagamentos").then((x) => (x.pagamentos || []).filter((p) => p.nota !== "emitida"))]);
  } catch (err) { semPonte = err.message; }
  const hoje = new Date();
  const mesPassado = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
  const competencia = mesPassado.getFullYear() + "-" + String(mesPassado.getMonth() + 1).padStart(2, "0");
  const html =
    (semPonte ? '<p class="dialogo-dica">Sem a lista de clientes (' + esc(semPonte) + "): preencha à mão. A nota não poderá ser enviada ao app do cliente.</p>" : "") +
    cnDuas('<div class="dialogo-campo"><label>Cliente (assinante)</label><div class="dialogo-caixa"><select id="cn-e-cliente" data-cn-campo="conta">' +
      '<option value="">— preencher à mão —</option>' + clientes.map((c) => '<option value="' + esc(c.id) + '">' + esc(c.nome) + "</option>").join("") +
      "</select></div></div>",
      '<div class="dialogo-campo"><label>Pagamento sem nota</label><div class="dialogo-caixa"><select id="cn-e-pagamento" data-cn-campo="pagamento">' +
      '<option value="">— nenhum —</option>' + pagamentos.map((p) => '<option value="' + esc(p.id) + '">' + esc(p.cliente + " · " + p.tipo + " · R$ " +
        Number(p.valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 }) + " · " + cnData(p.quando)) + "</option>").join("") +
      "</select></div></div>") +
    "<h4 class=\"cn-sub\">Tomador</h4>" + cnCamposTomador({}, "tomador.") +
    "<h4 class=\"cn-sub\">Serviço</h4>" +
    cnDuas(cnCampo("valor", "Valor (R$)", "", ' placeholder="300,00"'), cnCampo("competencia", "Competência", competencia, ' type="month"')) +
    cnCampo("descricao", "Descrição", "Assinatura do PAULUS — plano mensal") +
    '<p class="dialogo-dica">' + (cn.dados && cn.dados.ambiente === "producao" ? "<b>Produção:</b> esta nota vale de verdade." : "Ambiente de testes: a nota não tem valor fiscal.") + "</p>" +
    '<p class="cn-erro-dialogo" hidden></p>';
  let emitindo = false;
  const enviar = async () => {
    if (emitindo) return;
    const raiz = $("veu-dialogo");
    const v = cnValores(raiz);
    if (v.competencia) v.competencia = v.competencia + "-01";
    emitindo = true;
    cnErroNoDialogo("");
    const ok = raiz.querySelector('[data-dialogo="confirmar"]');
    if (ok) { ok.disabled = true; ok.textContent = "Emitindo…"; }
    try {
      const n = await cnPost("/api/casa-nfse/emitir", v);
      dialogoAberto.fechar({ ok: true });
      avisoCert(n.estado === "emitida" ? "NFS-e nº " + n.numero + " emitida" : "a nota ficou “" + n.estado_rotulo + "”: " + (n.erro || ""), { tom: n.estado === "emitida" ? "ok" : "erro" });
      await carregarCasaNfse();
    } catch (err) {
      cnErroNoDialogo(err.message);
      if (ok) { ok.disabled = false; ok.textContent = "Emitir"; }
    } finally { emitindo = false; }
  };
  setTimeout(() => {
    const raiz = $("veu-dialogo");
    if (!raiz) return;
    const preencher = (id) => {
      const c = clientes.find((x) => x.id === id);
      if (!c) return;
      CN_TOMADOR.forEach(([k]) => { const el = raiz.querySelector('[data-cn-campo="tomador.' + k + '"]'); if (el) el.value = (c.tomador || {})[k] || ""; });
    };
    $("cn-e-cliente").addEventListener("change", (e) => preencher(e.target.value));
    $("cn-e-pagamento").addEventListener("change", (e) => {
      const p = pagamentos.find((x) => x.id === e.target.value);
      if (!p) return;
      $("cn-e-cliente").value = p.conta;
      preencher(p.conta);
      const val = raiz.querySelector('[data-cn-campo="valor"]');
      if (val) val.value = Number(p.valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 });
      const desc = raiz.querySelector('[data-cn-campo="descricao"]');
      if (desc) desc.value = p.tipo === "mensalidade" ? "Assinatura do PAULUS — plano mensal" : "Recarga de uso do PAULUS (nuvem)";
      const q = String(p.quando || "");
      const comp = raiz.querySelector('[data-cn-campo="competencia"]');
      if (comp && q.length >= 7) comp.value = q.slice(0, 7);
    });
  }, 0);
  await dialogo({ titulo: "Emitir NFS-e", contexto: "Notas do PAVLVS", html, larga: true, classe: "cn-dialogo",
    confirmar: "Emitir", aoConfirmar: enviar });
}

/* ------------------------------------------------------- clientes */

async function cnDialogoClientes() {
  let clientes;
  try { clientes = (await cnPedir("/api/casa-nfse/clientes")).clientes || []; } catch (err) {
    avisoCert(err.message, { tom: "erro" });
    return;
  }
  const linha = (c) => {
    const t = c.tomador || {};
    const falta = ["documento", "cep", "logradouro", "bairro", "cmun"].filter((k) => !t[k]);
    return '<div class="cn-cliente" data-conta="' + esc(c.id) + '"><div class="cn-cliente-linha"><span class="duas-linhas"><b>' + esc(c.nome) + "</b><small>" +
      esc([t.documento, t.email, c.plano, c.situacao].filter(Boolean).join(" · ")) +
      (falta.length ? ' · <span class="cn-aviso">falta ' + esc(falta.join(", ")) + "</span>" : "") + "</small></span>" +
      '<button type="button" data-cn-editar="' + esc(c.id) + '">Editar</button></div></div>';
  };
  const html = '<p class="dialogo-dica">Os assinantes vêm do cadastro da assinatura no paulus.ia.br. O que você editar aqui vale para as notas (dados fiscais); o cadastro original da conta fica como está.</p>' +
    (clientes.length ? '<div class="cn-clientes">' + clientes.map(linha).join("") + "</div>" : '<p class="dialogo-dica">Nenhum assinante ainda.</p>') +
    '<p class="cn-erro-dialogo" hidden></p>';
  setTimeout(() => {
    const raiz = $("veu-dialogo");
    if (!raiz) return;
    raiz.addEventListener("click", async (e) => {
      const ed = e.target.closest("[data-cn-editar]");
      const sv = e.target.closest("[data-cn-salvar]");
      if (ed) {
        const bloco = ed.closest(".cn-cliente");
        if (bloco.querySelector(".cn-form")) { bloco.querySelector(".cn-form").remove(); return; }
        const c = clientes.find((x) => x.id === ed.dataset.cnEditar);
        const f = document.createElement("div");
        f.className = "cn-form";
        f.innerHTML = cnCamposTomador(c.tomador || {}, "") + '<div class="cfg-botoes"><button type="button" class="primario" data-cn-salvar="' + esc(c.id) + '">Salvar</button></div>';
        bloco.appendChild(f);
      } else if (sv) {
        const bloco = sv.closest(".cn-cliente");
        cnErroNoDialogo("");
        try {
          const r = await cnPost("/api/casa-nfse/clientes/" + encodeURIComponent(sv.dataset.cnSalvar), { tomador: cnValores(bloco.querySelector(".cn-form")) });
          const i = clientes.findIndex((x) => x.id === sv.dataset.cnSalvar);
          if (i >= 0 && r.cliente) clientes[i] = Object.assign({}, clientes[i], r.cliente);
          bloco.outerHTML = linha(clientes[i]);
          avisoCert("dados do cliente salvos", { tom: "ok" });
        } catch (err) { cnErroNoDialogo(err.message); }
      }
    });
  }, 0);
  await dialogo({ titulo: "Clientes", contexto: "Notas do PAVLVS", html, larga: true, classe: "cn-dialogo", confirmar: "Fechar", semCancelar: true });
}

/* ----------------------------------------------------- parâmetros */

async function cnDialogoParametros() {
  const d = cn.dados;
  const p = (d.prestador || {}).dados || {};
  const o = (d.prestador || {}).opcoes || {};
  const end = p.endereco || {};
  const s = p.servico || {};
  const ib = p.ibscbs || {};
  const pct = (bp) => (bp ? Math.floor(bp / 100) + "," + String(bp % 100).padStart(2, "0") : "");
  const quando = o.quando_reter || {};
  const ret = p.retencoes || {};
  const retencoes = Object.entries(o.retencoes || {}).map(([k, rot]) =>
    cnDuas(cnEscolha("prestador.retencoes." + k + ".quando", rot + " — quando reter", quando, (ret[k] || {}).quando),
      k === "iss" ? "<span></span>" : cnCampo("prestador.retencoes." + k + ".aliquota_pct", rot + " — alíquota (%)", pct((ret[k] || {}).aliquota_bp)))).join("");
  const ponte = d.ponte || {};
  const html =
    "<h4 class=\"cn-sub\">O PAVLVS (prestador)</h4>" +
    cnDuas(cnCampo("prestador.documento", "CNPJ", p.documento), cnCampo("prestador.inscricao_municipal", "Inscrição municipal", p.inscricao_municipal)) +
    cnCampo("prestador.razao_social", "Razão social", p.razao_social) +
    cnDuas(cnCampo("prestador.municipio", "Município (código IBGE)", p.municipio, ' list="cn-municipios" data-cn-busca="1"'),
      cnCampo("prestador.endereco.cep", "CEP", end.cep)) +
    cnDuas(cnCampo("prestador.endereco.logradouro", "Rua", end.logradouro), cnCampo("prestador.endereco.numero", "Número", end.numero)) +
    cnDuas(cnCampo("prestador.endereco.complemento", "Complemento", end.complemento), cnCampo("prestador.endereco.bairro", "Bairro", end.bairro)) +
    cnDuas(cnCampo("prestador.email", "E-mail", p.email), cnCampo("prestador.telefone", "Telefone", p.telefone)) +
    '<datalist id="cn-municipios"></datalist>' +
    "<h4 class=\"cn-sub\">Tributação</h4>" +
    cnDuas(cnEscolha("prestador.opcao_simples", "Regime", { "1": "Lucro presumido ou real", "3": "Simples Nacional (ME/EPP)", "2": "MEI" }, p.opcao_simples),
      cnEscolha("prestador.regime_apuracao_sn", "Apuração no Simples", Object.assign({ "": "não se aplica" }, o.regime_apuracao_sn || {}), p.regime_apuracao_sn)) +
    cnDuas(cnCampo("prestador.servico.ctribnac", "Código de tributação nacional", s.ctribnac, ' placeholder="ex.: 010501 (licenciamento de software)"'),
      cnCampo("prestador.servico.nbs", "NBS", s.nbs)) +
    cnDuas(cnCampo("prestador.servico.aliquota_iss_pct", "Alíquota do ISS (%)", pct(s.aliquota_iss_bp)), cnCampo("prestador.servico.descricao", "Descrição padrão", s.descricao)) +
    cnDuas(cnCampo("prestador.ibscbs.cst", "IBS/CBS — CST", ib.cst), cnCampo("prestador.ibscbs.cclasstrib", "IBS/CBS — cClassTrib", ib.cclasstrib)) +
    cnCampo("prestador.ibscbs.cindop", "IBS/CBS — indicador da operação (cIndOp)", ib.cindop) +
    '<p class="dialogo-dica">O código do serviço, a NBS e a classificação do IBS/CBS do PAVLVS (programa de computador) são do contador: os da advocacia não servem aqui.</p>' +
    retencoes +
    "<h4 class=\"cn-sub\">Ponte com o painel (paulus.ia.br)</h4>" +
    cnCampo("token_ponte", ponte.configurada ? "Chave da ponte (gravada em " + cnData(ponte.gravado_em) + "; preencha só para trocar)" : "Chave da ponte (NFSE_CASA_TOKEN)", "", ' type="password"') +
    '<label class="dialogo-marcar"><input type="checkbox" data-cn-campo="enviar_sozinho"' + (d.enviar_sozinho ? " checked" : "") +
    "><span>Enviar a nota ao app do cliente assim que for emitida</span></label>" +
    '<label class="dialogo-marcar"><input type="checkbox" data-cn-campo="mandar_email"' + (d.mandar_email ? " checked" : "") +
    "><span>Mandar também por e-mail (PDF e XML anexos; precisa da RESEND_API_KEY no Worker)</span></label>" +
    "<h4 class=\"cn-sub\">Produção</h4>" +
    (d.producao_liberada
      ? '<p class="dialogo-dica">Em produção: as notas valem de verdade.</p><div class="cfg-botoes"><button type="button" data-cn-amb="voltar">Voltar para o ambiente de testes</button></div>'
      : '<p class="dialogo-dica">Em testes (produção restrita). Libera depois de ao menos uma nota emitida em testes.</p><div class="cfg-botoes"><button type="button" class="perigo" data-cn-amb="liberar">Mudar para produção</button></div>') +
    '<p class="cn-erro-dialogo" hidden></p>';
  setTimeout(() => {
    const raiz = $("veu-dialogo");
    if (!raiz) return;
    raiz.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-cn-amb]");
      if (!b) return;
      try {
        cn.dados = await cnPost("/api/casa-nfse/producao/" + b.dataset.cnAmb);
        dialogoAberto.fechar({ ok: true });
        avisoCert(cn.dados.producao_liberada ? "em produção: as notas valem de verdade" : "de volta ao ambiente de testes", { tom: "ok" });
        desenharCasaNfse();
      } catch (err) { cnErroNoDialogo(err.message); }
    });
  }, 0);
  const salvar = async () => {
    const v = cnValores($("veu-dialogo"));
    cnErroNoDialogo("");
    try {
      cn.dados = await cnPost("/api/casa-nfse/parametros", v);
      dialogoAberto.fechar({ ok: true });
      avisoCert("parâmetros gravados", { tom: "ok" });
      desenharCasaNfse();
    } catch (err) { cnErroNoDialogo(err.message); }
  };
  await dialogo({ titulo: "Parâmetros", contexto: "Notas do PAVLVS", html, larga: true, classe: "cn-dialogo", confirmar: "Gravar", aoConfirmar: salvar });
}

casaNfseDisponivel();

/* ----------------------------------------------- cancelar e substituir */

function cnMotivos(tipo) {
  const m = ((cn.dados || {}).motivos || {})[tipo] || {};
  const o = {};
  Object.entries(m).forEach(([k, v]) => { o[k] = k + " – " + v; });
  return o;
}

async function cnDialogoCancelar(id) {
  const n = ((cn.dados || {}).notas || []).find((x) => x.id === id);
  if (!n) return;
  const html = '<p class="dialogo-dica">NFS-e nº ' + esc(n.numero) + " · " + esc(n.cliente) + " · " + esc(n.valor) +
    (n.ambiente === "producao" ? "" : " · ambiente de testes") + ". O cancelamento vai ao Sistema Nacional e não se desfaz; " +
    "o município tem um prazo para cancelar. Depois do prazo, o caminho é Substituir.</p>" +
    cnEscolha("motivo", "Motivo (tabela oficial)", cnMotivos("cancelamento"), "1") +
    cnCampo("texto", "Descreva o motivo (15 a 255 caracteres)", "", ' maxlength="255"') +
    (n.enviada_em ? '<p class="dialogo-dica">O app do cliente é avisado de que a nota foi cancelada.</p>' : "") +
    '<p class="cn-erro-dialogo" hidden></p>';
  const fazer = async () => {
    const raiz = $("veu-dialogo");
    const v = cnValores(raiz);
    cnErroNoDialogo("");
    const ok = raiz.querySelector('[data-dialogo="confirmar"]');
    if (ok) { ok.disabled = true; ok.textContent = "Cancelando…"; }
    try {
      const r = await cnPost("/api/casa-nfse/notas/" + id + "/cancelar", v);
      dialogoAberto.fechar({ ok: true });
      avisoCert("NFS-e nº " + r.numero + " cancelada" + (r.aviso ? "; " + r.aviso : ""), { tom: "ok" });
      await carregarCasaNfse();
    } catch (err) {
      cnErroNoDialogo(err.message);
      if (ok) { ok.disabled = false; ok.textContent = "Cancelar a nota"; }
    }
  };
  await dialogo({ titulo: "Cancelar a NFS-e nº " + n.numero, contexto: "Notas do PAVLVS", html, classe: "cn-dialogo",
    confirmar: "Cancelar a nota", cancelar: "Voltar", perigo: true, aoConfirmar: fazer });
}

async function cnDialogoSubstituir(id) {
  const n = ((cn.dados || {}).notas || []).find((x) => x.id === id);
  if (!n) return;
  const valor = String(n.valor || "").replace(/[^0-9,]/g, "");
  const html = '<p class="dialogo-dica">Sai uma nota nova no lugar da nº ' + esc(n.numero) + ", e a Sefin cancela a antiga sozinha. " +
    "Corrija abaixo o que estava errado; o resto vem da nota original.</p>" +
    cnEscolha("motivo", "Motivo (tabela oficial)", cnMotivos("substituicao"), "01") +
    cnCampo("texto", "Descrição do motivo (15 a 255 caracteres; obrigatória no motivo 99)", "", ' maxlength="255"') +
    '<h4 class="cn-sub">Tomador</h4>' + cnCamposTomador(n.tomador || {}, "ajustes.tomador.") +
    '<h4 class="cn-sub">Serviço</h4>' +
    cnDuas(cnCampo("ajustes.valor", "Valor (R$)", valor), cnCampo("ajustes.competencia", "Competência", (n.competencia || "").slice(0, 7), ' type="month"')) +
    cnCampo("ajustes.descricao", "Descrição", n.descricao) +
    '<p class="dialogo-dica">No Simples Nacional, a substituta não pode mudar o tomador, o valor nem a competência (regra E0061).</p>' +
    '<p class="cn-erro-dialogo" hidden></p>';
  const fazer = async () => {
    const raiz = $("veu-dialogo");
    const v = cnValores(raiz);
    if (v.ajustes && v.ajustes.competencia) v.ajustes.competencia = v.ajustes.competencia + "-01";
    cnErroNoDialogo("");
    const ok = raiz.querySelector('[data-dialogo="confirmar"]');
    if (ok) { ok.disabled = true; ok.textContent = "Emitindo…"; }
    try {
      const r = await cnPost("/api/casa-nfse/notas/" + id + "/substituir", v);
      dialogoAberto.fechar({ ok: true });
      avisoCert("NFS-e nº " + r.numero + " emitida no lugar da nº " + n.numero + (r.aviso ? "; " + r.aviso : ""), { tom: "ok" });
      await carregarCasaNfse();
    } catch (err) {
      cnErroNoDialogo(err.message);
      if (ok) { ok.disabled = false; ok.textContent = "Emitir a substituta"; }
    }
  };
  await dialogo({ titulo: "Substituir a NFS-e nº " + n.numero, contexto: "Notas do PAVLVS", html, larga: true, classe: "cn-dialogo",
    confirmar: "Emitir a substituta", aoConfirmar: fazer });
}
