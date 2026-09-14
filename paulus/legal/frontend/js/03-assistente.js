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

$("buscar").onclick = async () => {
  const termo = $("pedido").value.trim();
  if (!termo || estado.ocupado) return;
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
      bloco.innerHTML = "<div>Não achei essa palavra nos " + plural(d.contratos, "contrato") + " abertos.</div>";
    } else {
      const nomes = new Set(d.resultados.map((x) => x.documento));
      bloco.innerHTML = "<div>" + plural(d.resultados.length, "trecho") + " em " + plural(nomes.size, "contrato") + ", sem passar pelo assistente.</div>" +
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
  modoDoEnviar(estado.ocupado || t.estado === "executando" ? "parar" : "enviar");
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
  lista.innerHTML = fontes.map((f, i) =>
    '<div class="trecho-cartao' + (i === 0 ? " marcado" : "") + '">' +
    '<div class="trecho-origem"><span class="cit">' + (i + 1) + "</span><b>" + esc(f.documento) + "</b>" +
    '<span class="onde">' + esc(f.onde || ("trecho " + f.trecho)) + "</span>" +
    '<span class="ic ic-16 vira">expand_more</span></div>' +
    '<div class="trecho-texto">' + esc(f.texto) + "</div>" +
    '<button class="trecho-ver" data-ver-cit="' + i + '">ver no documento</button></div>').join("");

  lista.querySelectorAll(".trecho-cartao").forEach((c) => {
    c.onclick = () => lista.querySelectorAll(".trecho-cartao").forEach((o) => o.classList.toggle("marcado", o === c));
  });
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

function rolar() { $("fluxo").scrollTop = $("fluxo").scrollHeight; }

/* ------------------------------------------------------------ enviar */

/* O botao da caixa de pedido tem tres rostos. ENVIAR e o de sempre. PARAR
   aparece enquanto uma resposta esta sendo escrita - por esta pagina ou por
   uma sessao que ja nao existe e deixou a conversa "trabalhando". PARANDO e o
   instante entre o clique e o servidor confirmar: o botao fica apagado para
   ninguem clicar duas vezes. */
const ENVIAR_ORIGINAL = $("enviar").innerHTML;

function modoDoEnviar(modo) {
  const botao = $("enviar");
  const parar = modo === "parar" || modo === "parando";
  botao.classList.toggle("parar", parar);
  botao.disabled = modo === "parando";
  botao.title = parar ? "Parar a resposta" : "Enviar";
  botao.setAttribute("aria-label", botao.title);
  botao.innerHTML = parar ? ic("stop", 18) : ENVIAR_ORIGINAL;
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
          rolar();
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
    estado.controle = null;
    modoDoEnviar("enviar");
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

$("enviar").onclick = () => ((estado.ocupado || respondendoFora()) ? pararResposta() : enviar());
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
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); }
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
      '<span class="nome corta">' + esc(t.titulo) + "</span></div>" +
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
  $("agora").hidden = cartoes.length + espera.length === 0;
  $("agora-cartoes").innerHTML = espera.concat(cartoes).join("");
  ligarEsperaDoVinculo();
  $("agora-cartoes").querySelectorAll("[data-abre]").forEach((el) => {
    el.onclick = (e) => {
      e.stopPropagation();
      if (el.dataset.abre === "biblioteca") { marcarDestino("biblioteca"); mostrarBiblioteca(); }
      else abrirTrabalho(el.dataset.abre);
    };
  });
  $("agora-cartoes").querySelectorAll("[data-fila]").forEach((el) => {
    el.onclick = () => { marcarDestino("aprovacoes"); mostrarAprovacoes(); };
  });
}

setInterval(carregarAgora, 5000);

