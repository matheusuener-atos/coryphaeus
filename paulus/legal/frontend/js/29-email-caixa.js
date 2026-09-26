/* ------------------------------------------------------ e-mail: caixa */
/*
   A caixa de entrada numa experiencia so, na largura da tela como o Acervo
   e o Editor. No alto, o cabecalho editorial (a conta, a pasta e uma linha
   do que pede atencao) e o resumo da caixa: o da regra sai na hora, o do
   assistente local vem em segundo plano, cada um com o seu selo. Embaixo, a
   lista no padrao tabela do sistema: a barra com a contagem, as visoes e as
   pastas; selecao multipla (segurar, Ctrl ou Shift+clique, como nas outras
   listas) com marcar como lida e arquivar em lote.

   A mensagem abre no lugar da linha, em modulos: o cabecalho (so o assunto
   em serifa), o que eu entendi e o prazo, os anexos, a mensagem e a
   resposta. A antiga "fila" virou a visao "Pedem resposta" e o "Proxima que
   pede resposta" da mensagem aberta.

   Conta que precisa entrar de novo (senha recusada, sem senha guardada ou
   login do Google/Microsoft vencido) vai para o fluxo da Contas
   (js/28-email-contas.js), nunca para uma caixa quebrada.
*/

const EX_PASTAS = [
  { id: "entrada", rotulo: "Caixa de entrada" },
  { id: "enviados", rotulo: "Enviados" },
  { id: "rascunhos", rotulo: "Rascunhos" },
  { id: "aprovacao", rotulo: "Aguardando aprovação" },
];

/* "Todas" e "Pedem resposta" sao a mesma pagina do servidor (a segunda
   filtra aqui); as outras pedem ao servidor o filtro dele. */
const EX_VISOES = [
  { id: "todas", rotulo: "Todas", filtro: "tudo" },
  { id: "pedem", rotulo: "Pedem resposta", filtro: "tudo" },
  { id: "nao_lidos", rotulo: "Não lidas", filtro: "nao_lidos" },
  { id: "com_anexo", rotulo: "Com anexo", filtro: "com_anexo" },
  { id: "de_clientes", rotulo: "Clientes", filtro: "de_clientes" },
];

const EX_EXTENSO = ["Nenhuma", "Uma", "Duas", "Três", "Quatro", "Cinco", "Seis", "Sete", "Oito", "Nove", "Dez"];

const cx = {
  visao: "todas", escolhidos: new Set(), aberta: null, falhou: null, previas: {},
  resumo: null, resumoPara: null, relogioResumo: null, relogioRegra: null,
  resp: null, respRolar: false, rolarPara: null, chaveTela: "",
};

function exPede(m) { return !m.respondido && (!m.lido || !!m.prazo); }

function exQuem(m) { return m.de_nome || m.de_email || "?"; }

function exPrazoCurto(prazo) { return rotuloDoPrazo(prazo).replace(/^prazo /, ""); }

function exQuantas(n, uma, varias) { return (EX_EXTENSO[n] || n) + " " + (n === 1 ? uma : varias); }

/* O envio sai sozinho so quando a conta e o programa deixam; senao, fila. */
function exSaiSozinho() {
  const c = mail.conta;
  return !!(c && c.pode_enviar_sem_confirmar && mail.contas && mail.contas.pode_enviar_sozinho);
}

function exItens() {
  if (mail.pasta !== "entrada" || !mail.caixa) return [];
  const lista = mail.caixa.mensagens;
  return cx.visao === "pedem" ? lista.filter(exPede) : lista;
}

function exContagemDaPasta(id) {
  if (id === "entrada") return mail.caixa ? mail.caixa.nao_lidos : 0;
  if (id === "rascunhos") return lerRascunhoLocal() ? 1 : 0;
  if (id === "aprovacao") return mail.fila.length;
  return 0;
}

function exJson(url, corpo) {
  return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
}

/* ------------------------------------------------ conta que precisa entrar */

function exPrecisaEntrar(c) {
  if (!c) return false;
  if (c.por_login) return !!(c.precisa_entrar || !c.tem_senha);
  return !!(c.ultimo_erro || !c.tem_senha);
}

/* Leva ao "entrar de novo" da Contas: o login do provedor para a conta de
   login, o passo da senha para a de senha. Dando certo, a Contas abre a
   caixa desta conta. */
async function exEntrarDeNovo(c) {
  if (!c) return mostrarEmail("contas");
  if (c.por_login) {
    await mostrarEmail("contas");
    if (typeof entrarDeNovoOAuth === "function") entrarDeNovoOAuth(c, ecContaLigada);
    return;
  }
  Object.assign(ecEstado(), ecNovo(), { passo: "senha", reconectar: c, email: c.email, abrirDepois: true });
  await mostrarEmail("contas");
  ecFoco();
}

/* O pedido de envio de sempre (mandarPedido). A conta de login nao tem
   senha para perguntar: se o servidor pede para entrar de novo, vai para
   a Contas. */
async function exMandar(pedido) {
  const c = mail.conta;
  if (!c || !c.por_login) return mandarPedido(pedido);
  let r;
  try {
    r = await exJson("/api/email/enviar", pedido);
  } catch (err) { avisoCert(String(err)); return null; }
  if (r.status === 401) { avisoCert(await erroDe(r)); exEntrarDeNovo(c); return null; }
  if (!r.ok) { avisoCert(await erroDe(r)); return null; }
  return r.json();
}

/* Troca de conta pelo seletor do cabecalho. Conta que precisa entrar de
   novo vai para a Contas; as outras abrem a caixa aqui mesmo. */
async function exTrocarConta(c) {
  if (exPrecisaEntrar(c)) return exEntrarDeNovo(c);
  Object.assign(mail, { conta: c, pasta: "entrada", aberta: null, envioAberto: null, pedidoAberto: null, rascunho: null });
  exLimpar();
  await carregarPasta();
  if (mail.visao === "caixa") desenharEmail();
}

function exLimpar() {
  cx.escolhidos.clear();
  cx.aberta = null; cx.falhou = null; cx.resp = null;
  mail.aberta = null;
}

/* -------------------------------------------------- o cabecalho editorial */

function exLide() {
  if (mail.pasta === "enviados") return "O que saiu pelo PAULUS fica anotado aqui; a cópia completa está no seu servidor.";
  if (mail.pasta === "rascunhos") return "O rascunho fica guardado nesta máquina até sair.";
  if (mail.pasta === "aprovacao") return "Os envios que pedem o seu sim esperam aqui. E-mail enviado não volta.";
  if (mail.erroCaixa) return "Não consegui abrir a caixa agora.";
  const k = mail.caixa;
  if (!k) return "Buscando as mensagens no servidor.";
  const pedem = k.mensagens.filter(exPede);
  const urg = k.mensagens.filter((m) => m.prazo && !m.respondido).sort((a, b) => (a.prazo < b.prazo ? -1 : 1))[0];
  return (mail.busca ? "Busca por “" + mail.busca + "”: " + plural(k.mensagens.length, "mensagem", "mensagens") + ". " : "") +
    (pedem.length ? exQuantas(pedem.length, "mensagem pede resposta.", "mensagens pedem resposta.") : "Nada pede resposta nesta página.") +
    (urg ? " O prazo mais perto: " + exPrazoCurto(urg.prazo) + ", " + exQuem(urg) + "." : "");
}

function exAbertura() {
  const c = mail.conta;
  const pasta = EX_PASTAS.find((p) => p.id === mail.pasta) || EX_PASTAS[0];
  const busca = mail.busca ? '<p class="ex-lide">' + esc(exLide()) + ' <button class="sv-ligacao" data-ex-sem-busca="1">limpar a busca</button></p>' : "";
  // A caixa de entrada abre como a pasta de um servico (10-servicos.js): o
  // resumo da IA em cima e a ficha em faixa embaixo - mesmo desenho, mesmas
  // classes. As outras pastas ficam com o titulo e a conta.
  if (mail.pasta === "entrada" && !mail.busca && mail.caixa && mail.caixa.mensagens.length) {
    return '<header class="ex-abre sv-abertura" id="ex-resumo">' + exResumoMiolo() + "</header>";
  }
  return '<header class="ex-abre"><h1 class="ex-titulo">' + esc(pasta.rotulo) + "</h1>" +
    '<div class="ex-conta-casa">' + exBotaoConta(c) + "</div>" + busca + "</header>";
}

function exBotaoConta(c) {
  return '<button class="ex-conta" data-ex-conta="1" title="Trocar de conta">' + avatarDaConta(c) + "<span>" + esc(c.email) + "</span>" + ic("expand_more", 16) + "</button>";
}

/* ------------------------------------------------------- o resumo */
/*
   Dois blocos, cada um dizendo de onde veio. A regra conta o que esta nos
   cabecalhos e sai na hora (mesmo com o assistente desligado). O assistente
   local le so remetente, assunto e marcas - o corpo das mensagens continua
   no servidor - e escreve em segundo plano; a tela nunca espera por ele.
*/

/* O texto do resumo: o do assistente quando pronto; enquanto isso, o
   andamento do jeito de Servicos; sem assistente, diz que valem os numeros
   da ficha, contados por regra. */
function exTextoDoResumo(m) {
  const e = m ? m.estado : "";
  if (e === "pronto") return '<p class="sv-resumo-corpo">' + esc(m.texto) + "</p>";
  if (e === "resumindo" || e === "na_fila") {
    return '<p class="sv-ev-pensando">' + coroa(16) + "<span>lendo remetentes e assuntos… leva cerca de um minuto nesta máquina.</span></p>";
  }
  if (e === "indisponivel") return '<p class="sv-resumo-corpo vazio">O assistente local não está respondendo agora. Os números abaixo são contados por regra, na hora.</p>';
  if (e === "falhou") {
    return '<p class="sv-resumo-corpo vazio">Não consegui resumir: ' + esc(m.erro || "sem resposta") + ". Os números abaixo são contados por regra.</p>";
  }
  return '<p class="sv-ev-pensando">' + coroa(16) + "<span>lendo remetentes e assuntos…</span></p>";
}

function exResumoMiolo() {
  const r = cx.resumo && cx.resumoPara === mail.caixa ? cx.resumo : null;
  const g = r && r.regra;
  const m = r && r.modelo;
  const n = mail.caixa ? mail.caixa.mensagens.length : 0;
  const pronto = m && m.estado === "pronto";
  const hora = pronto ? (m.quando || "").slice(11, 16) : "";
  const andando = m && (m.estado === "resumindo" || m.estado === "na_fila");
  const item = (rotulo, valor) => '<div class="sv-ficha-item"><span class="sv-kicker">' + rotulo + "</span>" + valor + "</div>";
  const prazo = g && g.prazos.length ? g.prazos[0] : null;
  const quem = g && g.remetentes.length ? g.remetentes[0] : null;
  return '<div class="sv-resumo-topo"><div class="sv-resumo-cabeca"><h2>Resumo da IA</h2>' +
    '<small class="sv-resumo-quando">' + (hora ? "escrito às " + esc(hora) + " · " : "") + "leu só remetente e assunto de " + plural(n, "mensagem", "mensagens") + "</small>" +
    '<button type="button" class="sv-ligacao" data-ex-resumo-de-novo="1"' + (andando ? " disabled" : "") + ">" + ic("refresh", 15) + "atualizar resumo</button></div>" +
    exTextoDoResumo(m) + "</div>" +
    '<div class="sv-ficha">' +
    item("Conta", '<div class="ex-conta-casa">' + exBotaoConta(mail.conta) + "</div>") +
    item("Pedem resposta", "<b>" + (g ? g.pedem_resposta + " de " + n : "…") + "</b>") +
    item("Prazo mais perto", prazo
      ? '<button type="button" class="sv-ficha-pasta corta" data-ex-ir="' + esc(prazo.uid) + '" title="' + esc(prazo.assunto) + '">' + esc(dataCurta(prazo.prazo)) + " · " + esc(prazo.assunto) + "</button>"
      : "<b>" + (g ? "nenhum nos assuntos" : "…") + "</b>") +
    item("Quem mais escreveu", '<b class="corta">' + (quem ? esc(quem.nome) + (quem.quantas > 1 ? " · " + quem.quantas : "") : g ? "—" : "…") + "</b>") +
    "</div>";
}

function exCabecalhosParaResumo() {
  return mail.caixa.mensagens.map((m) => ({
    uid: m.uid, de_nome: m.de_nome, de_email: m.de_email, de_cadastro: m.de_cadastro, assunto: m.assunto,
    prazo: m.prazo, lido: m.lido, respondido: m.respondido, tem_anexo: m.tem_anexo,
  }));
}

async function exPedirResumo(deNovo) {
  if (mail.pasta !== "entrada" || !mail.caixa || !mail.conta || mail.busca) return;
  const k = mail.caixa;
  cx.resumoPara = k;
  if (!k.mensagens.length) { cx.resumo = null; return; }
  let d;
  try {
    const r = await exJson("/api/email/caixa/resumo", { conta_id: mail.conta.id, mensagens: exCabecalhosParaResumo(), de_novo: !!deNovo });
    d = r.ok ? await r.json() : { regra: null, modelo: { estado: "falhou", erro: await erroDe(r) } };
  } catch (err) {
    d = { regra: null, modelo: { estado: "falhou", erro: String(err) } };
  }
  if (cx.resumoPara !== k) return;
  cx.resumo = d;
  exPintarResumo();
  exAcompanharResumo();
}

/* A regra acompanha o que muda na lista (abrir, marcar): pede de novo, sem
   pressa. A chave do modelo nao muda por isso - nao roda outra vez. */
function exPedirResumoDepois() {
  clearTimeout(cx.relogioRegra);
  cx.relogioRegra = setTimeout(exPedirResumo, 1200);
}

function exAcompanharResumo() {
  clearTimeout(cx.relogioResumo);
  const r = cx.resumo;
  if (!r || !r.modelo || !r.chave || (r.modelo.estado !== "resumindo" && r.modelo.estado !== "na_fila")) return;
  cx.relogioResumo = setTimeout(async () => {
    if (cx.resumo !== r || mail.visao !== "caixa" || !document.querySelector("#email.ex-tela")) return;
    try {
      const d = await (await fetch("/api/email/caixa/resumo?chave=" + encodeURIComponent(r.chave))).json();
      if (d.modelo && d.modelo.estado !== "nenhum") r.modelo = d.modelo;
    } catch (err) { /* pergunta de novo no proximo giro */ }
    exPintarResumo();
    exAcompanharResumo();
  }, 4000);
}

function exPintarResumo() {
  const alvo = $("ex-resumo");
  if (!alvo) return;
  alvo.innerHTML = exResumoMiolo();
  exLigarResumo(alvo);
}

function exMenuDaConta(b, e) {
  e.stopPropagation();
  menuNaLinha(b, mail.contas.contas.map((c) => ({
    atual: !!(mail.conta && c.id === mail.conta.id),
    rotulo: c.email + (exPrecisaEntrar(c) ? " · entrar de novo" : ""),
    acao: () => exTrocarConta(c),
  })).concat(["-", { rotulo: "Gerenciar contas", acao: () => mostrarEmail("contas") }]));
}

function exLigarResumo(alvo) {
  alvo.querySelectorAll("[data-ex-ir]").forEach((b) => { b.onclick = () => exAbrir(b.dataset.exIr, true); });
  alvo.querySelectorAll("[data-ex-resumo-de-novo]").forEach((b) => { b.onclick = () => { cx.resumo = null; exPintarResumo(); exPedirResumo(true); }; });
  alvo.querySelectorAll("[data-ex-conta]").forEach((b) => { b.onclick = (e) => exMenuDaConta(b, e); });
}

/* --------------------------------------------------------- a lista */

function exAcoesDoLote() {
  return '<button class="com-icone" data-ex-lote="lidas">' + ic("done_all", 16) + "Marcar como lidas</button>" +
    '<button class="com-icone" data-ex-lote="nao-lidas">' + ic("mark_email_unread", 16) + "Como não lidas</button>" +
    '<button class="com-icone" data-ex-lote="arquivar">' + ic("archive", 16) + "Arquivar</button>" +
    '<span class="divisa-v"></span><button class="botao-icone perigo" data-ex-lote="excluir" title="Excluir" aria-label="Excluir">' + ic("delete", 18) + "</button>";
}

function exContagem() {
  if (mail.pasta === "enviados") return plural(mail.envios.length, "envio");
  if (mail.pasta === "rascunhos") return lerRascunhoLocal() ? "1 rascunho" : "Nenhum rascunho";
  if (mail.pasta === "aprovacao") return plural(mail.fila.length, "pedido") + " esperando";
  if (!mail.caixa) return mail.erroCaixa ? "A caixa não abriu" : "Abrindo…";
  const itens = exItens();
  return plural(itens.length, "mensagem", "mensagens") + (mail.caixa.nao_lidos ? '<span class="ex-conta-nao-lidas">' + plural(mail.caixa.nao_lidos, "não lida") + "</span>" : "");
}

function exBarra() {
  const n = cx.escolhidos.size;
  const naEntrada = mail.pasta === "entrada";
  // A mesma barra da lista de conversas do assistente.
  if (n && naEntrada) return '<span class="lc-selecao">' + barraDeSelecao(n, true, exAcoesDoLote(), "data-ex-sel-limpar", exItens().length) + "</span>";
  const pedem = mail.caixa ? mail.caixa.mensagens.filter(exPede).length : 0;
  const visoes = naEntrada && !mail.erroCaixa
    ? '<div class="visoes ex-visoes">' + EX_VISOES.map((v) => '<button class="' + (v.id === cx.visao ? "ativa" : "") + '" data-ex-visao="' + v.id + '">' + v.rotulo +
        (v.id === "pedem" && pedem ? '<span class="ex-visao-conta">' + pedem + "</span>" : "") + "</button>").join("") + "</div>"
    : (naEntrada ? "" : '<button class="com-icone" data-ex-pasta="entrada">' + ic("arrow_back", 16) + "Caixa de entrada</button>");
  const pastas = '<button class="com-icone ex-pastas-botao" data-ex-pastas="1">' + ic("folder_open", 16) + "Pastas" + ic("expand_more", 16) + "</button>";
  return '<span class="selecao">' + exContagem() + "</span>" + '<div class="direita">' + visoes + pastas + "</div>";
}

function exVazio(titulo, texto, acao) {
  return '<div class="ex-vazio"><h4>' + titulo + "</h4><p>" + texto + "</p>" + (acao || "") + "</div>";
}

/* Os botoes de quando a caixa nao abre: tentar outra vez, a Contas ou
   entrar de novo. */
function exBotoesDoErro() {
  return '<div class="ex-vazio-acoes"><button data-ex-tentar="1">Tentar de novo</button><button data-em-visao="contas">Abrir contas</button>' +
    (mail.conta ? '<button class="primario" data-ex-entrar="1">Entrar de novo</button>' : "") + "</div>";
}

function exMarcas(m) {
  const marcas = [];
  if (m.sinalizada) marcas.push('<span class="ex-marca-ic ex-marca-estrela" title="Com estrela">' + ic("star", 16) + "</span>");
  if (m.prazo && !m.respondido) marcas.push('<span class="em-pilula acc" title="Prazo achado no assunto">' + esc(rotuloDoPrazo(m.prazo)) + "</span>");
  if (m.de_cadastro) marcas.push('<span class="em-pilula" title="' + esc(m.de_cadastro) + '">cliente</span>');
  if (m.tem_anexo) marcas.push('<span class="ex-marca-ic" title="Com anexo">' + ic("attach_file", 16) + "</span>");
  if (m.respondido) marcas.push('<span class="ex-marca-ic" title="Respondida">' + ic("reply", 16) + "</span>");
  return marcas.join("");
}

/* A linha: remetente, assunto (e o comeco do texto, quando ja foi aberta
   nesta sessao - a lista so tem cabecalho), as marcas e a data. */
function exLinha(m) {
  const on = cx.escolhidos.has(m.uid);
  const aberta = cx.aberta === m.uid;
  const trecho = cx.previas[m.uid];
  const classe = "tabela-linha ex-linha" + (m.lido ? "" : " nova") + (on ? " escolhida" : "") + (aberta ? " aberta" : "");
  return '<div class="' + classe + '" data-ex-uid="' + esc(m.uid) + '" aria-expanded="' + aberta + '">' +
    '<span class="ex-de"><i class="ex-ponto"></i><span class="corta">' + esc(exQuem(m)) + "</span></span>" +
    '<span class="ex-sobre"><b>' + esc(m.assunto || "(sem assunto)") + "</b>" + (trecho ? '<span class="ex-trecho">' + esc(trecho) + "</span>" : "") + "</span>" +
    '<span class="ex-marcas">' + exMarcas(m) + "</span>" +
    '<span class="ex-quando">' + esc(m.quando_curto || "") + "</span>" +
    '<button class="mais-linha" data-ex-mais="' + esc(m.uid) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button></div>" +
    (aberta ? exMensagem(m) : "");
}

function exLinhaSimples(attr, aberta, quem, sobre, marcas, quando) {
  return '<div class="tabela-linha ex-linha' + (aberta ? " aberta" : "") + '" ' + attr + ">" +
    '<span class="ex-de"><span class="corta">' + esc(quem) + "</span></span>" +
    '<span class="ex-sobre"><b>' + esc(sobre || "(sem assunto)") + "</b></span>" +
    '<span class="ex-marcas">' + (marcas || "") + '</span><span class="ex-quando">' + esc(quando || "") + "</span><span></span></div>";
}

function exCorpoDaLista() {
  if (mail.pasta === "entrada") {
    if (mail.erroCaixa) return exVazio("Não consegui abrir a caixa", "O servidor respondeu: " + esc(mail.erroCaixa), exBotoesDoErro());
    if (!mail.caixa) return esqueleto("lista");
    const itens = exItens();
    if (!itens.length) {
      return cx.visao === "pedem"
        ? exVazio("Nada pede resposta", "Nenhuma mensagem desta página está sem ler ou com prazo esperando você.", '<div class="ex-vazio-acoes"><button data-ex-visao="todas">Ver todas</button></div>')
        : exVazio(mail.busca ? "Nada com “" + esc(mail.busca) + "”" : "Nada aqui", mail.busca ? "Procurei no assunto e no remetente." : "Nenhuma mensagem com esse filtro.");
    }
    return itens.map(exLinha).join("");
  }
  if (mail.pasta === "enviados") {
    return mail.envios.length
      ? mail.envios.map((e, i) => exLinhaSimples('data-ex-envio="' + i + '"', mail.envioAberto === i, (e.para || []).join(", ") || "—", e.assunto,
          (e.anexos || []).length ? '<span class="ex-marca-ic" title="Com anexo">' + ic("attach_file", 16) + "</span>" : "", quandoCurto(e.quando)) +
          (mail.envioAberto === i ? exEnvioAberto(e) : "")).join("")
      : exVazio("Nada enviado daqui", "O que sair pelo PAULUS fica anotado aqui.");
  }
  if (mail.pasta === "rascunhos") {
    const r = lerRascunhoLocal();
    return r ? exLinhaSimples('data-ex-rascunho="1"', false, r.para || "sem destinatário", r.assunto, '<span class="em-pilula">nesta máquina</span>', quandoCurto(r.quando))
      : exVazio("Nenhum rascunho", "O que você começa a escrever fica guardado aqui até sair.");
  }
  return mail.fila.length
    ? mail.fila.map((p) => exLinhaSimples('data-ex-pedido="' + esc(p.id) + '"', mail.pedidoAberto === p.id, p.titulo, p.resumo,
        '<span class="em-pilula acc">esperando você</span>', quandoCurto(p.criado_em)) + (mail.pedidoAberto === p.id ? exPedidoAberto(p) : "")).join("")
    : exVazio("Nada esperando", "Nenhum envio esperando o seu sim agora.");
}

function exRodape() {
  if (mail.pasta !== "entrada" || !mail.caixa) return "";
  const k = mail.caixa;
  return '<div class="tabela-rodape"><span>' + k.mostrando + " de " + k.total + "</span>" +
    (k.tem_mais ? '<button class="mais" id="mail-mais">Carregar mais</button>' : "") +
    '<span class="cresce"></span><span>As mensagens ficam no seu servidor · eu leio só o que você abre</span></div>';
}

function exTabela() {
  return '<div class="tabela-cartao ex-lista"><div class="tabela-barra ex-barra">' + exBarra() + "</div>" +
    '<div class="tabela-corpo" id="ex-corpo">' + exCorpoDaLista() + "</div>" + exRodape() + "</div>";
}

/* ---------------------------------------------- a mensagem, em modulos */

function exDataInteira(iso, curto) {
  const d = iso ? new Date(iso) : null;
  if (!d || isNaN(d)) return curto || "";
  return d.toLocaleString("pt-BR", { weekday: "short", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function exEntendi(m) {
  return esc(exQuem(m)) + (m.de_cadastro && m.de_cadastro !== m.de_nome ? ", de " + esc(m.de_cadastro) + " (do cadastro)," : "") +
    " escreveu sobre “" + esc(m.assunto || "sem assunto") + "”." +
    (m.prazo ? " O texto fala de prazo." : " Não achei prazo no texto.") +
    (m.anexos && m.anexos.length ? " Vem com " + plural(m.anexos.length, "anexo") + "." : "") + (m.respondido ? " Você já respondeu." : "");
}

function exModulo(rotulo, miolo, classe, nota) {
  // Sem rotulo, o modulo ocupa a largura toda (o texto da mensagem).
  if (!rotulo) return '<section class="ex-mod sem-rotulo' + (classe ? " " + classe : "") + '"><div class="ex-mod-miolo">' + miolo + "</div></section>";
  return '<section class="ex-mod' + (classe ? " " + classe : "") + '"><span class="ex-mod-rotulo">' + rotulo + (nota ? "<small>" + nota + "</small>" : "") + "</span>" +
    '<div class="ex-mod-miolo">' + miolo + "</div></section>";
}

function exIcones(m) {
  return '<span class="em-msg-acoes ex-msg-acoes">' +
    (m && m.corpo !== undefined && exLingua(m)
      ? '<button data-ex-traduzir="1"' + (cx.tradVista === m.uid ? ' class="ativo"' : "") + ' title="Traduzir para o português" aria-label="Traduzir para o português">' + icTraduzir(15) + "</button>" : "") +
    (m ? '<button data-ex-imprimir="1" title="Imprimir" aria-label="Imprimir">' + ic("print", 18) + "</button>" +
      '<button data-ex-nao-lida="1" title="Marcar como não lida" aria-label="Marcar como não lida">' + ic("mark_email_unread", 18) + "</button>" +
      '<button id="mail-arquivar" title="Arquivar" aria-label="Arquivar">' + ic("archive", 18) + "</button>" +
      '<button data-ex-excluir="1" title="Excluir" aria-label="Excluir">' + ic("delete", 18) + "</button>" +
      '<button id="mail-mais-msg" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + '</button><span class="divisa-v"></span>' : "") +
    '<button data-ex-fechar="1" title="Fechar (Esc)" aria-label="Fechar">' + ic("close", 18) + "</button></span>";
}

/* "há 5 min", "há 3 h" - so para o que chegou ha menos de um dia. */
function exHa(iso) {
  const d = iso ? new Date(iso) : null;
  if (!d || isNaN(d)) return "";
  const min = Math.round((Date.now() - d.getTime()) / 60000);
  if (min < 0 || min >= 24 * 60) return "";
  if (min < 1) return "agora";
  return min < 60 ? "há " + min + " min" : "há " + Math.floor(min / 60) + " h";
}

/* O cabecalho da mensagem aberta, no desenho do Gmail: assunto com a
   etiqueta da pasta; o remetente com o avatar, "para mim" que abre os
   detalhes, a hora com o "ha quanto tempo", a estrela e o responder. */
function exCabecaMsg(item, m) {
  const c = mail.conta;
  const eu = c ? c.email.toLowerCase() : "";
  const pasta = (EX_PASTAS.find((p) => p.id === mail.pasta) || EX_PASTAS[0]).rotulo;
  const nome = item.de_nome || item.de_email;
  const para = m ? exEnderecos(m.para) : [];
  const copia = m ? exEnderecos(m.cc) : [];
  const outros = para.concat(copia).filter((e) => e !== eu).length;
  const paraQuem = !m || !para.length || para.includes(eu) ? "para mim" : "para " + para[0];
  const mais = outros && paraQuem === "para mim" ? " e mais " + outros : outros > 1 ? " e mais " + (outros - 1) : "";
  const quando = m ? m.quando : item.quando;
  const ha = exHa(quando);
  const aberto = cx.detalhes === item.uid;
  const linha = (rotulo, valor) => (valor ? "<div><dt>" + rotulo + "</dt><dd>" + valor + "</dd></div>" : "");
  const detalhes = aberto
    ? '<dl class="ex-meta ex-detalhes">' +
      linha("De", esc(nome) + (item.de_nome ? ' <span class="ex-meta-email">&lt;' + esc(item.de_email) + "&gt;</span>" : "")) +
      linha("Para", esc(m && m.para ? m.para : (c ? c.email : ""))) +
      linha("Cc", m && m.cc ? esc(m.cc) : "") +
      linha("Data", esc(exDataInteira(quando, item.quando_curto))) +
      linha("Assunto", esc(item.assunto || "(sem assunto)")) +
      linha("Recebida em", esc(c ? c.email : "")) + "</dl>"
    : "";
  return '<header class="ex-mod ex-mod-cabeca"><div class="ex-cabeca-linha"><h2 class="ex-assunto">' + esc(item.assunto || "(sem assunto)") +
    ' <span class="ex-etiqueta">' + esc(pasta) + "</span></h2>" + exIcones(m) + "</div>" +
    '<div class="ex-remetente"><span class="ex-avatar" aria-hidden="true">' + esc(iniciaisDoRemetente(nome)) + "</span>" +
    '<div class="ex-rem-texto"><div class="ex-rem-nome"><b>' + esc(nome) + "</b>" +
    (item.de_nome ? ' <span class="ex-meta-email">&lt;' + esc(item.de_email) + "&gt;</span>" : "") +
    (item.de_cadastro ? ' <span class="em-pilula">cliente · ' + esc(item.de_cadastro) + "</span>" : "") + "</div>" +
    '<button class="ex-para-mim" data-ex-detalhes="' + esc(item.uid) + '" aria-expanded="' + aberto + '">' + esc(paraQuem + mais) +
    '<i class="ex-seta" aria-hidden="true"></i></button></div>' +
    '<div class="ex-rem-dir"><span class="ex-rem-quando" title="' + esc(exDataInteira(quando, item.quando_curto)) + '">' +
    esc(exDataCurta(quando, item.quando_curto)) + (ha ? " (" + ha + ")" : "") + "</span>" +
    '<button class="ex-estrela' + (item.sinalizada ? " on" : "") + '" data-ex-estrela="' + esc(item.uid) + '" title="' + (item.sinalizada ? "Tirar a estrela" : "Pôr estrela") +
    '" aria-label="Estrela" aria-pressed="' + !!item.sinalizada + '">' + ic(item.sinalizada ? "star" : "star_outline", 18) + "</button>" +
    (m ? '<button class="ex-rem-botao" id="ex-responder-rapido" title="Responder" aria-label="Responder">' + ic("reply", 18) + "</button>" : "") +
    "</div></div>" + detalhes + "</header>";
}

/* "26 de set., 00:48" - a data do cabecalho, sem o ano quando e deste ano. */
function exDataCurta(iso, curto) {
  const d = iso ? new Date(iso) : null;
  if (!d || isNaN(d)) return curto || "";
  const esteAno = d.getFullYear() === new Date().getFullYear();
  return d.toLocaleString("pt-BR", Object.assign({ day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }, esteAno ? {} : { year: "numeric" }));
}

/* O codigo de verificacao (GitHub, banco, gov.br...): um numero de 4 a 8
   digitos, ou letras e numeros misturados, perto de "codigo", "code",
   "verificacao"... Por regra; se a regra nao tiver certeza, nao mostra. */
const EX_GATILHO_CODIGO = /(c[oó]digo|code|verifica|autentica|authenticat|confirma|one[- ]time|otp\b|\bpin\b|token|senha tempor|passcode|security)/i;

function exCodigo(m) {
  const texto = ((m.assunto || "") + "\n" + (m.corpo || "")).slice(0, 8000);
  if (!EX_GATILHO_CODIGO.test(texto)) return "";
  const candidato = /(?<![\w@./:#-])(\d{3}[ -]\d{3}|\d{4,8}|[A-Z0-9]{6,8})(?![\w@/:-]|\.\d)/g;
  let achado;
  while ((achado = candidato.exec(texto))) {
    const bruto = achado[1];
    const limpo = bruto.replace(/[ -]/g, "");
    if (/^[A-Z0-9]+$/.test(limpo) && !(/\d/.test(limpo) && (/^\d+$/.test(limpo) || /[A-Z]/.test(limpo)))) continue;
    if (/^(19|20)\d\d$/.test(limpo)) continue;
    const antes = texto.slice(Math.max(0, achado.index - 160), achado.index);
    const depois = texto.slice(achado.index + bruto.length, achado.index + bruto.length + 60);
    if (EX_GATILHO_CODIGO.test(antes) || EX_GATILHO_CODIGO.test(depois)) return limpo;
  }
  return "";
}

/* Em que lingua a mensagem esta, por contagem de palavras comuns. So diz
   quando a diferenca e clara; na duvida, portugues (sem oferecer nada). */
const EX_PALAVRAS = {
  pt: ["de", "que", "não", "para", "com", "uma", "você", "está", "por", "os", "das", "dos", "é", "ao", "seu", "sua", "obrigado", "olá", "mais", "como"],
  en: ["the", "and", "you", "your", "to", "of", "is", "this", "for", "with", "are", "that", "will", "be", "on", "we", "our", "have", "please", "here"],
  es: ["el", "los", "las", "usted", "con", "una", "es", "su", "está", "gracias", "hola", "para", "por", "del", "que", "nuestro", "aquí", "correo"],
};
const EX_LINGUA = { en: "inglês", es: "espanhol" };

function exLingua(m) {
  const palavras = ((m.assunto || "") + " " + (m.corpo || "")).slice(0, 5000).toLowerCase().match(/[a-zà-úñ]+/g) || [];
  const conta = {};
  Object.keys(EX_PALAVRAS).forEach((l) => {
    const conj = new Set(EX_PALAVRAS[l]);
    conta[l] = palavras.filter((p) => conj.has(p)).length;
  });
  const fora = conta.en >= conta.es ? "en" : "es";
  return conta[fora] >= 5 && conta[fora] > conta.pt * 2 ? fora : "";
}

/* O "traduzir" nao existe entre os icones da fonte: vai desenhado. */
function icTraduzir(tamanho) {
  const t = tamanho || 18;
  // Sem a classe .ic: ela forca 22 px de caixa e o desenho, que ocupa o
  // quadro todo, ficava maior que os icones da fonte.
  return '<svg class="ic-svg" width="' + t + '" height="' + t + '" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12.87 15.07l-2.54-2.51.03-.03A17.5 17.5 0 0 0 14.07 6H17V4h-7V2H8v2H1v2h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zM18.5 10h-2L12 22h2l1.12-3h4.75L21 22h2l-4.5-12zm-2.62 7l1.62-4.33L19.12 17h-3.24z"/></svg>';
}

async function exTraduzir(m) {
  cx.trad = cx.trad || {};
  cx.tradVista = m.uid;
  const t = cx.trad[m.uid];
  if (t && t.estado !== "erro") { cx.tradAnimar = m.uid; exTrocarCorpo(m); return; }
  cx.trad[m.uid] = { estado: "andando" };
  exTrocarCorpo(m);
  let r;
  try { r = await exJson("/api/email/traduzir", { texto: m.corpo || "", html: m.html || "" }); } catch (err) { r = null; }
  if (!r || !r.ok) {
    const erro = r ? await erroDe(r) : "não consegui falar com o tradutor";
    cx.trad[m.uid] = { estado: "erro" };
    if (cx.tradVista === m.uid) cx.tradVista = null;
    exTrocarCorpo(m);
    avisoCert("tradução não saiu: " + erro, { tom: "erro" });
    return;
  }
  const d = await r.json();
  cx.trad[m.uid] = { estado: "pronta", texto: d.texto, html: d.html };
  cx.tradAnimar = m.uid;
  exTrocarCorpo(m);
}

/* Imprimir a mensagem: uma folha limpa (assunto, de, para, data e o texto,
   sem a tela em volta) num quadro escondido, e a janela de impressao do
   navegador. O modal de impressao do PAULUS (28-imprimir.js) trabalha sobre
   o PDF de um documento - e-mail nao tem PDF. O quadro nao roda script (a
   CSP e a mesma do quadro de leitura); so a folha e impressa. */
function exImprimir(m) {
  const c = mail.conta;
  const t = (cx.trad || {})[m.uid];
  const traduzida = !!(t && t.estado === "pronta" && cx.tradVista === m.uid);
  const html = traduzida ? t.html : m.html;
  const texto = traduzida ? t.texto : m.corpo;
  const linha = (r, v) => (v ? "<tr><th>" + r + "</th><td>" + esc(v) + "</td></tr>" : "");
  const corpo = html
    ? html.replace(/<\/?(html|body|head)\b[^>]*>/gi, "")
    : '<div style="white-space:pre-wrap">' + esc(texto || "") + "</div>";
  const folha = '<!doctype html><html><head><meta charset="utf-8">' +
    '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:' + (exImagensLiberadas(m.uid) ? " https: http:" : "") + "; style-src 'unsafe-inline'\">" +
    "<title>" + esc(m.assunto || "Mensagem") + "</title><style>" +
    "body{margin:0;padding:28px 36px;font:13px/1.5 Arial,Helvetica,sans-serif;color:#111;background:#fff}" +
    "h1{font:600 18px/1.3 Arial,Helvetica,sans-serif;margin:0 0 12px}" +
    ".cabeca{border-collapse:collapse;margin:0 0 18px;font-size:12px}.cabeca th{text-align:left;padding:2px 16px 2px 0;color:#555;font-weight:600}" +
    "hr{border:0;border-top:1px solid #ccc;margin:0 0 18px}img{max-width:100%;height:auto}" +
    "@page{margin:14mm}</style></head><body>" +
    "<h1>" + esc(m.assunto || "(sem assunto)") + "</h1>" +
    '<table class="cabeca">' + linha("De", (m.de_nome ? m.de_nome + " <" + m.de_email + ">" : m.de_email)) +
    linha("Para", m.para || (c ? c.email : "")) + linha("Cc", m.cc) + linha("Data", exDataInteira(m.quando, m.quando_curto)) +
    (traduzida ? linha("Obs.", "Tradução feita nesta máquina; na dúvida, vale o original.") : "") + "</table>" +
    "<hr>" + corpo + "</body></html>";
  const velho = document.getElementById("ex-folha-impressao");
  if (velho) velho.remove();
  const quadro = document.createElement("iframe");
  quadro.id = "ex-folha-impressao";
  quadro.className = "ex-folha-impressao";
  quadro.setAttribute("sandbox", "allow-same-origin allow-modals");
  quadro.setAttribute("aria-hidden", "true");
  quadro.onload = () => {
    try { quadro.contentWindow.focus(); quadro.contentWindow.print(); }
    catch (err) { avisoCert("não consegui abrir a impressão", { tom: "erro" }); }
  };
  quadro.srcdoc = folha;
  document.body.appendChild(quadro);
}

/* Troca so o modulo do texto da mensagem aberta (traducao, original,
   formatado), sem redesenhar a lista. */
function exTrocarCorpo(m) {
  if (!mail.aberta || mail.aberta.uid !== m.uid || typeof cx.trocarCorpo !== "function") return;
  cx.trocarCorpo();
}

/* O "Contexto IA": o assistente local le a mensagem aberta e diz em duas
   ou tres frases do que se trata. Leva cerca de um minuto; enquanto isso
   (ou sem o assistente) fica a frase por regra. */
function exTextoDoContexto(m) {
  const k = (cx.contexto || {})[m.uid];
  const e = k ? k.estado : "";
  if (e === "pronto" && k.texto) return '<p class="ex-mod-texto">' + esc(k.texto) + "</p>";
  const regra = '<p class="ex-mod-texto">' + exEntendi(m) + "</p>";
  if (e === "resumindo" || e === "na_fila" || !e) {
    return regra + '<p class="sv-ev-pensando">' + coroa(14) + "<span>lendo a mensagem… cerca de um minuto nesta máquina</span></p>";
  }
  if (e === "indisponivel") return regra + '<p class="ex-contexto-nota">O assistente local não está respondendo agora; a frase acima é por regra.</p>';
  return regra + '<p class="ex-contexto-nota">Não consegui o contexto: ' + esc(k.erro || "sem resposta") +
    '. <button class="sv-ligacao" data-ex-contexto-de-novo="1">tentar de novo</button></p>';
}

function exModEntendi(m) {
  const codigo = exCodigo(m);
  const blocoCodigo = codigo
    ? '<div class="ex-codigo"><span class="duas-linhas"><small>Código de verificação</small><b>' + esc(codigo) + "</b></span>" +
      '<button class="com-icone" data-ex-copiar-codigo="' + esc(codigo) + '">' + ic("content_copy", 16) + "Copiar código</button></div>"
    : "";
  const prazo = m.prazo
    ? '<div class="ex-prazo"><span class="ex-prazo-data"><b>' + esc(m.prazo.slice(8, 10)) + "</b><small>" + esc(dataCurta(m.prazo).split(" ").pop()) + "</small></span>" +
      '<span class="duas-linhas"><b>Prazo detectado · ' + esc(dataLonga(m.prazo)) + "</b>" + (m.prazo_trecho ? "<small>“" + esc(m.prazo_trecho) + "”</small>" : "") + "</span>" +
      '<span class="ex-prazo-acoes"><button class="com-icone" data-em-prazo="agenda">' + ic("event_upcoming", 16) + "Criar na Agenda</button>" +
      '<button class="com-icone" data-em-prazo="tarefa">' + ic("add_task", 16) + "Criar tarefa</button></span></div>"
    : "";
  const k = (cx.contexto || {})[m.uid];
  const hora = k && k.estado === "pronto" ? (k.quando || "").slice(11, 16) : "";
  const nota = "assistente local" + (hora ? " · escrito às " + hora : "") + (k && k.estado === "pronto" ? " · confira na mensagem" : "");
  return exModulo("Contexto IA", exTextoDoContexto(m) + blocoCodigo + prazo, "ex-mod-entendi", nota);
}

/* Pede o contexto ao abrir a mensagem e acompanha ate ficar pronto. */
async function exPedirContexto(m, deNovo) {
  cx.contexto = cx.contexto || {};
  const ja = cx.contexto[m.uid];
  if (!deNovo && ja && (ja.estado === "pronto" || ja.estado === "resumindo" || ja.estado === "na_fila" || ja.estado === "indisponivel")) {
    if (ja.estado !== "pronto" && ja.estado !== "indisponivel") exAcompanharContexto(m);
    return;
  }
  cx.contexto[m.uid] = { estado: "resumindo" };
  let d = null;
  try {
    const r = await exJson("/api/email/contexto", {
      conta_id: mail.conta ? mail.conta.id : "", uid: m.uid, de: exQuem(m), assunto: m.assunto || "",
      corpo: m.corpo || "", de_novo: !!deNovo,
    });
    d = r.ok ? await r.json() : { modelo: { estado: "falhou", erro: await erroDe(r) } };
  } catch (err) { d = { modelo: { estado: "falhou", erro: String(err) } }; }
  cx.contexto[m.uid] = Object.assign({ chave: d.chave }, d.modelo);
  exPintarContexto(m);
  exAcompanharContexto(m);
}

function exAcompanharContexto(m) {
  const k = (cx.contexto || {})[m.uid];
  if (!k || !k.chave || (k.estado !== "resumindo" && k.estado !== "na_fila")) return;
  clearTimeout(cx.relogioContexto);
  cx.relogioContexto = setTimeout(async () => {
    if (!mail.aberta || mail.aberta.uid !== m.uid) return;
    try {
      const d = await (await fetch("/api/email/contexto?chave=" + encodeURIComponent(k.chave))).json();
      if (d.modelo && d.modelo.estado !== "nenhum") cx.contexto[m.uid] = Object.assign({ chave: k.chave }, d.modelo);
    } catch (err) { /* pergunta de novo no proximo giro */ }
    exPintarContexto(m);
    exAcompanharContexto(m);
  }, 4000);
}

function exPintarContexto(m) {
  const velho = document.querySelector('#email [data-ex-msg="' + CSS.escape(m.uid) + '"] .ex-mod-entendi');
  if (!velho) return;
  const novo = document.createElement("div");
  novo.innerHTML = exModEntendi(m);
  const modulo = novo.firstElementChild;
  velho.replaceWith(modulo);
  if (typeof emEsmaecer === "function") emEsmaecer(modulo.querySelector(".ex-mod-miolo"));
  exLigarEntendi(modulo, m);
}

function exLigarEntendi(raiz, m) {
  raiz.querySelectorAll("[data-em-prazo]").forEach((b) => { b.onclick = () => criarPrazoDoEmail(m, b.dataset.emPrazo === "agenda"); });
  raiz.querySelectorAll("[data-ex-copiar-codigo]").forEach((b) => { b.onclick = () => copiarTexto(b.dataset.exCopiarCodigo, "código copiado"); });
  raiz.querySelectorAll("[data-ex-contexto-de-novo]").forEach((b) => { b.onclick = () => exPedirContexto(m, true); });
}

function exModAnexos(m) {
  if (!m.anexos || !m.anexos.length) return "";
  return exModulo(plural(m.anexos.length, "anexo"), '<div class="ex-anexos">' + m.anexos.map((a) =>
    '<div class="ex-anexo">' + glifo(a.nome || "arquivo") + '<span class="duas-linhas"><b>' + esc(a.nome || "arquivo") + "</b><small>" +
    (a.kb ? String(a.kb).replace(".", ",") + " KB" : "no seu servidor") + "</small></span>" +
    '<span class="em-msg-acoes"><button data-baixar="' + esc(a.nome) + '" title="Abrir" aria-label="Abrir">' + ic("visibility", 18) + "</button>" +
    '<button data-guardar="' + esc(a.nome) + '" title="Guardar no Acervo" aria-label="Guardar no Acervo">' + ic("inventory_2", 18) + "</button></span></div>").join("") + "</div>", "ex-mod-anexos");
}

/* O e-mail como o remetente desenhou: a versao HTML num iframe isolado -
   sem permissao de script e com CSP que so aceita o que veio dentro da
   mensagem. Imagem de fora avisa o remetente que o e-mail foi aberto (e o
   seu IP): fica bloqueada ate a pessoa pedir, so para esta mensagem. Sem
   HTML, ou com "ver so o texto", o texto puro de sempre. */
function exModCorpo(m) {
  const t = (cx.trad || {})[m.uid];
  const vendoTraducao = !!(t && cx.tradVista === m.uid && t.estado !== "erro");
  const original = '<button class="sv-ligacao ex-html-troca" data-ex-original="1">ver o original</button>';
  if (vendoTraducao && t.estado === "andando") {
    return exModulo("", '<p class="em-andamento ativo"><span class="indicador"></span>Traduzindo nesta máquina…</p>' +
      esqueleto("texto") + original, "ex-mod-corpo");
  }
  // A traducao usa o mesmo desenho do original: o HTML traduzido no quadro,
  // ou o texto traduzido, com a troca de volta embaixo.
  const msg = vendoTraducao ? Object.assign({}, m, { html: t.html || "", corpo: t.texto || m.corpo }) : m;
  // O texto da mensagem ocupa a largura toda, sem rotulo na margem; a
  // traducao se anuncia numa linha curta em cima.
  const rotulo = vendoTraducao ? "Tradução" : "Mensagem";
  const nota = vendoTraducao ? '<p class="ex-trad-nota">Tradução · tradutor desta máquina · na dúvida, vale o original</p>' : "";
  const soTexto = cx.soTexto === undefined ? emailPrefs().soTexto : cx.soTexto;
  const html = msg.html && !soTexto;
  if (!html) {
    const texto = vendoTraducao
      ? '<div class="ex-corpo ex-traducao">' + msg.corpo.split(/\n{2,}/).map((p) => "<p>" + esc(p) + "</p>").join("") + "</div>"
      : '<div class="ex-corpo">' + corpoComPrazo(msg.corpo, msg.prazo_trecho) + "</div>";
    return exModulo("", nota + texto + (vendoTraducao ? original : "") +
      (msg.html ? '<button class="sv-ligacao ex-html-troca" data-ex-formatado="1">ver com a formatação</button>' : ""), "ex-mod-corpo");
  }
  const liberadas = exImagensLiberadas(m.uid);
  const aviso = msg.imagens_remotas && !liberadas
    ? '<div class="ex-html-aviso">' + ic("visibility_off", 15) + "<span>" + plural(msg.imagens_remotas, "imagem de fora bloqueada", "imagens de fora bloqueadas") +
      " — carregar avisa o remetente que você abriu.</span>" + '<button class="sv-ligacao" data-ex-imagens="1">mostrar</button></div>'
    : "";
  return exModulo("", nota + aviso + '<div class="ex-html"><iframe class="ex-html-quadro" data-ex-html="' + esc(m.uid) + '" title="' + rotulo + '" ' +
    'sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox" referrerpolicy="no-referrer"></iframe></div>' +
    '<span class="ex-html-trocas">' + (vendoTraducao ? original : "") +
    '<button class="sv-ligacao ex-html-troca" data-ex-so-texto="1">ver só o texto</button></span>', "ex-mod-corpo");
}

/* Imagens de fora: liberadas para esta mensagem, ou para todas em
   E-mail › Configuracoes. */
function exImagensLiberadas(uid) {
  return emailPrefs().imagens || (cx.imagensLiberadas || new Set()).has(uid);
}

/* Qualquer cor CSS (inclusive o bgcolor="#fff" antigo) em [r, g, b, a]. */
function exRgb(cor, doc) {
  try {
    const el = doc.createElement("i");
    el.style.color = cor;
    doc.body.appendChild(el);
    const v = getComputedStyle(el).color.match(/[\d.]+/g);
    el.remove();
    return v ? v.slice(0, 3).map(Number) : null;
  } catch (err) { return null; }
}

function exLuz(rgb) { return (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255; }

function exCorDeRgb(rgb) { return "rgb(" + rgb.map((c) => Math.round(c)).join(", ") + ")"; }

/* A mesma cor com a claridade virada, mantendo o tom: o branco do papel vai
   a cerca de #1f1f1f (a folha do PAULUS escuro) e o preto do texto a
   #e0e0e0. Texto que virou claro nunca fica abaixo de 72% de claridade, para
   o link azul-escuro nao sumir no fundo. */
function exEscurecerCor(rgb, texto) {
  const [r, g, b] = rgb.map((c) => c / 255);
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, sat = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    sat = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h /= 6;
  }
  let l2 = 0.12 + (1 - l) * 0.76;
  if (texto) l2 = Math.max(l2, 0.72);
  // Fundo escurecido perde quase toda a cor: o azul-clarinho de um aviso
  // viraria um azul-marinho forte, que pesa mais que o original.
  else sat *= 0.3;
  const q = l2 < 0.5 ? l2 * (1 + sat) : l2 + sat - l2 * sat, p = 2 * l2 - q;
  const canal = (t) => {
    t = (t + 1) % 1;
    const v = t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p;
    return v * 255;
  };
  return sat === 0 ? [l2 * 255, l2 * 255, l2 * 255] : [canal(h + 1 / 3), canal(h), canal(h - 1 / 3)];
}

/* Passa o e-mail de versao so clara para o escuro, elemento a elemento:
   fundo claro escurece, texto escuro clareia, borda clara escurece. As
   imagens nao sao tocadas - ficam com as cores de verdade. */
function exEscurecerEmail(doc) {
  const numeros = (c) => { const v = (c || "").match(/[\d.]+/g); return v && (v.length < 4 || Number(v[3]) > 0) ? v.slice(0, 3).map(Number) : null; };
  const trocas = [];
  const elementos = [doc.body].concat(Array.from(doc.body.querySelectorAll("*")).slice(0, 5000));
  for (const el of elementos) {
    if (/^(IMG|VIDEO|PICTURE|SVG|CANVAS)$/i.test(el.tagName)) continue;
    const e = getComputedStyle(el);
    const fundo = numeros(e.backgroundColor);
    if (fundo && exLuz(fundo) > 0.5) trocas.push([el, "background-color", exCorDeRgb(exEscurecerCor(fundo, false))]);
    const letra = numeros(e.color);
    if (letra && exLuz(letra) < 0.6) trocas.push([el, "color", exCorDeRgb(exEscurecerCor(letra, true))]);
    ["top", "right", "bottom", "left"].forEach((lado) => {
      if (e["border-" + lado + "-style"] === "none") return;
      const borda = numeros(e.getPropertyValue("border-" + lado + "-color"));
      if (borda && exLuz(borda) > 0.6) trocas.push([el, "border-" + lado + "-color", exCorDeRgb(exEscurecerCor(borda, false))]);
    });
  }
  trocas.forEach(([el, prop, valor]) => el.style.setProperty(prop, valor, "important"));
}

/* Trocar o tema redesenha o e-mail aberto no tema novo. */
new MutationObserver(() => {
  document.querySelectorAll("iframe.ex-html-quadro").forEach((q) => { if (q._ex) exMontarHtml(q._ex.raiz, q._ex.m); });
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-tema"] });

function exMontarHtml(raiz, m) {
  const quadro = raiz.querySelector('[data-ex-html="' + CSS.escape(m.uid) + '"]');
  if (!quadro) return;
  const liberadas = exImagensLiberadas(m.uid);
  const img = liberadas ? "data: https: http:" : "data:";
  /* A CSP e a barreira de verdade: nada de script, nada de fora (salvo as
     imagens, se a pessoa liberou), nada de formulario. */
  const csp = "default-src 'none'; img-src " + img + "; style-src 'unsafe-inline'" + (liberadas ? " https:" : "") +
    "; font-src data:" + (liberadas ? " https:" : "") + "; form-action 'none'; base-uri 'none'";
  /* Claro ou escuro: o e-mail que tem versao escura (media query
     prefers-color-scheme) segue o tema do PAULUS; o que nao tem fica claro,
     como no Gmail - senao o texto escuro dele cairia num fundo escuro. O
     iframe herda o esquema do color-scheme do proprio elemento. */
  quadro._ex = { raiz: raiz, m: m };
  // Vendo a traducao: o HTML traduzido no lugar do original.
  const trad = (cx.trad || {})[m.uid];
  if (trad && trad.estado === "pronta" && cx.tradVista === m.uid && trad.html) m = Object.assign({}, m, { html: trad.html });
  // A escolha de E-mail › Configuracoes: acompanhar o PAULUS, sempre claro
  // ou sempre escuro.
  const escolha = emailPrefs().tema;
  const temaEscuro = escolha === "escuro" || (escolha === "auto" && document.documentElement.dataset.tema === "escuro");
  const escuro = temaEscuro && /prefers-color-scheme\s*:\s*dark/i.test(m.html);
  quadro.style.colorScheme = escuro ? "dark" : "light";
  const padrao = escuro ? "#1f1f1e" : "#ffffff";
  /* Dentro do iframe, prefers-color-scheme segue o Windows, e nao o tema do
     PAULUS. Entao a condicao e reescrita no CSS do proprio e-mail: a do tema
     escolhido vira sempre-verdadeira, a outra nunca. */
  const sempre = "(min-width: 0px)", nunca = "(max-width: 0px)";
  const corpoHtml = m.html
    .replace(/\(\s*prefers-color-scheme\s*:\s*dark\s*\)/gi, escuro ? sempre : nunca)
    .replace(/\(\s*prefers-color-scheme\s*:\s*light\s*\)/gi, escuro ? nunca : sempre);
  quadro.srcdoc = '<!doctype html><html><head><meta charset="utf-8">' +
    '<meta http-equiv="Content-Security-Policy" content="' + csp + '">' +
    '<meta name="color-scheme" content="' + (escuro ? "dark" : "light") + '">' +
    '<base target="_blank"><style>html,body{margin:0;padding:0;background:' + padrao + ";color:" + (escuro ? "#ececea" : "#1f1f1f") + ";" +
    "font:15px/1.5 -apple-system,'Segoe UI',Roboto,Arial,sans-serif;word-wrap:break-word;overflow-wrap:anywhere}" +
    "body{padding:16px 0}img{max-width:100%;height:auto}table{max-width:100%}" +
    "</style></head><body>" +
    corpoHtml + "</body></html>";
  const ajustar = () => {
    try {
      const doc = quadro.contentDocument;
      if (!doc || !doc.body) return;
      quadro.style.height = Math.max(120, doc.documentElement.scrollHeight) + "px";
    } catch (err) { /* sem acesso ao quadro: fica a altura padrao */ }
  };
  /* O fundo do proprio e-mail vai para a folha inteira: o bloco de 600 px
     centrado deixava faixas da cor padrao dos lados. Vale o fundo do maior
     elemento que ocupa boa parte da largura - a "moldura" do e-mail. */
  const pintarFundo = () => {
    try {
      const doc = quadro.contentDocument;
      const largura = doc.body.clientWidth || 1;
      let cor = "";
      let maior = 0;
      const vazio = (c) => !c || c === "transparent" || /rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*0\s*\)/.test(c);
      // O fundo que o e-mail pos no proprio <body> (bgcolor ou style) vale
      // primeiro: a regra padrao da folha o encobria.
      const doBody = doc.body.getAttribute("bgcolor") || "";
      if (doBody) cor = doBody;
      const candidatos = cor ? [] : Array.from(doc.body.querySelectorAll("table,div,center,td,section")).slice(0, 300);
      for (const el of candidatos) {
        const r = el.getBoundingClientRect();
        if (r.width < largura * 0.5 || r.height < 80) continue;
        const c = getComputedStyle(el).backgroundColor;
        if (vazio(c)) continue;
        const area = r.width * r.height;
        if (area > maior) { maior = area; cor = c; }
      }
      const caixa = quadro.closest(".ex-html");
      const rgb = exRgb(cor || padrao, doc);
      // Tema escuro, e-mail sem versao escura e de fundo claro: as cores dele
      // passam para o escuro. O de fundo ja escuro fica como veio.
      if (temaEscuro && !escuro && rgb && exLuz(rgb) > 0.5) {
        exEscurecerEmail(doc);
        const fora = exCorDeRgb(exEscurecerCor(rgb, false));
        doc.documentElement.style.background = fora;
        doc.body.style.setProperty("background", fora, "important");
        if (caixa) caixa.style.background = fora;
        return;
      }
      if (!cor) return;
      doc.documentElement.style.background = cor;
      doc.body.style.background = cor;
      if (caixa) caixa.style.background = cor;
    } catch (err) { /* sem acesso: fica o fundo padrao */ }
  };
  quadro.onload = () => {
    pintarFundo();
    ajustar();
    // Imagens que chegam depois (as liberadas) mudam a altura.
    try { quadro.contentDocument.querySelectorAll("img").forEach((i) => { i.addEventListener("load", ajustar); }); } catch (err) { /* ok */ }
    setTimeout(ajustar, 400);
  };
}

function exModResposta(m) {
  if (exRespAtiva(m)) return exModulo("Resposta", exResposta(m), "ex-mod-resposta");
  // Como no Gmail: responder, responder a todos (so quando ha mais gente) e
  // encaminhar, lado a lado; o rascunho do assistente vem depois.
  const todos = exTodos(m).length > 1;
  return exModulo("Resposta", '<div class="ex-resp-botoes"><button class="ex-pilula com-icone" id="mail-responder">' + ic("reply", 16) + "Responder</button>" +
    (todos ? '<button class="ex-pilula com-icone" id="mail-responder-todos">' + ic("reply", 16) + "Responder a todos</button>" : "") +
    '<button class="ex-pilula com-icone" id="mail-encaminhar-pe">' + ic("forward", 16) + "Encaminhar</button>" +
    (m.pode_rascunhar
      ? '<button class="com-icone" id="mail-responder-rascunho">' + ic("auto_awesome", 16) + "Rascunho pelo assistente</button><small>cerca de um minuto nesta máquina · você revisa antes de sair</small>"
      : "<small>Esta conta não permite rascunho pelo assistente.</small>") + "</div>", "ex-mod-resposta");
}

/* A proxima da lista que pede resposta, depois desta (e o que era a fila). */
function exProxima(uid) {
  const itens = exItens();
  const i = itens.findIndex((m) => m.uid === uid);
  return itens.slice(i + 1).find(exPede) || itens.slice(0, Math.max(i, 0)).find(exPede) || null;
}

function exPe(item) {
  const prox = exProxima(item.uid);
  return '<footer class="ex-msg-pe"><span class="ex-teclas">↑ ↓ passa · Esc fecha</span><span class="cresce"></span>' +
    (prox ? '<button class="com-icone" data-ex-ir="' + esc(prox.uid) + '">Próxima que pede resposta' + ic("arrow_forward", 16) + "</button>"
      : '<span class="ex-teclas">Nenhuma outra pede resposta nesta página</span>') + "</footer>";
}

/* A mensagem aberta e uma folha sobre a faixa da linha: os modulos um
   embaixo do outro, cada um com o seu rotulo na margem. */
function exFolha(miolo, uid) {
  return '<div class="ex-msg"' + (uid ? ' data-ex-msg="' + esc(uid) + '"' : "") + '><div class="ex-msg-folha">' + miolo + "</div></div>";
}

function exMensagem(item) {
  const m = mail.aberta && mail.aberta.uid === item.uid ? mail.aberta : null;
  if (!m) {
    const falhou = cx.falhou === item.uid;
    return exFolha(exCabecaMsg(item, null) +
      exModulo("", falhou ? '<p class="ex-mod-texto">Não consegui abrir esta mensagem.</p><div class="ex-vazio-acoes"><button data-ex-tentar-msg="1">Tentar de novo</button></div>'
        : esqueleto("texto"), "ex-mod-corpo"), item.uid);
  }
  return exFolha(exCabecaMsg(item, m) + exModEntendi(m) + exModAnexos(m) + exModCorpo(m) + exModResposta(m) + exPe(item), item.uid);
}

function exEnvioAberto(e) {
  return exFolha('<header class="ex-mod ex-mod-cabeca"><div class="ex-cabeca-linha"><h2 class="ex-assunto">' + esc(e.assunto || "(sem assunto)") + "</h2>" + exIcones(null) + "</div>" +
    '<dl class="ex-meta"><div><dt>De</dt><dd>' + esc(e.de) + "</dd></div><div><dt>Para</dt><dd>" + esc((e.para || []).join(", ")) + "</dd></div>" +
    "<div><dt>Saiu</dt><dd>" + esc(quandoCurto(e.quando)) + "</dd></div></dl></header>" +
    exModulo("Registro", '<p class="ex-mod-texto">O texto completo está na pasta de enviados do seu servidor; aqui fica o registro de que saiu.</p>' +
      ((e.anexos || []).length ? '<div class="em-anexo-fichas">' + e.anexos.map((n) => '<span class="em-anexo-ficha">' + glifo(n) + '<span class="corta">' + esc(n) + "</span></span>").join("") + "</div>" : "")) +
    '<footer class="ex-msg-pe"><span class="cresce"></span><button class="primario com-icone" data-em-escrever-para="' + esc((e.para || []).join(", ")) + '">' + ic("edit", 16) + "Escrever de novo</button></footer>");
}

function exPedidoAberto(p) {
  return exFolha('<header class="ex-mod ex-mod-cabeca"><div class="ex-cabeca-linha"><h2 class="ex-assunto">' + esc(p.titulo) + "</h2>" + exIcones(null) + "</div>" +
    '<dl class="ex-meta"><div><dt>Pedido em</dt><dd>' + esc(quandoCurto(p.criado_em)) + "</dd></div></dl></header>" +
    exModulo("O envio", '<p class="ex-mod-texto">' + esc(p.resumo || "") + "</p>" +
      (p.etiquetas && p.etiquetas.length ? '<div class="ex-etiquetas">' + p.etiquetas.map((t) => '<span class="em-pilula">' + esc(t) + "</span>").join("") + "</div>" : "")) +
    '<footer class="ex-msg-pe"><span class="ex-teclas">O e-mail só sai depois do seu sim.</span><span class="cresce"></span>' +
    '<button class="primario com-icone" data-em-aprovacoes="1">' + ic("verified", 16) + "Decidir em Aprovações</button></footer>");
}

/* ------------------------------------------------------- responder */
/*
   A resposta abre ali mesmo, no modulo de resposta da mensagem. Sai pelo
   mesmo pedido de envio do Escrever (fila de Aprovacoes, quando a conta
   pede). "Tela cheia" leva o texto para o Escrever, onde ficam os anexos.
*/

function exRespAtiva(m) { return !!(m && cx.resp && cx.resp.uid === m.uid); }

function exConferir(r, m) {
  const itens = [];
  const linha = (ok, t) => '<div class="em-conferencia ' + (ok ? "ok" : "aviso") + '">' + ic(ok ? "check_circle" : "error", 16) + "<span>" + t + "</span></div>";
  itens.push(m.de_cadastro ? linha(true, "Destinatário no cadastro · " + esc(m.de_cadastro)) : linha(false, esc(r.para) + " não está no cadastro"));
  if (/\banex[oa]/i.test(r.corpo)) itens.push(linha(false, "O texto cita anexo, mas nenhum arquivo vai junto"));
  const valores = r.corpo.match(/R\$\s?[\d.]+(,\d{2})?/g);
  if (valores) itens.push(linha(true, "Cita " + esc(valores.slice(0, 2).join(", ")) + " · confira antes"));
  itens.push(linha(true, "Sai por " + esc(mail.conta ? mail.conta.email : "") + (exSaiSozinho() ? "" : " · passa por Aprovações")));
  return itens.join("");
}

function exResposta(m) {
  const r = cx.resp;
  const c = mail.conta;
  if (r.estado === "enviado") {
    const esperando = r.retorno && r.retorno.aguardando_aprovacao;
    return '<div class="ex-resp feito"><b class="ex-resp-titulo">' + ic(esperando ? "schedule_send" : "check_circle", 16) + (esperando ? "Esperando o seu sim" : "Enviada") + "</b>" +
      "<p>" + (esperando ? "Parou na fila de Aprovações para " + esc(r.para) + ". Nada saiu ainda; e-mail enviado não volta." : "Saiu pelo servidor da sua conta para " + esc(r.para) + ".") + "</p>" +
      '<div class="ex-resp-acoes">' + (esperando ? '<button class="com-icone" data-em-aprovacoes="1">' + ic("verified", 16) + "Abrir Aprovações</button>" : "") +
      '<span class="cresce"></span><button data-ex-resp-fechar="1">Fechar</button></div></div>';
  }
  const preparando = r.estado === "preparando";
  return '<div class="ex-resp">' +
    '<div class="ex-resp-topo"><span class="ex-resp-para">para <b>' + esc(r.para) + "</b></span></div>" +
    '<input type="text" class="ex-resp-assunto" id="ex-resp-assunto" value="' + esc(r.assunto) + '" aria-label="Assunto">' +
    (preparando
      ? '<p class="ex-resp-preparando">' + coroa(16) + "<span>Escrevendo o rascunho a partir da mensagem… cerca de um minuto nesta máquina.</span></p>"
      : editorRico({ id: "ex-resp-texto", html: r.corpoHtml, texto: r.corpo, placeholder: "Escreva a resposta…", classe: "ex-er" })) +
    // A assinatura como vai sair; o HTML dela ja foi limpo no servidor.
    (c && (c.assinatura_html || c.assinatura) ? '<div class="ex-resp-assinatura">' + (c.assinatura_html || esc(c.assinatura)) + "</div>" : "") +
    (preparando ? "" : '<div class="ex-resp-conferi" id="ex-resp-conferi">' + exConferir(r, m) + "</div>") +
    '<div class="ex-resp-acoes"><button class="sv-ligacao" data-ex-resp-descartar="1">' + ic("delete", 15) + "Descartar</button>" +
    '<button class="sv-ligacao" data-ex-resp-cheia="1">' + ic("fullscreen", 15) + "Tela cheia · anexos</button>" +
    (m.pode_rascunhar && !preparando && !r.corpo.trim() ? '<button class="sv-ligacao" data-ex-resp-rascunho="1">' + ic("auto_awesome", 15) + "Rascunho pelo assistente</button>" : "") +
    '<span class="cresce"></span><button class="primario com-icone" data-ex-resp-enviar="1"' + (preparando || r.estado === "enviando" ? " disabled" : "") + ">" +
    ic("schedule_send", 16) + (r.estado === "enviando" ? "Enviando…" : exSaiSozinho() ? "Enviar" : "Enviar para aprovação") + "</button></div></div>";
}

/* Os enderecos de um cabecalho "Nome <a@b>, c@d". */
function exEnderecos(texto) {
  return (String(texto || "").match(/[^\s<>,;"']+@[^\s<>,;"']+\.[^\s<>,;"']+/g) || []).map((e) => e.toLowerCase());
}

/* Responder a todos: o remetente e quem estava em Para e Cc, menos a
   propria conta. */
function exTodos(m) {
  const eu = mail.conta ? mail.conta.email.toLowerCase() : "";
  const todos = [m.de_email].concat(exEnderecos(m.para), exEnderecos(m.cc)).filter((e) => e && e !== eu);
  return todos.filter((e, i) => todos.indexOf(e) === i);
}

async function exResponder(comRascunho, todos) {
  const m = mail.aberta;
  if (!m) return;
  const assunto = (m.assunto || "").toLowerCase().startsWith("re:") ? m.assunto : "Re: " + (m.assunto || "");
  const pronto = mail.rascunho && mail.rascunho.uid === m.uid ? mail.rascunho.rascunho : "";
  cx.resp = { uid: m.uid, para: todos ? exTodos(m).join(", ") : m.de_email, assunto, corpo: comRascunho ? pronto : "", estado: comRascunho && !pronto ? "preparando" : "escrevendo" };
  cx.respRolar = true;
  desenharEmail();
  if (cx.resp.estado !== "preparando") return;
  let r;
  try {
    r = await exJson("/api/email/rascunho", { uid: m.uid, conta_id: mail.conta ? mail.conta.id : "" });
  } catch (err) { r = null; avisoCert(String(err)); }
  if (!cx.resp || cx.resp.uid !== m.uid) return;
  if (!r || !r.ok) {
    if (r) avisoCert((r.status === 503 ? "o assistente local não respondeu: " : "") + (await erroDe(r)), { tom: "erro" });
    cx.resp.estado = "escrevendo";
  } else {
    const d = await r.json();
    mail.rascunho = Object.assign({ uid: m.uid }, d);
    Object.assign(cx.resp, { corpo: d.rascunho, corpoHtml: "", assunto: d.assunto || cx.resp.assunto, estado: "escrevendo" });
  }
  cx.respRolar = true;
  if (mail.visao === "caixa") desenharEmail();
}

function exFocarResposta() {
  setTimeout(() => {
    const t = $("ex-resp-texto");
    if (!t) return;
    t.focus();
    t.setSelectionRange(t.value.length, t.value.length);
  }, 0);
}

async function exEnviarResposta() {
  const r = cx.resp;
  if (!r || !r.corpo.trim()) { avisoCert("escreva a resposta antes de enviar"); exFocarResposta(); return; }
  r.estado = "enviando";
  desenharEmail();
  const d = await exMandar({ conta_id: mail.conta ? mail.conta.id : "", para: r.para, cc: "", cco: "", assunto: r.assunto, corpo: r.corpo, corpo_html: r.corpoHtml || "", anexos: [] });
  if (cx.resp !== r) return;
  if (!d) { r.estado = "escrevendo"; if (mail.visao === "caixa") desenharEmail(); return; }
  r.estado = "enviado"; r.retorno = d;
  await carregarFilaDeEmail();
  cx.respRolar = true;
  if (mail.visao === "caixa") desenharEmail();
}

function exLigarResposta(raiz) {
  const m = mail.aberta;
  ["mail-responder", "ex-responder-rapido"].forEach((id) => { const b = $(id); if (b) b.onclick = () => exResponder(false); });
  const todos = $("mail-responder-todos");
  if (todos) todos.onclick = () => exResponder(false, true);
  const comR = $("mail-responder-rascunho");
  if (comR) comR.onclick = () => exResponder(true);
  const r = cx.resp;
  if (!r || !m || r.uid !== m.uid) return;
  let relogio;
  // A mesma faixa de edicao do Escrever (js/33-email-editor.js).
  const texto = ligarEditorRico("ex-resp-texto", () => { r.corpoHtml = texto.html; });
  if (texto) {
    texto.oninput = () => {
      r.corpo = texto.value;
      r.corpoHtml = texto.html;
      clearTimeout(relogio);
      relogio = setTimeout(() => { const alvo = $("ex-resp-conferi"); if (alvo) alvo.innerHTML = exConferir(r, m); }, 500);
    };
  }
  const assunto = $("ex-resp-assunto");
  if (assunto) assunto.oninput = () => { r.assunto = assunto.value; };
  raiz.querySelectorAll("[data-ex-resp-descartar], [data-ex-resp-fechar]").forEach((b) => { b.onclick = () => { cx.resp = null; desenharEmail(); }; });
  raiz.querySelectorAll("[data-ex-resp-cheia]").forEach((b) => { b.onclick = () => { const x = cx.resp; cx.resp = null; telaEscrever({ para: x.para, assunto: x.assunto, corpo: x.corpo, corpo_html: x.corpoHtml || "" }); }; });
  raiz.querySelectorAll("[data-ex-resp-rascunho]").forEach((b) => { b.onclick = () => exResponder(true); });
  raiz.querySelectorAll("[data-ex-resp-enviar]").forEach((b) => { b.onclick = exEnviarResposta; });
}

/* ------------------------------------------------ abrir no lugar da linha */

function exAbrir(uid, forcar) {
  if (!uid) return;
  if (cx.aberta === uid && !forcar) { exFechar(); return; }
  if (cx.resp && cx.resp.uid !== uid) cx.resp = null;
  cx.aberta = uid; cx.falhou = null; cx.rolarPara = uid;
  mail.aberta = null;
  desenharEmail();
  abrirMensagem(uid).catch(() => {}).then(() => {
    if (cx.aberta !== uid) return;
    if (!mail.aberta || mail.aberta.uid !== uid) { cx.falhou = uid; if (mail.visao === "caixa") desenharEmail(); return; }
    if (mail.aberta.previa) cx.previas[uid] = mail.aberta.previa;
    exPedirResumoDepois();
  });
}

function exFechar() {
  cx.aberta = null; cx.falhou = null; mail.aberta = null;
  desenharEmail();
}

function exPassar(passo) {
  const uids = exItens().map((m) => m.uid);
  if (!uids.length) return;
  const i = uids.indexOf(cx.aberta);
  const j = i < 0 ? (passo > 0 ? 0 : uids.length - 1) : Math.min(uids.length - 1, Math.max(0, i + passo));
  if (uids[j] !== cx.aberta) exAbrir(uids[j]);
}

/* Traz a linha aberta para o alto da area de rolagem, logo abaixo da barra
   que fica presa. Sem scrollIntoView, que rola a janela inteira. */
function exMostrarLinha(uid) {
  const rolagem = document.querySelector("#email .sv-principal");
  const linha = document.querySelector('#email [data-ex-uid="' + uid + '"]');
  if (!rolagem || !linha) return;
  const barra = document.querySelector("#email .ex-barra");
  const folga = (barra ? barra.offsetHeight : 0) + 12;
  const r = rolagem.getBoundingClientRect(), l = linha.getBoundingClientRect();
  if (l.top < r.top + folga || l.top > r.top + rolagem.clientHeight * 0.45) rolagem.scrollTop += l.top - r.top - folga;
}

/* Quando a barra fica presa no alto, o cartao ja subiu por baixo dela: os
   cantos arredondados deixariam ver as linhas passando. Presa, ela fica reta. */
document.addEventListener("scroll", (ev) => {
  const rolagem = ev.target;
  if (!rolagem.classList || !rolagem.classList.contains("sv-principal") || !rolagem.closest("#email")) return;
  const barra = rolagem.querySelector(".ex-barra");
  const cartao = barra && barra.closest(".ex-lista");
  if (!cartao) return;
  barra.classList.toggle("presa", cartao.getBoundingClientRect().top < barra.getBoundingClientRect().top - 0.5);
}, { capture: true, passive: true });

/* Traz a resposta inteira para a vista: sobe o que passar do fundo, sem
   deixar o topo dela sair por cima. */
function exMostrarResposta() {
  const rolagem = document.querySelector("#email .sv-principal");
  const caixa = document.querySelector("#email .ex-resp");
  if (!rolagem || !caixa) return;
  const r = rolagem.getBoundingClientRect(), c = caixa.getBoundingClientRect();
  const sobra = c.bottom - r.bottom + 24;
  if (sobra > 0) rolagem.scrollTop += Math.min(sobra, c.top - r.top - 70);
  else if (c.top < r.top + 60) rolagem.scrollTop += c.top - r.top - 70;
}

document.addEventListener("keydown", (ev) => {
  if (!document.querySelector("#email.ex-tela") || mail.visao !== "caixa" || mail.pasta !== "entrada") return;
  if (ev.ctrlKey || ev.altKey || ev.metaKey) return;
  const alvo = ev.target;
  if (alvo && (alvo.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName))) return;
  if (document.querySelector(".menu-conversa.menu-novo") || document.getElementById("veu-dialogo")) return;
  if (cx.escolhidos.size) return;
  if (cx.resp && cx.resp.uid === cx.aberta && cx.resp.estado !== "enviado") return;
  if (ev.key === "ArrowDown" || ev.key === "j") { ev.preventDefault(); exPassar(1); }
  else if (ev.key === "ArrowUp" || ev.key === "k") { ev.preventDefault(); exPassar(-1); }
  else if (ev.key === "Escape" && cx.aberta) { ev.preventDefault(); exFechar(); }
});

/* --------------------------------------------------------- acoes */

async function exMarcar(uids, lido) {
  let r;
  try {
    r = await exJson("/api/email/marcar", { conta_id: mail.conta ? mail.conta.id : "", uids: uids, lido: lido });
  } catch (err) { avisoCert(String(err), { tom: "erro" }); return false; }
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return false; }
  const k = mail.caixa;
  (k ? k.mensagens : []).forEach((m) => {
    if (!uids.includes(m.uid) || m.lido === lido) return;
    m.lido = lido;
    k.nao_lidos = Math.max(0, k.nao_lidos + (lido ? -1 : 1));
  });
  exPedirResumoDepois();
  return true;
}

async function exArquivar(uids) {
  let r;
  try {
    r = await exJson("/api/email/arquivar", { conta_id: mail.conta ? mail.conta.id : "", uids: uids });
  } catch (err) { avisoCert(String(err), { tom: "erro" }); return false; }
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return false; }
  const d = await r.json();
  if (d.arquivadas === uids.length && mail.caixa) {
    const k = mail.caixa;
    const antes = k.mensagens.length;
    k.mensagens.filter((m) => uids.includes(m.uid) && !m.lido).forEach(() => { k.nao_lidos = Math.max(0, k.nao_lidos - 1); });
    k.mensagens = k.mensagens.filter((m) => !uids.includes(m.uid));
    k.mostrando = Math.max(0, k.mostrando - (antes - k.mensagens.length));
    k.total = Math.max(0, k.total - (antes - k.mensagens.length));
  } else {
    await carregarPasta();
  }
  avisoCert(d.aviso || (plural(d.arquivadas, "mensagem arquivada", "mensagens arquivadas") + " · continuam no servidor, na pasta de arquivo"), { tom: d.aviso ? "" : "ok" });
  exPedirResumoDepois();
  return true;
}

/* Excluir e mandar para a lixeira do servidor: confirma, porque a
   mensagem sai da caixa, mas avisa que da para recuperar pelo webmail. */
async function exExcluir(uids) {
  const n = uids.length;
  const ok = await confirmar({
    titulo: "Excluir " + (n === 1 ? "esta mensagem" : plural(n, "mensagem", "mensagens")) + "?", contexto: "E-mail › Caixa de entrada",
    texto: (n === 1 ? "Ela vai" : "Elas vão") + " para a lixeira do seu servidor. Dá para recuperar pelo webmail até a lixeira ser esvaziada — o Gmail esvazia sozinho depois de 30 dias.",
    confirmar: "Excluir", perigo: true,
  });
  if (!ok) return false;
  let r;
  try {
    r = await exJson("/api/email/excluir", { conta_id: mail.conta ? mail.conta.id : "", uids: uids });
  } catch (err) { avisoCert(String(err), { tom: "erro" }); return false; }
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return false; }
  const d = await r.json();
  if (d.excluidas === n && mail.caixa) {
    const k = mail.caixa;
    const antes = k.mensagens.length;
    k.mensagens.filter((m) => uids.includes(m.uid) && !m.lido).forEach(() => { k.nao_lidos = Math.max(0, k.nao_lidos - 1); });
    k.mensagens = k.mensagens.filter((m) => !uids.includes(m.uid));
    k.mostrando = Math.max(0, k.mostrando - (antes - k.mensagens.length));
    k.total = Math.max(0, k.total - (antes - k.mensagens.length));
  } else {
    await carregarPasta();
  }
  if (uids.includes(cx.aberta)) { cx.aberta = null; mail.aberta = null; }
  uids.forEach((u) => cx.escolhidos.delete(u));
  avisoCert(d.aviso || (plural(d.excluidas, "mensagem foi para a lixeira", "mensagens foram para a lixeira")), { tom: d.aviso ? "" : "ok" });
  exPedirResumoDepois();
  return true;
}

/* A estrela muda na tela na hora e volta atras se o servidor recusar. */
async function exEstrela(uid) {
  const item = (mail.caixa ? mail.caixa.mensagens : []).find((x) => x.uid === uid);
  if (!item) return;
  const sim = !item.sinalizada;
  item.sinalizada = sim;
  desenharEmail();
  let r;
  try {
    r = await exJson("/api/email/estrela", { conta_id: mail.conta ? mail.conta.id : "", uids: [uid], sim: sim });
  } catch (err) { r = null; }
  if (!r || !r.ok) {
    item.sinalizada = !sim;
    desenharEmail();
    avisoCert(r ? await erroDe(r) : "não consegui falar com o servidor", { tom: "erro" });
  }
}

async function exLote(acao) {
  const uids = exItens().map((m) => m.uid).filter((u) => cx.escolhidos.has(u));
  if (!uids.length) return;
  if (acao === "excluir") {
    if (await exExcluir(uids)) desenharEmail();
    return;
  }
  if (acao === "arquivar") {
    const ok = await confirmar({
      titulo: "Arquivar " + plural(uids.length, "mensagem", "mensagens") + "?", contexto: "E-mail › Caixa de entrada",
      texto: "Saem da caixa de entrada e ficam na pasta de arquivo do seu servidor. Se o servidor não tiver essa pasta, eu só marco como lidas.",
      confirmar: "Arquivar",
    });
    if (!ok || !(await exArquivar(uids))) return;
    if (uids.includes(cx.aberta)) { cx.aberta = null; mail.aberta = null; }
  } else {
    const lido = acao === "lidas";
    if (!(await exMarcar(uids, lido))) return;
    avisoCert(plural(uids.length, lido ? "marcada como lida" : "marcada como não lida", lido ? "marcadas como lidas" : "marcadas como não lidas"), { tom: "ok" });
  }
  cx.escolhidos.clear();
  desenharEmail();
}

async function exIrPasta(id) {
  mail.pasta = id;
  mail.envioAberto = null; mail.pedidoAberto = null;
  exLimpar();
  await carregarPasta();
  desenharEmail();
}

async function exMudarVisao(id) {
  const v = EX_VISOES.find((x) => x.id === id) || EX_VISOES[0];
  cx.visao = v.id;
  cx.escolhidos.clear();
  if (v.filtro !== mail.filtro) {
    mail.filtro = v.filtro;
    cx.aberta = null; mail.aberta = null;
    mail.caixa = null;
    desenharEmail();
    await carregarPasta();
  }
  desenharEmail();
}

function exMenuDaLinha(botao, m) {
  menuNaLinha(botao, [
    { rotulo: cx.aberta === m.uid ? "Fechar" : "Abrir", acao: () => exAbrir(m.uid) },
    { rotulo: "Selecionar", acao: () => { cx.escolhidos.add(m.uid); desenharEmail(); } },
    "-",
    { rotulo: m.lido ? "Marcar como não lida" : "Marcar como lida", acao: async () => { if (await exMarcar([m.uid], !m.lido)) desenharEmail(); } },
    { rotulo: "Arquivar", acao: async () => { if (await exArquivar([m.uid])) { if (cx.aberta === m.uid) { cx.aberta = null; mail.aberta = null; } desenharEmail(); } } },
    { rotulo: "Excluir", perigo: true, acao: async () => { if (await exExcluir([m.uid])) desenharEmail(); } },
    "-",
    { rotulo: "Copiar o endereço", acao: () => copiarTexto(m.de_email, "endereço copiado") },
  ]);
}

/* ------------------------------------------------------------ ligar */

function exLigarMensagem(raiz) {
  const m = mail.aberta;
  raiz.querySelectorAll("[data-ex-fechar]").forEach((b) => {
    b.onclick = () => {
      if (mail.pasta === "enviados") { mail.envioAberto = null; desenharEmail(); return; }
      if (mail.pasta === "aprovacao") { mail.pedidoAberto = null; desenharEmail(); return; }
      exFechar();
    };
  });
  raiz.querySelectorAll("[data-ex-tentar-msg]").forEach((b) => { b.onclick = () => exAbrir(cx.aberta, true); });
  if (!m || m.uid !== cx.aberta) return;
  exLigarResposta(raiz);
  const encaminharMsg = () => telaEscrever({
    assunto: "Fwd: " + (m.assunto || ""),
    corpo: "\n\n---------- Mensagem encaminhada ----------\nDe: " + (m.de_nome || "") + " <" + m.de_email + ">\nAssunto: " + (m.assunto || "") + "\n\n" + (m.corpo || ""),
  });
  const encaminhar = $("mail-encaminhar-pe");
  if (encaminhar) encaminhar.onclick = encaminharMsg;
  raiz.querySelectorAll("[data-ex-detalhes]").forEach((b) => {
    b.onclick = () => { cx.detalhes = cx.detalhes === m.uid ? null : m.uid; desenharEmail(); };
  });
  const arquivar = $("mail-arquivar");
  if (arquivar) arquivar.onclick = async () => {
    arquivar.disabled = true;
    const prox = exProxima(m.uid);
    if (!(await exArquivar([m.uid]))) { arquivar.disabled = false; return; }
    if (prox) exAbrir(prox.uid, true); else exFechar();
  };
  raiz.querySelectorAll("[data-ex-imprimir]").forEach((b) => { b.onclick = () => exImprimir(m); });
  raiz.querySelectorAll("[data-ex-excluir]").forEach((b) => {
    b.onclick = async () => {
      const prox = exProxima(m.uid);
      if (!(await exExcluir([m.uid]))) return;
      if (prox) exAbrir(prox.uid, true); else desenharEmail();
    };
  });
  raiz.querySelectorAll("[data-ex-nao-lida]").forEach((b) => {
    b.onclick = async () => { if (await exMarcar([m.uid], false)) { avisoCert("marcada como não lida"); exFechar(); } };
  });
  const maisMsg = $("mail-mais-msg");
  if (maisMsg) maisMsg.onclick = (e) => {
    e.stopPropagation();
    const itens = [{ rotulo: "Encaminhar", acao: encaminharMsg }, { rotulo: "Copiar o endereço", acao: () => copiarTexto(m.de_email, "endereço copiado") }];
    const codigo = exCodigo(m);
    if (codigo) itens.unshift({ rotulo: "Copiar o código " + codigo, acao: () => copiarTexto(codigo, "código copiado") });
    if (exLingua(m)) itens.push({ rotulo: "Traduzir para o português", acao: () => exTraduzir(m) });
    if (m.prazo) itens.push({ rotulo: "Virar tarefa", acao: () => criarPrazoDoEmail(m, false) });
    menuNaLinha(maisMsg, itens);
  };
  raiz.querySelectorAll("[data-baixar]").forEach((b) => {
    b.onclick = () => window.open("/api/email/anexo?uid=" + encodeURIComponent(m.uid) + "&nome=" + encodeURIComponent(b.dataset.baixar) +
      (mail.conta ? "&conta_id=" + mail.conta.id : ""), "_blank");
  });
  raiz.querySelectorAll("[data-guardar]").forEach((b) => {
    b.onclick = async () => {
      b.disabled = true;
      const r = await exJson("/api/email/anexo/guardar", { uid: m.uid, nome: b.dataset.guardar, conta_id: mail.conta ? mail.conta.id : "" });
      if (!r.ok) { b.disabled = false; avisoCert(await erroDe(r)); return; }
      const d = await r.json();
      estado.contratos = d.documentos;
      avisoCert("guardado no Acervo como " + d.guardado);
    };
  });
  exLigarEntendi(raiz, m);
  exPedirContexto(m);
  raiz.querySelectorAll("[data-ex-traduzir]").forEach((b) => {
    b.onclick = () => {
      if (cx.tradVista === m.uid) { cx.tradVista = null; exTrocarCorpo(m); return; }
      exTraduzir(m);
    };
  });
  // Mensagem em outra lingua: um aviso discreto, uma vez por mensagem.
  const lingua = exLingua(m);
  cx.avisouTraducao = cx.avisouTraducao || new Set();
  if (lingua && !cx.avisouTraducao.has(m.uid)) {
    cx.avisouTraducao.add(m.uid);
    avisoCert("Mensagem em " + EX_LINGUA[lingua] + " · tradução disponível", { acao: { rotulo: "Traduzir", fazer: () => exTraduzir(m) } });
  }
  exMontarHtml(raiz, m);
  const corpoDaMsg = () => {
    const mod = raiz.querySelector(".ex-mod-corpo");
    if (!mod) return;
    const novo = document.createElement("div");
    novo.innerHTML = exModCorpo(m);
    const trocado = novo.firstElementChild;
    mod.replaceWith(trocado);
    const traducao = trocado.querySelector(".ex-traducao");
    if (traducao && cx.tradAnimar === m.uid && typeof emCascata === "function") emCascata(traducao.children);
    else if (typeof emEsmaecer === "function") emEsmaecer(trocado.querySelector(".ex-mod-miolo"));
    cx.tradAnimar = null;
    raiz.querySelectorAll("[data-ex-traduzir]").forEach((b) => b.classList.toggle("ativo", cx.tradVista === m.uid));
    exLigarCorpo(raiz, m);
  };
  cx.trocarCorpo = corpoDaMsg;
  const exLigarCorpo = (r, msg) => {
    exMontarHtml(r, msg);
    r.querySelectorAll("[data-ex-original]").forEach((b) => { b.onclick = () => { cx.tradVista = null; corpoDaMsg(); }; });
    r.querySelectorAll("[data-ex-imagens]").forEach((b) => {
      b.onclick = () => { cx.imagensLiberadas = cx.imagensLiberadas || new Set(); cx.imagensLiberadas.add(msg.uid); corpoDaMsg(); };
    });
    r.querySelectorAll("[data-ex-so-texto]").forEach((b) => { b.onclick = () => { cx.soTexto = true; corpoDaMsg(); }; });
    r.querySelectorAll("[data-ex-formatado]").forEach((b) => { b.onclick = () => { cx.soTexto = false; corpoDaMsg(); }; });
  };
  exLigarCorpo(raiz, m);
}

/* A caixa liga tudo aqui (18-email.js chama ligarCaixa depois dos botoes do
   cabecalho da tela). */
function ligarCaixa() {
  const raiz = $("email");
  if (!raiz || !raiz.classList.contains("ex-tela")) return;
  const corpo = $("ex-corpo");
  const clique = (sel, fazer) => raiz.querySelectorAll(sel).forEach((b) => { b.onclick = (e) => fazer(b, e); });

  if (corpo && mail.pasta === "entrada") {
    ligarSelecao(corpo, {
      linhas: "[data-ex-uid]", chave: (linha) => linha.dataset.exUid, escolhidos: cx.escolhidos,
      aoMudar: () => desenharEmail(),
      apagar: () => exLote("excluir"),
    });
  }
  clique("[data-ex-uid]", (b) => exAbrir(b.dataset.exUid));
  clique("[data-ex-sel-limpar]", () => { cx.escolhidos.clear(); desenharEmail(); });
  clique("[data-ex-lote]", (b) => exLote(b.dataset.exLote));
  clique("[data-ex-visao]", (b) => exMudarVisao(b.dataset.exVisao));
  clique("[data-ex-pasta]", (b) => exIrPasta(b.dataset.exPasta));
  clique("[data-ex-pastas]", (b, e) => {
    e.stopPropagation();
    menuNaLinha(b, EX_PASTAS.map((p) => {
      const n = exContagemDaPasta(p.id);
      return { rotulo: p.rotulo + (n ? " · " + n : ""), atual: p.id === mail.pasta, acao: () => exIrPasta(p.id) };
    }));
  });
  clique("[data-ex-estrela]", (b, e) => { e.stopPropagation(); exEstrela(b.dataset.exEstrela); });
  clique("[data-ex-mais]", (b, e) => {
    e.stopPropagation();
    const m = (mail.caixa ? mail.caixa.mensagens : []).find((x) => x.uid === b.dataset.exMais);
    if (m) exMenuDaLinha(b, m);
  });
  clique("[data-ex-ir]", (b, e) => { e.stopPropagation(); exAbrir(b.dataset.exIr, true); });
  clique("[data-ex-envio]", (b) => { const i = Number(b.dataset.exEnvio); mail.envioAberto = mail.envioAberto === i ? null : i; desenharEmail(); });
  clique("[data-ex-pedido]", (b) => { mail.pedidoAberto = mail.pedidoAberto === b.dataset.exPedido ? null : b.dataset.exPedido; desenharEmail(); });
  clique("[data-ex-rascunho]", () => telaEscrever());
  clique("[data-em-aprovacoes]", () => { marcarDestino("aprovacoes"); mostrarAprovacoes(); });
  clique("[data-em-escrever-para]", (b) => telaEscrever({ para: b.dataset.emEscreverPara }));
  clique("[data-ex-tentar]", async (b) => { b.disabled = true; await carregarPasta(); desenharEmail(); });
  clique("[data-ex-entrar]", () => exEntrarDeNovo(mail.conta));
  clique("[data-ex-sem-busca]", () => { mail.busca = ""; mostrarEmail("caixa"); });
  clique("[data-ex-conta]", exMenuDaConta);
  const mais = $("mail-mais");
  if (mais) mais.onclick = async () => {
    mais.disabled = true;
    const k = mail.caixa;
    const r = await fetch("/api/email/caixa?filtro=" + mail.filtro + "&antes_de=" + encodeURIComponent(k.ultimo_uid) + "&conta_id=" + mail.conta.id +
      (mail.busca ? "&busca=" + encodeURIComponent(mail.busca) : ""));
    if (!r.ok) { mais.disabled = false; avisoCert(await erroDe(r)); return; }
    const d = await r.json();
    k.mensagens = k.mensagens.concat(d.mensagens);
    k.mostrando += d.mostrando;
    k.nao_lidos += d.nao_lidos || 0;
    k.ultimo_uid = d.ultimo_uid || k.ultimo_uid;
    k.tem_mais = d.tem_mais;
    desenharEmail();
    exPedirResumoDepois();
  };
  const resumo = $("ex-resumo");
  if (resumo) exLigarResumo(resumo);
  exLigarMensagem(raiz);
}

/* --------------------------------------------------------- desenho */

function exSemConta() {
  return '<div class="ec-palco"><section class="ec-cartao">' +
    "<h2>Nenhuma conta conectada</h2><p class=\"ec-lide\">Entre com a sua conta para ver a caixa de entrada.</p>" +
    '<div class="ec-botoes"><button class="primario" data-em-visao="contas">Entrar em uma conta</button></div></section>' + ecRegras() + "</div>";
}

function exDesenhar() {
  cabecalhoEmail();
  const chave = [mail.conta ? mail.conta.id : "", mail.pasta, cx.visao, mail.busca].join(":");
  const antes = document.querySelector("#email.ex-tela .sv-principal");
  const topo = antes ? antes.scrollTop : 0;
  const miolo = mail.conta
    ? '<div class="sv-medida">' + exAbertura() + exTabela() + '<div class="ex-regras">' + ecRegras() + "</div></div>"
    : exSemConta();
  $("centro").innerHTML = '<div class="acervo sem-painel ex-tela" id="email"><div class="acervo-principal sv-principal">' + miolo + "</div></div>";
  ligarEmail();
  const novo = document.querySelector("#email .sv-principal");
  if (novo && antes && chave === cx.chaveTela) novo.scrollTop = topo;
  if (conteudoNovo("email:" + chave)) {
    entraConteudo(novo.firstElementChild);
    entraLista(novo, ".ex-linha");
  }
  cx.chaveTela = chave;
  if (cx.rolarPara) { const u = cx.rolarPara; cx.rolarPara = null; exMostrarLinha(u); }
  if (cx.respRolar && cx.resp) {
    cx.respRolar = false;
    exMostrarResposta();
    if (cx.resp.estado === "escrevendo") exFocarResposta();
  }
  if (mail.pasta === "entrada" && mail.caixa && cx.resumoPara !== mail.caixa) exPedirResumo();
  else exAcompanharResumo();
}

(function () {
  const desenharAntes = desenharEmail;
  window.desenharEmail = function () {
    if (mail.visao !== "caixa") return desenharAntes();
    exDesenhar();
  };
})();
