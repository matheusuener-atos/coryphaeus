/* --------------------------------------------------------- aprovacoes */
/*
   A regra central do manual mora aqui: nada com efeito externo acontece sem o
   sim de uma pessoa. A fila e o lugar comum onde essas acoes param.
*/

/*
   A fila de aprovacoes do desenho (docs/ui/03-telas-desktop.md, A11): fila,
   historico e regras de alcada, sobre a mesma grade do Acervo. A regra
   central do produto mora aqui: nada com efeito externo acontece sem o sim
   de uma pessoa.

   O servidor guarda os pedidos pendentes e os decididos hoje. As regras de
   alcada sao a autonomia do assistente, a mesma de Configuracoes: ligada, a
   acao acontece direto; desligada, para na fila.
*/

const aprov = {
  pendentes: [], hoje: [], leitura: null, marcados: new Set(), aberto: null,
  visao: "fila", filtro: "", largo: false, regras: null, regraAberta: null,
};

const ICONE_CATEGORIA = { organizar: "drive_file_move", arquivo: "folder", email: "mail", assinatura: "draw", permissao: "shield_person", financeiro: "payments" };
const CHAVE_DA_CATEGORIA = { organizar: "organizar_mover", assinatura: "assinar", email: "enviar_mensagem" };
const ICONE_REGRA = { ler_pastas: "inventory_2", organizar_mover: "drive_file_move", assinar: "draw", enviar_mensagem: "mail", modelo_nuvem: "cloud_upload" };
const VERBO_APROVAR = { organizar: "Aprovar e mover", email: "Aprovar e enviar", assinatura: "Aprovar e assinar", financeiro: "Aprovar e pagar", permissao: "Aprovar" };

function dataHoraCurta(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return esc(iso);
  const hoje = new Date();
  const hora = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  const mesmoDia = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  if (mesmoDia(d, hoje)) return "hoje " + hora;
  const ontem = new Date(hoje);
  ontem.setDate(hoje.getDate() - 1);
  if (mesmoDia(d, ontem)) return "ontem " + hora;
  return d.getDate() + " " + MESES_CURTOS[d.getMonth()] + " " + hora;
}

function cabecalhoAprovacoes(visao) {
  const botao = (v, r) => {
    const classe = v === visao ? "ativa" : "";
    return '<button class="' + classe + '" data-visao-ap="' + v + '">' + r + "</button>";
  };
  $("acoes-tela").innerHTML =
    '<div class="visoes">' + botao("fila", "Fila") + botao("historico", "Histórico") + "</div>" +
    '<div class="visoes">' + botao("regras", "Regras de alçada") + "</div>";
  $("acoes-tela").querySelectorAll("[data-visao-ap]").forEach((b) => {
    b.onclick = () => abrirVisaoDeAprovacoes(b.dataset.visaoAp);
  });
}

function abrirVisaoDeAprovacoes(visao) {
  marcarDestino("aprovacoes");
  if (visao === "historico") return mostrarHistoricoDeAprovacoes();
  if (visao === "regras") return mostrarRegrasDeAlcada();
  return mostrarAprovacoes();
}

async function carregarFila() {
  try {
    const d = await (await fetch("/api/aprovacoes")).json();
    aprov.pendentes = d.pendentes;
    aprov.hoje = d.hoje;
    aprov.leitura = d.leitura;
    return true;
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' +
      esc(String(err)) + "</p></div></div>";
    return false;
  }
}

async function mostrarAprovacoes() {
  abrirTela("Aprovações", { cheia: true });
  aprov.visao = "fila";
  cabecalhoAprovacoes("fila");
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">abrindo a fila…</p></div></div>';
  if (!(await carregarFila())) return;
  if (!aprov.regras) {
    try { aprov.regras = await (await fetch("/api/preferencias")).json(); } catch (err) { aprov.regras = null; }
  }
  desenharAprovacoes();
  atualizarPostura();
}

function quemPediu(nome) {
  const assistente = !nome || nome === "Assistente" || nome === "PAULUS";
  const iniciais = (nome || "").trim().split(/\s+/).map((x) => x[0] || "").slice(0, 2).join("").toUpperCase();
  return '<span class="quem">' +
    (assistente ? '<span class="avatar-p">P</span>' : '<span class="avatar-mini">' + esc(iniciais || "?") + "</span>") +
    "<span>" + esc(nome || "Assistente") + "</span></span>";
}

function metaDoPedido(p) {
  const partes = [p.categoria_rotulo].concat(p.etiquetas || []);
  if (p.vence_hoje) partes.push("vence hoje");
  if (!p.reversivel) partes.push("sem desfazer");
  return partes.filter(Boolean).join(" · ");
}

function esperandoHa(iso) {
  return quando(iso).replace(/^há /, "");
}

function autonomiaAtual() {
  const r = aprov.regras;
  if (!r) return {};
  return ((r.preferencias || r).autonomia) || {};
}

function desenharAprovacoes() {
  const todos = aprov.pendentes;
  const categorias = [...new Set(todos.map((p) => p.categoria))];
  if (aprov.filtro && !categorias.includes(aprov.filtro)) aprov.filtro = "";
  const lista = aprov.filtro ? todos.filter((p) => p.categoria === aprov.filtro) : todos;
  for (const id of [...aprov.marcados]) if (!todos.some((p) => p.id === id)) aprov.marcados.delete(id);
  if (aprov.aberto && !todos.some((p) => p.id === aprov.aberto)) aprov.aberto = null;
  const n = todos.length, m = aprov.marcados.size;
  $("conversa-meta").textContent = (n ? n + " esperando você" : "nada esperando você") + " · nada sai sem aprovação";

  const chips = '<span class="visoes">' +
    [["", "Tudo"]].concat(categorias.map((c) => [c, (todos.find((p) => p.categoria === c) || {}).categoria_rotulo || c])).map(([v, r]) => {
      const classe = v === aprov.filtro ? "ativa" : "";
      return '<button class="' + classe + '" data-filtro-ap="' + esc(v) + '">' + esc(r) + "</button>";
    }).join("") + "</span>";
  const acoes = '<span class="direita">' +
    '<button class="com-icone" id="ap-recusar"' + (m ? "" : " disabled") + ">" + ic("close", 16) + "Recusar" + (m ? " · " + m : "") + "</button>" +
    '<button class="primario com-icone" id="ap-aprovar"' + (m ? "" : " disabled") + ">" + ic("done_all", 16) + "Aprovar" + (m ? " · " + m : "") + "</button></span>";

  const linhas = lista.length
    ? lista.map(linhaPedido).join("")
    : (n
      ? '<p class="nota">Nada nesta categoria.</p>'
      : '<div class="painel-vazio"><h3>Nada esperando você</h3><p>' +
        (aprov.hoje.length
          ? "Hoje você já decidiu " + plural(aprov.hoje.length, "pedido") + ". O que precisar do seu sim aparece aqui."
          : "Quando o assistente quiser fazer algo com efeito fora do programa — mover arquivos em lote, " +
            "assinar, enviar mensagem — o pedido para aqui e espera.") + "</p></div>");

  const todosMarcados = n > 0 && m === n;
  const classe = "marcar" + (todosMarcados ? " on" : "");
  $("centro").innerHTML =
    '<div class="acervo' + (aprov.largo ? " painel-largo" : "") + '"><div class="acervo-principal"><div class="tabela-cartao">' +
    '<div class="tabela-barra">' + chips + acoes + "</div>" +
    '<div class="tabela-cabecalho colunas-fila"><span class="' + classe + '" id="ap-todos" role="checkbox" aria-checked="' +
    (todosMarcados ? "true" : "false") + '" title="Marcar todos">' + ic("check", 12) + "</span>" +
    '<span>O que precisa do seu sim</span><span>Pedido por</span><span>Esperando há</span><span style="text-align:right">Ação</span></div>' +
    '<div class="tabela-corpo">' + linhas + "</div>" +
    '<div class="tabela-rodape"><span>' + (n ? n + " esperando você" : "nada esperando você") + " · nada sai sem aprovação</span>" +
    '<span class="cresce"></span><span>Aprovado ou recusado, tudo fica registrado no Histórico</span></div>' +
    "</div></div>" + painelDoPedido() + "</div>";
  ligarAprovacoes();
}

function linhaPedido(p) {
  const marcado = aprov.marcados.has(p.id);
  const classe = "tabela-linha colunas-fila" + (marcado ? " escolhida" : "") + (aprov.aberto === p.id ? " aberta" : "");
  return '<div class="' + classe + '" data-pedido="' + esc(p.id) + '">' +
    '<span class="marcar' + (marcado ? " on" : "") + '" data-marcar="' + esc(p.id) + '" role="checkbox" aria-checked="' +
    (marcado ? "true" : "false") + '">' + ic("check", 12) + "</span>" +
    '<span class="nome-doc"><span class="caixa-tipo">' + ic(ICONE_CATEGORIA[p.categoria] || "verified", 18) + "</span>" +
    '<span class="duas-linhas"><b>' + esc(p.titulo) + "</b><small" + (p.vence_hoje ? ' style="color:var(--acc)"' : "") + ">" +
    esc(metaDoPedido(p)) + "</small></span></span>" +
    quemPediu(p.pedido_por) +
    '<span class="espera">' + esc(esperandoHa(p.criado_em)) + "</span>" +
    '<span class="acoes-linha direita"><button data-ver="' + esc(p.id) + '">Ver</button>' +
    '<button data-recusar="' + esc(p.id) + '">Recusar</button>' +
    '<button class="primario" data-aprovar="' + esc(p.id) + '">Aprovar</button></span></div>';
}

/* O painel do pedido: o que vai sair, o efeito, se da para desfazer. */
function painelDoPedido() {
  const alca = '<button class="alca-painel" id="ap-alca" title="Alargar ou recolher o painel" aria-label="Alargar ou recolher o painel">' +
    ic(aprov.largo ? "chevron_right" : "chevron_left", 18) + "</button>";
  const p = aprov.pendentes.find((x) => x.id === aprov.aberto);
  if (!p) {
    const linhas = aprov.leitura && aprov.leitura.linhas ? aprov.leitura.linhas : [];
    return '<aside class="acervo-painel">' + alca + '<div class="rolagem"><div class="painel-vazio"><h3>' +
      (linhas.length ? "Leitura da fila" : "Nenhum pedido aberto") + "</h3>" +
      (linhas.length
        ? '<div class="leitura-fila">' + linhas.map((x) => "<span>" + ic("info", 18) + "<span>" + esc(x) + "</span></span>").join("") + "</div>"
        : "<p>Clique numa linha para ver o que vai sair, o efeito e se dá para desfazer.</p>") +
      "</div></div></aside>";
  }

  const chave = CHAVE_DA_CATEGORIA[p.categoria];
  const regra = chave && autonomiaAtual()[chave]
    ? "o assistente pode fazer isso sem pedir"
    : "você aprova · o assistente não faz isso sozinho";
  const dados = p.dados || {};
  const arquivos = Array.isArray(dados.arquivos) ? dados.arquivos : (Array.isArray(dados.caminhos) ? dados.caminhos : []);
  const para = Array.isArray(dados.para) ? dados.para : (Array.isArray(dados.destinatarios) ? dados.destinatarios : (dados.para ? [dados.para] : []));
  // Caminho inteiro vira so o nome do arquivo: a pasta esta no resumo.
  const nomeDe = (x) => {
    const bruto = typeof x === "string" ? x : (x.nome || x.arquivo || x.caminho || x.email || "");
    return bruto.includes("@") ? bruto : bruto.split(/[\\/]/).pop();
  };
  const saida = (arquivos.length || para.length)
    ? '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>O que vai sair</span><span class="contagem">' +
      (para.length ? plural(para.length, "destinatário") : plural(arquivos.length, "arquivo")) + "</span></div>" +
      (para.length ? '<div style="display:grid;gap:8px">' + para.slice(0, 8).map((x) =>
        '<div class="arquivo-painel">' + ic("mail", 16) + "<span>" + esc(nomeDe(x)) + "</span></div>").join("") + "</div>" : "") +
      (arquivos.length ? '<div style="display:grid;gap:8px">' + arquivos.slice(0, 8).map((x) => {
        const nome = nomeDe(x);
        return '<div class="arquivo-painel">' + glifo(nome) + "<span>" + esc(nome) + "</span></div>";
      }).join("") + (arquivos.length > 8 ? '<span class="nota-barra">e mais ' + (arquivos.length - 8) + "</span>" : "") + "</div>" : "") +
      "</div>"
    : "";

  return '<aside class="acervo-painel">' + alca + '<div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + esc(p.titulo) + '</h3><span class="meta">Pedido por ' +
    esc(p.pedido_por || "Assistente") + " · " + esc(quando(p.criado_em)) + " · " + esc(p.categoria_rotulo) + "</span></span>" +
    '<button class="voltar" id="ap-fechar" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>" +
    '<div class="painel-acoes"><button class="primario" data-aprovar="' + esc(p.id) + '">' + ic("check", 16) + esc(VERBO_APROVAR[p.categoria] || "Aprovar") + "</button>" +
    '<button data-recusar="' + esc(p.id) + '">' + ic("close", 16) + "Recusar</button></div>" +
    (p.resumo ? '<div class="resumo-painel"><p>' + esc(p.resumo) + "</p></div>" : "") +
    saida +
    '<div class="painel-chaves">' +
    '<div class="chave-valor"><span>Regra de alçada</span><b>' + regra + "</b></div>" +
    '<div class="chave-valor"><span>Efeito</span><b class="' + (p.reversivel ? "" : "acc") + '">' + (p.reversivel ? "dá para desfazer" : "externo · irreversível") + "</b></div>" +
    (p.prazo ? '<div class="chave-valor"><span>Prazo</span><b class="' + (p.vence_hoje ? "acc" : "") + '">' + dataLonga(p.prazo) + "</b></div>" : "") +
    '<div class="chave-valor"><span>Se recusar</span><b>encerra o pedido · nada é executado</b></div>' +
    '<div class="chave-valor"><span>Pedido em</span><b>' + dataHoraCurta(p.criado_em) + "</b></div></div>" +
    ((p.etiquetas || []).length
      ? '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Etiquetas</span></div><div class="doc-etiquetas">' +
        p.etiquetas.map((e) => '<span class="etiqueta">' + esc(e) + "</span>").join("") + "</div></div>"
      : "") +
    "</div></aside>";
}

function ligarAprovacoes() {
  const centro = $("centro");
  centro.querySelectorAll("[data-filtro-ap]").forEach((b) => {
    b.onclick = () => { aprov.filtro = b.dataset.filtroAp; desenharAprovacoes(); };
  });
  centro.querySelectorAll("[data-marcar]").forEach((c) => {
    c.onclick = (e) => {
      e.stopPropagation();
      const id = c.dataset.marcar;
      if (aprov.marcados.has(id)) aprov.marcados.delete(id); else aprov.marcados.add(id);
      desenharAprovacoes();
    };
  });
  const todos = $("ap-todos");
  if (todos) todos.onclick = () => {
    aprov.marcados = aprov.marcados.size === aprov.pendentes.length ? new Set() : new Set(aprov.pendentes.map((p) => p.id));
    desenharAprovacoes();
  };
  centro.querySelectorAll("[data-pedido]").forEach((l) => {
    l.onclick = () => { aprov.aberto = aprov.aberto === l.dataset.pedido ? null : l.dataset.pedido; desenharAprovacoes(); };
  });
  centro.querySelectorAll("[data-ver]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); aprov.aberto = b.dataset.ver; desenharAprovacoes(); };
  });
  centro.querySelectorAll("[data-aprovar]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); decidirPedidos([b.dataset.aprovar], true); };
  });
  centro.querySelectorAll("[data-recusar]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); decidirPedidos([b.dataset.recusar], false); };
  });
  const aprovar = $("ap-aprovar"), recusar = $("ap-recusar");
  if (aprovar) aprovar.onclick = () => decidirPedidos(Array.from(aprov.marcados), true);
  if (recusar) recusar.onclick = () => decidirPedidos(Array.from(aprov.marcados), false);
  const alca = $("ap-alca");
  if (alca) alca.onclick = () => { aprov.largo = !aprov.largo; desenharAprovacoes(); };
  const fechar = $("ap-fechar");
  if (fechar) fechar.onclick = () => { aprov.aberto = null; desenharAprovacoes(); };
}

/* Ctrl+Enter na fila: aprova o que esta marcado. Sem nada marcado nao faz
   nada calado - dizer "marque primeiro" e melhor que parecer que travou. */
function aprovarMarcados() {
  const ids = Array.from(aprov.marcados);
  if (!ids.length) { avisoCert("marque os pedidos que você quer aprovar"); return; }
  decidirPedidos(ids, true);
}

async function decidirPedidos(ids, aprovar) {
  if (!ids.length) return;
  const quais = ids.map((id) => aprov.pendentes.find((p) => p.id === id)).filter(Boolean);
  const semVolta = quais.filter((p) => !p.reversivel);

  const titulo = (aprovar ? "Aprovar " : "Recusar ") + plural(ids.length, "pedido") + "?";
  let texto = aprovar ? "A ação é executada agora." : "Os pedidos saem da fila sem executar.";
  if (aprovar && semVolta.length) texto += "\n" + plural(semVolta.length, "não tem", "não têm") + " como desfazer depois.";
  if (!(await confirmar({ titulo: titulo, contexto: "Aprovações", texto: texto, confirmar: aprovar ? "Aprovar" : "Recusar", perigo: aprovar && semVolta.length > 0 }))) return;

  atualizarSelo(true);
  try {
    const r = await fetch("/api/aprovacoes/decidir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: ids, aprovar: aprovar }),
    });
    const d = await r.json();
    aprov.pendentes = d.pendentes;
    aprov.hoje = d.hoje;
    aprov.leitura = d.leitura;
    aprov.marcados = new Set();
    if (aprov.visao === "fila") desenharAprovacoes();
    if (d.falhas.length) {
      avisoCert("Não consegui em " + d.falhas.length + ": " + d.falhas.map((f) => f.motivo).join("; "));
    } else {
      avisoCert(aprovar ? plural(ids.length, "pedido") + (ids.length === 1 ? " aprovado" : " aprovados") : plural(ids.length, "pedido") + (ids.length === 1 ? " recusado" : " recusados"));
    }
    carregarStatus();
    contarPendencias();
  } catch (err) {
    avisoCert("Falha ao decidir: " + err);
  } finally {
    atualizarSelo(false);
  }
}

/* ----------------------------------------------------------- historico */
/* O servidor guarda as decisoes de hoje; e o que a tela mostra, dizendo isso. */

async function mostrarHistoricoDeAprovacoes() {
  abrirTela("Histórico de aprovações", { cheia: true });
  aprov.visao = "historico";
  cabecalhoAprovacoes("historico");
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal">' + esqueleto("lista") + '</div></div>';
  if (!(await carregarFila())) return;
  desenharHistorico();
  atualizarPostura();
}

function seloDecisao(p) {
  if (p.estado === "aprovado") return '<span class="pilula-estado ok"><i></i>Aprovado' + (p.resultado ? " · " + esc(p.resultado) : "") + "</span>";
  if (p.estado === "recusado") return '<span class="pilula-estado prazo"><i></i>Recusado</span>';
  return '<span class="pilula-estado atencao"><i></i>Não deu' + (p.resultado ? " · " + esc(p.resultado) : "") + "</span>";
}

function desenharHistorico() {
  const lista = aprov.hoje.slice().sort((a, b) => (b.decidido_em || "").localeCompare(a.decidido_em || ""));
  const aprovados = lista.filter((p) => p.estado === "aprovado").length;
  const recusados = lista.filter((p) => p.estado === "recusado").length;
  const falhas = lista.length - aprovados - recusados;
  $("conversa-meta").textContent = plural(lista.length, "decisão", "decisões") + " hoje · " + aprovados + " aprovadas · " +
    recusados + " recusadas" + (falhas ? " · " + falhas + " não deram" : "");
  if (aprov.aberto && !lista.some((p) => p.id === aprov.aberto)) aprov.aberto = null;

  const linhas = lista.length ? lista.map((p) => {
    const classe = "tabela-linha colunas-historico" + (aprov.aberto === p.id ? " aberta" : "");
    return '<div class="' + classe + '" data-pedido="' + esc(p.id) + '">' +
      '<span class="nome-doc"><span class="caixa-tipo">' + ic(ICONE_CATEGORIA[p.categoria] || "verified", 18) + "</span>" +
      '<span class="duas-linhas"><b>' + esc(p.titulo) + "</b><small>" + esc(metaDoPedido(p)) + "</small></span></span>" +
      quemPediu(p.pedido_por) +
      '<span class="quando-doc">você</span>' +
      '<span class="espera">' + dataHoraCurta(p.decidido_em) + "</span>" +
      '<span class="acoes-linha direita">' + seloDecisao(p) + "</span></div>";
  }).join("")
    : '<div class="painel-vazio"><h3>Nenhuma decisão hoje</h3><p>O que você aprovar ou recusar aparece aqui, com o resultado.</p></div>';

  $("centro").innerHTML =
    '<div class="acervo' + (aprov.largo ? " painel-largo" : "") + '"><div class="acervo-principal"><div class="tabela-cartao">' +
    '<div class="tabela-barra"><span class="visoes"><button class="ativa">Hoje · ' + lista.length + "</button></span>" +
    '<span class="nota-barra">O histórico completo fica em disco; a tela mostra o de hoje</span></div>' +
    '<div class="tabela-cabecalho colunas-historico"><span>Pedido</span><span>Pedido por</span><span>Decidido por</span><span>Quando</span><span style="text-align:right">Resultado</span></div>' +
    '<div class="tabela-corpo">' + linhas + "</div>" +
    '<div class="tabela-rodape"><span>' + plural(lista.length, "decisão", "decisões") + ' hoje</span><span class="cresce"></span>' +
    "<span>Toda ação executada é reversível ou registrada</span></div></div></div>" + painelDoHistorico(lista) + "</div>";
  ligarHistorico();
}

function painelDoHistorico(lista) {
  const alca = '<button class="alca-painel" id="ap-alca" title="Alargar ou recolher o painel" aria-label="Alargar ou recolher o painel">' +
    ic(aprov.largo ? "chevron_right" : "chevron_left", 18) + "</button>";
  const p = lista.find((x) => x.id === aprov.aberto);
  if (!p) {
    return '<aside class="acervo-painel">' + alca + '<div class="rolagem"><div class="painel-vazio"><h3>Nenhuma decisão aberta</h3>' +
      "<p>Clique numa linha para ver a linha do tempo do pedido.</p></div></div></aside>";
  }
  const hora = (iso) => (iso || "").slice(11, 16);
  const decisao = p.estado === "aprovado" ? "Aprovado" : (p.estado === "recusado" ? "Recusado" : "Não deu");
  return '<aside class="acervo-painel">' + alca + '<div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + esc(p.titulo) + '</h3><span class="meta">' + decisao +
    " por você · " + dataHoraCurta(p.decidido_em) + " · " + esc(p.categoria_rotulo) + "</span></span>" +
    '<button class="voltar" id="ap-fechar" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>" +
    (p.resumo ? '<div class="resumo-painel"><p>' + esc(p.resumo) + "</p></div>" : "") +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Linha do tempo</span></div><div class="linha-tempo">' +
    '<div><span class="hora">' + esc(hora(p.criado_em)) + "</span><span>" + esc(p.pedido_por || "Assistente") + " pediu: " + esc(p.titulo) + "</span></div>" +
    '<div><span class="hora">' + esc(hora(p.decidido_em)) + "</span><span>Você " + (p.estado === "recusado" ? "recusou" : "aprovou") + "</span></div>" +
    (p.resultado ? '<div><span class="hora"></span><span>' + esc(p.resultado) + "</span></div>" : "") + "</div></div>" +
    '<div class="painel-chaves"><div class="chave-valor"><span>Efeito</span><b class="' + (p.reversivel ? "" : "acc") + '">' +
    (p.reversivel ? "reversível" : "externo · irreversível") + "</b></div>" +
    '<div class="chave-valor"><span>Resultado</span><b>' + esc(p.resultado || (p.estado === "recusado" ? "nada foi executado" : "—")) + "</b></div></div>" +
    "</div></aside>";
}

function ligarHistorico() {
  const centro = $("centro");
  centro.querySelectorAll("[data-pedido]").forEach((l) => {
    l.onclick = () => { aprov.aberto = aprov.aberto === l.dataset.pedido ? null : l.dataset.pedido; desenharHistorico(); };
  });
  const alca = $("ap-alca");
  if (alca) alca.onclick = () => { aprov.largo = !aprov.largo; desenharHistorico(); };
  const fechar = $("ap-fechar");
  if (fechar) fechar.onclick = () => { aprov.aberto = null; desenharHistorico(); };
}

/* ------------------------------------------------------ regras de alcada */
/* A autonomia do assistente, a mesma de Configuracoes. Ligada, a acao
   acontece direto; desligada, para na fila. O padrao e sempre o mais
   cauteloso. */

async function mostrarRegrasDeAlcada() {
  abrirTela("Regras de alçada", { cheia: true });
  aprov.visao = "regras";
  cabecalhoAprovacoes("regras");
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal">' + esqueleto("lista") + '</div></div>';
  try {
    aprov.regras = await (await fetch("/api/preferencias")).json();
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' + esc(String(err)) + "</p></div></div>";
    return;
  }
  desenharRegras();
  atualizarPostura();
}

function desenharRegras() {
  const opcoes = (aprov.regras && aprov.regras.autonomia_opcoes) || [];
  const ligadas = autonomiaAtual();
  $("conversa-meta").textContent = plural(opcoes.length, "regra") + " · quem aprova o quê";
  if (aprov.regraAberta && !opcoes.some((o) => o.chave === aprov.regraAberta)) aprov.regraAberta = null;

  const linhas = opcoes.map((o) => {
    const ligada = Boolean(ligadas[o.chave]);
    const classe = "tabela-linha colunas-regras" + (aprov.regraAberta === o.chave ? " aberta" : "");
    const quem = o.travada ? '<span class="pill-papel">indisponível</span>'
      : (ligada ? '<span class="pill-papel">Assistente sozinho</span>' : '<span class="pill-papel forte">Você</span>');
    return '<div class="' + classe + '" data-regra="' + esc(o.chave) + '">' +
      '<span class="nome-doc"><span class="caixa-tipo">' + ic(ICONE_REGRA[o.chave] || "rule", 18) + "</span>" +
      '<span class="duas-linhas"><b>' + esc(o.titulo) + "</b><small>" + esc(o.explica) + "</small></span></span>" +
      '<span class="papeis">' + quem + "</span>" +
      '<span class="quando-doc">—</span>' +
      '<span class="quando-doc">' + (o.travada ? "não existe" : (ligada ? "acontece direto" : "fica na fila · nunca sai sozinho")) + "</span>" +
      (o.travada ? "<span></span>"
        : '<span class="interruptor-min' + (ligada ? " on" : "") + '" data-ligar="' + esc(o.chave) + '" role="switch" aria-checked="' +
          (ligada ? "true" : "false") + '" title="' + (ligada ? "Desligar" : "Ligar") + '"><span class="chave"></span></span>') +
      "</div>";
  }).join("");

  $("centro").innerHTML =
    '<div class="acervo' + (aprov.largo ? " painel-largo" : "") + '"><div class="acervo-principal"><div class="tabela-cartao">' +
    '<div class="tabela-barra"><span style="font:600 14px var(--sans)">Quem aprova o quê</span>' +
    '<span class="nota-barra">Nada com efeito externo acontece sem aprovação</span></div>' +
    '<div class="tabela-cabecalho colunas-regras"><span>Tipo de pedido</span><span>Quem aprova</span><span>Limite</span><span>Se ninguém decidir</span><span></span></div>' +
    '<div class="tabela-corpo">' + linhas + "</div>" +
    '<div class="tabela-rodape"><span>' + plural(opcoes.length, "regra") + '</span><span class="cresce"></span>' +
    "<span>Mudar uma regra vale na hora, para os próximos pedidos</span></div></div></div>" +
    painelDaRegra(opcoes, ligadas) + "</div>";
  ligarRegras();
}

function painelDaRegra(opcoes, ligadas) {
  const alca = '<button class="alca-painel" id="ap-alca" title="Alargar ou recolher o painel" aria-label="Alargar ou recolher o painel">' +
    ic(aprov.largo ? "chevron_right" : "chevron_left", 18) + "</button>";
  const o = opcoes.find((x) => x.chave === aprov.regraAberta);
  if (!o) {
    return '<aside class="acervo-painel">' + alca + '<div class="rolagem"><div class="painel-vazio"><h3>Nenhuma regra aberta</h3>' +
      "<p>Ligada, a ação acontece direto. Desligada, para na fila e espera o seu sim. O padrão é sempre o mais cauteloso.</p></div></div></aside>";
  }
  const ligada = Boolean(ligadas[o.chave]);
  const naFila = aprov.pendentes.filter((p) => CHAVE_DA_CATEGORIA[p.categoria] === o.chave).length;
  return '<aside class="acervo-painel">' + alca + '<div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + esc(o.titulo) + '</h3><span class="meta">' + esc(o.explica) + "</span></span>" +
    '<button class="voltar" id="ap-fechar" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>" +
    (o.travada
      ? '<div class="painel-bloco"><p>Indisponível de propósito: o programa promete que nenhum documento sai desta máquina.</p></div>'
      : '<div class="painel-bloco"><div class="interruptor' + (ligada ? " on" : "") + '" data-ligar="' + esc(o.chave) +
        '" role="switch" aria-checked="' + (ligada ? "true" : "false") + '" tabindex="0"><span>Acontece sem pedir</span><span class="chave"></span></div></div>') +
    '<div class="painel-chaves"><div class="chave-valor"><span>Hoje</span><b>' + (ligada ? "o assistente faz sozinho" : "para na fila e espera você") + "</b></div>" +
    '<div class="chave-valor"><span>Padrão</span><b>' + (o.padrao ? "ligado" : "desligado") + "</b></div>" +
    '<div class="chave-valor"><span>Na fila agora</span><b>' + naFila + "</b></div></div>" +
    (o.travada ? "" : '<div class="painel-botoes"><button id="regra-padrao"' + (ligada === Boolean(o.padrao) ? " disabled" : "") + ">Restaurar padrão</button></div>") +
    "</div></aside>";
}

function ligarRegras() {
  const centro = $("centro");
  centro.querySelectorAll("[data-regra]").forEach((l) => {
    l.onclick = () => { aprov.regraAberta = aprov.regraAberta === l.dataset.regra ? null : l.dataset.regra; desenharRegras(); };
  });
  centro.querySelectorAll("[data-ligar]").forEach((s) => {
    s.onclick = (e) => { e.stopPropagation(); gravarRegra(s.dataset.ligar, !s.classList.contains("on")); };
    s.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); s.click(); } };
  });
  const padrao = $("regra-padrao");
  if (padrao) padrao.onclick = () => {
    const o = ((aprov.regras && aprov.regras.autonomia_opcoes) || []).find((x) => x.chave === aprov.regraAberta);
    if (o) gravarRegra(o.chave, Boolean(o.padrao));
  };
  const alca = $("ap-alca");
  if (alca) alca.onclick = () => { aprov.largo = !aprov.largo; desenharRegras(); };
  const fechar = $("ap-fechar");
  if (fechar) fechar.onclick = () => { aprov.regraAberta = null; desenharRegras(); };
}

async function gravarRegra(chave, ligar) {
  const pr = aprov.regras.preferencias || aprov.regras;
  const autonomia = Object.assign({}, pr.autonomia || {});
  autonomia[chave] = ligar;
  try {
    const r = await fetch("/api/preferencias", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ autonomia: autonomia }),
    });
    if (!r.ok) throw new Error(await erroDe(r));
    pr.autonomia = autonomia;
    desenharRegras();
    avisoCert(ligar ? "ligado: passa a acontecer sem pedir" : "desligado: volta a parar na fila");
  } catch (err) {
    avisoCert("não consegui gravar: " + err);
  }
}

/* O menu mostra quantos pedidos esperam - a fila nao serve se ninguem ve. */
async function contarPendencias() {
  try {
    const d = await (await fetch("/api/aprovacoes")).json();
    const n = d.pendentes.length;
    document.querySelectorAll('[data-destino="aprovacoes"] .conta').forEach((c) => {
      c.textContent = n ? String(n) : "";
      c.hidden = !n;
    });
  } catch (err) { /* sem numero e melhor que numero errado */ }
}

setInterval(contarPendencias, 8000);

