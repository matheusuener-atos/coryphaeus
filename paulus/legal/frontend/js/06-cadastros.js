/* ---------------------------------------------------------- cadastros */
/*
   Cadastros (docs/ui/03-telas-desktop.md, A10): Clientes, Equipe e Despesas
   fixas, cada uma uma tabela na medida editorial das outras telas (Servicos,
   E-mail) - sem coluna ao lado. A ficha abre em pop-up de exibicao (o mesmo
   do compromisso da Agenda: ver, e Editar leva ao cadastro); novo e editar
   abrem no pop-up de cadastro (docs/ui/05). O que o desenho pede e ainda nao
   tem motor - acesso por pasta, papeis e alcadas por pessoa, importar e
   exportar - diz isso na tela.

   Acima dos clientes, a sugestao de cadastro: quem a leitura do Acervo achou
   nos contratos e ainda nao tem ficha, uma por vez. Cadastrar abre o
   cadastro ja preenchido com o que foi lido (conferir, nao digitar);
   Ignorar tira o nome de vez (data/cadastros_ignorados.json). Sem sugestao,
   o cartao oferece o levantamento: ler os documentos do Acervo que ainda nao
   foram lidos.
*/

const cad = {
  visao: "clientes", fichas: [], contagem: {}, tipos: [], sugestoes: [], sugTotal: 0, sugIndice: 0,
  ignorados: 0, levantamento: { documentos: 0, faltam: 0 }, lendo: null,
  lancamentos: [], tarefas: [], termo: "", ordem: "nome", filtro: "todos",
  aberta: null, form: null, escolhidas: new Set(),
};

const CAD_JSON = { "Content-Type": "application/json" };

const CAD_VINCULOS = [["", "não entra na folha"], ["clt", "CLT"], ["estagio", "Estágio"], ["prolabore", "Pró-labore"], ["autonomo", "Autônomo"]];

/* O que cada papel vai poder quando a equipe existir de verdade. Hoje uma
   pessoa so usa o PAULUS nesta maquina, e ela pode tudo. */
const CAD_PAPEIS = {
  socio: [
    [true, "Aprovar envios, pagamentos e assinaturas"], [true, "Ver e editar todas as pastas"],
    [true, "Convidar e alterar papéis da equipe"], [true, "Ver o Financeiro completo"],
  ],
  colaborador: [
    [true, "Ver e editar as pastas liberadas para ela"], [true, "Pedir envios e pagamentos pela fila de Aprovações"],
    [false, "Aprovar o que sai do escritório"], [false, "Ver o Financeiro completo"],
  ],
};

async function mostrarCadastros(visao) {
  if (visao) cad.visao = visao;
  abrirTela("Cadastros", { cheia: true });
  marcarDestino("cadastros");
  if (!document.getElementById("cad-tela")) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal">' + esqueleto("lista") + '</div></div>';
  }
  atualizarPostura();
  try {
    const [d, g, l, t] = await Promise.all([
      fetch("/api/cadastros?tipo=&termo=" + encodeURIComponent(cad.termo) + "&ordem=" + encodeURIComponent(cad.ordem)).then((r) => r.json()),
      fetch("/api/cadastros/sugestoes").then((r) => r.json()),
      fetch("/api/financeiro/lancamentos?tipo=&mes=&situacao=").then((r) => r.json()),
      fetch("/api/tarefas?filtro=abertas").then((r) => r.json()),
    ]);
    cad.fichas = d.fichas || [];
    cad.contagem = d.contagem || {};
    cad.tipos = d.tipos || [];
    cad.sugestoes = g.sugestoes || [];
    cad.sugTotal = g.total || cad.sugestoes.length;
    cad.ignorados = g.ignorados || 0;
    cad.levantamento = g.levantamento || { documentos: 0, faltam: 0 };
    cad.lancamentos = l.lancamentos || [];
    cad.tarefas = t.tarefas || [];
    if (cad.aberta) cad.aberta = cad.fichas.find((f) => f.id === cad.aberta.id) || null;
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' +
      esc(String(err)) + "</p></div></div>";
    return;
  }
  desenharCadastros();
}

function desenharCadastros() {
  cabecalhoCadastros();
  let miolo;
  if (cad.visao === "equipe") miolo = corpoDaEquipe();
  else if (cad.visao === "despesas") miolo = corpoDasDespesas();
  else miolo = corpoDosClientes();
  const antes = document.querySelector("#cad-tela .sv-principal");
  const topo = antes && antes.dataset.cadVisao === cad.visao ? antes.scrollTop : 0;
  $("centro").innerHTML = '<div class="acervo sem-painel cad-tela" id="cad-tela">' +
    '<div class="acervo-principal sv-principal" data-cad-visao-tela="' + cad.visao + '"><div class="sv-medida">' + miolo + "</div></div></div>";
  const depois = document.querySelector("#cad-tela .sv-principal");
  if (depois) {
    depois.dataset.cadVisao = cad.visao;
    if (topo) depois.scrollTop = topo;
  }
  if (conteudoNovo("cadastros:" + cad.visao) && depois) {
    entraConteudo(depois.firstElementChild);
    entraLista(depois, ".tabela-linha");
  }
  ligarCadastros();
  atualizarPostura();
}

/* ------------------------------------------------------ o cabecalho */

function cabecalhoCadastros() {
  const c = cad.contagem;
  const titulo = $("conversa-titulo");
  const meta = $("conversa-meta");
  const equipe = (c.colaborador || 0) + (c.socio || 0);
  if (cad.visao === "equipe") {
    titulo.textContent = "Equipe";
    meta.textContent = plural(c.socio || 0, "sócio") + " · " + plural(c.colaborador || 0, "colaborador", "colaboradores") +
      " · máquinas na rede e pedidos de acesso em breve";
  } else if (cad.visao === "despesas") {
    const total = fichasDaVisao().reduce((s, f) => s + centavosDe(f.honorario), 0);
    titulo.textContent = "Despesas fixas";
    meta.textContent = plural(c.despesa || 0, "despesa") + " · " + emReais(total) + " por mês";
  } else {
    titulo.textContent = "Cadastros";
    meta.textContent = plural(c.cliente || 0, "cliente") + " · " + equipe + " na equipe · " + plural(c.despesa || 0, "despesa fixa", "despesas fixas");
  }
  const botao = (v, r) => {
    const classe = v === cad.visao ? "ativa" : "";
    return '<button class="' + classe + '" data-cad-visao="' + v + '">' + r + "</button>";
  };
  let novo;
  if (cad.visao === "equipe") novo = ic("person_add", 16) + "Nova pessoa";
  else if (cad.visao === "despesas") novo = ic("add", 16) + "Nova despesa";
  else novo = ic("person_add", 16) + "Novo cliente";
  $("acoes-tela").innerHTML =
    '<label class="busca-tela">' + ic("search", 18) + '<input type="text" id="cad-busca" placeholder="Buscar nome, CPF/CNPJ ou e-mail…" value="' + esc(cad.termo) + '"></label>' +
    '<div class="visoes">' + botao("clientes", "Clientes") + botao("equipe", "Equipe") + botao("despesas", "Despesas fixas") + "</div>" +
    '<button class="primario com-icone" data-cad-nova="1">' + novo + "</button>";
  $("nav-tela").innerHTML = "";
}

/* --------------------------------------------------------- miudezas */

function fichasDaVisao() {
  if (cad.visao === "equipe") return cad.fichas.filter((f) => f.tipo === "colaborador" || f.tipo === "socio");
  if (cad.visao === "despesas") return cad.fichas.filter((f) => f.tipo === "despesa");
  return cad.fichas.filter((f) => f.tipo === "cliente");
}

function visaoDoTipo(tipo) {
  if (tipo === "colaborador" || tipo === "socio") return "equipe";
  if (tipo === "despesa") return "despesas";
  return "clientes";
}

function digitosDoDocumento(f) { return String(f.documento || "").replace(/\D/g, ""); }
function pessoaFisica(f) { const n = digitosDoDocumento(f).length; return n > 0 && n <= 11; }
function pessoaJuridica(f) { return digitosDoDocumento(f).length === 14; }
function lancamentosDe(f) { return cad.lancamentos.filter((l) => l.cadastro_id === f.id); }
function prazosDe(f) { return cad.tarefas.filter((t) => t.cadastro_id === f.id && !t.concluida); }
function folhaDe(f) { return f.vinculo ? (f.salario_centavos || 0) + (f.encargos_centavos || 0) : 0; }

function rotuloDoVinculo(v) {
  const achado = CAD_VINCULOS.find((x) => x[0] === v);
  return achado ? achado[1] : "";
}

function rotuloDoDocumento(doc) {
  const n = String(doc || "").replace(/\D/g, "").length;
  if (n === 14) return "CNPJ";
  if (n === 11) return "CPF";
  return "Documento";
}

function vazioDosCadastros(total) {
  if (cad.termo) return "Nenhuma ficha com “" + cad.termo + "”.";
  if (total) return "Nenhuma ficha com este filtro.";
  if (cad.visao === "equipe") return "Ninguém na equipe ainda. Quem tem vínculo definido entra na folha de pagamento do Financeiro.";
  if (cad.visao === "despesas") return "Nenhuma despesa fixa ainda. Aluguel, contabilidade, sistemas: cadastre para acompanhar o mês no Financeiro.";
  return "Nenhum cliente ainda. Cadastre pelo botão Novo cliente — ou confira um dos nomes lidos nos contratos, acima.";
}

function menuDaLinha(id) {
  return '<button class="mais-linha" data-cad-mais="' + id + '" title="Mais">' + ic("more_horiz", 18) + "</button>";
}

/* ------------------------------------------- a sugestao de cadastro */
/*
   Uma sugestao por vez, como um carrossel: o nome lido, onde apareceu e as
   duas saidas - cadastrar (o pop-up ja preenchido) ou ignorar (nao volta).
   As setas so passam, sem decidir nada. Durante a busca o cartao sai: quem
   busca procura uma ficha, nao uma sugestao.
*/

function cartaoDeSugestao() {
  if (cad.termo) return "";
  return '<section class="cad-sug" id="cad-sug" aria-label="Sugestão de cadastro">' + corpoDaSugestao() + "</section>";
}

function corpoDaSugestao() {
  if (cad.lendo) return sugestaoLendo();
  const lista = cad.sugestoes;
  if (!lista.length) return sugestaoVazia();
  if (cad.sugIndice >= lista.length) cad.sugIndice = lista.length - 1;
  if (cad.sugIndice < 0) cad.sugIndice = 0;
  const x = lista[cad.sugIndice];
  const n = lista.length;
  const faltam = cad.levantamento.faltam || 0;
  const doc = x.documento ? rotuloDoDocumento(x.documento) + " " + x.documento : "sem CPF/CNPJ no documento";
  const arquivos = (x.arquivos || []).slice(0, 2).map((a) => a.nome);
  const resto = Math.max(0, (x.aparicoes || 0) - arquivos.length);
  const prova = arquivos.length
    ? "Em " + arquivos.join(", ") + (resto ? " e mais " + plural(resto, "documento") : "")
    : "";
  const anterior = '<button class="botao-icone" data-cad-sug-anterior="1" title="Anterior" aria-label="Sugestão anterior"' + (n < 2 ? " disabled" : "") + ">" + ic("chevron_left", 18) + "</button>";
  const proxima = '<button class="botao-icone" data-cad-sug-proxima="1" title="Próxima" aria-label="Próxima sugestão"' + (n < 2 ? " disabled" : "") + ">" + ic("chevron_right", 18) + "</button>";
  const alem = cad.sugTotal > n ? " · mostrando os " + n + " que mais aparecem" : "";
  return '<div class="cad-sug-topo"><span class="sv-kicker">Lido nos contratos, ainda sem ficha</span>' +
    (faltam ? '<button class="sv-ligacao" data-cad-levantar="1" title="Ler os documentos do Acervo que ainda não foram lidos">' + ic("search", 16) +
      "Ler " + plural(faltam, "documento novo", "documentos novos") + "</button>" : "") +
    '<span class="cad-sug-nav">' + anterior + '<span class="cad-sug-conta">' + (cad.sugIndice + 1) + " de " + cad.sugTotal + "</span>" + proxima + "</span></div>" +
    '<div class="cad-sug-corpo"><div class="cad-sug-quem">' +
    '<h3 class="cad-sug-nome">' + esc(x.nome) + "</h3>" +
    '<p class="cad-sug-meta">' + esc(doc + " · aparece em " + plural(x.aparicoes || 0, "documento") + alem) + "</p>" +
    (prova ? '<p class="cad-sug-prova">' + esc(prova) + "</p>" : "") + "</div>" +
    '<div class="cad-sug-acoes">' +
    '<button data-cad-sug-ignorar="1" title="Não sugerir mais este nome">Ignorar</button>' +
    '<button class="primario com-icone" data-cad-sug-cadastrar="1">' + ic("person_add", 16) + "Cadastrar</button></div></div>";
}

function sugestaoVazia() {
  const lev = cad.levantamento || {};
  const docs = lev.documentos || 0;
  const faltam = lev.faltam || 0;
  let texto;
  if (!docs) texto = "O Acervo ainda não tem documentos. Quando tiver, o levantamento lê cada um e traz quem assina e ainda não tem ficha.";
  else if (faltam) texto = plural(faltam, "documento", "documentos") + " do Acervo ainda não " + (faltam === 1 ? "foi lido" : "foram lidos") +
    ". O levantamento lê " + (faltam === 1 ? "esse documento" : "esses documentos") + " e traz quem assina e ainda não tem ficha.";
  else texto = (docs === 1 ? "O documento do Acervo já foi lido" : "Os " + docs + " documentos do Acervo já foram lidos") +
    " e cada nome achado tem ficha" + (cad.ignorados ? " ou foi ignorado" : "") + ". O levantamento lê o que tiver entrado no Acervo desde então.";
  return '<div class="cad-sug-vazio"><span class="cad-sug-texto"><b>Nenhum nome novo para cadastrar</b><small>' + esc(texto) + "</small></span>" +
    '<button class="com-icone" data-cad-levantar="1">' + ic("search", 16) + "Fazer levantamento</button></div>";
}

function sugestaoLendo() {
  const l = cad.lendo;
  const pct = l.total ? Math.round((l.indice / l.total) * 100) : 0;
  const texto = l.total ? "Lendo " + l.indice + " de " + l.total + (l.nome ? " — " + l.nome : "") : "Conferindo os documentos do Acervo…";
  return '<div class="cad-sug-vazio"><span class="cad-sug-texto"><b>Fazendo o levantamento</b><small>' + esc(texto) + "</small>" +
    '<span class="cad-sug-fita"><i style="width:' + pct + '%"></i></span></span>' +
    '<button data-cad-levantar-parar="1"' + (l.parando ? " disabled" : "") + ">" + (l.parando ? "Parando…" : "Parar") + "</button></div>";
}

/* Redesenha so o cartao, sem mexer na tabela (a leitura manda andamento a
   cada documento). Fora da tela de Cadastros, nao faz nada. */
function redesenharSugestao() {
  const caixa = document.getElementById("cad-sug");
  if (!caixa) return;
  caixa.innerHTML = corpoDaSugestao();
  ligarCartaoSugestao(caixa);
}

function ligarCartaoSugestao(raiz) {
  const clique = (seletor, fn) => raiz.querySelectorAll(seletor).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b); }; });
  const n = cad.sugestoes.length;
  clique("[data-cad-sug-anterior]", () => { cad.sugIndice = (cad.sugIndice - 1 + n) % n; redesenharSugestao(); });
  clique("[data-cad-sug-proxima]", () => { cad.sugIndice = (cad.sugIndice + 1) % n; redesenharSugestao(); });
  clique("[data-cad-sug-cadastrar]", () => cadastrarSugestao(cad.sugestoes[cad.sugIndice]));
  clique("[data-cad-sug-ignorar]", () => ignorarSugestao(cad.sugestoes[cad.sugIndice]));
  clique("[data-cad-levantar]", () => fazerLevantamento());
  clique("[data-cad-levantar-parar]", async () => {
    if (!cad.lendo) return;
    cad.lendo.parando = true;
    redesenharSugestao();
    await fetch("/api/organizar/cancelar", { method: "POST" });
  });
}

function cadastrarSugestao(x) {
  if (!x) return;
  cad.aberta = null;
  cad.form = Object.assign(formDaFicha({ tipo: "cliente" }), { nome: x.nome, documento: x.documento || "", _sugestao: x });
  abrirFormCad();
}

async function ignorarSugestao(x) {
  if (!x) return;
  const r = await fetch("/api/cadastros/sugestoes/ignorar", { method: "POST", headers: CAD_JSON, body: JSON.stringify({ nome: x.nome }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const i = cad.sugestoes.indexOf(x);
  if (i >= 0) cad.sugestoes.splice(i, 1);
  cad.sugTotal = Math.max(0, cad.sugTotal - 1);
  cad.ignorados += 1;
  // O indice fica onde estava: a proxima sugestao ocupa o lugar da ignorada.
  if (cad.sugIndice >= cad.sugestoes.length) cad.sugIndice = 0;
  redesenharSugestao();
  avisoCert(x.nome + " não será mais sugerido", {
    tom: "ok",
    acao: {
      rotulo: "Desfazer",
      fazer: async () => {
        const d = await fetch("/api/cadastros/sugestoes/desfazer", { method: "POST", headers: CAD_JSON, body: JSON.stringify({ nome: x.nome }) });
        if (!d.ok) { avisoCert(await erroDe(d), { tom: "erro" }); return; }
        if (document.getElementById("cad-tela")) mostrarCadastros();
      },
    },
  });
}

/* O levantamento: le no servidor os documentos do Acervo que ainda nao
   foram lidos (a mesma leitura do Acervo) e, no fim, as sugestoes vem de
   novo. O andamento e o numero de documentos prontos, contado. */
async function fazerLevantamento() {
  if (cad.lendo) return;
  cad.lendo = { indice: 0, total: 0, nome: "" };
  redesenharSugestao();
  let novos = 0;
  let fim = null;
  let erro = "";
  try {
    const r = await fetch("/api/cadastros/levantamento", { method: "POST" });
    if (!r.ok) throw new Error(await erroDe(r));
    await lerEventos(r, (tipo, d) => {
      if (tipo === "inicio") { novos = d.novos || 0; cad.lendo.total = novos; redesenharSugestao(); }
      else if (tipo === "progresso") { Object.assign(cad.lendo, { indice: d.indice, total: d.total, nome: d.nome || "" }); redesenharSugestao(); }
      else if (tipo === "erro") erro = d.mensagem || "não deu certo";
      else if (tipo === "fim") fim = d;
    });
  } catch (err) {
    erro = err && err.message ? err.message : String(err);
  }
  cad.lendo = null;
  if (erro) avisoCert("não consegui fazer o levantamento: " + erro, { tom: "erro" });
  else if (fim) avisoCert(fraseDoLevantamento(novos, fim), { tom: "ok" });
  cad.sugIndice = 0;
  if (document.getElementById("cad-tela")) mostrarCadastros();
}

function fraseDoLevantamento(novos, d) {
  const achados = d.novas
    ? plural(d.novas, "nome novo", "nomes novos") + " para conferir"
    : (d.sugestoes ? "nenhum nome novo além dos que já estavam na fila" : "nenhum nome novo sem ficha");
  if (d.parado) return "levantamento parado: li " + plural(d.lidos, "documento") + " — " + achados;
  if (!novos) {
    if (!d.total) return "o Acervo não tem documentos para ler";
    return (d.total === 1 ? "o documento do Acervo já tinha sido lido" : "os " + d.total + " documentos do Acervo já tinham sido lidos") + " — " + achados;
  }
  // O que nao deu para ler (sem texto, sem acesso) continua contado como
  // por ler - e dito aqui, para o numero do cartao nao parecer engano.
  const falhou = Math.max(0, novos - (d.lidos || 0));
  return "li " + plural(d.lidos, "documento novo", "documentos novos") +
    (falhou ? " (" + plural(falhou, "não deu para ler", "não deram para ler") + ")" : "") + " — " + achados;
}

/* ------------------------------------------------------- os clientes */

function corpoDosClientes() {
  const todas = fichasDaVisao();
  const contagem = {
    todos: todas.length, pj: todas.filter(pessoaJuridica).length, pf: todas.filter(pessoaFisica).length,
    atraso: todas.filter((f) => f.atraso_dias > 0).length,
  };
  let lista = todas;
  if (cad.filtro === "pj") lista = todas.filter(pessoaJuridica);
  else if (cad.filtro === "pf") lista = todas.filter(pessoaFisica);
  else if (cad.filtro === "atraso") lista = todas.filter((f) => f.atraso_dias > 0);
  const chip = (v, r) => {
    const classe = v === cad.filtro ? "ativa" : "";
    return '<button class="' + classe + '" data-cad-filtro="' + v + '">' + r + " · " + contagem[v] + "</button>";
  };
  const ordens = { nome: "A–Z", aberto: "Em aberto", atraso: "Atraso" };
  return cartaoDeSugestao() +
    '<div class="tabela-cartao cad-lista">' +
    '<div class="tabela-barra cad-barra">' + barraCad(chip("todos", "Todos") + chip("pj", "Pessoa jurídica") + chip("pf", "Pessoa física") + chip("atraso", "Com atraso")) +
    '<div class="direita"><button data-cad-ordem="1">' + ic("swap_vert", 16) + esc(ordens[cad.ordem] || "A–Z") + "</button>" +
    '<button class="adiante" data-cad-importar="1">' + ic("upload", 16) + "Importar</button>" +
    '<button class="adiante" data-cad-exportar="1">' + ic("download", 16) + "Exportar</button></div></div>" +
    '<div class="tabela-cabecalho colunas-clientes"><span>Nome e documento</span><span>Contato</span><span>Ligado a</span><span class="fin-num">Em aberto</span><span></span></div>' +
    '<div class="tabela-corpo">' + (lista.length ? lista.map(linhaDeCliente).join("") : '<p class="rel-vazio">' + esc(vazioDosCadastros(todas.length)) + "</p>") + "</div>" +
    '<div class="tabela-rodape"><span>' + lista.length + " de " + todas.length + "</span></div></div>";
}

function linhaDeCliente(f) {
  const classe = "tabela-linha colunas-clientes" + (cad.escolhidas.has(String(f.id)) ? " escolhida" : "");
  const n = digitosDoDocumento(f).length;
  const tipoDoc = n === 14 ? "CNPJ " : (n ? "CPF " : "");
  const sub = [f.atraso_dias ? "Atrasado " + plural(f.atraso_dias, "dia") : "", f.documento ? tipoDoc + f.documento : "", pessoaFisica(f) ? "pessoa física" : ""]
    .filter(Boolean).join(" · ") || "sem documento";
  const classeSub = f.atraso_dias ? "cad-atrasado" : "";
  const contato = [f.telefone, f.email].filter(Boolean).join(" · ") || "—";
  const docs = (f.documentos || []).length;
  const prazos = prazosDe(f).length;
  const ligado = [docs ? plural(docs, "doc") : "", f.aberto_quantos ? plural(f.aberto_quantos, "cobrança") : "", prazos ? plural(prazos, "prazo") : ""].filter(Boolean);
  const classeValor = "fin-valor fin-valor-col" + (f.aberto_centavos ? "" : " cad-zero");
  return '<div class="' + classe + '" data-cad-abrir="' + f.id + '" data-sel="' + f.id + '">' +
    '<span class="cad-nome"><span class="cad-avatar">' + esc(iniciaisDoRemetente(f.nome)) + '</span><span class="duas-linhas"><b>' + esc(f.nome) + '</b><small class="' + classeSub + '">' + esc(sub) + "</small></span></span>" +
    '<span class="cad-contato">' + esc(contato) + "</span>" +
    '<span class="cad-ligado">' + (ligado.length ? ligado.map((x) => "<span>" + esc(x) + "</span>").join("") : "<small>sem vínculo</small>") + "</span>" +
    '<span class="' + classeValor + '">' + esc(f.aberto_centavos ? semReais(f.aberto) : "—") + "</span>" +
    menuDaLinha(f.id) + "</div>";
}

/* --------------------------------------------------------- a equipe */

function corpoDaEquipe() {
  const todas = fichasDaVisao();
  const contagem = { todos: todas.length, socio: todas.filter((f) => f.tipo === "socio").length, colaborador: todas.filter((f) => f.tipo === "colaborador").length };
  let lista = todas;
  if (cad.filtro === "socio" || cad.filtro === "colaborador") lista = todas.filter((f) => f.tipo === cad.filtro);
  const chip = (v, r) => {
    const classe = v === cad.filtro ? "ativa" : "";
    return '<button class="' + classe + '" data-cad-filtro="' + v + '">' + r + " · " + contagem[v] + "</button>";
  };
  const folha = todas.reduce((s, f) => s + folhaDe(f), 0);
  return '<div class="tabela-cartao cad-lista">' +
    '<div class="tabela-barra cad-barra">' + barraCad(chip("todos", "Todos") + chip("socio", "Sócios") + chip("colaborador", "Colaboradores")) +
    '<div class="direita"><button data-cad-regras="1">' + ic("shield_person", 16) + "Papéis e alçadas</button></div></div>" +
    '<div class="tabela-cabecalho colunas-equipe"><span>Nome e função</span><span>Papel</span><span>Acesso por pasta</span><span class="fin-num">Na folha</span><span></span></div>' +
    '<div class="tabela-corpo">' + (lista.length ? lista.map(linhaDaEquipe).join("") : '<p class="rel-vazio">' + esc(vazioDosCadastros(todas.length)) + "</p>") + "</div>" +
    '<div class="tabela-rodape"><span>' + esc(plural(todas.length, "pessoa")) + " · folha " + esc(emReais(folha)) + "</span>" +
    '<span class="cad-rodape-nota">Alterar papel ou acesso passa por Aprovações · em breve</span></div></div>';
}

function linhaDaEquipe(f) {
  const classe = "tabela-linha colunas-equipe" + (cad.escolhidas.has(String(f.id)) ? " escolhida" : "");
  const socio = f.tipo === "socio";
  const classePapel = "cad-pill" + (socio ? " forte" : "");
  const sub = [f.observacao, rotuloDoVinculo(f.vinculo) === "não entra na folha" ? "" : rotuloDoVinculo(f.vinculo)].filter(Boolean).join(" · ") || (f.documento ? "CPF " + f.documento : "sem função anotada");
  const folha = folhaDe(f);
  const classeValor = "fin-valor fin-valor-col" + (folha ? "" : " cad-zero");
  return '<div class="' + classe + '" data-cad-abrir="' + f.id + '" data-sel="' + f.id + '">' +
    '<span class="cad-nome"><span class="cad-avatar">' + esc(iniciaisDoRemetente(f.nome)) + '</span><span class="duas-linhas"><b>' + esc(f.nome) + "</b><small>" + esc(sub) + "</small></span></span>" +
    '<span><span class="' + classePapel + '">' + (socio ? "Sócio" : "Colaborador") + "</span></span>" +
    '<span class="cad-ligado"><small title="Acesso por pasta ainda não existe: hoje o PAULUS é de uma pessoa só, nesta máquina">em breve</small></span>' +
    '<span class="' + classeValor + '">' + esc(folha ? semReais(emReais(folha)) : "—") + "</span>" +
    menuDaLinha(f.id) + "</div>";
}

/* ------------------------------------------------------- as despesas */

function situacaoDaDespesa(f) {
  const mes = mesDeHoje();
  const doMes = lancamentosDe(f).filter((l) => mesDoLancamento(l) === mes);
  if (doMes.some((l) => !l.aberto)) return { classe: "pago", texto: "Pago" };
  const atrasado = doMes.find((l) => l.atrasado);
  if (atrasado) return { classe: "atrasado", texto: "Atrasado " + atrasado.dias_atraso + " d" };
  if (doMes.length) return { classe: "aberto", texto: "Agendado" };
  return { classe: "nada", texto: "Nada lançado" };
}

function corpoDasDespesas() {
  const todas = fichasDaVisao();
  const contagem = { todos: todas.length, dia: todas.filter((f) => f.dia_vencimento > 0).length, semdia: todas.filter((f) => !f.dia_vencimento).length };
  let lista = todas;
  if (cad.filtro === "dia") lista = todas.filter((f) => f.dia_vencimento > 0);
  else if (cad.filtro === "semdia") lista = todas.filter((f) => !f.dia_vencimento);
  const chip = (v, r) => {
    const classe = v === cad.filtro ? "ativa" : "";
    return '<button class="' + classe + '" data-cad-filtro="' + v + '">' + r + " · " + contagem[v] + "</button>";
  };
  const total = lista.reduce((s, f) => s + centavosDe(f.honorario), 0);
  return '<div class="tabela-cartao cad-lista">' +
    '<div class="tabela-barra cad-barra">' + barraCad(chip("todos", "Todas") + chip("dia", "Com dia certo") + chip("semdia", "Sem dia")) +
    '<div class="direita"><button class="adiante" data-cad-exportar="1">' + ic("download", 16) + "Exportar</button></div></div>" +
    '<div class="tabela-cabecalho colunas-despesas"><span>Despesa</span><span>Fornecedor</span><span>Vence</span><span class="fin-num">Valor</span><span>' +
    esc(maiuscula(mesCurto(mesDeHoje()))) + "</span><span></span></div>" +
    '<div class="tabela-corpo">' + (lista.length ? lista.map(linhaDaDespesa).join("") : '<p class="rel-vazio">' + esc(vazioDosCadastros(todas.length)) + "</p>") + "</div>" +
    '<div class="tabela-rodape"><span>' + lista.length + " de " + todas.length + " · " + esc(emReais(total)) + ' no mês</span>' +
    '<span class="cad-rodape-nota"><button class="em-ligacao forte" data-cad-financeiro="1">Ver no Financeiro →</button></span></div></div>';
}

function linhaDaDespesa(f) {
  const classe = "tabela-linha colunas-despesas" + (cad.escolhidas.has(String(f.id)) ? " escolhida" : "");
  const s = situacaoDaDespesa(f);
  const classeStatus = "fin-status " + s.classe;
  const valor = centavosDe(f.honorario);
  const classeValor = "fin-valor fin-valor-col" + (valor ? "" : " cad-zero");
  return '<div class="' + classe + '" data-cad-abrir="' + f.id + '" data-sel="' + f.id + '">' +
    '<span class="duas-linhas"><b>' + esc(f.nome) + "</b><small>" + esc(f.observacao || rotuloDoFornecedor(f) || "sem anotação") + "</small></span>" +
    '<span class="cad-texto">' + esc(rotuloDoFornecedor(f) || "—") + "</span>" +
    '<span class="cad-texto">' + esc(f.dia_vencimento ? "dia " + f.dia_vencimento : "—") + "</span>" +
    '<span class="' + classeValor + '">' + esc(valor ? semReais(emReais(valor)) : "—") + "</span>" +
    '<span class="' + classeStatus + '"><i></i>' + esc(s.texto) + "</span>" +
    menuDaLinha(f.id) + "</div>";
}

function rotuloDoFornecedor(f) {
  return f.documento || f.email || f.telefone || "";
}

/* ------------------------------------------- a ficha, em pop-up de ver */
/*
   Clicar numa linha abre a ficha no pop-up de exibicao, como o compromisso
   da Agenda: os dados, o que esta ligado e as acoes do que se ve; Editar
   leva ao pop-up de cadastro. A tabela tem cinco colunas estreitas - abrir a
   ficha dentro da linha empurraria as outras e repetiria o que ja esta nela.
*/

function verFicha(id) {
  const f = cad.fichas.find((x) => x.id === id);
  if (!f) return;
  cad.aberta = f;
  const p = partesDaFicha(f);
  const escolha = dialogo({
    titulo: f.nome, contexto: p.contexto, classe: "dialogo-ver cad-dialogo", larga: true,
    html: p.corpo, rodape: '<button type="button" class="dialogo-excluir" data-cad-apagar="1">Apagar</button>',
    cancelar: "Fechar", confirmar: "Editar",
  });
  const dlg = document.querySelector(".dialogo.cad-dialogo");
  if (dlg) ligarFichaVista(dlg, f);
  escolha.then((r) => { if (r && r.ok) editarFicha(f); });
}

function partesDaFicha(f) {
  const equipe = f.tipo === "socio" || f.tipo === "colaborador";
  const botao = (dado, icone, rotulo, extra) => '<button type="button" class="com-icone" ' + dado + '="1"' + (extra || "") + ">" + ic(icone, 16) + esc(rotulo) + "</button>";
  const docs = (f.documentos || []).length;
  if (f.tipo === "despesa") {
    const valor = centavosDe(f.honorario);
    const s = situacaoDaDespesa(f);
    const lancada = s.classe !== "nada";
    const acoes = (lancada ? "" : botao("data-cad-lancar", "payments", "Lançar em " + mesCurto(mesDeHoje()), valor ? "" : " disabled")) +
      botao("data-cad-financeiro", "bar_chart", "Ver no Financeiro") +
      (docs ? botao("data-cad-acervo", "description", "Ver contrato") : "");
    return {
      contexto: "Cadastros › Despesa fixa · cadastrada em " + quandoDaFicha(f.criado_em),
      corpo: '<div class="cad-destaque"><span class="cad-valor-grande">' + esc(valor ? emReais(valor) : "sem valor") + "</span>" +
        '<span class="cad-destaque-nota">' + esc(lancada ? mesCurto(mesDeHoje()) + " · " + s.texto.toLowerCase() : "nada lançado em " + mesCurto(mesDeHoje())) + "</span></div>" +
        fichaDoDialogo([
          ["Vence", f.dia_vencimento ? "dia " + f.dia_vencimento : "sem dia certo"],
          ["Fornecedor", rotuloDoFornecedor(f)],
          ["Anotação", f.observacao],
          ["Aviso", f.avisar_dias ? plural(f.avisar_dias, "dia") + " antes" : "não avisar"],
        ]) +
        '<div class="dialogo-acoes">' + acoes + "</div>" +
        (lancada ? "" : '<p class="cad-nota">Lançar cria a conta a pagar no Financeiro; o pagamento de verdade continua no banco.</p>') +
        blocoDaDespesa(f),
    };
  }
  if (equipe) {
    const folha = folhaDe(f);
    return {
      contexto: "Cadastros › Equipe · " + (f.tipo === "socio" ? "sócio" : "colaborador") + " desde " + quandoDaFicha(f.criado_em),
      corpo: fichaDoDialogo([
        ["Função", f.observacao],
        ["CPF", f.documento],
        ["E-mail", f.email],
        ["Telefone", f.telefone],
        ["Na folha", folha ? rotuloDoVinculo(f.vinculo) + " · " + emReais(folha) : "não entra"],
      ]) +
        '<div class="dialogo-acoes">' + botao("data-cad-email", "mail", "Novo e-mail") + "</div>" +
        blocoDoPapel(f),
    };
  }
  const tipoPessoa = pessoaJuridica(f) ? "pessoa jurídica" : (pessoaFisica(f) ? "pessoa física" : "sem documento");
  return {
    contexto: "Cadastros › Cliente desde " + quandoDaFicha(f.criado_em) + " · " + tipoPessoa,
    corpo: fichaDoDialogo([
      [rotuloDoDocumento(f.documento), f.documento],
      ["Telefone", f.telefone],
      ["E-mail", f.email],
      ["Endereço", f.endereco],
      ["Honorário", [f.honorario, f.dia_vencimento ? "vence dia " + f.dia_vencimento : ""].filter(Boolean).join(" · ")],
    ]) +
      '<div class="dialogo-acoes">' + botao("data-cad-perguntar", "forum", "Perguntar sobre") + botao("data-cad-email", "mail", "Novo e-mail") +
      botao("data-cad-agendar", "calendar_month", "Agendar") + "</div>" +
      blocoLigadoA(f),
  };
}

function blocoLigadoA(f) {
  const docs = (f.documentos || []).length;
  const prazos = prazosDe(f).sort((a, b) => String(a.prazo).localeCompare(String(b.prazo)));
  const lanc = lancamentosDe(f).filter((l) => l.aberto && l.tipo === "recebimento").sort((a, b) => String(a.vencimento).localeCompare(String(b.vencimento)));
  const linha = (icone, texto, lado) => '<div class="cad-ligacao">' + ic(icone, 18) + "<span>" + texto + "</span>" + (lado || "") + "</div>";
  return '<div class="cad-bloco"><span class="cad-bloco-titulo">Ligado a</span><div class="cad-ligacoes">' +
    linha("inventory_2", esc(docs ? plural(docs, "documento") + " ligado" + (docs === 1 ? "" : "s") : "nenhum documento ligado"),
      '<button type="button" class="sv-ligacao" data-cad-acervo="1">ver no Acervo</button>') +
    linha("payments", esc(f.aberto_centavos ? f.aberto + " em aberto" : "nada em aberto"),
      "<small>" + esc(f.atraso_dias ? "atrasado " + plural(f.atraso_dias, "dia") : (lanc.length && lanc[0].vencimento ? "vence " + dataCurta(lanc[0].vencimento) : "")) + "</small>") +
    linha("event_upcoming", esc(prazos.length ? plural(prazos.length, "prazo") : "nenhum prazo"),
      "<small>" + esc(prazos.length && prazos[0].prazo ? "próximo: " + dataCurta(prazos[0].prazo) : "") + "</small>") +
    "</div></div>";
}

function blocoDoPapel(f) {
  const regras = CAD_PAPEIS[f.tipo === "socio" ? "socio" : "colaborador"];
  return '<div class="cad-bloco"><span class="cad-bloco-titulo">O que este papel pode <small>em breve</small></span>' +
    '<div class="cad-pode">' + regras.map(([pode, texto]) => {
      const classe = "ic ic-18" + (pode ? "" : " nao");
      return '<div><span class="' + classe + '">' + (pode ? "check_circle" : "close") + "</span><span>" + esc(texto) + "</span></div>";
    }).join("") + "</div>" +
    '<p class="cad-nota">Papéis e alçadas ainda não têm motor: hoje uma pessoa só usa o PAULUS nesta máquina, e ela pode tudo. Isto é o que o papel vai poder quando a equipe existir.</p></div>';
}

function blocoDaDespesa(f) {
  const ano = mesDeHoje().slice(0, 4);
  const todos = lancamentosDe(f).sort((a, b) => String(b.vencimento || b.liquidado_em).localeCompare(String(a.vencimento || a.liquidado_em)));
  const pagos = todos.filter((l) => !l.aberto && String(l.liquidado_em).startsWith(ano));
  const soma = pagos.reduce((s, l) => s + l.centavos, 0);
  return '<div class="cad-bloco"><span class="cad-bloco-titulo">Histórico <small>' + esc(plural(todos.length, "lançamento") + " · pago em " + ano + ": " +
    (pagos.length ? plural(pagos.length, "vez", "vezes") + ", " + emReais(soma) : "nada ainda")) + "</small></span>" +
    (todos.length
      ? '<div class="cad-historico">' + todos.slice(0, 5).map((l) =>
        "<span>" + esc(mesCurto(mesDoLancamento(l)) + " · " + (l.aberto ? situacaoCurta(l) : "pago em " + dataBR(l.liquidado_em).slice(0, 5)) + " · " + l.valor +
          (l.atrasado ? "" : (!l.aberto && l.vencimento && l.liquidado_em > l.vencimento ? " · " + plural(diasEntre(l.vencimento, l.liquidado_em), "dia") + " de atraso" : ""))) + "</span>").join("") + "</div>"
      : '<p class="cad-nota">Nenhum lançamento ligado a esta despesa ainda.</p>') + "</div>";
}

/* Os botoes do pop-up de ver: quem leva para outra tela fecha o pop-up antes. */
function ligarFichaVista(dlg, f) {
  const sair = (fn) => () => { if (dialogoAberto) dialogoAberto.fechar(null); fn(); };
  const clique = (seletor, fn) => dlg.querySelectorAll(seletor).forEach((b) => { b.onclick = fn; });
  clique("[data-cad-perguntar]", sair(() => perguntarSobreFicha(f)));
  clique("[data-cad-email]", sair(() => novoEmailPara(f)));
  clique("[data-cad-agendar]", sair(() => agendarCom(f)));
  clique("[data-cad-acervo]", sair(() => verNoAcervo(f.nome)));
  clique("[data-cad-financeiro]", sair(() => mostrarFinanceiro("lancamentos")));
  clique("[data-cad-lancar]", sair(() => lancarDespesa(f)));
  // Apagar pergunta num pop-up proprio, que toma o lugar deste; desistir
  // traz a ficha de volta.
  clique("[data-cad-apagar]", async () => { if (!(await apagarFicha(f))) verFicha(f.id); });
}

function quandoDaFicha(iso) {
  const m = /^(\d{4})-(\d{2})/.exec(iso || "");
  if (!m) return "—";
  return MESES_CURTOS[Number(m[2]) - 1] + " " + m[1];
}

function diasEntre(de, ate) {
  return Math.max(0, Math.round((deIso(String(ate).slice(0, 10)) - deIso(String(de).slice(0, 10))) / 86400000));
}

/* --------------------------------------- o cadastro, em pop-up (docs/ui/05) */
/*
   Novo e Editar: os campos na caixa do sistema, Apagar a esquerda do rodape
   so ao editar, Cancelar e Salvar a direita. Salvar com erro avisa no rodape
   e nao fecha - o que foi escrito nao se perde.
*/

function formDaFicha(f) {
  return {
    id: f.id, tipo: f.tipo, nome: f.nome || "", documento: f.documento || "", telefone: f.telefone || "", email: f.email || "",
    endereco: f.endereco || "", honorario: f.honorario || "", dia_vencimento: f.dia_vencimento || 0, avisar_dias: f.avisar_dias || 0,
    observacao: f.observacao || "", vinculo: f.vinculo || "",
    salario: f.salario_centavos ? semReais(emReais(f.salario_centavos)) : "",
    encargos: f.encargos_centavos ? semReais(emReais(f.encargos_centavos)) : "",
  };
}

function campoCad(chave, rotulo, dica) {
  const v = cad.form;
  const id = "cad-f-" + chave;
  return '<div class="dialogo-campo"><label for="' + id + '">' + esc(rotulo) + '</label><div class="dialogo-caixa">' +
    '<input type="text" id="' + id + '" data-cc="' + chave + '" value="' + esc(v[chave] || "") + '"' +
    (dica ? ' placeholder="' + esc(dica) + '"' : "") + ' autocomplete="off"></div></div>';
}

function listaCad(chave, rotulo, opcoes) {
  const v = cad.form;
  const id = "cad-f-" + chave;
  const atual = String(v[chave] === undefined || v[chave] === null ? "" : v[chave]);
  return '<div class="dialogo-campo"><label for="' + id + '">' + esc(rotulo) + '</label><div class="dialogo-caixa">' +
    '<select id="' + id + '" data-cc="' + chave + '">' +
    opcoes.map(([valor, r]) => '<option value="' + esc(String(valor)) + '"' + (String(valor) === atual ? " selected" : "") + ">" + esc(r) + "</option>").join("") +
    "</select></div></div>";
}

function duasCad(a, b) { return '<div class="dialogo-duas">' + a + b + "</div>"; }

function seletorDeDia() {
  const opcoes = [["0", "sem dia certo"]];
  for (let d = 1; d <= 31; d += 1) opcoes.push([String(d), "dia " + d]);
  return listaCad("dia_vencimento", "Dia de vencimento", opcoes);
}

function seletorDeAviso() {
  return listaCad("avisar_dias", "Avisar antes", [["0", "não avisar"], ["1", "1 dia antes"], ["3", "3 dias antes"], ["5", "5 dias antes"], ["7", "7 dias antes"]]);
}

function partesDoFormCad(v) {
  const nova = !v.id;
  const equipe = v.tipo === "socio" || v.tipo === "colaborador";
  const despesa = v.tipo === "despesa";
  let titulo, contexto, corpo = "";
  if (despesa) {
    titulo = nova ? "Nova despesa fixa" : "Editar despesa";
    contexto = "Cadastros › Despesas fixas";
  } else if (equipe) {
    titulo = nova ? "Nova pessoa na equipe" : "Editar pessoa";
    contexto = "Cadastros › Equipe";
  } else {
    titulo = nova ? "Novo cliente" : "Editar cliente";
    contexto = "Cadastros › Clientes";
  }
  if (!nova) contexto += " · " + v.nome;

  if (v._sugestao) {
    const x = v._sugestao;
    const nomes = (x.arquivos || []).map((a) => a.nome);
    const total = Math.max(x.aparicoes || 0, nomes.length);
    const lista = nomes.slice(0, 3).join(", ") + (nomes.length > 3 ? "…" : "");
    const ligar = nomes.length === 1 ? "a esse documento" : (nomes.length < total ? "a " + nomes.length + " deles" : "a esses documentos");
    corpo += '<p class="cad-veio">' + ic("description", 16) + "<span>Lido em " + esc(plural(total, "documento")) + " do Acervo" +
      (nomes.length ? (nomes.length < total ? ", entre eles " : ": ") + esc(lista) : "") +
      ". Confira o nome e o documento; o resto, se souber." + (nomes.length ? " Ao salvar, a ficha já nasce ligada " + ligar + "." : "") + "</span></p>";
  }

  if (despesa) {
    corpo += campoCad("nome", "Descrição", "aluguel, contabilidade, sistema…") +
      duasCad(campoCad("honorario", "Valor mensal", "R$ 0,00"), seletorDeDia()) +
      campoCad("documento", "CNPJ / CPF do fornecedor") +
      duasCad(campoCad("email", "E-mail do fornecedor"), campoCad("telefone", "Telefone")) +
      campoCad("observacao", "Anotação", "fornecedor, contrato, reajuste…") + seletorDeAviso();
  } else if (equipe) {
    corpo += campoCad("nome", "Nome completo") +
      duasCad(campoCad("documento", "CPF"), campoCad("observacao", "Função", "advogada · OAB/GO 00000")) +
      duasCad(campoCad("email", "E-mail"), campoCad("telefone", "Telefone")) +
      duasCad(listaCad("tipo", "Papel", [["socio", "Sócio · edita e aprova tudo"], ["colaborador", "Colaborador"]]),
        listaCad("vinculo", "Vínculo", CAD_VINCULOS)) +
      (v.vinculo ? duasCad(campoCad("salario", v.vinculo === "estagio" ? "Bolsa" : "Salário ou retirada", "R$ 0,00"), campoCad("encargos", "Encargos e INSS", "R$ 0,00")) : "") +
      campoCad("endereco", "Endereço");
  } else {
    corpo += campoCad("nome", "Razão social ou nome") +
      duasCad(campoCad("documento", "CNPJ / CPF"), campoCad("telefone", "Telefone")) +
      campoCad("email", "E-mail para cobrança") +
      campoCad("endereco", "Endereço") +
      duasCad(campoCad("honorario", "Honorário padrão", "R$ 0,00"), seletorDeDia()) +
      seletorDeAviso();
  }
  return {
    titulo: titulo, contexto: contexto, corpo: corpo, botao: nova ? "Salvar cadastro" : "Salvar",
    excluir: nova ? "" : '<button type="button" class="dialogo-excluir" data-cad-apagar-form="1">Apagar</button>',
  };
}

function abrirFormCad() {
  const v = cad.form;
  if (!v) return;
  const f = partesDoFormCad(v);
  const escolha = dialogo({
    titulo: f.titulo, contexto: f.contexto, classe: "dialogo-cadastro cad-dialogo", larga: true,
    html: '<div class="dialogo-form" id="cad-form-pop">' + f.corpo + "</div>",
    rodape: f.excluir + '<span class="dialogo-aviso" data-cad-aviso="1"></span>',
    cancelar: "Cancelar", confirmar: f.botao, aoConfirmar: salvarFicha,
  });
  const caixa = document.getElementById("cad-form-pop");
  if (caixa) {
    ligarFormCad(caixa.closest(".dialogo"));
    const nome = caixa.querySelector('[data-cc="nome"]');
    if (nome && !v._sugestao) nome.focus();
  }
  // Fechou sem salvar (Cancelar, Esc, clique fora): o formulario sai junto.
  escolha.then(() => { if (cad.form === v) cad.form = null; });
}

/* Papel e vinculo mudam os campos: refaz o miolo no proprio pop-up. */
function redesenharFormCad() {
  const caixa = document.getElementById("cad-form-pop");
  if (!caixa) return abrirFormCad();
  const dlg = caixa.closest(".dialogo");
  const f = partesDoFormCad(cad.form);
  dlg.querySelector("#dialogo-titulo").textContent = f.titulo;
  caixa.innerHTML = f.corpo;
  ligarFormCad(dlg);
}

function ligarFormCad(dlg) {
  if (!dlg) return;
  const v = cad.form;
  dlg.querySelectorAll(".dialogo-caixa select").forEach(melhorarSelect);
  dlg.querySelectorAll("[data-cc]").forEach((el) => {
    el.oninput = () => { v[el.dataset.cc] = el.value; };
    el.onchange = () => {
      v[el.dataset.cc] = el.value;
      if (el.dataset.cc === "tipo" || el.dataset.cc === "vinculo") redesenharFormCad();
    };
  });
  const apagar = dlg.querySelector("[data-cad-apagar-form]");
  if (apagar) apagar.onclick = async () => {
    const f = cad.fichas.find((x) => x.id === v.id);
    // A pergunta de apagar toma o lugar do pop-up; desistir o traz de volta.
    const foi = await apagarFicha(f);
    if (!foi) { cad.form = v; abrirFormCad(); }
  };
}

function avisoDoFormCad(texto) {
  const aviso = document.querySelector("[data-cad-aviso]");
  if (aviso) aviso.textContent = texto;
  else avisoCert(texto);
}

async function salvarFicha() {
  const v = cad.form;
  if (!v) return;
  if (!String(v.nome || "").trim()) {
    avisoDoFormCad("o cadastro precisa de um nome");
    const campo = document.querySelector('#cad-form-pop [data-cc="nome"]');
    if (campo) campo.focus();
    return;
  }
  const dados = {
    tipo: v.tipo, nome: v.nome, documento: v.documento, telefone: v.telefone, email: v.email, endereco: v.endereco,
    honorario: v.honorario, dia_vencimento: Number(v.dia_vencimento) || 0, avisar_dias: Number(v.avisar_dias) || 0,
    observacao: v.observacao, vinculo: v.vinculo || "",
    salario_centavos: v.vinculo ? centavosDe(v.salario) : 0, encargos_centavos: v.vinculo ? centavosDe(v.encargos) : 0,
  };
  const r = await fetch("/api/cadastros", { method: "POST", headers: CAD_JSON, body: JSON.stringify({ id: v.id || null, dados: dados }) });
  if (!r.ok) { avisoDoFormCad(await erroDe(r)); return; }
  const ficha = await r.json();
  // Sugestao aceita ja nasce ligada aos documentos de onde veio.
  if (v._sugestao) {
    for (const a of v._sugestao.arquivos || []) {
      await fetch("/api/cadastros/" + ficha.id + "/vincular", { method: "POST", headers: CAD_JSON, body: JSON.stringify({ sha1: a.sha1, nome: a.nome }) });
    }
  }
  cad.form = null;
  if (dialogoAberto && document.getElementById("cad-form-pop")) dialogoAberto.fechar(null);
  if (!v.id && !v._sugestao) cad.visao = visaoDoTipo(ficha.tipo);
  avisoCert(v.id ? "ficha atualizada" : (v._sugestao ? ficha.nome + " cadastrado — ligado aos documentos de onde veio" : "cadastro salvo"), { tom: "ok" });
  mostrarCadastros();
}

/* ------------------------------------------------------------ as acoes */

function ligarCadastros() {
  const cada = (seletor, fn) => document.querySelectorAll(seletor).forEach(fn);
  const clique = (seletor, fn) => cada(seletor, (b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });

  clique("[data-cad-visao]", (b) => { cad.visao = b.dataset.cadVisao; cad.filtro = "todos"; cad.escolhidas.clear(); desenharCadastros(); });
  const busca = $("cad-busca");
  if (busca) {
    let t;
    busca.oninput = () => { clearTimeout(t); const v = busca.value; t = setTimeout(() => { cad.termo = v.trim(); mostrarCadastros(); }, 280); };
  }
  clique("[data-cad-nova]", () => novaFicha());
  clique("[data-cad-filtro]", (b) => { cad.filtro = b.dataset.cadFiltro; desenharCadastros(); });
  clique("[data-cad-ordem]", (b) => {
    menuNaLinha(b, [["nome", "A–Z"], ["aberto", "Maior valor em aberto"], ["atraso", "Maior atraso"]].map(([v, r]) =>
      ({ rotulo: r, acao: () => { cad.ordem = v; mostrarCadastros(); } })));
  });
  clique("[data-cad-importar]", () => avisoCert("Importar cadastros ainda não existe — os nomes lidos nos contratos aparecem no cartão acima, prontos para conferir"));
  clique("[data-cad-exportar]", () => avisoCert("Exportar cadastros ainda não existe — a planilha do mês sai pelo Financeiro"));
  clique("[data-cad-regras]", () => { marcarDestino("aprovacoes"); mostrarRegrasDeAlcada(); });
  clique("[data-cad-financeiro]", () => mostrarFinanceiro("lancamentos"));
  clique("[data-cad-abrir]", (b) => verFicha(Number(b.dataset.cadAbrir)));
  ligarSelecao(document.querySelector("#cad-tela .tabela-corpo"), {
    linhas: ".tabela-linha[data-sel]", escolhidos: cad.escolhidas, aoMudar: desenharCadastros, apagar: (ids) => apagarFichasEmLote(ids),
  });
  clique("[data-cad-sel-limpar]", () => { cad.escolhidas.clear(); desenharCadastros(); });
  clique("[data-cad-sel-apagar]", () => apagarFichasEmLote([...cad.escolhidas]));
  clique("[data-cad-mais]", (b) => menuDaFicha(b, Number(b.dataset.cadMais)));
  const sug = document.getElementById("cad-sug");
  if (sug) ligarCartaoSugestao(sug);
}

function editarFicha(f) {
  if (!f) return;
  cad.aberta = f;
  cad.form = formDaFicha(f);
  abrirFormCad();
}

function novaFicha() {
  const tipo = cad.visao === "equipe" ? "colaborador" : (cad.visao === "despesas" ? "despesa" : "cliente");
  cad.aberta = null;
  cad.form = formDaFicha({ tipo: tipo });
  abrirFormCad();
}

function menuDaFicha(botao, id) {
  const f = cad.fichas.find((x) => x.id === id);
  if (!f) return;
  const itens = [
    { icone: "open_in_new", rotulo: "Abrir a ficha", acao: () => verFicha(id) },
    { icone: "edit", rotulo: "Editar", acao: () => editarFicha(f) },
  ];
  if (f.tipo === "cliente") {
    itens.push({ icone: "mail", rotulo: "Novo e-mail", acao: () => novoEmailPara(f) });
    itens.push({ icone: "calendar_month", rotulo: "Agendar", acao: () => agendarCom(f) });
    itens.push({ icone: "inventory_2", rotulo: "Ver no Acervo", acao: () => verNoAcervo(f.nome) });
  } else if (f.tipo === "despesa") {
    itens.push({ icone: "payments", rotulo: "Lançar em " + mesCurto(mesDeHoje()), acao: () => lancarDespesa(f) });
    itens.push({ icone: "bar_chart", rotulo: "Ver no Financeiro", acao: () => mostrarFinanceiro("lancamentos") });
  } else {
    itens.push({ icone: "mail", rotulo: "Novo e-mail", acao: () => novoEmailPara(f) });
    itens.push({ icone: "payments", rotulo: "Ver a folha", acao: () => mostrarFinanceiro("geral") });
  }
  itens.push("-");
  itens.push({ icone: "delete", rotulo: "Apagar ficha", perigo: true, acao: () => apagarFicha(f) });
  menuNaLinha(botao, itens);
}

/* A barra das tres listas: os filtros, ou a selecao quando ha fichas marcadas. */
function barraCad(chips) {
  if (!cad.escolhidas.size) return '<div class="visoes">' + chips + "</div>";
  return barraDeSelecao(cad.escolhidas.size, true,
    '<button class="botao-icone perigo" data-cad-sel-apagar="1" title="Apagar" aria-label="Apagar">' + ic("delete", 18) + "</button>", "data-cad-sel-limpar");
}

function apagarFichasEmLote(ids) {
  return apagarEmLote(ids, (id) => "/api/cadastros/" + id, {
    rotulo: "ficha", contexto: "Cadastros", texto: "Os lançamentos e documentos continuam onde estão, só perdem a ligação; restaurar religa.",
    depois: () => { cad.escolhidas.clear(); cad.aberta = null; cad.form = null; mostrarCadastros(); },
  });
}

/* Devolve se apagou: quem pergunta de dentro de um pop-up o reabre se a
   pessoa desistir. */
async function apagarFicha(f) {
  if (!f) return false;
  if (!(await confirmar({ titulo: "Apagar a ficha de " + f.nome + "?", contexto: "Cadastros", texto: "Os lançamentos e documentos continuam onde estão, só perdem a ligação com a ficha. " + LIXEIRA_TEXTO + " Restaurar religa tudo.", confirmar: "Apagar", perigo: true }))) return false;
  const r = await fetch("/api/cadastros/" + f.id, { method: "DELETE" });
  if (!r.ok) { avisoCert(await erroDe(r)); return false; }
  cad.aberta = null;
  cad.form = null;
  mostrarCadastros();
  avisarLixeira(r, () => mostrarCadastros());
  return true;
}

function perguntarSobreFicha(f) {
  if (!f) return;
  $("nova").click();
  marcarDestino("conversa");
  const campo = $("pedido");
  if (campo) {
    campo.value = "Sobre " + f.nome + ": ";
    campo.focus();
    campo.setSelectionRange(campo.value.length, campo.value.length);
  }
}

async function novoEmailPara(f) {
  if (!f) return;
  if (!f.email) { avisoCert(f.nome + " não tem e-mail no cadastro — preencha e salve primeiro"); return; }
  if (!mail.contas) {
    try { mail.contas = await (await fetch("/api/email/contas")).json(); } catch (err) { mail.contas = null; }
  }
  if (!mail.contas || !mail.contas.contas.length) { marcarDestino("caixa"); return mostrarEmail(); }
  mail.conta = mail.contas.contas.find((c) => c.em_uso) || mail.contas.contas[0];
  marcarDestino("caixa");
  telaEscrever({ para: f.email, assunto: "", corpo: "" });
}

/* Agendar abre a semana da Agenda com o formulario ja apontando para a
   pessoa: a visao e posta antes, para mostrarAgenda nao zerar o formulario. */
function agendarCom(f) {
  if (!f) return;
  ag.visao = "semana";
  ag.painel = "form";
  ag.form = Object.assign(compromissoEmBranco("compromisso"), { cadastro_id: f.id, titulo: "Reunião com " + f.nome });
  mostrarAgenda("semana");
}

function categoriaDaDespesa(nome) {
  const n = String(nome || "").toLowerCase();
  if (/alugu|condom/.test(n)) return "aluguel";
  if (/contab|sistema|software|internet|telefon|assinatura|nuvem|energia|luz|água|agua/.test(n)) return "sistemas";
  if (/imposto|taxa|anuidade|oab|tribut|iss|inss|darf/.test(n)) return "imposto";
  if (/folha|salár|salar|estagi/.test(n)) return "folha";
  return "outros";
}

/* Lancar em um mes cria a conta a pagar no Financeiro com o valor e o dia
   da ficha; pagar de verdade continua no banco. */
async function lancarDespesa(f) {
  if (!f) return;
  const valor = centavosDe(f.honorario);
  if (!valor) { avisoCert("a despesa precisa de um valor mensal para ser lançada"); return; }
  const mes = mesDeHoje();
  const dia = f.dia_vencimento ? String(Math.min(f.dia_vencimento, Number(ultimoDiaDoMes(mes).slice(8)))).padStart(2, "0") : ultimoDiaDoMes(mes).slice(8);
  const r = await fetch("/api/financeiro/lancamentos", {
    method: "POST", headers: CAD_JSON,
    body: JSON.stringify({ id: null, dados: {
      tipo: "despesa", descricao: f.nome, valor: semReais(emReais(valor)), categoria: categoriaDaDespesa(f.nome),
      cadastro_id: f.id, vencimento: mes + "-" + dia, liquidado_em: "",
    } }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  avisoCert(f.nome + " lançada em " + mesCurto(mes) + " — está em contas a pagar no Financeiro", { tom: "ok" });
  mostrarCadastros();
}
