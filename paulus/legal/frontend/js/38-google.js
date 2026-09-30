/* --------------------------------------------------------------- google */
/*
   A conta Google além do Gmail (src/google_servicos.py): a Agenda com o
   Meet, e o Drive. É a mesma conta que entrou no e-mail; conectar um serviço
   pede ao Google mais uma permissão (a tela do Google abre no navegador), e
   ela se soma às que já existem.

   O que sai desta máquina, dito na tela onde se liga:
   - Agenda: com "Sincronizar" ligado, título, data, hora, duração e lugar de
     cada compromisso (a anotação e o cliente ficam aqui);
   - Drive: só o documento que a pessoa manda, e pela fila de Aprovações.
     Ler o Drive (a permissão à parte, só leitura) só baixa: as pastas
     escolhidas viram cópia no Acervo (src/drive_online.py).
*/

const gg = { dados: null, relogio: null, pedido: null, tentou: false };

async function carregarGoogle() {
  try {
    const r = await fetch("/api/google");
    gg.dados = r.ok ? await r.json() : null;
  } catch (err) {
    gg.dados = null;
  }
  gg.tentou = true;
  return gg.dados;
}

/* O estado do Google uma vez so, para quem precisa dele e chega junto (o
   cabecalho da Agenda e a opcao do Meet no formulario). */
function googleCarregado() {
  if (gg.dados !== null) return Promise.resolve(gg.dados);
  if (!gg.pedido) gg.pedido = carregarGoogle().finally(() => { gg.pedido = null; });
  return gg.pedido;
}

function googleConectado(servico) {
  return Boolean(gg.dados && gg.dados.servicos && gg.dados.servicos[servico] && gg.dados.servicos[servico].conectado);
}

function cartaoGoogle() {
  const d = gg.dados;
  if (!d) return cartaoCfg("Conta Google", "", '<p class="cfg-texto">Lendo a conta Google…</p>');
  if (!d.configurado) {
    return cartaoCfg("Conta Google", "", '<p class="cfg-texto">Esta versão do PAULUS não traz o login do Google.</p>');
  }
  if (!d.conta) {
    return cartaoCfg("Conta Google", metaCfg("Gmail · Agenda e Meet · Drive"),
      '<p class="cfg-texto">Entre primeiro com a conta Google no e-mail: é a mesma conta que depois ganha a Agenda, o Meet e o Drive.</p>' +
      '<div class="cfg-botoes"><button class="primario" data-gg-email="1">Entrar com Google em E-mail › Contas</button></div>');
  }
  const ponto = (texto, tom) => '<span class="fin-meta-ponto' + (tom ? " " + tom : "") + '"><i></i>' + esc(texto) + "</span>";
  const agenda = googleConectado("agenda");
  const drive = googleConectado("drive");
  const linha = (icone, nome, sub, estado, acao) => '<div class="cfg-servico"><span class="caixa-tipo">' + ic(icone, 18) +
    '</span><span class="duas-linhas"><b>' + nome + "</b><small>" + esc(sub) + "</small></span>" + estado + '<span class="cfg-botoes">' + acao + "</span></div>";

  const sinc = d.ultimo_sinc ? "sincronizada em " + d.ultimo_sinc.slice(8, 10) + "/" + d.ultimo_sinc.slice(5, 7) + " às " + d.ultimo_sinc.slice(11, 16) : "ainda não sincronizada";
  let html =
    linha("mail", "Gmail", d.conta, d.precisa_entrar ? ponto("entrar de novo", "acc") : ponto("conectado", "ok"), '<button data-gg-email="1">Contas</button>') +
    linha("calendar_month", "Agenda e Meet", agenda ? sinc : "compromissos na Agenda do Google, com sala do Meet de verdade",
      agenda ? ponto("conectada", "ok") : ponto("não conectada", ""),
      agenda ? '<button class="com-icone" data-gg-sinc="1">' + marca("google-agenda", 16) + "Sincronizar agora</button>"
        : '<button class="primario com-icone" data-gg-conectar="agenda">' + marca("google-agenda", 16) + "Conectar</button>") +
    linha("folder", "Enviar ao Google Drive", drive ? "os documentos que você envia vão para a pasta PAULUS do seu Drive" : "enviar documentos do Acervo para o seu Drive",
      drive ? ponto("conectado", "ok") : ponto("não conectado", ""),
      drive ? "" : '<button class="primario" data-gg-conectar="drive">Conectar</button>') +
    linhaDriveNoAcervo(linha, ponto);

  if (agenda) {
    html += '<div class="cfg-sub">' +
      ligaGoogle("agenda_sincronizar", "Sincronizar os compromissos com o Google", "vai título, data, hora, duração e lugar; a anotação e o cliente ficam aqui", d.agenda_sincronizar) +
      ligaGoogle("agenda_mostrar", "Mostrar os eventos do Google na Agenda", "só para ver: editar é no Google", d.agenda_mostrar) + "</div>";
  }
  const locais = d.drive_no_computador || [];
  html += '<p class="cfg-explica">' + (locais.length
    ? "Google Drive neste computador: " + locais.map((p) => esc(p.caminho) + (p.vigiada ? " (o Acervo já vigia)"
        : ' <button class="em-ligacao" data-gg-vigiar="' + esc(p.caminho) + '">vigiar no Acervo</button>')).join(" · ") +
      ". Assim o Acervo lê o seu Drive inteiro sem pedir permissão nenhuma ao Google."
    : "Outro caminho, sem dar permissão ao PAULUS: o Google Drive para computador vira uma pasta do Windows, e aí é só vigiar a pasta no Acervo.") + "</p>";
  if (d.erro) html += '<p class="cfg-explica mod-erro">' + esc(maiuscula(d.erro)) + ".</p>";
  html += '<p class="cfg-explica">O PAULUS só usa o que você conecta aqui. Para tirar as permissões do Google de vez, use myaccount.google.com/permissions.</p>';
  return cartaoCfg("Conta Google", metaCfg(d.conta), html);
}

/* Ler o Drive pela internet: a permissao so de leitura e as pastas que
   viraram copia no Acervo, cada uma com a hora da ultima conferida. */
function linhaDriveNoAcervo(linha, ponto) {
  const leitura = googleConectado("drive_leitura");
  const copias = ((gg.dados || {}).drive_online || {}).pastas || [];
  let html = linha("folder_special", "Google Drive no Acervo",
    leitura ? (copias.length ? plural(copias.length, "pasta") + " do Drive com cópia no Acervo, conferidas a cada 15 minutos" : "escolha as pastas em Acervo › Incluir pasta › Google Drive")
      : "ler pastas do seu Drive pela internet e ter uma cópia delas no Acervo",
    leitura ? ponto("autorizado", "ok") : ponto("não autorizado", ""),
    leitura ? (copias.length ? '<button data-gg-drive-sinc="1">Conferir agora</button>' : "") + '<button data-gg-drive-incluir="1">Escolher pasta</button>'
      : '<button class="primario" data-gg-conectar="drive_leitura">Autorizar leitura</button>');
  if (copias.length) {
    const quando = (t) => (t ? "conferida " + t.slice(8, 10) + "/" + t.slice(5, 7) + " às " + t.slice(11, 16) : "ainda descendo");
    html += '<div class="cfg-sub">' + copias.map((p) => '<div class="cfg-servico"><span class="caixa-tipo">' + marca("google-drive", 16) + "</span>" +
      '<span class="duas-linhas"><b>' + esc(p.nome) + "</b><small>" +
      esc(p.sincronizando ? "descendo agora · " + plural(p.baixados_agora, "arquivo") : plural(p.arquivos || 0, "documento") + " · " + quando(p.ultimo) +
        (p.ignorados ? " · " + p.ignorados + " que o Acervo não lê ficaram no Drive" : "")) + "</small>" +
      (p.erro ? '<small class="mod-erro">' + esc(maiuscula(p.erro)) + "</small>" : "") + "</span>" +
      '<span class="cfg-botoes"><button class="mais-linha" data-gg-drive-tirar="' + esc(p.id) + '" title="Parar de acompanhar" aria-label="Parar de acompanhar">' +
      ic("close", 16) + "</button></span></div>").join("") + "</div>";
  }
  return html;
}

/* O mesmo interruptor das outras preferencias (ligaCfg), mas vale na hora:
   nao passa pelo "Salvar alterações" - e uma acao, nao rascunho. */
function ligaGoogle(chave, rotulo, sub, ligado) {
  return '<div class="ag-toggle' + (ligado ? " on" : "") + '" data-gg-pref="' + chave + '" role="switch" aria-checked="' + Boolean(ligado) +
    '" tabindex="0"><span class="duas-linhas"><b>' + esc(rotulo) + "</b><small>" + esc(sub) + "</small></span><i></i></div>";
}

/* `depois(pronto)` e para quem conecta de fora de Conexoes (a opcao do Meet
   no formulario do compromisso): redesenha o que dependia da Agenda. */
async function conectarGoogle(servico, botao, depois) {
  const rotulo = botao ? botao.innerHTML : "";
  if (botao) { botao.disabled = true; botao.textContent = "abrindo o Google…"; }
  const r = await fetch("/api/google/conectar", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ servico: servico, tema: document.documentElement.dataset.tema || "" }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); if (botao) { botao.disabled = false; botao.innerHTML = rotulo; } return; }
  avisoCert("Abri a tela do Google no navegador: marque a permissão e volte aqui.", { dura: 8000 });
  clearTimeout(gg.relogio);
  const acompanhar = async () => {
    let d;
    try { d = await (await fetch("/api/email/oauth/andamento")).json(); } catch (err) { d = null; }
    if (!d || ["aguardando", "trocando", "testando", "preparando"].includes(d.fase)) { gg.relogio = setTimeout(acompanhar, 1500); return; }
    if (d.fase === "pronto") avisoCert((servico === "agenda" ? "Agenda do Google conectada — sincronizando" : "Google Drive conectado"), { tom: "ok" });
    else if (d.fase !== "cancelado") avisoCert(maiuscula(d.mensagem || "o Google não terminou"), { tom: "erro" });
    await carregarGoogle();
    if (depois) depois(d.fase === "pronto");
    if (typeof cfg !== "undefined" && cfg.secao === "conexoes" && $("cfg-tela")) desenharConfig();
  };
  gg.relogio = setTimeout(acompanhar, 1500);
}

async function sincronizarGoogle(botao) {
  if (botao) { botao.disabled = true; }
  const r = await fetch("/api/google/sincronizar", { method: "POST" });
  if (botao) botao.disabled = false;
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  const d = await r.json();
  gg.dados = d.google;
  avisoCert(d.falhas.length ? plural(d.enviados, "compromisso") + " no Google; " + d.falhas[0].motivo
    : plural(d.enviados, "compromisso") + " no Google Agenda", { tom: d.falhas.length ? "erro" : "ok" });
  return d;
}

function ligarGoogle(raiz) {
  const r = raiz || document;
  r.querySelectorAll("[data-gg-conectar]").forEach((b) => { b.onclick = () => conectarGoogle(b.dataset.ggConectar, b); });
  r.querySelectorAll("[data-gg-email]").forEach((b) => { b.onclick = () => { marcarDestino("caixa"); mostrarEmail("contas"); }; });
  r.querySelectorAll("[data-gg-sinc]").forEach((b) => {
    b.onclick = async () => { await sincronizarGoogle(b); desenharConfig(); };
  });
  r.querySelectorAll("[data-gg-pref]").forEach((c) => {
    c.onclick = async () => {
      const ligar = !c.classList.contains("on");
      c.classList.toggle("on", ligar);
      const resp = await fetch("/api/google/preferencias", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ [c.dataset.ggPref]: ligar }),
      });
      if (resp.ok) gg.dados = await resp.json();
      desenharConfig();
    };
  });
  r.querySelectorAll("[data-gg-drive-incluir]").forEach((b) => { b.onclick = () => adicionarPastaAoAcervo(); });
  r.querySelectorAll("[data-gg-drive-sinc]").forEach((b) => {
    b.onclick = async () => {
      b.disabled = true;
      const resp = await fetch("/api/google/drive/copias/sincronizar", { method: "POST" });
      if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); b.disabled = false; return; }
      avisoCert("conferindo o Drive — o que mudou lá desce para o Acervo", { tom: "ok" });
      setTimeout(async () => { await carregarGoogle(); if (typeof cfg !== "undefined" && cfg.secao === "conexoes") desenharConfig(); }, 3000);
    };
  });
  r.querySelectorAll("[data-gg-drive-tirar]").forEach((b) => {
    b.onclick = async () => {
      const p = (((gg.dados || {}).drive_online || {}).pastas || []).find((x) => x.id === b.dataset.ggDriveTirar);
      if (!p) return;
      const e = await dialogo({
        titulo: "Parar de acompanhar “" + p.nome + "”?", contexto: "Conexões › Google Drive",
        texto: "A pasta continua no seu Drive. A cópia no Acervo deixa de ser atualizada; se preferir, ela sai também.",
        marcar: { rotulo: "Apagar também a cópia do Acervo", marcada: false },
        confirmar: "Parar de acompanhar",
      });
      if (!e || !e.ok) return;
      const resp = await fetch("/api/google/drive/copias/tirar", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: p.id, apagar_copia: Boolean(e.marcada) }),
      });
      if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
      avisoCert(e.marcada ? "“" + p.nome + "” saiu do Acervo" : "“" + p.nome + "” não é mais acompanhada; a cópia ficou no Acervo", { tom: "ok" });
      await carregarGoogle();
      desenharConfig();
    };
  });
  r.querySelectorAll("[data-gg-vigiar]").forEach((b) => {
    b.onclick = async () => {
      const resp = await fetch("/api/acervo/pastas", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminho: b.dataset.ggVigiar }),
      });
      if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
      const d = await resp.json();
      avisoCert("O Acervo vigia o seu Drive: " + plural(d.arquivos, "documento") + " para ler, sem sair do lugar", { tom: "ok" });
      await carregarGoogle();
      desenharConfig();
    };
  });
}

/* Acervo: enviar ao Drive é pedido na fila - sai desta máquina. */
async function enviarAoDrive(caminhos) {
  const r = await fetch("/api/google/drive/enviar", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminhos: caminhos }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  avisoCert("Pedido na fila de aprovações: " + d.pedido.titulo + ". Nada sai antes do seu sim.", { tom: "ok" });
  contarPendencias();
}
