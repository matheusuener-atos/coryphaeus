/* ---------------------------------------------------------- gravacoes */
/*
   Gravacoes (docs/ui/03-telas-desktop.md, A16): a lista, o gravador ao vivo
   e a gravacao arquivada. O audio vem do microfone (MediaRecorder) ou de
   um arquivo importado e fica nesta maquina (src/gravacoes.py). Transcricao
   por falante, resumo e contexto ao vivo precisam de um modelo de voz local
   que ainda nao esta aqui: a tela mostra o lugar deles e diz isso, em vez
   de fingir uma transcricao. A gravacao vive fora do DOM (gv.vivo): trocar
   de tela nao a interrompe, e a lista mostra "gravando · ao vivo".
*/

const GV_JSON = { "Content-Type": "application/json" };
const GV_PLURAIS = { reuniao: "Reuniões", atendimento: "Atendimentos", audiencia: "Audiências", nota: "Notas de voz" };
const GV_VELOCIDADES = [1, 1.25, 1.5, 2];

const gv = {
  visao: "lista", tipo: "", termo: "", lista: [], totalSegundos: 0, tipos: [], clientes: [], servicos: [], pasta: "",
  aberta: null, aba: "transcricao", velocidade: 1, marcarTexto: "", voz: null, relogioVoz: null, buscaTrecho: "", resumindo: false,
  escolhidas: new Set(),
  // O tocador da lista: um só áudio, fora da página, a gravação que está nele
  // e a forma da onda de cada uma, lida uma vez.
  som: null, tocandoId: null, picos: {},
  vivo: {
    estado: "pronto", inicio: 0, decorrido: 0, relogio: null, gravador: null, pedacos: [], fluxo: null, marcadores: [], erro: "",
    form: { titulo: "", tipo: "reuniao", cadastro_id: null, servico_id: null, participantes: "" },
    sessao: "", captura: null, amostras: [], enviando: false, relogioEnvio: null, enviados: 0, transcricao: [], rolar: true, avisoVivo: "",
  },
};

async function mostrarGravacoes(visao) {
  if (visao) gv.visao = visao;
  clearTimeout(gv.relogioVoz);
  if (gv.visao === "gravacao" && !gv.aberta) gv.visao = "lista";
  abrirTela("Gravações", { cheia: true });
  marcarDestino("gravacoes");
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal">' + esqueleto("lista") + '</div></div>';
  atualizarPostura();
  try {
    const pedidos = [
      fetch("/api/gravacoes?termo=" + encodeURIComponent(gv.termo)).then((r) => r.json()),
      fetch("/api/voz").then((r) => (r.ok ? r.json() : null)).catch(() => null),
    ];
    if (gv.visao === "gravacao") pedidos.push(fetch("/api/gravacoes/" + gv.aberta.id).then((r) => (r.ok ? r.json() : null)));
    const [d, voz, g] = await Promise.all(pedidos);
    gv.voz = voz;
    gv.lista = d.gravacoes || [];
    gv.totalSegundos = d.total_segundos || 0;
    gv.tipos = d.tipos || [];
    gv.clientes = d.clientes || [];
    gv.servicos = d.servicos || [];
    gv.pasta = d.pasta || "";
    if (gv.visao === "gravacao") {
      if (g) gv.aberta = g;
      else { gv.aberta = null; gv.visao = "lista"; avisoCert("essa gravação não existe mais"); }
    }
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' +
      esc(String(err)) + "</p></div></div>";
    return;
  }
  desenharGravacoes();
}

async function abrirGravacao(id) {
  gv.aberta = { id: id };
  gv.aba = "transcricao";
  await mostrarGravacoes("gravacao");
}

function desenharGravacoes() {
  cabecalhoGravacoes();
  let html;
  if (gv.visao === "vivo") html = '<div class="acervo gv-tela" id="gv-tela">' + corpoAoVivo() + painelAoVivo() + "</div>";
  else if (gv.visao === "gravacao") html = '<div class="acervo gv-tela" id="gv-tela">' + corpoDaGravacao() + painelDaGravacao() + "</div>";
  else html = '<div class="acervo gv-tela sem-painel" id="gv-tela">' + corpoDaListaGv() + "</div>";
  $("centro").innerHTML = html;
  ligarGravacoes();
  atualizarPostura();
  vigiarVoz();
}

/* ------------------------------------------------------------ tempo */

function duracaoGv(segundos) {
  const s = Math.max(0, Math.round(segundos || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const dois = (n) => String(n).padStart(2, "0");
  return h ? h + ":" + dois(m) + ":" + dois(r) : m + ":" + dois(r);
}

function duracaoLongaGv(segundos) {
  const s = Math.max(0, Math.round(segundos || 0));
  const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
  if (h) return h + " h " + m + " min";
  if (m) return m + " min";
  return s + " s";
}

function segundosGravados() {
  const v = gv.vivo;
  return (v.decorrido + (v.estado === "gravando" ? Date.now() - v.inicio : 0)) / 1000;
}

function quandoDaGravacao(g) {
  const d = new Date(g.criado_em);
  if (isNaN(d)) return "";
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const dias = -diasAte(g.criado_em.slice(0, 10));
  if (dias === 0) return "hoje " + hora;
  if (dias === 1) return "ontem " + hora;
  return d.getDate() + " " + MESES_CURTOS[d.getMonth()] + (d.getFullYear() !== new Date().getFullYear() ? " " + d.getFullYear() : "") + " " + hora;
}

function tituloPadraoGv(form) {
  const rotulo = (gv.tipos.find((t) => t.valor === form.tipo) || {}).rotulo || "Gravação";
  const d = new Date();
  return rotulo + " · " + d.getDate() + " " + MESES_CURTOS[d.getMonth()] + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

/* ------------------------------------------------------ o cabecalho */

function cabecalhoGravacoes() {
  const titulo = $("conversa-titulo");
  const meta = $("conversa-meta");
  const nav = $("nav-tela");
  const botao = (v, r) => {
    const classe = v === gv.aba ? "ativa" : "";
    return '<button class="' + classe + '" data-gv-aba="' + v + '">' + r + "</button>";
  };
  const voltar = '<button class="voltar" data-gv-voltar="1" title="Voltar à lista" aria-label="Voltar à lista">' + ic("arrow_back", 18) + "</button>";
  if (gv.visao === "vivo") {
    const v = gv.vivo;
    nav.innerHTML = voltar;
    titulo.textContent = v.estado === "pronto" ? "Nova gravação" : (v.form.titulo || tituloPadraoGv(v.form));
    meta.textContent = v.estado === "pronto" ? "microfone desta máquina · o áudio fica só aqui" : metaAoVivo();
    $("acoes-tela").innerHTML =
      '<div class="visoes">' + botao("vivo", "Ao vivo") + botao("transcricao", "Transcrição") + botao("resumo", "Resumo") + "</div>" +
      (v.estado === "pronto"
        ? '<button class="primario com-icone" data-gv-comecar="1">' + ic("mic", 16) + "Começar a gravar</button>"
        : '<button class="primario com-icone" data-gv-parar="1"' + (v.estado === "salvando" ? " disabled" : "") + ">" + ic("stop_circle", 16) + "Parar e arquivar</button>");
    return;
  }
  if (gv.visao === "gravacao" && gv.aberta) {
    const g = gv.aberta;
    nav.innerHTML = voltar;
    titulo.textContent = g.titulo;
    meta.textContent = [quandoDaGravacao(g), duracaoLongaGv(g.duracao_s), g.participantes_lista.join(", ")].filter(Boolean).join(" · ") +
      " · " + statusDaGravacao(g);
    $("acoes-tela").innerHTML =
      '<div class="visoes">' + botao("transcricao", "Transcrição") + botao("resumo", "Resumo") + botao("marcadores", "Marcadores") + "</div>" +
      '<button class="com-icone" data-gv-compartilhar="1">' + ic("mail", 16) + "Compartilhar resumo</button>" +
      '<button class="primario com-icone" data-gv-perguntar="1">' + ic("forum", 16) + "Perguntar sobre esta gravação</button>";
    return;
  }
  nav.innerHTML = "";
  titulo.textContent = "Gravações";
  meta.textContent = plural(gv.lista.length, "gravação", "gravações") + " · reuniões, atendimentos, audiências e notas de voz · o áudio fica nesta máquina";
  $("acoes-tela").innerHTML =
    '<label class="busca-tela">' + ic("search", 18) + '<input type="text" id="gv-busca" placeholder="Buscar gravações…" value="' + esc(gv.termo) + '"></label>' +
    '<button class="primario com-icone" data-gv-nova="1">' + ic("mic", 16) + "Nova gravação</button>";
}

function metaAoVivo() {
  const v = gv.vivo;
  const servico = gv.servicos.find((s) => s.id === v.form.servico_id);
  return [servico ? "Serviço: " + servico.nome : "", (gv.tipos.find((t) => t.valor === v.form.tipo) || {}).rotulo,
    v.estado === "pausada" ? "pausada" : (v.estado === "salvando" ? "guardando" : "gravando")].filter(Boolean).join(" · ");
}

/* ----------------------------------------------------------- a lista */

function avataresGv(nomes, quantos) {
  const lista = nomes.slice(0, quantos || 3);
  const resto = nomes.length - lista.length;
  if (!lista.length) return '<span class="gv-avatares"><small>—</small></span>';
  return '<span class="gv-avatares">' + lista.map((n) => '<span class="cad-avatar" title="' + esc(n) + '">' + esc(iniciaisDoRemetente(n)) + "</span>").join("") +
    (resto > 0 ? "<small>+" + resto + "</small>" : "") + "</span>";
}

function linhaAoVivoGv() {
  const v = gv.vivo;
  if (v.estado === "pronto") return "";
  const nomes = v.form.participantes.split(",").map((x) => x.trim()).filter(Boolean);
  return '<div class="tabela-linha colunas-gravacoes" data-gv-vivo="1"><span class="gv-ic-linha viva">' + ic("mic", 20) + "</span>" +
    '<div class="duas-linhas"><b>' + esc(v.form.titulo || tituloPadraoGv(v.form)) + "</b><small>" + esc(metaAoVivo()) + "</small></div>" +
    avataresGv(nomes) + '<span class="gv-duracao" id="gv-tempo-linha">' + duracaoGv(segundosGravados()) + "</span>" +
    '<span class="fin-status gv-viva">' + (v.estado === "pausada" ? "pausada · ao vivo" : "gravando · ao vivo") + '</span><span></span></div>';
}

function corpoDaListaGv() {
  const lista = gv.tipo ? gv.lista.filter((g) => g.tipo === gv.tipo) : gv.lista;
  const chips = [["", "Todas · " + gv.lista.length]].concat(gv.tipos.map((t) => [t.valor, GV_PLURAIS[t.valor] || t.rotulo])).map(([v, r]) => {
    const classe = v === gv.tipo ? "on" : "";
    return '<button class="' + classe + '" data-gv-tipo="' + v + '">' + r + "</button>";
  }).join("");
  const linhas = lista.map((g) => {
    const sub = [quandoDaGravacao(g), g.servico_nome ? "Serviço: " + g.servico_nome : "", !g.servico_nome && g.cliente_nome ? g.cliente_nome : ""].filter(Boolean).join(" · ");
    const status = statusDaGravacao(g);
    const classe = "tabela-linha colunas-gravacoes" + (gv.escolhidas.has(String(g.id)) ? " escolhida" : "");
    return '<div class="' + classe + '" data-gv-abrir="' + g.id + '" data-sel="' + g.id + '">' + iconeDaLinhaGv(g) +
      '<div class="duas-linhas"><b>' + esc(g.titulo) + "</b><small>" + esc(sub) + "</small></div>" + avataresGv(g.participantes_lista) +
      '<span class="gv-duracao">' + duracaoGv(g.duracao_s) + '</span><span class="fin-status">' + status + "</span>" +
      '<button class="mais-linha" data-gv-mais="' + g.id + '" title="Mais">' + ic("more_horiz", 18) + "</button></div>";
  }).join("");
  let vazio = "";
  if (!linhas && !linhaAoVivoGv()) {
    vazio = '<p class="rel-vazio">' + (gv.termo ? "Nada com “" + esc(gv.termo) + "”. Procurei no título, nos participantes, nas notas, no cliente e no serviço." :
      (gv.tipo ? "Nenhuma gravação deste tipo." : "Nenhuma gravação ainda. Grave pelo microfone em Nova gravação ou importe um áudio — tudo fica nesta máquina, e a transcrição entra quando houver um modelo de voz local.")) + "</p>";
  }
  const barra = gv.escolhidas.size
    ? barraDeSelecao(gv.escolhidas.size, true, '<button class="botao-icone perigo" data-gv-sel-apagar="1" title="Apagar" aria-label="Apagar">' + ic("delete", 18) + "</button>", "data-gv-sel-limpar")
    : '<div class="ag-chips">' + chips + "</div>";
  return '<div class="acervo-principal">' + tocadorDaListaGv() + '<div class="tabela-cartao gv-lista">' +
    '<div class="tabela-barra">' + barra +
    '<div class="direita"><input type="file" id="gv-importar" hidden accept="audio/*,.webm,.ogg,.opus,.mp3,.m4a,.wav,.aac,.flac,.mp4">' +
    '<button data-gv-importar="1">' + ic("upload", 16) + 'Importar áudio</button><button class="primario" data-gv-nova="1">' + ic("mic", 16) + "Nova gravação</button></div></div>" +
    '<div class="tabela-cabecalho colunas-gravacoes"><span></span><span>Gravação</span><span>Participantes</span><span>Duração</span><span>Status</span><span></span></div>' +
    '<div class="tabela-corpo">' + linhaAoVivoGv() + linhas + vazio + "</div>" +
    '<div class="tabela-rodape"><span>' + lista.length + " de " + gv.lista.length + " · " + duracaoLongaGv(gv.totalSegundos) + ' gravados</span>' +
    '<span class="direita">' + esc(notaDaVoz()) + "</span></div></div></div>";
}

/* ------------------------------------------------ o tocador da lista */

/* O TOCADOR DA LISTA. Fora de cartão, acima da tabela: a gravação escolhida
   (a mais recente, até alguém tocar outra), a forma da onda — que se clica
   para ir a um ponto —, o tempo e a velocidade. A linha que está tocando
   mostra o equalizador. O áudio é um objeto só, fora da página: trocar o
   filtro redesenha a lista sem cortar o som; sair da lista para. */
const GV_BARRAS = 96;
// Forma da onda só de gravação de até meia hora: ler o áudio inteiro de uma
// audiência de três horas para desenhar barras não vale a memória.
const GV_ONDA_ATE_S = 30 * 60;

function somGv() {
  if (!gv.som) {
    const som = new Audio();
    som.preload = "metadata";
    som.ontimeupdate = () => pintarTocadorGv(false);
    som.onplay = som.onpause = som.onended = () => pintarTocadorGv(true);
    som.onerror = () => { if (som.getAttribute("src")) avisoCert("não consegui tocar o áudio — o formato pode não ser reconhecido por esta janela"); };
    gv.som = som;
  }
  return gv.som;
}

function gravacaoDoTocadorGv() {
  return gv.lista.find((g) => g.id === gv.tocandoId) || gv.lista.find((g) => g.existe);
}

function tocandoAgoraGv(id) {
  return Boolean(gv.som && gv.tocandoId === id && !gv.som.paused);
}

function iconeDaLinhaGv(g) {
  if (!g.existe) return '<span class="gv-ic-linha">' + ic("graphic_eq", 20) + "</span>";
  const tocando = tocandoAgoraGv(g.id);
  const classe = "gv-ic-linha" + (tocando ? " tocando" : "");
  const parado = tocando ? '<span class="gv-ic-onda gv-eq"><i></i><i></i><i></i><i></i></span>' : '<span class="gv-ic-onda">' + ic("graphic_eq", 20) + "</span>";
  return '<button type="button" class="' + classe + '" data-gv-tocar-linha="' + g.id + '" title="' + (tocando ? "Pausar" : "Tocar") + '">' +
    parado + '<span class="gv-ic-tocar">' + ic(tocando ? "pause" : "play_arrow", 20) + "</span></button>";
}

function tocadorDaListaGv() {
  const g = gravacaoDoTocadorGv();
  if (!g) return "";
  const som = gv.som;
  const deste = Boolean(som && gv.tocandoId === g.id);
  const tocando = tocandoAgoraGv(g.id);
  const total = deste && isFinite(som.duration) && som.duration ? som.duration : g.duracao_s;
  const agora = deste ? som.currentTime : 0;
  const picos = gv.picos[g.id] || Array.from({ length: GV_BARRAS }, () => 0.14);
  const tocadas = total ? Math.round((agora / total) * picos.length) : 0;
  const barras = picos.map((p, i) => {
    const classe = i < tocadas ? "tocada" : "";
    return '<i class="' + classe + '" style="height:' + Math.max(10, Math.round(p * 100)) + '%"></i>';
  }).join("");
  const classe = "gv-radio" + (tocando ? " tocando" : "");
  return '<div class="' + classe + '" id="gv-radio" data-gv-radio="' + g.id + '">' +
    '<button class="gv-radio-tocar" data-gv-radio-tocar="1" title="' + (tocando ? "Pausar" : "Tocar") + '" aria-label="' + (tocando ? "Pausar" : "Tocar") + '">' +
    ic(tocando ? "pause" : "play_arrow", 24) + "</button>" +
    '<div class="duas-linhas gv-radio-titulo"><b>' + esc(g.titulo) + "</b><small>" + esc([quandoDaGravacao(g), statusDaGravacao(g)].filter(Boolean).join(" · ")) + "</small></div>" +
    '<div class="gv-onda" data-gv-onda="1" title="Clique para ir a este ponto">' + barras + "</div>" +
    '<span class="gv-radio-tempo"><span id="gv-radio-pos">' + duracaoGv(agora) + "</span> / " + duracaoGv(total) + "</span>" +
    '<button class="gv-vel" data-gv-radio-vel="1" title="Velocidade">' + velocidadeGv() + "</button></div>";
}

/* O tempo e as barras andam sem redesenhar; tocar e pausar trocam os ícones
   do tocador e das linhas. Sem o tocador na página, a lista foi embora:
   o som para. */
function pintarTocadorGv(mudouEstado) {
  const som = gv.som;
  const radio = document.getElementById("gv-radio");
  if (!som) return;
  if (!radio) { if (!som.paused) som.pause(); return; }
  if (mudouEstado) {
    redesenharTocadorGv();
    document.querySelectorAll("[data-gv-tocar-linha]").forEach((b) => {
      const g = gv.lista.find((x) => x.id === Number(b.dataset.gvTocarLinha));
      if (g) b.outerHTML = iconeDaLinhaGv(g);
    });
    ligarLinhasDoTocadorGv();
    return;
  }
  if (Number(radio.dataset.gvRadio) !== gv.tocandoId) return;
  const g = gravacaoDoTocadorGv();
  const total = isFinite(som.duration) && som.duration ? som.duration : (g ? g.duracao_s : 0);
  const barras = radio.querySelectorAll(".gv-onda i");
  const ate = total ? Math.round((som.currentTime / total) * barras.length) : 0;
  barras.forEach((b, i) => b.classList.toggle("tocada", i < ate));
  const pos = document.getElementById("gv-radio-pos");
  if (pos) pos.textContent = duracaoGv(som.currentTime);
}

/* Trocar de tela para o tocador da lista - menos voltar à própria lista
   (a busca, que redesenha tudo, não corta o som). A gravação aberta tem o
   tocador dela. */
function pararTocadorDaListaGv(tela) {
  if (!gv.som || gv.som.paused) return;
  if (tela === "Gravações" && gv.visao === "lista") return;
  gv.som.pause();
}

function redesenharTocadorGv() {
  const radio = document.getElementById("gv-radio");
  if (!radio) return;
  radio.outerHTML = tocadorDaListaGv();
  ligarTocadorDaListaGv();
}

async function tocarNaListaGv(id, fracao) {
  const som = somGv();
  if (gv.tocandoId === id && som.getAttribute("src")) {
    if (fracao !== undefined) {
      const g = gravacaoDoTocadorGv();
      const total = isFinite(som.duration) && som.duration ? som.duration : (g ? g.duracao_s : 0);
      som.currentTime = fracao * total;
      if (som.paused) som.play().catch(() => {});
      pintarTocadorGv(false);
    } else if (som.paused) som.play().catch(() => {});
    else som.pause();
    return;
  }
  gv.tocandoId = id;
  som.src = "/api/gravacoes/" + id + "/audio";
  som.playbackRate = gv.velocidade;
  if (fracao !== undefined) som.onloadedmetadata = () => { som.onloadedmetadata = null; if (isFinite(som.duration)) som.currentTime = fracao * som.duration; };
  som.play().catch(() => {});
  redesenharTocadorGv();
  carregarOndaGv(id);
}

/* A forma da onda: o áudio lido uma vez numa taxa baixa, o pico de cada
   pedaço, em GV_BARRAS barras. Formato que a janela não lê fica com as
   barras baixas - sem inventar onda. */
async function carregarOndaGv(id) {
  const g = gv.lista.find((x) => x.id === id);
  if (!g || gv.picos[id] || !g.existe || (g.duracao_s || 0) > GV_ONDA_ATE_S || !window.OfflineAudioContext) return;
  gv.picos[id] = null;
  try {
    const dados = await (await fetch("/api/gravacoes/" + id + "/audio")).arrayBuffer();
    const buffer = await new OfflineAudioContext(1, 1, 8000).decodeAudioData(dados);
    const canal = buffer.getChannelData(0);
    const passo = Math.max(1, Math.floor(canal.length / GV_BARRAS));
    const picos = [];
    for (let b = 0; b < GV_BARRAS; b++) {
      let maior = 0;
      for (let i = b * passo, fim = Math.min(canal.length, (b + 1) * passo); i < fim; i++) {
        const v = Math.abs(canal[i]);
        if (v > maior) maior = v;
      }
      picos.push(maior);
    }
    const teto = Math.max(...picos) || 1;
    gv.picos[id] = picos.map((p) => Math.sqrt(p / teto));
  } catch (err) {
    delete gv.picos[id];
    return;
  }
  const radio = document.getElementById("gv-radio");
  if (radio && Number(radio.dataset.gvRadio) === id) redesenharTocadorGv();
}

function ligarLinhasDoTocadorGv() {
  document.querySelectorAll("[data-gv-tocar-linha]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); tocarNaListaGv(Number(b.dataset.gvTocarLinha)); };
  });
}

function ligarTocadorDaListaGv() {
  const radio = document.getElementById("gv-radio");
  if (!radio) return;
  const id = Number(radio.dataset.gvRadio);
  radio.querySelector("[data-gv-radio-tocar]").onclick = () => tocarNaListaGv(id);
  const onda = radio.querySelector("[data-gv-onda]");
  onda.onclick = (e) => {
    const caixa = onda.getBoundingClientRect();
    tocarNaListaGv(id, Math.max(0, Math.min(1, (e.clientX - caixa.left) / caixa.width)));
  };
  radio.querySelector("[data-gv-radio-vel]").onclick = (e) => {
    const i = GV_VELOCIDADES.indexOf(gv.velocidade);
    gv.velocidade = GV_VELOCIDADES[(i + 1) % GV_VELOCIDADES.length];
    if (gv.som) gv.som.playbackRate = gv.velocidade;
    e.currentTarget.textContent = velocidadeGv();
  };
  carregarOndaGv(id);
}

/* ---------------------------------------------------------- ao vivo */

function corpoAoVivo() {
  const v = gv.vivo;
  let gravador;
  if (v.estado === "pronto") gravador = formaDaGravacao();
  else {
    const classe = "gv-estado" + (v.estado === "pausada" ? " parada" : "");
    const rotulo = v.estado === "pausada" ? "Pausada" : (v.estado === "salvando" ? "Guardando o áudio…" : "Gravando");
    gravador = '<div class="fin-cartao"><div class="gv-gravador">' +
      '<span class="' + classe + '"><i class="gv-pulso"></i>' + rotulo + "</span>" +
      '<div class="gv-tempo" id="gv-tempo">' + duracaoGv(segundosGravados()) + "</div>" +
      '<span class="meta">' + esc((v.form.titulo || tituloPadraoGv(v.form)) + " · " + plural(v.marcadores.length, "marcador", "marcadores") + " · microfone desta máquina") + "</span>" +
      '<div class="gv-controles">' +
      '<button class="gv-redondo" data-gv-pausar="1" title="' + (v.estado === "pausada" ? "Continuar" : "Pausar") + '"' + (v.estado === "salvando" ? " disabled" : "") + ">" + ic(v.estado === "pausada" ? "play_arrow" : "pause", 22) + "</button>" +
      '<button class="gv-redondo primario" data-gv-parar="1" title="Parar e arquivar"' + (v.estado === "salvando" ? " disabled" : "") + ">" + ic("stop", 26) + "</button>" +
      '<button class="gv-redondo" data-gv-marcar-vivo="1" title="Marcar momento"' + (v.estado === "salvando" ? " disabled" : "") + ">" + ic("bookmark_add", 22) + "</button></div>" +
      '<p class="gv-aviso">Avise os participantes de que a reunião está sendo gravada. O áudio fica só nesta máquina; trocar de tela não interrompe a gravação.</p>' +
      "</div></div>";
  }
  const transcricao = cartaoAoVivo();
  return '<div class="acervo-principal">' + gravador + transcricao + "</div>";
}

function formaDaGravacao() {
  const f = gv.vivo.form;
  const tipos = gv.tipos.map((t) => { const classe = t.valor === f.tipo ? "on" : ""; return '<button type="button" class="' + classe + '" data-gv-form-tipo="' + t.valor + '">' + esc(t.rotulo) + "</button>"; }).join("");
  const clientes = '<option value="">sem cliente</option>' + gv.clientes.map((c) => '<option value="' + c.id + '"' + (c.id === f.cadastro_id ? " selected" : "") + ">" + esc(c.nome) + "</option>").join("");
  const servicos = '<option value="">sem serviço</option>' + gv.servicos.map((s) => '<option value="' + s.id + '"' + (s.id === f.servico_id ? " selected" : "") + ">" + esc(s.nome) + "</option>").join("");
  return '<div class="fin-cartao"><div class="gv-gravador">' +
    '<span class="gv-estado pronta"><i class="gv-pulso"></i>Pronto para gravar</span>' +
    '<div class="gv-tempo">0:00</div>' +
    (gv.vivo.erro ? '<div class="gv-erro">' + esc(gv.vivo.erro) + "</div>" : "") +
    '<div class="gv-forma">' +
    '<div class="ag-campo"><label>Título</label><input type="text" data-gv-form="titulo" value="' + esc(f.titulo) + '" placeholder="' + esc(tituloPadraoGv(f)) + '"></div>' +
    '<div class="ag-campo"><label>Tipo</label><div class="ag-chips">' + tipos + "</div></div>" +
    '<div class="ag-duas"><div class="ag-campo"><label>Cliente</label><select data-gv-form="cadastro_id">' + clientes + "</select></div>" +
    '<div class="ag-campo"><label>Serviço</label><select data-gv-form="servico_id">' + servicos + "</select></div></div>" +
    '<div class="ag-campo"><label>Participantes</label><input type="text" data-gv-form="participantes" value="' + esc(f.participantes) + '" placeholder="Priscila Almeida, João Medeiros"></div>' +
    '<div class="ag-form-rodape"><button class="primario com-icone" data-gv-comecar="1">' + ic("mic", 16) + "Começar a gravar</button>" +
    '<p class="ag-explica">Microfone desta máquina. Avise os participantes de que a reunião está sendo gravada; o áudio fica só aqui.</p></div>' +
    "</div></div></div>";
}

function painelAoVivo() {
  const v = gv.vivo;
  const marcadores = v.marcadores.map((m, i) => '<div class="gv-marcador">' + ic("bookmark", 18) + '<span class="em-ligacao forte">' + duracaoGv(m.t) + "</span>" +
    '<input type="text" value="' + esc(m.texto) + '" placeholder="o que aconteceu aqui" data-gv-marcador-vivo="' + i + '">' +
    '<button class="mais-linha" data-gv-marcador-vivo-tirar="' + i + '" title="Tirar">' + ic("close", 16) + "</button></div>").join("");
  return '<aside class="acervo-painel gv-painel"><div class="rolagem">' +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span class="gv-titulo-ic"><span class="sv-faisca">' + ic("auto_awesome", 16) + '</span>Contexto ao vivo</span><span class="contagem">só nesta máquina</span></div>' +
    '<p class="nota">Quando houver transcrição, o assistente vai cruzar o que está sendo dito com os arquivos do serviço e o Acervo: a cláusula citada, o valor em atraso, o prazo que muda, o que já foi combinado antes. Sem o modelo de voz local, este painel fica assim, sem inventar contexto.</p></div>' +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca">Marcadores<span class="contagem">' + v.marcadores.length + "</span></div>" +
    (marcadores || '<p class="nota">' + (v.estado === "pronto" ? "Durante a gravação, o botão de marcador guarda o minuto — e você escreve o que aconteceu." : "Nenhum marcador ainda. Use o botão de marcador para guardar este minuto.") + "</p>") + "</div>" +
    '<div class="painel-bloco">' + ligaCfg("", "Sugerir respostas enquanto ouço", "com base nos arquivos do serviço e no Acervo · entra com a transcrição", false, true) + "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca">Perguntar ao PAULUS sem parar a gravação</div>' +
    '<textarea class="gv-pergunta" rows="2" placeholder="Pergunte algo sobre o que está sendo dito… (Enter abre a conversa; a gravação continua)" data-gv-pergunta="1"></textarea></div>' +
    "</div></aside>";
}

/* --------------------------------------------------------- gravacao */

function corpoDaGravacao() {
  const g = gv.aberta;
  const player = g.existe
    ? '<div class="gv-player"><audio id="gv-audio" src="/api/gravacoes/' + g.id + '/audio" preload="metadata"></audio>' +
      '<button class="gv-redondo primario" data-gv-tocar="1" title="Tocar">' + ic("play_arrow", 26) + "</button>" +
      '<span class="gv-posicao"><span id="gv-posicao">0:00</span> / ' + duracaoGv(g.duracao_s) + "</span>" +
      '<div class="gv-barra" data-gv-barra="1"><i id="gv-barra-fill"></i>' + g.marcadores.map((m) => '<u style="left:' + porcentagemGv(m.t, g.duracao_s) + '%" title="' + esc(m.texto || duracaoGv(m.t)) + '"></u>').join("") + "</div>" +
      '<button class="botao-icone" data-gv-pular="-10" title="Voltar 10 s">' + ic("replay_10", 20) + "</button>" +
      '<button class="botao-icone" data-gv-pular="10" title="Avançar 10 s">' + ic("forward_10", 20) + "</button>" +
      '<button class="gv-vel" data-gv-velocidade="1" title="Velocidade">' + velocidadeGv() + "</button></div>"
    : '<div class="gv-player"><span class="gv-posicao">— / ' + duracaoGv(g.duracao_s) + '</span><span class="nota-barra">o arquivo de áudio não está mais em ' + esc(gv.pasta) + "</span></div>";
  return '<div class="acervo-principal">' + player + '<div class="gv-conteudo" id="gv-conteudo">' + conteudoDaGravacao() + "</div></div>";
}

function porcentagemGv(t, total) {
  return total ? Math.min(100, Math.max(0, (t / total) * 100)).toFixed(1) : 0;
}

function velocidadeGv() {
  return String(gv.velocidade).replace(".", ",") + "×";
}

function conteudoDaGravacao() {
  const g = gv.aberta;
  if (gv.aba === "marcadores") {
    const linhas = g.marcadores.map((m, i) => '<div class="gv-marcador sv-evento grande">' + ic("bookmark", 18) +
      '<button class="em-ligacao forte" data-gv-ir="' + m.t + '">' + duracaoGv(m.t) + "</button>" +
      '<input type="text" value="' + esc(m.texto) + '" placeholder="o que aconteceu aqui" data-gv-marcador="' + i + '">' +
      '<button class="mais-linha" data-gv-marcador-tirar="' + i + '" title="Tirar">' + ic("close", 16) + "</button></div>").join("");
    return '<div class="tabela-cartao"><div class="tabela-barra"><b>Marcadores</b><span class="nota-barra">' + g.marcadores.length + "</span>" +
      '<div class="direita gv-marcar"><input type="text" placeholder="o que aconteceu neste momento" data-gv-marcar-texto="1" value="' + esc(gv.marcarTexto) + '">' +
      '<button data-gv-marcar="1"' + (g.existe ? "" : " disabled") + ">" + ic("bookmark_add", 16) + 'Marcar em <span id="gv-marcar-em">' + duracaoGv(posicaoDoAudio()) + "</span></button></div></div>" +
      '<div class="tabela-corpo">' + (linhas || '<p class="nota">Nenhum marcador. Toque o áudio e marque os momentos que importam; o minuto fica clicável.</p>') + "</div></div>";
  }
  if (gv.aba === "resumo") return cartaoDoResumoGv(g);
  return cartaoDaTranscricao(g);
}

/* --------------------------------------------- transcricao e resumo */

function statusDaGravacao(g) {
  if (!g.existe) return "áudio não encontrado";
  if (g.transcricao_estado === "transcrevendo") return "transcrevendo · " + Math.round((g.progresso || 0) * 100) + "%";
  if (g.transcricao_estado === "fila") return "na fila para transcrever";
  if (g.transcricao_estado === "pronta") return g.resumo ? "resumo pronto" : "transcrita";
  if (g.transcricao_estado === "erro") return "erro na transcrição";
  return "arquivada · sem transcrição";
}

function notaDaVoz() {
  const v = gv.voz;
  if (v && v.disponivel) return "Áudio, transcrição e resumo ficam nesta máquina · " + v.rotulo;
  return "Áudio fica nesta máquina · baixe o modelo de voz para transcrever aqui";
}

function rotuloDoModeloGv(nome) {
  const partes = String(nome || "").split(" ");
  const m = ((gv.voz || {}).modelos || []).find((x) => x.nome === partes[0]);
  return (m ? m.rotulo : (partes[0] || "Whisper")) + (partes.length > 1 ? " " + partes.slice(1).join(" ") : "");
}

/* Quanto costuma demorar: a medida desta maquina em CPU (turbo ~2,4x o tempo
   real, small ~6x), arredondada para cima porque promessa curta irrita. */
function estimativaGv(segundos) {
  const fator = (gv.voz || {}).modelo === "small" ? 5 : 2;
  const min = Math.max(1, Math.ceil(segundos / fator / 60));
  return min === 1 ? "cerca de 1 minuto" : "uns " + min + " minutos";
}

function realcarGv(texto, termo) {
  if (!termo) return esc(texto);
  const partes = texto.split(new RegExp("(" + termo.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig"));
  return partes.map((p, i) => (i % 2 ? "<mark>" + esc(p) + "</mark>" : esc(p))).join("");
}

function linhasDaTranscricao(g) {
  const termo = gv.buscaTrecho.trim();
  const trechos = termo ? g.trechos.filter((t) => t.texto.toLowerCase().includes(termo.toLowerCase())) : g.trechos;
  return trechos.map((t) => '<div class="gv-trecho"><button class="em-ligacao forte" data-gv-ir="' + Math.floor(t.inicio) + '">' + duracaoGv(t.inicio) + "</button><p>" +
    realcarGv(t.texto, termo) + "</p></div>").join("") || '<p class="nota">Nada com “' + esc(termo) + "” nesta transcrição.</p>";
}

function textoDoProgressoGv(g) {
  if (g.transcricao_estado === "fila") return "na fila" + (g.posicao_na_fila > 1 ? " · posição " + g.posicao_na_fila : " · outra gravação está sendo transcrita");
  return "transcrevendo nesta máquina · " + Math.round((g.progresso || 0) * 100) + "% · " + rotuloDoModeloGv((gv.voz || {}).modelo);
}

function textoDoDownloadGv(v) {
  const m = (v.modelos || []).find((x) => x.nome === v.baixando) || {};
  return "baixando " + (m.rotulo || "o modelo de voz") + " · " + (v.baixado_mb || 0) + " de " + (m.mb || "?") + " MB";
}

/* O que a aba Transcricao mostra depende do estado: sem modelo, baixar; sem
   transcricao, transcrever; na fila ou transcrevendo, o andamento; pronta,
   os trechos com o minuto clicavel e a busca com realce. */
function cartaoDaTranscricao(g) {
  const v = gv.voz || {};
  const cabeca = (meta, direita) => '<div class="fin-cartao-cabeca"><span>Transcrição</span><small>' + esc(meta) + "</small>" +
    (direita ? '<div class="direita">' + direita + "</div>" : "") + "</div>";
  const corpo = (titulo, icone, texto, extra) => '<div class="gv-adiante"><b>' + ic(icone, 18) + esc(titulo) + "</b><p>" + texto + "</p>" + (extra || "") + "</div>";
  if (g.transcricao_estado === "pronta" && g.trechos && g.trechos.length) {
    const meta = "literal · " + duracaoLongaGv(g.duracao_s) + " · " + plural(g.palavras || 0, "palavra") + " · " + rotuloDoModeloGv(g.transcricao_modelo) +
      (g.transcricao_tempo ? " em " + duracaoLongaGv(g.transcricao_tempo) : "");
    return '<div class="fin-cartao gv-transcrita">' + cabeca(meta,
      '<label class="busca-tela gv-busca-trecho">' + ic("search", 18) + '<input type="text" placeholder="Buscar na transcrição…" data-gv-busca-trecho="1" value="' + esc(gv.buscaTrecho) + '"></label>' +
      '<button data-gv-corrigir="1">Corrigir nomes</button>' +
      '<button data-gv-exportar="1">Exportar .docx</button>' +
      '<button data-gv-copiar-transcricao="1">Copiar</button>') +
      '<div class="gv-trechos">' + linhasDaTranscricao(g) + "</div></div>";
  }
  if (!g.existe) {
    return '<div class="fin-cartao">' + cabeca("sem áudio") + corpo("O áudio não está mais no disco", "error",
      "Ele ficava em " + esc(gv.pasta) + ". Sem o arquivo não há o que transcrever.") + "</div>";
  }
  if (g.transcricao_estado === "fila" || g.transcricao_estado === "transcrevendo") {
    return '<div class="fin-cartao">' + cabeca("em andamento") + corpo("Transcrevendo nesta máquina", "graphic_eq",
      "O áudio não sai daqui. Dá para sair desta tela e voltar; a lista mostra o andamento e a transcrição aparece sozinha quando terminar.",
      '<div class="gv-progresso"><i id="gv-progresso" style="width:' + Math.round((g.progresso || 0) * 100) + '%"></i></div>' +
      '<small class="nota" id="gv-progresso-texto">' + esc(textoDoProgressoGv(g)) + "</small>") + "</div>";
  }
  if (g.transcricao_estado === "erro") {
    return '<div class="fin-cartao">' + cabeca("não deu certo") + corpo("A transcrição falhou", "error",
      esc(g.transcricao_erro || "erro desconhecido"),
      '<div class="fin-botoes"><button class="primario com-icone" data-gv-transcrever="1">' + ic("refresh", 16) + "Tentar de novo</button></div>") + "</div>";
  }
  if (v.disponivel) {
    return '<div class="fin-cartao">' + cabeca("ainda não transcrita") + corpo("Transcrever nesta máquina", "graphic_eq",
      "O " + esc(v.rotulo) + " lê o áudio aqui mesmo — nada sai do computador — e devolve o texto literal com o minuto de cada trecho. Para " +
      duracaoLongaGv(g.duracao_s) + " de áudio costuma levar " + estimativaGv(g.duracao_s) + "; roda em segundo plano.",
      '<div class="fin-botoes"><button class="primario com-icone" data-gv-transcrever="1">' + ic("graphic_eq", 16) + "Transcrever nesta máquina</button></div>") + "</div>";
  }
  if (v.baixando) {
    return '<div class="fin-cartao">' + cabeca("baixando o modelo de voz") + corpo("Baixando o modelo de voz", "download",
      "Uma vez só, com internet. Depois disso a transcrição roda aqui, sem mandar o áudio para fora.",
      '<small class="nota" id="gv-baixando-texto">' + esc(textoDoDownloadGv(v)) + "</small>") + "</div>";
  }
  const modelos = (v.modelos || []).map((m) => '<button class="' + (m.nome === v.modelo ? "primario " : "") + 'com-icone" data-gv-baixar-voz="' + m.nome + '">' +
    ic("download", 16) + "Baixar " + esc(m.rotulo) + " (" + esc(String(Math.round(m.mb / 100) / 10).replace(".", ",")) + " GB)</button>").join("");
  const notas = (v.modelos || []).map((m) => "<li><b>" + esc(m.rotulo) + "</b> — " + esc(m.nota) + "</li>").join("");
  return '<div class="fin-cartao">' + cabeca("sem modelo de voz nesta máquina") + corpo("Baixe o modelo de voz para transcrever aqui", "graphic_eq",
    "A transcrição é feita nesta máquina, e para isso o modelo de voz precisa estar baixado nela. É um download só, com internet; depois o áudio nunca sai do computador." +
    (v.erro ? '<br><span class="gv-erro">' + esc(v.erro) + "</span>" : ""),
    '<ul class="sv-falta">' + notas + "</ul>" + '<div class="fin-botoes">' + modelos + "</div>") + "</div>";
}

function cartaoDoResumoGv(g) {
  const transcrita = g.transcricao_estado === "pronta" && g.trechos && g.trechos.length;
  if (g.resumo) {
    return '<div class="fin-cartao gv-transcrita"><div class="fin-cartao-cabeca"><span>Resumo</span><small>escrito ' + esc(quandoCurtoSv(g.resumo_em)) + " · pelo modelo local, sobre a transcrição</small>" +
      '<div class="direita"><button data-gv-copiar-resumo="1">Copiar</button><button class="com-icone" data-gv-resumo="1"' + (gv.resumindo ? " disabled" : "") + ">" + ic("auto_awesome", 16) +
      (gv.resumindo ? "escrevendo…" : "Atualizar resumo") + "</button></div></div>" +
      '<p class="gv-resumo-texto">' + esc(g.resumo) + "</p>" + blocoDePendenciasGv(g) + "</div>";
  }
  const cabeca = '<div class="fin-cartao-cabeca"><span>Resumo</span><small>decisões · pendências · próximos passos</small></div>';
  if (gv.resumindo) {
    return '<div class="fin-cartao">' + cabeca + '<div class="gv-adiante"><b>' + ic("auto_awesome", 18) + "Escrevendo o resumo…</b>" +
      "<p>O modelo local lê a transcrição inteira e escreve resumo, decisões e pendências. Em CPU leva alguns minutos; a tela espera aqui.</p></div></div>";
  }
  if (transcrita) {
    return '<div class="fin-cartao">' + cabeca + '<div class="gv-adiante"><b>' + ic("auto_awesome", 18) + "Pedir o resumo ao modelo local</b>" +
      "<p>Ele lê a transcrição e escreve: do que se tratou, o que foi decidido e o que ficou pendente — só com o que está dito, sem inventar nome, valor ou data. " +
      "Em CPU leva alguns minutos" + (g.palavras > 3000 ? ", e uma gravação longa é resumida em partes" : "") + ".</p>" +
      '<div class="fin-botoes"><button class="primario com-icone" data-gv-resumo="1">' + ic("auto_awesome", 16) + "Pedir resumo</button></div></div></div>";
  }
  return '<div class="fin-cartao">' + cabeca + '<div class="gv-adiante"><b>' + ic("auto_awesome", 18) + "O resumo nasce da transcrição</b>" +
    "<p>Transcreva a gravação primeiro; depois o modelo local escreve o resumo com decisões e pendências. Até lá, as suas notas no painel e os marcadores são o registro.</p>" +
    '<div class="fin-botoes"><button data-gv-aba="transcricao">Ir para a transcrição</button></div></div></div>';
}

/* ------------------------------------------ o que sai da transcricao */
/*
   O que o desenho poe ao lado da transcricao e do resumo: corrigir um nome
   que o modelo de voz errou, levar a transcricao em .docx, mandar o resumo
   por e-mail (que passa por Aprovacoes como qualquer envio) e transformar
   as pendencias do resumo em tarefas ou num compromisso na Agenda.
*/

async function corrigirNomesGv(g) {
  if (!g) return;
  const r = await dialogo({
    titulo: "Corrigir nomes", contexto: "Gravações › " + g.titulo,
    texto: "O modelo de voz erra nome próprio. A troca vale para a transcrição inteira e para o resumo; palavra inteira, sem diferenciar maiúsculas.",
    campos: [
      { chave: "de", rotulo: "Como saiu na transcrição", placeholder: "Priscilla", icone: "search" },
      { chave: "para", rotulo: "Como é", placeholder: "Priscila", icone: "person", sugestoes: g.participantes_lista || [], obrigatorio: true },
    ],
    confirmar: "Corrigir",
  });
  if (!r || !r.ok) return;
  const resp = await fetch("/api/gravacoes/" + g.id + "/corrigir", { method: "POST", headers: GV_JSON, body: JSON.stringify({ de: r.valores.de, para: r.valores.para }) });
  if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
  const d = await resp.json();
  gv.aberta = d;
  if (d.trocados) avisoCert(plural(d.trocados, "trecho") + (d.trocados === 1 ? " corrigido" : " corrigidos"), { tom: "ok" });
  else avisoCert("não achei “" + r.valores.de + "” na transcrição", { tom: "erro" });
  redesenharConteudoGv();
}

function baixarTranscricaoGv(g) {
  if (!g) return;
  const a = document.createElement("a");
  a.href = "/api/gravacoes/" + g.id + "/transcricao.docx";
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

/* O e-mail nasce pronto - destinatario (o e-mail do cliente, se a ficha
   tem), assunto, o resumo no corpo e a transcricao em .docx anexa - e vai
   para a tela de escrever, que manda pela fila de Aprovacoes conforme o
   limite que a pessoa escolheu. */
async function compartilharResumoGv(g) {
  if (!g) return;
  if (!g.trechos || !g.trechos.length) { avisoCert("transcreva a gravação primeiro — o e-mail leva o resumo e a transcrição"); return; }
  if (!g.resumo) {
    const ok = await confirmar({ titulo: "Compartilhar sem resumo?", contexto: "Gravações › " + g.titulo,
      texto: "Ainda não há resumo. O e-mail vai só com a transcrição em anexo; dá para pedir o resumo antes, na aba Resumo.", confirmar: "Compartilhar assim" });
    if (!ok) return;
  }
  const r = await fetch("/api/gravacoes/" + g.id + "/exportar", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const anexo = await r.json();
  let para = "";
  if (g.cadastro_id) {
    try {
      const d = await (await fetch("/api/cadastros?tipo=&termo=&ordem=nome")).json();
      const f = (d.fichas || []).find((x) => x.id === g.cadastro_id);
      if (f && f.email) para = f.email;
    } catch (err) { /* sem e-mail na ficha: a pessoa escreve */ }
  }
  const corpo = "Segue o resumo de “" + g.titulo + "” (" + quandoDaGravacao(g) + ").\n\n" + (g.resumo || "").trim() + "\n\nA transcrição completa vai em anexo.";
  const rascunho = { para: para, cc: "", cco: "", assunto: "Resumo · " + g.titulo, corpo: corpo, anexos: [anexo], quando: new Date().toISOString() };
  // O rascunho fica guardado nesta maquina: se ainda nao ha conta de e-mail,
  // a tela pede a conta e o e-mail continua pronto quando ela existir.
  try { localStorage.setItem("paulus.email.rascunho", JSON.stringify(rascunho)); } catch (err) { /* sem memoria local */ }
  marcarDestino("caixa");
  await telaEscrever(rascunho);
  if (mail.visao === "contas") avisoCert("cadastre uma conta de e-mail primeiro — o e-mail com o resumo fica guardado como rascunho", { tom: "erro" });
  else avisoCert("e-mail pronto para revisar — enviar passa por Aprovações conforme o seu limite", { tom: "ok" });
}

/* As pendencias que o modelo escreveu no resumo ("Pendências:" e uma linha
   por item), para virarem tarefas. A data, quando vem como dd/mm, "hoje",
   "amanhã" ou um dia da semana, vira prazo. */
function pendenciasDoResumo(texto) {
  const itens = [];
  let dentro = false;
  for (const bruta of String(texto || "").split("\n")) {
    const linha = bruta.trim();
    if (!linha) continue;
    if (/^pend[êe]ncias?\b/i.test(linha)) {
      dentro = true;
      const resto = linha.replace(/^pend[êe]ncias?\s*:?\s*/i, "").replace(/^[-•*\d.)\s]+/, "");
      if (resto && !/^nenhuma/i.test(resto)) itens.push(resto);
      continue;
    }
    if (/^(resumo|decis[õo]es|pr[óo]ximos passos|observa[çc][õo]es)\b/i.test(linha)) { if (dentro) break; continue; }
    if (!dentro) continue;
    const item = linha.replace(/^[-•*\d.)\s]+/, "").trim();
    if (item && !/^nenhuma/i.test(item)) itens.push(item);
  }
  return itens.map((t) => ({ texto: t, prazo: prazoNoTexto(t) }));
}

function prazoNoTexto(t) {
  const hoje = new Date();
  const m = /(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?/.exec(t);
  if (m) {
    let ano = m[3] ? Number(m[3]) : hoje.getFullYear();
    if (ano < 100) ano += 2000;
    const d = new Date(ano, Number(m[2]) - 1, Number(m[1]));
    if (!isNaN(d) && d.getMonth() === Number(m[2]) - 1) return iso(d);
  }
  if (/\bhoje\b/i.test(t)) return iso(hoje);
  if (/\bamanh[ãa]\b/i.test(t)) { const d = new Date(hoje); d.setDate(d.getDate() + 1); return iso(d); }
  const dias = ["domingo", "segunda", "ter[çc]a", "quarta", "quinta", "sexta", "s[áa]bado"];
  for (let i = 0; i < 7; i++) {
    if (new RegExp("\\b" + dias[i] + "(-feira)?\\b", "i").test(t)) {
      const d = new Date(hoje);
      let delta = (i - d.getDay() + 7) % 7;
      if (delta === 0) delta = 7;
      d.setDate(d.getDate() + delta);
      return iso(d);
    }
  }
  return "";
}

function blocoDePendenciasGv(g) {
  const itens = pendenciasDoResumo(g.resumo);
  if (!itens.length) return '<div class="gv-pendencias"><p class="nota">O resumo não separou pendências. Se houver, peça um resumo novo — ou anote no painel.</p></div>';
  return '<div class="gv-pendencias"><div class="painel-bloco-cabeca">Pendências<span class="contagem">' + itens.length + "</span></div>" +
    itens.map((p, i) => '<label class="gv-pendencia"><input type="checkbox" data-gv-pendencia="' + i + '" checked><span>' + esc(p.texto) +
      (p.prazo ? ' <small>· prazo ' + esc(dataCurta(p.prazo)) + "</small>" : "") + "</span></label>").join("") +
    '<div class="fin-botoes"><button class="primario com-icone" data-gv-criar-tarefas="1">' + ic("add_task", 16) + "Criar tarefas</button>" +
    '<button class="com-icone" data-gv-agenda="1">' + ic("event_upcoming", 16) + "Levar para a Agenda</button></div></div>";
}

async function criarTarefasDoResumo(g) {
  if (!g) return;
  const itens = pendenciasDoResumo(g.resumo);
  const marcadas = Array.from(document.querySelectorAll("[data-gv-pendencia]")).filter((c) => c.checked).map((c) => itens[Number(c.dataset.gvPendencia)]).filter(Boolean);
  if (!marcadas.length) { avisoCert("marque ao menos uma pendência"); return; }
  let criadas = 0;
  for (const p of marcadas) {
    const r = await fetch("/api/tarefas", { method: "POST", headers: GV_JSON, body: JSON.stringify({ id: null, dados: {
      titulo: p.texto.slice(0, 140), prazo: p.prazo || "", cadastro_id: g.cadastro_id || null,
      anotacao: "Da gravação “" + g.titulo + "” (" + quandoDaGravacao(g) + ").",
    } }) });
    if (r.ok) criadas += 1;
  }
  if (g.servico_id && criadas) {
    fetch("/api/servicos/" + g.servico_id + "/anotacoes", { method: "POST", headers: GV_JSON, body: JSON.stringify({ texto: plural(criadas, "tarefa") + " da gravação “" + g.titulo + "” na Agenda." }) });
  }
  avisoCert(plural(criadas, "tarefa") + (criadas === 1 ? " criada" : " criadas") + " na Agenda", { tom: "ok" });
}

function levarParaAgendaGv(g) {
  if (!g) return;
  const itens = pendenciasDoResumo(g.resumo);
  ag.visao = "semana";
  ag.painel = "form";
  ag.form = Object.assign(compromissoEmBranco("compromisso"), {
    cadastro_id: g.cadastro_id || null, titulo: "Retorno · " + g.titulo,
    anotacao: itens.length ? "Pendências da gravação:\n" + itens.map((p) => "- " + p.texto).join("\n") : "Retorno da gravação “" + g.titulo + "”.",
  });
  marcarDestino("calendario");
  mostrarAgenda("semana");
}

function vigiarVoz() {
  clearTimeout(gv.relogioVoz);
  const v = gv.voz || {};
  const g = gv.aberta;
  const andando = (x) => x && (x.transcricao_estado === "fila" || x.transcricao_estado === "transcrevendo");
  const esperando = (gv.visao === "gravacao" && andando(g)) || (gv.visao === "lista" && gv.lista.some(andando)) || Boolean(v.baixando);
  if (!esperando) return;
  gv.relogioVoz = setTimeout(async () => {
    if (!$("gv-tela")) return;
    try {
      const voz = await (await fetch("/api/voz")).json();
      const baixava = Boolean((gv.voz || {}).baixando);
      gv.voz = voz;
      if (gv.visao === "lista") {
        const d = await (await fetch("/api/gravacoes?termo=" + encodeURIComponent(gv.termo))).json();
        gv.lista = d.gravacoes || [];
        gv.totalSegundos = d.total_segundos || 0;
        desenharGravacoes();
        return;
      }
      if (gv.visao === "gravacao" && g) {
        const r = await fetch("/api/gravacoes/" + g.id);
        if (r.ok) {
          const novo = await r.json();
          const mudou = novo.transcricao_estado !== gv.aberta.transcricao_estado;
          gv.aberta = novo;
          if (mudou) { cabecalhoGravacoes(); redesenharConteudoGv(); redesenharPainelGv(); }
          else {
            const barra = $("gv-progresso");
            if (barra) barra.style.width = Math.round((novo.progresso || 0) * 100) + "%";
            const texto = $("gv-progresso-texto");
            if (texto) texto.textContent = textoDoProgressoGv(novo);
          }
        }
      }
      if (baixava && !voz.baixando) { avisoCert(voz.disponivel ? "modelo de voz baixado — já dá para transcrever" : (voz.erro || "o download parou")); redesenharConteudoGv(); }
      else if (voz.baixando) { const t = $("gv-baixando-texto"); if (t) t.textContent = textoDoDownloadGv(voz); }
    } catch (err) { /* sem servidor neste tique: tenta no proximo */ }
    vigiarVoz();
  }, 2500);
}

async function transcreverGravacao() {
  const g = gv.aberta;
  const r = await fetch("/api/gravacoes/" + g.id + "/transcrever", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  gv.aberta = await r.json();
  cabecalhoGravacoes();
  redesenharConteudoGv();
  vigiarVoz();
}

async function baixarModeloDeVoz(nome) {
  let r = await fetch("/api/voz/modelo", { method: "POST", headers: GV_JSON, body: JSON.stringify({ modelo: nome }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  r = await fetch("/api/voz/baixar", { method: "POST", headers: GV_JSON, body: JSON.stringify({ modelo: nome }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  gv.voz = await r.json();
  avisoCert("baixando o modelo de voz — pode continuar usando o PAULUS; a tela avisa quando terminar");
  redesenharConteudoGv();
  vigiarVoz();
}

async function pedirResumoDaGravacao() {
  if (gv.resumindo) return;
  gv.resumindo = true;
  redesenharConteudoGv();
  redesenharPainelGv();
  const r = await fetch("/api/gravacoes/" + gv.aberta.id + "/resumo", { method: "POST" });
  gv.resumindo = false;
  if (!r.ok) {
    avisoCert("sem resumo agora: " + (await erroDe(r)));
  } else {
    gv.aberta = await r.json();
    cabecalhoGravacoes();
  }
  if ($("gv-tela")) { redesenharConteudoGv(); redesenharPainelGv(); }
}

function painelDaGravacao() {
  const g = gv.aberta;
  const servicos = '<option value="">ligar a um serviço…</option>' + gv.servicos.map((s) => '<option value="' + s.id + '"' + (s.id === g.servico_id ? " selected" : "") + ">" + esc(s.nome) + "</option>").join("");
  const clientes = '<option value="">ligar a um cliente…</option>' + gv.clientes.map((c) => '<option value="' + c.id + '"' + (c.id === g.cadastro_id ? " selected" : "") + ">" + esc(c.nome) + "</option>").join("");
  return '<aside class="acervo-painel gv-painel"><div class="rolagem">' +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span class="gv-titulo-ic"><span class="sv-faisca">' + ic("auto_awesome", 16) + '</span>Resumo da IA</span><span class="contagem">' +
    esc(g.resumo ? "escrito " + quandoCurtoSv(g.resumo_em) : (g.transcricao_estado === "pronta" ? "a pedir" : "depende da transcrição")) + "</span></div>" +
    (g.resumo
      ? '<p class="gv-resumo-curto">' + esc(g.resumo) + '</p><button class="em-ligacao forte" data-gv-aba="resumo">Ver o resumo inteiro</button>'
      : (g.transcricao_estado === "pronta"
        ? '<p class="nota">A transcrição está pronta. O modelo local pode escrever o resumo com decisões e pendências.</p><button class="em-ligacao forte" data-gv-resumo="1"' + (gv.resumindo ? " disabled" : "") + ">" + (gv.resumindo ? "escrevendo…" : "Pedir resumo") + "</button>"
        : '<p class="nota">O resumo nasce da transcrição: transcreva a gravação primeiro (aba Transcrição).</p>')) + "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca">Notas<span class="contagem">' + (g.notas ? "guardadas" : "suas") + "</span></div>" +
    '<textarea class="gv-notas" rows="4" placeholder="O que foi combinado, o que ficou pendente… (guarda ao sair do campo)" data-gv-notas="1">' + esc(g.notas || "") + "</textarea></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca">Arquivado em</div>' +
    '<div class="gv-arquivado">' + ic("inventory_2", 18) + '<div class="duas-linhas"><b>Nesta máquina</b><small>' + esc((g.arquivo || "—") + " · " + g.mb + " MB · " + (g.origem === "importada" ? "importada" : "gravada aqui")) + "</small></div></div>" +
    '<div class="gv-arquivado">' + ic("work", 18) + '<div class="duas-linhas">' +
    (g.servico_nome ? "<b>Serviço: " + esc(g.servico_nome) + '</b><small><button class="em-ligacao" data-gv-abrir-servico="' + g.servico_id + '">abrir a pasta</button> · trilha atualizada</small>' : "") +
    '<select data-gv-ligar="servico_id">' + servicos + "</select></div></div>" +
    '<div class="gv-arquivado">' + ic("person", 18) + '<div class="duas-linhas">' + (g.cliente_nome ? "<b>" + esc(g.cliente_nome) + "</b>" : "") + '<select data-gv-ligar="cadastro_id">' + clientes + "</select></div></div>" +
    '<div class="gv-arquivado">' + ic("description", 18) + '<div class="duas-linhas"><b>Transcrição' + (g.resumo ? " e resumo" : "") + "</b><small>" +
    esc(g.transcricao_estado === "pronta" ? plural(g.palavras || 0, "palavra") + " · " + rotuloDoModeloGv(g.transcricao_modelo) + " · .docx pela aba" : statusDaGravacao(g)) + "</small></div></div>" +
    '<p class="gv-nota-pe">Áudio, transcrição e notas ficam nesta máquina. Compartilhar o resumo monta o e-mail com a transcrição anexa; enviar passa por Aprovações conforme o seu limite.</p></div>' +
    "</div></aside>";
}

function posicaoDoAudio() {
  const a = $("gv-audio");
  return a ? a.currentTime || 0 : 0;
}

/* ------------------------------------------------------------ ligar */

function ligarGravacoes() {
  const clique = (sel, fn) => document.querySelectorAll(sel).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });
  const busca = $("gv-busca");
  if (busca) {
    let t;
    busca.oninput = () => { clearTimeout(t); const v = busca.value; t = setTimeout(() => { gv.termo = v.trim(); mostrarGravacoes("lista"); }, 280); };
  }
  clique("[data-gv-voltar]", () => mostrarGravacoes("lista"));
  clique("[data-gv-nova]", () => { gv.aba = "vivo"; mostrarGravacoes("vivo"); });
  clique("[data-gv-vivo]", () => { gv.aba = "vivo"; mostrarGravacoes("vivo"); });
  clique("[data-gv-tipo]", (b) => { gv.tipo = b.dataset.gvTipo; desenharGravacoes(); });
  clique("[data-gv-abrir]", (b) => abrirGravacao(Number(b.dataset.gvAbrir)));
  ligarLinhasDoTocadorGv();
  ligarTocadorDaListaGv();
  ligarSelecao(document.querySelector("#gv-tela .gv-lista .tabela-corpo"), {
    linhas: ".tabela-linha[data-sel]", escolhidos: gv.escolhidas, aoMudar: desenharGravacoes,
    apagar: (ids) => apagarGravacoesEmLote(ids), renomear: (id) => renomearGravacao(Number(id)),
  });
  clique("[data-gv-sel-limpar]", () => { gv.escolhidas.clear(); desenharGravacoes(); });
  clique("[data-gv-sel-apagar]", () => apagarGravacoesEmLote([...gv.escolhidas]));
  clique("[data-gv-mais]", (b) => menuDaGravacao(b, gv.lista.find((x) => x.id === Number(b.dataset.gvMais))));
  clique("[data-gv-importar]", () => $("gv-importar").click());
  const importar = $("gv-importar");
  if (importar) importar.onchange = () => { if (importar.files[0]) importarAudioGv(importar.files[0]); };
  clique("[data-gv-adiante]", (b) => avisoCert(b.dataset.gvAdiante));
  clique("[data-gv-aba]", (b) => {
    const aba = b.dataset.gvAba;
    if (gv.visao === "vivo") {
      if (aba !== "vivo") {
        avisoCert(aba === "resumo" ? "O resumo é escrito depois, na gravação arquivada — a gravação continua"
          : ((gv.voz || {}).disponivel ? "A transcrição ao vivo está no cartão abaixo do gravador" : "A transcrição precisa do modelo de voz baixado nesta máquina"));
        return;
      }
      return;
    }
    gv.aba = aba;
    cabecalhoGravacoes();
    ligarGravacoes();
    const alvo = $("gv-conteudo");
    if (alvo) { alvo.innerHTML = conteudoDaGravacao(); ligarGravacoes(); }
  });
  // ao vivo
  document.querySelectorAll("[data-gv-form]").forEach((el) => {
    el.oninput = () => { gv.vivo.form[el.dataset.gvForm] = /_id$/.test(el.dataset.gvForm) ? (Number(el.value) || null) : el.value; };
    el.onchange = el.oninput;
  });
  clique("[data-gv-form-tipo]", (b) => { gv.vivo.form.tipo = b.dataset.gvFormTipo; document.querySelectorAll("[data-gv-form-tipo]").forEach((x) => x.classList.toggle("on", x === b)); });
  clique("[data-gv-comecar]", () => comecarGravacao());
  clique("[data-gv-pausar]", () => pausarGravacao());
  clique("[data-gv-parar]", () => pararGravacao());
  clique("[data-gv-marcar-vivo]", () => marcarMomentoAoVivo());
  clique("[data-gv-rolar]", (b) => { gv.vivo.rolar = !gv.vivo.rolar; b.classList.toggle("primario", gv.vivo.rolar); if (gv.vivo.rolar) desenharTrechosAoVivo(); });
  document.querySelectorAll("[data-gv-marcador-vivo]").forEach((el) => { el.oninput = () => { gv.vivo.marcadores[Number(el.dataset.gvMarcadorVivo)].texto = el.value; }; });
  clique("[data-gv-marcador-vivo-tirar]", (b) => { gv.vivo.marcadores.splice(Number(b.dataset.gvMarcadorVivoTirar), 1); redesenharPainelGv(); });
  const pergunta = document.querySelector("[data-gv-pergunta]");
  if (pergunta) pergunta.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); perguntarSemParar(pergunta.value); } };
  // gravacao arquivada
  ligarTocador();
  clique("[data-gv-ir]", (b) => irParaGv(Number(b.dataset.gvIr)));
  clique("[data-gv-marcar]", () => marcarNaGravacao());
  const marcarTexto = document.querySelector("[data-gv-marcar-texto]");
  if (marcarTexto) {
    marcarTexto.oninput = () => { gv.marcarTexto = marcarTexto.value; };
    marcarTexto.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); marcarNaGravacao(); } };
  }
  document.querySelectorAll("[data-gv-marcador]").forEach((el) => {
    el.onchange = () => renomearMarcadorGv(Number(el.dataset.gvMarcador), el.value);
  });
  clique("[data-gv-marcador-tirar]", (b) => tirarMarcadorGv(Number(b.dataset.gvMarcadorTirar)));
  const notas = document.querySelector("[data-gv-notas]");
  if (notas) notas.onblur = () => guardarNotasGv(notas.value);
  document.querySelectorAll("[data-gv-ligar]").forEach((el) => { el.onchange = () => ligarGravacaoA(el.dataset.gvLigar, Number(el.value) || null); });
  clique("[data-gv-abrir-servico]", (b) => abrirServico(Number(b.dataset.gvAbrirServico)));
  clique("[data-gv-perguntar]", () => perguntarSobreGravacao(gv.aberta));
  // transcricao e resumo
  clique("[data-gv-transcrever]", () => transcreverGravacao());
  clique("[data-gv-baixar-voz]", (b) => baixarModeloDeVoz(b.dataset.gvBaixarVoz));
  clique("[data-gv-resumo]", () => pedirResumoDaGravacao());
  clique("[data-gv-copiar-transcricao]", () => copiarTexto(gv.aberta.trechos.map((t) => "[" + duracaoGv(t.inicio) + "] " + t.texto).join("\n"), "transcrição copiada"));
  clique("[data-gv-copiar-resumo]", () => copiarTexto(gv.aberta.resumo || "", "resumo copiado"));
  clique("[data-gv-corrigir]", () => corrigirNomesGv(gv.aberta));
  clique("[data-gv-exportar]", () => baixarTranscricaoGv(gv.aberta));
  clique("[data-gv-compartilhar]", () => compartilharResumoGv(gv.aberta));
  clique("[data-gv-criar-tarefas]", () => criarTarefasDoResumo(gv.aberta));
  clique("[data-gv-agenda]", () => levarParaAgendaGv(gv.aberta));
  const buscaTrecho = document.querySelector("[data-gv-busca-trecho]");
  if (buscaTrecho) buscaTrecho.oninput = () => {
    gv.buscaTrecho = buscaTrecho.value;
    const alvo = document.querySelector("#gv-conteudo .gv-trechos");
    if (alvo) { alvo.innerHTML = linhasDaTranscricao(gv.aberta); ligarGravacoes(); }
  };
}

function redesenharPainelGv() {
  const velho = document.querySelector("#gv-tela .acervo-painel");
  if (!velho) return;
  velho.outerHTML = gv.visao === "vivo" ? painelAoVivo() : painelDaGravacao();
  ligarGravacoes();
}

/* --------------------------------------------------- gravar ao vivo */

async function comecarGravacao() {
  const v = gv.vivo;
  if (v.estado !== "pronto") return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === "undefined") {
    v.erro = "Este navegador não dá acesso ao microfone aqui. Abra o PAULUS na janela do programa ou no Edge.";
    desenharGravacoes();
    return;
  }
  let fluxo;
  try {
    fluxo = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    v.erro = err && err.name === "NotAllowedError"
      ? "O microfone foi negado. Libere o microfone para o PAULUS nas permissões da janela e tente de novo."
      : (err && err.name === "NotFoundError" ? "Nenhum microfone encontrado nesta máquina." : "Não consegui abrir o microfone: " + (err && err.message ? err.message : err));
    desenharGravacoes();
    return;
  }
  const tipos = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  const mime = tipos.find((t) => MediaRecorder.isTypeSupported(t)) || "";
  const gravador = mime ? new MediaRecorder(fluxo, { mimeType: mime }) : new MediaRecorder(fluxo);
  v.pedacos = [];
  v.marcadores = [];
  v.erro = "";
  gravador.ondataavailable = (e) => { if (e.data && e.data.size) v.pedacos.push(e.data); };
  gravador.start(1000);
  v.gravador = gravador;
  v.fluxo = fluxo;
  v.estado = "gravando";
  v.inicio = Date.now();
  v.decorrido = 0;
  clearInterval(v.relogio);
  v.relogio = setInterval(tiquetaqueGv, 500);
  if (!v.form.titulo) v.form.titulo = tituloPadraoGv(v.form);
  comecarTranscricaoAoVivo(fluxo);
  desenharGravacoes();
}

function tiquetaqueGv() {
  const texto = duracaoGv(segundosGravados());
  const el = $("gv-tempo");
  if (el) el.textContent = texto;
  const linha = $("gv-tempo-linha");
  if (linha) linha.textContent = texto;
}

function pausarGravacao() {
  const v = gv.vivo;
  if (!v.gravador) return;
  if (v.estado === "gravando") {
    v.gravador.pause();
    v.decorrido += Date.now() - v.inicio;
    v.estado = "pausada";
  } else if (v.estado === "pausada") {
    v.gravador.resume();
    v.inicio = Date.now();
    v.estado = "gravando";
  }
  desenharGravacoes();
}

function marcarMomentoAoVivo() {
  const v = gv.vivo;
  if (v.estado === "pronto" || v.estado === "salvando") return;
  v.marcadores.push({ t: Math.round(segundosGravados()), texto: "" });
  redesenharPainelGv();
  const campos = document.querySelectorAll("[data-gv-marcador-vivo]");
  const ultimo = campos[campos.length - 1];
  if (ultimo) ultimo.focus();
  const meta = document.querySelector("#gv-tela .gv-gravador .meta");
  if (meta) meta.textContent = (v.form.titulo || tituloPadraoGv(v.form)) + " · " + plural(v.marcadores.length, "marcador", "marcadores") + " · microfone desta máquina";
}

function limparGravacaoAoVivo() {
  const v = gv.vivo;
  clearInterval(v.relogio);
  clearInterval(v.relogioEnvio);
  pararCaptura(v);
  if (v.fluxo) v.fluxo.getTracks().forEach((t) => t.stop());
  Object.assign(v, { estado: "pronto", inicio: 0, decorrido: 0, relogio: null, gravador: null, pedacos: [], fluxo: null, marcadores: [], erro: "",
    form: { titulo: "", tipo: "reuniao", cadastro_id: null, servico_id: null, participantes: "" },
    sessao: "", captura: null, amostras: [], enviando: false, relogioEnvio: null, enviados: 0, transcricao: [], rolar: true, avisoVivo: "" });
}

async function pararGravacao() {
  const v = gv.vivo;
  if (!v.gravador || v.estado === "salvando") return;
  if (v.estado === "gravando") v.decorrido += Date.now() - v.inicio;
  v.estado = "salvando";
  desenharGravacoes();
  const gravador = v.gravador;
  const blob = await new Promise((resolve) => {
    gravador.onstop = () => resolve(new Blob(v.pedacos, { type: gravador.mimeType || "audio/webm" }));
    gravador.stop();
  });
  v.fluxo.getTracks().forEach((t) => t.stop());
  clearInterval(v.relogio);
  const mime = gravador.mimeType || "";
  const extensao = /ogg/.test(mime) ? ".ogg" : (/mp4/.test(mime) ? ".m4a" : ".webm");
  const sessao = await encerrarTranscricaoAoVivo();
  const dados = new FormData();
  dados.append("arquivo", blob, "gravacao" + extensao);
  dados.append("sessao", sessao || "");
  dados.append("titulo", v.form.titulo || tituloPadraoGv(v.form));
  dados.append("tipo", v.form.tipo);
  dados.append("cadastro_id", v.form.cadastro_id ? String(v.form.cadastro_id) : "");
  dados.append("servico_id", v.form.servico_id ? String(v.form.servico_id) : "");
  dados.append("participantes", v.form.participantes);
  dados.append("duracao_s", String(Math.round(v.decorrido / 1000)));
  dados.append("origem", "gravada");
  dados.append("marcadores", JSON.stringify(v.marcadores));
  const r = await fetch("/api/gravacoes", { method: "POST", body: dados });
  if (!r.ok) {
    avisoCert("não consegui guardar o áudio: " + (await erroDe(r)));
    v.estado = "pausada";
    v.gravador = null;
    desenharGravacoes();
    return;
  }
  const g = await r.json();
  limparGravacaoAoVivo();
  avisoCert("gravação arquivada nesta máquina · " + duracaoLongaGv(g.duracao_s));
  gv.aberta = g;
  gv.aba = "transcricao";
  mostrarGravacoes("gravacao");
}

function perguntarSemParar(texto) {
  const v = gv.vivo;
  $("nova").click();
  marcarDestino("conversa");
  const campo = $("pedido");
  if (campo) {
    const dito = v.transcricao.slice(-6).map((t) => t.texto).join(" ").slice(-700);
    campo.value = (v.estado === "pronto" ? "" : "Durante a gravação “" + (v.form.titulo || tituloPadraoGv(v.form)) + "”" +
      (dito ? ", em que acabou de ser dito: “" + dito + "”" : "") + ". ") + (texto || "").trim();
    campo.focus();
    campo.setSelectionRange(campo.value.length, campo.value.length);
  }
  if (v.estado !== "pronto") avisoCert("a gravação continua — volte por Gravações para parar e arquivar");
}

/* ------------------------------------------------------- ao vivo */
/*
   A transcricao enquanto grava. Um AudioWorklet captura o microfone em
   PCM, a cada 2 s o que juntou vai ao servidor (16 kHz, 16 bits), e o
   servidor devolve trechos quando acha uma pausa na fala. O texto entra no
   cartao abaixo do gravador, com o minuto. Ao parar, o que sobrou e
   transcrito e a sessao vai junto com o audio: a gravacao ja nasce
   transcrita.
*/

const GV_CAPTADOR = 'class Captador extends AudioWorkletProcessor { process(entradas) { const canal = entradas[0] && entradas[0][0]; if (canal) this.port.postMessage(canal.slice(0)); return true; } } registerProcessor("paulus-captador", Captador);';

function linhaAoVivo(t) {
  return '<div class="gv-trecho"><span class="em-ligacao forte fixo">' + duracaoGv(t.inicio) + "</span><p>" + esc(t.texto) + "</p></div>";
}

function rodapeAoVivo() {
  const v = gv.vivo;
  if (v.avisoVivo) return '<p class="nota gv-vivo-aviso">' + esc(v.avisoVivo) + "</p>";
  const classe = "gv-ouvindo" + (v.estado === "gravando" && v.sessao ? " viva" : "");
  let texto;
  if (v.estado === "pausada") texto = "pausada — volta a ouvir quando a gravação continuar";
  else if (v.estado === "salvando") texto = "transcrevendo o que sobrou…";
  else if (!v.sessao) texto = "abrindo a sessão de transcrição…";
  else texto = v.transcricao.length ? "ouvindo… o próximo trecho chega na próxima pausa" : "ouvindo… o texto chega a cada pausa na fala, alguns segundos depois";
  return '<div class="' + classe + '"><i class="gv-pulso"></i>' + texto + "</div>";
}

function cartaoAoVivo() {
  const v = gv.vivo;
  const voz = gv.voz || {};
  const cabeca = (meta, direita) => '<div class="fin-cartao-cabeca"><span>Transcrição ao vivo</span><small>' + esc(meta) + "</small>" +
    (direita ? '<div class="direita">' + direita + "</div>" : "") + "</div>";
  if (!voz.disponivel) {
    return '<div class="fin-cartao gv-transcricao">' + cabeca("sem modelo de voz nesta máquina") +
      '<div class="gv-adiante"><b>' + ic("graphic_eq", 18) + "Ainda sem modelo de voz nesta máquina</b>" +
      "<p>A transcrição ao vivo — literal, com o minuto de cada trecho — precisa do modelo de voz baixado aqui, para o áudio não sair do computador. " +
      "O áudio é gravado normalmente e os marcadores guardam os momentos que importam; baixe o modelo pela aba Transcrição de qualquer gravação ou em Configurações.</p></div></div>";
  }
  if (v.estado === "pronto") {
    return '<div class="fin-cartao gv-transcricao">' + cabeca("literal · " + voz.rotulo + " · alguns segundos depois da fala") +
      '<div class="gv-adiante"><b>' + ic("graphic_eq", 18) + "Começa junto com a gravação</b>" +
      "<p>O áudio vai em pedaços para o modelo nesta máquina, que devolve o texto a cada pausa na fala — com o minuto, alguns segundos depois. Nada sai do computador. " +
      "Ao parar e arquivar, a gravação já nasce transcrita. Separar quem disse o quê ainda não existe.</p></div></div>";
  }
  return '<div class="fin-cartao gv-transcricao">' + cabeca("literal · " + voz.rotulo + " · " + plural(v.transcricao.length, "trecho"),
    '<button data-gv-adiante="Corrigir nomes fica para depois de arquivar: na gravação, a troca vale para a transcrição inteira">Corrigir nomes</button>' +
    '<button class="' + (v.rolar ? "primario" : "") + '" data-gv-rolar="1">Rolar junto</button>') +
    '<div class="gv-vivo-trechos" id="gv-vivo-trechos">' + v.transcricao.map(linhaAoVivo).join("") + rodapeAoVivo() + "</div></div>";
}

function desenharTrechosAoVivo() {
  const alvo = $("gv-vivo-trechos");
  if (!alvo) return;
  const v = gv.vivo;
  alvo.innerHTML = v.transcricao.map(linhaAoVivo).join("") + rodapeAoVivo();
  const meta = document.querySelector("#gv-tela .gv-transcricao .fin-cartao-cabeca small");
  if (meta) meta.textContent = "literal · " + ((gv.voz || {}).rotulo || "") + " · " + plural(v.transcricao.length, "trecho");
  if (v.rolar) alvo.scrollTop = alvo.scrollHeight;
}

async function comecarTranscricaoAoVivo(fluxo) {
  const v = gv.vivo;
  v.transcricao = [];
  v.avisoVivo = "";
  v.sessao = "";
  v.amostras = [];
  v.enviados = 0;
  if (!gv.voz || !gv.voz.disponivel) return;
  let r = null;
  try { r = await fetch("/api/voz/ao-vivo", { method: "POST", headers: GV_JSON, body: "{}" }); } catch (err) { r = null; }
  if (!r || !r.ok) {
    v.avisoVivo = "não consegui abrir a transcrição ao vivo" + (r ? ": " + (await erroDe(r)) : " — o servidor não respondeu");
    desenharTrechosAoVivo();
    return;
  }
  const sessao = (await r.json()).sessao;
  if (v.estado === "pronto") { fetch("/api/voz/ao-vivo/" + sessao, { method: "DELETE" }); return; }
  v.sessao = sessao;
  try {
    let ctx;
    try { ctx = new AudioContext({ sampleRate: 16000 }); } catch (err) { ctx = new AudioContext(); }
    const fonte = ctx.createMediaStreamSource(fluxo);
    await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([GV_CAPTADOR], { type: "application/javascript" })));
    const no = new AudioWorkletNode(ctx, "paulus-captador");
    no.port.onmessage = (e) => { if (v.estado === "gravando" && v.sessao) v.amostras.push(e.data); };
    fonte.connect(no);
    no.connect(ctx.destination);
    v.captura = { ctx: ctx, no: no, fonte: fonte };
  } catch (err) {
    v.avisoVivo = "esta janela não deixou capturar o áudio para transcrever (" + (err && err.message ? err.message : err) + "); a gravação continua e a transcrição sai ao arquivar";
    desenharTrechosAoVivo();
    return;
  }
  clearInterval(v.relogioEnvio);
  v.relogioEnvio = setInterval(enviarPedacoAoVivo, 2000);
  desenharTrechosAoVivo();
}

function pcm16De(f32) {
  const out = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const x = Math.max(-1, Math.min(1, f32[i]));
    out[i] = x < 0 ? x * 32768 : x * 32767;
  }
  return out.buffer;
}

/* Quando a janela nao aceita um contexto a 16 kHz, o audio vem na taxa do
   aparelho e e reamostrado aqui, por interpolacao linear: para voz basta. */
function reamostrarGv(f32, de, para) {
  if (de === para) return f32;
  const razao = de / para;
  const n = Math.floor(f32.length / razao);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const p = i * razao;
    const j = Math.floor(p);
    const f = p - j;
    out[i] = f32[j] * (1 - f) + (f32[Math.min(j + 1, f32.length - 1)] || 0) * f;
  }
  return out;
}

async function enviarPedacoAoVivo() {
  const v = gv.vivo;
  if (!v.sessao || v.enviando || !v.amostras.length) return;
  const partes = v.amostras;
  v.amostras = [];
  const total = partes.reduce((s, p) => s + p.length, 0);
  const junto = new Float32Array(total);
  let i = 0;
  partes.forEach((p) => { junto.set(p, i); i += p.length; });
  const taxa = v.captura ? v.captura.ctx.sampleRate : 16000;
  const pcm = pcm16De(reamostrarGv(junto, taxa, 16000));
  v.enviando = true;
  try {
    const r = await fetch("/api/voz/ao-vivo/" + v.sessao + "/audio", { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: pcm });
    if (!r.ok) {
      v.avisoVivo = "a transcrição ao vivo parou: " + (await erroDe(r)) + " — a gravação continua e a transcrição sai ao arquivar";
      clearInterval(v.relogioEnvio);
      desenharTrechosAoVivo();
      return;
    }
    const d = await r.json();
    v.enviados += 1;
    if (d.trechos && d.trechos.length) {
      v.transcricao = v.transcricao.concat(d.trechos);
      desenharTrechosAoVivo();
    }
  } catch (err) {
    v.amostras = partes.concat(v.amostras);
  } finally {
    v.enviando = false;
  }
}

function pararCaptura(v) {
  if (!v.captura) return;
  try { v.captura.no.disconnect(); v.captura.fonte.disconnect(); v.captura.ctx.close(); } catch (err) { /* ja fechado */ }
  v.captura = null;
}

/* A gravacao parou: manda o que sobrou, fecha a sessao e devolve o id para
   ir junto com o audio. */
async function encerrarTranscricaoAoVivo() {
  const v = gv.vivo;
  clearInterval(v.relogioEnvio);
  pararCaptura(v);
  if (!v.sessao) return "";
  while (v.enviando) await new Promise((fim) => setTimeout(fim, 100));
  if (v.amostras.length) await enviarPedacoAoVivo();
  try {
    const r = await fetch("/api/voz/ao-vivo/" + v.sessao + "/fim", { method: "POST" });
    if (r.ok) {
      const d = await r.json();
      if (d.trechos) v.transcricao = d.trechos;
      desenharTrechosAoVivo();
    }
  } catch (err) { /* o servidor ainda guarda a sessao; ela vai junto com o audio */ }
  return v.sessao;
}

/* ------------------------------------------------------- importar */

function duracaoDoArquivoGv(arquivo) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(arquivo);
    const audio = new Audio();
    const fim = (s) => { URL.revokeObjectURL(url); resolve(isFinite(s) ? Math.round(s) : 0); };
    audio.onloadedmetadata = () => fim(audio.duration);
    audio.onerror = () => fim(0);
    setTimeout(() => fim(0), 8000);
    audio.src = url;
  });
}

async function importarAudioGv(arquivo) {
  avisoCert("lendo " + arquivo.name + "…");
  const segundos = await duracaoDoArquivoGv(arquivo);
  const dados = new FormData();
  dados.append("arquivo", arquivo, arquivo.name);
  dados.append("titulo", arquivo.name.replace(/\.[^.]+$/, ""));
  dados.append("tipo", gv.tipo || "reuniao");
  dados.append("duracao_s", String(segundos));
  dados.append("origem", "importada");
  const r = await fetch("/api/gravacoes", { method: "POST", body: dados });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const g = await r.json();
  avisoCert(g.titulo + " importada" + (segundos ? " · " + duracaoLongaGv(segundos) : ""));
  gv.aberta = g;
  mostrarGravacoes("gravacao");
}

/* ---------------------------------------------------------- tocador */

function ligarTocador() {
  const audio = $("gv-audio");
  if (!audio) return;
  const g = gv.aberta;
  const total = () => (isFinite(audio.duration) && audio.duration ? audio.duration : g.duracao_s);
  const botao = document.querySelector("[data-gv-tocar]");
  audio.playbackRate = gv.velocidade;
  const pintar = () => {
    const pos = $("gv-posicao");
    if (pos) pos.textContent = duracaoGv(audio.currentTime);
    const fill = $("gv-barra-fill");
    if (fill) fill.style.width = porcentagemGv(audio.currentTime, total()) + "%";
    const em = $("gv-marcar-em");
    if (em) em.textContent = duracaoGv(audio.currentTime);
  };
  audio.ontimeupdate = pintar;
  audio.onplay = () => { if (botao) botao.innerHTML = ic("pause", 26); };
  audio.onpause = () => { if (botao) botao.innerHTML = ic("play_arrow", 26); };
  audio.onended = () => { if (botao) botao.innerHTML = ic("play_arrow", 26); };
  audio.onerror = () => avisoCert("não consegui tocar o áudio — o formato pode não ser reconhecido por esta janela");
  if (botao) botao.onclick = () => { if (audio.paused) audio.play(); else audio.pause(); };
  document.querySelectorAll("[data-gv-pular]").forEach((b) => {
    b.onclick = () => { audio.currentTime = Math.max(0, Math.min(total(), audio.currentTime + Number(b.dataset.gvPular))); pintar(); };
  });
  const vel = document.querySelector("[data-gv-velocidade]");
  if (vel) vel.onclick = () => {
    const i = GV_VELOCIDADES.indexOf(gv.velocidade);
    gv.velocidade = GV_VELOCIDADES[(i + 1) % GV_VELOCIDADES.length];
    audio.playbackRate = gv.velocidade;
    vel.textContent = velocidadeGv();
  };
  const barra = document.querySelector("[data-gv-barra]");
  if (barra) barra.onclick = (e) => {
    const caixa = barra.getBoundingClientRect();
    const fracao = Math.max(0, Math.min(1, (e.clientX - caixa.left) / caixa.width));
    audio.currentTime = fracao * total();
    pintar();
  };
}

function irParaGv(segundo) {
  const audio = $("gv-audio");
  if (!audio) { avisoCert("o áudio desta gravação não está mais no disco"); return; }
  audio.currentTime = segundo;
  audio.play();
}

async function marcarNaGravacao() {
  const g = gv.aberta;
  const r = await fetch("/api/gravacoes/" + g.id + "/marcadores", { method: "POST", headers: GV_JSON, body: JSON.stringify({ t: Math.round(posicaoDoAudio()), texto: gv.marcarTexto }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  g.marcadores = (await r.json()).marcadores;
  gv.marcarTexto = "";
  redesenharConteudoGv();
}

async function renomearMarcadorGv(i, texto) {
  const g = gv.aberta;
  const m = g.marcadores[i];
  if (!m || m.texto === texto) return;
  // O servidor so tem "por" e "tirar": renomear e tirar e por de novo no mesmo minuto.
  let r = await fetch("/api/gravacoes/" + g.id + "/marcadores/" + i, { method: "DELETE" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  r = await fetch("/api/gravacoes/" + g.id + "/marcadores", { method: "POST", headers: GV_JSON, body: JSON.stringify({ t: m.t, texto: texto }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  g.marcadores = (await r.json()).marcadores;
}

async function tirarMarcadorGv(i) {
  const g = gv.aberta;
  const r = await fetch("/api/gravacoes/" + g.id + "/marcadores/" + i, { method: "DELETE" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  g.marcadores = (await r.json()).marcadores;
  redesenharConteudoGv();
}

function redesenharConteudoGv() {
  const alvo = $("gv-conteudo");
  if (alvo) alvo.innerHTML = conteudoDaGravacao();
  const barra = document.querySelector("[data-gv-barra]");
  if (barra) {
    barra.querySelectorAll("u").forEach((u) => u.remove());
    gv.aberta.marcadores.forEach((m) => {
      const u = document.createElement("u");
      u.style.left = porcentagemGv(m.t, gv.aberta.duracao_s) + "%";
      u.title = m.texto || duracaoGv(m.t);
      barra.appendChild(u);
    });
  }
  ligarGravacoes();
}

async function guardarNotasGv(texto) {
  const g = gv.aberta;
  if (!g || (g.notas || "") === texto) return;
  const r = await fetch("/api/gravacoes/" + g.id, { method: "POST", headers: GV_JSON, body: JSON.stringify({ notas: texto }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  g.notas = texto;
  avisoCert("notas guardadas");
}

async function ligarGravacaoA(campo, valor) {
  const g = gv.aberta;
  const dados = {};
  dados[campo] = valor;
  const r = await fetch("/api/gravacoes/" + g.id, { method: "POST", headers: GV_JSON, body: JSON.stringify(dados) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  gv.aberta = await r.json();
  cabecalhoGravacoes();
  redesenharPainelGv();
}

function apagarGravacoesEmLote(ids) {
  return apagarEmLote(ids, (id) => "/api/gravacoes/" + id, {
    rotulo: "gravação", plural: "gravações", contexto: "Gravações", texto: "O áudio, a transcrição e as notas saem da lista.",
    depois: () => { gv.escolhidas.clear(); mostrarGravacoes("lista"); },
  });
}

async function renomearGravacao(id) {
  const g = gv.lista.find((x) => x.id === id);
  if (!g) return;
  const novo = await perguntar({ titulo: "Renomear gravação", contexto: "Gravações", campo: { rotulo: "Título", valor: g.titulo, icone: "graphic_eq" }, confirmar: "Renomear" });
  if (!novo) return;
  const r = await fetch("/api/gravacoes/" + id, { method: "POST", headers: GV_JSON, body: JSON.stringify({ titulo: novo }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  mostrarGravacoes("lista");
}

function menuDaGravacao(botao, g) {
  if (!g) return;
  menuNaLinha(botao, [
    { rotulo: "Abrir", icone: "graphic_eq", acao: () => abrirGravacao(g.id) },
    { rotulo: "Renomear", icone: "edit", acao: () => renomearGravacao(g.id) },
    { rotulo: "Baixar o áudio", icone: "download", acao: () => baixarAudioGv(g) },
    "-",
    { rotulo: "Apagar", icone: "delete", perigo: true, acao: () => apagarGravacao(g) },
  ]);
}

function baixarAudioGv(g) {
  if (!g.existe) { avisoCert("o áudio não está mais no disco"); return; }
  const a = document.createElement("a");
  a.href = "/api/gravacoes/" + g.id + "/audio";
  a.download = g.arquivo || "gravacao";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function apagarGravacao(g) {
  if (!(await confirmar({ titulo: "Apagar esta gravação?", contexto: "Gravações › " + g.titulo, texto: "O áudio, a transcrição e as notas saem da lista. " + LIXEIRA_TEXTO + " Depois disso o áudio some desta máquina.", confirmar: "Apagar", perigo: true }))) return;
  const r = await fetch("/api/gravacoes/" + g.id, { method: "DELETE" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  if (gv.aberta && gv.aberta.id === g.id) gv.aberta = null;
  mostrarGravacoes("lista");
  avisarLixeira(r, () => mostrarGravacoes("lista"));
}

function perguntarSobreGravacao(g) {
  if (!g) return;
  $("nova").click();
  marcarDestino("conversa");
  const campo = $("pedido");
  if (!campo) return;
  campo.value = "Sobre a gravação “" + g.titulo + "” (" + quandoDaGravacao(g) + (g.servico_nome ? ", serviço " + g.servico_nome : "") + ")" +
    (g.resumo ? ", cujo resumo é: " + g.resumo.trim().slice(0, 1500) : (g.notas ? ", com estas notas: " + g.notas.trim() : "")) + ": ";
  campo.focus();
  campo.setSelectionRange(campo.value.length, campo.value.length);
}

