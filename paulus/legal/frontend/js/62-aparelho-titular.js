/* ------------------------------ pensar no aparelho: o que o titular controla (D5) */
/*
   O cartão "Escrever no aparelho" em Configurações › Acesso externo, só na
   janela do escritório (as rotas também só respondem aqui):

   - ligar e desligar para o escritório (a chave aparelho.ligado). Desligar
     para na hora toda resposta que um aparelho estiver escrevendo: ela
     termina aqui;
   - por conta, a liberação fica em Contas › Permissões ("Escrever a
     resposta no próprio aparelho"); o cartão mostra quem está liberado;
   - "só no escritório": clientes, Serviços e pastas cujo conteúdo nunca vai
     para aparelho - a regra vale na montagem do pacote, no servidor;
   - o relatório: por pessoa, quantas respostas foram escritas no aparelho,
     quantas foram refeitas pela conferência e quantas o escritório terminou.
*/

const aparelhoTitular = { chaves: null, marcas: [], servicos: [], clientes: [], relatorio: null, erro: "" };

async function carregarAparelhoTitular() {
  aparelhoTitular.erro = "";
  try {
    const [c, m, r] = await Promise.all([fetch("/api/chaves"), fetch("/api/aparelho/so-no-escritorio"), fetch("/api/aparelho/relatorio")]);
    aparelhoTitular.chaves = c.ok ? await c.json() : null;
    const d = m.ok ? await m.json() : {};
    aparelhoTitular.marcas = d.marcas || [];
    aparelhoTitular.servicos = d.servicos || [];
    aparelhoTitular.clientes = d.clientes || [];
    aparelhoTitular.relatorio = r.ok ? await r.json() : null;
  } catch (err) {
    aparelhoTitular.erro = "não consegui ler: " + ((err && err.message) || err);
  }
}

const TIPOS_DA_MARCA = { cliente: "Cliente", servico: "Serviço", pasta: "Pasta" };

function cartaoAparelhoTitular() {
  if (!acessoDeFora.local) return "";
  const a = aparelhoTitular;
  a.marcas = a.marcas || []; a.clientes = a.clientes || []; a.servicos = a.servicos || [];
  const ligado = Boolean(a.chaves && a.chaves.aparelho && a.chaves.aparelho.ligado);
  const liberadas = (acessoCfg.contas || []).filter((c) => c.papel !== "titular" && (c.permissoes || {}).aparelho === "faz");
  const erro = a.erro ? '<p class="cfg-explica">' + esc(a.erro) + "</p>" : "";

  /* 1. A chave do escritorio, quem pode e o que vai ou fica. */
  const chave = '<div class="ag-toggle' + (ligado ? " on" : "") + '" data-apt-ligar="' + (ligado ? "0" : "1") + '" role="switch" tabindex="0" aria-checked="' + ligado + '">' +
    '<span class="duas-linhas"><b>Deixar o aparelho escrever a resposta</b><small>' +
    (ligado ? "Quem pergunta de fora recebe a resposta escrita no próprio celular ou computador. Desligar agora faz o que estiver em andamento terminar aqui."
      : "Hoje toda resposta é escrita neste computador, venha a pergunta de onde vier.") + "</small></span><i></i></div>";
  const pessoas = '<div class="apt-quem"><span class="sv-kicker">Quem pode</span><div class="apt-chips">' +
    '<span class="apt-chip on">' + ic("person", 14) + "Você, o titular</span>" +
    liberadas.map((c) => '<span class="apt-chip on">' + ic("person", 14) + esc(c.nome) + "</span>").join("") +
    (liberadas.length ? "" : '<span class="apt-chip">Ninguém da equipe ainda</span>') + "</div>" +
    '<small class="apt-dica">Para liberar alguém: Contas › Permissões › “Escrever a resposta no próprio aparelho”.</small></div>';
  const limites = '<div class="apt-limites">' +
    '<div class="apt-lim"><span class="sv-kicker">' + ic("desktop_windows", 14) + "Vai ao aparelho</span><p>A pergunta e só os trechos dos documentos que ela precisa.</p></div>" +
    '<div class="apt-lim"><span class="sv-kicker">' + ic("work", 14) + "Fica sempre aqui</span><p>Ler o documento inteiro, editar, redigir peças e e-mail.</p></div></div>";
  const c1 = cartaoCfg("Escrever no aparelho", pontoCfg(ligado ? "ligado" : "desligado", ligado ? "ok" : ""),
    '<div class="apt" id="apt">' + erro + chave + (ligado ? pessoas : "") + limites + "</div>");

  /* 2. O que nunca sai: clientes, Servicos e pastas. */
  const opcoes = ['<option value="">Cliente ou Serviço…</option>']
    .concat(a.clientes.map((c) => '<option value="cliente:' + c.id + '">Cliente · ' + esc(c.nome) + "</option>"))
    .concat(a.servicos.map((x) => '<option value="servico:' + x.id + '">Serviço · ' + esc(x.nome) + (x.cliente ? " (" + esc(x.cliente) + ")" : "") + "</option>"));
  const icone = { cliente: "person", servico: "work", pasta: "folder" };
  const marcas = a.marcas.length
    ? '<div class="cfg-linhas">' + a.marcas.map((m, i) =>
      '<div class="cfg-servico"><span class="caixa-tipo">' + ic(icone[m.tipo] || "folder", 18) + '</span><span class="duas-linhas"><b>' + esc(m.rotulo) + "</b><small>" + esc(TIPOS_DA_MARCA[m.tipo] || m.tipo) + "</small></span>" +
      '<span class="cfg-botoes"><button class="com-icone" data-apt-tirar="' + i + '">' + ic("close", 16) + "Tirar</button></span></div>").join("") + "</div>"
    : '<p class="apt-vazio">' + ic("folder", 18) + "<span>Nada marcado. Tudo o que a pessoa vê pode ir ao aparelho dela.</span></p>";
  const c2 = cartaoCfg("Só no escritório", metaCfg(a.marcas.length ? (a.marcas.length === 1 ? "1 caso" : a.marcas.length + " casos") : "nunca vão ao aparelho"),
    '<div class="apt" id="apt-so">' + marcas +
    '<div class="apt-nova"><select id="apt-escolha" aria-label="Cliente ou Serviço">' + opcoes.join("") + "</select>" +
    '<button class="com-icone" data-apt-marcar="1">' + ic("add", 16) + "Marcar</button></div>" +
    '<div class="apt-nova"><input type="text" id="apt-pasta" placeholder="Pasta do Acervo, ex.: Clientes\\Fusão" aria-label="Pasta do Acervo">' +
    '<button class="com-icone" data-apt-pasta="1">' + ic("add", 16) + "Marcar pasta</button></div>" +
    '<p class="cfg-explica">Se a resposta usar algo marcado, ela é escrita aqui e a pessoa vê o motivo. Marcar um cliente vale para todos os Serviços dele, inclusive os novos.</p></div>');

  /* 3. O relatorio. */
  const r = Object.assign({ pessoas: [], total: {} }, a.relatorio || {});
  r.pessoas = r.pessoas || [];
  const rel = r.pessoas.length
    ? '<div class="apt-relatorio"><div class="apt-rel-cab"><span>Pessoa</span><span>No aparelho</span><span>Refeitas</span><span>Terminadas aqui</span></div>' +
      r.pessoas.map((p) => '<div class="apt-rel-linha"><span>' + esc(p.pessoa) + "</span><b>" + p.no_aparelho + "</b><b>" + p.refeitas + "</b><b>" + p.no_escritorio + "</b></div>").join("") +
      "</div>" +
      '<p class="cfg-explica"><b>Refeitas:</b> não passaram na conferência e foram escritas de novo aqui. <b>Terminadas aqui:</b> o aparelho parou, o prazo venceu ou a escrita foi desligada.</p>'
    : '<p class="apt-vazio">' + ic("bar_chart", 18) + "<span>Nenhuma resposta escrita em aparelho ainda.</span></p>";
  const c3 = cartaoCfg("Respostas escritas no aparelho", metaCfg("por pessoa"), '<div class="apt" id="apt-rel">' + rel + "</div>");

  return c1 + c2 + c3;
}

async function guardarMarcasDoAparelho(marcas) {
  const r = await fetch("/api/aparelho/so-no-escritorio", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ marcas: marcas.map((m) => ({ tipo: m.tipo, valor: m.valor })) }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return false; }
  aparelhoTitular.marcas = (await r.json()).marcas || [];
  return true;
}

function ligarAparelhoTitular() {
  const caixa = $("cfg-tela") || document;
  if (!$("apt")) return;
  const redesenhar = () => { if (typeof desenharConfig === "function") desenharConfig(); };
  const ligar = caixa.querySelector("[data-apt-ligar]");
  if (ligar) ligar.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); ligar.click(); } };
  if (ligar) ligar.onclick = async () => {
    const r = await fetch("/api/chaves", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bloco: "aparelho", chave: "ligado", ligada: ligar.dataset.aptLigar === "1" }) });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    aparelhoTitular.chaves = await r.json();
    avisoCert(aparelhoTitular.chaves.aparelho.ligado ? "Escrita no aparelho ligada para o escritório."
      : "Escrita no aparelho desligada: o que estava sendo escrito termina aqui.", { tom: "ok" });
    redesenhar();
  };
  caixa.querySelectorAll("[data-apt-tirar]").forEach((b) => {
    b.onclick = async () => {
      const i = Number(b.dataset.aptTirar);
      if (await guardarMarcasDoAparelho(aparelhoTitular.marcas.filter((_, j) => j !== i))) redesenhar();
    };
  });
  const marcar = caixa.querySelector("[data-apt-marcar]");
  if (marcar) marcar.onclick = async () => {
    const v = ($("apt-escolha") || {}).value || "";
    if (!v) return;
    const [tipo, valor] = v.split(":");
    if (await guardarMarcasDoAparelho(aparelhoTitular.marcas.concat([{ tipo: tipo, valor: Number(valor) }]))) redesenhar();
  };
  const pasta = caixa.querySelector("[data-apt-pasta]");
  if (pasta) pasta.onclick = async () => {
    const v = (($("apt-pasta") || {}).value || "").trim();
    if (!v) return;
    if (await guardarMarcasDoAparelho(aparelhoTitular.marcas.concat([{ tipo: "pasta", valor: v }]))) redesenhar();
  };
}
