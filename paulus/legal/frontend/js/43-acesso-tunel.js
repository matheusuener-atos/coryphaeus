/* ---------------------------------------------- acesso de fora: o tunel */
/*
   R7: o assistente de conexao, dentro de Configuracoes › Acesso de fora
   (js/42-acesso.js desenha a secao; este arquivo, o cartao do tunel).

   Tres estados, e o cartao e um de cada vez:
     - conectar: nome do escritorio e e-mail do titular, e um botao;
     - esperando: o codigo XXXX-XXXX grande, enquanto o titular confirma em
       paulus.ia.br/conectar (a tela pergunta de novo a cada 3 s);
     - conectado: o endereco, copiavel, o estado do tunel, quem pode entrar,
       e Desligar / Remover.

   O instalador abre o programa com --configurar-acesso, e o desktop.py poe
   #acesso no endereco: a tela abre direto aqui.
*/

const tunelCfg = { dados: null, relogio: null };

async function carregarTunel() {
  try {
    const r = await fetch("/api/acesso/tunel");
    tunelCfg.dados = r.ok ? await r.json() : null;
  } catch (err) {
    tunelCfg.dados = null;
  }
}

const TUNEL_ESTADOS = {
  conectado: ["conectado", "ok"], ligando: ["ligando", ""], caiu: ["desconectado — tentando de novo", "acc"],
  porta_ocupada: ["indisponível: porta ocupada", "acc"], desligado: ["desligado", ""], nao_conectado: ["não conectado", ""],
  sem_cloudflared: ["falta o cloudflared", "acc"], sem_token: ["falta conectar", "acc"],
};

function cartaoTunel() {
  const d = tunelCfg.dados;
  if (!d) return "";
  const s = d.situacao || {};
  const pedido = (d.conexao || {}).pedido;
  if (pedido && pedido.estado === "esperando") return cartaoTunelEsperando(pedido);
  if (s.conectado_ao_worker) return cartaoTunelConectado(s, d);
  return cartaoTunelConectar(s, d, pedido, (d.conexao || {}).erro);
}

function cartaoTunelConectar(s, d, pedido, erro) {
  const titulares = d.titulares || [];
  const nome = ((cfg.prefs || {}).preferencias || {}).escritorio ? cfg.prefs.preferencias.escritorio.nome || "" : "";
  const faltas = [];
  if (!s.disponivel) faltas.push("Este computador não tem como guardar os segredos do acesso de fora com proteção.");
  if (!(s.cloudflared || {}).basta) {
    faltas.push((s.cloudflared || {}).caminho
      ? "O cloudflared deste computador é antigo (" + s.cloudflared.versao + "); o PAULUS precisa da " + s.cloudflared.minima + " ou mais nova. Reinstale o PAULUS marcando “Acesso de fora”."
      : "Falta o cloudflared, o programa da Cloudflare que abre o túnel. Reinstale o PAULUS marcando “Acesso de fora pelo celular”.");
  }
  if (!titulares.length) faltas.push("Primeiro, a conta do titular com o autenticador confirmado — logo abaixo, em Contas.");
  const aviso = pedido && pedido.estado === "expirado"
    ? '<p class="acesso-erro">O código venceu antes da confirmação (dura 15 minutos). Comece de novo.</p>'
    : (erro ? '<p class="acesso-erro">' + esc(erro) + "</p>" : "");
  const passos = '<ol class="acesso-passos">' +
    "<li>O PAULUS pede um endereço em paulus.ia.br e abre o navegador.</li>" +
    "<li>Você entra com o e-mail do titular (a Cloudflare manda um código) e confirma.</li>" +
    "<li>O túnel liga sozinho, e o endereço aparece aqui.</li></ol>";
  if (faltas.length) {
    return cartaoCfg("Conectar", metaCfg("ainda não dá"),
      passos + '<ul class="acesso-faltas">' + faltas.map((f) => "<li>" + esc(f) + "</li>").join("") + "</ul>" + aviso);
  }
  const opcoes = titulares.map((t) => '<option value="' + esc(t.email) + '">' + esc(t.nome + " · " + t.email) + "</option>").join("");
  return cartaoCfg("Conectar", metaCfg("desligado"),
    passos +
    '<div class="acesso-form">' +
    '<div class="ag-campo"><label>Nome do escritório</label><input type="text" id="tunel-nome" value="' + esc(nome) + '" maxlength="80" placeholder="vira o endereço: nome-do-escritorio.paulus.ia.br"></div>' +
    '<div class="ag-campo"><label>E-mail do titular</label><select id="tunel-email">' + opcoes + "</select></div></div>" +
    aviso +
    '<div class="acesso-pe"><button class="primario com-icone" data-tunel-conectar="1">' + ic("link", 16) + "Conectar</button>" +
    '<p class="cfg-explica">Nada é criado antes de você confirmar no navegador.</p></div>');
}

function cartaoTunelEsperando(p) {
  return cartaoCfg("Conectar", pontoCfg("esperando a confirmação", "acc"),
    '<p class="cfg-texto">Abri <b>paulus.ia.br/conectar</b> no navegador. Entre com <b>' + esc(p.email) +
    "</b> (a Cloudflare manda um código para esse e-mail), confira que o código abaixo é o mesmo e aperte Confirmar.</p>" +
    '<div class="acesso-codigo-usuario" aria-label="código">' + esc(p.codigo_usuario) + "</div>" +
    '<p class="cfg-explica">Vale até ' + esc(new Date(p.expira_em).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })) +
    ". Esta tela confere sozinha a cada 3 segundos.</p>" +
    '<div class="acesso-pe"><button class="com-icone" data-tunel-abrir="' + esc(p.url) + '">' + ic("open_in_new", 16) + "Abrir de novo</button>" +
    '<button data-tunel-cancelar="1">Cancelar</button></div>');
}

function cartaoTunelConectado(s, d) {
  const [rotulo, tom] = TUNEL_ESTADOS[s.estado] || [s.estado, ""];
  const endereco = s.hostname ? "https://" + s.hostname : "";
  const contas = (acessoCfg.contas || []).map((c) => c.email);
  const energia = d.energia || {};
  const corpo =
    '<div class="acesso-endereco"><code>' + esc(endereco) + "</code>" +
    '<button class="com-icone" data-tunel-copiar="' + esc(endereco) + '">' + ic("content_copy", 16) + "Copiar</button></div>" +
    '<div class="cfg-linhas">' +
    chaveCfg("Túnel", rotulo, tom) +
    chaveCfg("Porta deste computador", String(s.porta || "—")) +
    chaveCfg("cloudflared", ((s.cloudflared || {}).versao || "não encontrado")) +
    (energia.situacao ? chaveCfg("Energia", energia.situacao, energia.tom || "") : "") +
    "</div>" +
    (s.ultimo_erro && s.estado !== "conectado" ? '<p class="cfg-explica">' + esc(s.ultimo_erro) + "</p>" : "") +
    (s.porta_ocupada ? '<p class="acesso-erro">Outro programa está usando a porta ' + esc(String(s.porta)) +
      ". Enquanto isso, ninguém entra de fora — a janela daqui não é afetada.</p>" : "") +
    '<p class="cfg-texto acesso-quem">Podem passar pela Cloudflare: ' +
    (contas.length ? esc(contas.join(", ")) : "ninguém ainda") + ". A lista acompanha as contas abaixo.</p>" +
    (typeof blocoEnergia === "function" ? blocoEnergia(energia) : "") +
    '<div class="acesso-pe">' +
    (s.porta_ocupada ? '<button class="primario" data-tunel-porta="1">Usar outra porta</button>' : "") +
    (s.ligado ? '<button class="com-icone" data-tunel-ligar="0">' + ic("pause", 16) + "Desligar</button>"
      : '<button class="primario com-icone" data-tunel-ligar="1">' + ic("play_arrow", 16) + "Ligar</button>") +
    '<button class="perigo" data-tunel-remover="1">Remover o acesso de fora</button>' +
    '<p class="cfg-explica">Desligar para o túnel e guarda o endereço. Remover apaga o endereço em paulus.ia.br e tudo o que ficou guardado aqui.</p></div>';
  return cartaoCfg("Endereço", pontoCfg(rotulo, tom), corpo);
}

/* Enquanto espera a confirmacao, a tela pergunta de novo a cada 3 s - e so
   redesenha quando algo mudou (o titular confirmou, o codigo venceu). */
function acompanharTunel() {
  clearInterval(tunelCfg.relogio);
  tunelCfg.relogio = setInterval(async () => {
    if (cfg.secao !== "acesso" || !document.getElementById("cfg-tela")) { clearInterval(tunelCfg.relogio); return; }
    const antes = JSON.stringify(tunelCfg.dados);
    await carregarTunel();
    const pedido = ((tunelCfg.dados || {}).conexao || {}).pedido;
    if (JSON.stringify(tunelCfg.dados) !== antes) {
      if (pedido && pedido.estado === "concluido") avisoCert("acesso de fora conectado", { tom: "ok" });
      desenharConfig();
    }
    if (!pedido || pedido.estado !== "esperando") {
      // Fora da espera, basta olhar o tunel de vez em quando.
      clearInterval(tunelCfg.relogio);
      tunelCfg.relogio = setInterval(async () => {
        if (cfg.secao !== "acesso" || !document.getElementById("cfg-tela")) { clearInterval(tunelCfg.relogio); return; }
        const velho = JSON.stringify((tunelCfg.dados || {}).situacao);
        await carregarTunel();
        if (JSON.stringify((tunelCfg.dados || {}).situacao) !== velho) desenharConfig();
      }, 5000);
    }
  }, 3000);
}

function ligarTunel() {
  const clique = (seletor, fn) => document.querySelectorAll(seletor).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b); }; });
  const depois = async () => { await carregarTunel(); desenharConfig(); };
  clique("[data-tunel-conectar]", async (b) => {
    const nome = ($("tunel-nome") || {}).value || "";
    const email = ($("tunel-email") || {}).value || "";
    b.disabled = true;
    try {
      await acessoPost("/api/acesso/tunel/conectar", { nome: nome, email: email });
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    await depois();
  });
  clique("[data-tunel-abrir]", (b) => window.open(b.dataset.tunelAbrir, "_blank"));
  clique("[data-tunel-cancelar]", async () => { await acessoPost("/api/acesso/tunel/cancelar"); await depois(); });
  clique("[data-tunel-copiar]", async (b) => {
    try { await navigator.clipboard.writeText(b.dataset.tunelCopiar); avisoCert("endereço copiado", { tom: "ok" }); }
    catch (err) { avisoCert("não consegui copiar: selecione o endereço e copie", { tom: "erro" }); }
  });
  clique("[data-tunel-ligar]", async (b) => {
    const ligar = b.dataset.tunelLigar === "1";
    if (!ligar && !(await confirmar({ titulo: "Desligar o acesso de fora?", contexto: "Configurações › Acesso de fora",
      texto: "Quem estiver de fora sai agora, e o endereço para de responder. Ligar de novo usa o mesmo endereço.", confirmar: "Desligar" }))) return;
    try { await acessoPost("/api/acesso/tunel/ligar", { ligado: ligar }); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    await depois();
  });
  clique("[data-tunel-porta]", async () => {
    try {
      const r = await acessoPost("/api/acesso/tunel/porta");
      avisoCert("agora na porta " + r.porta, { tom: "ok" });
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    await depois();
  });
  clique("[data-tunel-remover]", async () => {
    if (!(await confirmar({ titulo: "Remover o acesso de fora?", contexto: "Configurações › Acesso de fora",
      texto: "O endereço sai de paulus.ia.br, o túnel é apagado, e quem estiver de fora sai. As contas continuam aqui. Para voltar, é conectar de novo — com outro endereço.",
      confirmar: "Remover", perigo: true }))) return;
    try { await acessoPost("/api/acesso/tunel/remover"); avisoCert("acesso de fora removido", { tom: "ok" }); }
    catch (err) { avisoCert(err.message, { tom: "erro" }); }
    await depois();
  });
  if (typeof ligarEnergia === "function") ligarEnergia();
  acompanharTunel();
}

/* --configurar-acesso (o instalador) chega como #acesso: abre direto aqui. */
function abrirAcessoPeloEndereco() {
  if (location.hash !== "#acesso" || !acessoDeFora.local) return;
  history.replaceState(null, "", location.pathname);
  setTimeout(() => mostrarConfig("acesso"), 600);
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", abrirAcessoPeloEndereco);
else abrirAcessoPeloEndereco();
