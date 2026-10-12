/* CONSUMO DA CONVERSA (pedido de 11/10/2026): no painel lateral, embaixo de
   Propriedades, o que esta conversa gastou do modelo - entrada e saida - e a
   BARRA DE CONTEXTO: quanto da janela do modelo a conversa ja ocupa. Cheia,
   a conversa e compactada sozinha (o historico vira um resumo); o botao a
   direita compacta na hora. Compactar diz quantos tokens economizou.
   Vem de `uso` no trabalho (/api/trabalhos/<id>): entrada, saida, respostas,
   contexto (tokens que a proxima pergunta leva) e janela (o limite). */
(function () {
  const props = document.getElementById("lat-propriedades");
  if (!props || document.getElementById("lat-consumo")) return;
  // Duas setas que se encontram no meio: o que estava espalhado fica menor.
  const ICONE_COMPACTAR = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M13.25 2.75 9.5 6.5"/><path d="M9.5 3.25V6.5h3.25"/><path d="M2.75 13.25 6.5 9.5"/><path d="M6.5 12.75V9.5H3.25"/></svg>';
  const bloco = document.createElement("section");
  bloco.className = "lateral-bloco";
  bloco.id = "lat-consumo";
  bloco.hidden = true;
  bloco.innerHTML =
    '<button class="lateral-cabeca" aria-expanded="true"><b>Consumo da conversa</b><span class="ic lado-seta">expand_more</span></button>' +
    '<div class="propriedades lat-consumo">' +
    '<div><span>Entrada</span><span class="valor-prop mono" data-cs="entrada">—</span></div>' +
    '<div><span>Saída</span><span class="valor-prop mono" data-cs="saida">—</span></div>' +
    '<div><span>Contexto</span><span class="valor-prop mono" data-cs="contexto">—</span></div>' +
    '<div class="lat-contexto">' +
      '<div class="lat-contexto-linha"><div class="lat-contexto-barra" role="progressbar" aria-label="Contexto usado" aria-valuemin="0" aria-valuemax="100"><i data-cs="barra"></i></div>' +
      '<button type="button" class="botao-icone lat-compactar" data-cs="compactar" title="Compactar a conversa agora" aria-label="Compactar a conversa">' + ICONE_COMPACTAR + "</button></div>" +
      '<p class="lat-consumo-nota" data-cs="nota-contexto"></p>' +
    "</div>" +
    '<p class="lat-consumo-nota" data-cs="nota"></p></div>';
  props.after(bloco);
  const cabeca = bloco.querySelector(".lateral-cabeca");
  cabeca.onclick = () => {
    const aberto = cabeca.getAttribute("aria-expanded") !== "false";
    cabeca.setAttribute("aria-expanded", String(!aberto));
    bloco.classList.toggle("fechado", aberto);
  };
  const num = (n) => Number(n || 0).toLocaleString("pt-BR");
  const mil = (n) => (n >= 1000 ? (Math.round(n / 100) / 10).toLocaleString("pt-BR") + " mil" : String(n));
  const campo = (k) => bloco.querySelector('[data-cs="' + k + '"]');
  const compactando = new Set();
  let assinatura = "";

  async function compactar(t, sozinha) {
    if (!t || compactando.has(t.id)) return;
    const u = t.uso;
    compactando.add(t.id);
    assinatura = "";
    bloco.classList.add("compactando");
    desenhar();
    let d = {};
    try {
      const r = await fetch("/api/trabalhos/" + t.id + "/compactar", { method: "POST" });
      if (r.ok) d = await r.json();
    } catch (err) { /* sem servidor: a conta abaixo */ }
    await new Promise((ok) => setTimeout(ok, 900));
    if (!d.depois) {
      // Sem a resposta do servidor nao ha numero medido: nada de economia estimada.
      compactando.delete(t.id);
      bloco.classList.remove("compactando");
      desenhar();
      if (typeof avisoNaJanela === "function") avisoNaJanela("Não consegui compactar a conversa agora.", { icone: "error" });
      return;
    }
    const antes = d.antes || u.contexto || 0;
    const depois = d.depois;
    const economia = Math.max(0, antes - depois);
    u.contexto = depois;
    u.compactada = { economia: economia, sozinha: Boolean(sozinha), em: Date.now() };
    compactando.delete(t.id);
    bloco.classList.remove("compactando");
    assinatura = "";
    desenhar();
    const texto = (sozinha ? "O contexto encheu e a conversa foi compactada" : "Conversa compactada") + " · " + num(economia) + " tokens economizados";
    if (typeof avisoNaJanela === "function") avisoNaJanela(texto, { icone: "check_circle" });
  }
  campo("compactar").onclick = () => compactar(estado.trabalho, false);

  function desenhar() {
    const t = typeof estado !== "undefined" && estado.trabalho;
    const u = t && t.uso;
    if (!u) { bloco.hidden = true; assinatura = ""; return; }
    const ocupado = compactando.has(t.id);
    const chave = [t.id, u.entrada, u.saida, u.contexto, u.janela, t.estado, ocupado, u.compactada && u.compactada.em].join(":");
    if (chave === assinatura) return;
    assinatura = chave;
    bloco.hidden = false;
    campo("entrada").textContent = num(u.entrada) + " tokens";
    campo("saida").textContent = t.estado === "executando" && !u.saida ? "escrevendo…" : num(u.saida) + " tokens";
    const janela = u.janela || 0;
    const usado = u.contexto != null ? u.contexto : (u.entrada || 0) + (u.saida || 0);
    const pct = janela ? Math.min(100, (usado / janela) * 100) : 0;
    campo("contexto").textContent = janela ? mil(usado) + " de " + mil(janela) : num(usado) + " tokens";
    const barra = campo("barra");
    barra.style.width = pct.toFixed(1) + "%";
    barra.parentElement.setAttribute("aria-valuenow", String(Math.round(pct)));
    barra.parentElement.classList.toggle("perto", pct >= 80);
    const botao = campo("compactar");
    botao.disabled = ocupado || usado < 1000 || t.estado === "executando";
    const notaCtx = campo("nota-contexto");
    if (ocupado) notaCtx.textContent = "Compactando: o histórico vira um resumo…";
    else if (u.compactada) notaCtx.textContent = (u.compactada.sozinha ? "Compactada sozinha" : "Compactada") + " · " + num(u.compactada.economia) + " tokens economizados";
    else if (janela) notaCtx.textContent = Math.round(pct) + "% da janela do modelo · ao encher, a conversa é compactada";
    else notaCtx.textContent = "";
    const respostas = u.respostas || 0;
    campo("nota").textContent = (respostas ? (respostas === 1 ? "1 resposta" : respostas + " respostas") + " · " : "") +
      (u.nuvem ? "na nuvem, conta do plano" : "neste computador, sem custo por token");
    // Cheia, compacta sozinha - uma vez, e nunca no meio de uma resposta.
    if (janela && usado >= janela && !ocupado && t.estado !== "executando") compactar(t, true);
  }
  setInterval(desenhar, 800);
  desenhar();
})();
