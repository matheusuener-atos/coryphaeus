/* ------------------------------------------------ publicacoes e prazos */
/*
   Tarefas › Publicacoes (src/publicacoes.py) e a calculadora de prazo
   (src/prazos.py) - docs/PLANO-PRODUTO.md, P3. Uma vez por dia o Paulus
   pergunta ao Diario de Justica Eletronico Nacional o que saiu para as OABs
   acompanhadas; cada comunicacao nova aparece aqui, e "Criar prazo" conta os
   dias uteis a partir da disponibilizacao e cria a tarefa na lista Prazos,
   com a conta na anotacao. So na janela do servidor, por ora.
*/

const pub = { dados: null, filtro: "novas", aberta: null };

function pubLocal() { return typeof acessoDeFora === "undefined" || acessoDeFora.local; }

async function carregarPublicacoes() {
  try { pub.dados = await (await fetch("/api/publicacoes?filtro=" + pub.filtro)).json(); } catch (err) { pub.dados = null; }
}

function dataBr(isoData) {
  if (!isoData) return "";
  const [a, m, d] = isoData.slice(0, 10).split("-");
  return d + "/" + m + "/" + a;
}

function vistaPublicacoes() {
  const d = pub.dados || {};
  const lista = d.publicacoes || [];
  const oabs = (d.oabs || []).join(" · ");
  const topo = '<div class="tabela-barra"><b>Publicações do DJEN</b><span class="nota-barra">' +
    (oabs ? "OAB " + esc(oabs) : "nenhuma OAB") + (d.ultima ? " · consultado em " + esc(dataBr(d.ultima)) : "") + "</span>" +
    '<span class="direita"><button data-pub-oabs="1">' + ic("gavel", 16) + "OABs</button>" +
    '<button data-pub-feriados="1">' + ic("today", 16) + "Feriados</button>" +
    '<button class="primario com-icone" data-pub-consultar="1">' + ic("refresh", 16) + "Consultar agora</button></span></div>";
  const aviso = (d.ultimo_erro ? '<p class="acesso-erro pub-aviso">' + esc(d.ultimo_erro) + "</p>" : "") +
    '<div class="pub-opcoes"><div class="pub-abas">' +
    [["novas", "Novas" + (d.novas ? " · " + d.novas : "")], ["lidas", "Lidas"], ["todas", "Todas"]].map(([aba, r]) => {
      const classe = pub.filtro === aba ? "ativa" : "";
      return '<button class="' + classe + '" data-pub-filtro="' + aba + '">' + esc(r) + "</button>";
    }).join("") + "</div>" +
    ligaCfg("", "Consultar todo dia", "uma vez por dia, com o Paulus aberto", Boolean(d.ligado)).replace('class="ag-toggle', 'data-pub-ligado="1" class="ag-toggle') + "</div>";
  const linhas = lista.length ? lista.map((p) => {
    const aberta = pub.aberta === p.id;
    return '<div class="pub-item' + (p.lida ? " lida" : "") + '">' +
      '<button class="pub-cabeca" data-pub-abrir="' + p.id + '"><span class="duas-linhas"><b>' + esc(p.tipo || "Comunicação") + " · " + esc(p.processo || "sem número") + "</b>" +
      "<small>" + esc([p.tribunal, p.orgao, "disponibilizado em " + dataBr(p.data)].filter(Boolean).join(" · ")) + "</small></span>" +
      (p.tarefa_id ? '<span class="etiqueta ok">prazo criado</span>' : (p.pedido_id ? '<span class="etiqueta">prazo em Aprovações</span>' : "")) + (aberta ? ic("expand_more", 18).replace('class="ic', 'class="ic pub-seta-aberta') : ic("expand_more", 18)) + "</button>" +
      (aberta ? '<div class="pub-corpo"><p class="pub-texto">' + esc(p.texto || "").replace(/\n/g, "<br>") + "</p>" +
        (p.processo_id ? '<p class="cfg-explica">Processo cadastrado em Serviços › Processos: esta publicação entra no aviso dele' +
          (p.pedido_id && !p.tarefa_id ? ", e o prazo já espera em Aprovações." : ".") + "</p>" : "") +
        '<div class="cfg-botoes">' + (p.tarefa_id || p.pedido_id ? "" : '<button class="primario com-icone" data-pub-prazo="' + p.id + '">' + ic("event", 16) + "Criar prazo</button>") +
        (p.processo_id ? '<button data-pub-processo="' + p.processo_id + '">' + ic("gavel", 16) + "Abrir o processo</button>"
          : (p.processo ? '<button data-pub-acompanhar="' + p.id + '">' + ic("add", 16) + "Acompanhar este processo</button>" : "")) +
        '<button data-pub-lida="' + p.id + '" data-pub-valor="' + (p.lida ? "0" : "1") + '">' + (p.lida ? "Marcar como nova" : "Marcar como lida") + "</button></div></div>" : "") +
      "</div>";
  }).join("") : '<div class="ag-vazio"><h4>' + (pub.filtro === "novas" ? "Nenhuma publicação nova" : "Nada aqui") + "</h4><p>" +
    (oabs ? "O Paulus consulta o Diário de Justiça Eletrônico Nacional pelas OABs acompanhadas. Só o número e a UF da OAB saem deste computador."
      : "Diga a sua OAB em Configurações › Meus dados, ou acrescente as da equipe em OABs.") + "</p></div>";
  return '<div class="ag-cartao">' + topo + aviso + '<div class="tabela-corpo">' + linhas + "</div></div>";
}

async function pubPost(url, corpo) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || "não deu certo");
  return d;
}

function ligarPublicacoes(raiz) {
  const clique = (sel, fn) => raiz.querySelectorAll(sel).forEach((b) => { b.onclick = (ev) => { ev.stopPropagation(); fn(b); }; });
  const redesenhar = () => mostrarAgenda();
  clique("[data-pub-filtro]", async (b) => { pub.filtro = b.dataset.pubFiltro; await carregarPublicacoes(); redesenhar(); });
  clique("[data-pub-abrir]", (b) => { const id = Number(b.dataset.pubAbrir); pub.aberta = pub.aberta === id ? null : id; redesenhar(); });
  clique("[data-pub-ligado]", async (b) => {
    try { pub.dados = await pubPost("/api/publicacoes/configurar", { ligado: !b.classList.contains("on") }); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-pub-consultar]", async (b) => {
    b.disabled = true;
    try {
      const d = await pubPost("/api/publicacoes/consultar");
      avisoCert(d.encontradas ? plural(d.encontradas, "publicação nova", "publicações novas") : "nenhuma publicação nova", { tom: "ok" });
      await carregarPublicacoes();
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-pub-lida]", async (b) => {
    try { await pubPost("/api/publicacoes/" + b.dataset.pubLida + "/lida?lida=" + (b.dataset.pubValor === "1")); await carregarPublicacoes(); }
    catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-pub-prazo]", async (b) => {
    const p = ((pub.dados || {}).publicacoes || []).find((x) => String(x.id) === b.dataset.pubPrazo);
    if (!p) return;
    // N1: a sugestão pelo tipo de ato, lida no texto; a pessoa troca à vontade.
    const s = p.sugestao && !p.sugestao.sem_prazo && p.sugestao.dias ? p.sugestao : null;
    const semPrazo = p.sugestao && p.sugestao.sem_prazo ? p.sugestao.sem_prazo : "";
    const alternativas = s && s.alternativas && s.alternativas.length
      ? "<br>Também pode ser: " + s.alternativas.map((a) => esc(a.ato + " (" + a.dias + " dias " + (a.uteis ? "úteis" : "corridos") + ")")).join("; ") + "." : "";
    const sugestao = s
      ? '<p class="pub-sugestao"><b>' + esc(s.ato) + " — " + s.dias + " dias " + (s.uteis ? "úteis" : "corridos") + "</b> · " + esc(s.base) + ".<br>" +
        "Por quê: " + esc(s.porque) + "." + (s.certeza === "generico" ? " Confira o ato na intimação." : "") + alternativas + "</p>"
      : (semPrazo ? '<p class="pub-sugestao">' + esc(semPrazo) + "</p>" : "");
    const r = await dialogo({
      titulo: "Criar o prazo", contexto: (p.processo || "") + " · " + (p.tribunal || ""),
      texto: "Disponibilizado no DJEN em " + dataBr(p.data) + ". O Paulus conta a partir da publicação (o primeiro dia útil seguinte) e cria a tarefa na lista Prazos, com a conta na anotação para você conferir.",
      html: sugestao,
      campos: [
        { chave: "dias", rotulo: "Prazo (dias)", valor: String(s ? s.dias : 15), obrigatorio: true },
        { chave: "titulo", rotulo: "Título da tarefa", valor: "Prazo: " + (s ? s.ato : (p.tipo || "intimação")) + " · " + (p.processo || ""), obrigatorio: false },
      ],
      depois: '<div class="dialogo-campo"><label for="pub-uteis">Contagem</label><div class="dialogo-caixa"><select id="pub-uteis" data-dialogo-chave="uteis">' +
        '<option value="1"' + (s && !s.uteis ? "" : " selected") + '>Dias úteis (CPC, art. 219)</option><option value="0"' + (s && !s.uteis ? " selected" : "") + ">Dias corridos</option></select></div></div>",
      confirmar: "Criar o prazo",
    });
    if (!r || !r.ok) return;
    const mesmo = s && Number(r.valores.dias) === s.dias;
    try {
      const d = await pubPost("/api/publicacoes/" + p.id + "/prazo", { dias: Number(r.valores.dias) || 15, uteis: r.valores.uteis !== "0", titulo: r.valores.titulo || "",
        recesso: !(s && s.ramo === "penal"), ato: mesmo ? s.ato : "", base: mesmo ? s.base : "" });
      avisoCert("prazo criado: vence em " + dataBr(d.conta.vencimento), { tom: "ok" });
      await carregarPublicacoes();
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-pub-processo]", (b) => { if (typeof abrirProcesso === "function") abrirProcesso(Number(b.dataset.pubProcesso), () => carregarPublicacoes().then(redesenhar)); });
  clique("[data-pub-acompanhar]", async (b) => {
    const p = ((pub.dados || {}).publicacoes || []).find((x) => String(x.id) === b.dataset.pubAcompanhar);
    if (!p) return;
    try {
      await pubPost("/api/processos", { numero: p.processo });
      avisoCert("Processo " + p.processo + " cadastrado e acompanhado: as publicações dele entram no aviso do processo.", { tom: "ok" });
      await carregarPublicacoes();
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-pub-oabs]", async () => {
    const d = pub.dados || {};
    const r = await dialogo({
      titulo: "OABs acompanhadas", contexto: "Tarefas › Publicações",
      texto: "A OAB de Meus dados já entra. Acrescente as da equipe, uma por linha ou separadas por vírgula (ex.: GO 12345). Só o número e a UF saem deste computador, na consulta ao CNJ.",
      campos: [{ chave: "oabs", rotulo: "Outras OABs", valor: (d.oabs_extras || []).join(", "), obrigatorio: false }],
      confirmar: "Guardar",
    });
    if (!r || !r.ok) return;
    const oabs = String(r.valores.oabs || "").split(/[,;\n]/).map((x) => x.trim()).filter(Boolean);
    try { pub.dados = await pubPost("/api/publicacoes/configurar", { oabs: oabs }); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-pub-feriados]", () => editarFeriados());
}

/* Feriados do escritorio: municipal, estadual, ponto facultativo e suspensao
   do tribunal - os nacionais, o Carnaval, a Semana Santa, Corpus Christi e o
   recesso de 20/12 a 20/01 o Paulus ja conta. */
async function editarFeriados() {
  let atuais = [];
  try { atuais = (await (await fetch("/api/prazos/feriados")).json()).feriados || []; } catch (err) { /* vazio */ }
  const texto = atuais.map((f) => dataBr(f.data) + " " + (f.nome || "")).join("\n");
  const r = await dialogo({
    titulo: "Feriados do escritório", contexto: "Prazos",
    texto: "Os nacionais, o Carnaval, a Sexta-feira Santa, Corpus Christi e o recesso de 20/12 a 20/01 já contam. Acrescente os do seu município, do estado e as suspensões do tribunal: um por linha, com a data primeiro (ex.: 24/10/2026 Aniversário de Goiânia).",
    html: '<div class="dialogo-campo"><textarea id="pub-feriados" data-dialogo-chave="feriados" rows="8" class="pub-feriados">' + esc(texto) + "</textarea></div>",
    confirmar: "Guardar",
  });
  if (!r || !r.ok) return;
  const feriados = String(r.valores.feriados || "").split("\n").map((linha) => {
    const m = linha.trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})\s*(.*)$/);
    return m ? { data: m[3] + "-" + m[2].padStart(2, "0") + "-" + m[1].padStart(2, "0"), nome: m[4] || "sem expediente" } : null;
  }).filter(Boolean);
  try { await pubPost("/api/prazos/feriados", { feriados: feriados }); avisoCert(plural(feriados.length, "feriado guardado", "feriados guardados"), { tom: "ok" }); }
  catch (err) { avisoCert(err.message, { tom: "erro" }); }
}

/* A calculadora de prazo, solta (Tarefas › Calcular prazo): mostra a conta e
   cria a tarefa, se a pessoa quiser. */
async function calcularPrazo() {
  const hoje = new Date();
  const r = await dialogo({
    titulo: "Calcular prazo", contexto: "Tarefas",
    campos: [
      { chave: "data", rotulo: "Data (disponibilização ou intimação)", valor: hoje.toLocaleDateString("pt-BR"), obrigatorio: true,
        conferir: (x) => (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(x.trim()) ? "" : "escreva a data como dd/mm/aaaa") },
      { chave: "dias", rotulo: "Prazo (dias)", valor: "15", obrigatorio: true,
        conferir: (x) => (/^\d{1,4}$/.test(x.trim()) && Number(x) > 0 ? "" : "o prazo é um número de dias") },
    ],
    depois: '<div class="dialogo-duas"><div class="dialogo-campo"><label for="cp-origem">A data é da (no DJE)</label><div class="dialogo-caixa"><select id="cp-origem" data-dialogo-chave="origem">' +
      '<option value="disponibilizacao">Disponibilização</option><option value="intimacao">Intimação (ciência)</option></select></div></div>' +
      '<div class="dialogo-campo"><label for="cp-uteis">Contagem</label><div class="dialogo-caixa"><select id="cp-uteis" data-dialogo-chave="uteis">' +
      '<option value="1">Dias úteis</option><option value="0">Dias corridos</option></select></div></div></div>',
    confirmar: "Calcular",
  });
  if (!r || !r.ok) return;
  const m = String(r.valores.data || "").trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!m) { avisoCert("escreva a data como dd/mm/aaaa", { tom: "erro" }); return; }
  let conta;
  try {
    conta = await pubPost("/api/prazos/calcular", { data: m[3] + "-" + m[2].padStart(2, "0") + "-" + m[1].padStart(2, "0"),
      dias: Number(r.valores.dias) || 0, origem: r.valores.origem, uteis: r.valores.uteis !== "0" });
  } catch (err) { avisoCert(err.message, { tom: "erro" }); return; }
  const c = await dialogo({
    titulo: "Vence em " + dataBr(conta.vencimento), contexto: "Calcular prazo",
    texto: conta.passos.join("\n"),
    campos: [{ chave: "titulo", rotulo: "Criar a tarefa (título)", valor: "Prazo", obrigatorio: false }],
    confirmar: "Criar a tarefa", cancelar: "Só queria saber",
  });
  if (!c || !c.ok) return;
  try {
    await pubPost("/api/tarefas", { id: null, dados: { titulo: c.valores.titulo || "Prazo", prazo: conta.vencimento, importante: true,
      lista: "Prazos", anotacao: conta.passos.join("\n") } });
    avisoCert("tarefa criada na lista Prazos", { tom: "ok" });
    mostrarAgenda();
  } catch (err) { avisoCert(err.message, { tom: "erro" }); }
}
