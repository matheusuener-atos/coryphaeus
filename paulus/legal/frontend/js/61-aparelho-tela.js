/* ------------------------------------------ pensar no aparelho: a tela (D4) */
/*
   O seletor Escritório · Este aparelho · Automático, a janela que sugere o
   aparelho quando o escritório está ocupado, o aviso da primeira vez e o
   caminho de uma resposta escrita aqui (docs/PROGRESSO-APARELHO.md, D4).
   O motor mora em js/60-aparelho.js e no trabalhador.

   - O seletor só aparece de fora, para a conta que o titular liberou
     (/api/aparelho/estado) e neste aparelho depois de passar no teste de
     capacidade. Não passou: o motivo fica em Minha conta › Este aparelho.
   - O que fica guardado neste navegador (localStorage "paulus.aparelho") é
     só a escolha, o resultado do teste (números), o "entendi" e o "não
     sugerir hoje". Nada da conversa: a pergunta, os trechos e a resposta
     passam pela memória e somem (o trabalhador solta tudo no fim).
   - Quem decide se pode é o servidor: a tela só pede. Pedido que não pode
     vira resposta do escritório, com o motivo na resposta.
*/

const aparelhoTela = { estado: null, escrevendo: null };
const APARELHO_CHAVE = "paulus.aparelho";
// Mais devagar que isso, a resposta aqui levaria minutos: o teste não passa.
const APARELHO_MINIMO_TPS = 3;

function prefsDoAparelho() {
  try { return JSON.parse(localStorage.getItem(APARELHO_CHAVE) || "{}") || {}; } catch (err) { return {}; }
}

function guardarPrefsDoAparelho(mudar) {
  const p = Object.assign(prefsDoAparelho(), mudar || {});
  try { localStorage.setItem(APARELHO_CHAVE, JSON.stringify(p)); } catch (err) { /* sem armazenamento: vale só agora */ }
  return p;
}

function hojeNoAparelho() {
  const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
}

function tamanhoDoModelo(bytes) {
  if (!bytes) return "";
  const gb = bytes / (1024 * 1024 * 1024);
  return gb >= 1 ? String(Math.round(gb * 10) / 10).replace(".", ",") + " GB" : Math.round(bytes / (1024 * 1024)) + " MB";
}

/* De fora, com a conta liberada e o teste passado neste aparelho. */
function aparelhoDisponivel() {
  const e = aparelhoTela.estado;
  const t = prefsDoAparelho().teste;
  return Boolean(e && e.pode && t && t.passou);
}

async function lerEstadoDoAparelho() {
  try { await acessoDeFora.pronto; } catch (err) { /* segue */ }
  if (acessoDeFora.local) { aparelhoTela.estado = null; desenharSeletorDoAparelho(); return null; }
  try {
    const r = await fetch("/api/aparelho/estado");
    aparelhoTela.estado = r.ok ? await r.json() : null;
  } catch (err) { aparelhoTela.estado = null; }
  desenharSeletorDoAparelho();
  return aparelhoTela.estado;
}

/* ------------------------------------------------------------ o seletor */

const MODOS_DO_APARELHO = [["escritorio", "Escritório"], ["aparelho", "Este aparelho"], ["automatico", "Automático"]];

function desenharSeletorDoAparelho() {
  const pilulas = document.querySelector("#cartao-campo .pilulas");
  if (!pilulas) return;
  let caixa = $("aparelho-onde");
  if (!aparelhoDisponivel()) { if (caixa) caixa.hidden = true; return; }
  const modo = prefsDoAparelho().modo || "escritorio";
  if (!caixa) {
    caixa = document.createElement("label");
    caixa.id = "aparelho-onde";
    caixa.className = "pilula pilula-aparelho";
    caixa.title = "Onde a resposta é escrita: no computador do escritório ou neste aparelho";
    caixa.innerHTML = ic("desktop_windows", 18) + '<select id="aparelho-modo" aria-label="Onde a resposta é escrita">' +
      MODOS_DO_APARELHO.map(([v, r]) => '<option value="' + v + '">' + r + "</option>").join("") + "</select>";
    const ditar = $("ditar");
    if (ditar && ditar.parentElement === pilulas) pilulas.insertBefore(caixa, ditar);
    else pilulas.appendChild(caixa);
    caixa.querySelector("select").addEventListener("change", async (e) => {
      if (aparelhoTela.mostrando) return;
      const novo = e.target.value;
      if (novo !== "escritorio" && !(await avisoDaPrimeiraVez())) { mostrarModoDoAparelho(e.target, prefsDoAparelho().modo || "escritorio"); return; }
      guardarPrefsDoAparelho({ modo: novo });
    });
  }
  mostrarModoDoAparelho(caixa.querySelector("select"), modo);
  caixa.hidden = false;
}

/* O valor do select e o rótulo do botão de escolha que fica na frente dele
   (js/16-dialogos.js), sem contar como escolha da pessoa. */
function mostrarModoDoAparelho(sel, modo) {
  if (sel.value === modo) return;
  sel.value = modo;
  aparelhoTela.mostrando = true;
  try { sel.dispatchEvent(new Event("change")); } finally { aparelhoTela.mostrando = false; }
}

/* §2.6: o que o aparelho recebe, o que fica e o que não dá para garantir. */
async function avisoDaPrimeiraVez() {
  if (prefsDoAparelho().entendi) return true;
  const e = aparelhoTela.estado || {};
  const tamanho = tamanhoDoModelo(e.bytes);
  const r = await dialogo({
    titulo: "Escrever as respostas neste aparelho", contexto: "Primeira vez",
    html: '<div class="aparelho-aviso">' +
      "<p>O escritório continua procurando nos documentos. Para este aparelho vão só os trechos que a sua conta já veria por aqui; " +
      "o modelo (" + esc(e.modelo || "de linguagem") + ") escreve a resposta aqui, e o escritório confere o texto antes de ele aparecer.</p>" +
      "<p>O que fica guardado neste aparelho: só o modelo" + (tamanho ? ", " + esc(tamanho) + " baixados uma vez" +
        " (alguns minutos numa rede boa)" : "") + ". A pergunta, os trechos e a resposta não ficam.</p>" +
      "<p><b>O que não dá para garantir:</b> um aparelho com vírus ou uma extensão maliciosa no navegador pode ler o que a página mostra. " +
      "Isso já vale hoje, só por ver os documentos pelo acesso de fora. Escrever aqui não aumenta esse risco, mas também não o elimina.</p></div>",
    confirmar: "Entendi",
  });
  if (!r || !r.ok) return false;
  guardarPrefsDoAparelho({ entendi: true });
  return true;
}

/* -------------------------------------- antes de mandar: onde escrever */

async function modeloGuardadoNoAparelho(sha) {
  const saida = { partes: 0, bytes: 0 };
  try {
    if (!(await caches.has("paulus-modelo"))) return saida;
    const c = await caches.open("paulus-modelo");
    for (const req of await c.keys()) {
      if (sha && !req.url.includes("/" + sha + "/")) continue;
      const resp = await c.match(req);
      saida.partes += 1;
      saida.bytes += Number((resp && resp.headers.get("content-length")) || 0);
    }
  } catch (err) { /* sem Cache Storage: nada guardado */ }
  return saida;
}

async function pedirSugestaoDoAparelho(envio, o) {
  const t = prefsDoAparelho().teste || {};
  const guardado = await modeloGuardadoNoAparelho(t.sha);
  try {
    const r = await fetch("/api/aparelho/sugestao", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apenas: (envio && envio.apenas) || [], inteiro: Boolean(o && o.inteiro),
        tokens_por_segundo: t.tokens_por_segundo || null, leitura_tps: t.leitura_tps || null, carregou_s: t.carregou_s || null,
        carregado: Boolean(motorAparelho.carregado), baixado: guardado.partes > 0 }),
    });
    return r.ok ? await r.json() : null;
  } catch (err) { return null; }
}

/* O que vai no corpo da pergunta: {aparelho: true} ou {escolha: "..."}.
   Nunca decide sozinho que pode: o servidor confere de novo. */
async function ondeEscrever(o, envio, sinal) {
  if (!aparelhoDisponivel() || (o && o.retomar)) return {};
  const p = prefsDoAparelho();
  const modo = p.modo || "escritorio";
  if (modo === "escritorio" && p.semSugestaoAte === hojeNoAparelho()) return { escolha: "escritorio" };
  const sug = await pedirSugestaoDoAparelho(envio, o);
  if (!sug || !sug.pode) return modo === "escritorio" ? { escolha: "escritorio" } : { aparelho: true };
  if (!sug.vai_ao_aparelho) return { escolha: /caso/.test(sug.motivo_do_escritorio || "") ? "caso" : "inteiro" };
  if (modo === "aparelho") return { aparelho: true };
  if (modo === "automatico") return sug.automatico === "aparelho" ? { aparelho: true, escolha: "automatico" } : { escolha: "automatico" };
  if (!sug.sugerir) return { escolha: "escritorio" };
  const r = await janelaDeSugestao(sug, sinal);
  if (r === "aparelho" && (await avisoDaPrimeiraVez())) return { aparelho: true };
  if (r === "hoje") guardarPrefsDoAparelho({ semSugestaoAte: hojeNoAparelho() });
  return { escolha: "fila" };
}

function esperaEmPalavras(s) {
  return s >= 90 ? "~" + Math.round(s / 60) + " min" : "~" + Math.max(5, Math.round(s / 5) * 5) + " s";
}

/* A janela pequena, não bloqueante, em cima do campo (§3). Resolve com
   "aparelho", "fila" ou "hoje"; a pessoa parar a resposta resolve "fila". */
function janelaDeSugestao(sug, sinal) {
  return new Promise((resolver) => {
    const velha = $("aparelho-sugestao");
    if (velha) velha.remove();
    const e = sug.escritorio || {};
    const frente = e.na_frente ? (e.na_frente === 1 ? "1 na sua frente" : e.na_frente + " na sua frente") : "";
    const espera = e.sabe && e.espera_s ? esperaEmPalavras(e.espera_s) : "";
    const caixa = document.createElement("div");
    caixa.id = "aparelho-sugestao";
    caixa.className = "aparelho-sugestao";
    caixa.setAttribute("role", "dialog");
    caixa.setAttribute("aria-live", "polite");
    caixa.innerHTML = '<p><b>O escritório está respondendo outras perguntas</b>' +
      (frente || espera ? " (" + [frente, espera].filter(Boolean).join(", ") + ")" : "") + ". " +
      "Responder com este aparelho?" + (sug.aparelho_s ? " " + esperaEmPalavras(sug.aparelho_s) : "") +
      (!sug.baixado && sug.modelo && sug.modelo.bytes ? " · baixa o modelo (" + esc(tamanhoDoModelo(sug.modelo.bytes)) + ") antes" : "") + "</p>" +
      '<div class="aparelho-sugestao-botoes">' +
      '<button class="primario" data-sugestao="aparelho">' + ic("desktop_windows", 16) + "Usar este aparelho</button>" +
      '<button data-sugestao="fila">' + ic("schedule", 16) + "Esperar na fila</button>" +
      '<button class="sv-ligacao" data-sugestao="hoje">Não sugerir de novo hoje</button></div>';
    const cartao = $("cartao-campo");
    if (cartao) cartao.appendChild(caixa);
    else document.body.appendChild(caixa);
    const fechar = (valor) => { caixa.remove(); resolver(valor); };
    caixa.querySelectorAll("[data-sugestao]").forEach((b) => { b.onclick = () => fechar(b.dataset.sugestao); });
    if (sinal) sinal.addEventListener("abort", () => fechar("fila"), { once: true });
    const primeiro = caixa.querySelector("[data-sugestao]");
    if (primeiro) primeiro.focus();
  });
}

/* -------------------------------------- a resposta escrita aqui */

async function mandarAoPacote(ev, acao, corpo, fica) {
  try {
    return await fetch("/api/aparelho/pacote/" + encodeURIComponent(ev.pacote) + "/" + acao, {
      method: "POST", headers: { "Content-Type": "application/json" }, keepalive: Boolean(fica),
      body: JSON.stringify(Object.assign({ assinatura: ev.assinatura }, corpo || {})),
    });
  } catch (err) { return null; }
}

/* O evento "aparelho" da resposta: pega o pacote (uma vez, desta sessão),
   escreve, manda pedaços enquanto escreve e devolve. Falhou: abandona com o
   que já tinha, e o escritório termina. `v`: o texto e a linha da resposta. */
async function escreverPacoteNoAparelho(ev, v) {
  if (!ev || !ev.pacote || aparelhoTela.escrevendo) return;
  let r;
  try { r = await fetch("/api/aparelho/pacote/" + encodeURIComponent(ev.pacote) + "?assinatura=" + encodeURIComponent(ev.assinatura)); }
  catch (err) { return; }
  // 409: já entregue (a conversa foi reaberta no meio); 410: venceu. O escritório cuida.
  if (!r.ok) return;
  let pacote = await r.json();
  const vivo = { ev: ev, parcial: "" };
  aparelhoTela.escrevendo = vivo;
  let ultimo = 0;
  if (v && v.linha) v.linha("Escrevendo neste aparelho…");
  if (v && v.anotar) v.anotar("o escritório mandou " + ((pacote.trechos || []).length) + " trecho(s); este aparelho escreve");
  try {
    const texto = await escreverNoAparelho(pacote.mensagens, pacote.parametros, (a) => {
      if (a.fase === "escrevendo") {
        vivo.parcial = a.texto || "";
        if (v && v.texto && aparelhoTela.escrevendo === vivo) v.texto.textContent = vivo.parcial;
        if (Date.now() - ultimo > 1500) { ultimo = Date.now(); mandarAoPacote(ev, "pedaco", { texto: vivo.parcial }); }
      } else if (a.fase === "baixando" && v && v.linha) v.linha("Baixando o modelo para este aparelho" + (a.partes ? " · parte " + a.parte + " de " + a.partes : "") + "…");
      else if ((a.fase === "carregando" || a.fase === "conferindo") && v && v.linha) v.linha("Preparando o modelo neste aparelho…");
    });
    pacote = null;
    if (aparelhoTela.escrevendo !== vivo) return;
    if (v && v.linha) v.linha("Conferindo no escritório…");
    await mandarAoPacote(ev, "devolver", { texto: texto });
  } catch (err) {
    pacote = null;
    if (aparelhoTela.escrevendo === vivo) await mandarAoPacote(ev, "abandonar", { parcial: vivo.parcial });
  } finally {
    if (aparelhoTela.escrevendo === vivo) aparelhoTela.escrevendo = null;
  }
}

/* O evento "aparelho_fim": onde a resposta ficou. Se o escritório assumiu,
   o que o aparelho ainda escrevesse não serve mais. */
function fimDoAparelho(dados, v) {
  const vivo = aparelhoTela.escrevendo;
  if (dados.onde !== "aparelho") {
    if (vivo) { aparelhoTela.escrevendo = null; pararNoAparelho(); }
    if (v && v.texto && !dados.continuou) v.texto.textContent = "";
    if (v && v.anotar) v.anotar((dados.continuou ? "o escritório continuou do que o aparelho escreveu" : "o escritório escreveu") +
      (dados.motivo ? " · " + dados.motivo : ""), "atencao");
    if (v && v.linha) v.linha("Escrevendo no escritório…");
  } else if (v && v.anotar) v.anotar("escrito neste aparelho e conferido no escritório", "feito");
}

function pararEscritaNoAparelho() {
  const vivo = aparelhoTela.escrevendo;
  if (!vivo) return;
  aparelhoTela.escrevendo = null;
  pararNoAparelho();
}

/* A aba fechando no meio: avisa o escritório, que termina do que já chegou.
   Sem este aviso, ele termina do mesmo jeito depois de 45 s sem sinal. */
window.addEventListener("pagehide", () => {
  const vivo = aparelhoTela.escrevendo;
  if (!vivo) return;
  aparelhoTela.escrevendo = null;
  mandarAoPacote(vivo.ev, "abandonar", { parcial: vivo.parcial }, true);
});

/* Onde a resposta foi escrita, em linguagem simples (§3). */
function fraseDaEscrita(e) {
  if (!e || !e.onde) return "";
  const aqui = acessoDeFora.local ? "no aparelho de quem perguntou" : "neste aparelho";
  const partes = e.partes || [];
  if (partes.length === 2 && partes[0].onde === "aparelho") {
    return "começou " + aqui + " e o escritório terminou" + (e.motivo ? " · " + e.motivo : "");
  }
  if (e.onde === "aparelho") {
    return (e.automatico ? "no automático, " : "") + "escrita " + aqui + (e.modelo ? " · " + e.modelo : "") + " · conferida no escritório";
  }
  return "escrita no escritório" + (e.motivo ? " · " + e.motivo : "");
}

/* ---------------------------------------- Minha conta › Este aparelho */

async function fazerTesteDoAparelho(andamento) {
  const r = await testarCapacidadeDoAparelho(andamento);
  const lento = r.passa && (!r.tokens_por_segundo || r.tokens_por_segundo < APARELHO_MINIMO_TPS);
  const teste = {
    passou: Boolean(r.passa && !lento),
    motivo: lento ? "este aparelho escreve devagar demais (" + String(r.tokens_por_segundo || 0).replace(".", ",") + " palavras por segundo)" : (r.motivo || ""),
    tokens_por_segundo: r.tokens_por_segundo || null, leitura_tps: r.leitura_tps || null, carregou_s: r.carregou_s || null,
    quando: new Date().toISOString(), sha: motorAparelho.carregado || "",
  };
  guardarPrefsDoAparelho({ teste: teste });
  desenharSeletorDoAparelho();
  return teste;
}

async function apagarModeloDesteAparelho() {
  try { await apagarModeloDoAparelho(); } catch (err) { try { await caches.delete("paulus-modelo"); } catch (e) { /* já não há */ } }
  guardarPrefsDoAparelho({ teste: null, modo: "escritorio" });
  desenharSeletorDoAparelho();
}

async function htmlDoAparelho() {
  const e = aparelhoTela.estado || {};
  const t = prefsDoAparelho().teste;
  const guardado = await modeloGuardadoNoAparelho(t && t.sha);
  const linha = (k, val) => '<div class="aparelho-linha"><span>' + esc(k) + "</span><b>" + esc(val) + "</b></div>";
  let teste;
  if (!t) teste = "ainda não fiz";
  else if (t.passou) teste = "passou · " + String(t.tokens_por_segundo || 0).replace(".", ",") + " palavras por segundo";
  else teste = "não passou · " + (t.motivo || "");
  return '<div class="aparelho-config">' +
    (e.pode ? "" : '<p class="aparelho-nota">' + esc(e.motivo || "a escrita no aparelho não está liberada para a sua conta") + ".</p>") +
    linha("Teste de capacidade", teste) +
    linha("Modelo guardado aqui", guardado.partes ? tamanhoDoModelo(guardado.bytes) + " · " + (e.modelo || "") : "nenhum") +
    (t && !t.passou && /WebGPU/.test(t.motivo || "") ? '<p class="aparelho-nota">A maioria dos celulares ainda não tem WebGPU; ' +
      "o Edge e o Chrome de computador têm.</p>" : "") +
    '<div class="aparelho-config-botoes">' +
    (e.pode ? '<button data-aparelho-acao="testar">' + ic("speed", 16) + (t ? "Fazer o teste de novo" : "Fazer o teste") + "</button>" : "") +
    (guardado.partes || t ? '<button class="perigo" data-aparelho-acao="apagar">' + ic("delete", 16) + "Apagar o modelo deste aparelho</button>" : "") +
    "</div>" +
    (e.pode && !t ? '<p class="aparelho-nota">O teste baixa o modelo' + (e.bytes ? " (" + esc(tamanhoDoModelo(e.bytes)) + ")" : "") +
      " e mede a velocidade num texto de exemplo, sem nada do escritório. Ao escritório vão só os números.</p>" : "") +
    '<p class="aparelho-andamento" id="aparelho-andamento" hidden></p></div>';
}

async function configuracoesDoAparelho() {
  if (!aparelhoTela.estado) await lerEstadoDoAparelho();
  const aberto = dialogo({ titulo: "Este aparelho", contexto: "Escrever as respostas aqui", html: await htmlDoAparelho(),
    confirmar: "Fechar", semCancelar: true, classe: "aparelho-dialogo" });
  const ligar = () => document.querySelectorAll("[data-aparelho-acao]").forEach((b) => {
    b.onclick = async () => {
      const andamento = $("aparelho-andamento");
      const dizer = (txt) => { if (andamento) { andamento.hidden = false; andamento.textContent = txt; } };
      b.disabled = true;
      try {
        if (b.dataset.aparelhoAcao === "testar") {
          dizer("Conferindo o aparelho…");
          const t = await fazerTesteDoAparelho((a) => {
            if (a.fase === "baixando") dizer("Baixando o modelo" + (a.partes ? " · parte " + a.parte + " de " + a.partes : "") + "…");
            else if (a.fase === "conferindo") dizer("Conferindo o modelo pelo hash…");
            else if (a.fase === "carregando") dizer("Carregando o modelo…");
            else if (a.fase === "sem_espaco") dizer("O navegador não deixou guardar o modelo: ele vai ser baixado de novo a cada vez.");
          });
          dizer(t.passou ? "Passou. O seletor aparece embaixo do campo da pergunta." : "Não passou: " + t.motivo + ".");
        } else {
          dizer("Apagando…");
          await apagarModeloDesteAparelho();
          dizer("Apaguei o modelo deste aparelho.");
        }
      } catch (err) {
        dizer("Não deu: " + ((err && err.message) || err));
      }
      const corpo = document.querySelector(".aparelho-config");
      if (corpo) {
        const fala = andamento ? andamento.textContent : "";
        corpo.outerHTML = await htmlDoAparelho();
        const novo = $("aparelho-andamento");
        if (novo && fala) { novo.hidden = false; novo.textContent = fala; }
        ligar();
      }
    };
  });
  ligar();
  await aberto;
}

lerEstadoDoAparelho();
