/* ------------------------------------------------------- notas fiscais */
/*
   A tela Notas fiscais (03/10/2026): um lugar no menu para as NFS-e, que
   antes ficavam espalhadas (a configuracao em Configuracoes › Nota fiscal, a
   lista dentro do Financeiro). Duas abas:

   - Emitidas: as notas que o escritorio emite para os clientes dele
     (/api/nfse/notas). Cada linha abre o mesmo cartao das outras portas
     (js/91-nfse-nota.js, abrirCartaoNota); PDF (DANFSe), XML, Cancelar e
     Substituir sao os botoes do cartao (data-nota-*), ligados la.
   - Recebidas: as que o PAVLVS emitiu para o escritorio pela assinatura
     (/api/nfse-recebidas, src/nfse_recebidas.py).

   As rotas de NFS-e so respondem na janela do escritorio
   (src/acesso/politicas.py): de fora, o destino abre a tela "Disponivel so
   no computador do escritorio" (DESTINOS_SO_NO_ESCRITORIO, js/42-acesso.js).
*/

const nf = { aba: "emitidas", mes: "", situacao: "", notas: null, recebidas: null, disp: null, erro: "" };

const NF_SITUACOES = [
  ["", "Todas"], ["emitida", "Emitidas"], ["andamento", "Em andamento"], ["rascunho", "Rascunhos"],
  ["cancelada", "Canceladas"], ["substituida", "Substituídas"], ["rejeitada", "Rejeitadas"],
];
const NF_ANDAMENTO = ["aguardando_aprovacao", "aprovada", "assinada", "enviando", "aguardando_confirmacao", "na_fila"];
const NF_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

async function mostrarNotasFiscais(aba) {
  if (aba) nf.aba = aba;
  abrirTela("Notas fiscais", { cheia: true });
  marcarDestino("notas");
  cabecalhoNotas();
  cascaNotas('<p class="nota">lendo…</p>');
  await carregarNotas();
  desenharNotas();
}

function cabecalhoNotas() {
  $("conversa-meta").textContent = nf.aba === "emitidas"
    ? "As NFS-e que o escritório emite para os clientes"
    : "As NFS-e que o PAVLVS emitiu para o escritório pela assinatura";
  const aba = (v, r) => '<button class="' + (v === nf.aba ? "ativa" : "") + '" data-nf-aba="' + v + '" role="tab" aria-selected="' +
    (v === nf.aba) + '"><span>' + r + "</span></button>";
  $("nav-tela").innerHTML = '<div class="visoes nf-abas" role="tablist">' + aba("emitidas", "Emitidas") + aba("recebidas", "Recebidas") + "</div>";
  $("acoes-tela").innerHTML = nf.aba === "emitidas" && nf.disp && nf.disp.pode_emitir
    ? '<button class="com-icone primario" data-nf-emitir="1">' + ic("add", 16) + "Emitir nota</button>" : "";
  document.querySelectorAll("[data-nf-aba]").forEach((b) => {
    b.onclick = async () => {
      nf.aba = b.dataset.nfAba;
      cabecalhoNotas();
      cascaNotas('<p class="nota">lendo…</p>');
      await carregarNotas();
      desenharNotas();
    };
  });
  const emitir = document.querySelector("[data-nf-emitir]");
  if (emitir) emitir.onclick = emitirNotaDaTela;
}

function cascaNotas(html) {
  $("centro").innerHTML = '<div class="acervo sem-painel nf-tela" id="nf-tela"><div class="acervo-principal sv-principal">' +
    '<div class="sv-medida">' + html + "</div></div></div>";
  atualizarPostura();
}

async function carregarNotas() {
  nf.erro = "";
  try {
    if (nf.aba === "emitidas") {
      const disp = typeof nfseEstaDisponivel === "function" ? nfseEstaDisponivel(true) : null;
      const r = await fetch("/api/nfse/notas" + (nf.mes ? "?mes=" + encodeURIComponent(nf.mes) : ""));
      nf.disp = await disp;
      nf.notas = r.ok ? (await r.json()).notas || [] : null;
      if (!r.ok) nf.erro = await erroDe(r);
    } else {
      const r = await fetch("/api/nfse-recebidas");
      nf.recebidas = r.ok ? (await r.json()).notas || [] : null;
      if (!r.ok) nf.erro = await erroDe(r);
    }
  } catch (err) {
    nf.erro = String(err.message || err);
  }
}

function desenharNotas() {
  if (!$("nf-tela")) return;
  cabecalhoNotas();
  cascaNotas(nf.aba === "emitidas" ? blocoEmitidas() : blocoRecebidas());
  ligarNotas();
}

/* "2026-10" ou "2026-10-01" -> "outubro de 2026". */
function competenciaPorExtenso(c) {
  const m = /^(\d{4})-(\d{2})/.exec(String(c || ""));
  if (!m) return c || "—";
  return (NF_MESES[Number(m[2]) - 1] || m[2]) + " de " + m[1];
}

function nfAmbiente(a) {
  return a === "producao" ? '<span class="nf-amb">produção</span>' : '<span class="nf-amb nf-amb-teste" title="Produção restrita: sem valor fiscal">testes</span>';
}

/* ------------------------------------------------------------- Emitidas */

function nfPassaFiltro(n) {
  if (n.estado === "descartada") return nf.situacao === "descartada";
  if (!nf.situacao) return true;
  if (nf.situacao === "andamento") return NF_ANDAMENTO.includes(n.estado);
  return n.estado === nf.situacao;
}

function nfClasseEstado(e) {
  if (e === "emitida") return " ok";
  if (e === "rejeitada" || e === "cancelada") return " ruim";
  if (e === "substituida" || e === "rascunho") return " neutro";
  return " andamento";
}

function blocoEmitidas() {
  const disp = nf.disp || {};
  if (nf.notas === null) return '<p class="pc-vazio">Não consegui ler as notas: ' + esc(nf.erro || "o servidor não respondeu") + ".</p>";
  const todas = nf.notas;
  // Sem a emissão configurada e sem nota nenhuma: o estado vazio que leva ao assistente.
  if (!disp.pode_emitir && !todas.length && !nf.mes) return estadoVazioEmitidas(disp);
  const aviso = disp.pode_emitir ? "" : '<div class="nf-aviso">' + ic("info", 16) + "<span>" +
    (disp.ligado ? "A emissão está ligada, mas ainda não dá para emitir: " + esc((disp.motivos || []).join("; ") || "falta configurar") + "."
      : "A emissão pelo PAULUS está desligada. As notas abaixo continuam aqui para consultar.") +
    '</span><button type="button" class="sv-ligacao" data-nf-configurar="1">Configurar a nota fiscal</button></div>';
  const lista = todas.filter(nfPassaFiltro);
  const opcoesSit = NF_SITUACOES.map(([v, r]) => '<option value="' + v + '"' + (v === nf.situacao ? " selected" : "") + ">" + r + "</option>").join("");
  const filtros = '<div class="nf-filtros">' +
    '<label>Competência <input type="month" id="nf-mes" value="' + esc(nf.mes) + '"></label>' +
    '<label>Situação <select id="nf-situacao">' + opcoesSit + "</select></label>" +
    (nf.mes || nf.situacao ? '<button type="button" class="pc-sublinhado" data-nf-limpar="1">Limpar filtros</button>' : "") + "</div>";
  const linhas = lista.map((n) => {
    const emitida = Boolean(n.xml_nfse);
    const r = n.rascunho || {};
    const cliente = n.tomador_nome || (r.tomador || {}).nome || "sem cliente";
    const acoes = (emitida ? '<button type="button" data-nota-danfse="' + n.id + '" title="Abrir o DANFSe">' + ic("picture_as_pdf", 15) + "PDF</button>" +
      '<button type="button" data-nf-xml="' + n.id + '" title="Baixar o XML">' + ic("code", 15) + "XML</button>" : "") +
      (n.estado === "emitida" ? '<button type="button" data-nota-cancelar="' + n.id + '">Cancelar</button>' +
        '<button type="button" data-nota-substituir="' + n.id + '">Substituir</button>' : "");
    return '<tr data-nf-linha="' + n.id + '">' +
      '<td class="nf-num">' + (n.numero_nfse ? esc(n.numero_nfse) : '<span class="pc-apagado">—</span>') + "</td>" +
      '<td class="nf-cliente"><button type="button" class="nf-abrir" data-nf-abrir="' + n.id + '">' + esc(cliente) + "</button></td>" +
      "<td>" + esc(competenciaPorExtenso(n.competencia || r.competencia)) + "</td>" +
      '<td class="nf-valor">' + esc(n.valor || "") + "</td>" +
      '<td><span class="nf-estado' + nfClasseEstado(n.estado) + '">' + esc(n.estado_rotulo || n.estado) + "</span></td>" +
      "<td>" + nfAmbiente(n.ambiente) + "</td>" +
      '<td class="nf-acoes">' + acoes + "</td></tr>";
  }).join("");
  const tabela = lista.length
    ? '<div class="nf-rolagem"><table class="nf-tabela"><thead><tr><th>Nº</th><th>Cliente</th><th>Competência</th><th>Valor</th><th>Situação</th><th>Ambiente</th><th></th></tr></thead><tbody>' +
      linhas + "</tbody></table></div>"
    : '<p class="sv-dica pc-sem">' + (todas.length ? "Nenhuma nota com esses filtros." : "Nenhuma nota" + (nf.mes ? " com competência neste mês." : " ainda.")) + "</p>";
  return aviso + '<section class="sv-secao nf-secao" aria-labelledby="nf-t-emitidas"><div class="sv-secao-cabeca">' +
    '<span class="sv-secao-titulo" id="nf-t-emitidas">' + ic("receipt_long", 16) + "Notas emitidas pelo escritório</span>" +
    '<span class="sv-secao-meta">' + esc(plural(lista.length, "nota")) + "</span>" +
    '<button type="button" class="sv-ligacao" data-nf-contador="1">' + ic("calendar_month", 15) + "Mês para o contador</button></div>" +
    filtros + tabela +
    '<p class="sv-dica">Clique no cliente para abrir o cartão da nota. Cancelar e substituir passam por Aprovações.</p></section>';
}

function estadoVazioEmitidas(disp) {
  const frase = disp.ligado
    ? "A emissão está ligada, mas ainda falta: " + esc((disp.motivos || []).join("; ") || "configurar") + "."
    : "A emissão de NFS-e pelo PAULUS está desligada.";
  return '<div class="nf-vazio">' + ic("receipt_long", 36) +
    "<h2>Nenhuma nota fiscal emitida por aqui</h2>" +
    "<p>" + frase + " O assistente de Configurações › Nota fiscal liga a emissão pelo Padrão Nacional com o certificado A1 do escritório, em cinco passos.</p>" +
    "<p>No município sem convênio com o Padrão Nacional, a nota é emitida no sistema da prefeitura e registrada no Financeiro.</p>" +
    '<div class="linha-form"><button class="primario" data-nf-configurar="1">Configurar a nota fiscal</button>' +
    '<button type="button" data-nf-financeiro="1">Abrir o Financeiro</button></div></div>';
}

async function emitirNotaDaTela() {
  await novaNotaFiscal({}, "manual");
  if (nf.aba === "emitidas" && $("nf-tela")) { await carregarNotas(); desenharNotas(); }
}

/* ------------------------------------------------------------ Recebidas */

function blocoRecebidas() {
  if (nf.recebidas === null) return '<p class="pc-vazio">Não consegui ler as notas recebidas: ' + esc(nf.erro || "o servidor não respondeu") + ".</p>";
  if (!nf.recebidas.length) {
    return '<div class="nf-vazio">' + ic("inbox", 36) + "<h2>Nenhuma nota recebida</h2>" +
      "<p>As NFS-e da assinatura do PAVLVS aparecem aqui quando o escritório tem a assinatura.</p></div>";
  }
  const linhas = nf.recebidas.map((n) => {
    const sit = n.cancelada ? '<span class="nf-estado ruim">Cancelada</span>' : n.substituida ? '<span class="nf-estado neutro">Substituída</span>'
      : '<span class="nf-estado ok">Emitida</span>';
    const base = "/api/nfse-recebidas/" + encodeURIComponent(n.id);
    return "<tr><td>" + esc(competenciaPorExtenso(n.competencia)) + '</td><td class="nf-num">' + esc(n.numero || "—") + "</td>" +
      '<td class="nf-valor">' + esc(reaisNf(n.valor)) + "</td><td>" + sit + "</td><td>" + nfAmbiente(n.ambiente) + "</td>" +
      '<td class="nf-acoes"><button type="button" data-nf-baixar="' + esc(base + "/pdf") + '">' + ic("download", 15) + "Download</button>" +
      '<button type="button" data-nf-baixar="' + esc(base + "/xml") + '">' + ic("code", 15) + "XML</button></td></tr>";
  }).join("");
  return '<section class="sv-secao nf-secao" aria-labelledby="nf-t-recebidas"><div class="sv-secao-cabeca">' +
    '<span class="sv-secao-titulo" id="nf-t-recebidas">' + ic("inbox", 16) + "Notas do PAVLVS para o escritório</span>" +
    '<span class="sv-secao-meta">' + esc(plural(nf.recebidas.length, "nota")) + "</span></div>" +
    '<div class="nf-rolagem"><table class="nf-tabela"><thead><tr><th>Competência</th><th>Nº</th><th>Valor</th><th>Situação</th><th>Ambiente</th><th></th></tr></thead><tbody>' +
    linhas + "</tbody></table></div>" +
    '<p class="sv-dica">A nota da assinatura é emitida pelo PAVLVS a cada cobrança; o PDF e o XML vêm de paulus.ia.br.</p></section>';
}

function reaisNf(v) {
  return "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function baixarNf(url) {
  const a = document.createElement("a");
  a.href = url;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

/* --------------------------------------------------------------- ligar */

function ligarNotas() {
  const tela = $("nf-tela");
  if (!tela) return;
  const mes = $("nf-mes");
  if (mes) mes.onchange = async () => { nf.mes = mes.value; await carregarNotas(); desenharNotas(); };
  const sit = $("nf-situacao");
  if (sit) sit.onchange = () => { nf.situacao = sit.value; desenharNotas(); };
  tela.onclick = async (e) => {
    const b = (s) => e.target.closest(s);
    if (b("[data-nf-limpar]")) { nf.mes = ""; nf.situacao = ""; await carregarNotas(); desenharNotas(); return; }
    if (b("[data-nf-configurar]")) { marcarDestino("config"); mostrarConfig("nfse"); return; }
    if (b("[data-nf-financeiro]")) { abrirDestino("financeiro"); return; }
    if (b("[data-nf-contador]")) { abrirRelatorioNfse(nf.mes || undefined); return; }
    const x = b("[data-nf-xml]");
    if (x) { baixarNf("/api/nfse/notas/" + x.dataset.nfXml + "/xml"); return; }
    const d = b("[data-nf-baixar]");
    if (d) { baixarNf(d.dataset.nfBaixar); return; }
    const a = b("[data-nf-abrir]");
    if (a) {
      await abrirNotaFiscal(Number(a.dataset.nfAbrir));
      if ($("nf-tela")) { await carregarNotas(); desenharNotas(); }
    }
  };
}
