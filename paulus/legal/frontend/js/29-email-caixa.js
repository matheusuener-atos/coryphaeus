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
  const conta = '<button class="ex-conta" data-ex-conta="1" title="Trocar de conta">' + avatarDaConta(c) + "<span>" + esc(c.email) + "</span>" + ic("expand_more", 16) + "</button>";
  return '<header class="ex-abre"><div class="ex-abre-topo"><span class="sv-kicker">E-mail</span>' + conta + "</div>" +
    '<h1 class="ex-titulo">' + esc(pasta.rotulo) + "</h1>" +
    '<p class="ex-lide">' + esc(exLide()) + (mail.busca ? ' <button class="sv-ligacao" data-ex-sem-busca="1">limpar a busca</button>' : "") + "</p>" +
    (mail.pasta === "entrada" && mail.caixa && mail.caixa.mensagens.length ? '<section class="ex-resumo" id="ex-resumo">' + exResumoMiolo() + "</section>" : "") +
    "</header>";
}

/* ------------------------------------------------------- o resumo */
/*
   Dois blocos, cada um dizendo de onde veio. A regra conta o que esta nos
   cabecalhos e sai na hora (mesmo com o assistente desligado). O assistente
   local le so remetente, assunto e marcas - o corpo das mensagens continua
   no servidor - e escreve em segundo plano; a tela nunca espera por ele.
*/

function exFraseDaRegra(g) {
  const partes = [];
  partes.push("<li><b>" + g.pedem_resposta + "</b> " + (g.pedem_resposta === 1 ? "pede" : "pedem") + " resposta: não lidas ou com prazo, ainda sem resposta.</li>");
  if (g.remetentes.length) {
    partes.push("<li>Quem mais escreveu: " + g.remetentes.map((r) => esc(r.nome) + (r.quantas > 1 ? " (" + r.quantas + ")" : "")).join(", ") + ".</li>");
  }
  if (g.prazos.length) {
    g.prazos.forEach((p) => {
      partes.push('<li>Prazo no assunto: <button class="ex-resumo-prazo" data-ex-ir="' + esc(p.uid) + '"><b>' + esc(dataCurta(p.prazo)) + "</b> · " +
        esc(p.assunto) + "</button> <span class=\"ex-resumo-de\">(" + esc(p.de) + ")</span></li>");
    });
  } else {
    partes.push("<li>Nenhum prazo nos assuntos. O texto de cada mensagem eu confiro quando você abre.</li>");
  }
  const extra = [];
  if (g.de_clientes) extra.push(plural(g.de_clientes, "de cliente do cadastro", "de clientes do cadastro"));
  if (g.com_anexo) extra.push(plural(g.com_anexo, "com anexo", "com anexo"));
  if (extra.length) partes.push("<li>" + maiuscula(extra.join(" · ")) + ".</li>");
  return "<ul>" + partes.join("") + "</ul>";
}

function exFraseDoModelo(m) {
  const e = m ? m.estado : "";
  if (e === "pronto") {
    const hora = (m.quando || "").slice(11, 16);
    return '<p class="ex-resumo-texto">' + esc(m.texto) + "</p>" + (hora ? '<small class="ex-resumo-nota">escrito às ' + esc(hora) + " · confira antes de agir</small>" : "");
  }
  if (e === "resumindo" || e === "na_fila") {
    return '<p class="ex-resumo-texto espera">' + coroa(14) + "<span>resumindo… leva cerca de um minuto nesta máquina. Enquanto isso, vale o resumo por regra.</span></p>";
  }
  if (e === "indisponivel") return '<p class="ex-resumo-texto vazio">O assistente local não está respondendo agora, então fica só o resumo por regra.</p>';
  if (e === "falhou") {
    return '<p class="ex-resumo-texto vazio">Não consegui resumir: ' + esc(m.erro || "sem resposta") + '. <button class="sv-ligacao" data-ex-resumo-de-novo="1">tentar de novo</button></p>';
  }
  return '<p class="ex-resumo-texto vazio">…</p>';
}

function exResumoMiolo() {
  const r = cx.resumo && cx.resumoPara === mail.caixa ? cx.resumo : null;
  const n = mail.caixa ? mail.caixa.mensagens.length : 0;
  return '<div class="ex-resumo-cabeca"><span class="ex-resumo-titulo">Resumo da caixa</span><span class="ex-resumo-onde">das ' +
    plural(n, "mensagem", "mensagens") + " desta página</span></div>" +
    '<div class="ex-resumo-blocos"><div class="ex-resumo-bloco"><span class="ex-selo">' + ic("rule", 14) + "Por regra · na hora</span>" +
    (r && r.regra ? exFraseDaRegra(r.regra) : '<p class="ex-resumo-texto vazio">contando…</p>') + "</div>" +
    '<div class="ex-resumo-bloco"><span class="ex-selo">' + ic("auto_awesome", 14) + "Assistente local · lê só remetente e assunto</span>" +
    exFraseDoModelo(r && r.modelo) + "</div></div>";
}

function exCabecalhosParaResumo() {
  return mail.caixa.mensagens.map((m) => ({
    uid: m.uid, de_nome: m.de_nome, de_email: m.de_email, de_cadastro: m.de_cadastro, assunto: m.assunto,
    prazo: m.prazo, lido: m.lido, respondido: m.respondido, tem_anexo: m.tem_anexo,
  }));
}

async function exPedirResumo() {
  if (mail.pasta !== "entrada" || !mail.caixa || !mail.conta || mail.busca) return;
  const k = mail.caixa;
  cx.resumoPara = k;
  if (!k.mensagens.length) { cx.resumo = null; return; }
  let d;
  try {
    const r = await exJson("/api/email/caixa/resumo", { conta_id: mail.conta.id, mensagens: exCabecalhosParaResumo() });
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

function exLigarResumo(alvo) {
  alvo.querySelectorAll("[data-ex-ir]").forEach((b) => { b.onclick = () => exAbrir(b.dataset.exIr, true); });
  alvo.querySelectorAll("[data-ex-resumo-de-novo]").forEach((b) => { b.onclick = () => { cx.resumo = null; exPintarResumo(); exPedirResumo(); }; });
}

/* --------------------------------------------------------- a lista */

function exAcoesDoLote() {
  return '<button class="com-icone" data-ex-lote="lidas">' + ic("done_all", 16) + "Marcar como lidas</button>" +
    '<button class="com-icone" data-ex-lote="nao-lidas">' + ic("mark_email_unread", 16) + "Como não lidas</button>" +
    '<button class="com-icone" data-ex-lote="arquivar">' + ic("archive", 16) + "Arquivar</button>";
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
  if (n && naEntrada) return barraDeSelecao(n, true, exAcoesDoLote(), "data-ex-sel-limpar", exItens().length);
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
    '<span class="marcar' + (on ? " on" : "") + '" data-ex-marcar="' + esc(m.uid) + '" role="checkbox" aria-checked="' + on + '" title="Marcar">' + ic("check", 12) + "</span>" +
    '<span class="ex-de"><i class="ex-ponto"></i><span class="corta">' + esc(exQuem(m)) + "</span></span>" +
    '<span class="ex-sobre"><b>' + esc(m.assunto || "(sem assunto)") + "</b>" + (trecho ? '<span class="ex-trecho">' + esc(trecho) + "</span>" : "") + "</span>" +
    '<span class="ex-marcas">' + exMarcas(m) + "</span>" +
    '<span class="ex-quando">' + esc(m.quando_curto || "") + "</span>" +
    '<button class="mais-linha" data-ex-mais="' + esc(m.uid) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button></div>" +
    (aberta ? exMensagem(m) : "");
}

function exLinhaSimples(attr, aberta, quem, sobre, marcas, quando) {
  return '<div class="tabela-linha ex-linha' + (aberta ? " aberta" : "") + '" ' + attr + ">" +
    '<span class="marcar"></span><span class="ex-de"><span class="corta">' + esc(quem) + "</span></span>" +
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
  const n = mail.pasta === "entrada" ? cx.escolhidos.size : 0;
  return '<div class="tabela-cartao ex-lista' + (n ? "" : " sem-selecao") + '"><div class="tabela-barra ex-barra">' + exBarra() + "</div>" +
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
  return '<section class="ex-mod' + (classe ? " " + classe : "") + '"><span class="ex-mod-rotulo">' + rotulo + (nota ? "<small>" + nota + "</small>" : "") + "</span>" +
    '<div class="ex-mod-miolo">' + miolo + "</div></section>";
}

function exIcones(m) {
  return '<span class="em-msg-acoes ex-msg-acoes">' +
    (m ? '<button id="mail-responder-ic" title="Responder" aria-label="Responder">' + ic("reply", 18) + "</button>" +
      '<button id="mail-encaminhar" title="Encaminhar" aria-label="Encaminhar">' + ic("forward", 18) + "</button>" +
      '<button data-ex-nao-lida="1" title="Marcar como não lida" aria-label="Marcar como não lida">' + ic("mark_email_unread", 18) + "</button>" +
      '<button id="mail-arquivar" title="Arquivar" aria-label="Arquivar">' + ic("archive", 18) + "</button>" +
      '<button id="mail-mais-msg" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + '</button><span class="divisa-v"></span>' : "") +
    '<button data-ex-fechar="1" title="Fechar (Esc)" aria-label="Fechar">' + ic("close", 18) + "</button></span>";
}

function exCabecaMsg(item, m) {
  const c = mail.conta;
  const quem = esc(item.de_nome || "") + (item.de_nome ? ' <span class="ex-meta-email">&lt;' + esc(item.de_email) + "&gt;</span>" : esc(item.de_email));
  return '<header class="ex-mod ex-mod-cabeca"><div class="ex-cabeca-linha"><h2 class="ex-assunto">' + esc(item.assunto || "(sem assunto)") + "</h2>" + exIcones(m) + "</div>" +
    '<dl class="ex-meta"><div><dt>De</dt><dd>' + quem + (item.de_cadastro ? ' <span class="em-pilula">cliente · ' + esc(item.de_cadastro) + "</span>" : "") + "</dd></div>" +
    "<div><dt>Para</dt><dd>" + esc(c ? c.email : "") + "</dd></div>" +
    "<div><dt>Recebida</dt><dd>" + esc(exDataInteira(m ? m.quando : item.quando, item.quando_curto)) + "</dd></div></dl></header>";
}

function exModEntendi(m) {
  const prazo = m.prazo
    ? '<div class="ex-prazo"><span class="ex-prazo-data"><b>' + esc(m.prazo.slice(8, 10)) + "</b><small>" + esc(dataCurta(m.prazo).split(" ").pop()) + "</small></span>" +
      '<span class="duas-linhas"><b>Prazo detectado · ' + esc(dataLonga(m.prazo)) + "</b>" + (m.prazo_trecho ? "<small>“" + esc(m.prazo_trecho) + "”</small>" : "") + "</span>" +
      '<span class="ex-prazo-acoes"><button class="com-icone" data-em-prazo="agenda">' + ic("event_upcoming", 16) + "Criar na Agenda</button>" +
      '<button class="com-icone" data-em-prazo="tarefa">' + ic("add_task", 16) + "Criar tarefa</button></span></div>"
    : "";
  return exModulo("O que eu entendi", '<p class="ex-mod-texto">' + exEntendi(m) + "</p>" + prazo, "ex-mod-entendi", "por regra, sem o modelo");
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
  const html = m.html && !cx.soTexto;
  if (!html) {
    return exModulo("Mensagem", '<div class="ex-corpo">' + corpoComPrazo(m.corpo, m.prazo_trecho) + "</div>" +
      (m.html ? '<button class="sv-ligacao ex-html-troca" data-ex-formatado="1">ver com a formatação</button>' : ""), "ex-mod-corpo");
  }
  const liberadas = (cx.imagensLiberadas || new Set()).has(m.uid);
  const aviso = m.imagens_remotas && !liberadas
    ? '<div class="ex-html-aviso">' + ic("visibility_off", 15) + "<span>" + plural(m.imagens_remotas, "imagem de fora bloqueada", "imagens de fora bloqueadas") +
      " — carregar avisa o remetente que você abriu.</span>" + '<button class="sv-ligacao" data-ex-imagens="1">mostrar</button></div>'
    : "";
  return exModulo("Mensagem", aviso + '<div class="ex-html"><iframe class="ex-html-quadro" data-ex-html="' + esc(m.uid) + '" title="Mensagem" ' +
    'sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox" referrerpolicy="no-referrer"></iframe></div>' +
    '<button class="sv-ligacao ex-html-troca" data-ex-so-texto="1">ver só o texto</button>', "ex-mod-corpo");
}

function exMontarHtml(raiz, m) {
  const quadro = raiz.querySelector('[data-ex-html="' + CSS.escape(m.uid) + '"]');
  if (!quadro) return;
  const liberadas = (cx.imagensLiberadas || new Set()).has(m.uid);
  const img = liberadas ? "data: https: http:" : "data:";
  /* A CSP e a barreira de verdade: nada de script, nada de fora (salvo as
     imagens, se a pessoa liberou), nada de formulario. */
  const csp = "default-src 'none'; img-src " + img + "; style-src 'unsafe-inline'" + (liberadas ? " https:" : "") +
    "; font-src data:" + (liberadas ? " https:" : "") + "; form-action 'none'; base-uri 'none'";
  /* Claro ou escuro: o e-mail que tem versao escura (media query
     prefers-color-scheme) segue o tema do PAULUS; o que nao tem fica claro,
     como no Gmail - senao o texto escuro dele cairia num fundo escuro. O
     iframe herda o esquema do color-scheme do proprio elemento. */
  const temaEscuro = document.documentElement.getAttribute("data-tema") === "escuro" ||
    (!document.documentElement.getAttribute("data-tema") && matchMedia("(prefers-color-scheme: dark)").matches) ||
    getComputedStyle(document.documentElement).colorScheme === "dark";
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
    "body{padding:16px 0}img{max-width:100%;height:auto}table{max-width:100%}</style></head><body>" +
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
      if (!cor) return;
      doc.documentElement.style.background = cor;
      doc.body.style.background = cor;
      const caixa = quadro.closest(".ex-html");
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
  return exModulo("Resposta", '<div class="ex-resp-botoes"><button class="primario com-icone" id="mail-responder">' + ic("reply", 16) + "Responder</button>" +
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
      exModulo("Mensagem", falhou ? '<p class="ex-mod-texto">Não consegui abrir esta mensagem.</p><div class="ex-vazio-acoes"><button data-ex-tentar-msg="1">Tentar de novo</button></div>'
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
      : '<textarea class="ex-resp-texto" id="ex-resp-texto" placeholder="Escreva a resposta…" rows="6">' + esc(r.corpo) + "</textarea>") +
    (c && c.assinatura ? '<div class="ex-resp-assinatura">' + esc(c.assinatura) + "</div>" : "") +
    (preparando ? "" : '<div class="ex-resp-conferi" id="ex-resp-conferi">' + exConferir(r, m) + "</div>") +
    '<div class="ex-resp-acoes"><button class="sv-ligacao" data-ex-resp-descartar="1">' + ic("delete", 15) + "Descartar</button>" +
    '<button class="sv-ligacao" data-ex-resp-cheia="1">' + ic("fullscreen", 15) + "Tela cheia · anexos</button>" +
    (m.pode_rascunhar && !preparando && !r.corpo.trim() ? '<button class="sv-ligacao" data-ex-resp-rascunho="1">' + ic("auto_awesome", 15) + "Rascunho pelo assistente</button>" : "") +
    '<span class="cresce"></span><button class="primario com-icone" data-ex-resp-enviar="1"' + (preparando || r.estado === "enviando" ? " disabled" : "") + ">" +
    ic("schedule_send", 16) + (r.estado === "enviando" ? "Enviando…" : exSaiSozinho() ? "Enviar" : "Enviar para aprovação") + "</button></div></div>";
}

async function exResponder(comRascunho) {
  const m = mail.aberta;
  if (!m) return;
  const assunto = (m.assunto || "").toLowerCase().startsWith("re:") ? m.assunto : "Re: " + (m.assunto || "");
  const pronto = mail.rascunho && mail.rascunho.uid === m.uid ? mail.rascunho.rascunho : "";
  cx.resp = { uid: m.uid, para: m.de_email, assunto, corpo: comRascunho ? pronto : "", estado: comRascunho && !pronto ? "preparando" : "escrevendo" };
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
    Object.assign(cx.resp, { corpo: d.rascunho, assunto: d.assunto || cx.resp.assunto, estado: "escrevendo" });
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
    t.style.height = "auto"; t.style.height = Math.max(150, t.scrollHeight) + "px";
  }, 0);
}

async function exEnviarResposta() {
  const r = cx.resp;
  if (!r || !r.corpo.trim()) { avisoCert("escreva a resposta antes de enviar"); exFocarResposta(); return; }
  r.estado = "enviando";
  desenharEmail();
  const d = await exMandar({ conta_id: mail.conta ? mail.conta.id : "", para: r.para, cc: "", cco: "", assunto: r.assunto, corpo: r.corpo, anexos: [] });
  if (cx.resp !== r) return;
  if (!d) { r.estado = "escrevendo"; if (mail.visao === "caixa") desenharEmail(); return; }
  r.estado = "enviado"; r.retorno = d;
  await carregarFilaDeEmail();
  cx.respRolar = true;
  if (mail.visao === "caixa") desenharEmail();
}

function exLigarResposta(raiz) {
  const m = mail.aberta;
  ["mail-responder", "mail-responder-ic"].forEach((id) => { const b = $(id); if (b) b.onclick = () => exResponder(false); });
  const comR = $("mail-responder-rascunho");
  if (comR) comR.onclick = () => exResponder(true);
  const r = cx.resp;
  if (!r || !m || r.uid !== m.uid) return;
  const texto = $("ex-resp-texto");
  let relogio;
  if (texto) {
    texto.style.height = "auto"; texto.style.height = Math.max(150, texto.scrollHeight) + "px";
    texto.oninput = () => {
      r.corpo = texto.value;
      texto.style.height = "auto"; texto.style.height = Math.max(150, texto.scrollHeight) + "px";
      clearTimeout(relogio);
      relogio = setTimeout(() => { const alvo = $("ex-resp-conferi"); if (alvo) alvo.innerHTML = exConferir(r, m); }, 500);
    };
  }
  const assunto = $("ex-resp-assunto");
  if (assunto) assunto.oninput = () => { r.assunto = assunto.value; };
  raiz.querySelectorAll("[data-ex-resp-descartar], [data-ex-resp-fechar]").forEach((b) => { b.onclick = () => { cx.resp = null; desenharEmail(); }; });
  raiz.querySelectorAll("[data-ex-resp-cheia]").forEach((b) => { b.onclick = () => { const x = cx.resp; cx.resp = null; telaEscrever({ para: x.para, assunto: x.assunto, corpo: x.corpo }); }; });
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

async function exLote(acao) {
  const uids = exItens().map((m) => m.uid).filter((u) => cx.escolhidos.has(u));
  if (!uids.length) return;
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
  const encaminhar = $("mail-encaminhar");
  if (encaminhar) encaminhar.onclick = () => telaEscrever({
    assunto: "Fwd: " + (m.assunto || ""),
    corpo: "\n\n---------- Mensagem encaminhada ----------\nDe: " + (m.de_nome || "") + " <" + m.de_email + ">\nAssunto: " + (m.assunto || "") + "\n\n" + (m.corpo || ""),
  });
  const arquivar = $("mail-arquivar");
  if (arquivar) arquivar.onclick = async () => {
    arquivar.disabled = true;
    const prox = exProxima(m.uid);
    if (!(await exArquivar([m.uid]))) { arquivar.disabled = false; return; }
    if (prox) exAbrir(prox.uid, true); else exFechar();
  };
  raiz.querySelectorAll("[data-ex-nao-lida]").forEach((b) => {
    b.onclick = async () => { if (await exMarcar([m.uid], false)) { avisoCert("marcada como não lida"); exFechar(); } };
  });
  const maisMsg = $("mail-mais-msg");
  if (maisMsg) maisMsg.onclick = (e) => {
    e.stopPropagation();
    const itens = [{ rotulo: "Copiar o endereço", acao: () => copiarTexto(m.de_email, "endereço copiado") }];
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
  raiz.querySelectorAll("[data-em-prazo]").forEach((b) => { b.onclick = () => criarPrazoDoEmail(m, b.dataset.emPrazo === "agenda"); });
  exMontarHtml(raiz, m);
  const corpoDaMsg = () => {
    const mod = raiz.querySelector(".ex-mod-corpo");
    if (!mod) return;
    const novo = document.createElement("div");
    novo.innerHTML = exModCorpo(m);
    mod.replaceWith(novo.firstElementChild);
    exLigarCorpo(raiz, m);
  };
  const exLigarCorpo = (r, msg) => {
    exMontarHtml(r, msg);
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
    });
  }
  clique("[data-ex-uid]", (b) => exAbrir(b.dataset.exUid));
  clique("[data-ex-marcar]", (b, e) => {
    e.stopPropagation();
    const u = b.dataset.exMarcar;
    if (cx.escolhidos.has(u)) cx.escolhidos.delete(u); else cx.escolhidos.add(u);
    desenharEmail();
  });
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
  clique("[data-ex-conta]", (b, e) => {
    e.stopPropagation();
    menuNaLinha(b, mail.contas.contas.map((c) => ({
      atual: !!(mail.conta && c.id === mail.conta.id),
      rotulo: c.email + (exPrecisaEntrar(c) ? " · entrar de novo" : ""),
      acao: () => exTrocarConta(c),
    })).concat(["-", { rotulo: "Gerenciar contas", acao: () => mostrarEmail("contas") }]));
  });
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
  return '<div class="ec-palco"><section class="ec-cartao"><div class="ec-marca"><img src="img/paulus-icone.svg" alt=""><span>PAULUS · E-mail</span></div>' +
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
