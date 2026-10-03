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
  // O desenho "Servidor - Entrar" (02/10/2026): a coluna de 360 px no meio,
  // como a tela de entrar de fora (frontend/entrar.html) - a conta deste
  // servidor, manter aberto, o Google no trilho e, embaixo, o que continua
  // funcionando enquanto a janela esta travada. O codigo e a chave seguem o
  // mesmo desenho ("Codigo" e "Chave de recuperacao").
  const esperando = e.fase === "aguardando" || e.fase === "trocando" || e.fase === "testando";
  const fora = e.acesso_de_fora || {};
  const foraNoAr = Boolean(fora.ligado && fora.hostname);
  const recuperacao = Boolean(vinc.porRecuperacao);
  const semNet = Boolean(vinc.semInternet) && !e.precisa_codigo;
  const codigo = e.precisa_codigo || semNet;
  const pronto = Boolean((e.sem_internet || {}).pronto);
  const conta = (rotulo, trocar) => '<div class="trava-grupo"><span class="trava-etiqueta">' + rotulo + "</span>" +
    '<div class="trava-caixa">' + (semNet ? ic("desktop_windows", 16) : G_DO_GOOGLE) + '<span class="trava-email">' + esc(e.email) + "</span>" +
    (trocar ? '<button type="button" class="trava-trocar" id="trava-trocar">' + esc(trocar) + "</button>" : "") + "</div></div>";
  const trilho = (id, texto, google, desligado) => '<button type="' + (google ? "button" : "submit") + '" class="trava-trilho" id="' + id + '"' +
    (desligado ? " disabled" : "") + '><span class="trava-pastilha">' + (google ? G_DO_GOOGLE : "") + esc(texto) + "</span></button>";
  let frase, corpo, tela;
  if (codigo) {
    tela = recuperacao ? "chave" : semNet ? "trava_sem_internet" : "trava_codigo";
    frase = recuperacao ? "Use uma das chaves de recuperação que você guardou. Cada uma vale uma vez." : semNet
      ? "Sem internet, o código do celular abre o PAULUS neste computador." : "Falta confirmar que é você: digite o código do Google Authenticator.";
    const n = recuperacao ? 0 : 6;
    corpo = '<form class="trava-form" id="trava-codigo">' +
      conta("CONTA", recuperacao ? "" : (semNet ? "Entrar com o Google" : "Trocar")) +
      '<div class="trava-grupo"><div class="trava-rotulo-linha"><span class="trava-etiqueta">' + (recuperacao ? "CHAVE DE RECUPERAÇÃO" : "GOOGLE AUTHENTICATOR") +
      '</span><span class="trava-renova" id="trava-renova">' + (recuperacao ? "uso único" : "renova em <b>00:30</b>") + "</span></div>" +
      '<div class="trava-casas' + (recuperacao ? " campo" : "") + '" id="trava-casas" style="--n:' + (n || 6) + '">' +
      '<input id="trava-codigo-campo"' + (recuperacao ? ' autocomplete="off" maxlength="9" aria-label="Chave de recuperação"'
        : ' inputmode="numeric" autocomplete="one-time-code" maxlength="6" aria-label="Código de 6 dígitos"') + "></div>" +
      (recuperacao ? '<span class="trava-ajuda">Cada chave vale uma vez.</span>' : "") + "</div>" +
      '<p class="trava-erro" id="trava-erro"></p>' +
      trilho("trava-abrir", "Abrir o PAVLVS", false, false) +
      '<button type="button" class="trava-link" id="trava-recuperacao">' + (recuperacao ? "Usar o Google Authenticator" : "Não tenho o celular") + "</button></form>";
  } else {
    tela = "trava";
    frase = "Entre com a sua conta para abrir o escritório.";
    corpo = '<div class="trava-form">' + conta("CONTA DESTE SERVIDOR", "") +
      '<label class="trava-manter"><input type="checkbox" id="trava-manter"' + (vinc.manterAoEntrar ? " checked" : "") + '><i aria-hidden="true">' +
      ic("check", 13) + "</i><span>Manter aberto neste computador</span></label>" +
      trilho("trava-google", esperando ? "Esperando o Google…" : "Entrar com Google", true, esperando) +
      (esperando ? '<button type="button" class="trava-link" id="trava-cancelar">Cancelar</button>' : "") +
      '<p class="trava-erro" id="trava-erro">' + esc(e.fase === "erro" ? e.mensagem : "") + "</p>" +
      '<div class="trava-grupo trava-enquanto"><span class="trava-etiqueta">ENQUANTO ISSO</span>' +
      '<div class="trava-fora"><span class="trava-estado' + (foraNoAr ? " ok" : "") + '"><i></i>' +
      (foraNoAr ? "Acesso de fora funcionando" : "Acesso de fora desligado") + "</span>" +
      (foraNoAr ? '<span class="trava-mono">' + esc(fora.hostname) + "</span>" : "") + "</div></div>" +
      (pronto ? '<button type="button" class="trava-link" id="trava-sem-internet">Sem internet? Entre com o código do celular</button>' : "") +
      "</div>";
  }
  const escuro = document.documentElement.dataset.tema === "escuro";
  // O alto ("Paulus está te esperando." e a frase) sobrevive ao redesenho:
  // a tela e refeita a cada mudanca de estado, e a saudacao so troca quando
  // muda o passo (js/entrada-saudacao.js).
  const antes = telaDaTrava().querySelector(".trava-marca");
  telaDaTrava().innerHTML =
    '<header class="trava-topo pywebview-drag-region"><span class="trava-selo">' + ic("desktop_windows", 16) + "servidor</span>" +
    '<button type="button" class="trava-tema" id="trava-tema" aria-label="Alternar tema">' + ic(escuro ? "light_mode" : "dark_mode", 16) + "</button></header>" +
    '<main class="trava-corpo">' + (codigo ? '<button type="button" class="trava-voltar" id="trava-voltar">' + ic("arrow_back", 18) + "Voltar</button>" : "") +
    '<div class="trava-coluna"><div class="trava-marca abrindo"><h1 data-es-titulo>Paulus está te esperando.</h1><p data-es-frase>' + esc(frase) +
    "</p></div>" + corpo + "</div></main>";
  const marca = telaDaTrava().querySelector(".trava-marca");
  if (antes) marca.replaceWith(antes);
  saudarNaTrava(antes || marca, tela);
  ligarTrava();
}

function saudarNaTrava(bloco, tela) {
  if (typeof EntradaSaudacao === "undefined") { bloco.classList.remove("abrindo"); return; }
  if (!bloco.dataset.aberto) { bloco.dataset.aberto = "1"; EntradaSaudacao.abrir(bloco, tela); }
  else EntradaSaudacao.trocar(bloco, tela);
}

function ligarTrava() {
  const t = document.getElementById("trava-tema");
  if (t) t.onclick = () => { alternarTema(); desenharTrava(); };
  const m = document.getElementById("trava-manter");
  if (m) m.onchange = () => { vinc.manterAoEntrar = m.checked; };
  const b = document.getElementById("trava-google");
  if (b) b.onclick = async () => {
    const manter = document.getElementById("trava-manter");
    vinc.manterAoEntrar = Boolean(manter && manter.checked);
    try { await entrarNoGoogleDoVinculo("destravar", aoMudarNaTrava); }
    catch (err) { const p = document.getElementById("trava-erro"); if (p) p.textContent = err.message; }
  };
  const tr = document.getElementById("trava-trocar");
  if (tr) tr.onclick = async () => {
    vinc.porRecuperacao = false;
    if (vinc.semInternet) { vinc.semInternet = false; desenharTrava(); return; }
    await postVinculo("/api/vinculo/cancelar").catch(() => {});
    desenharTrava();
  };
  const sn = document.getElementById("trava-sem-internet");
  if (sn) sn.onclick = () => { vinc.semInternet = true; vinc.porRecuperacao = false; desenharTrava(); };
  const rec = document.getElementById("trava-recuperacao");
  if (rec) rec.onclick = () => { vinc.porRecuperacao = !vinc.porRecuperacao; desenharTrava(); };
  const c = document.getElementById("trava-cancelar");
  if (c) c.onclick = async () => { await postVinculo("/api/vinculo/cancelar").catch(() => {}); desenharTrava(); };
  const v = document.getElementById("trava-voltar");
  if (v) v.onclick = async () => {
    vinc.porRecuperacao = false;
    if (vinc.semInternet) { vinc.semInternet = false; desenharTrava(); return; }
    await postVinculo("/api/vinculo/cancelar").catch(() => {});
    desenharTrava();
  };
  const f = document.getElementById("trava-codigo");
  if (f) {
    const campo = document.getElementById("trava-codigo-campo");
    // As seis casas: o campo de verdade fica por cima, transparente.
    const casas = document.getElementById("trava-casas");
    const desenhar = () => {
      if (casas.classList.contains("campo")) return;
      const val = campo.value.replace(/\D/g, "").slice(0, 6);
      casas.querySelectorAll("span").forEach((x) => x.remove());
      for (let i = 0; i < 6; i++) {
        const x = document.createElement("span");
        x.textContent = val[i] || "";
        if (i === Math.min(val.length, 5) && document.activeElement === campo) x.classList.add("vez");
        casas.insertBefore(x, campo);
      }
    };
    campo.addEventListener("input", desenhar);
    campo.addEventListener("focus", desenhar);
    campo.addEventListener("blur", desenhar);
    const renova = () => {
      const b = document.querySelector("#trava-renova b");
      if (!b) { clearInterval(vinc.renova); return; }
      b.textContent = "00:" + String(30 - (Math.floor(Date.now() / 1000) % 30)).padStart(2, "0");
    };
    clearInterval(vinc.renova);
    renova();
    vinc.renova = setInterval(renova, 1000);
    campo.focus();
    desenhar();
    f.onsubmit = async (ev) => {
      ev.preventDefault();
      try {
        const semNet = vinc.semInternet && !(vinc.estado || {}).precisa_codigo;
        await postVinculo(semNet ? "/api/vinculo/sem-internet" : "/api/vinculo/codigo", { codigo: campo.value.trim() });
        vinc.semInternet = false;
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
  mostrarBotaoSair();
  if (e && e.travado) desenharTrava();
});

/* ------------------------------------------------ sair (no servidor) */
/*
   "Sair", na barra da janela do servidor: trava o PAULUS na hora - mesmo com
   "manter aberto" - para ninguem mexer no computador do escritorio. Quem
   entra de fora nao passa pela trava: com o programa aberto, a equipe
   continua entrando pelo endereco. De fora, o "Sair" e o da propria conta
   (js/00-acesso.js).
*/
function mostrarBotaoSair() {
  const ver = Boolean(acessoDeFora.local);
  ["sair-servidor", "sair-servidor-menu"].forEach((id) => {
    const b = document.getElementById(id);
    if (!b) return;
    b.hidden = !ver;
    b.onclick = (ev) => { ev.stopPropagation(); sairDoServidor(); };
  });
}

async function sairDoServidor() {
  const e = (await lerVinculoGoogle()) || {};
  if (!e.vinculado) {
    const ir = await confirmar({ titulo: "Sair da conta", contexto: "servidor do escritório",
      texto: "Para sair, este PAULUS precisa estar vinculado a uma conta Google: é com ela que se entra de novo. Vincule em Configurações › Escritório e equipe.",
      confirmar: "Vincular agora" });
    if (ir) mostrarConfig("vinculos");
    return;
  }
  try {
    await postVinculo("/api/vinculo/travar");
  } catch (err) { avisoCert(err.message, { tom: "erro" }); return; }
  desenharTrava();
}

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
    blocoSemInternet(e) +
    '<div class="acesso-pe"><button class="com-icone" data-vinc-travar="1">' + ic("logout", 16) + "Sair</button>" +
    '<button class="perigo" data-vinc-desvincular="1">Desvincular</button>' +
    '<p class="cfg-explica">Sair trava este computador até alguém entrar com o Google (o acesso de fora continua). Desvincular não apaga nada: o PAULUS só deixa de pedir o Google ao abrir.</p></div>');
}

/* Entrar sem internet (src/vinculo.py): o login do servidor nao depende do
   Google. Com a conta de titular do mesmo e-mail, o codigo dela ja vale; sem
   ela, o servidor ganha um codigo proprio, ligado aqui com o QR. */
function blocoSemInternet(e) {
  const si = e.sem_internet || {};
  const miolo = vinc.semNetNovo
    ? '<div class="acesso-qr-bloco"><div class="acesso-qr">' + (vinc.semNetNovo.qr_svg || "") + "</div>" +
      '<div class="acesso-qr-texto"><p>No celular, abra o <b>Google Authenticator</b>, toque em <b>+</b> e em <b>Ler código QR</b>.</p>' +
      '<p class="cfg-explica">Sem câmera? Digite a chave:</p><code class="acesso-segredo">' +
      esc((vinc.semNetNovo.segredo || "").replace(/(.{4})/g, "$1 ").trim()) + "</code></div></div>" +
      '<div class="acesso-form"><div class="ag-campo"><label for="vinc-sn-codigo">Código de 6 números que aparece no aplicativo</label>' +
      '<input type="text" id="vinc-sn-codigo" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="000000"></div></div>' +
      '<div class="acesso-pe"><button class="primario" data-vinc-sn-confirmar="1">Confirmar o código</button>' +
      '<button data-vinc-sn-cancelar="1">Cancelar</button></div>'
    : vinc.semNetCodigos
      ? '<p class="cfg-texto">Guarde estes códigos fora do celular: cada um abre o PAVLVS uma vez, sem internet, se o celular sumir. Eles não aparecem de novo.</p>' +
        '<div class="acesso-codigos">' + vinc.semNetCodigos.map((x) => "<code>" + esc(x) + "</code>").join("") + "</div>" +
        '<div class="acesso-pe"><button class="primario" data-vinc-sn-guardei="1">Guardei os códigos</button></div>'
      : si.por === "titular"
        ? '<p class="cfg-explica">' + ic("check_circle", 14) + " Pronto: sem internet, o código do celular da sua conta de titular abre este PAVLVS.</p>"
        : si.por === "servidor"
          ? '<p class="cfg-explica">' + ic("check_circle", 14) + " Pronto: sem internet, o código do celular deste servidor abre o PAVLVS" +
            (si.recuperacao_restantes != null ? " · " + si.recuperacao_restantes + " códigos de recuperação" : "") + ".</p>" +
            '<div class="cfg-botoes"><button data-vinc-sn-desligar="1">Desligar</button></div>'
          : '<p class="cfg-explica">Sem internet, o Google não responde e o PAVLVS travado não abre. Ligue o código do celular: o Google Authenticator funciona sem conexão.</p>' +
            '<div class="cfg-botoes"><button class="com-icone" data-vinc-sn-ligar="1">' + ic("shield_person", 16) + "Ligar entrar sem internet</button></div>";
  return '<div class="acesso-energia"><b>Entrar sem internet</b>' + miolo + "</div>";
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
  clique("[data-vinc-travar]", () => sairDoServidor());
  clique("[data-vinc-sn-ligar]", async () => {
    try {
      const r = await fetch("/api/vinculo/sem-internet/ligar", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || "não deu certo");
      vinc.semNetNovo = d;
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-vinc-sn-cancelar]", () => { vinc.semNetNovo = null; redesenhar(); });
  clique("[data-vinc-sn-confirmar]", async () => {
    const campo = document.getElementById("vinc-sn-codigo");
    try {
      const r = await fetch("/api/vinculo/sem-internet/confirmar", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ codigo: campo ? campo.value.trim() : "" }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || "não deu certo");
      vinc.semNetNovo = null;
      vinc.semNetCodigos = d.codigos_recuperacao || [];
      vinc.estado = d.estado || vinc.estado;
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-vinc-sn-guardei]", () => { vinc.semNetCodigos = null; redesenhar(); });
  clique("[data-vinc-sn-desligar]", async () => {
    try { await postVinculo("/api/vinculo/sem-internet/desligar"); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-vinc-desvincular]", async () => {
    if (!(await confirmar({ titulo: "Desvincular a conta Google?", contexto: "Configurações › Escritório e equipe",
      texto: "O PAULUS deixa de pedir o Google ao abrir. Para ligar o acesso de fora e convidar a equipe, vai ser preciso vincular de novo.",
      confirmar: "Desvincular", perigo: true }))) return;
    try { await postVinculo("/api/vinculo/desvincular"); avisoCert("desvinculado", { tom: "ok" }); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
}
