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

/* A tela inteira (Processos › Andamentos no DataJud), no desenho de Configuracoes:
   resumo com pontos de estado e um cartao para cada coisa. A aba do Servico
   continua compacta (htmlDosProcessos com servicoId). */
function telaDosProcessos(d) {
  const ps = d.processos || [];
  const local = acessoDeFora.local;
  const novas = ps.reduce((n, p) => n + (p.novas || 0), 0);
  const acompanhados = ps.filter((p) => p.acompanhar).length;
  const ultima = d.ultima ? d.ultima.slice(0, 10).split("-").reverse().join("/") : "";
  const st = (t, classe) => '<b class="cfg-st ' + classe + '">' + esc(t) + "</b>";
  const item = (rot, v) => '<div class="sv-ficha-item"><span class="sv-kicker">' + rot + "</span>" + v + "</div>";
  const ficha = '<div class="sv-ficha cfg-ficha">' +
    item("Acompanhamento", d.acompanhar ? st("Ativado", "ok") : st("Desativado", "cfg-mudo")) +
    item("Processos", ps.length ? st(acompanhados + " de " + ps.length + " acompanhados", acompanhados ? "ok" : "cfg-mudo") : st("Nenhum ainda", "cfg-mudo")) +
    item("Movimentações novas", novas ? st(novas === 1 ? "1 nova" : novas + " novas", "acc") : st("Nenhuma", "cfg-mudo")) +
    item("Última consulta", ultima ? "<b>" + esc(ultima) + "</b>" : st("Nunca", "cfg-mudo")) + "</div>";

  const liga = local ? cartaoCfg("Acompanhamento", metaCfg("uma vez por dia"),
    '<div class="ag-toggle' + (d.acompanhar ? " on" : "") + '" data-pr-ligar="1">' +
    '<span class="duas-linhas"><b>Consultar o DataJud todo dia</b><small>Só o número de cada processo acompanhado sai deste computador, para a API pública do CNJ.</small></span><i></i></div>' +
    (d.acompanhar ? '<div class="cfg-botoes cfg-botoes-fim"><button class="com-icone" data-pr-rodar="1">' + ic("sync", 16) + "Consultar todos agora</button></div>" : "")) : "";

  const acoes = local ? '<div class="cfg-acoes-topo"><button class="com-icone" data-pr-descobrir="1">' + ic("search", 16) + "Achar nos documentos</button>" +
    '<button class="primario com-icone" data-pr-novo="1">' + ic("add", 16) + "Adicionar número</button></div>" : "";
  const lista = ps.length ? '<div class="pr-lista">' + ps.map((p) => linhaDoProcesso(p, true)).join("") + "</div>"
    : '<p class="apt-vazio">' + ic("gavel", 18) + "<span>Nenhum processo ainda." + (local ? " “Achar nos documentos” traz os números que a leitura já validou." : "") + "</span></p>";
  const processos = cartaoCfg("Processos", metaCfg(ps.length ? (ps.length === 1 ? "1 processo" : ps.length + " processos") : "nenhum"), lista);

  const prazo = cartaoCfg("Quando chega uma intimação", metaCfg("o prazo é sugestão"),
    '<p class="cfg-explica">Movimentação nova aparece nos avisos. Intimação, citação ou publicação vira um pedido em Aprovações, com o prazo contado pelo ato que ela comunica. ' +
    "Sem reconhecer o ato, o Paulus sugere 15 dias úteis. Confira sempre o ato e a data da ciência.</p>");
  return '<div class="cfg-secao pr-secao">' + ficha + liga + acoes + processos + prazo + "</div>";
}

function htmlDosProcessos(d, servicoId) {
  if (!servicoId) return telaDosProcessos(d);
  // A aba do Servico traz o que faz sentido da tela Andamentos no DataJud:
  // o resumo, os processos deste servico (com acompanhar, achar e adicionar) e o que acontece numa intimacao.
  const ps = d.processos || [];
  const local = acessoDeFora.local;
  const novas = ps.reduce((n, p) => n + (p.novas || 0), 0);
  const acompanhados = ps.filter((p) => p.acompanhar).length;
  const ultima = d.ultima ? d.ultima.slice(0, 10).split("-").reverse().join("/") : "";
  const st = (t, classe) => '<b class="cfg-st ' + classe + '">' + esc(t) + "</b>";
  const item = (rot, val) => '<div class="sv-ficha-item"><span class="sv-kicker">' + rot + "</span>" + val + "</div>";
  const ficha = '<div class="sv-ficha cfg-ficha">' +
    item("Acompanhamento", d.acompanhar ? st("Ativado", "ok") : st("Desativado", "cfg-mudo")) +
    item("Processos deste serviço", ps.length ? st(acompanhados + " de " + ps.length + " acompanhados", acompanhados ? "ok" : "cfg-mudo") : st("Nenhum ainda", "cfg-mudo")) +
    item("Movimentações novas", novas ? st(novas === 1 ? "1 nova" : novas + " novas", "acc") : st("Nenhuma", "cfg-mudo")) +
    item("Última consulta", ultima ? "<b>" + esc(ultima) + "</b>" : st("Nunca", "cfg-mudo")) + "</div>";

  const cab = '<div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + ic("gavel", 16) + "Processos</span>" +
    '<span class="sv-secao-meta">' + (ps.length ? (ps.length === 1 ? "1 processo" : ps.length + " processos") : "nenhum") + "</span></div>";
  const liga = local ? '<div class="pr-aba-liga"><div class="ag-toggle' + (d.acompanhar ? " on" : "") + '" data-pr-ligar="1">' +
    '<span class="duas-linhas"><b>Consultar o DataJud todo dia</b><small>' + (d.acompanhar ? "Vale para todos os processos do escritório." : "Só o número de cada processo sai deste computador, para a API pública do CNJ.") + "</small></span><i></i></div></div>" : "";
  const lista = ps.length ? '<div class="pr-lista pr-aba-lista">' + ps.map((p) => linhaDoProcesso(p, false)).join("") + "</div>"
    : '<p class="apt-vazio pr-aba-vazio">' + ic("gavel", 18) + "<span>Nenhum processo neste serviço ainda." + (local ? " “Achar nos documentos” traz os números que a leitura já validou." : "") + "</span></p>";
  const botoes = local ? '<div class="cfg-botoes pr-aba-novo"><button type="button" class="com-icone" data-pr-descobrir="1">' + ic("search", 16) + "Achar nos documentos</button>" +
    '<button type="button" class="com-icone" data-pr-novo="1">' + ic("add", 16) + "Adicionar número</button>" +
    (d.acompanhar ? '<button type="button" class="com-icone" data-pr-rodar="1">' + ic("sync", 16) + "Consultar agora</button>" : "") + "</div>" : "";
  const processos = '<section class="sv-secao">' + cab + liga + lista + botoes + "</section>";

  const intimacao = '<section class="sv-secao"><div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + ic("notifications", 16) + "Quando chega uma intimação</span>" +
    '<span class="sv-secao-meta">o prazo é sugestão</span></div>' +
    '<p class="sv-dica pr-aba-dica">Movimentação nova aparece nos avisos. Intimação, citação ou publicação vira um pedido em Aprovações, com o prazo contado pelo ato que ela comunica. ' +
    "Sem reconhecer o ato, o Paulus sugere 15 dias úteis. Confira sempre o ato e a data da ciência.</p></section>";
  return ficha + processos + intimacao;
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
  $("conversa-titulo").textContent = "Andamentos no DataJud";
  $("conversa-meta").textContent = "os processos do escritório, consultados no CNJ";
  $("acoes-tela").innerHTML = '<button class="com-icone" data-pr-voltar="1">' + ic("arrow_back", 16) + "Processos</button>";
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
      (d.prazos_propostos ? " · " + plural(d.prazos_propostos, "prazo", "prazos") + " em Aprovações" : "") +
      (d.erros ? " · " + plural(d.erros, "sem resposta do DataJud", "sem resposta do DataJud") + " (o motivo fica no processo)" : ""), { tom: d.erros ? "erro" : "ok" });
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
    (local || p.orgao_codigo ? '<button data-pr-perfil="1">' + ic("bar_chart", 16) + "Perfil da vara</button>" : "") +
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
  const perfil = document.querySelector("[data-pr-perfil]");
  if (perfil) perfil.onclick = () => { if (dialogoAberto) dialogoAberto.fechar(null); setTimeout(() => abrirPerfilDaVara(id, depois), 50); };
  const apagar = document.querySelector("[data-pr-apagar]");
  if (apagar) apagar.onclick = async () => { if (await acao("/api/processos/" + id, "DELETE", null, "Processo tirado da lista.")) { if (dialogoAberto) dialogoAberto.fechar(null); } };
  await aberto;
  if (typeof depois === "function") depois();
}

/* O perfil da vara: o retrato do órgão julgador no DataJud (contagens) e o
   tempo até a sentença numa amostra da mesma classe. Guardado 30 dias; quem
   está de fora vê o guardado, mas não tira outro. */
const PR_GRAUS = { G1: "1º grau", G2: "2º grau", JE: "Juizado Especial", TR: "Turma Recursal", SUP: "Tribunal superior" };

function prBarras(lista, nome) {
  const max = Math.max(1, ...lista.map((x) => x.qtd));
  return '<div class="pr-barras">' + lista.map((x) =>
    '<div class="pr-barra"><span>' + esc(nome ? nome(x.nome) : x.nome) + "</span><b>" + x.qtd.toLocaleString("pt-BR") + "</b>" +
    '<i style="width:' + Math.round(100 * x.qtd / max) + '%"></i></div>').join("") + "</div>";
}

function prTempo(t) {
  if (!t) return "";
  const meses = (d) => (d < 60 ? d + " dias" : "cerca de " + Math.round(d / 30.4) + " meses");
  let texto;
  if (!t.amostra) {
    texto = "Não achei processos de " + esc(t.classe || "mesma classe") + " distribuídos nesta vara de " + t.de + " a " + t.ate + " para medir o tempo.";
  } else if (t.com_sentenca < 5) {
    texto = "Olhei " + plural(t.amostra, "processo", "processos") + " de " + esc(t.classe) + " distribuídos de " + t.de + " a " + t.ate +
      ", e só " + t.com_sentenca + " tiveram sentença: pouco para dizer um tempo.";
  } else {
    texto = "Olhei " + plural(t.amostra, "processo", "processos") + " de " + esc(t.classe) + " distribuídos nesta vara de " + t.de + " a " + t.ate +
      (t.populacao > t.amostra ? " (de " + t.populacao.toLocaleString("pt-BR") + " no período)" : "") + "; " + t.com_sentenca +
      " já tiveram sentença. Metade deles teve a sentença em até <b>" + meses(t.mediana) + "</b>; a metade do meio, entre " +
      meses(t.q1) + " e " + meses(t.q3) + ".";
  }
  return '<h4 class="pr-sub">Tempo até a sentença</h4><p class="cfg-explica">' + texto + "</p>" +
    (t.com_sentenca >= 5 ? '<p class="cfg-explica pr-nota">Os que ainda esperam a sentença ficam fora da conta, então o tempo real tende a ser maior. ' +
      "A sentença é reconhecida pela movimentação registrada no DataJud (procedência, improcedência, homologação, extinção).</p>" : "");
}

async function abrirPerfilDaVara(id, depois) {
  const voltar = () => setTimeout(() => abrirProcesso(id, depois), 50);
  let r = await fetch("/api/processos/" + id + "/perfil");
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); voltar(); return; }
  let d = await r.json();
  const local = acessoDeFora.local;
  const tirar = async () => {
    avisoCert("Consultando o DataJud… o perfil de uma vara grande pode levar alguns minutos.", { tom: "ok" });
    const x = await fetch("/api/processos/" + id + "/perfil", { method: "POST" });
    if (!x.ok) { avisoCert(await erroDe(x), { tom: "erro" }); return null; }
    return x.json();
  };
  if (!d.perfil) {
    if (!local) { avisoCert("O perfil desta vara ainda não foi tirado; quem está no computador do escritório pode tirar.", { tom: "ok" }); voltar(); return; }
    d = await tirar();
    if (!d) { voltar(); return; }
  }
  const p = d.perfil;
  const html = '<div class="pr-detalhe pr-perfil"><p class="cfg-explica"><b>' + esc(p.orgao || "Vara") + "</b> · " + esc(p.tribunal) + "<br>" +
    p.total.toLocaleString("pt-BR") + " processos desta vara no DataJud, contando os arquivados.</p>" +
    (p.graus.length > 1 ? prBarras(p.graus, (g) => PR_GRAUS[g] || g) : "") +
    '<h4 class="pr-sub">Distribuídos por ano</h4>' + prBarras(p.por_ano, (a) => (String(a) === String(new Date().getFullYear()) ? a + " (até agora)" : a)) +
    '<h4 class="pr-sub">Classes mais comuns</h4>' + prBarras(p.classes) +
    '<h4 class="pr-sub">Assuntos mais comuns</h4>' + prBarras(p.assuntos) +
    prTempo(p.tempo) +
    '<p class="cfg-explica pr-nota">Fonte: DataJud, API pública do CNJ, consultado em ' + esc(dataBr(String(d.guardado_em || "").slice(0, 10))) +
    (d.vencido ? " (tem mais de 30 dias)" : "") + ". Só os códigos da vara e da classe saíram deste computador.</p></div>";
  const fim = await dialogo({ titulo: "Perfil da vara", contexto: "Processos", html: html, confirmar: "Voltar ao processo", semCancelar: true,
    classe: "pr-dialogo", segundo: local ? { rotulo: "Atualizar" } : null });
  if (fim && fim.segundo) {
    const novo = await tirar();
    if (novo) { setTimeout(() => abrirPerfilDaVara(id, depois), 50); return; }
  }
  voltar();
}

document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest("[data-pr-tela]");
  if (b) { e.preventDefault(); mostrarProcessos(); }
});
