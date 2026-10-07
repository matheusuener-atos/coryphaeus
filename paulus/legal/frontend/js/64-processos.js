/* ------------------------------------------ processos pelo DataJud (L2) */
/*
   A tela Processos (a partir de Serviços), a aba Processos de cada Serviço
   e o detalhe de um processo com as movimentações (src/processos.py).

   Acompanhar pelo DataJud vem desligado: ligado, uma vez por dia o Paulus
   manda só o número de cada processo acompanhado à API pública do CNJ.
   Movimentação nova vira aviso; intimação, citação ou publicação vira um
   pedido em Aprovações com a conta do prazo pelo tipo de ato (N1) - sugestão,
   nunca tarefa sozinha.
*/

const proc = { dados: null, servicos: [] };

function linhaDoProcesso(p, comServico) {
  const estado_ = p.ultimo_erro ? '<span class="pr-erro" title="' + esc(p.ultimo_erro) + '">erro na última consulta</span>'
    : (p.ultima_consulta ? "consultado " + esc(quandoCurto(p.ultima_consulta)) : (p.acompanhar ? "ainda não consultado" : "não acompanhado"));
  return '<div class="pr-linha" data-pr-abrir="' + p.id + '" tabindex="0">' +
    '<span class="duas-linhas"><b>' + esc(p.numero_fmt) + (p.novas ? ' <span class="pr-novas">' + p.novas + (p.novas === 1 ? " nova" : " novas") + "</span>" : "") +
    "</b><small>" + esc([p.tribunal, p.classe, p.orgao].filter(Boolean).join(" · ") || "sem dados do DataJud ainda") + "</small></span>" +
    (comServico ? '<span class="pr-servico">' + esc(p.servico_nome || "sem Serviço") + "</span>" : "") +
    '<span class="pr-estado">' + (p.acompanhar ? ic("task_alt", 14) + " " : "") + estado_ + "</span></div>";
}

function htmlDosProcessos(d, servicoId) {
  const lista = (d.processos || []).map((p) => linhaDoProcesso(p, !servicoId)).join("");
  const local = acessoDeFora.local;
  const cab = local
    ? '<div class="pr-cab"><div class="ag-toggle' + (d.acompanhar ? " on" : "") + '" data-pr-ligar="1">' +
      '<span class="duas-linhas"><b>Acompanhar pelo DataJud</b><small>uma vez por dia; só o número de cada processo acompanhado sai deste computador, ' +
      "para a API pública do CNJ" + (d.ultima ? " · última volta em " + esc(d.ultima.slice(0, 10).split("-").reverse().join("/")) : "") + "</small></span><i></i></div>" +
      '<div class="pr-botoes"><button data-pr-novo="1">' + ic("add", 16) + "Adicionar número</button>" +
      (servicoId ? "" : '<button data-pr-descobrir="1">' + ic("search", 16) + "Achar nos documentos</button>") +
      (d.acompanhar && !servicoId ? '<button data-pr-rodar="1">' + ic("sync", 16) + "Consultar todos agora</button>" : "") + "</div></div>"
    : "";
  return cab + (lista ? '<div class="pr-lista">' + lista + "</div>"
    : '<p class="cfg-explica">' + (servicoId ? "Nenhum processo neste Serviço." : "Nenhum processo ainda.") +
      (local ? " “Achar nos documentos” traz os números que a leitura já validou; eles entram sem acompanhar." : "") + "</p>") +
    '<p class="cfg-explica">Movimentação nova aparece nos avisos. Intimação, citação ou publicação vira um pedido em Aprovações com a conta do prazo ' +
    "pelo ato que ela comunica — a sentença, o acórdão, a decisão ou o despacho de antes, no ramo do processo; sem reconhecer o ato, 15 dias úteis. " +
    "É sugestão: confira o ato e a data da ciência.</p>";
}

async function carregarProcessos(alvo, servicoId) {
  if (!alvo) return;
  try {
    const r = await fetch("/api/processos" + (servicoId ? "?servico_id=" + servicoId : ""));
    if (!r.ok) throw new Error(await erroDe(r));
    proc.dados = await r.json();
  } catch (err) {
    alvo.innerHTML = '<p class="cfg-explica">não consegui abrir os processos: ' + esc(String(err.message || err)) + "</p>";
    return;
  }
  alvo.innerHTML = htmlDosProcessos(proc.dados, servicoId);
  ligarProcessos(alvo, servicoId);
}

async function mostrarProcessos() {
  abrirTela("Processos", { cheia: true });
  marcarDestino("servicos");
  $("conversa-meta").textContent = "acompanhados pelo DataJud";
  $("acoes-tela").innerHTML = '<button class="com-icone" data-pr-voltar="1">' + ic("arrow_back", 16) + "Serviços</button>";
  const voltar = document.querySelector("[data-pr-voltar]");
  if (voltar) voltar.onclick = () => mostrarServicos("pastas");
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal sv-principal"><div class="sv-medida">' +
    '<div id="pr-tela"><p class="nota">abrindo…</p></div></div></div></div>';
  atualizarPostura();
  await carregarProcessos($("pr-tela"), null);
}

function ligarProcessos(alvo, servicoId) {
  const recarregar = () => carregarProcessos(alvo, servicoId);
  alvo.querySelectorAll("[data-pr-abrir]").forEach((el) => {
    el.onclick = () => abrirProcesso(Number(el.dataset.prAbrir), recarregar);
    el.onkeydown = (e) => { if (e.key === "Enter") el.click(); };
  });
  const ligar = alvo.querySelector("[data-pr-ligar]");
  if (ligar) ligar.onclick = async () => {
    const d = await ligarChave("processos", "acompanhar", !ligar.classList.contains("on"));
    if (d) avisoCert(d.processos.acompanhar ? "Acompanhamento ligado: a primeira volta guarda o que já existe, sem avisos." : "Acompanhamento desligado.", { tom: "ok" });
    recarregar();
  };
  const novo = alvo.querySelector("[data-pr-novo]");
  if (novo) novo.onclick = async () => {
    const numero = await perguntar({ titulo: "Adicionar processo", contexto: "Processos",
      texto: "O número único (CNJ), com ou sem pontuação. Ele entra acompanhado.",
      campo: { rotulo: "Número", placeholder: "0000000-00.0000.0.00.0000", icone: "gavel" }, confirmar: "Adicionar" });
    if (!numero) return;
    const r = await fetch("/api/processos", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ numero: numero, servico_id: servicoId || null }) });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    recarregar();
  };
  const descobrir = alvo.querySelector("[data-pr-descobrir]");
  if (descobrir) descobrir.onclick = async () => {
    const r = await fetch("/api/processos/descobrir", { method: "POST" });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const d = await r.json();
    avisoCert(d.novos ? plural(d.novos, "processo novo", "processos novos") + " achado" + (d.novos === 1 ? "" : "s") + " nos documentos, sem acompanhar ainda."
      : "Nenhum número novo nos documentos lidos.", { tom: "ok" });
    recarregar();
  };
  const rodar = alvo.querySelector("[data-pr-rodar]");
  if (rodar) rodar.onclick = async () => {
    rodar.disabled = true;
    avisoCert("Consultando o DataJud… pode levar alguns minutos.", { tom: "ok" });
    const r = await fetch("/api/processos/acompanhar-agora", { method: "POST" });
    rodar.disabled = false;
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const d = await r.json();
    avisoCert(plural(d.consultados, "processo consultado", "processos consultados") + " · " + plural(d.novos, "movimentação nova", "movimentações novas") +
      (d.prazos_propostos ? " · " + plural(d.prazos_propostos, "prazo", "prazos") + " em Aprovações" : ""), { tom: "ok" });
    recarregar();
  };
}

async function abrirProcesso(id, depois) {
  const r = await fetch("/api/processos/" + id);
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  const p = d.processo;
  const movs = (d.movimentos || []).map((m) =>
    '<div class="pr-mov' + (m.visto ? "" : " nova") + '"><span class="pr-mov-quando">' + esc(quandoCurto(m.quando)) + "</span>" +
    '<span class="duas-linhas"><b>' + esc(m.nome) + (m.visto ? "" : ' <span class="pr-novas">nova</span>') + "</b>" +
    (m.complemento ? "<small>" + esc(m.complemento) + "</small>" : "") + "</span></div>").join("");
  // N2: as publicações do DJEN deste processo, com o que houve com o prazo de cada uma.
  const pubs = (d.publicacoes || []).map((u) =>
    '<div class="pr-mov' + (u.lida ? "" : " nova") + '"><span class="pr-mov-quando">' + esc(dataBr(u.data)) + "</span>" +
    '<span class="duas-linhas"><b>' + esc(u.tipo || "Publicação") + " no DJEN" + (u.lida ? "" : ' <span class="pr-novas">nova</span>') + "</b>" +
    "<small>" + esc([u.orgao, u.tarefa_id ? "prazo anotado em Tarefas › Prazos" : (u.pedido_id ? "o prazo espera em Aprovações" : "")].filter(Boolean).join(" · ")) + "</small>" +
    '<small class="pr-pub-texto">' + esc(String(u.texto || "").slice(0, 280)) + (String(u.texto || "").length > 280 ? "…" : "") + "</small></span></div>").join("");
  const local = acessoDeFora.local;
  let servicos = "";
  if (local) {
    try { proc.servicos = ((await (await fetch("/api/servicos?filtro=todos")).json()).servicos || []); } catch (err) { proc.servicos = []; }
    servicos = '<div class="ag-campo"><label>Serviço</label><select data-pr-servico="1"><option value="">sem Serviço</option>' +
      proc.servicos.map((s) => '<option value="' + s.id + '"' + (s.id === p.servico_id ? " selected" : "") + ">" + esc(s.nome) + "</option>").join("") + "</select></div>";
  }
  const html = '<div class="pr-detalhe"><p class="cfg-explica">' + esc([p.tribunal, p.classe, p.orgao].filter(Boolean).join(" · ")) +
    (p.documento ? " · achado em “" + esc(p.documento) + "”" : "") + "</p>" + servicos +
    (local ? '<div class="ag-toggle' + (p.acompanhar ? " on" : "") + '" data-pr-acompanhar="1"><span class="duas-linhas"><b>Acompanhar este processo</b>' +
      "<small>entra na volta diária do DataJud</small></span><i></i></div>" : "") +
    '<div class="pr-botoes">' + (local ? '<button data-pr-consultar="1">' + ic("sync", 16) + "Consultar agora</button>" : "") +
    (p.novas || (d.publicacoes || []).some((u) => !u.lida) ? '<button data-pr-vistos="1">' + ic("check", 16) + "Marcar como vistas</button>" : "") +
    (local ? '<button class="perigo" data-pr-apagar="1">' + ic("delete", 16) + "Tirar da lista</button>" : "") + "</div>" +
    (pubs ? '<h4 class="pr-sub">Publicações no DJEN</h4><div class="pr-movs pr-pubs">' + pubs + "</div>" : "") +
    (pubs ? '<h4 class="pr-sub">Movimentações no DataJud</h4>' : "") +
    '<div class="pr-movs">' + (movs || '<p class="cfg-explica">Nenhuma movimentação guardada ainda.</p>') + "</div></div>";
  const aberto = dialogo({ titulo: "Processo " + p.numero_fmt, contexto: "Processos", html: html, confirmar: "Fechar", semCancelar: true, classe: "pr-dialogo" });
  const acao = async (url, metodo, corpo, frase) => {
    const x = await fetch(url, { method: metodo, headers: { "Content-Type": "application/json" }, body: corpo ? JSON.stringify(corpo) : undefined });
    if (!x.ok) { avisoCert(await erroDe(x), { tom: "erro" }); return null; }
    if (frase) avisoCert(frase, { tom: "ok" });
    return x.json();
  };
  const sel = document.querySelector("[data-pr-servico]");
  if (sel) sel.onchange = () => acao("/api/processos/" + id, "PUT", { servico_id: sel.value ? Number(sel.value) : null, mudar_servico: true }, "Serviço trocado.");
  const ac = document.querySelector("[data-pr-acompanhar]");
  if (ac) ac.onclick = async () => {
    const on = !ac.classList.contains("on");
    if (await acao("/api/processos/" + id, "PUT", { acompanhar: on }, on ? "Este processo entra na volta diária." : "Este processo sai da volta diária.")) ac.classList.toggle("on", on);
  };
  const vistos = document.querySelector("[data-pr-vistos]");
  if (vistos) vistos.onclick = async () => { if (await acao("/api/processos/" + id + "/vistos", "POST", {}, "Marcadas como vistas.")) { if (dialogoAberto) dialogoAberto.fechar(null); } };
  const consultar = document.querySelector("[data-pr-consultar]");
  if (consultar) consultar.onclick = async () => {
    consultar.disabled = true;
    avisoCert("Consultando o DataJud… pode levar um minuto.", { tom: "ok" });
    const x = await acao("/api/processos/" + id + "/consultar", "POST", {}, "");
    consultar.disabled = false;
    if (x) {
      avisoCert(x.erro ? "O DataJud não respondeu: " + x.erro : (x.primeira ? "Primeira consulta: guardei o que já existe." : plural((x.novos || []).length, "movimentação nova", "movimentações novas")), { tom: x.erro ? "erro" : "ok" });
      if (dialogoAberto) dialogoAberto.fechar(null);
      setTimeout(() => abrirProcesso(id, depois), 50);
    }
  };
  const apagar = document.querySelector("[data-pr-apagar]");
  if (apagar) apagar.onclick = async () => { if (await acao("/api/processos/" + id, "DELETE", null, "Processo tirado da lista.")) { if (dialogoAberto) dialogoAberto.fechar(null); } };
  await aberto;
  if (typeof depois === "function") depois();
}

document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest("[data-pr-tela]");
  if (b) { e.preventDefault(); mostrarProcessos(); }
});
