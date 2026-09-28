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
    linha("folder", "Google Drive", drive ? "os documentos que você envia vão para a pasta PAULUS do seu Drive" : "enviar documentos do Acervo para o seu Drive",
      drive ? ponto("conectado", "ok") : ponto("não conectado", ""),
      drive ? "" : '<button class="primario" data-gg-conectar="drive">Conectar</button>');

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
    : "Para o Acervo ler o seu Drive inteiro, instale o Google Drive para computador: ele vira uma pasta do Windows, e aí é só vigiar a pasta no Acervo.") + "</p>";
  if (d.erro) html += '<p class="cfg-explica mod-erro">' + esc(maiuscula(d.erro)) + ".</p>";
  html += '<p class="cfg-explica">O PAULUS só usa o que você conecta aqui. Para tirar as permissões do Google de vez, use myaccount.google.com/permissions.</p>';
  return cartaoCfg("Conta Google", metaCfg(d.conta), html);
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
