/* ------------------------------------- criar um agente pela conversa (T3) */
/*
   Pacote de telas de 01/10/2026: `Conversa - Criar agente`. "Crie um agente
   que preencha a procuração ad judicia a partir dos documentos do cliente"
   (src/agente_pela_conversa.py):

   1. a conversa pergunta tres coisas, com as opcoes na mao - qual modelo
      (os documentos do Acervo cujo nome tem as palavras do pedido), o que
      fazer quando faltar um dado, em que formato entregar;
   2. "Escrever o agente": a regra le o modelo e conta os campos em branco, e
      o rascunho abre na coluna da direita; o modelo local escreve o nome, a
      descricao, as instrucoes e os exemplos (as respostas entram por regra);
   3. na coluna, as propriedades (modelo, fontes, entrega, modelo de IA) e as
      instrucoes editaveis, e os testes. "Salvar agente" grava pelo caminho de
      sempre (POST /api/agentes, com a validacao); o agente entra DESLIGADO,
      como todo agente novo. "Testar" salva e roda os testes dele.
*/

const agn = {
  campos: null,      // os campos do formulario (src/agentes_tela.py)
  pedido: "",
  respostas: null,   // { modelo, faltando, formato }
  slug: "",          // depois de salvo
  aba: "instrucoes", // instrucoes | testes
  escrevendo: false,
  resultados: null,  // o ultimo /testar
  modelos: [],
  modeloDeIA: "",
};

const AGN_FALTANDO = [["perguntar", "Perguntar antes de entregar"], ["marcar", "Entregar marcando o que falta"]];
const AGN_FORMATOS = [["modelo_de_documento", "Documento Word"], ["texto", "Texto na conversa"], ["lista", "Lista"], ["tabela", "Tabela"]];
const AGN_EXPLICA_FORMATO = {
  modelo_de_documento: "o modelo preenchido, sem controle de alterações", texto: "a resposta escrita na conversa",
  lista: "itens, um por linha", tabela: "linhas e colunas",
};

/* --------------------------------------------- as tres perguntas, no chat */

function cartaoDeCriarAgente(d) {
  const c = d.campos || {};
  const modelos = c.modelos || [];
  const chip = (grupo, valor, rotulo, on) => '<button type="button" class="asc-chip' + (on ? " on" : "") + '" data-agn-' + grupo + '="' + esc(valor) + '">' +
    (on ? ic("check", 14) : "") + esc(rotulo) + "</button>";
  const pergunta = (titulo, chips) => '<div class="agn-pergunta"><small>' + titulo + '</small><div class="asc-chips">' + chips + "</div></div>";
  return '<div class="proposta agn-perguntas" data-agn="1">' +
    pergunta("Qual modelo devo usar?", modelos.map((m, i) => chip("modelo", m, m, i === 0)).join("") + chip("modelo", "", "Nenhum, sem modelo", !modelos.length)) +
    pergunta("Se faltar um dado, o que faço?", AGN_FALTANDO.map(([v, r], i) => chip("faltando", v, r, i === 0)).join("")) +
    pergunta("Em que formato entrego?", AGN_FORMATOS.map(([v, r]) => chip("formato", v, r, v === (modelos.length ? "modelo_de_documento" : "texto"))).join("")) +
    '<div class="linha-form"><button class="primario" data-agn-escrever="1">' + ic("edit_note", 16) + "Escrever o agente</button>" +
    '<button class="fantasma" data-prop="nao">Deixa pra lá</button></div></div>';
}

function ligarCriarAgente(caixa, d) {
  const c = d.campos || {};
  const escolhido = (grupo) => { const b = caixa.querySelector("[data-agn-" + grupo + "].on"); return b ? b.getAttribute("data-agn-" + grupo) : ""; };
  ["modelo", "faltando", "formato"].forEach((grupo) => {
    caixa.querySelectorAll("[data-agn-" + grupo + "]").forEach((b) => {
      b.onclick = () => {
        caixa.querySelectorAll("[data-agn-" + grupo + "]").forEach((x) => {
          const on = x === b;
          x.classList.toggle("on", on);
          const visto = x.querySelector(".ic");
          if (on && !visto) x.insertAdjacentHTML("afterbegin", ic("check", 14));
          if (!on && visto) visto.remove();
        });
        // Sem modelo nao ha documento Word para preencher.
        if (grupo === "modelo" && !b.getAttribute("data-agn-modelo") && escolhido("formato") === "modelo_de_documento") {
          caixa.querySelector('[data-agn-formato="texto"]').click();
        }
      };
    });
  });
  const nao = caixa.querySelector('[data-prop="nao"]');
  if (nao) nao.onclick = () => { caixa.innerHTML = '<p class="explica">Tudo bem — não criei nada.</p>'; };
  caixa.querySelector("[data-agn-escrever]").onclick = () => {
    const respostas = { modelo: escolhido("modelo"), faltando: escolhido("faltando") || "perguntar", formato: escolhido("formato") || "texto" };
    if (respostas.formato === "modelo_de_documento" && !respostas.modelo) respostas.formato = "texto";
    escreverAgente(c, respostas, caixa);
  };
}

/* As respostas viram a ficha de pergunta e resposta do desenho. */
function respostasDoAgente(r) {
  const linha = (p, v) => '<div class="agn-resposta"><small>' + p + "</small><b>" + esc(v) + "</b></div>";
  return '<div class="agn-respondidas">' + linha("Qual modelo devo usar?", r.modelo || "Nenhum, sem modelo") +
    linha("Se faltar um dado, o que faço?", (AGN_FALTANDO.find((x) => x[0] === r.faltando) || [])[1] || "") +
    linha("Em que formato entrego?", (AGN_FORMATOS.find((x) => x[0] === r.formato) || [])[1] || "") + "</div>";
}

function linhaDoAgente(estadoDaEtapa, titulo) {
  const icone = estadoDaEtapa === "feito" ? ic("check", 14) : estadoDaEtapa === "andando" ? '<span class="giro"></span>' : '<span class="circulo-vazio"></span>';
  return '<div class="agn-etapa ' + estadoDaEtapa + '">' + icone + "<span>" + esc(titulo) + "</span></div>";
}

async function escreverAgente(c, respostas, caixa) {
  if (agn.escrevendo) return;
  agn.escrevendo = true;
  agn.pedido = c.pedido || "";
  agn.respostas = respostas;
  agn.modelos = c.modelos || [];
  agn.slug = "";
  agn.aba = "instrucoes";
  agn.resultados = null;
  caixa.innerHTML = respostasDoAgente(respostas);
  const andamento = document.createElement("div");
  andamento.className = "agn-andamento";
  caixa.after(andamento);
  const etapas = [respostas.modelo ? "Ler o modelo “" + nomeSemExtensao(respostas.modelo) + "”" : "Montar o roteiro sem modelo", "Mapear os campos em branco", "Escrever as instruções"];
  const desenhar = (k, brancos) => {
    const titulos = etapas.slice();
    if (brancos !== undefined) titulos[1] = respostas.modelo ? "Mapear " + plural(brancos, "campo em branco", "campos em branco") : "Sem modelo: nada a mapear";
    andamento.innerHTML = '<b class="agn-andamento-topo">Escrevendo o agente · etapa ' + Math.min(k + 1, 3) + " de 3</b>" +
      titulos.map((t, i) => linhaDoAgente(i < k ? "feito" : i === k ? "andando" : "espera", t)).join("");
  };
  desenhar(0);
  rolar();
  const corpo = JSON.stringify({ pedido: agn.pedido, modelo: respostas.modelo, faltando: respostas.faltando, formato: respostas.formato });
  let base = null;
  try {
    const r = await fetch("/api/agentes/rascunho", { method: "POST", headers: { "Content-Type": "application/json" }, body: corpo });
    if (!r.ok) throw new Error(await erroDe(r));
    base = (await r.json()).campos;
  } catch (err) {
    andamento.innerHTML = '<p class="explica">Não consegui montar o rascunho: ' + esc(String(err.message || err)) + "</p>";
    agn.escrevendo = false;
    return;
  }
  desenhar(2, base.brancos || 0);
  agn.campos = base;
  // O que a pessoa decidiu nas tres perguntas: fica nas instrucoes mesmo que
  // um pedido de mudanca na conversa leve o modelo a tira-lo.
  agn.fixos = (base.passos || []).slice();
  abrirAgenteAoLado(true);
  try {
    const r = await fetch("/api/agentes/rascunho/escrever", { method: "POST", headers: { "Content-Type": "application/json" }, body: corpo });
    if (!r.ok) throw new Error(await erroDe(r));
    const d = await r.json();
    agn.campos = d.campos;
    agn.modeloDeIA = d.modelo_de_ia || "";
    andamento.innerHTML = '<b class="agn-andamento-topo">Escrevi o agente · 3 de 3 etapas</b>' +
      etapas.map((t, i) => linhaDoAgente("feito", i === 1 ? (respostas.modelo ? "Mapear " + plural(base.brancos || 0, "campo em branco", "campos em branco") : "Sem modelo: nada a mapear") : t)).join("");
    notaDeFeitoNaConversa(d.campos.escrito_por === "modelo"
      ? "Escrevi “" + d.campos.nome + "” ao lado com o " + (agn.modeloDeIA || "modelo local") + ". As suas três respostas entraram nas instruções como você disse. Nada foi salvo ainda: confira, ajuste e salve."
      : "O modelo não respondeu agora: deixei ao lado as instruções que a regra monta com as suas respostas, para você completar. Nada foi salvo ainda.");
  } catch (err) {
    andamento.innerHTML = '<b class="agn-andamento-topo">Escrevendo o agente · etapa 3 de 3</b>' + linhaDoAgente("feito", etapas[0]) +
      linhaDoAgente("feito", etapas[1]) + '<p class="explica">O modelo não escreveu: ' + esc(String(err.message || err)) +
      ". As instruções ao lado são as da regra, com as suas respostas.</p>";
  } finally {
    agn.escrevendo = false;
    if (papelDoLado() === "ferramenta" && $("agn-instrucoes")) desenharAgenteAoLado();
    rolar();
  }
}

/* --------------------------------------------- markdown <-> a folha */

function marcasEmLinha(texto) {
  return esc(texto).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>");
}

function htmlDasInstrucoes(md) {
  const linhas = String(md || "").replace(/\r\n/g, "\n").split("\n");
  let html = "";
  let lista = "";
  const fechar = () => { if (lista) { html += "</" + lista + ">"; lista = ""; } };
  linhas.forEach((l) => {
    const t = l.trim();
    let m;
    if (!t) { fechar(); return; }
    if ((m = /^#\s+(.*)$/.exec(t))) { fechar(); html += "<h1>" + marcasEmLinha(m[1]) + "</h1>"; return; }
    if ((m = /^#{2,3}\s+(.*)$/.exec(t))) { fechar(); html += "<h2>" + marcasEmLinha(m[1]) + "</h2>"; return; }
    if ((m = /^\d+[.)]\s+(.*)$/.exec(t))) { if (lista !== "ol") { fechar(); html += "<ol>"; lista = "ol"; } html += "<li>" + marcasEmLinha(m[1]) + "</li>"; return; }
    if ((m = /^[-*]\s+(.*)$/.exec(t))) { if (lista !== "ul") { fechar(); html += "<ul>"; lista = "ul"; } html += "<li>" + marcasEmLinha(m[1]) + "</li>"; return; }
    fechar();
    html += "<p>" + marcasEmLinha(t) + "</p>";
  });
  fechar();
  return html;
}

function textoDoNo(no) {
  let s = "";
  no.childNodes.forEach((n) => {
    if (n.nodeType === 3) s += n.textContent;
    else if (n.nodeName === "B" || n.nodeName === "STRONG") s += "**" + textoDoNo(n) + "**";
    else if (n.nodeName === "I" || n.nodeName === "EM") s += "*" + textoDoNo(n) + "*";
    else if (n.nodeName === "BR") s += " ";
    else s += textoDoNo(n);
  });
  return s.replace(/\s+/g, " ").trim();
}

function instrucoesDaFolha(folha) {
  const partes = [];
  folha.childNodes.forEach((n) => {
    if (n.nodeType === 3) { if (n.textContent.trim()) partes.push(n.textContent.trim()); return; }
    if (n.nodeName === "H1") partes.push("# " + textoDoNo(n));
    else if (/^H[2-6]$/.test(n.nodeName)) partes.push("## " + textoDoNo(n));
    else if (n.nodeName === "OL") partes.push(Array.from(n.children).map((li, i) => (i + 1) + ". " + textoDoNo(li)).join("\n"));
    else if (n.nodeName === "UL") partes.push(Array.from(n.children).map((li) => "- " + textoDoNo(li)).join("\n"));
    else if (textoDoNo(n)) partes.push(textoDoNo(n));
  });
  return partes.join("\n\n") + "\n";
}

/* ---------------------------------------------------- a coluna */

function abrirAgenteAoLado(escrevendo) {
  abrirNoLado("ferramenta", {
    chave: "agente-novo",
    html: '<div class="fl" data-fl-tipo="agente" id="agn-lado"></div>',
    aoFechar: () => { atualizarPostura(); $("pedido").placeholder = "Pergunte outra coisa ou aponte outra pasta…"; },
  });
  desenharAgenteAoLado(escrevendo);
  $("pedido").placeholder = "Descreva o que o agente deve mudar…";
}

function linhaDoRascunhoDoAgente() {
  if (agn.slug) return "salvo · desligado até você ligar em Agentes";
  return "rascunho · ainda não salvo";
}

function desenharAgenteAoLado(escrevendo) {
  const raiz = $("agn-lado");
  if (!raiz || !agn.campos) return;
  const c = agn.campos;
  const modelo = c.saida_modelo || (agn.respostas || {}).modelo || "";
  const pastas = c.acervo === "pastas" && (c.pastas || []).length;
  const prop = (rotulo, valor) => '<div class="agn-prop"><span>' + rotulo + "</span><div>" + valor + "</div></div>";
  raiz.innerHTML = topoDaFerramenta({
    nome: (c.nome || "Novo agente") + ".md",
    marca: '<span class="fl-marca outro">' + ic("description", 18) + "</span>",
    tituloHtml: '<span class="agn-nome" id="agn-nome" contenteditable="true" spellcheck="false">' + esc(c.nome || "Novo agente") + "</span>",
    depoisDoNome: '<span class="agn-lapis">' + ic("edit", 14) + "</span>",
    linhaHtml: '<small id="agn-linha">' + esc(linhaDoRascunhoDoAgente()) + "</small>",
    acoes: '<button data-agn="testar">Testar</button><button class="primario" data-agn="salvar">' + (agn.slug ? "Salvar versão" : "Salvar agente") + "</button>",
  }) +
    '<div class="agn-props">' +
    prop("Modelo", modelo ? '<button class="agn-chip" data-agn="modelo">' + glifo(modelo) + "<b>" + esc(modelo) + "</b></button>"
      : '<button class="agn-chip" data-agn="modelo"><span>sem modelo</span></button>') +
    prop("Fontes", '<span class="agn-chip">' + ic("folder_open", 16) + "<b>" + (pastas ? esc(c.pastas.join(", ")) : "Acervo inteiro") + "</b></span>" +
      '<button class="fantasma agn-incluir" data-agn="pasta">' + ic("add", 16) + "Incluir pasta</button>") +
    prop("Entrega", '<button class="agn-chip" data-agn="formato"><b>' + esc((AGN_FORMATOS.find((x) => x[0] === c.formato) || [c.formato, c.formato])[1]) + "</b></button>" +
      "<small>" + esc(AGN_EXPLICA_FORMATO[c.formato] || "") + "</small>") +
    prop("Modelo de IA", '<span class="agn-chip fl-mono">' + esc(agn.modeloDeIA || estado.modelo || "modelo local") + "</span><small>roda neste computador</small>") +
    "</div>" +
    '<div class="fl-quadro agn-quadro"><div class="fl-barra edl-barra">' +
    '<label class="edl-bloco"><select id="agn-bloco" aria-label="Estilo do parágrafo"><option value="p">Parágrafo</option><option value="h1">Título</option><option value="h2">Subtítulo</option></select>' + ic("expand_more", 16) + "</label>" +
    '<span class="divisa-v"></span>' +
    ["bold:format_bold:Negrito", "italic:format_italic:Itálico", "underline:format_underlined:Sublinhado", "insertOrderedList:format_list_numbered:Lista numerada"].map((x) => {
      const [cmd, icone, titulo] = x.split(":");
      return '<button class="botao-icone" data-agn-cmd="' + cmd + '" title="' + titulo + '" aria-label="' + titulo + '">' + ic(icone, 18) + "</button>";
    }).join("") +
    '<span class="cresce"></span><span class="visoes agn-abas"><button data-agn-aba="instrucoes"' + (agn.aba === "instrucoes" ? ' class="ativa"' : "") + ">Instruções</button>" +
    '<button data-agn-aba="testes"' + (agn.aba === "testes" ? ' class="ativa"' : "") + ">Testes" + ((c.testes || []).length ? " · " + c.testes.length : "") + "</button></span></div>" +
    '<div class="agn-folha-mesa">' + (agn.aba === "testes" ? htmlDosTestesDoAgente() :
      '<div class="agn-folha" id="agn-instrucoes" contenteditable="true" spellcheck="true">' + htmlDasInstrucoes(c.instrucoes) + "</div>" +
      (agn.escrevendo || escrevendo ? '<p class="agn-escrevendo"><i></i>escrevendo…</p>' : "")) + "</div></div>";
  ligarAgenteAoLado(raiz);
}

function htmlDosTestesDoAgente() {
  const testes = agn.campos.testes || [];
  const r = agn.resultados;
  const linhas = testes.map((t, i) => {
    const res = r && r.resultados ? r.resultados[i] : null;
    const selo = res ? (res.passou ? '<span class="etiqueta ok"><i></i>passou</span>' : '<span class="etiqueta prazo"><i></i>falhou</span>') : "";
    return '<div class="agn-teste"><div class="agn-teste-campos"><input type="text" data-agn-teste="' + i + '" data-agn-campo="pergunta" value="' + esc(t.pergunta || "") + '" placeholder="uma pergunta que este agente deve acertar">' +
      '<input type="text" data-agn-teste="' + i + '" data-agn-campo="deve_conter" value="' + esc(t.deve_conter || "") + '" placeholder="a resposta certa tem: palavras, separadas por vírgula"></div>' +
      selo + '<button class="botao-icone" data-agn-tirar="' + i + '" aria-label="Tirar o teste">' + ic("close", 16) + "</button>" +
      (res && !res.passou ? '<p class="explica">' + esc(res.erro ? "deu erro: " + res.erro : "faltou: " + (res.faltou || []).join(", ")) + "</p>" : "") + "</div>";
  }).join("");
  return '<div class="agn-testes">' + (linhas || '<p class="explica">Sem testes. Um teste é uma pergunta e as palavras que a resposta certa tem; "Testar" salva o agente e roda cada uma pela conversa, com as instruções dele.</p>') +
    '<button class="fantasma" data-agn="mais-teste">' + ic("add", 16) + "Acrescentar teste</button>" +
    (r ? '<p class="explica">' + esc(r.passaram + " de " + r.total + " passaram") + "</p>" : "") + "</div>";
}

/* Le a coluna para os campos (o nome, a folha, os testes). */
function lerAgenteDaColuna() {
  const c = agn.campos;
  const nome = $("agn-nome");
  if (nome) c.nome = nome.textContent.replace(/\s+/g, " ").trim().slice(0, 60) || c.nome;
  const folha = $("agn-instrucoes");
  if (folha) c.instrucoes = instrucoesDaFolha(folha);
  document.querySelectorAll("[data-agn-teste]").forEach((el) => {
    const t = (c.testes || [])[Number(el.dataset.agnTeste)];
    if (t) t[el.dataset.agnCampo] = el.value;
  });
}

function marcarAgenteMudado() {
  const linha = $("agn-linha");
  if (linha) linha.textContent = agn.slug ? "alterações não salvas" : "rascunho · ainda não salvo";
}

function ligarAgenteAoLado(raiz) {
  const acao = (q, fn) => { const b = raiz.querySelector('[data-agn="' + q + '"]'); if (b) b.onclick = (e) => fn(e.currentTarget); };
  raiz.querySelector('[data-fl="fechar"]').onclick = () => voltarAoContexto();
  raiz.querySelector('[data-fl="mais"]').onclick = (e) => menuNaLinha(e.currentTarget, [
    { rotulo: "Ver o AGENTE.md", acao: verMarkdownDoAgente },
    { rotulo: "Abrir em Agentes", acao: () => { lerAgenteDaColuna(); voltarAoContexto(); marcarDestino("agentes"); if (agn.slug) mostrarAgentes(agn.slug); else mostrarAgentes(); } },
  ]);
  acao("salvar", () => salvarAgenteDaConversa());
  acao("testar", () => testarAgenteDaConversa());
  acao("modelo", (b) => menuNaLinha(b, agn.modelos.map((m) => ({ rotulo: m, acao: () => trocarModeloDoAgente(m) }))
    .concat([{ rotulo: "Sem modelo", acao: () => trocarModeloDoAgente("") }])));
  acao("formato", (b) => menuNaLinha(b, AGN_FORMATOS.filter(([v]) => v !== "modelo_de_documento" || agn.campos.saida_modelo || (agn.respostas || {}).modelo)
    .map(([v, r]) => ({ rotulo: r, acao: () => { lerAgenteDaColuna(); agn.campos.formato = v; if (v === "modelo_de_documento" && !agn.campos.saida_modelo) agn.campos.saida_modelo = (agn.respostas || {}).modelo || ""; marcarAgenteMudado(); desenharAgenteAoLado(); } }))));
  acao("pasta", incluirPastaNoAgente);
  acao("mais-teste", () => { lerAgenteDaColuna(); agn.campos.testes = (agn.campos.testes || []).concat([{ pergunta: "", deve_conter: "" }]); desenharAgenteAoLado(); });
  raiz.querySelectorAll("[data-agn-tirar]").forEach((b) => {
    b.onclick = () => { lerAgenteDaColuna(); agn.campos.testes.splice(Number(b.dataset.agnTirar), 1); marcarAgenteMudado(); desenharAgenteAoLado(); };
  });
  raiz.querySelectorAll("[data-agn-aba]").forEach((b) => {
    b.onclick = () => { lerAgenteDaColuna(); agn.aba = b.dataset.agnAba; desenharAgenteAoLado(); };
  });
  raiz.querySelectorAll("[data-agn-cmd]").forEach((b) => {
    b.onmousedown = (e) => { e.preventDefault(); document.execCommand(b.dataset.agnCmd, false, null); marcarAgenteMudado(); };
  });
  const bloco = $("agn-bloco");
  if (bloco) bloco.onchange = (e) => { const f = $("agn-instrucoes"); if (f) { f.focus(); document.execCommand("formatBlock", false, e.target.value); marcarAgenteMudado(); } };
  raiz.addEventListener("input", marcarAgenteMudado);
}

function trocarModeloDoAgente(m) {
  lerAgenteDaColuna();
  agn.campos.saida_modelo = m;
  if (!m && agn.campos.formato === "modelo_de_documento") agn.campos.formato = "texto";
  if (m) agn.campos.formato = "modelo_de_documento";
  marcarAgenteMudado();
  desenharAgenteAoLado();
}

async function incluirPastaNoAgente() {
  let pastas = [];
  try { pastas = ((await (await fetch("/api/acervo/pastas")).json()).pastas || []).filter((p) => p && p.caminho && !p.sumiu); } catch (err) { pastas = []; }
  if (!pastas.length) { avisoNaJanela("Nenhuma pasta no Acervo para escolher"); return; }
  const r = await dialogo({
    titulo: "Incluir pasta", contexto: "Fontes do agente",
    texto: "O agente lê só o que está nas pastas escolhidas (e não o Acervo inteiro).",
    html: '<div class="dialogo-campo"><label for="agn-pasta">Pasta</label><div class="dialogo-caixa"><select id="agn-pasta">' +
      pastas.map((p) => '<option value="' + esc(p.caminho) + '">' + esc(p.nome || p.caminho) + "</option>").join("") + "</select></div></div>",
    confirmar: "Incluir",
  });
  if (!r || !r.ok) return;
  const sel = document.getElementById("agn-pasta");
  const escolhida = sel ? sel.value : pastas[0].caminho;
  lerAgenteDaColuna();
  agn.campos.acervo = "pastas";
  agn.campos.pastas = Array.from(new Set((agn.campos.pastas || []).concat([escolhida])));
  marcarAgenteMudado();
  desenharAgenteAoLado();
}

async function markdownDoAgente() {
  lerAgenteDaColuna();
  const campos = Object.assign({}, agn.campos, {
    exemplos: (agn.campos.exemplos || []).join ? agn.campos.exemplos.join("\n") : agn.campos.exemplos,
    pastas: (agn.campos.pastas || []).join ? agn.campos.pastas.join("\n") : agn.campos.pastas,
  });
  const r = await fetch("/api/agentes/formulario", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ campos: campos }) });
  if (!r.ok) throw new Error(await erroDe(r));
  return r.json();
}

async function verMarkdownDoAgente() {
  try { const d = await markdownDoAgente(); mostrarMarkdown("AGENTE.md", d.markdown); } catch (err) { avisoNaJanela(String(err.message || err), { icone: "error" }); }
}

async function salvarAgenteDaConversa() {
  const botao = document.querySelector('#agn-lado [data-agn="salvar"]');
  if (botao) botao.disabled = true;
  try {
    const d = await markdownDoAgente();
    if (!d.valido) { avisoNaJanela("O agente não foi salvo: " + d.erro, { icone: "error" }); return null; }
    const r = await fetch("/api/agentes" + (agn.slug ? "/" + encodeURIComponent(agn.slug) : ""), {
      method: agn.slug ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ markdown: d.markdown }),
    });
    if (!r.ok) { avisoNaJanela("O agente não foi salvo: " + (await erroDe(r)), { icone: "error" }); return null; }
    const ficha = await r.json();
    const novo = !agn.slug;
    agn.slug = ficha.slug;
    agn.campos.versao = ficha.versao || agn.campos.versao;
    if (novo) notaDeFeitoNaConversa("Salvei o agente “" + ficha.nome + "”. Ele entra desligado: teste e ligue em Agentes quando estiver bom.");
    desenharAgenteAoLado();
    return ficha;
  } catch (err) {
    avisoNaJanela("O agente não foi salvo: " + (err.message || err), { icone: "error" });
    return null;
  } finally {
    if (botao && botao.isConnected) botao.disabled = false;
  }
}

/* O pedido escrito na conversa com o agente aberto ao lado: o modelo devolve
   as instrucoes com a mudanca, e a folha troca a lista numerada. Desfazer
   volta ao que era. Nada e salvo sem o "Salvar". */
function agenteAoLadoAberto() {
  return Boolean(agn.campos && $("agn-lado") && papelDoLado() === "ferramenta");
}

function passosDasInstrucoes(md) {
  return String(md || "").split("\n").map((l) => /^\s*\d+[.)]\s+(.*)$/.exec(l)).filter(Boolean).map((m) => m[1].trim());
}

function trocarPassos(md, passos) {
  const linhas = String(md || "").split("\n");
  const numeradas = linhas.map((l, i) => (/^\s*\d+[.)]\s+/.test(l) ? i : -1)).filter((i) => i >= 0);
  const lista = passos.map((p, i) => (i + 1) + ". " + p);
  if (!numeradas.length) return String(md || "").replace(/\s*$/, "") + "\n\n" + lista.join("\n") + "\n";
  return linhas.slice(0, numeradas[0]).concat(lista, linhas.slice(numeradas[numeradas.length - 1] + 1)).join("\n");
}

async function mudarAgentePelaConversa(pedido) {
  lerAgenteDaColuna();
  const antes = agn.campos.instrucoes;
  const centro = $("centro");
  centro.insertAdjacentHTML("beforeend", bolhaPessoa(pedido));
  const resposta = document.createElement("div");
  resposta.className = "resposta";
  resposta.innerHTML = '<div class="agn-andamento">' + linhaDoAgente("andando", "Mudar as instruções") + "</div>";
  centro.appendChild(resposta);
  rolar();
  const r = await fetch("/api/agentes/rascunho/mudar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ passos: passosDasInstrucoes(antes), fixos: agn.fixos || [], pedido: pedido }),
  }).catch(() => null);
  if (!r || !r.ok) {
    resposta.innerHTML = '<div class="texto">Não mudei: ' + esc(r ? await erroDe(r) : "sem resposta do servidor") + "</div>";
    return;
  }
  const d = await r.json();
  agn.campos.instrucoes = trocarPassos(antes, d.passos);
  agn.aba = "instrucoes";
  desenharAgenteAoLado();
  marcarAgenteMudado();
  resposta.innerHTML = '<div class="texto">Mudei as instruções ao lado (agora são ' + plural(d.passos.length, "passo") +
    "). Confira antes de salvar.</div>" + '<div class="linha-form"><button data-agn-desfazer="1">Desfazer</button></div>';
  resposta.querySelector("[data-agn-desfazer]").onclick = () => {
    agn.campos.instrucoes = antes;
    desenharAgenteAoLado();
    marcarAgenteMudado();
    resposta.querySelector(".linha-form").remove();
  };
  rolar();
}

async function testarAgenteDaConversa() {
  lerAgenteDaColuna();
  const validos = (agn.campos.testes || []).filter((t) => (t.pergunta || "").trim());
  if (!validos.length) { agn.aba = "testes"; if (!(agn.campos.testes || []).length) agn.campos.testes = [{ pergunta: "", deve_conter: "" }]; desenharAgenteAoLado(); avisoNaJanela("Escreva um teste: a pergunta e o que a resposta certa tem"); return; }
  const ficha = await salvarAgenteDaConversa();
  if (!ficha) return;
  agn.aba = "testes";
  desenharAgenteAoLado();
  avisoNaJanela("Rodando " + plural(validos.length, "teste") + " pela conversa…");
  const r = await fetch("/api/agentes/" + encodeURIComponent(agn.slug) + "/testar", { method: "POST" }).catch(() => null);
  if (!r || !r.ok) { avisoNaJanela("O teste não rodou: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return; }
  agn.resultados = await r.json();
  desenharAgenteAoLado();
}
