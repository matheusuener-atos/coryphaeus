/* ------------------------------------------ O cartão da nota fiscal (N2) */
/*
   O mesmo cartão para as quatro portas (Financeiro, Serviço, conversa,
   recorrência): o tomador (o que falta, pedido), descrição, competência,
   valor, serviço; a conta linha a linha, com a regra de cada uma; os erros
   (bloqueiam) e os avisos (não bloqueiam). Toda edição refaz a conta e
   confere a DPS no XSD oficial, no servidor (src/nfse/notas.py).
*/

const NOTA_CAMPOS_TOMADOR = [
  ["nome", "Nome ou razão social"], ["documento", "CPF ou CNPJ"], ["logradouro", "Logradouro"], ["numero", "Número"],
  ["complemento", "Complemento"], ["bairro", "Bairro"], ["cep", "CEP"], ["cmun", "Município (código IBGE)"],
  ["inscricao_municipal", "Inscrição municipal"], ["email", "E-mail para a nota"],
];

function centavosTexto(c) {
  const n = Number(c || 0);
  const sinal = n < 0 ? "−" : "";
  const a = Math.abs(n);
  return sinal + "R$ " + Math.floor(a / 100).toLocaleString("pt-BR") + "," + String(a % 100).padStart(2, "0");
}

function semRs(c) {
  return c ? centavosTexto(c).replace("R$ ", "") : "";
}

function campoNota(caminho, rotulo, valor, extra) {
  return '<div class="dialogo-campo"><label>' + esc(rotulo) + '</label><div class="dialogo-caixa"><input type="text" data-nota-campo="' + caminho +
    '" value="' + esc(valor == null ? "" : String(valor)) + '"' + (extra || "") + "></div></div>";
}

function htmlDoCartaoNota(n) {
  const r = n.rascunho || {};
  const t = r.tomador || {};
  const ro = n.editavel ? "" : " readonly";
  const tomador = NOTA_CAMPOS_TOMADOR.map(([k, rot]) => campoNota("tomador." + k, rot, t[k], ro));
  const pares = [];
  for (let i = 0; i < tomador.length; i += 2) pares.push('<div class="dialogo-duas">' + tomador[i] + (tomador[i + 1] || "") + "</div>");
  const linhas = ((n.conta && n.conta.linhas) || []).map((l) => '<tr class="nota-' + esc(l.tipo) + '"><td>' + esc(l.rotulo) + "</td><td>" +
    (l.tipo === "info" ? "" : esc(centavosTexto(l.centavos))) + '</td><td class="nota-regra">' + esc(l.regra) + "</td></tr>").join("");
  const lista = (itens) => (itens || []).map((e) => "<li>" + esc(e) + "</li>").join("");
  const erros = lista(n.erros);
  const avisos = lista(n.avisos);
  const passos = (n.passos || []).map((p) => "<li>" + esc((p.quando || "").slice(0, 16).replace("T", " ")) + " · " +
    esc(p.para || "") + (p.detalhe ? " — " + esc(p.detalhe) : "") + "</li>").join("");
  const rejeicao = (n.rejeicao || []).map((x) => "<li><b>" + esc(x.codigo || "") + "</b> " + esc(x.frase || x.descricao || "") + "</li>").join("");
  return '<div class="nota-cartao" data-nota-id="' + n.id + '">' +
    '<p class="nota-estado"><b>' + esc(n.estado_rotulo || "") + "</b> · " +
    esc(n.ambiente === "producao" ? "produção" : "produção restrita (sem valor fiscal)") +
    (n.numero_nfse ? " · NFS-e nº " + esc(n.numero_nfse) : "") + (n.chave ? " · chave " + esc(n.chave) : "") + "</p>" +
    (rejeicao ? '<div class="nota-erros"><b>A Sefin recusou:</b><ul>' + rejeicao + "</ul></div>" : "") +
    htmlDaNotaEmitida(n) +
    (erros ? '<div class="nota-erros"><b>Para enviar, falta resolver:</b><ul>' + erros + "</ul></div>" : "") +
    (avisos ? '<div class="nota-avisos"><b>Avisos</b><ul>' + avisos + "</ul></div>" : "") +
    "<h3>Tomador</h3>" + pares.join("") +
    "<h3>Serviço</h3>" +
    '<div class="dialogo-duas">' + campoNota("valor", "Valor (R$)", semRs(r.valor_centavos), ro) +
    campoNota("competencia", "Competência (início do serviço)", r.competencia, ' placeholder="AAAA-MM-DD"' + ro) + "</div>" +
    campoNota("descricao", "Descrição", r.descricao, ro) +
    '<div class="dialogo-duas">' + campoNota("municipio_incidencia", "Município da prestação (IBGE)", r.municipio_incidencia, ' placeholder="o do escritório"' + ro) +
    campoNota("desconto", "Desconto incondicionado (R$)", semRs(r.desconto_incond_centavos), ro) + "</div>" +
    campoNota("informacoes", "Informações complementares", r.informacoes, ro) +
    "<h3>A conta</h3>" +
    '<div class="nota-conta-rolagem"><table class="nota-conta"><tbody>' + linhas + "</tbody></table></div>" +
    '<p class="cfg-explica">A Sefin calcula o ISS próprio, o IBS e a CBS na hora de emitir: o que está como previsão pode mudar, e a nota emitida mostra os valores dela.</p>' +
    '<details class="nota-dps" data-nota-dps="' + n.id + '"><summary>Ver a DPS (XML)</summary><pre>carregando…</pre></details>' +
    (passos ? '<details class="nota-passos"><summary>Passos da nota</summary><ul>' + passos + "</ul></details>" : "") +
    "</div>";
}

function dadosDoCartaoNota() {
  const dados = { tomador: {} };
  document.querySelectorAll(".nota-cartao [data-nota-campo]").forEach((el) => {
    const c = el.dataset.notaCampo;
    if (c.startsWith("tomador.")) dados.tomador[c.slice(8)] = el.value;
    else dados[c] = el.value;
  });
  return dados;
}

async function gravarCartaoNota(id) {
  const r = await fetch("/api/nfse/notas/" + id, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dados: dadosDoCartaoNota() }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  return r.json();
}

async function abrirCartaoNota(nota) {
  let n = nota;
  const conferir = async () => {
    const novo = await gravarCartaoNota(n.id);
    if (!novo) return;
    n = novo;
    const alvo = document.querySelector(".nota-cartao");
    if (alvo) alvo.outerHTML = htmlDoCartaoNota(n);
    const falta = n.erros && n.erros.length;
    avisoCert(falta ? "conferido: ainda há o que resolver" : "conferido: a nota está pronta para pedir aprovação", { tom: falta ? "info" : "ok" });
  };
  const nome = n.rascunho && n.rascunho.tomador && n.rascunho.tomador.nome;
  // A segunda ação depende de onde a nota está: pedir aprovação (rascunho),
  // mandar agora (aprovada que não saiu) ou atualizar a situação (emitida).
  const mandar = ["aprovada", "assinada", "na_fila", "aguardando_confirmacao"].includes(n.estado);
  let segundo = null;
  if (n.editavel) segundo = { rotulo: "Pedir aprovação" };
  else if (mandar) segundo = { rotulo: n.estado === "aprovada" ? "Mandar agora" : "Consultar e mandar" };
  else if (n.estado === "emitida") segundo = { rotulo: "Atualizar situação" };
  const escolha = await dialogo({
    titulo: "Nota fiscal" + (nome ? " — " + nome : "") + (n.centavos ? " — " + n.valor : ""),
    contexto: "NFS-e · " + (n.estado_rotulo || ""), larga: true, classe: "dialogo-nota",
    html: htmlDoCartaoNota(n),
    confirmar: n.editavel ? "Conferir" : "Fechar", aoConfirmar: n.editavel ? conferir : undefined, cancelar: "Fechar",
    segundo: segundo,
    rodape: n.editavel ? '<button type="button" class="perigo" data-nota-descartar="' + n.id + '">Descartar</button>' : "",
  });
  if (escolha && escolha.segundo) {
    if (n.editavel) {
      // O que foi editado e não conferido vai junto: grava antes de pedir.
      const gravada = await gravarCartaoNota(n.id);
      if (gravada) await pedirAprovacaoDaNota(gravada);
    } else if (mandar) {
      await acaoDaNota(n.id, "enviar", "mandando ao Sistema Nacional…");
    } else if (n.estado === "emitida") {
      await acaoDaNota(n.id, "consultar", "perguntando ao Sistema Nacional…");
    }
  }
  return n;
}

async function novaNotaFiscal(dados, origem) {
  const r = await fetch("/api/nfse/notas", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origem: origem || "manual", dados: dados || {} }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  return abrirCartaoNota(await r.json());
}

async function abrirNotaFiscal(id) {
  const r = await fetch("/api/nfse/notas/" + id);
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  return abrirCartaoNota(await r.json());
}

document.addEventListener("toggle", async (e) => {
  const d = e.target;
  if (!d.matches || !d.matches("[data-nota-dps]") || !d.open) return;
  const pre = d.querySelector("pre");
  const r = await fetch("/api/nfse/notas/" + d.dataset.notaDps + "/dps").catch(() => null);
  if (!r || !r.ok) { pre.textContent = r ? await erroDe(r) : "não consegui montar a DPS"; return; }
  const x = await r.json();
  pre.textContent = (x.previa ? "Prévia: o número definitivo é reservado ao assinar.\n\n" : "") + x.xml.split("><").join(">\n<");
}, true);

document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-nota-descartar]");
  if (!b) return;
  const r = await fetch("/api/nfse/notas/" + b.dataset.notaDescartar + "/descartar", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  avisoCert("nota descartada", { tom: "ok" });
  if (dialogoAberto) dialogoAberto.fechar(null);
});

/* ------------------------------------------ Aprovação e envio (N4) */

async function pedirAprovacaoDaNota(nota) {
  if (nota.erros && nota.erros.length) {
    avisoCert("antes de pedir a aprovação, falta: " + nota.erros.slice(0, 2).join("; "), { tom: "erro" });
    return abrirCartaoNota(nota);
  }
  const r = await fetch("/api/nfse/notas/" + nota.id + "/pedir-aprovacao", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  const n = await r.json();
  avisoCert("pedido em Aprovações: a nota sai depois do sim", { tom: "ok",
    acao: { rotulo: "Abrir Aprovações", fazer: () => abrirDestino("aprovacoes") } });
  return n;
}

async function acaoDaNota(id, acao, aviso) {
  avisoCert(aviso, { tom: "info" });
  const r = await fetch("/api/nfse/notas/" + id + "/" + acao, { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  const n = await r.json();
  const tom = n.estado === "emitida" ? "ok" : (n.estado === "rejeitada" ? "erro" : "info");
  avisoCert("nota " + (n.estado_rotulo || "").toLowerCase() + (n.numero_nfse ? " · NFS-e nº " + n.numero_nfse : ""), { tom: tom });
  return abrirCartaoNota(n);
}

/* As portas (Financeiro, Serviço) perguntam uma vez se a emissão está à mão. */
let nfseDisponivel = null;
async function nfseEstaDisponivel(recarregar) {
  if (nfseDisponivel && !recarregar) return nfseDisponivel;
  try {
    const r = await fetch("/api/nfse/disponivel");
    nfseDisponivel = r.ok ? await r.json() : { ligado: false, pode_emitir: false };
  } catch (err) { nfseDisponivel = { ligado: false, pode_emitir: false }; }
  return nfseDisponivel;
}

// Na janela do escritório, as portas já sabem ao abrir se a emissão está à mão.
nfseEstaDisponivel();

/* ------------------------------------- A nota emitida: DANFSe, cancelar, substituir (N5) */

function htmlDaNotaEmitida(n) {
  const partes = [];
  if (n.substitui) partes.push("Substitui a NFS-e nº " + esc(n.substitui.numero_nfse || "") + ".");
  if (n.substituida_por) partes.push("Substituída pela NFS-e nº " + esc(n.substituida_por.numero_nfse || "(ainda não emitida)") + ".");
  const eventos = (n.eventos || []).map((e) => "<li>" + esc(e.tipo === "101101" ? "Cancelamento" : e.tipo) + " · " + esc(e.estado) +
    (e.ultimo_erro ? " — " + esc(e.ultimo_erro) : "") + "</li>").join("");
  if (!["emitida", "cancelada", "substituida"].includes(n.estado) && !partes.length) return "";
  const prazo = n.prazo_cancelamento ? '<p class="cfg-explica">' + esc(n.prazo_cancelamento.frase) + "</p>" : "";
  const botoes = n.estado === "emitida"
    ? '<div class="word-acoes"><button type="button" data-nota-danfse="' + n.id + '">' + ic("picture_as_pdf", 16) + "Abrir o DANFSe</button>" +
      '<button type="button" data-nota-cancelar="' + n.id + '">Cancelar a nota</button>' +
      '<button type="button" data-nota-substituir="' + n.id + '">Substituir</button></div>'
    : (n.xml_nfse ? '<div class="word-acoes"><button type="button" data-nota-danfse="' + n.id + '">' + ic("picture_as_pdf", 16) + "Abrir o DANFSe</button></div>" : "");
  return '<div class="nota-emitida">' + (partes.length ? "<p>" + partes.join(" ") + "</p>" : "") + prazo + botoes +
    (eventos ? '<details class="nota-passos"><summary>Eventos</summary><ul>' + eventos + "</ul></details>" : "") + "</div>";
}

async function perguntarMotivo(titulo, motivos, explica, textoObrigatorio) {
  const opcoes = Object.entries(motivos || {}).map(([k, v]) => '<option value="' + esc(k) + '">' + esc(k + " – " + v) + "</option>").join("");
  const r = await dialogo({
    titulo: titulo, contexto: "Nota fiscal", larga: true,
    html: '<div class="dialogo-campo"><label>Motivo (tabela oficial)</label><div class="dialogo-caixa"><select data-dialogo-chave="motivo">' + opcoes + "</select></div></div>" +
      (explica ? '<p class="cfg-explica">' + esc(explica) + "</p>" : ""),
    campos: [{ chave: "texto", rotulo: "Descreva o motivo (15 a 255 caracteres)", obrigatorio: Boolean(textoObrigatorio), max: 255 }],
    confirmar: "Continuar",
  });
  if (!r || !r.ok) return null;
  return { motivo: (r.valores || {}).motivo, texto: (r.valores || {}).texto || r.valor || "" };
}

document.addEventListener("click", async (e) => {
  const danfse = e.target.closest("[data-nota-danfse]");
  if (danfse) { window.open("/api/nfse/notas/" + danfse.dataset.notaDanfse + "/danfse", "_blank"); return; }
  const cancelar = e.target.closest("[data-nota-cancelar]");
  const substituir = e.target.closest("[data-nota-substituir]");
  if (!cancelar && !substituir) return;
  const id = (cancelar || substituir).dataset.notaCancelar || (cancelar || substituir).dataset.notaSubstituir;
  const r0 = await fetch("/api/nfse/notas/" + id);
  if (!r0.ok) return;
  const n = await r0.json();
  if (cancelar) {
    const m = await perguntarMotivo("Cancelar a NFS-e nº " + n.numero_nfse, n.motivos_cancelamento,
      (n.prazo_cancelamento || {}).frase + " O pedido vai para Aprovações; depois do sim, o cancelamento é registrado no Sistema Nacional.", true);
    if (!m) return;
    const r = await fetch("/api/nfse/notas/" + id + "/cancelar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(m) });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    avisoCert("pedido de cancelamento em Aprovações", { tom: "ok", acao: { rotulo: "Abrir Aprovações", fazer: () => abrirDestino("aprovacoes") } });
    return;
  }
  const m = await perguntarMotivo("Substituir a NFS-e nº " + n.numero_nfse, n.motivos_substituicao,
    "Cria uma nota nova (rascunho) que substitui esta; emitida, a Sefin cancela esta por substituição. No Simples Nacional, tomador, competência e valor não mudam.", false);
  if (!m) return;
  const r = await fetch("/api/nfse/notas/" + id + "/substituir", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(m) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  abrirCartaoNota(await r.json());
});
