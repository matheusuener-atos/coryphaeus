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
   no painel, como as pastas ficam. Nada e apagado nem sobrescrito, e da para
   desfazer. Entrar na tela nao e comecar um trabalho: a conversa nasce quando
   a varredura comeca, que e quando existe trabalho.
*/

const org = {
  raizes: [], tipos: [], docs: [], selecao: new Set(), padroes: [], padrao: "", destino: "",
  fase: 0, plano: null, largo: false, encontrados: null, resultado: null, parado: false,
};

const ETAPAS_ORG = [
  "Escolher onde procurar",
  "Ler e classificar",
  "Conferir a classificação",
  "Mover para a estrutura nova",
];

function fitaOrg(feitos, total) {
  const metas = [
    org.raizes.length ? plural(org.raizes.length, "pasta") : "",
    org.fase === 1 && total ? (feitos || 0) + " de " + total : (org.docs.length ? plural(org.docs.length, "doc") : ""),
    org.fase === 2 ? "agora" : (org.fase > 2 ? plural(org.selecao.size, "marcado") : ""),
    org.fase === 3 ? "agora" : (org.fase > 3 ? "feito" : ""),
  ];
  // O anel so gira quando e a maquina que trabalha (ler, mover). Nas fases
  // em que a pessoa decide, o marcador e parcial, sem movimento.
  const agora = org.trabalhando ? coroa(18) : ic("radio_button_partial", 18);
  return '<div class="fita" id="org-fita">' + ETAPAS_ORG.map((t, i) => {
    const classe = i < org.fase ? "feita" : (i === org.fase ? "atual" : "");
    const icone = i < org.fase ? ic("check_circle", 18) : (i === org.fase ? agora : ic("radio_button_unchecked", 18));
    return (i ? '<span class="ic ic-16 seta">chevron_right</span>' : "") +
      '<div class="fase ' + classe + '">' + icone + '<span class="rotulo-fase">' + t + "</span>" +
      '<span class="meta-fase">' + esc(metas[i] || (i > org.fase ? "na fila" : "")) + "</span></div>";
  }).join("") + "</div>";
}

function ondeProcuro() {
  return '<div class="onde-procuro" id="org-onde"><span class="rotulo-suave">Onde eu procuro:</span>' +
    (org.raizes.length
      ? org.raizes.map((c, i) =>
          '<span class="chip-pasta">' + ic("folder", 16) + "<span>" + esc(c) + "</span>" +
          '<button data-tirar-raiz="' + i + '" title="tirar" aria-label="tirar">' + ic("close", 14) + "</button></span>").join("")
      : '<span class="nota-barra">nenhuma pasta escolhida ainda</span>') +
    (org.fase === 0 ? "" : '<button class="ac-incluir" data-outras="1">+ incluir pasta</button>') +
    '<span class="nota-direita">Não entro em pastas do sistema nem de programas</span></div>';
}

/* A tela inteira: fita, pastas escolhidas, o cartao da fase e o painel. */
function desenharOrg(cartao, painel) {
  $("centro").innerHTML =
    '<div class="acervo' + (org.largo ? " painel-largo" : "") + '"><div class="acervo-principal">' +
    fitaOrg() + ondeProcuro() + '<div class="tabela-cartao" id="org-cartao">' + cartao + "</div></div>" +
    '<aside class="acervo-painel"><button class="alca-painel" id="org-alca" title="Alargar ou recolher o painel" aria-label="Alargar ou recolher o painel">' +
    ic(org.largo ? "chevron_right" : "chevron_left", 18) + '</button><div class="rolagem" id="org-painel">' + painel + "</div></aside></div>";
  $("org-alca").onclick = () => {
    org.largo = !org.largo;
    $("centro").querySelector(".acervo").classList.toggle("painel-largo", org.largo);
    $("org-alca").innerHTML = ic(org.largo ? "chevron_right" : "chevron_left", 18);
  };
  ligarOnde();
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
      const v = $("org-varrer");
      if (v) v.disabled = !org.raizes.length;
    };
  });
  document.querySelectorAll("[data-outras]").forEach((b) => {
    b.onclick = () => { org.fase = 0; passoOnde(); };
  });
}

async function organizarComecar() {
  abrirTela("Organizar pastas", { cheia: true });
  bib.visao = "organizar";
  cabecalhoAcervo("organizar", '<button class="com-icone" id="org-de-novo">' + ic("search", 16) + "Procurar de novo</button>");
  $("org-de-novo").onclick = () => {
    org.fase = 0; org.docs = []; org.selecao = new Set(); org.plano = null; org.resultado = null; org.parado = false;
    passoOnde();
  };
  estado.trabalhoId = null;
  estado.trabalho = null;
  $("conversa-meta").textContent = "nada foi movido ainda";

  const o = await (await fetch("/api/organizar/opcoes")).json();
  org.raizes = [];      // nada pre-selecionado: a pessoa escolhe onde procurar
  org.tipos = o.tipos;
  org.padroes = o.padroes;
  org.padrao = (o.padroes[0] || {}).padrao || "";
  org.destino = o.destino_sugerido;
  org.diarios = o.diarios;
  org.fase = 0; org.docs = []; org.selecao = new Set(); org.plano = null; org.resultado = null; org.parado = false;

  passoOnde();
  atualizarPostura();
}

/* Fase 0: onde procurar. O navegador de pastas do proprio programa. */
function passoOnde() {
  org.fase = 0;
  desenharOrg(
    '<div class="cartao-cabeca"><span class="texto-cabeca"><b>Onde eu procuro</b>' +
    "<small>Navegue até a pasta e clique em Incluir esta pasta. Vou procurar nela e em tudo o que estiver dentro.</small></span>" +
    '<span class="direita"><span class="nota-barra" id="nav-atual"></span>' +
    '<button class="com-icone" id="nav-incluir" disabled>' + ic("add", 16) + "Incluir esta pasta</button></span></div>" +
    '<div class="cartao-miolo"><div class="navegador"><div class="migalhas" id="nav-migalhas"></div>' +
    '<div class="nav-lista" id="nav-lista"></div></div></div>' +
    '<div class="tabela-rodape"><span id="org-nota">nenhuma pasta escolhida ainda</span><span class="cresce"></span>' +
    '<button class="primario com-icone" id="org-varrer" disabled>' + ic("search", 16) + "Procurar documentos</button></div>",
    painelOrgPlano()
  );
  navegar("");
  $("nav-incluir").onclick = () => {
    if (!org.navegando) return;
    if (!org.raizes.some((r) => r.toLowerCase() === org.navegando.toLowerCase())) {
      org.raizes.push(org.navegando);
    }
    atualizarOnde();
    atualizarFita();
    $("org-varrer").disabled = false;
    $("org-nota").textContent = plural(org.raizes.length, "pasta") + " para procurar";
  };
  $("org-varrer").onclick = organizarVarrer;
  $("org-varrer").disabled = !org.raizes.length;
  if (org.raizes.length) $("org-nota").textContent = plural(org.raizes.length, "pasta") + " para procurar";
}

async function navegar(caminho) {
  const lista = $("nav-lista");
  lista.innerHTML = '<div class="nav-vazio">abrindo…</div>';

  let d;
  try {
    d = await (await fetch("/api/pastas?caminho=" + encodeURIComponent(caminho))).json();
  } catch (err) {
    lista.innerHTML = '<div class="nav-vazio">não consegui abrir: ' + esc(String(err)) + "</div>";
    return;
  }

  org.navegando = d.atual;
  $("nav-incluir").disabled = !d.atual;
  $("nav-atual").textContent = d.atual || "escolha uma pasta abaixo";

  let trilha = '<button data-ir="">Este computador</button>';
  for (const m of d.migalhas) {
    trilha += '<span class="sep">›</span><button data-ir="' + esc(m.caminho) + '">' + esc(m.nome) + "</button>";
  }
  $("nav-migalhas").innerHTML = trilha;
  $("nav-migalhas").querySelectorAll("button").forEach((b) => {
    b.onclick = () => navegar(b.dataset.ir);
  });

  let html = "";
  if (d.atalhos.length) {
    html += '<div class="nav-grupo">Começar por</div>' + d.atalhos.map((a) =>
      '<div class="nav-item" data-ir="' + esc(a.caminho) + '">' + ic("folder", 16) +
      "<span>" + esc(a.nome) + '</span><span class="cam">' + esc(a.caminho) + "</span></div>"
    ).join("");
  }
  if (d.unidades.length) {
    html += '<div class="nav-grupo">Unidades</div>' + d.unidades.map((u) =>
      '<div class="nav-item" data-ir="' + esc(u.caminho) + '">' + ic("desktop_windows", 16) +
      "<span>" + esc(u.nome) + "</span></div>"
    ).join("");
  }
  if (d.pai) {
    html += '<div class="nav-item" data-ir="' + esc(d.pai) + '">' + ic("subdirectory_arrow_right", 16) +
      "<span>.. voltar</span></div>";
  }
  html += d.pastas.map((p) =>
    '<div class="nav-item" data-ir="' + esc(p.caminho) + '">' + ic("folder", 16) +
    "<span>" + esc(p.nome) + "</span></div>"
  ).join("");

  if (d.erro) html += '<div class="nav-vazio">' + esc(d.erro) + "</div>";
  else if (!html) html = '<div class="nav-vazio">nenhuma subpasta aqui</div>';

  lista.innerHTML = html;
  lista.querySelectorAll(".nav-item").forEach((el) => {
    el.onclick = () => navegar(el.dataset.ir);
  });
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
    passoConfirmarLeitura(d);
  } catch (err) {
    $("org-nota").textContent = "não consegui procurar: " + err;
    $("org-varrer").disabled = false;
  }
}

/* Varrer e barato; ler custa ~20 s por documento. Encadear os dois sem
   perguntar foi o que fez o programa sair lendo o computador inteiro. */
function passoConfirmarLeitura(d) {
  org.fase = 1;
  let detalhe = plural(d.total, "documento") + " em " + plural(d.pastas_visitadas, "pasta");
  if (d.em_cache) detalhe += " · " + d.em_cache + (d.em_cache === 1 ? " já lido antes" : " já lidos antes");
  if (d.sem_permissao) detalhe += " · " + d.sem_permissao + " sem permissão de leitura";
  if (d.grandes) detalhe += " · " + d.grandes + " grandes demais";

  const tempo = d.novos === 0
    ? "Todos já foram lidos antes: sai na hora."
    : "Ler os " + plural(d.novos, "documento") + (d.novos === 1 ? " novo" : " novos") +
      " deve levar de <strong>" + formatarMinutos(d.minutos_min) + " a " + formatarMinutos(d.minutos_max) +
      "</strong>. Dá para parar no meio, e o que já foi lido fica guardado.";

  desenharOrg(
    '<div class="cartao-cabeca"><span class="texto-cabeca"><b>Encontrei ' + plural(d.total, "documento") + "</b><small>" +
    esc(detalhe) + "</small></span></div>" +
    '<div class="cartao-miolo"><p>' + tempo + "</p>" +
    '<div class="linha-form"><button class="primario com-icone" id="org-ler">' + ic("visibility", 16) + "Ler e classificar</button>" +
    '<button id="org-voltar">Escolher outras pastas</button></div><div id="org-andamento"></div></div>' +
    '<div class="tabela-rodape"><span>Nada foi lido ainda</span></div>',
    painelOrgPlano()
  );
  $("conversa-meta").textContent = plural(d.total, "documento") + " encontrados · nada foi movido ainda";
  $("org-ler").onclick = () => {
    $("org-ler").disabled = true;
    $("org-voltar").disabled = true;
    organizarClassificar(d.total);
  };
  $("org-voltar").onclick = () => { org.fase = 0; passoOnde(); };
}

function formatarMinutos(m) {
  if (m < 1) return "menos de 1 min";
  if (m < 60) return Math.round(m) + " min";
  return (m / 60).toFixed(1).replace(".", ",") + " h";
}

/* Fase 1: ler. Um acervo grande leva quase uma hora; desistir tem que estar
   a um clique, nao a um fechar-a-janela. */
async function organizarClassificar(total) {
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
    const r = await fetch("/api/organizar/classificar", { method: "POST" });
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
  desenharOrg(cartaoConferir(), painelOrgPlano());
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

/* O painel: estrutura, destino e o plano - como as pastas ficam. */
function painelOrgPlano() {
  const p = org.plano;
  const pronto = org.fase === 2 && p && p.total;
  return '<div class="painel-cabeca"><span class="titulo-painel"><h3>Como as pastas ficam</h3><span class="meta">' +
    (p ? "Plano · " + plural(p.total, "arquivo") + " em " + plural(p.pastas.length, "pasta") : "O plano aparece depois de ler e conferir") +
    "</span></span></div>" +
    '<div style="padding:0 18px 12px;display:grid;gap:12px">' +
    '<div class="campo-painel"><label for="org-padrao">Estrutura</label><select id="org-padrao">' +
    (org.padroes || []).map((x) => '<option value="' + esc(x.padrao) + '"' + (org.padrao === x.padrao ? " selected" : "") + ">" + esc(x.rotulo) + "</option>").join("") +
    "</select></div>" +
    '<div class="campo-painel"><label for="org-destino">Pasta de destino</label><div class="com-botao">' +
    '<input type="text" id="org-destino" value="' + esc(org.destino || "") + '">' +
    (window.pywebview ? '<button id="org-escolher">Trocar</button>' : "") + "</div></div></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Plano</span><span class="contagem">' +
    (p ? plural(p.pastas.length, "pasta") : "—") + "</span></div>" +
    (p
      ? "<div>" + p.pastas.map((x) =>
          '<div class="plano-linha">' + ic("folder", 16) + "<span>" + esc(x.pasta) + '</span><span class="contagem">' + x.arquivos + "</span></div>").join("") +
        (p.ignorados.length
          ? '<div class="plano-linha fora">' + ic("folder", 16) + '<span>Sem classificação · ficam onde estão</span><span class="contagem">' + p.ignorados.length + "</span></div>"
          : "") + "</div>"
      : "<p>Escolha as pastas, mande ler, confira a classificação. O plano se monta sozinho.</p>") + "</div>" +
    (pronto
      ? '<div class="cartao-pronto"><div class="cabeca">' + coroa(18) + "Pronto para mover</div>" +
        "<p>Vou mover " + plural(p.total, "arquivo") + " para " + plural(p.pastas.length, "pasta") + " dentro de " + esc(p.destino) +
        ". Nada é apagado nem sobrescrito, e dá para desfazer tudo depois.</p>" +
        '<div class="acoes"><button class="fantasma" id="org-revisar">Revisar o plano</button>' +
        '<button class="primario" id="org-aprovar">' + ic("drive_file_move", 16) + "Aprovar e mover</button></div></div>"
      : "") +
    (org.fase >= 2
      ? '<div class="painel-botoes"><button class="com-icone" id="org-recomecar">' + ic("restart_alt", 16) + "Começar de novo</button></div>"
      : "");
}

function ligarPainelOrg() {
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
  if (recomecar) recomecar.onclick = () => {
    org.fase = 0; org.docs = []; org.selecao = new Set(); org.plano = null; org.resultado = null; org.parado = false;
    passoOnde();
  };
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
   pedir estiver desligada. */
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
    org.resultado = d;

    if (d.aguardando_aprovacao) {
      cartao.innerHTML = '<div class="cartao-cabeca"><span class="texto-cabeca"><b>Pedido enviado para aprovação</b><small>Nada foi movido ainda. ' +
        plural(d.total, "arquivo") + " esperam o seu sim em Aprovações — a permissão de mover sem pedir está desligada.</small></span></div>" +
        '<div class="cartao-miolo"><div class="linha-form"><button class="primario" id="org-ver-fila">Abrir Aprovações</button></div></div>';
      $("org-ver-fila").onclick = () => { marcarDestino("aprovacoes"); mostrarAprovacoes(); };
      contarPendencias();
      atualizarPainelOrg();
      return;
    }

    org.fase = 4;
    atualizarFita();
    cartao.innerHTML = '<div class="cartao-cabeca"><span class="texto-cabeca"><b>' + plural(d.movidos, "arquivo") + " no lugar novo</b><small>" +
      (d.falhas.length
        ? d.falhas.length + " não deu para mover: " + esc(d.falhas.map((f) => f.nome).join(", "))
        : "Dá para voltar ao estado anterior.") + "</small></span></div>" +
      '<div class="cartao-miolo"><div class="linha-form"><button class="com-icone" id="org-desfazer">' + ic("undo", 16) + "Desfazer tudo</button>" +
      '<span class="nota-barra" id="org-nota3"></span></div></div>';
    $("conversa-meta").textContent = plural(d.movidos, "arquivo") + " movidos";
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
    atualizarPainelOrg();
  } catch (err) {
    cartao.innerHTML = '<div class="cartao-miolo"><div class="aprovacao"><p><strong>Não consegui mover.</strong> ' + esc(String(err)) + "</p></div></div>";
  } finally {
    org.trabalhando = false;
    atualizarSelo(false);
    atualizarFita();
    carregarTrabalhos();
  }
}

