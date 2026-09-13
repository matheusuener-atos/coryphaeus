/* ---------------------------------------------------------- cadastros */
/*
   Cadastros (docs/ui/03-telas-desktop.md, A10): Clientes, Equipe e Despesas
   fixas, cada uma uma tabela com a ficha editavel no painel. As fichas sao
   as mesmas de sempre (tipo cliente, colaborador, socio e despesa); o que a
   tela nova faz e ler cada tipo do jeito que ele e usado. O que o desenho
   pede e ainda nao tem motor - acesso por pasta, papeis e alcadas por pessoa,
   contatos dentro da ficha, importar e exportar - diz isso na tela.
*/

const cad = {
  visao: "clientes", fichas: [], contagem: {}, tipos: [], sugestoes: [],
  lancamentos: [], tarefas: [], termo: "", ordem: "nome", filtro: "todos",
  aberta: null, form: null, largo: false,
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
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">abrindo…</p></div></div>';
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
    cad.lancamentos = l.lancamentos || [];
    cad.tarefas = t.tarefas || [];
    if (cad.aberta) {
      cad.aberta = cad.fichas.find((f) => f.id === cad.aberta.id) || null;
      if (cad.aberta && cad.form && cad.form.id === cad.aberta.id) cad.form = formDaFicha(cad.aberta);
      if (!cad.aberta) cad.form = null;
    }
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
  const classe = "acervo cad-tela" + (cad.largo ? " painel-largo" : "");
  $("centro").innerHTML = '<div class="' + classe + '" id="cad-tela">' + miolo + painelDosCadastros() + "</div>";
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

function vazioDosCadastros(total) {
  if (cad.termo) return "Nenhuma ficha com “" + cad.termo + "”.";
  if (total) return "Nenhuma ficha com este filtro.";
  if (cad.visao === "equipe") return "Ninguém na equipe ainda. Quem tem vínculo definido entra na folha de pagamento do Financeiro.";
  if (cad.visao === "despesas") return "Nenhuma despesa fixa ainda. Aluguel, contabilidade, sistemas: cadastre para acompanhar o mês no Financeiro.";
  return "Nenhum cliente ainda. Cadastre pelo botão Novo cliente — ou aceite um dos nomes que o assistente já leu nos contratos.";
}

function menuDaLinha(id) {
  return '<button class="mais-linha" data-cad-mais="' + id + '" title="Mais">' + ic("more_horiz", 18) + "</button>";
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
  return '<div class="acervo-principal">' +
    '<div class="tabela-cartao">' +
    '<div class="tabela-barra cad-barra"><div class="visoes">' + chip("todos", "Todos") + chip("pj", "Pessoa jurídica") + chip("pf", "Pessoa física") + chip("atraso", "Com atraso") + "</div>" +
    '<div class="direita"><button data-cad-ordem="1">' + ic("swap_vert", 16) + esc(ordens[cad.ordem] || "A–Z") + "</button>" +
    '<button class="adiante" data-cad-importar="1">' + ic("upload", 16) + "Importar</button>" +
    '<button class="adiante" data-cad-exportar="1">' + ic("download", 16) + "Exportar</button></div></div>" +
    avisoDeSugestoes() +
    '<div class="tabela-cabecalho colunas-clientes"><span>Nome e documento</span><span>Contato</span><span>Ligado a</span><span class="fin-num">Em aberto</span><span></span></div>' +
    '<div class="tabela-corpo">' + (lista.length ? lista.map(linhaDeCliente).join("") : '<p class="rel-vazio">' + esc(vazioDosCadastros(todas.length)) + "</p>") + "</div>" +
    '<div class="tabela-rodape"><span>' + lista.length + " de " + todas.length + "</span></div></div></div>";
}

function avisoDeSugestoes() {
  if (!cad.sugestoes.length) return "";
  const mostrar = cad.sugestoes.slice(0, 4);
  return '<div class="cad-aviso">' + ic("person_add", 18) +
    '<span class="cresce">' + esc(plural(cad.sugestoes.length, "nome lido", "nomes lidos")) + " nos contratos, ainda sem ficha — cadastrar é conferir, não digitar</span>" +
    mostrar.map((x, i) => '<button class="cad-sug" data-cad-sug="' + i + '">' + esc(x.nome) + "<small>" + esc(plural(x.aparicoes, "doc")) + "</small></button>").join("") +
    (cad.sugestoes.length > mostrar.length ? '<span class="cad-mudo">+ ' + (cad.sugestoes.length - mostrar.length) + "</span>" : "") + "</div>";
}

function linhaDeCliente(f) {
  const aberta = cad.aberta && cad.aberta.id === f.id;
  const classe = "tabela-linha colunas-clientes" + (aberta ? " aberta" : "");
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
  return '<div class="' + classe + '" data-cad-abrir="' + f.id + '">' +
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
  return '<div class="acervo-principal"><div class="tabela-cartao">' +
    '<div class="tabela-barra cad-barra"><div class="visoes">' + chip("todos", "Todos") + chip("socio", "Sócios") + chip("colaborador", "Colaboradores") + "</div>" +
    '<div class="direita"><button data-cad-regras="1">' + ic("shield_person", 16) + "Papéis e alçadas</button>" +
    '<button class="primario" data-cad-nova="1">' + ic("person_add", 16) + "Nova pessoa</button></div></div>" +
    '<div class="tabela-cabecalho colunas-equipe"><span>Nome e função</span><span>Papel</span><span>Acesso por pasta</span><span class="fin-num">Na folha</span><span></span></div>' +
    '<div class="tabela-corpo">' + (lista.length ? lista.map(linhaDaEquipe).join("") : '<p class="rel-vazio">' + esc(vazioDosCadastros(todas.length)) + "</p>") + "</div>" +
    '<div class="tabela-rodape"><span>' + esc(plural(todas.length, "pessoa")) + " · folha " + esc(emReais(folha)) + "</span>" +
    '<span class="cad-rodape-nota">Alterar papel ou acesso passa por Aprovações · em breve</span></div></div></div>';
}

function linhaDaEquipe(f) {
  const aberta = cad.aberta && cad.aberta.id === f.id;
  const classe = "tabela-linha colunas-equipe" + (aberta ? " aberta" : "");
  const socio = f.tipo === "socio";
  const classePapel = "cad-pill" + (socio ? " forte" : "");
  const sub = [f.observacao, rotuloDoVinculo(f.vinculo) === "não entra na folha" ? "" : rotuloDoVinculo(f.vinculo)].filter(Boolean).join(" · ") || (f.documento ? "CPF " + f.documento : "sem função anotada");
  const folha = folhaDe(f);
  const classeValor = "fin-valor fin-valor-col" + (folha ? "" : " cad-zero");
  return '<div class="' + classe + '" data-cad-abrir="' + f.id + '">' +
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
  return '<div class="acervo-principal"><div class="tabela-cartao">' +
    '<div class="tabela-barra cad-barra"><div class="visoes">' + chip("todos", "Todas") + chip("dia", "Com dia certo") + chip("semdia", "Sem dia") + "</div>" +
    '<div class="direita"><button class="adiante" data-cad-exportar="1">' + ic("download", 16) + "Exportar</button>" +
    '<button class="primario" data-cad-nova="1">' + ic("add", 16) + "Nova despesa</button></div></div>" +
    '<div class="tabela-cabecalho colunas-despesas"><span>Despesa</span><span>Fornecedor</span><span>Vence</span><span class="fin-num">Valor</span><span>' +
    esc(maiuscula(mesCurto(mesDeHoje()))) + "</span><span></span></div>" +
    '<div class="tabela-corpo">' + (lista.length ? lista.map(linhaDaDespesa).join("") : '<p class="rel-vazio">' + esc(vazioDosCadastros(todas.length)) + "</p>") + "</div>" +
    '<div class="tabela-rodape"><span>' + lista.length + " de " + todas.length + " · " + esc(emReais(total)) + ' no mês</span>' +
    '<span class="cad-rodape-nota"><button class="em-ligacao forte" data-cad-financeiro="1">Ver no Financeiro →</button></span></div></div></div>';
}

function linhaDaDespesa(f) {
  const aberta = cad.aberta && cad.aberta.id === f.id;
  const classe = "tabela-linha colunas-despesas" + (aberta ? " aberta" : "");
  const s = situacaoDaDespesa(f);
  const classeStatus = "fin-status " + s.classe;
  const valor = centavosDe(f.honorario);
  const classeValor = "fin-valor fin-valor-col" + (valor ? "" : " cad-zero");
  return '<div class="' + classe + '" data-cad-abrir="' + f.id + '">' +
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

/* ---------------------------------------------------------- o painel */

function painelDosCadastros() {
  const alca = '<button class="alca-painel" data-cad-alca="1" title="Alargar ou recolher o painel" aria-label="Alargar ou recolher o painel">' +
    ic(cad.largo ? "chevron_right" : "chevron_left", 18) + "</button>";
  if (cad.form) return '<aside class="acervo-painel cad-painel">' + alca + '<div class="rolagem">' + painelDaFicha() + "</div></aside>";
  let h3, p, novo;
  if (cad.visao === "equipe") { h3 = "Ninguém aberto"; p = "Clique numa pessoa para ver a ficha, o vínculo e o que o papel dela pode."; novo = "Nova pessoa"; }
  else if (cad.visao === "despesas") { h3 = "Nenhuma despesa aberta"; p = "Clique numa despesa para ver o valor, o dia e o histórico de pagamento."; novo = "Nova despesa"; }
  else { h3 = "Nenhum cliente aberto"; p = "Clique numa linha para ver a ficha, o que está em aberto e os documentos ligados."; novo = "Novo cliente"; }
  return '<aside class="acervo-painel cad-painel">' + alca + '<div class="rolagem"><div class="painel-vazio"><h3>' + h3 + "</h3><p>" + p + "</p>" +
    '<div class="fin-botoes"><button class="primario" data-cad-nova="1">' + ic("add", 16) + novo + "</button></div></div></div></aside>";
}

function formDaFicha(f) {
  return {
    id: f.id, tipo: f.tipo, nome: f.nome || "", documento: f.documento || "", telefone: f.telefone || "", email: f.email || "",
    endereco: f.endereco || "", honorario: f.honorario || "", dia_vencimento: f.dia_vencimento || 0, avisar_dias: f.avisar_dias || 0,
    observacao: f.observacao || "", vinculo: f.vinculo || "",
    salario: f.salario_centavos ? semReais(emReais(f.salario_centavos)) : "",
    encargos: f.encargos_centavos ? semReais(emReais(f.encargos_centavos)) : "",
  };
}

function campoDaFicha(chave, rotulo, dica) {
  const v = cad.form;
  return '<div class="ag-campo"><label>' + esc(rotulo) + '</label><input type="text" data-cc="' + chave + '" value="' + esc(v[chave] || "") + '"' +
    (dica ? ' placeholder="' + esc(dica) + '"' : "") + "></div>";
}

function seletorDeDia() {
  const v = cad.form;
  let opcoes = '<option value="0"' + (!Number(v.dia_vencimento) ? " selected" : "") + ">sem dia certo</option>";
  for (let d = 1; d <= 31; d += 1) opcoes += '<option value="' + d + '"' + (Number(v.dia_vencimento) === d ? " selected" : "") + ">dia " + d + "</option>";
  return '<div class="ag-campo"><label>Dia de vencimento</label><select data-cc="dia_vencimento">' + opcoes + "</select></div>";
}

function seletorDeAviso() {
  const v = cad.form;
  return '<div class="ag-campo"><label>Avisar antes</label><select data-cc="avisar_dias">' +
    [[0, "não avisar"], [1, "1 dia antes"], [3, "3 dias antes"], [5, "5 dias antes"], [7, "7 dias antes"]].map(([n, r]) =>
      '<option value="' + n + '"' + (Number(v.avisar_dias) === n ? " selected" : "") + ">" + r + "</option>").join("") + "</select></div>";
}

function painelDaFicha() {
  const v = cad.form;
  const f = cad.aberta;
  const nova = !v.id;
  const equipe = v.tipo === "socio" || v.tipo === "colaborador";
  const despesa = v.tipo === "despesa";

  let titulo, meta;
  if (nova) {
    titulo = despesa ? "Nova despesa" : (equipe ? "Nova pessoa" : "Novo cliente");
    meta = v._sugestao ? "veio de " + plural(v._sugestao.aparicoes, "documento") + " do Acervo" : "ainda não salva — entra na lista ao salvar";
  } else if (despesa) {
    titulo = f.nome;
    meta = "Despesa fixa mensal" + (f.dia_vencimento ? " · vence dia " + f.dia_vencimento : " · sem dia certo");
  } else if (equipe) {
    titulo = f.nome;
    meta = (f.tipo === "socio" ? "Sócio" : "Colaborador") + " · " + (rotuloDoVinculo(f.vinculo) || "não entra na folha") + (f.observacao ? " · " + f.observacao : "");
  } else {
    titulo = f.nome;
    meta = "Cliente desde " + quandoDaFicha(f.criado_em) + " · " + (pessoaJuridica(f) ? "pessoa jurídica" : (pessoaFisica(f) ? "pessoa física" : "sem documento"));
  }

  let html = '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + esc(titulo) + '</h3><span class="meta">' + esc(meta) + "</span></span>" +
    (equipe && !nova ? '<span class="cad-avatar grande">' + esc(iniciaisDoRemetente(f.nome)) + "</span>" : "") +
    '<button class="botao-icone" data-cad-fechar="1" title="Fechar">' + ic("close", 18) + "</button></div>";

  if (!nova && !equipe && !despesa) {
    html += '<div class="painel-acoes"><button class="primario" data-cad-perguntar="1">' + ic("forum", 16) + "Perguntar sobre</button>" +
      '<button data-cad-email="1">' + ic("mail", 16) + "Novo e-mail</button>" +
      '<button data-cad-agendar="1">' + ic("calendar_month", 16) + "Agendar</button></div>";
  } else if (!nova && equipe) {
    html += '<div class="painel-acoes"><button data-cad-email="1">' + ic("mail", 16) + "Novo e-mail</button>" +
      '<button data-cad-senha="1">' + ic("key", 16) + "Redefinir senha</button></div>";
  } else if (!nova && despesa) {
    const valor = centavosDe(f.honorario);
    const s = situacaoDaDespesa(f);
    const lancada = s.classe !== "nada";
    html += '<div class="fin-detalhe"><span class="cad-valor-grande">' + esc(emReais(valor)) + "</span>" +
      '<div class="fin-botoes">' +
      (lancada
        ? '<span class="fin-feito">' + ic("check_circle", 16) + "já em " + esc(mesCurto(mesDeHoje())) + " · " + esc(s.texto.toLowerCase()) + "</span>"
        : '<button class="primario" data-cad-lancar="1"' + (valor ? "" : " disabled") + ">" + ic("payments", 16) + "Lançar em " + esc(mesCurto(mesDeHoje())) + "</button>") +
      '<button data-cad-financeiro="1">' + ic("bar_chart", 16) + "Ver no Financeiro</button>" +
      ((f.documentos || []).length ? '<button data-cad-acervo="1">' + ic("description", 16) + "Ver contrato</button>" : "") + "</div>" +
      '<small class="fin-nota">Lançar cria a conta a pagar no Financeiro; o pagamento de verdade continua no banco.</small></div>';
  }

  if (v._sugestao) {
    html += '<p class="ag-explica" style="padding:0 18px 4px">Veio de ' + esc(v._sugestao.arquivos.map((a) => a.nome).join(", ")) + ".</p>";
  }

  html += '<div class="cad-campos">';
  if (despesa) {
    html += campoDaFicha("nome", "Descrição", "aluguel, contabilidade, sistema…") +
      '<div class="ag-duas">' + campoDaFicha("honorario", "Valor mensal", "R$ 0,00") + seletorDeDia() + "</div>" +
      campoDaFicha("documento", "CNPJ / CPF do fornecedor") +
      '<div class="ag-duas">' + campoDaFicha("email", "E-mail do fornecedor") + campoDaFicha("telefone", "Telefone") + "</div>" +
      campoDaFicha("observacao", "Anotação", "fornecedor, contrato, reajuste…") + seletorDeAviso();
  } else if (equipe) {
    const vinculos = CAD_VINCULOS.map(([val, r]) => '<option value="' + val + '"' + (val === (v.vinculo || "") ? " selected" : "") + ">" + r + "</option>").join("");
    html += campoDaFicha("nome", "Nome completo") +
      '<div class="ag-duas">' + campoDaFicha("documento", "CPF") + campoDaFicha("observacao", "Função", "advogada · OAB/GO 00000") + "</div>" +
      '<div class="ag-duas">' + campoDaFicha("email", "E-mail") + campoDaFicha("telefone", "Telefone") + "</div>" +
      '<div class="ag-duas"><div class="ag-campo"><label>Papel</label><select data-cc="tipo">' +
      '<option value="socio"' + (v.tipo === "socio" ? " selected" : "") + '>Sócio · edita e aprova tudo</option>' +
      '<option value="colaborador"' + (v.tipo === "colaborador" ? " selected" : "") + ">Colaborador</option></select></div>" +
      '<div class="ag-campo"><label>Vínculo</label><select data-cc="vinculo">' + vinculos + "</select></div></div>" +
      (v.vinculo ? '<div class="ag-duas">' + campoDaFicha("salario", v.vinculo === "estagio" ? "Bolsa" : "Salário ou retirada", "R$ 0,00") + campoDaFicha("encargos", "Encargos e INSS", "R$ 0,00") + "</div>" : "") +
      campoDaFicha("endereco", "Endereço");
  } else {
    html += campoDaFicha("nome", "Razão social ou nome") +
      '<div class="ag-duas">' + campoDaFicha("documento", "CNPJ / CPF") + campoDaFicha("telefone", "Telefone") + "</div>" +
      campoDaFicha("email", "E-mail para cobrança") +
      campoDaFicha("endereco", "Endereço") +
      '<div class="ag-duas">' + campoDaFicha("honorario", "Honorário padrão", "R$ 0,00") + seletorDeDia() + "</div>" +
      seletorDeAviso();
  }
  html += "</div>";

  if (!nova && !equipe && !despesa) html += blocoLigadoA(f);
  if (!nova && equipe) html += blocoDoPapel(f);
  if (!nova && despesa) html += blocoDaDespesa(f);

  html += '<div class="cad-rodape">' +
    (nova ? "" : '<button class="em-ligacao acc" data-cad-apagar="1">Apagar ficha</button>') +
    '<button class="primario" data-cad-salvar="1">' + ic("check", 16) + (nova ? "Salvar cadastro" : "Salvar") + "</button></div>";
  return html;
}

function blocoLigadoA(f) {
  const docs = (f.documentos || []).length;
  const prazos = prazosDe(f).sort((a, b) => String(a.prazo).localeCompare(String(b.prazo)));
  const lanc = lancamentosDe(f).filter((l) => l.aberto && l.tipo === "recebimento").sort((a, b) => String(a.vencimento).localeCompare(String(b.vencimento)));
  const linha = (icone, texto, lado) => '<div class="cad-ligacao">' + ic(icone, 18) + "<span>" + texto + "</span>" + (lado || "") + "</div>";
  return '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Ligado a</span></div><div class="cad-ligacoes">' +
    linha("inventory_2", esc(docs ? plural(docs, "documento") + " ligado" + (docs === 1 ? "" : "s") : "nenhum documento ligado"),
      '<button class="em-ligacao" data-cad-acervo="1">ver no Acervo</button>') +
    linha("payments", esc(f.aberto_centavos ? f.aberto + " em aberto" : "nada em aberto"),
      "<small>" + esc(f.atraso_dias ? "atrasado " + plural(f.atraso_dias, "dia") : (lanc.length && lanc[0].vencimento ? "vence " + dataCurta(lanc[0].vencimento) : "")) + "</small>") +
    linha("event_upcoming", esc(prazos.length ? plural(prazos.length, "prazo") : "nenhum prazo"),
      "<small>" + esc(prazos.length && prazos[0].prazo ? "próximo: " + dataCurta(prazos[0].prazo) : "") + "</small>") +
    "</div></div>";
}

function blocoDoPapel(f) {
  const regras = CAD_PAPEIS[f.tipo === "socio" ? "socio" : "colaborador"];
  const folha = folhaDe(f);
  return '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>O que este papel pode</span><span class="contagem">em breve</span></div>' +
    '<div class="cad-pode">' + regras.map(([pode, texto]) => {
      const classe = "ic ic-18" + (pode ? "" : " nao");
      return '<div><span class="' + classe + '">' + (pode ? "check_circle" : "close") + "</span><span>" + esc(texto) + "</span></div>";
    }).join("") + "</div>" +
    "<p>Papéis e alçadas ainda não têm motor: hoje uma pessoa só usa o PAULUS nesta máquina, e ela pode tudo. Isto é o que o papel vai poder quando a equipe existir.</p></div>" +
    '<div class="painel-chaves">' +
    '<div class="chave-valor"><span>Cadastrado em</span><b>' + esc(quandoDaFicha(f.criado_em)) + "</b></div>" +
    '<div class="chave-valor"><span>Na folha</span><b>' + esc(folha ? rotuloDoVinculo(f.vinculo) + " · " + emReais(folha) : "não entra") + "</b></div>" +
    '<div class="chave-valor"><span>Último acesso</span><b class="mute">em breve</b></div>' +
    '<div class="chave-valor"><span>Certificado</span><b class="mute">em breve</b></div></div>';
}

function blocoDaDespesa(f) {
  const ano = mesDeHoje().slice(0, 4);
  const todos = lancamentosDe(f).sort((a, b) => String(b.vencimento || b.liquidado_em).localeCompare(String(a.vencimento || a.liquidado_em)));
  const pagos = todos.filter((l) => !l.aberto && String(l.liquidado_em).startsWith(ano));
  const soma = pagos.reduce((s, l) => s + l.centavos, 0);
  const docs = (f.documentos || []).length;
  return '<div class="painel-chaves">' +
    '<div class="chave-valor"><span>Documentos ligados</span>' + (docs ? '<button class="em-ligacao forte" data-cad-acervo="1">' + esc(plural(docs, "documento")) + " · ver</button>" : '<b class="mute">nenhum</b>') + "</div>" +
    '<div class="chave-valor"><span>Pago em ' + esc(ano) + "</span><b>" + esc(pagos.length ? plural(pagos.length, "vez", "vezes") + " · " + emReais(soma) : "nada ainda") + "</b></div>" +
    '<div class="chave-valor"><span>Cadastrada em</span><b>' + esc(quandoDaFicha(f.criado_em)) + "</b></div></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Histórico</span><span class="contagem">' + esc(plural(todos.length, "lançamento")) + "</span></div>" +
    (todos.length
      ? '<div class="cad-historico">' + todos.slice(0, 5).map((l) =>
        "<span>" + esc(mesCurto(mesDoLancamento(l)) + " · " + (l.aberto ? situacaoCurta(l) : "pago em " + dataBR(l.liquidado_em).slice(0, 5)) + " · " + l.valor +
          (l.atrasado ? "" : (!l.aberto && l.vencimento && l.liquidado_em > l.vencimento ? " · " + plural(diasEntre(l.vencimento, l.liquidado_em), "dia") + " de atraso" : ""))) + "</span>").join("") + "</div>"
      : "<p>Nenhum lançamento ligado a esta despesa ainda. Lançar em " + esc(mesCurto(mesDeHoje())) + " cria o primeiro.</p>") + "</div>";
}

function quandoDaFicha(iso) {
  const m = /^(\d{4})-(\d{2})/.exec(iso || "");
  if (!m) return "—";
  return MESES_CURTOS[Number(m[2]) - 1] + " " + m[1];
}

function diasEntre(de, ate) {
  return Math.max(0, Math.round((deIso(String(ate).slice(0, 10)) - deIso(String(de).slice(0, 10))) / 86400000));
}

/* ------------------------------------------------------------ as acoes */

function ligarCadastros() {
  const cada = (seletor, fn) => document.querySelectorAll(seletor).forEach(fn);
  const clique = (seletor, fn) => cada(seletor, (b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });

  clique("[data-cad-visao]", (b) => { cad.visao = b.dataset.cadVisao; cad.filtro = "todos"; cad.aberta = null; cad.form = null; desenharCadastros(); });
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
  clique("[data-cad-importar]", () => avisoCert("Importar cadastros ainda não existe — os nomes lidos nos contratos já aparecem acima, prontos para conferir"));
  clique("[data-cad-exportar]", () => avisoCert("Exportar cadastros ainda não existe — a planilha do mês sai pelo Financeiro"));
  clique("[data-cad-regras]", () => { marcarDestino("aprovacoes"); mostrarRegrasDeAlcada(); });
  clique("[data-cad-financeiro]", () => mostrarFinanceiro("lancamentos"));
  clique("[data-cad-sug]", (b) => {
    const x = cad.sugestoes[Number(b.dataset.cadSug)];
    if (!x) return;
    cad.aberta = null;
    cad.form = Object.assign(formDaFicha({ tipo: "cliente" }), { nome: x.nome, documento: x.documento || "", _sugestao: x });
    desenharCadastros();
  });
  clique("[data-cad-abrir]", (b) => abrirFicha(Number(b.dataset.cadAbrir)));
  clique("[data-cad-mais]", (b) => menuDaFicha(b, Number(b.dataset.cadMais)));
  clique("[data-cad-fechar]", () => { cad.aberta = null; cad.form = null; desenharCadastros(); });
  clique("[data-cad-alca]", () => { cad.largo = !cad.largo; desenharCadastros(); });
  clique("[data-cad-perguntar]", () => perguntarSobreFicha(cad.aberta));
  clique("[data-cad-email]", () => novoEmailPara(cad.aberta));
  clique("[data-cad-agendar]", () => agendarCom(cad.aberta));
  clique("[data-cad-senha]", () => avisoCert("senha por pessoa ainda não existe — hoje o PAULUS abre com a sua conta do Windows"));
  clique("[data-cad-acervo]", () => verNoAcervo(cad.aberta ? cad.aberta.nome : ""));
  clique("[data-cad-lancar]", () => lancarDespesa(cad.aberta));
  clique("[data-cad-salvar]", salvarFicha);
  clique("[data-cad-apagar]", () => apagarFicha(cad.aberta));

  cada("[data-cc]", (el) => {
    el.oninput = () => { cad.form[el.dataset.cc] = el.value; };
    el.onchange = () => {
      cad.form[el.dataset.cc] = el.value;
      // papel e vinculo mudam o que a ficha mostra; os outros campos so guardam
      if (el.dataset.cc === "tipo" || el.dataset.cc === "vinculo") desenharCadastros();
    };
  });
}

function abrirFicha(id) {
  const f = cad.fichas.find((x) => x.id === id);
  if (!f) return;
  cad.aberta = f;
  cad.form = formDaFicha(f);
  const visao = visaoDoTipo(f.tipo);
  if (visao !== cad.visao) { cad.visao = visao; cad.filtro = "todos"; }
  desenharCadastros();
}

function novaFicha() {
  const tipo = cad.visao === "equipe" ? "colaborador" : (cad.visao === "despesas" ? "despesa" : "cliente");
  cad.aberta = null;
  cad.form = formDaFicha({ tipo: tipo });
  desenharCadastros();
  const campo = document.querySelector('[data-cc="nome"]');
  if (campo) campo.focus();
}

function menuDaFicha(botao, id) {
  const f = cad.fichas.find((x) => x.id === id);
  if (!f) return;
  const itens = [{ icone: "open_in_new", rotulo: "Abrir a ficha", acao: () => abrirFicha(id) }];
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

async function salvarFicha() {
  const v = cad.form;
  if (!v) return;
  if (!String(v.nome || "").trim()) { avisoCert("o cadastro precisa de um nome"); return; }
  const dados = {
    tipo: v.tipo, nome: v.nome, documento: v.documento, telefone: v.telefone, email: v.email, endereco: v.endereco,
    honorario: v.honorario, dia_vencimento: Number(v.dia_vencimento) || 0, avisar_dias: Number(v.avisar_dias) || 0,
    observacao: v.observacao, vinculo: v.vinculo || "",
    salario_centavos: v.vinculo ? centavosDe(v.salario) : 0, encargos_centavos: v.vinculo ? centavosDe(v.encargos) : 0,
  };
  const r = await fetch("/api/cadastros", { method: "POST", headers: CAD_JSON, body: JSON.stringify({ id: v.id || null, dados: dados }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const ficha = await r.json();
  // Sugestao aceita ja nasce ligada aos documentos de onde veio.
  if (v._sugestao) {
    for (const a of v._sugestao.arquivos) {
      await fetch("/api/cadastros/" + ficha.id + "/vincular", { method: "POST", headers: CAD_JSON, body: JSON.stringify({ sha1: a.sha1, nome: a.nome }) });
    }
  }
  cad.aberta = { id: ficha.id };
  cad.form = { id: ficha.id };
  cad.visao = visaoDoTipo(ficha.tipo);
  avisoCert(v.id ? "ficha atualizada" : "cadastro salvo");
  mostrarCadastros();
}

async function apagarFicha(f) {
  if (!f) return;
  if (!(await confirmar({ titulo: "Apagar a ficha de " + f.nome + "?", contexto: "Cadastros", texto: "Os lançamentos e documentos continuam onde estão, só perdem a ligação com a ficha. " + LIXEIRA_TEXTO + " Restaurar religa tudo.", confirmar: "Apagar", perigo: true }))) return;
  const r = await fetch("/api/cadastros/" + f.id, { method: "DELETE" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  cad.aberta = null;
  cad.form = null;
  mostrarCadastros();
  avisarLixeira(r, () => mostrarCadastros());
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
  avisoCert(f.nome + " lançada em " + mesCurto(mes) + " — está em contas a pagar no Financeiro");
  cad.aberta = { id: f.id };
  cad.form = { id: f.id };
  mostrarCadastros();
}

