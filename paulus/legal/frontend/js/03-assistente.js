/* ----------------------------------------------------------- anexar */

$("anexar").onclick = () => $("arquivos").click();
$("arquivos").onchange = (e) => {
  const lista = Array.from(e.target.files);
  e.target.value = "";
  if (lista.length) subirArquivos(lista);
};

const fluxo = $("fluxo");
["dragenter", "dragover"].forEach((ev) => fluxo.addEventListener(ev, (e) => {
  e.preventDefault();
  fluxo.classList.add("arrastando");
}));
["dragleave", "drop"].forEach((ev) => fluxo.addEventListener(ev, (e) => {
  e.preventDefault();
  if (ev === "dragleave" && fluxo.contains(e.relatedTarget)) return;
  fluxo.classList.remove("arrastando");
}));
fluxo.addEventListener("drop", (e) => {
  const lista = Array.from(e.dataTransfer.files || []);
  if (lista.length) subirArquivos(lista);
});

async function subirArquivos(lista) {
  const dados = new FormData();
  lista.forEach((a) => dados.append("arquivos", a));

  avisoNaJanela("Lendo " + plural(lista.length, "arquivo") + "…", { icone: "sync", girar: true, dura: 0 });

  try {
    const r = await fetch("/api/upload", { method: "POST", body: dados });
    const res = await r.json();

    let texto = res.salvos.length
      ? plural(res.salvos.length, "documento") +
        (res.salvos.length === 1 ? " aberto" : " abertos") + ". Agora são " + res.contratos + " no total."
      : "Nenhum documento novo foi aberto.";
    if (res.recusados.length) {
      texto += " Não consegui abrir: " +
        res.recusados.map((x) => x.nome + " (" + x.motivo + ")").join(", ") + ".";
    }
    avisoNaJanela(texto, res.recusados.length
      ? { tom: "erro", dura: 12000 }
      : { icone: res.salvos.length ? "task_alt" : "info" });
    estado.contratos = res.contratos;
    carregarStatus();
    await carregarAbertos();
    /* Anexar é dizer do que se quer falar. Sem isto, quem arrastava dois PDFs
       e perguntava sobre eles fazia o programa reler o acervo inteiro — 55 mil
       caracteres e um minuto — como se nada tivesse sido anexado. */
    if (res.salvos.length) definirEscopo(estado.escopo.concat(res.salvos));
  } catch (err) {
    avisoNaJanela("Não consegui abrir os arquivos: " + String(err), { tom: "erro", dura: 12000 });
  }
}

/* ------------------------------------------------------------ buscar */

/* BUSCAR sem nada escrito nao pode ser um clique que nao faz nada - era o
   que parecia quebrado. Vazio, ele liga o modo de busca: a pilula acende, o
   campo pede a palavra e ganha o foco, e Enter busca em vez de perguntar ao
   assistente. Clicar de novo ou Esc desliga. */
function modoDeBusca(ligar) {
  const campo = $("pedido");
  estado.modoBusca = Boolean(ligar);
  $("buscar").classList.toggle("ativa", estado.modoBusca);
  if (estado.modoBusca) {
    if (!campo.dataset.placeholderAntes) campo.dataset.placeholderAntes = campo.placeholder;
    campo.placeholder = "Qual palavra procurar nos documentos?";
    campo.focus();
  } else if (campo.dataset.placeholderAntes) {
    campo.placeholder = campo.dataset.placeholderAntes;
    delete campo.dataset.placeholderAntes;
  }
}

$("buscar").onclick = async () => {
  const termo = $("pedido").value.trim();
  if (estado.ocupado) return;
  if (!termo) { modoDeBusca(!estado.modoBusca); return; }
  modoDeBusca(false);
  $("pedido").value = "";
  $("pedido").style.height = "auto";

  const centro = $("centro");
  if (!estado.trabalhoId) centro.innerHTML = "";
  centro.insertAdjacentHTML("beforeend", bolhaPessoa(termo));
  atualizarPostura();

  const bloco = document.createElement("div");
  bloco.className = "resposta";
  centro.appendChild(bloco);
  rolar();

  try {
    const r = await fetch("/api/buscar-agora", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ termo: termo }),
    });
    const d = await r.json();

    if (!d.resultados.length) {
      bloco.innerHTML = "<div>Não achei “" + esc(termo) + "” nos " + plural(d.documentos, "documento") + " abertos.</div>";
    } else {
      const nomes = new Set(d.resultados.map((x) => x.documento));
      bloco.innerHTML = "<div>" + plural(d.resultados.length, "trecho") + " com “" + esc(termo) + "” em " + plural(nomes.size, "documento") + ", sem passar pelo assistente.</div>" +
        d.resultados.map((x) =>
          '<div class="trecho"><div class="origem">' + esc(x.documento) + " · trecho " + x.trecho +
          "</div><pre>" + esc(x.texto) + "</pre></div>"
        ).join("");
    }
  } catch (err) {
    bloco.innerHTML = "<div>Não consegui buscar: " + esc(String(err)) + "</div>";
  }
  rolar();
};

/* ------------------------------------------------------------ desenho */

function desenharTrabalho() {
  const t = estado.trabalho;
  $("conversa-titulo").textContent = t.titulo;
  atualizarBotaoEnviar();
  entrarNaConversa();

  let html = "";
  let pergunta = "";
  let fontes = [], perguntaDasFontes = "";
  for (const m of t.mensagens) {
    if (m.autor === "pessoa") {
      pergunta = m.texto;
      html += bolhaPessoa(m.texto);
    } else {
      html += blocoResposta(m, pergunta);
      if (m.fontes && m.fontes.length) { fontes = m.fontes; perguntaDasFontes = pergunta; }
    }
  }
  if (t.etapas.length && t.estado !== "concluido") html += cartaoPlano(t.etapas, t.etapa_atual);
  if (t.aprovacao) html += cartaoAprovacao(t.aprovacao);

  $("centro").innerHTML = html || exemplos();
  ligarExemplos();
  ligarResposta($("centro"));
  ligarAprovacaoNaConversa($("centro"));
  desenharProgresso(t.etapas || []);
  desenharTrechos(fontes, perguntaDasFontes, null);
  desenharAtividade(t.atividade);
  atualizarPostura();
  rolar();
}

function bolhaPessoa(texto) {
  return '<div class="bolha-pessoa">' + esc(texto) + "</div>";
}

function blocoResposta(m, pergunta) {
  let html = '<div class="resposta">';
  if (m.cobertura && m.cobertura.ignorados && m.cobertura.ignorados.length) {
    html += avisoCobertura(m.cobertura);
  }
  if (m.interrompida) html += etiquetaDeParada();
  if (m.inferencia) html += etiquetaDeLeitura();
  html += '<div class="texto">' + esc(m.texto) + "</div>";
  if (m.fontes && m.fontes.length) html += blocoFontes(m.fontes, m.cobertura);
  const citados = m.fontes && m.fontes.length ? new Set(m.fontes.map((f) => f.documento)).size : 0;
  if (m.segundos) html += linhaAssinatura(m.segundos, citados, pergunta || "");
  return html + "</div>";
}

/* O que veio do resumo guardado nao e trecho de documento: e conclusao do
   assistente sobre ele. A resposta tem de dizer isso antes de ser lida - uma
   frase que parece citacao e nao e vale menos que nada. */
/* A resposta que a pessoa parou no meio: o texto e o que o modelo tinha
   escrito ate ali, e quem le precisa saber que nao e a resposta inteira. */
function etiquetaDeParada() {
  return '<div class="etiqueta-inferencia">' + ic("pause", 14) + "resposta parada no meio</div>";
}

function etiquetaDeLeitura() {
  return '<div class="etiqueta-inferencia">' + ic("auto_awesome", 14) +
    "leitura do assistente, não trecho do documento</div>";
}

function avisoCobertura(c) {
  return '<div class="aviso-cobertura"><strong>Li ' + c.consultados.length + " de " +
    c.total_contratos + " documentos.</strong> Sem trecho sobre isso em: " +
    esc(c.ignorados.join(", ")) + ". A resposta não fala por esses.</div>";
}

/* No desenho os trechos moram no painel da direita. Na resposta fica so a
   conta, que abre o painel, e a caixa onde o visor do PDF se desenha. */
function blocoFontes(fontes, cobertura) {
  const quantos = cobertura && cobertura.consultados ? cobertura.consultados.length : 1;
  return '<div class="fontes"><button data-ver-trechos="1">' + ic("format_quote", 16) +
    plural(fontes.length, "trecho") + " de " + plural(quantos, "documento") + " — ver no painel</button></div>" +
    '<div class="visor-caixa"></div>';
}

/* A linha que fecha a resposta, como no desenho: modelo, tempo, quantos
   arquivos foram citados, e Copiar / Refazer. */
function linhaAssinatura(segundos, citados, pergunta) {
  return '<div class="assinatura"><span>' + esc(estado.modelo || "assistente local") + " · " +
    esc(String(segundos)) + " s" +
    (citados ? " · " + plural(citados, "arquivo citado", "arquivos citados") : "") + "</span>" +
    '<button data-copiar="1">' + ic("content_copy", 16) + "<span>Copiar</span></button>" +
    (pergunta ? '<button data-refazer="' + esc(pergunta) + '">' + ic("refresh", 16) + "<span>Refazer</span></button>" : "") +
    "</div>";
}

function ligarResposta(caixa) {
  caixa.querySelectorAll("[data-copiar]").forEach((b) => {
    b.onclick = () => {
      const texto = b.closest(".resposta").querySelector(".texto");
      if (!texto || !navigator.clipboard) return;
      navigator.clipboard.writeText(texto.textContent).then(() => {
        b.lastElementChild.textContent = "Copiado";
        setTimeout(() => { b.lastElementChild.textContent = "Copiar"; }, 1800);
      });
    };
  });
  caixa.querySelectorAll("[data-refazer]").forEach((b) => {
    b.onclick = () => { $("pedido").value = b.dataset.refazer; enviar(); };
  });
  caixa.querySelectorAll("[data-ver-trechos]").forEach((b) => {
    b.onclick = () => {
      try { localStorage.setItem("paulus.lateral", "1"); } catch (err) { /* sem memoria */ }
      mostrarLateral(true);
      alternarRamo($("lat-trechos-cabeca"), true);
      $("lat-trechos").scrollIntoView({ behavior: "smooth", block: "start" });
    };
  });
}

/* Os trechos citados, no painel da direita, numerados. Clicar num trecho
   marca-o; "ver no documento" abre a pagina do PDF na conversa, com o trecho
   destacado - e o visor de sempre, so mudou de onde e chamado. */
function desenharTrechos(fontes, pergunta, ondeVisor) {
  const bloco = $("lat-trechos");
  const lista = $("lat-trechos-lista");
  if (!fontes || !fontes.length) { bloco.hidden = true; lista.innerHTML = ""; return; }

  bloco.hidden = false;
  $("lat-trechos-conta").textContent = fontes.length;
  /* Um por vez aberto: o painel tem 316 px e seis trechos abertos ao mesmo
     tempo empurrariam Propriedades para fora da tela. O primeiro ja vem
     aberto porque e o mais citado. */
  /* Arvore: documento > trecho > texto, na ordem em que foram citados. Uma
     leitura nova chega sempre compacta. A numeracao continua a da citacao,
     que e a que a resposta usa. */
  const porDocumento = new Map();
  fontes.forEach((f, i) => {
    if (!porDocumento.has(f.documento)) porDocumento.set(f.documento, []);
    porDocumento.get(f.documento).push(i);
  });
  const seta = '<span class="ic ic-16 arv-seta">chevron_right</span>';
  lista.innerHTML = [...porDocumento].map(([documento, indices]) =>
    '<div class="arv-ramo">' +
    '<button class="arv-no arv-doc" aria-expanded="false">' + seta + "<b>" + esc(documento) + "</b>" +
    "<small>" + plural(indices.length, "trecho") + "</small></button>" +
    '<div class="arv-filhos" hidden>' + indices.map((i) => {
      const f = fontes[i];
      return '<div class="arv-ramo">' +
        '<button class="arv-no arv-trecho" aria-expanded="false">' + seta + '<span class="cit">' + (i + 1) + "</span>" +
        '<span class="onde">' + esc(f.onde || ("trecho " + f.trecho)) + "</span></button>" +
        '<div class="arv-filhos arv-folha" hidden><div class="trecho-texto">' + esc(f.texto) + "</div>" +
        '<button class="trecho-ver" data-ver-cit="' + i + '">ver no documento</button></div></div>';
    }).join("") + "</div></div>").join("");
  lista.hidden = true;
  $("lat-trechos-cabeca").setAttribute("aria-expanded", "false");
  lista.querySelectorAll(".arv-no").forEach((no) => { no.onclick = () => alternarRamo(no); });
  const caixa = ondeVisor || Array.from($("centro").querySelectorAll(".visor-caixa")).pop();
  lista.querySelectorAll("[data-ver-cit]").forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();
      const f = fontes[Number(b.dataset.verCit)];
      if (!f || !caixa) return;
      abrirCitacao(f.documento, f.texto, pergunta, caixa);
      caixa.scrollIntoView({ behavior: "smooth", block: "nearest" });
    };
  });
}

/* Abre ou fecha um ramo da arvore (o botao e o que vem logo depois dele).
   Fechar leva junto tudo o que estava aberto abaixo: reabrir mostra o ramo
   compacto de novo, e nao a arvore inteira do jeito que ficou. */
function alternarRamo(no, abrir) {
  const filhos = no.nextElementSibling;
  if (!filhos) return;
  const vai = abrir === undefined ? filhos.hidden : abrir;
  if (vai === !filhos.hidden) return;
  no.setAttribute("aria-expanded", String(vai));
  if (!vai) {
    filhos.querySelectorAll('.arv-no[aria-expanded="true"]').forEach((n) => {
      n.setAttribute("aria-expanded", "false");
      n.nextElementSibling.hidden = true;
    });
  }
  abrirComoGaveta(filhos, vai);
}

/* A gaveta de sempre: cresce ate a altura dela enquanto aparece (curva expo)
   e encolhe mais rapido ao fechar. A mesma da lista de conversas. */
function abrirComoGaveta(el, abrir) {
  if (el.gaveta) { el.gaveta.cancel(); el.gaveta = null; el.style.overflow = ""; }
  if (!animacoesLigadas()) { el.hidden = !abrir; return; }
  el.style.overflow = "hidden";
  if (abrir) {
    el.hidden = false;
    el.gaveta = el.animate([{ height: "0px", opacity: 0 }, { height: el.scrollHeight + "px", opacity: 1 }],
      { duration: 360, easing: CURVA_ENTRA });
    el.gaveta.onfinish = () => { el.gaveta = null; el.style.overflow = ""; };
  } else {
    el.gaveta = el.animate([{ height: el.offsetHeight + "px", opacity: 1 }, { height: "0px", opacity: 0 }],
      { duration: 240, easing: "cubic-bezier(.55,0,.45,1)" });
    el.gaveta.onfinish = () => { el.gaveta = null; el.hidden = true; el.style.overflow = ""; };
  }
}

$("lat-trechos-cabeca").onclick = () => alternarRamo($("lat-trechos-cabeca"));

/* O progresso do plano, no painel: etapa feita fica riscada. */
function desenharProgresso(etapas) {
  const bloco = $("lat-progresso");
  if (!etapas || !etapas.length) { bloco.hidden = true; return; }
  bloco.hidden = false;
  const feitas = etapas.filter((e) => e.estado === "concluido").length;
  $("lat-progresso-conta").textContent = feitas + " de " + etapas.length;
  const icone = { concluido: "check_circle", executando: "radio_button_partial", na_fila: "radio_button_unchecked", falhou: "error", pausado: "pause" };
  const classe = { concluido: "feita", executando: "andando", na_fila: "fila", falhou: "falhou", pausado: "fila" };
  $("lat-etapas").innerHTML = etapas.map((e) =>
    '<div class="lat-etapa ' + (classe[e.estado] || "fila") + '">' +
    ic(icone[e.estado] || "radio_button_unchecked", 18) +
    "<span>" + esc(e.titulo) + (e.total ? " · " + e.feitos + " / " + e.total : "") + "</span></div>").join("");
}

function cartaoPlano(etapas, atual) {
  const total = etapas.length;
  const rodando = estado.ocupado;
  return '<div class="cartao"><div class="cartao-topo">' +
    (rodando ? coroa(20) : '<span class="ic ic-20 marcador">pause</span>') +
    '<span class="quem">' + (rodando ? "Trabalhando" : "Parado") + " · etapa " + atual + " de " + total + "</span>" +
    '<span class="tempo" id="cronometro"></span></div><div class="cartao-corpo">' +
    etapas.map(linhaEtapa).join("") + "</div></div>";
}

function linhaEtapa(e) {
  const rotulos = { concluido: "concluído", executando: "", na_fila: "na fila", falhou: "não deu", pausado: "parada" };
  const icone = { concluido: "check_circle", executando: "radio_button_partial", na_fila: "radio_button_unchecked", falhou: "error", pausado: "pause" };
  const direita = e.total
    ? '<span class="estado">' + e.feitos + " / " + e.total + "</span>"
    : '<span class="estado">' + (rotulos[e.estado] || "") + "</span>";
  const barra = e.estado === "executando" && e.total
    ? '<div class="progresso"><i style="width:' + Math.round((e.feitos / e.total) * 100) + '%"></i></div>'
    : "";
  return '<div class="etapa ' + e.estado + '"><span class="ic ic-18 marcador">' +
    (icone[e.estado] || "radio_button_unchecked") + "</span>" +
    '<span class="texto">' + esc(e.titulo) + (e.detalhe ? " · " + esc(e.detalhe) : "") + "</span>" +
    direita + "</div>" + barra;
}

function cartaoAprovacao(a) {
  return '<div class="aprovacao"><div class="cabeca"><i class="ponto-acc"></i><span class="nome">Esperando você</span></div>' +
    "<p>" + esc(a.pergunta) + "</p>" +
    (a.detalhe ? '<p class="detalhe">' + esc(a.detalhe) + "</p>" : "") +
    '<div class="acoes"><button class="fantasma aprovar-secundario">Revisar</button>' +
    '<button class="primario">Aprovar</button></div></div>';
}

/* Aprovar e decidir na fila: os dois botoes levam para la. */
function ligarAprovacaoNaConversa(caixa) {
  caixa.querySelectorAll(".aprovacao button").forEach((b) => {
    b.onclick = () => { marcarDestino("aprovacoes"); mostrarAprovacoes(); };
  });
}

function desenharAtividade(itens) {
  const caixa = $("registro");
  if (!itens || !itens.length) {
    caixa.hidden = true;
    return;
  }

  caixa.hidden = false;
  $("registro-agora").textContent = itens[0].texto;
  $("atividade").innerHTML = itens.slice(0, 6).map((a) =>
    '<div class="atividade-linha"><span class="txt">' + esc(a.texto) +
    '<span class="num">' + quando(a.em) + "</span></span></div>"
  ).join("");
}

$("registro-cabeca").onclick = () => {
  const aberto = $("registro").classList.toggle("aberto");
  $("atividade").hidden = !aberto;
};

function quando(iso) {
  const seg = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (seg < 5) return "agora";
  if (seg < 60) return "há " + seg + " s";
  if (seg < 3600) return "há " + Math.floor(seg / 60) + " min";
  return "há " + Math.floor(seg / 3600) + " h";
}

function rolar() {
  $("fluxo").scrollTop = $("fluxo").scrollHeight;
  atualizarIrAoFim();
}

/* A pessoa subiu para reler: a resposta que esta chegando nao a arrasta de
   volta para baixo, e o botao de ir ao fim aparece. Perto do fim (120 px) e
   o mesmo que estar no fim - uma linha nova nao conta como ter subido. */
const FOLGA_DO_FIM = 120;

function pertoDoFim() {
  const f = $("fluxo");
  return f.scrollHeight - f.scrollTop - f.clientHeight < FOLGA_DO_FIM;
}

function atualizarIrAoFim() {
  const longe = !$("conversa-col").classList.contains("vazia") && !pertoDoFim();
  $("ir-ao-fim").classList.toggle("visivel", longe);
}

$("fluxo").addEventListener("scroll", atualizarIrAoFim, { passive: true });
$("ir-ao-fim").onclick = () => {
  const f = $("fluxo");
  f.scrollTo({ top: f.scrollHeight, behavior: animacoesLigadas() ? "smooth" : "auto" });
};

/* ------------------------------------------------------------ ditar */
/*
   O microfone da caixa de pedido. Usa o modelo de voz que ja mora nesta
   maquina (o mesmo das Gravacoes): o audio vai em pedacos de 2 s para uma
   sessao ao vivo no servidor local, que devolve o texto a cada pausa na
   fala. Nada sai do computador - foi a escolha entre isto e o ditado do
   Windows, que em portugues manda o audio para a Microsoft. A captura e a
   conversao do audio sao as das Gravacoes (11-gravacoes.js).

   O que e ditado junta NO CARTAO DO DITADO, e so vai para o campo quando a
   pessoa manda ("Usar no chat", clicar de novo no microfone ou enviar). O
   cartao mostra a voz chegando num equalizador, o tempo e o texto. Estados:

     ouvindo     microfone aberto
     pausado     microfone aberto, mas nada e ouvido
     pendente    a pessoa saiu do Assistente: o microfone fechou, o texto e
                 a sessao ficam, e o cartao oferece continuar, usar ou
                 descartar
     finalizando transcrevendo o que sobrou antes de ir para o campo
*/
const ditado = {
  estado: "", sessao: "", texto: "", fluxo: null, captura: null, amostras: [],
  relogio: 0, enviando: false, recebidos: 0, inicio: 0, acumulado: 0, quadro: 0,
};

const dsAberto = () => ditado.estado === "ouvindo" || ditado.estado === "pausado";

/* O tempo que o microfone ficou ouvindo, sem contar pausas nem o pendente. */
function tempoDoDitado() {
  const ms = ditado.acumulado + (ditado.estado === "ouvindo" ? performance.now() - ditado.inicio : 0);
  const s = Math.floor(ms / 1000);
  return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
}

function marcarTempo(parando) {
  if (ditado.estado === "ouvindo" && parando) ditado.acumulado += performance.now() - ditado.inicio;
  if (!parando) ditado.inicio = performance.now();
}

function previaDoDitado() {
  const t = ditado.texto.trim();
  if (!t) return '<span class="vazio">o texto aparece aqui a cada pausa na fala</span>';
  return esc(t.length > 240 ? "…" + t.slice(-240) : t);
}

function juntarAoDitado(trechos) {
  const novos = (trechos || []).map((x) => (x.texto || "").trim()).filter(Boolean);
  if (!novos.length) return;
  ditado.texto = (ditado.texto.trim() ? ditado.texto.trim() + " " : "") + novos.join(" ");
  document.querySelectorAll("[data-ditado-texto]").forEach((p) => { p.innerHTML = previaDoDitado(); });
}

/* O CARTAO DO DITADO. So o aviso la embaixo nao bastava para saber se o
   microfone estava ouvindo. No inicio ele e o primeiro cartao de
   "Acontecendo agora"; numa conversa, onde essa secao nao existe, fica logo
   acima da caixa de pedido. */
function cartaoDoDitado() {
  const e = ditado.estado;
  if (!e) return "";
  const nomes = { ouvindo: "Ditando", pausado: "Ditado em pausa", pendente: "Ditado pendente", finalizando: "Transcrevendo o que sobrou…" };
  const notas = {
    ouvindo: "modelo de voz desta máquina · nada sai do computador",
    pausado: "o microfone não ouve nada até continuar",
    pendente: "o microfone fechou quando você saiu do Assistente",
    finalizando: "o texto vai para o campo em alguns segundos",
  };
  const botao = (dado, icone, rotulo, classe) => '<button class="' + (classe || "fantasma") + '" ' + dado + '="1">' + ic(icone, 16) + rotulo + "</button>";
  let acoes = "";
  if (e === "ouvindo" || e === "pausado") {
    acoes = botao("data-ditado-cancelar", "close", "Cancelar") +
      botao("data-ditado-pausar", e === "pausado" ? "play_arrow" : "pause", e === "pausado" ? "Continuar" : "Pausar") +
      botao("data-ditado-usar", "arrow_upward", "Usar no chat", "primario");
  } else if (e === "pendente") {
    acoes = botao("data-ditado-cancelar", "delete", "Descartar") +
      botao("data-ditado-continuar", "mic", "Continuar gravação") +
      botao("data-ditado-usar", "arrow_upward", "Usar no chat", "primario");
  }
  const classe = "cartao-agora ditado-cartao " + e;
  return '<div class="' + classe + '">' +
    '<div class="cabeca">' + (e === "finalizando" ? coroa(20) : ic(e === "pendente" ? "pause" : "mic", 20)) +
    '<span class="nome">' + nomes[e] + "</span>" +
    '<span class="ditado-tempo" data-ditado-tempo="1">' + tempoDoDitado() + "</span></div>" +
    (dsAberto() ? '<canvas class="ditado-onda" data-ditado-onda="1"></canvas>' : "") +
    '<p class="ditado-texto" data-ditado-texto="1">' + previaDoDitado() + "</p>" +
    '<div class="rodape">' + notas[e] + "</div>" +
    (acoes ? '<div class="acoes">' + acoes + "</div>" : "") + "</div>";
}

function ligarCartaoDoDitado() {
  const ligar = (dado, fazer) => document.querySelectorAll("[" + dado + "]").forEach((b) => { b.onclick = (ev) => { ev.stopPropagation(); fazer(); }; });
  ligar("data-ditado-cancelar", () => cancelarDitado());
  ligar("data-ditado-pausar", () => pausarDitado(ditado.estado === "ouvindo"));
  ligar("data-ditado-continuar", () => continuarDitado());
  ligar("data-ditado-usar", () => usarDitadoNoChat());
  document.querySelectorAll("[data-ditado-onda]").forEach((cv) => desenharOnda(cv, null));
}

function desenharCartaoDoDitado() {
  const html = cartaoDoDitado();
  const noInicio = $("conversa-col").classList.contains("vazia");
  const lista = $("agora-cartoes");
  lista.querySelectorAll(".ditado-cartao").forEach((c) => c.remove());
  if (noInicio) {
    if (html) lista.insertAdjacentHTML("afterbegin", html);
    $("agora").hidden = !lista.children.length;
  }
  const rodape = $("ditado-rodape");
  rodape.hidden = !html || noInicio;
  rodape.querySelector(".centro").innerHTML = html && !noInicio ? html : "";
  $("ditar").classList.toggle("ouvindo", dsAberto());
  $("ditar").title = dsAberto() ? "Usar o ditado no chat" : (ditado.estado === "pendente" ? "Continuar o ditado" : "Ditar — o modelo de voz desta máquina escreve no campo");
  ligarCartaoDoDitado();
}

/* O equalizador: barras finas, espelhadas a partir do centro - os graves da
   voz no meio, os agudos nas pontas -, como uma onda. Le o analisador do
   proprio contexto de audio da captura; em pausa, as barras deitam. */
function desenharOnda(cv, dados) {
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth;
  const h = cv.clientHeight;
  if (!w || !h) return;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
  }
  const g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  g.fillStyle = getComputedStyle(cv).color;
  const barra = 3;
  const passo = 6;
  const n = Math.max(1, Math.floor(w / passo));
  const sobra = (w - n * passo + (passo - barra)) / 2;
  const util = dados ? Math.max(1, Math.floor(dados.length * 0.5)) : 1;
  for (let i = 0; i < n; i++) {
    const pos = n > 1 ? Math.abs(i - (n - 1) / 2) / ((n - 1) / 2) : 0;
    const valor = dados && ditado.estado === "ouvindo" ? dados[Math.floor(pos * (util - 1))] / 255 : 0;
    const alt = Math.max(2, valor * h * (1 - pos * 0.4));
    g.fillRect(sobra + i * passo, (h - alt) / 2, barra, alt);
  }
}

function animarDitado() {
  const captura = ditado.captura;
  if (!dsAberto() || !captura) { ditado.quadro = 0; return; }
  const dados = new Uint8Array(captura.analisador.frequencyBinCount);
  captura.analisador.getByteFrequencyData(dados);
  document.querySelectorAll("[data-ditado-onda]").forEach((cv) => desenharOnda(cv, dados));
  document.querySelectorAll("[data-ditado-tempo]").forEach((t) => { t.textContent = tempoDoDitado(); });
  ditado.quadro = requestAnimationFrame(animarDitado);
}

async function novaSessaoDeDitado() {
  const r = await fetch("/api/voz/ao-vivo", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).catch(() => null);
  if (!r || !r.ok) {
    avisoCert("não consegui abrir o ditado" + (r ? ": " + (await erroDe(r)) : ""), { tom: "erro" });
    return "";
  }
  ditado.recebidos = 0;
  return (await r.json()).sessao;
}

/* Abre o microfone e a captura. Falhou, nao muda o estado do ditado. */
async function abrirCapturaDoDitado() {
  let fluxo;
  try {
    fluxo = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    avisoCert("não consegui usar o microfone: " + (err && err.message ? err.message : err), { tom: "erro" });
    return false;
  }
  try {
    let ctx;
    try { ctx = new AudioContext({ sampleRate: 16000 }); } catch (err) { ctx = new AudioContext(); }
    const fonte = ctx.createMediaStreamSource(fluxo);
    await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([GV_CAPTADOR], { type: "application/javascript" })));
    const no = new AudioWorkletNode(ctx, "paulus-captador");
    no.port.onmessage = (e) => { if (ditado.estado === "ouvindo") ditado.amostras.push(e.data); };
    fonte.connect(no);
    no.connect(ctx.destination);
    const analisador = ctx.createAnalyser();
    analisador.fftSize = 128;
    analisador.smoothingTimeConstant = 0.72;
    fonte.connect(analisador);
    ditado.fluxo = fluxo;
    ditado.captura = { ctx: ctx, no: no, fonte: fonte, analisador: analisador };
  } catch (err) {
    fluxo.getTracks().forEach((t) => t.stop());
    avisoCert("esta janela não deixou capturar o áudio (" + (err && err.message ? err.message : err) + ")", { tom: "erro" });
    return false;
  }
  clearInterval(ditado.relogio);
  ditado.relogio = setInterval(enviarPedacoDoDitado, 2000);
  return true;
}

function fecharCapturaDoDitado() {
  clearInterval(ditado.relogio);
  cancelAnimationFrame(ditado.quadro);
  if (ditado.captura) {
    try { ditado.captura.no.disconnect(); ditado.captura.fonte.disconnect(); ditado.captura.ctx.close(); } catch (err) { /* ja fechado */ }
    ditado.captura = null;
  }
  if (ditado.fluxo) { ditado.fluxo.getTracks().forEach((t) => t.stop()); ditado.fluxo = null; }
}

function ouvir() {
  ditado.estado = "ouvindo";
  marcarTempo(false);
  desenharCartaoDoDitado();
  cancelAnimationFrame(ditado.quadro);
  ditado.quadro = requestAnimationFrame(animarDitado);
}

async function comecarDitado() {
  let voz = null;
  try { voz = await (await fetch("/api/voz")).json(); } catch (err) { voz = null; }
  if (!voz || !voz.disponivel) {
    avisoCert("ditar precisa do modelo de voz desta máquina — baixe em Configurações › Assistente", {
      tom: "erro", acao: { rotulo: "Abrir", fazer: () => { cfg.secao = "assistente"; abrirDestino("config"); } },
    });
    return;
  }
  const sessao = await novaSessaoDeDitado();
  if (!sessao) return;
  if (!(await abrirCapturaDoDitado())) { fetch("/api/voz/ao-vivo/" + sessao, { method: "DELETE" }).catch(() => {}); return; }
  ditado.sessao = sessao;
  ditado.texto = "";
  ditado.amostras = [];
  ditado.acumulado = 0;
  ouvir();
}

function pausarDitado(pausar) {
  if (!dsAberto()) return;
  if (pausar) {
    marcarTempo(true);
    ditado.estado = "pausado";
    enviarPedacoDoDitado();   // o que foi ouvido antes da pausa vai logo
    desenharCartaoDoDitado();
  } else {
    ouvir();
  }
}

/* Voltar do pendente: o microfone abre de novo na mesma sessao. */
async function continuarDitado() {
  if (ditado.estado !== "pendente") return;
  if (!(await abrirCapturaDoDitado())) return;
  ouvir();
}

/* SAIR DO ASSISTENTE com o microfone aberto: ele fecha - ninguem quer o
   microfone ouvindo enquanto mexe no Financeiro -, mas o que foi ditado e a
   sessao ficam, e o cartao espera a pessoa voltar. */
function deixarDitadoPendente() {
  if (!dsAberto()) return;
  marcarTempo(true);
  fecharCapturaDoDitado();
  ditado.estado = "pendente";
  enviarPedacoDoDitado();
  desenharCartaoDoDitado();
}

async function enviarPedacoDoDitado() {
  if (!ditado.sessao || ditado.enviando || !ditado.amostras.length) return;
  const sessao = ditado.sessao;
  const partes = ditado.amostras;
  ditado.amostras = [];
  const junto = new Float32Array(partes.reduce((n, p) => n + p.length, 0));
  let i = 0;
  partes.forEach((p) => { junto.set(p, i); i += p.length; });
  const taxa = ditado.captura ? ditado.captura.ctx.sampleRate : 16000;
  ditado.enviando = true;
  try {
    const r = await fetch("/api/voz/ao-vivo/" + sessao + "/audio", {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: pcm16De(reamostrarGv(junto, taxa, 16000)),
    });
    if (ditado.sessao !== sessao) return;   // descartado enquanto transcrevia
    if (r.status === 404) {
      // O servidor descarta sessao parada ha 15 min (pendente esquecido):
      // abre outra e o pedaco tenta de novo. O texto do cartao nao se perde.
      ditado.sessao = await novaSessaoDeDitado();
      ditado.amostras = partes.concat(ditado.amostras);
      return;
    }
    if (!r.ok) { avisoCert("o ditado parou: " + (await erroDe(r)), { tom: "erro" }); deixarDitadoPendente(); return; }
    const d = await r.json();
    if (d.trechos && d.trechos.length) {
      ditado.recebidos += d.trechos.length;
      juntarAoDitado(d.trechos);
    }
  } catch (err) {
    if (ditado.sessao === sessao) ditado.amostras = partes.concat(ditado.amostras);
  } finally {
    ditado.enviando = false;
  }
}

function zerarDitado() {
  ditado.estado = "";
  ditado.sessao = "";
  ditado.texto = "";
  ditado.amostras = [];
  ditado.acumulado = 0;
  desenharCartaoDoDitado();
}

/* Cancelar (ou Descartar, no pendente): o microfone fecha, a sessao e
   descartada sem transcrever o resto, e o texto ditado vai embora. O campo
   nao muda - o ditado nunca chegou nele. */
function cancelarDitado() {
  if (!ditado.estado) return;
  const sessao = ditado.sessao;
  fecharCapturaDoDitado();
  if (sessao) fetch("/api/voz/ao-vivo/" + sessao, { method: "DELETE" }).catch(() => {});
  zerarDitado();
  $("pedido").focus();
}

/* Usar no chat: o que ficou sem pausa ainda e transcrito, o texto todo entra
   no campo (depois do que ja estava escrito) e a sessao e descartada - a
   fila de transcricao das Gravacoes espera enquanto ha sessao aberta. */
async function usarDitadoNoChat() {
  if (!ditado.estado || ditado.estado === "finalizando") return;
  if (dsAberto()) marcarTempo(true);
  fecharCapturaDoDitado();
  ditado.estado = "finalizando";
  desenharCartaoDoDitado();
  while (ditado.enviando) await new Promise((fimEspera) => setTimeout(fimEspera, 100));
  if (ditado.amostras.length) await enviarPedacoDoDitado();
  const sessao = ditado.sessao;
  if (sessao) {
    try {
      const r = await fetch("/api/voz/ao-vivo/" + sessao + "/fim", { method: "POST" });
      if (r.ok) juntarAoDitado(((await r.json()).trechos || []).slice(ditado.recebidos));
    } catch (err) { /* o que ja foi transcrito continua valendo */ }
    fetch("/api/voz/ao-vivo/" + sessao, { method: "DELETE" }).catch(() => {});
  }
  const texto = ditado.texto.trim();
  if (texto) {
    const campo = $("pedido");
    campo.value = (campo.value.trim() ? campo.value.replace(/\s+$/, "") + " " : "") + texto;
    campo.style.height = "auto";
    campo.style.height = Math.min(campo.scrollHeight, 150) + "px";
  } else {
    avisoCert("não ouvi nada para escrever");
  }
  zerarDitado();
  $("pedido").focus();
}

$("ditar").onclick = () => {
  if (dsAberto()) return usarDitadoNoChat();
  if (ditado.estado === "pendente") return continuarDitado();
  if (!ditado.estado) return comecarDitado();
};

/* Fechar a janela com uma sessao aberta: ela e descartada, para a fila de
   transcricao nao ficar esperando por ninguem. */
window.addEventListener("pagehide", () => {
  if (ditado.sessao) navigator.sendBeacon && fetch("/api/voz/ao-vivo/" + ditado.sessao, { method: "DELETE", keepalive: true }).catch(() => {});
});

/* ------------------------------------------------------------ enviar */

/* O botao da caixa de pedido tem quatro rostos. ENVIAR e o de sempre. PARAR
   aparece na conversa cuja resposta esta sendo escrita - por esta pagina ou
   por uma sessao que ja nao existe e a deixou "trabalhando". PARANDO e o
   instante entre o clique e o servidor confirmar. ESPERANDO e fora dessa
   conversa (no inicio, em outra): uma resposta anda por vez, entao o enviar
   fica esmaecido, e interromper e pelo icone do cartao em "Acontecendo
   agora" - antes o botao virava parar ali tambem, e nao parava nada. */
const ENVIAR_ORIGINAL = $("enviar").innerHTML;

function modoDoEnviar(modo) {
  const botao = $("enviar");
  const parar = modo === "parar" || modo === "parando";
  botao.classList.toggle("parar", parar);
  botao.classList.toggle("esperando", modo === "esperando");
  botao.disabled = modo === "parando" || modo === "esperando";
  botao.title = parar ? "Parar a resposta" : (modo === "esperando" ? "Uma resposta está sendo escrita — interrompa pelo cartão em Acontecendo agora" : "Enviar");
  botao.setAttribute("aria-label", botao.title);
  botao.innerHTML = parar ? ic("stop", 18) : ENVIAR_ORIGINAL;
}

function atualizarBotaoEnviar() {
  if (estado.ocupado) modoDoEnviar(estado.trabalhoId && estado.trabalhoId === estado.respondendoId ? "parar" : "esperando");
  else modoDoEnviar(estado.trabalho && estado.trabalho.estado === "executando" ? "parar" : "enviar");
}

/* Conversa aberta "trabalhando" sem resposta andando nesta pagina: a janela
   foi recarregada no meio, ou a resposta e de antes. Ainda da para parar. */
function respondendoFora() {
  return Boolean(!estado.ocupado && estado.trabalho && estado.trabalho.estado === "executando");
}

async function pararResposta() {
  const id = estado.trabalhoId;
  if (!id) return;
  modoDoEnviar("parando");
  let d = {};
  try {
    d = await (await fetch("/api/trabalhos/" + id + "/parar", { method: "POST" })).json();
  } catch (err) { /* o servidor sumiu: cortar a leitura daqui mesmo */ }
  if (estado.ocupado) {
    /* A resposta desta pagina termina sozinha com o evento "parado", em ate
       um quarto de segundo. Se nao terminar - servidor travado -, a pagina
       corta a leitura dela e segue. */
    const controle = estado.controle;
    setTimeout(() => { if (estado.ocupado && estado.controle === controle && controle) controle.abort(); }, 5000);
    return;
  }
  /* Nada andando por aqui: a rota ja devolveu a conversa como parada. */
  if (!d.parando) {
    abrirTrabalho(id);
  } else {
    setTimeout(() => abrirTrabalho(id), 700);
  }
}


async function enviar() {
  if (estado.ocupado) return;
  // Enviar com ditado aberto ou pendente: primeiro o texto ditado entra no campo.
  if (ditado.estado && ditado.estado !== "finalizando") await usarDitadoNoChat();
  const pedido = $("pedido").value.trim();
  if (!pedido) return;

  if (!estado.trabalhoId) {
    const r = await fetch("/api/trabalhos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pedido: pedido }),
    });
    const t = await r.json();
    estado.trabalhoId = t.id;
    estado.trabalho = t;
    $("centro").innerHTML = "";
  }

  entrarNaConversa();
  estado.ocupado = true;
  estado.respondendoId = estado.trabalhoId;
  estado.controle = new AbortController();
  modoDoEnviar("parar");
  $("pedido").value = "";
  $("pedido").style.height = "auto";
  atualizarSelo(true);

  const centro = $("centro");
  centro.insertAdjacentHTML("beforeend", bolhaPessoa(pedido));
  atualizarPostura();

  const plano = document.createElement("div");
  // "Entender o pedido" vem primeiro porque e o que acontece primeiro: nem
  // toda mensagem e pergunta sobre documento.
  plano.innerHTML = cartaoPlano(
    [{ titulo: "Entender o pedido", estado: "executando", feitos: 0, total: 0, detalhe: "" },
     { titulo: "Procurar e responder", estado: "na_fila", feitos: 0, total: 0, detalhe: "" }], 1);
  centro.appendChild(plano);

  // A janelinha dos bastidores: o que esta acontecendo, enquanto acontece.
  const bastidores = document.createElement("div");
  centro.appendChild(bastidores);
  abrirBastidor(bastidores);

  const resposta = document.createElement("div");
  resposta.className = "resposta";
  resposta.innerHTML = '<div class="texto"></div>';
  centro.appendChild(resposta);
  const texto = resposta.querySelector(".texto");
  rolar();

  let citados = 0;
  const inicio = Date.now();
  const relogio = setInterval(() => {
    const c = $("cronometro");
    if (c) c.textContent = Math.round((Date.now() - inicio) / 1000) + " s";
  }, 1000);

  try {
    const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/perguntar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pergunta: pedido, apenas: estado.escopo }),
      signal: estado.controle.signal,
    });
    if (!r.ok) throw new Error("não consegui responder");

    const leitor = r.body.getReader();
    const dec = new TextDecoder();
    let buffer = "", primeiro = true;

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
        const dados = JSON.parse(md[1]);

        if (mt[1] === "fontes") {
          /* Quando a pergunta nomeia um arquivo, a leitura para nele — e o
             bastidor diz isso, porque "li 1 de 9" sem explicação parece falha
             de cobertura quando é obediência ao que foi pedido. */
          definirEscopo(dados.apenas || []);
          anotarBastidor(dados.apenas.length
            ? (dados.apenas.length === 1
                ? "a pergunta é sobre “" + dados.apenas[0] + "” · li só ele, "
                : "a pergunta é sobre " + plural(dados.apenas.length, "documento") +
                  " · li só eles, ") + plural(dados.trechos.length, "trecho")
            : "procurei nos " + plural(dados.total_contratos, "documento") +
              " abertos · vou usar " + plural(dados.trechos.length, "trecho") +
              " de " + plural(dados.consultados.length, "documento"));
          if (dados.ignorados.length) {
            anotarBastidor(plural(dados.ignorados.length, "documento") +
              " sem trecho sobre isso: " + dados.ignorados.join(", "), "atencao");
            resposta.insertAdjacentHTML("afterbegin", avisoCobertura(dados));
          }
          resposta.insertAdjacentHTML("beforeend", blocoFontes(dados.trechos, dados));
          citados = new Set(dados.trechos.map((f) => f.documento)).size;
          desenharTrechos(dados.trechos, pedido, resposta.querySelector(".visor-caixa"));
        } else if (mt[1] === "lendo") {
          anotarBastidor("mandei " + milhar(dados.caracteres) + " caracteres para o " +
            dados.modelo + ", janela de " + milhar(dados.janela) + " tokens");
          bastidor.previsao = dados.previsao;
          if (dados.previsao && dados.previsao.sabe) {
            anotarBastidor("aqui, leituras deste tamanho levaram ~" +
              dados.previsao.segundos + " s (mediana de " +
              plural(dados.previsao.medicoes, "leitura") + ")");
          } else {
            anotarBastidor("ainda não medi leituras deste modelo nesta máquina — " +
              "esta vai virar a primeira medida");
          }
          faseBastidor("lendo", "lendo…");
        } else if (mt[1] === "escrevendo") {
          anotarBastidor("primeira palavra saiu · esperei " +
            segundosBR(dados.lendo_segundos) + " até aqui");
          bastidor.escreveDesde = Date.now();
          bastidor.palavras = 0;
          faseBastidor("escrevendo", "escrevendo…");
        } else if (mt[1] === "medida") {
          fecharBastidor();
          // Dois tempos diferentes e de proposito: o que a pessoa esperou e o
          // que o modelo gastou calculando. A diferenca e o modelo carregando.
          anotarBastidor("pronto · o modelo gastou " + segundosBR(dados.lendo_segundos) +
            " lendo " + milhar(dados.tokens_lidos) + " tokens" +
            (dados.do_cache ? " (boa parte ja estava em cache)" : "") +
            " e " + segundosBR(dados.escrevendo_segundos) + " escrevendo " +
            milhar(dados.tokens_escritos), "feito");
        } else if (mt[1] === "etapas") {
          plano.innerHTML = cartaoPlano(dados.etapas, 2);
          desenharProgresso(dados.etapas);
        } else if (mt[1] === "token") {
          if (primeiro) { texto.textContent = ""; primeiro = false; }
          texto.textContent += dados.t;
          // Palavras escritas ate agora: e o numero que a janelinha mostra
          // subindo enquanto o modelo escreve. Contado, nao estimado.
          bastidor.palavras = texto.textContent.trim().split(/\s+/).filter(Boolean).length;
          if (pertoDoFim()) rolar(); else atualizarIrAoFim();
        } else if (mt[1] === "proposta") {
          // Pedido de ação: nada de procurar nos documentos. O cartão mostra
          // o que eu entendi, e quem grava é a pessoa.
          plano.remove();
          const caixa = document.createElement("div");
          caixa.className = "proposta-caixa";
          caixa.innerHTML = cartaoProposta(dados);
          resposta.appendChild(caixa);
          ligarProposta(caixa, dados);
          rolar();
        } else if (mt[1] === "vazio") {
          texto.textContent = dados.mensagem;
        } else if (mt[1] === "erro") {
          plano.innerHTML = '<div class="aprovacao"><p><strong>Não consegui terminar.</strong> ' +
            esc(dados.mensagem) + '</p><div class="acoes"><button class="primario" onclick="location.reload()">Tentar de novo</button></div></div>';
        } else if (mt[1] === "parado") {
          // A pessoa parou: o que ja saiu fica, com a marca de que parou ali.
          fecharBastidor();
          plano.remove();
          if (!texto.textContent.trim()) texto.textContent = "Parei antes de escrever a resposta.";
          resposta.insertAdjacentHTML("afterbegin", etiquetaDeParada());
          resposta.insertAdjacentHTML("beforeend", linhaAssinatura(dados.segundos, citados, pedido));
          ligarResposta(resposta);
          $("conversa-titulo").textContent = dados.titulo;
        } else if (mt[1] === "fim") {
          fecharBastidor();
          plano.remove();
          resposta.insertAdjacentHTML("beforeend", linhaAssinatura(dados.segundos, citados, pedido));
          ligarResposta(resposta);
          $("conversa-titulo").textContent = dados.titulo;
        }
      }
    }
  } catch (err) {
    if (err && err.name === "AbortError") {
      plano.remove();
      if (!texto.textContent.trim()) texto.textContent = "Parei antes de escrever a resposta.";
      resposta.insertAdjacentHTML("afterbegin", etiquetaDeParada());
    } else {
      texto.textContent = "Não consegui responder: " + err;
    }
  } finally {
    fecharBastidor();
    clearInterval(relogio);
    estado.ocupado = false;
    estado.respondendoId = null;
    estado.controle = null;
    atualizarBotaoEnviar();
    atualizarSelo(false);
    carregarTrabalhos();
    if (estado.trabalhoId) {
      fetch("/api/trabalhos/" + estado.trabalhoId)
        .then((r) => r.json())
        .then((t) => { estado.trabalho = t; desenharAtividade(t.atividade); desenharProgresso(t.etapas || []); });
    }
    rolar();
    $("pedido").focus();
  }
}

/* ------------------------------------------- o documento de que se fala

   Ler o acervo inteiro para responder sobre um documento é o que fazia a
   pergunta sobre um comprovante de viagem voltar falando de contrato de compra
   e venda: o documento citado era 3,4% do que o modelo recebia. Agora a
   conversa tem um documento em foco, e ele fica à VISTA numa pílula — escopo
   silencioso seria tão ruim quanto ler tudo calado.

   Para sair dele: o ✕ da pílula, ou pedir com todas as letras ("em todos os
   documentos"). */

const mencao = { aberta: false, itens: [], marcado: 0, inicio: -1 };

async function carregarAbertos() {
  try {
    const d = await (await fetch("/api/documentos-abertos")).json();
    estado.abertos = d.documentos || [];
  } catch (err) { estado.abertos = []; }
}

/* Lista, e nao um nome so: anexar dois arquivos e perguntar sobre "eles" e o
   caso comum - quem arrasta um contrato e o aditivo quer os dois lidos. */
function definirEscopo(nomes) {
  const lista = Array.isArray(nomes) ? nomes : (nomes ? [nomes] : []);
  estado.escopo = lista.filter((n, i) => n && lista.indexOf(n) === i);
  desenharEscopo();
}

function somarAoEscopo(nome) {
  if (nome && !estado.escopo.includes(nome)) definirEscopo(estado.escopo.concat([nome]));
}

function tirarDoEscopo(nome) {
  definirEscopo(estado.escopo.filter((n) => n !== nome));
}

function desenharEscopo() {
  const caixa = $("escopo");
  if (!caixa) return;
  atualizarPropriedades();
  caixa.hidden = false;
  if (!estado.escopo.length) {
    caixa.innerHTML = '<span class="escopo-acervo" title="Lendo o acervo inteiro — anexe um documento, ou digite / na caixa, para focar num só">' + ic("folder", 18) + "<b>" +
      (estado.contratos ? "Acervo · " + plural(estado.contratos, "documento") : "Acervo vazio") + "</b></span>";
    return;
  }

  caixa.hidden = false;
  caixa.innerHTML = estado.escopo.map((nome) =>
      '<span class="escopo-pilula" title="Lendo só este documento">' + ic("folder", 18) +
      '<b class="corta">' + esc(nome) + "</b>" +
      '<button data-tirar="' + esc(nome) + '" title="Tirar este documento do foco" ' +
      'aria-label="Tirar ' + esc(nome) + ' do foco">✕</button></span>').join("") +
    (estado.escopo.length > 1
      ? '<button class="escopo-limpar" id="escopo-tirar">procurar em todos</button>'
      : "");

  caixa.querySelectorAll("[data-tirar]").forEach((b) => {
    b.onclick = () => { tirarDoEscopo(b.dataset.tirar); $("pedido").focus(); };
  });
  const limpar = $("escopo-tirar");
  if (limpar) limpar.onclick = () => { definirEscopo([]); $("pedido").focus(); };
}

/* O "/" e o que vem depois dele, até o cursor. Só vale no começo de uma
   palavra: "e/ou" não abre menção. */
function termoDaMencao() {
  const campo = $("pedido");
  const ate = campo.value.slice(0, campo.selectionStart);
  const barra = ate.lastIndexOf("/");
  if (barra < 0) return null;
  if (barra > 0 && !/\s/.test(ate[barra - 1])) return null;
  const termo = ate.slice(barra + 1);
  if (/[\n]/.test(termo)) return null;
  return { inicio: barra, termo: termo };
}

function fecharMencao() {
  mencao.aberta = false;
  const caixa = $("mencao");
  if (caixa) { caixa.hidden = true; caixa.innerHTML = ""; }
}

function abrirMencao() {
  const achado = termoDaMencao();
  const caixa = $("mencao");
  if (!caixa || !achado) { fecharMencao(); return; }

  const plano = (t) => String(t || "").normalize("NFD")
    .replace(new RegExp("[\u0300-\u036f]", "g"), "").toLowerCase();
  const procurado = plano(achado.termo);
  const todos = estado.abertos || [];
  mencao.itens = todos.filter((d) => plano(d.nome).includes(procurado)).slice(0, 12);
  mencao.marcado = 0;
  mencao.inicio = achado.inicio;
  mencao.aberta = true;

  caixa.hidden = false;
  caixa.innerHTML = mencao.itens.length
    ? mencao.itens.map((d, i) =>
        '<button class="mencao-item' + (i === 0 ? " marcado" : "") +
        '" data-doc="' + esc(d.nome) + '"><b>' + esc(d.nome) + "</b>" +
        (d.paginas ? '<span class="rotulo">' + plural(d.paginas, "página") + "</span>" : "") +
        "</button>").join("")
    : '<div class="mencao-vazio">nenhum documento aberto com “' +
      esc(achado.termo) + "”</div>";

  caixa.querySelectorAll("[data-doc]").forEach((b) => {
    b.onmousedown = (e) => { e.preventDefault(); escolherMencao(b.dataset.doc); };
  });
}

function escolherMencao(nome) {
  const campo = $("pedido");
  /* Tira o "/termo" do texto: quem guarda o documento é a pílula, e deixar o
     nome escrito no meio da frase faria a pergunta chegar ao modelo com um
     pedaço que não é pergunta. */
  const antes = campo.value.slice(0, mencao.inicio);
  const depois = campo.value.slice(campo.selectionStart);
  campo.value = (antes + depois).replace(/^\s+/, "");
  campo.selectionStart = campo.selectionEnd = antes.replace(/^\s+/, "").length;

  somarAoEscopo(nome);
  fecharMencao();
  campo.focus();
}

function andarNaMencao(passo) {
  if (!mencao.itens.length) return;
  mencao.marcado = (mencao.marcado + passo + mencao.itens.length) % mencao.itens.length;
  const caixa = $("mencao");
  caixa.querySelectorAll(".mencao-item").forEach((b, i) => {
    b.classList.toggle("marcado", i === mencao.marcado);
    if (i === mencao.marcado) b.scrollIntoView({ block: "nearest" });
  });
}

$("enviar").onclick = () => {
  const aqui = estado.ocupado && estado.trabalhoId && estado.trabalhoId === estado.respondendoId;
  return (aqui || respondendoFora()) ? pararResposta() : enviar();
};
$("pedido").addEventListener("keydown", (e) => {
  if (mencao.aberta) {
    if (e.key === "ArrowDown") { e.preventDefault(); andarNaMencao(1); return; }
    if (e.key === "ArrowUp") { e.preventDefault(); andarNaMencao(-1); return; }
    if (e.key === "Escape") { e.preventDefault(); fecharMencao(); return; }
    if ((e.key === "Enter" || e.key === "Tab") && mencao.itens.length) {
      e.preventDefault();
      escolherMencao(mencao.itens[mencao.marcado].nome);
      return;
    }
  }
  if (estado.modoBusca && e.key === "Escape") { e.preventDefault(); modoDeBusca(false); return; }
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (estado.modoBusca) $("buscar").click(); else enviar(); }
});
$("pedido").addEventListener("input", (e) => {
  e.target.style.height = "auto";
  e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px";
  if (termoDaMencao()) abrirMencao(); else fecharMencao();
});
$("pedido").addEventListener("blur", () => setTimeout(fecharMencao, 120));

/* ------------------------------------------------------------- estado */

/* A marca do trilho e so a marca: quando o assistente trabalha, quem diz e a
   propria conversa - o cartao do plano, a linha do que esta acontecendo e o
   ponto no cabecalho. Um anel girando em volta do logo repetia isso no canto
   do olho, longe de onde a pessoa esta lendo. */
function atualizarSelo(trabalhando) {
  document.documentElement.classList.toggle("trabalhando", Boolean(trabalhando));
}

async function carregarStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    estado.contratos = s.contratos;
    estado.modelo = s.modelo || "";
    estado.trechos = s.trechos || 0;
    estado.pasta = s.pasta || "";
    $("conversa-meta").textContent = s.contratos
      ? plural(s.contratos, "documento") + " abertos · " + s.trechos + " trechos"
      : "nenhum documento aberto";
    desenharAvisoDoMotor(s);
    desenharEscopo();
    if ($("conversa-col").classList.contains("vazia")) desenharRecentes();
  } catch (err) { /* servidor caiu; o anel do trilho ja parou */ }
}

/* O cartao de erro do motor (docs/ui/05): "O assistente esta desligado" com
   Ligar agora; "Falta baixar o modelo" com o tamanho e Baixar agora; "O
   Ollama nao esta instalado" com o caminho. Aparece no inicio, acima da
   caixa de pedido, e some sozinho quando o motor responde. */
let relogioDaPuxada = null;

function desenharAvisoDoMotor(s) {
  const alvo = $("aviso-motor");
  if (!alvo) return;
  const m = s.motor || {};
  const puxando = m.puxando || {};
  if ((s.ollama && !puxando.andando) || !$("conversa-col").classList.contains("vazia")) {
    alvo.hidden = true;
    alvo.innerHTML = "";
    return;
  }
  let titulo, causa, acao;
  if (puxando.andando) {
    titulo = "Baixando o modelo do assistente";
    causa = "Uma vez só, com internet. Dá para continuar usando o PAULUS; o assistente responde quando terminar.";
    acao = '<div class="barra-fina"><i id="motor-barra" style="width:' + (puxando.progresso || 1) + '%"></i></div><small id="motor-linha">' + esc(puxando.linha || "começando…") + "</small>";
  } else if (puxando.erro) {
    titulo = "O download do modelo parou";
    causa = puxando.erro;
    acao = '<button class="primario" data-motor-puxar="1">' + ic("refresh", 16) + "Tentar de novo</button>";
  } else if (!m.instalado) {
    titulo = "O Ollama não está instalado";
    causa = "O Ollama é o programa que roda o modelo nesta máquina, sem mandar nada para fora. Instale pelo site e abra o PAULUS de novo.";
    acao = '<button class="primario" data-motor-site="1">' + ic("open_in_new", 16) + "Abrir a página do Ollama</button>";
  } else if (!m.rodando) {
    titulo = "O assistente está desligado";
    causa = "O Ollama, que roda o modelo nesta máquina, não está aberto. Dá para ligar daqui, sem terminal.";
    acao = '<button class="primario" data-motor-ligar="1">' + ic("play_arrow", 16) + "Ligar agora</button>";
  } else if (!m.modelo_presente) {
    titulo = "Falta baixar o modelo";
    causa = "O Ollama está aberto, mas o modelo" + (m.tamanho ? " (" + m.tamanho + ")" : "") + " ainda não está nesta máquina. É um download só, com internet; leva alguns minutos.";
    acao = '<button class="primario" data-motor-puxar="1">' + ic("download", 16) + "Baixar agora</button>";
  } else {
    alvo.hidden = true;
    alvo.innerHTML = "";
    return;
  }
  alvo.innerHTML = '<div class="cartao-erro"><b>' + esc(titulo) + "</b><p>" + esc(causa) + '</p><div class="acoes">' + acao + "</div>" +
    (m.mensagem && !puxando.andando ? "<details><summary>Detalhes</summary><pre>" + esc(m.mensagem) + "</pre></details>" : "") + "</div>";
  alvo.hidden = false;
  const ligar = alvo.querySelector("[data-motor-ligar]");
  if (ligar) ligar.onclick = () => ligarMotor(ligar);
  const puxar = alvo.querySelector("[data-motor-puxar]");
  if (puxar) puxar.onclick = () => puxarModelo(puxar);
  const site = alvo.querySelector("[data-motor-site]");
  if (site) site.onclick = () => window.open("https://ollama.com/download", "_blank");
  if (puxando.andando) vigiarPuxada();
}

async function ligarMotor(botao) {
  botao.disabled = true;
  botao.textContent = "ligando…";
  const r = await fetch("/api/ollama/ligar", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); botao.disabled = false; botao.textContent = "Ligar agora"; return; }
  const d = await r.json();
  if (d.ligado) avisoCert("assistente ligado", { tom: "ok" });
  else if (d.motor && d.motor.rodando) avisoCert("o Ollama abriu, mas falta o modelo", { tom: "erro" });
  else avisoCert("o Ollama não respondeu: " + (d.mensagem || ""), { tom: "erro" });
  carregarStatus();
}

async function puxarModelo(botao) {
  botao.disabled = true;
  const r = await fetch("/api/ollama/puxar", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); botao.disabled = false; return; }
  carregarStatus();
}

function vigiarPuxada() {
  clearTimeout(relogioDaPuxada);
  relogioDaPuxada = setTimeout(async () => {
    let p;
    try { p = await (await fetch("/api/ollama/puxar")).json(); } catch (err) { return; }
    if (p.andando) {
      const barra = $("motor-barra");
      if (barra) barra.style.width = (p.progresso || 1) + "%";
      const linha = $("motor-linha");
      if (linha) linha.textContent = p.linha || "baixando…";
      vigiarPuxada();
      return;
    }
    if (p.pronto) avisoCert("modelo baixado — o assistente está pronto", { tom: "ok" });
    carregarStatus();
  }, 2000);
}

async function carregarModelo() {
  try {
    const s = await (await fetch("/api/status")).json();
    $("prop-modelo").title = s.tamanho_gb
      ? String(s.tamanho_gb).replace(".", ",") + " GB na sua máquina"
      : "na sua máquina";
  } catch (err) { /* mantem o texto padrao */ }
}

/* O painel Propriedades: modelo, motor, o que esta em foco e o indice. */
function atualizarPropriedades() {
  $("prop-modelo-nome").textContent = estado.modelo || "—";
  let pasta = "—";
  if (estado.escopo.length === 1) pasta = estado.escopo[0];
  else if (estado.escopo.length > 1) pasta = plural(estado.escopo.length, "documento") + " em foco";
  else if (estado.contratos) pasta = "Acervo · " + plural(estado.contratos, "documento");
  $("prop-pasta").textContent = pasta;
  $("prop-trechos").textContent = estado.trechos ? plural(estado.trechos, "trecho") + " indexados" : "—";
}

/* ------------------------------------------------- saudacao e relogio */
/*
   A saudacao sai do relogio da maquina, nao de um modelo. Pedir isso ao
   assistente custaria 20 s de espera na abertura, e o programa promete nao
   falar com ninguem la fora - a hora ele ja tem.
*/

function contexto() {
  const d = new Date();
  const dias = ["domingo", "segunda-feira", "terça-feira", "quarta-feira",
                "quinta-feira", "sexta-feira", "sábado"];
  const meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                 "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  const h = d.getHours();
  const periodo = h < 5 ? "madrugada" : h < 12 ? "manha" : h < 18 ? "tarde" : h < 22 ? "noite" : "noite_alta";
  const hora = String(h).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  return {
    dia: dias[d.getDay()],
    hora: hora,
    periodo: periodo,
    /* A etiqueta do alto da saudacao. O dia sai sem "-feira" porque ali ele e
       um carimbo, nao uma frase. */
    momento: dias[d.getDay()].replace("-feira", "") + ", " + d.getDate() + " de " +
      meses[d.getMonth()] + " · " + hora.replace(":", "h"),
  };
}

/* O texto da saudacao fala como gente, nao como o painel de controle:
   nada de "indexar", "trecho" ou "varrer". Quem le e advogado, e o que ele
   quer saber e se pode pedir e se o que e dele fica com ele. */
function saudacao(c, temDocumentos) {
  const semDocs = "Para começar, me mande alguns documentos — ou me mostre a pasta onde eles estão.";
  const padrao = "É só me dizer o que você precisa — eu leio e respondo aqui mesmo.";
  const sub = temDocumentos ? padrao : semDocs;

  if (c.periodo === "madrugada") {
    return ["Ainda de pé a esta hora?", temDocumentos ? "Se quiser, eu adianto a leitura enquanto você descansa." : semDocs];
  }
  if (c.periodo === "noite_alta") return ["Trabalhando até tarde?!", temDocumentos ? "Me conta o que falta, e eu vou adiantando por aqui." : semDocs];
  if (c.dia === "sexta-feira") return ["Sexta. Fechamos algo antes do fim do dia?", sub];
  if (c.dia === "segunda-feira" && c.periodo === "manha") return ["Segunda. Por onde começamos?", sub];
  return ["Olá. Por onde começamos?", sub];
}

function atualizarSaudacao() {
  const c = contexto();
  const [titulo, sub] = saudacao(c, estado.contratos > 0);
  $("momento").textContent = c.momento;
  $("chamada").textContent = titulo;
  /* O texto base fica guardado aqui porque `carregarAgora` acrescenta a
     situacao do acervo a esta mesma frase, e ele roda a cada cinco segundos:
     sem a base, a frase cresceria sozinha a cada volta. */
  $("sub-chamada").dataset.base = sub;
  $("sub-chamada").textContent = sub;
  $("relogio").textContent = c.hora;
}

setInterval(() => { $("relogio").textContent = contexto().hora; }, 30000);

/* ------------------------------------------------- acontecendo agora */

async function carregarAgora() {
  if (!$("conversa-col").classList.contains("vazia")) {
    $("agora").hidden = true;
    return;
  }

  let d;
  try {
    d = await (await fetch("/api/agora")).json();
  } catch (err) {
    $("agora").hidden = true;
    return;
  }

  const cartoes = [];

  for (const t of d.executando) {
    const quanto = t.total
      ? t.feitos + " de " + t.total
      : (t.progresso ? t.progresso + "%" : "começando");
    cartoes.push(
      '<div class="cartao-agora" data-abre="' + esc(t.id) + '"><div class="cabeca">' + coroa(20) +
      '<span class="nome corta">' + esc(t.titulo) + "</span>" +
      '<button class="agora-parar" data-parar-trabalho="' + esc(t.id) + '" title="Interromper" aria-label="Interromper">' + ic("stop", 18) + "</button></div>" +
      '<div class="barra-fina"><i style="width:' + (t.progresso || 4) + '%"></i></div>' +
      '<div class="rodape">' + esc(t.etapa || "trabalhando") + " · " + esc(quanto) + "</div></div>"
    );
  }

  for (const t of d.esperando) {
    cartoes.push(
      '<div class="cartao-agora chama"><div class="cabeca"><i class="ponto-acc"></i>' +
      '<span class="nome">Esperando você</span></div>' +
      '<div class="corpo">' + esc(t.pergunta) + "</div>" +
      '<div class="acoes"><button class="fantasma" data-abre="' + esc(t.id) + '">Revisar</button>' +
      '<button class="primario" data-fila="1">Aprovar</button></div></div>'
    );
  }

  /* O acervo em dia e as conversas paradas nao sao cartoes: sao frases da
     saudacao. Nenhum dos dois pede acao nenhuma - virar cartao com botao
     seria dar a eles o peso de quem espera resposta, que e dos de cima.

     Embaixo do titulo cabem DUAS linhas, entao entra uma frase de situacao
     so, depois da de abertura. A conversa que ficou pela metade vence o
     acervo em dia: e a unica das duas que a pessoa talvez queira retomar. */
  const sub = $("sub-chamada");
  const base = sub.dataset.base || sub.textContent;
  const docs = d.biblioteca.documentos;
  let situacao = "";
  if (d.pausados) {
    situacao = (d.pausados === 1 ? "Uma conversa ficou pela metade" : plural(d.pausados, "conversa") + " ficaram pela metade") +
      " — abra pelo menu para continuar.";
  } else if (docs) {
    situacao = (docs === 1 ? "Seu documento já está lido" : "Seus " + docs + " documentos já estão lidos") +
      ", e nada saiu deste computador hoje.";
  }
  sub.textContent = situacao ? base + " " + situacao : base;

  const espera = vinculoPendente() ? [cartaoDeEsperaDoVinculo()] : [];
  const ditando = cartaoDoDitado();
  $("agora").hidden = cartoes.length + espera.length === 0 && !ditando;
  $("agora-cartoes").innerHTML = ditando + espera.concat(cartoes).join("");
  ligarCartaoDoDitado();
  ligarEsperaDoVinculo();
  $("agora-cartoes").querySelectorAll("[data-abre]").forEach((el) => {
    el.onclick = (e) => {
      e.stopPropagation();
      if (el.dataset.abre === "biblioteca") { marcarDestino("biblioteca"); mostrarBiblioteca(); }
      else abrirTrabalho(el.dataset.abre);
    };
  });
  /* Interromper daqui: vale para qualquer resposta andando, inclusive a que
     esta pagina esta lendo - que entao termina sozinha com "parada". */
  $("agora-cartoes").querySelectorAll("[data-parar-trabalho]").forEach((el) => {
    el.onclick = async (e) => {
      e.stopPropagation();
      el.disabled = true;
      try { await fetch("/api/trabalhos/" + el.dataset.pararTrabalho + "/parar", { method: "POST" }); } catch (err) { /* a lista se refaz */ }
      avisoCert("resposta interrompida", { tom: "ok" });
      setTimeout(carregarAgora, 600);
    };
  });
  $("agora-cartoes").querySelectorAll("[data-fila]").forEach((el) => {
    el.onclick = () => { marcarDestino("aprovacoes"); mostrarAprovacoes(); };
  });
}

setInterval(carregarAgora, 5000);

