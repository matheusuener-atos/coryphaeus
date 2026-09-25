/* -------------------------------------------------------- habilidades */
/* O catalogo mora em Configuracoes > Aprendizado; fica aqui so o atalho de usar. */

function usarHabilidade(acao) {
  if (acao === "organizacao") { $("centro").innerHTML = ""; organizarComecar(); return; }
  if (acao === "anexar") { $("nova").click(); $("arquivos").click(); return; }
  $("nova").click();
  if (acao === "busca") $("pedido").placeholder = "Digite a palavra e clique em Buscar…";
  $("pedido").focus();
}


/* -------------------------------------------------------- organizador */
/*
   A visao Organizar do Acervo (docs/ui/03-telas-desktop.md, A5): quatro fases
   numa fita - Escolher, Ler, Conferir, Mover -, o cartao da fase no meio e,
   no painel, onde procuro e como as pastas ficam. Nada e apagado nem
   sobrescrito, e da para desfazer. Entrar na tela nao e comecar um trabalho:
   a conversa nasce quando a varredura comeca, que e quando existe trabalho.
*/

const org = {
  raizes: [], tipos: [], docs: [], selecao: new Set(), padroes: [], padrao: "", destino: "",
  fase: 0, plano: null, encontrados: null, escolhidos: new Set(), resultado: null, parado: false,
  semPedir: false,
};

// Na fita vai o verbo; o nome inteiro da fase fica no title.
const ETAPAS_ORG = [
  ["Escolher", "Escolher onde procurar"],
  ["Ler", "Ler e classificar"],
  ["Conferir", "Conferir a classificação"],
  ["Mover", "Mover para a estrutura nova"],
];

function fitaOrg(feitos, total) {
  const metas = [
    org.raizes.length ? plural(org.raizes.length, "pasta") : "",
    org.fase === 1 && total ? (feitos || 0) + " de " + total : (org.docs.length ? plural(org.docs.length, "doc") : ""),
    org.fase === 2 ? "agora" : (org.fase > 2 && org.selecao.size ? plural(org.selecao.size, "marcado") : ""),
    org.fase === 3 ? "agora" : (org.fase > 3 ? "feito" : ""),
  ];
  // O anel so gira quando e a maquina que trabalha (ler, mover). Nas fases
  // em que a pessoa decide, o marcador e parcial, sem movimento.
  const agora = org.trabalhando ? coroa(18) : ic("radio_button_partial", 18);
  return '<div class="fita" id="org-fita">' + ETAPAS_ORG.map(([curto, longo], i) => {
    const classe = i < org.fase ? "feita" : (i === org.fase ? "atual" : "");
    const icone = i < org.fase ? ic("check_circle", 18) : (i === org.fase ? agora : ic("radio_button_unchecked", 18));
    return (i ? '<span class="ic ic-16 seta">chevron_right</span>' : "") +
      '<div class="fase ' + classe + '" title="' + longo + '">' + icone + '<span class="rotulo-fase">' + curto + "</span>" +
      '<span class="meta-fase">' + esc(metas[i] || "") + "</span></div>";
  }).join("") + "</div>";
}

/* Onde procuro, no painel: as pastas escolhidas, uma por linha, e - na
   primeira fase - o botao de procurar logo embaixo delas. */
function ondeProcuro() {
  const n = org.raizes.length;
  // Depois de ler, as pastas ficam so para lembrar de onde veio; sem elas
  // (o fim do fluxo aberto pela fila, noutra sessao) o bloco nao diz nada.
  if (org.fase >= 2 && !n) return '<div id="org-onde"></div>';
  // Tirar so antes de procurar: depois, a lista do cartao ja veio delas.
  const tirar = org.fase === 0;
  const linhas = n
    ? '<div class="org-raizes">' + org.raizes.map((c, i) => {
        const nome = c.split(/[\\/]/).filter(Boolean).pop() || c;
        return '<div class="org-raiz">' + ic("folder", 16) +
          '<span class="duas-linhas"><b class="corta">' + esc(nome) + '</b><small class="corta" title="' + esc(c) + '">' + esc(c) + "</small></span>" +
          (tirar ? '<button class="org-tirar" data-tirar-raiz="' + i + '" title="Tirar esta pasta" aria-label="Tirar esta pasta">' + ic("close", 14) + "</button>" : "") + "</div>";
      }).join("") + "</div>"
    : "<p>Nenhuma pasta ainda. Marque na árvore as pastas onde devo procurar.</p>";
  const acao = org.fase === 0
    ? '<button class="primario com-icone org-largo" id="org-varrer"' + (n ? "" : " disabled") + ">" + ic("search", 16) + "Procurar documentos</button>" +
      '<small class="org-nota" id="org-nota"></small>'
    : (org.fase === 1 ? '<button class="sv-ligacao" data-outras="1">' + ic("add", 15) + "incluir outra pasta</button>" : "");
  return '<div class="painel-bloco org-onde" id="org-onde"><div class="painel-bloco-cabeca"><span>Onde eu procuro</span>' +
    '<span class="contagem">' + (n ? plural(n, "pasta") : "") + "</span></div>" + linhas + acao +
    '<small class="org-nota">Não entro em pastas do sistema nem de programas.</small></div>';
}

/* A tela inteira: a fita e o cartao da fase de um lado, o painel do outro. */
function desenharOrg(cartao) {
  $("centro").innerHTML =
    '<div class="acervo org-tela"><div class="acervo-principal">' + fitaOrg() +
    '<div class="tabela-cartao" id="org-cartao">' + cartao + "</div></div>" +
    '<aside class="acervo-painel"><div class="rolagem" id="org-painel">' + painelOrgPlano() + "</div></aside></div>";
  ligarPainelOrg();
}

function atualizarFita(feitos, total) {
  const f = $("org-fita");
  if (f) f.outerHTML = fitaOrg(feitos, total);
}

function atualizarOnde() {
  const o = $("org-onde");
  if (o) { o.outerHTML = ondeProcuro(); ligarOnde(); }
}

function ligarOnde() {
  document.querySelectorAll("[data-tirar-raiz]").forEach((b) => {
    b.onclick = () => {
      org.raizes.splice(Number(b.dataset.tirarRaiz), 1);
      atualizarOnde();
      atualizarFita();
      desenharArvore();
    };
  });
  document.querySelectorAll("[data-outras]").forEach((b) => {
    b.onclick = () => { org.fase = 0; passoOnde(); };
  });
  const varrer = $("org-varrer");
  if (varrer) varrer.onclick = organizarVarrer;
}

function limparOrg() {
  org.fase = 0; org.docs = []; org.selecao = new Set(); org.plano = null; org.resultado = null;
  org.parado = false; org.encontrados = null; org.escolhidos = new Set();
}

/* `manter` abre a tela sem zerar o que ja foi feito: e por onde a fila de
   aprovacoes devolve a pessoa ao fim do fluxo. */
async function organizarComecar(manter) {
  abrirTela("Organizar pastas", { cheia: true });
  bib.visao = "organizar";
  cabecalhoAcervo("organizar", '<button class="com-icone" id="org-de-novo">' + ic("search", 16) + "Procurar de novo</button>");
  $("org-de-novo").onclick = () => { limparOrg(); passoOnde(); };
  if (!manter) { estado.trabalhoId = null; estado.trabalho = null; }
  $("conversa-meta").textContent = "nada foi movido ainda";

  const [o, pr] = await Promise.all([
    fetch("/api/organizar/opcoes").then((r) => r.json()),
    fetch("/api/preferencias").then((r) => r.json()).catch(() => null),
  ]);
  org.tipos = o.tipos;
  org.padroes = o.padroes;
  if (!manter || !org.padrao) org.padrao = (o.padroes[0] || {}).padrao || "";
  if (!manter || !org.destino) org.destino = o.destino_sugerido;
  org.diarios = o.diarios;
  // Com a permissao de mover desligada (o padrao), o botao diz a verdade:
  // o pedido vai para a fila, nada se move ainda.
  org.semPedir = Boolean((((pr && (pr.preferencias || pr)) || {}).autonomia || {}).organizar_mover);
  if (manter) return;

  org.raizes = [];      // nada pre-selecionado: a pessoa escolhe onde procurar
  arv.abertos.clear(); arv.filhos.clear(); arv.topo = null;   // o disco pode ter mudado
  limparOrg();
  passoOnde();
  atualizarPostura();
}

/* Fase 0: onde procurar, numa arvore de pastas. A seta abre a pasta ali
   mesmo, sem sair de onde se esta; a caixinha marca onde procurar. Pasta sem
   subpasta nao tem seta - clicar nela marca. Entrar numa pasta so para
   descobrir que nao havia nada dentro era um beco. */
const arv = { abertos: new Set(), filhos: new Map(), topo: null };

function chaveDe(c) {
  return (c || "").replace(/\//g, "\\").replace(/\\+$/, "").toLowerCase();
}

/* `c` esta dentro de `r` (e nao e a propria `r`). */
function dentroDe(c, r) {
  const a = chaveDe(c), b = chaveDe(r);
  return a !== b && a.startsWith(b + "\\");
}

/* "on": marcada. "herdada": entra porque uma pasta de cima esta marcada.
   "parcial": alguma pasta de dentro esta marcada. */
function marcaDaPasta(c) {
  if (org.raizes.some((r) => chaveDe(r) === chaveDe(c))) return "on";
  if (org.raizes.some((r) => dentroDe(c, r))) return "herdada";
  if (org.raizes.some((r) => dentroDe(r, c))) return "parcial";
  return "";
}

function passoOnde() {
  org.fase = 0;
  desenharOrg(
    '<div class="cartao-cabeca"><span class="texto-cabeca"><b>Onde eu procuro</b>' +
    "<small>Marque as pastas onde devo procurar. Cada uma entra com tudo o que estiver dentro; a seta abre a pasta para marcar só uma parte.</small></span></div>" +
    '<div class="cartao-miolo"><div class="navegador"><div class="nav-lista" id="nav-lista"><div class="nav-vazio">abrindo…</div></div></div></div>' +
    '<div class="tabela-rodape"><span id="nav-nota">nenhuma pasta marcada</span><span class="cresce"></span>' +
    "<span>Nada é lido antes de você mandar procurar</span></div>"
  );
  carregarTopoDaArvore();
}

async function carregarTopoDaArvore() {
  if (!arv.topo) {
    try { arv.topo = await (await fetch("/api/pastas")).json(); } catch (err) {
      arv.topo = { atalhos: [], unidades: [], erro: "não consegui abrir: " + err };
    }
  }
  desenharArvore();
}

function noDaArvore(e, nivel) {
  const k = chaveDe(e.caminho);
  const pode = e.tem_subpastas !== false;
  const aberto = pode && arv.abertos.has(k);
  const marca = marcaDaPasta(e.caminho);
  const icone = e.tipo === "unidade" ? "desktop_windows" : (aberto ? "folder_open" : "folder");
  const marcada = marca === "on" || marca === "herdada";
  let html = '<div class="nav-item arv-no' + (marcada ? " marcada" : "") + '" data-no="' + esc(e.caminho) + '" data-pode="' + (pode ? 1 : 0) +
    '" style="--nivel:' + nivel + '">' +
    (pode
      ? '<button class="arv-seta" aria-expanded="' + aberto + '" aria-label="' + (aberto ? "Fechar" : "Abrir") + " a pasta\">" +
        ic(aberto ? "expand_more" : "chevron_right", 16) + "</button>"
      : '<span class="arv-seta"></span>') +
    '<span class="marcar' + (marca ? " on " + marca : "") + '" data-marcar-pasta="1" role="checkbox" aria-checked="' +
    (marca === "parcial" ? "mixed" : String(marcada)) + '"' + (marca === "herdada" ? ' title="Já entra pela pasta de cima"' : "") + ">" +
    ic(marca === "parcial" ? "remove" : "check", 12) + "</span>" +
    ic(icone, 16) + '<span class="corta">' + esc(e.nome) + "</span>" +
    (e.cam ? '<span class="cam">' + esc(e.cam) + "</span>" : "") + "</div>";
  if (aberto) {
    const f = arv.filhos.get(k);
    const vazio = (t) => '<div class="nav-vazio arv-vazio" style="--nivel:' + (nivel + 1) + '">' + esc(t) + "</div>";
    if (!f) html += vazio("abrindo…");
    else if (f.erro) html += vazio(f.erro);
    else if (!f.pastas.length) html += vazio("nenhuma subpasta");
    else html += f.pastas.map((x) => noDaArvore(x, nivel + 1)).join("");
  }
  return html;
}

function desenharArvore() {
  const lista = $("nav-lista");
  if (!lista || !arv.topo) return;
  const rolagem = lista.scrollTop;
  const t = arv.topo;
  lista.innerHTML =
    (t.atalhos.length ? '<div class="nav-grupo">Começar por</div>' +
      t.atalhos.map((a) => noDaArvore(Object.assign({ cam: a.caminho }, a), 0)).join("") : "") +
    (t.unidades.length ? '<div class="nav-grupo">Unidades</div>' + t.unidades.map((u) => noDaArvore(u, 0)).join("") : "") +
    (t.erro ? '<div class="nav-vazio">' + esc(t.erro) + "</div>" : "");
  lista.scrollTop = rolagem;
  lista.querySelectorAll("[data-no]").forEach((linha) => {
    linha.onclick = (ev) => {
      const caminho = linha.dataset.no;
      if (ev.target.closest("[data-marcar-pasta]") || linha.dataset.pode !== "1") return marcarPasta(caminho);
      abrirNo(caminho);
    };
  });
  const n = org.raizes.length;
  $("nav-nota").textContent = n ? plural(n, "pasta marcada", "pastas marcadas") : "nenhuma pasta marcada";
}

async function abrirNo(caminho) {
  const k = chaveDe(caminho);
  if (arv.abertos.has(k)) { arv.abertos.delete(k); desenharArvore(); return; }
  arv.abertos.add(k);
  desenharArvore();
  if (arv.filhos.has(k)) return;
  let d;
  try { d = await (await fetch("/api/pastas?caminho=" + encodeURIComponent(caminho))).json(); } catch (err) {
    d = { pastas: [], erro: "não consegui abrir: " + err };
  }
  arv.filhos.set(k, { pastas: d.pastas || [], erro: d.erro || "" });
  desenharArvore();
}

/* Marcar uma pasta leva tudo o que ha dentro: as de dentro que ja estavam
   marcadas saem da lista, que elas ja entram por esta. */
function marcarPasta(caminho) {
  const marca = marcaDaPasta(caminho);
  if (marca === "herdada") { avisoCert("Esta pasta já entra pela pasta de cima."); return; }
  if (marca === "on") org.raizes = org.raizes.filter((r) => chaveDe(r) !== chaveDe(caminho));
  else org.raizes = org.raizes.filter((r) => !dentroDe(r, caminho)).concat([caminho]);
  desenharArvore();
  atualizarOnde();
  atualizarFita();
}

async function organizarVarrer() {
  if (!org.raizes.length) return;
  $("org-varrer").disabled = true;
  $("org-nota").textContent = "procurando…";

  try {
    // Agora sim existe trabalho: a pessoa escolheu as pastas e mandou procurar.
    if (!estado.trabalhoId) {
      const nova = await (await fetch("/api/trabalhos", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pedido: "Organizar uma pasta", tipo: "organizacao" }),
      })).json();
      estado.trabalhoId = nova.id;
      estado.trabalho = nova;
      carregarTrabalhos();
    }

    const r = await fetch("/api/organizar/escanear", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raizes: org.raizes }),
    });
    if (!r.ok) throw new Error((await r.json()).detail);
    const d = await r.json();

    if (!d.total) {
      $("org-nota").textContent = "nenhum documento encontrado nessas pastas";
      $("org-varrer").disabled = false;
      return;
    }
    org.encontrados = d;
    org.escolhidos = new Set((d.arquivos || []).map((a) => a.path));
    passoEscolherLeitura();
  } catch (err) {
    $("org-nota").textContent = "não consegui procurar: " + err;
    $("org-varrer").disabled = false;
  }
}

/* Fase 1: o que a varredura achou, documento por documento, para a pessoa
   escolher o que vale ler. Varrer e barato; ler custa ~20 s por documento.
   Encadear os dois sem perguntar foi o que fez o programa sair lendo o
   computador inteiro. */
function passoEscolherLeitura() {
  const d = org.encontrados;
  org.fase = 1;
  desenharOrg(cartaoLeitura(d));
  $("conversa-meta").textContent = plural(d.total, "documento") + " encontrados · nada foi movido ainda";
  ligarLeitura();
}

function cartaoLeitura(d) {
  let detalhe = plural(d.total, "documento") + " em " + plural(d.pastas_visitadas, "pasta");
  if (d.em_cache) detalhe += " · " + d.em_cache + (d.em_cache === 1 ? " já lido antes" : " já lidos antes");
  if (d.sem_permissao) detalhe += " · " + d.sem_permissao + " sem permissão de leitura";
  if (d.grandes) detalhe += " · " + d.grandes + " grandes demais";
  const lista = d.arquivos || [];
  return '<div class="cartao-cabeca"><span class="texto-cabeca"><b>Encontrei ' + plural(d.total, "documento") + "</b><small>" +
    esc(detalhe) + "</small></span>" +
    '<span class="direita"><span class="nota-barra" id="org-escolhidos"></span>' +
    '<button id="org-ler-todos">Marcar todos</button><button id="org-so-novos">Só os novos</button></span></div>' +
    '<div class="tabela-barra org-estimativa"><span class="org-tempo" id="org-tempo-leitura"></span>' +
    '<span class="direita"><button id="org-voltar">Escolher outras pastas</button>' +
    '<button class="primario com-icone" id="org-ler">' + ic("visibility", 16) + "Ler e classificar</button></span></div>" +
    '<div class="org-andamento" id="org-andamento"></div>' +
    '<div class="tabela-cabecalho colunas-ler"><span></span><span>Documento e pasta</span><span>Tamanho</span><span>Leitura</span></div>' +
    '<div class="tabela-corpo" id="org-achados">' + lista.map(linhaAchado).join("") + "</div>" +
    '<div class="tabela-rodape"><span>Mostrando ' + lista.length + " de " + d.total +
    '</span><span class="cresce"></span><span>Nada foi lido ainda</span></div>';
}

/* A pasta do documento contada a partir da pasta escolhida, que e o que a
   pessoa reconhece: "MES 06 › Contratos", nao o caminho inteiro. */
function pastaRelativa(pasta) {
  const raiz = org.raizes.find((r) => pasta.toLowerCase().startsWith(r.toLowerCase()));
  if (!raiz) return pasta;
  const base = raiz.split(/[\\/]/).filter(Boolean).pop() || raiz;
  return [base].concat(pasta.slice(raiz.length).split(/[\\/]/).filter(Boolean)).join(" › ");
}

function linhaAchado(a) {
  const on = org.escolhidos.has(a.path);
  return '<div class="tabela-linha colunas-ler' + (on ? "" : " fora") + '" data-achado="' + esc(a.path) + '">' +
    '<span class="marcar' + (on ? " on" : "") + '" role="checkbox" aria-checked="' + on + '">' + ic("check", 12) + "</span>" +
    '<span class="nome-doc">' + glifo(a.nome) + '<span class="duas-linhas"><b>' + esc(a.nome) + "</b>" +
    '<small title="' + esc(a.pasta) + '">' + esc(pastaRelativa(a.pasta || "")) + "</small></span></span>" +
    '<span class="quando-doc">' + tamanho(Math.round((a.mb || 0) * 1024 * 1024)) + "</span>" +
    '<span class="org-lido' + (a.lido ? " ok" : "") + '">' + (a.lido ? "já lido" : "novo") + "</span></div>";
}

/* A conta do tempo refeita a cada marca: o mesmo 8 a 25 s por documento
   novo que o servidor usa; o ja lido sai na hora. */
function contaDaLeitura() {
  const d = org.encontrados;
  const lista = d.arquivos || [];
  const escolhidos = lista.filter((a) => org.escolhidos.has(a.path));
  const novos = escolhidos.filter((a) => !a.lido).length;
  const ocultos = d.total - lista.length;
  const todos = escolhidos.length === lista.length;
  $("org-escolhidos").textContent = escolhidos.length + " de " + lista.length + " marcados";
  $("org-ler").disabled = !escolhidos.length;
  let texto;
  if (!escolhidos.length) texto = "Marque o que devo ler.";
  else if (!novos) texto = "Todos os marcados já foram lidos antes: sai na hora.";
  else {
    const de = formatarMinutos(novos * 8 / 60), ate = formatarMinutos(novos * 25 / 60);
    texto = "Ler " + plural(novos, "documento novo", "documentos novos") + " deve levar " +
      (de === ate ? "<strong>" + de + "</strong>" : "de <strong>" + de + " a " + ate + "</strong>") + ". Dá para parar no meio.";
  }
  if (ocultos > 0 && todos) texto += " Os outros " + ocultos + " que não cabem na lista entram também.";
  $("org-tempo-leitura").innerHTML = texto;
}

function ligarLeitura() {
  const lista = org.encontrados.arquivos || [];
  $("org-achados").querySelectorAll("[data-achado]").forEach((linha) => {
    linha.onclick = () => {
      if (org.trabalhando) return;
      const c = linha.dataset.achado;
      if (org.escolhidos.has(c)) org.escolhidos.delete(c); else org.escolhidos.add(c);
      const on = org.escolhidos.has(c);
      linha.classList.toggle("fora", !on);
      linha.querySelector(".marcar").classList.toggle("on", on);
      contaDaLeitura();
    };
  });
  $("org-ler-todos").onclick = () => { org.escolhidos = new Set(lista.map((a) => a.path)); passoEscolherLeitura(); };
  $("org-so-novos").onclick = () => { org.escolhidos = new Set(lista.filter((a) => !a.lido).map((a) => a.path)); passoEscolherLeitura(); };
  $("org-voltar").onclick = () => { org.fase = 0; passoOnde(); };
  $("org-ler").onclick = () => {
    // Tudo marcado manda ler tudo - inclusive o que passou do limite da
    // lista. Com alguma coisa desmarcada, vai so o que esta marcado.
    const todos = lista.every((a) => org.escolhidos.has(a.path));
    ["org-ler", "org-voltar", "org-ler-todos", "org-so-novos"].forEach((id) => { $(id).disabled = true; });
    organizarClassificar(todos ? [] : [...org.escolhidos]);
  };
  contaDaLeitura();
}

function formatarMinutos(m) {
  if (m < 1) return "menos de 1 min";
  if (m < 60) return Math.round(m) + " min";
  return (m / 60).toFixed(1).replace(".", ",") + " h";
}

/* Ler. Um acervo grande leva quase uma hora; desistir tem que estar a um
   clique, nao a um fechar-a-janela. */
async function organizarClassificar(apenas) {
  const total = apenas.length || org.encontrados.total;
  org.fase = 1;
  org.trabalhando = true;
  atualizarFita(0, total);
  atualizarSelo(true);

  $("org-andamento").innerHTML = '<div class="linha-form">' + coroa(18) +
    '<span id="org-progresso">lendo 0 de ' + total + '…</span><span class="nota-barra" id="org-tempo"></span>' +
    '<button id="org-parar">Parar a leitura</button></div>';
  $("org-parar").onclick = async () => {
    $("org-parar").disabled = true;
    $("org-tempo").textContent = "parando depois do documento atual…";
    await fetch("/api/organizar/cancelar", { method: "POST" });
  };

  const inicio = Date.now();
  try {
    const r = await fetch("/api/organizar/classificar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apenas: apenas }),
    });
    if (!r.ok) throw new Error((await r.json()).detail);

    const leitor = r.body.getReader();
    const dec = new TextDecoder();
    let buffer = "";

    while (true) {
      const passo = await leitor.read();
      if (passo.done) break;
      buffer += dec.decode(passo.value, { stream: true });
      const partes = buffer.split("\n\n");
      buffer = partes.pop();

      for (const parte of partes) {
        const mt = parte.match(/^event: (.+)$/m);
        const md = parte.match(/^data: (.*)$/m);
        if (!mt || !md) continue;
        const d = JSON.parse(md[1]);

        if (mt[1] === "progresso") {
          atualizarFita(d.indice, d.total);
          const p = $("org-progresso");
          if (p) p.textContent = "lendo " + d.indice + " de " + d.total + (d.nome ? " — " + d.nome : "");
          const c = $("org-tempo");
          if (c) {
            const seg = (Date.now() - inicio) / 1000;
            const faltam = d.indice ? (seg / d.indice) * (d.total - d.indice) : 0;
            c.textContent = faltam > 5 ? "faltam ~" + Math.ceil(faltam / 60) + " min" : Math.round(seg) + " s";
          }
        } else if (mt[1] === "resultados") {
          org.docs = d.documentos;
          org.selecao = new Set(d.documentos.filter((x) => !x.erro).map((x) => x.arquivo));
          org.parado = Boolean(d.parado);
          if (d.documentos.length) passoConferir();
          else {
            const a = $("org-andamento");
            if (a) a.innerHTML = '<p class="nota">nenhum documento pôde ser lido</p>';
          }
        } else if (mt[1] === "erro") {
          const a = $("org-andamento");
          if (a) a.innerHTML = '<div class="aprovacao"><p><strong>Não consegui ler os documentos.</strong> ' + esc(d.mensagem) + "</p></div>";
        }
      }
    }
  } catch (err) {
    const a = $("org-andamento");
    if (a) a.innerHTML = '<div class="aprovacao"><p><strong>Não consegui classificar.</strong> ' + esc(String(err)) + "</p></div>";
  } finally {
    org.trabalhando = false;
    atualizarSelo(false);
    atualizarFita();
  }
}

/* Fase 2: conferir. Cliente e tipo sao palpite do modelo; a pessoa corrige
   e desmarca. O plano do painel se monta sozinho conforme ela mexe. */
function passoConferir() {
  org.fase = 2;
  desenharOrg(cartaoConferir());
  $("conversa-meta").textContent = plural(org.docs.length, "documento") + " encontrados · nada foi movido ainda";
  ligarConferir();
  montarPlano();
}

function cartaoConferir() {
  return '<div class="cartao-cabeca"><span class="texto-cabeca"><b>Confira antes de eu mexer em alguma coisa</b>' +
    "<small>Cliente e tipo são palpite meu. Corrija o que estiver errado e desmarque o que não deve entrar.</small></span>" +
    '<span class="direita"><span class="nota-barra" id="org-marcados">' + org.selecao.size + " de " + org.docs.length + " marcados</span>" +
    '<button id="org-todos">Marcar todos</button><button id="org-incertos">Só os incertos</button></span></div>' +
    (org.parado
      ? '<div class="tabela-barra"><span class="nota-barra">Leitura interrompida: li ' + plural(org.docs.length, "documento") +
        " antes de parar. Se mandar ler de novo, continua daqui.</span></div>"
      : "") +
    '<div class="tabela-cabecalho colunas-conferir"><span></span><span>Documento e cliente</span><span>Tipo</span><span>Certeza</span></div>' +
    '<div class="tabela-corpo" id="org-corpo">' + org.docs.map(linhaConferir).join("") + "</div>" +
    '<div class="tabela-rodape"><span>Mostrando ' + org.docs.length + " de " + org.docs.length +
    '</span><span class="cresce"></span><span>Nada foi movido ainda</span></div>';
}

function linhaConferir(d, i) {
  const marcado = org.selecao.has(d.arquivo);
  const rotulo = { alta: "Alta", media: "Média", baixa: "Baixa" };
  return '<div class="tabela-linha colunas-conferir' + (marcado ? "" : " fora") + '" data-i="' + i + '">' +
    '<span class="marcar' + (marcado ? " on" : "") + (d.erro ? " desligado" : "") + '" data-a="marcar" role="checkbox" aria-checked="' +
    (marcado ? "true" : "false") + '">' + ic("check", 12) + "</span>" +
    '<span class="nome-doc">' + glifo(d.nome) + '<span class="duas-linhas"><b>' + esc(d.nome) + "</b>" +
    (d.erro
      ? "<small>" + esc(d.erro) + "</small>"
      : '<small><input type="text" class="campo-cliente" data-a="cliente" value="' + esc(d.cliente || "") +
        '" placeholder="cliente não identificado">' + (d.data ? " · " + esc(d.data) : "") + "</small>") + "</span></span>" +
    '<select class="campo-tipo" data-a="tipo"' + (d.erro ? " disabled" : "") + ">" +
    org.tipos.map((t) => '<option value="' + t.valor + '"' + (t.valor === d.tipo ? " selected" : "") + ">" + esc(t.rotulo) + "</option>").join("") +
    "</select>" +
    '<span class="certeza ' + esc(d.confianca) + '">' + (rotulo[d.confianca] || esc(d.confianca)) + "</span></div>";
}

function ligarConferir() {
  const corpo = $("org-corpo");
  corpo.querySelectorAll(".tabela-linha").forEach((tr) => {
    const d = org.docs[Number(tr.dataset.i)];
    tr.querySelector('[data-a="marcar"]').onclick = (e) => {
      e.stopPropagation();
      if (d.erro) return;
      if (org.selecao.has(d.arquivo)) org.selecao.delete(d.arquivo); else org.selecao.add(d.arquivo);
      const dentro = org.selecao.has(d.arquivo);
      tr.classList.toggle("fora", !dentro);
      tr.querySelector('[data-a="marcar"]').classList.toggle("on", dentro);
      $("org-marcados").textContent = org.selecao.size + " de " + org.docs.length + " marcados";
      atualizarFita();
      montarPlano();
    };
    tr.querySelector('[data-a="tipo"]').onchange = (e) => {
      d.tipo = e.target.value;
      const achado = org.tipos.find((t) => t.valor === e.target.value);
      if (achado) d.tipo_rotulo = achado.rotulo;
      montarPlano();
    };
    const cli = tr.querySelector('[data-a="cliente"]');
    if (cli) {
      cli.oninput = (e) => { d.cliente = e.target.value; };
      cli.onchange = montarPlano;
      cli.onclick = (e) => e.stopPropagation();
    }
  });
  $("org-todos").onclick = () => {
    org.selecao = new Set(org.docs.filter((d) => !d.erro).map((d) => d.arquivo));
    passoConferir();
  };
  $("org-incertos").onclick = () => {
    org.selecao = new Set(org.docs.filter((d) => !d.erro && d.confianca !== "alta").map((d) => d.arquivo));
    passoConferir();
  };
}

/* As pastas do plano contadas a partir do destino e agrupadas pela
   primeira pasta (o cliente, no padrao de sempre): o caminho inteiro nao
   cabe no painel e repete o destino em toda linha. */
function arvoreDoPlano(pastas, destino) {
  const base = (destino || "").replace(/[\\/]+$/, "").toLowerCase();
  const grupos = new Map();
  for (const x of pastas) {
    const rel = x.pasta.toLowerCase().startsWith(base) ? x.pasta.slice(base.length) : x.pasta;
    const [topo, ...resto] = rel.split(/[\\/]/).filter(Boolean);
    const g = grupos.get(topo || x.pasta) || { n: 0, folhas: [] };
    g.n += x.arquivos;
    if (resto.length) g.folhas.push({ nome: resto.join(" › "), n: x.arquivos });
    grupos.set(topo || x.pasta, g);
  }
  return '<div class="org-plano">' + [...grupos].map(([topo, g]) =>
    '<div class="org-plano-grupo"><div class="org-plano-topo">' + ic("folder", 16) + '<span class="corta">' + esc(topo) + "</span><small>" + g.n + "</small></div>" +
    g.folhas.map((f) => '<div class="org-plano-folha"><span class="corta">' + esc(f.nome) + "</span><small>" + f.n + "</small></div>").join("") +
    "</div>").join("") + "</div>";
}

function nomeDaPasta(caminho) {
  return (caminho || "").split(/[\\/]/).filter(Boolean).pop() || caminho || "";
}

/* O painel: onde procuro, a estrutura, o destino e o plano. */
function painelOrgPlano() {
  const feito = org.fase === 4 && org.resultado;
  const p = feito ? { total: org.resultado.movidos, pastas: org.resultado.pastas || [], destino: org.resultado.destino, ignorados: [] } : org.plano;
  const pronto = org.fase === 2 && p && p.total;
  const meta = feito ? plural(p.total, "arquivo") + " no lugar novo"
    : (p ? plural(p.total, "arquivo") + " em " + plural(p.pastas.length, "pasta") : "O plano aparece depois de ler e conferir");
  return '<div class="painel-cabeca"><span class="titulo-painel"><h3>Como as pastas ficam</h3><span class="meta">' + meta + "</span></span></div>" +
    ondeProcuro() +
    '<div class="painel-bloco"><div class="campo-painel"><label for="org-padrao">Estrutura</label><select id="org-padrao"' + (feito ? " disabled" : "") + ">" +
    (org.padroes || []).map((x) => '<option value="' + esc(x.padrao) + '"' + (org.padrao === x.padrao ? " selected" : "") + ">" + esc(x.rotulo) + "</option>").join("") +
    "</select></div>" +
    '<div class="campo-painel"><label for="org-destino">Pasta de destino</label><div class="com-botao">' +
    '<input type="text" id="org-destino" value="' + esc(org.destino || "") + '"' + (feito ? " disabled" : "") + ">" +
    (window.pywebview && !feito ? '<button id="org-escolher">Trocar</button>' : "") + "</div></div></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>' + (feito ? "Como ficou" : "Plano") + '</span><span class="contagem">' +
    (p && p.pastas.length ? plural(p.pastas.length, "pasta") + " em " + esc(nomeDaPasta(p.destino)) : "") + "</span></div>" +
    (p && p.pastas.length
      ? arvoreDoPlano(p.pastas, p.destino) +
        (p.ignorados.length ? '<small class="org-nota">' + plural(p.ignorados.length, "arquivo") + " sem classificação ficam onde estão.</small>" : "")
      : "<p>Escolha as pastas, mande ler e confira a classificação. O plano se monta sozinho.</p>") + "</div>" +
    (pronto
      ? '<div class="painel-bloco org-pronto"><p>' +
        (org.semPedir ? "Vou mover " : "Peço para mover ") + "<b>" + plural(p.total, "arquivo") + "</b> para <b>" + plural(p.pastas.length, "pasta") +
        "</b> em <b>" + esc(nomeDaPasta(p.destino)) + "</b>. " +
        (org.semPedir ? "" : "O pedido vai para Aprovações e nada se move antes do seu sim. ") +
        "Nada é apagado nem sobrescrito, e dá para desfazer depois.</p>" +
        '<button class="primario com-icone org-largo" id="org-aprovar">' + ic("drive_file_move", 16) +
        (org.semPedir ? "Mover agora" : "Enviar para aprovação") + "</button>" +
        '<div class="org-links"><button class="sv-ligacao" id="org-revisar">Revisar o plano</button><span class="cresce"></span>' +
        '<button class="sv-ligacao" id="org-recomecar">' + ic("restart_alt", 15) + "Começar de novo</button></div></div>"
      : (org.fase >= 2 && !feito
        ? '<div class="painel-bloco org-links"><span class="cresce"></span><button class="sv-ligacao" id="org-recomecar">' + ic("restart_alt", 15) + "Começar de novo</button></div>"
        : ""));
}

function ligarPainelOrg() {
  ligarOnde();
  const padrao = $("org-padrao");
  if (padrao) padrao.onchange = (e) => { org.padrao = e.target.value; montarPlano(); };
  const destino = $("org-destino");
  if (destino) destino.onchange = (e) => { org.destino = e.target.value.trim(); montarPlano(); };
  const escolher = $("org-escolher");
  if (escolher) escolher.onclick = async () => {
    const p = await window.pywebview.api.escolher_pasta();
    if (p) { org.destino = p; $("org-destino").value = p; montarPlano(); }
  };
  const revisar = $("org-revisar");
  if (revisar) revisar.onclick = () => {
    const c = $("org-corpo");
    if (c) c.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const aprovar = $("org-aprovar");
  if (aprovar) aprovar.onclick = organizarAplicar;
  const recomecar = $("org-recomecar");
  if (recomecar) recomecar.onclick = () => { limparOrg(); passoOnde(); };
}

function atualizarPainelOrg() {
  const p = $("org-painel");
  if (p) { p.innerHTML = painelOrgPlano(); ligarPainelOrg(); }
}

function corpoPlano() {
  return {
    destino: org.destino || "",
    padrao: org.padrao || "",
    apenas: Array.from(org.selecao),
    ajustes: org.docs.filter((d) => org.selecao.has(d.arquivo))
      .map((d) => ({ arquivo: d.arquivo, cliente: d.cliente, tipo: d.tipo })),
  };
}

/* O plano se monta no servidor a cada mexida na conferencia, com uma espera
   curta para nao pedir um plano por tecla. */
let planoTimer = null;
function montarPlano() {
  clearTimeout(planoTimer);
  planoTimer = setTimeout(async () => {
    if (org.fase !== 2 || !org.selecao.size) { org.plano = null; atualizarPainelOrg(); return; }
    try {
      const r = await fetch("/api/organizar/plano", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpoPlano()),
      });
      if (!r.ok) throw new Error((await r.json()).detail);
      org.plano = await r.json();
    } catch (err) {
      org.plano = null;
      avisoCert("não consegui montar o plano: " + err);
    }
    atualizarPainelOrg();
  }, 250);
}

/* Fase 3: mover. Ou o pedido vai para a fila, se a permissao de mover sem
   pedir estiver desligada; nesse caso o fim do fluxo volta para ca depois
   do sim, por organizarDesfecho. */
async function organizarAplicar() {
  org.fase = 3;
  org.trabalhando = true;
  atualizarFita();
  atualizarSelo(true);
  const cartao = $("org-cartao");
  cartao.innerHTML = '<div class="cartao-cabeca"><span class="texto-cabeca"><b>Movendo…</b><small>Nada é apagado nem sobrescrito.</small></span></div>' +
    '<div class="cartao-miolo"><div class="linha-form">' + coroa(18) + " movendo os arquivos</div></div>";

  try {
    const r = await fetch("/api/organizar/aplicar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpoPlano()),
    });
    if (!r.ok) throw new Error((await r.json()).detail);
    const d = await r.json();

    if (d.aguardando_aprovacao) {
      org.pedido = d.pedido.id;
      cartao.innerHTML = '<div class="cartao-cabeca"><span class="texto-cabeca"><b>Pedido enviado para aprovação</b><small>Nada foi movido ainda. ' +
        plural(d.total, "arquivo") + " esperam o seu sim em Aprovações. Depois de aprovar, eu trago você de volta para ver como ficou.</small></span></div>" +
        '<div class="cartao-miolo"><div class="linha-form"><button class="primario" id="org-ver-fila">Abrir Aprovações</button></div></div>';
      $("org-ver-fila").onclick = () => { marcarDestino("aprovacoes"); mostrarAprovacoes(); };
      contarPendencias();
      atualizarPainelOrg();
      return;
    }

    mostrarMovidos(d);
  } catch (err) {
    cartao.innerHTML = '<div class="cartao-miolo"><div class="aprovacao"><p><strong>Não consegui mover.</strong> ' + esc(String(err)) + "</p></div></div>";
  } finally {
    org.trabalhando = false;
    atualizarSelo(false);
    atualizarFita();
    carregarTrabalhos();
  }
}

/* O fim do fluxo: quantos foram, para onde, e o desfazer a um clique. Serve
   ao mover direto e ao mover que passou pela fila. */
function mostrarMovidos(d) {
  org.fase = 4;
  org.resultado = d;
  org.pedido = null;
  const falhas = d.falhas || [];
  desenharOrg(
    '<div class="cartao-cabeca"><span class="texto-cabeca"><b>' + plural(d.movidos, "arquivo") + " no lugar novo</b><small>" +
    (d.destino ? "Em " + esc(d.destino) + ". " : "") + "Nada foi apagado nem sobrescrito, e dá para voltar ao estado anterior.</small></span></div>" +
    '<div class="cartao-miolo">' +
    (falhas.length
      ? '<div class="aprovacao"><p><strong>' + plural(falhas.length, "arquivo") + " não deu para mover:</strong> " +
        esc(falhas.map((f) => f.nome || f.arquivo || f).join(", ")) + ". Eles ficaram onde estavam.</p></div>"
      : "") +
    '<div class="linha-form">' +
    (d.destino ? '<button class="com-icone" id="org-abrir-destino">' + ic("folder_open", 16) + "Abrir a pasta</button>" : "") +
    '<button class="com-icone" id="org-outra">' + ic("search", 16) + "Organizar outra pasta</button>" +
    '<span class="cresce"></span><button class="com-icone" id="org-desfazer">' + ic("undo", 16) + "Desfazer tudo</button></div>" +
    '<p class="nota-barra" id="org-nota3"></p></div>' +
    '<div class="tabela-rodape"><span>' + (falhas.length ? plural(falhas.length, "falha") : "Tudo movido") + '</span><span class="cresce"></span>' +
    "<span>Registrado no diário da organização</span></div>"
  );
  $("conversa-meta").textContent = plural(d.movidos, "arquivo") + " movidos";
  const abrir = $("org-abrir-destino");
  if (abrir) abrir.onclick = () => fetch("/api/biblioteca/abrir-pasta", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminho: d.destino }),
  });
  $("org-outra").onclick = () => { limparOrg(); passoOnde(); };
  $("org-desfazer").onclick = async () => {
    if (!(await confirmar({ titulo: "Devolver os " + plural(d.movidos, "arquivo") + "?", contexto: "Acervo › Organizar", texto: "Cada arquivo volta para a pasta onde estava antes desta organização.", confirmar: "Devolver" }))) return;
    $("org-desfazer").disabled = true;
    $("org-nota3").textContent = "devolvendo…";
    try {
      const rr = await fetch("/api/organizar/desfazer", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ diario: d.diario }),
      });
      const dd = await rr.json();
      $("org-nota3").textContent = plural(dd.revertidos, "arquivo") + " de volta ao lugar de origem";
    } catch (err) {
      $("org-desfazer").disabled = false;
      $("org-nota3").textContent = "não consegui desfazer: " + err;
    }
  };
  estado.contratos = 0;
  bib.todos = [];
  bib.sugestoes = null;
  carregarStatus();
}

/* Chamado pela fila de aprovacoes depois do sim num pedido de organizar:
   a pessoa volta para esta tela e ve o desfecho, em vez de parar na fila. */
async function organizarDesfecho() {
  let d;
  try { d = await (await fetch("/api/organizar/ultima")).json(); } catch (err) { return false; }
  if (!d || !d.diario) return false;
  marcarDestino("biblioteca");
  await organizarComecar(true);
  mostrarMovidos(d);
  atualizarPostura();
  return true;
}
