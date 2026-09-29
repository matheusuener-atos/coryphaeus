/* ----------------------------------------------------------- o vinculo */
/*
   O PAULUS do servidor vinculado a conta Google de quem o administra
   (src/vinculo.py, E5). Vinculado, ele abre TRAVADO: esta tela cobre tudo e
   pede "Entrar com Google" (e o codigo do celular, se a conta de titular dessa
   pessoa tem o autenticador). "Manter aberto neste computador" desliga a
   trava. A trava e do servidor: travado, toda outra rota responde 423 - por
   isso a tela recarrega a pagina quando destrava.

   O mesmo login serve ao passo "Conta Google" do assistente de configuracao
   (js/23-boas-vindas.js) e ao cartao em Configuracoes › Escritorio e equipe.
*/

const vinc = { estado: null, relogio: null, aoMudar: null };

async function lerVinculoGoogle() {
  try {
    const r = await fetch("/api/vinculo");
    vinc.estado = r.ok ? await r.json() : null;
  } catch (err) { vinc.estado = null; }
  return vinc.estado;
}

async function postVinculo(url, corpo) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || "não deu certo");
  vinc.estado = d;
  return d;
}

/* Vai ao Google (o navegador abre) e acompanha ate voltar. `aoMudar` e quem
   redesenha (a trava, o passo do assistente, o cartao de Configuracoes). */
async function entrarNoGoogleDoVinculo(finalidade, aoMudar, servicos) {
  vinc.aoMudar = aoMudar;
  await postVinculo("/api/vinculo/entrar", { finalidade, servicos: Boolean(servicos) });
  aoMudar && aoMudar();
  clearInterval(vinc.relogio);
  vinc.relogio = setInterval(async () => {
    const e = await lerVinculoGoogle();
    if (!e || ["pronto", "erro", "cancelado"].includes(e.fase)) clearInterval(vinc.relogio);
    vinc.aoMudar && vinc.aoMudar();
  }, 1000);
}

/* ------------------------------------------------------------ a trava */

const G_DO_GOOGLE = '<svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>';

function telaDaTrava() {
  let el = document.getElementById("trava");
  if (!el) {
    el = document.createElement("div");
    el.id = "trava";
    el.className = "trava";
    document.body.appendChild(el);
  }
  return el;
}

function desenharTrava() {
  const e = vinc.estado || {};
  if (!e.travado) {
    const el = document.getElementById("trava");
    if (el) {
      el.remove();
      // Destravou: a pagina volta a ler tudo o que o servidor recusava.
      location.reload();
    }
    return;
  }
  const esperando = e.fase === "aguardando" || e.fase === "trocando" || e.fase === "testando";
  const direita = e.precisa_codigo
    ? '<form class="trava-form" id="trava-codigo"><div class="trava-quem"><span>' + esc(e.email) + "</span></div>" +
      '<label class="trava-campo"><span class="trava-etiqueta">CÓDIGO DO CELULAR</span>' +
      '<input id="trava-codigo-campo" inputmode="numeric" autocomplete="one-time-code" maxlength="9" placeholder="000000"></label>' +
      '<p class="trava-erro" id="trava-erro"></p><button type="submit" class="trava-principal">Abrir o PAVLVS</button></form>'
    : '<div class="trava-form"><span class="trava-etiqueta">CONTA GOOGLE DESTE PAVLVS</span>' +
      '<button type="button" class="trava-google" id="trava-google"' + (esperando ? " disabled" : "") + ">" + G_DO_GOOGLE +
      (esperando ? "Esperando o Google no navegador…" : "Entrar com Google") + "</button>" +
      (esperando ? '<button type="button" class="trava-link" id="trava-cancelar">Cancelar</button>' : "") +
      '<p class="trava-erro" id="trava-erro">' + esc(e.fase === "erro" ? e.mensagem : "") + "</p>" +
      '<label class="trava-manter"><input type="checkbox" id="trava-manter">Manter aberto neste computador</label>' +
      '<p class="trava-ajuda">Vinculado a <b>' + esc(e.email) + "</b>. Entre com essa conta. Com “manter aberto”, o PAVLVS deixa de pedir o Google ao abrir neste computador (dá para travar de novo em Configurações).</p></div>";
  telaDaTrava().innerHTML =
    '<header class="trava-topo"><span class="trava-marca">PAVLVS</span><span class="trava-selo">' + ic("desktop_windows", 15) + "servidor do escritório</span></header>" +
    '<main class="trava-corpo"><section class="trava-texto"><span class="trava-rotulo"><i></i>' + (e.precisa_codigo ? "PASSO 2 DE 2" : "ESCRITÓRIO TRAVADO") + "</span>" +
    "<h1>" + (e.precisa_codigo ? "Confirme que é você" : "Entre para abrir o escritório") + "</h1>" +
    "<p>" + (e.precisa_codigo ? "Digite o código de 6 dígitos que aparece no app autenticador do seu celular."
      : "Este PAVLVS é vinculado à conta Google de quem o administra. Os documentos e as contas ficam aqui; o Google só confirma que é você.") + "</p>" +
    '<span class="trava-nota">' + (e.precisa_codigo ? "O código muda a cada 30 segundos." : "Nada dos seus documentos vai para o Google.") + "</span></section>" +
    '<section class="trava-painel">' + direita + "</section></main>";
  ligarTrava();
}

function ligarTrava() {
  const b = document.getElementById("trava-google");
  if (b) b.onclick = async () => {
    const manter = document.getElementById("trava-manter");
    vinc.manterAoEntrar = Boolean(manter && manter.checked);
    try { await entrarNoGoogleDoVinculo("destravar", aoMudarNaTrava); }
    catch (err) { const p = document.getElementById("trava-erro"); if (p) p.textContent = err.message; }
  };
  const c = document.getElementById("trava-cancelar");
  if (c) c.onclick = async () => { await postVinculo("/api/vinculo/cancelar").catch(() => {}); desenharTrava(); };
  const f = document.getElementById("trava-codigo");
  if (f) {
    const campo = document.getElementById("trava-codigo-campo");
    campo.focus();
    f.onsubmit = async (ev) => {
      ev.preventDefault();
      try {
        await postVinculo("/api/vinculo/codigo", { codigo: campo.value.trim() });
        await aoDestravar();
      } catch (err) { document.getElementById("trava-erro").textContent = err.message; campo.select(); }
    };
  }
}

async function aoMudarNaTrava() {
  const e = vinc.estado || {};
  if (!e.travado) { await aoDestravar(); return; }
  desenharTrava();
}

async function aoDestravar() {
  // "Manter aberto" marcado na trava: vale a partir de agora.
  if (vinc.manterAoEntrar) { await postVinculo("/api/vinculo/manter-aberto", { ligado: true }).catch(() => {}); }
  desenharTrava();
}

/* O servidor recusou por estar travado (423): a trava aparece, venha de onde vier. */
async function mostrarTrava() {
  await lerVinculoGoogle();
  if (vinc.estado && vinc.estado.travado && !document.getElementById("trava")) desenharTrava();
}

acessoDeFora.pronto.then(async () => {
  if (!acessoDeFora.local) return;
  const e = await lerVinculoGoogle();
  if (e && e.travado) desenharTrava();
});

/* ----------------------------------------- o cartao de Configuracoes */

function cartaoDoVinculo() {
  const e = vinc.estado;
  if (!e) return "";
  const esperando = e.fase === "aguardando" || e.fase === "trocando" || e.fase === "testando";
  if (!e.vinculado) {
    return cartaoCfg("Conta Google deste PAULUS", metaCfg("não vinculado"),
      '<p class="cfg-texto">Vincule este PAULUS à sua conta Google: ele passa a abrir travado e pede o Google a cada abertura (dá para manter aberto neste computador). O vínculo é exigido para ligar o acesso de fora e convidar a equipe.</p>' +
      (e.fase === "erro" ? '<p class="acesso-erro">' + esc(e.mensagem) + "</p>" : "") +
      '<div class="acesso-pe"><button class="primario com-icone" data-vinc-vincular="1"' + (esperando || !e.google ? " disabled" : "") + ">" +
      (esperando ? "Esperando o Google no navegador…" : "Vincular com Google") + "</button>" +
      (esperando ? '<button data-vinc-cancelar="1">Cancelar</button>' : "") +
      (!e.google ? '<p class="cfg-explica">Esta versão do PAULUS não traz o login do Google.</p>' : "") + "</div>");
  }
  const quando = e.vinculado_em ? new Date(e.vinculado_em).toLocaleDateString("pt-BR") : "";
  return cartaoCfg("Conta Google deste PAULUS", pontoCfg("vinculado", "ok"),
    '<div class="cfg-linhas">' + chaveCfg("Conta", e.email) + (e.nome ? chaveCfg("Nome", e.nome) : "") + (quando ? chaveCfg("Desde", quando) : "") + "</div>" +
    '<div class="acesso-energia">' +
    ligaCfg("", "Manter aberto neste computador", e.manter_aberto
      ? "o PAULUS abre sem pedir o Google neste computador"
      : "o PAULUS abre travado e pede o Google a cada abertura", e.manter_aberto, false)
      .replace('class="ag-toggle', 'data-vinc-manter="1" class="ag-toggle') + "</div>" +
    '<div class="acesso-pe"><button class="com-icone" data-vinc-travar="1">' + ic("logout", 16) + "Travar agora</button>" +
    '<button class="perigo" data-vinc-desvincular="1">Desvincular</button>' +
    '<p class="cfg-explica">Desvincular não apaga nada: o PAULUS só deixa de pedir o Google ao abrir.</p></div>');
}

function ligarVinculoCfg() {
  const redesenhar = () => { if (typeof desenharConfig === "function") desenharConfig(); };
  const clique = (sel, fn) => document.querySelectorAll(sel).forEach((b) => { b.onclick = (ev) => { ev.stopPropagation(); fn(b); }; });
  clique("[data-vinc-vincular]", async () => {
    try { await entrarNoGoogleDoVinculo("vincular", redesenhar); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
  });
  clique("[data-vinc-cancelar]", async () => { await postVinculo("/api/vinculo/cancelar").catch(() => {}); redesenhar(); });
  clique("[data-vinc-manter]", async (b) => {
    try { await postVinculo("/api/vinculo/manter-aberto", { ligado: !b.classList.contains("on") }); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-vinc-travar]", async () => {
    await postVinculo("/api/vinculo/travar").catch(() => {});
    desenharTrava();
  });
  clique("[data-vinc-desvincular]", async () => {
    if (!(await confirmar({ titulo: "Desvincular a conta Google?", contexto: "Configurações › Escritório e equipe",
      texto: "O PAULUS deixa de pedir o Google ao abrir. Para ligar o acesso de fora e convidar a equipe, vai ser preciso vincular de novo.",
      confirmar: "Desvincular", perigo: true }))) return;
    try { await postVinculo("/api/vinculo/desvincular"); avisoCert("desvinculado", { tom: "ok" }); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
}
