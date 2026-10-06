/* ------------------------------------ os cadastros pela conversa (T4) */
/*
   Pacote de telas de 01/10/2026: `Conversa - Cadastro`, `Conversa - Equipe`
   e `Conversa - Despesa fixa` (src/fichas_pela_conversa.py).

   A ficha abre na coluna da direita (o papel "formulario", 420 px), ja
   preenchida com o que a regra achou - o nome no Acervo com o CPF/CNPJ e o
   endereco que estao perto dele, a pessoa que a frase descreveu, o contrato
   anexo -, e cada campo que veio de um documento diz de onde ("lido em 22
   documentos"). Na conversa, o que acompanha a ficha: onde o nome aparece,
   a equipe com a pessoa nova marcada, as despesas fixas com a nova.

   Com a ficha aberta, a frase escrita na caixa corrige os campos que ela
   traz (POST /api/fichas/corrigir, por regra): o campo mudado ganha o selo
   "novo". Nada e gravado sem o clique em Salvar; depois de salvar, a
   conversa registra o que foi feito (/fazer "ficha").
*/

const fcn = {
  d: null,          // a proposta
  v: null,          // os valores da ficha
  caixa: null,      // o cartao da conversa
  achados: null,    // onde o nome aparece (cliente)
  ligar: null,      // Set: os documentos que entram na ficha
  todos: false,     // "Ver todos" aberto
  novos: new Set(), // os campos mudados pela conversa
  lista: null,      // a equipe ou as despesas, para a tabela da conversa
  modulos: null,    // o que o papel pode (Configuracoes › Acesso)
  salva: null,      // a ficha depois de salva
};
const FCN_AVISAR = [[0, "não avisar"], [1, "1 dia antes"], [3, "3 dias antes"], [5, "5 dias antes"], [7, "7 dias antes"], [10, "10 dias antes"]];
const FCN_VINCULOS = [["clt", "CLT"], ["estagio", "Estágio"], ["prolabore", "Pró-labore"], ["autonomo", "Autônomo"]];
const FCN_PEDIDO = {
  cliente: "Corrija um dado ou cadastre outra pessoa…",
  colaborador: "Mude o papel, o salário ou cadastre outra pessoa…",
  socio: "Mude o papel, o salário ou cadastre outra pessoa…",
  despesa: "Mude o valor, o dia ou cadastre outra despesa…",
};

function fcnIniciais(nome) {
  const p = String(nome || "?").replace(/[^\p{L}\s]/gu, " ").trim().split(/\s+/).filter((x) => x.length > 1 || /\p{Lu}/u.test(x));
  return ((p[0] || "?")[0] + (p.length > 1 ? p[p.length - 1][0] : (p[0] || "")[1] || "")).toUpperCase();
}

function fcnReais(centavos) {
  return (Number(centavos) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fcnCentavos(texto) {
  const limpo = String(texto || "").replace(/[^\d,]/g, "");
  if (!limpo) return 0;
  const [inteiro, cents] = limpo.split(",");
  return Number(inteiro || 0) * 100 + Number(((cents || "") + "00").slice(0, 2));
}

/* ------------------------------------------------------------ o cartao */

function cartaoDeFicha(d) {
  return '<div class="fcn-cartao" data-fcn-cartao="1"><div class="emc-carregando">' + esqueleto("lista") + "</div></div>";
}

function ligarFichaNaProposta(caixa, d) {
  const alvo = caixa.querySelector("[data-fcn-cartao]");
  if (!alvo) return;
  // A conversa reaberta: so o convite para abrir a ficha de novo.
  if (caixa.dataset.propostaGuardada) {
    alvo.innerHTML = '<div class="emc-fechado">' + ic("group", 16) + "<span>Ficha de “" + esc(d.titulo || "cadastro") + "”</span>" +
      '<button type="button" class="emc-botao" data-fcn-reabrir="1">Abrir a ficha</button></div>';
    alvo.querySelector("[data-fcn-reabrir]").onclick = () => abrirFichaNaConversa(alvo, d);
    return;
  }
  abrirFichaNaConversa(alvo, d);
}

async function abrirFichaNaConversa(alvo, d) {
  const c = d.campos || {};
  fcn.d = d;
  fcn.caixa = alvo;
  fcn.achados = d.achados || null;
  fcn.todos = false;
  fcn.novos = new Set();
  fcn.salva = null;
  fcn.v = valoresDaFicha(c);
  fcn.ligar = new Set(((fcn.achados || {}).documentos || []).map((x, i) => (x.campos.length > 1 ? i : -1)).filter((i) => i >= 0).slice(0, 6));
  await carregarListaDaFicha();
  desenharCartaoDaFicha();
  abrirFormularioDaFicha();
}

function valoresDaFicha(c) {
  const tipo = c.tipo || "cliente";
  if (tipo === "despesa") {
    return { tipo: tipo, nome: c.nome || "", valor: c.valor || "", dia: Number(c.dia) || 0, fornecedor: c.fornecedor || "", documento: c.documento || "",
      email: c.email || "", telefone: c.telefone || "", observacao: c.observacao || "", avisar_dias: Number(c.avisar_dias) || 0,
      lancar_mensal: c.lancar_mensal !== false };
  }
  if (tipo === "socio" || tipo === "colaborador") {
    return { tipo: tipo, nome: c.nome || "", funcao: c.funcao || "", email: c.email || "", documento: "", telefone: "",
      folha: Boolean(c.salario), salario: c.salario || "", inicio: c.inicio || "", vinculo: c.vinculo || (c.salario ? "clt" : ""),
      convidar: Boolean(c.convidar) };
  }
  return { tipo: "cliente", pessoa: c.pessoa || "fisica", nome: c.nome || "", documento: c.documento || "", endereco: c.endereco || "",
    telefone: c.telefone || "", email: c.email || "", honorario: "", dia_vencimento: 0, avisar_dias: 0 };
}

/* A equipe ou as despesas fixas, para a tabela da conversa. */
async function carregarListaDaFicha() {
  const v = fcn.v;
  fcn.lista = null;
  if (v.tipo === "cliente") return;
  try {
    if (v.tipo === "despesa") {
      const mes = new Date().toISOString().slice(0, 7);
      const [fichas, lanc] = await Promise.all([
        fetch("/api/cadastros?tipo=despesa").then((r) => r.json()),
        fetch("/api/financeiro/lancamentos?tipo=despesa&mes=" + mes).then((r) => (r.ok ? r.json() : { lancamentos: [] })).catch(() => ({ lancamentos: [] })),
      ]);
      fcn.lista = { fichas: fichas.fichas || [], lancamentos: lanc.lancamentos || lanc.itens || [], mes: mes };
    } else {
      const [socios, colab, contas, convites] = await Promise.all([
        fetch("/api/cadastros?tipo=socio").then((r) => r.json()),
        fetch("/api/cadastros?tipo=colaborador").then((r) => r.json()),
        fetch("/api/acesso/contas").then((r) => (r.ok ? r.json() : { contas: [] })).catch(() => ({ contas: [] })),
        fetch("/api/acesso/convites").then((r) => (r.ok ? r.json() : { convites: [] })).catch(() => ({ convites: [] })),
      ]);
      fcn.lista = { fichas: (socios.fichas || []).concat(colab.fichas || []), contas: contas.contas || [], convites: convites.convites || [],
        local: true };
      if (!fcn.modulos) {
        const r = await fetch("/api/acesso/permissoes/modulos").catch(() => null);
        fcn.modulos = r && r.ok ? (await r.json()).modulos || [] : [];
      }
    }
  } catch (err) { fcn.lista = fcn.lista || { fichas: [] }; }
}

function desenharCartaoDaFicha() {
  const alvo = fcn.caixa;
  if (!alvo || !alvo.isConnected) return;
  const v = fcn.v;
  if (v.tipo === "cliente") alvo.innerHTML = cartaoOndeAparece();
  else if (v.tipo === "despesa") alvo.innerHTML = cartaoDasDespesas();
  else alvo.innerHTML = cartaoDaEquipe();
  ligarCartaoDaFicha(alvo);
}

function cartaoOndeAparece() {
  const a = fcn.achados || { documentos: [], total: 0, sem_dado: 0 };
  const docs = fcn.todos ? a.documentos : a.documentos.slice(0, 6);
  const sem = a.total - docs.length;
  const linhas = docs.map((x, i) => {
    const marcado = fcn.ligar.has(i);
    return '<div class="fcn-doc">' + glifo(x.nome) + '<div class="fcn-doc-nome"><b title="' + esc(x.nome) + '">' + esc(x.nome) + "</b><small>" + esc(x.trecho) + "</small></div>" +
      '<span class="fcn-doc-campos">' + esc(x.campos.join(" · ")) + "</span>" +
      '<span class="fcn-doc-data">' + esc(x.data || "") + "</span>" +
      '<input type="checkbox" data-fcn-ligar="' + i + '"' + (marcado ? " checked" : "") + (x.sha1 ? "" : " disabled") +
      ' title="' + (x.sha1 ? "Entra na ficha" : "Sem a impressão digital do arquivo: não dá para ligar") + '"></div>';
  }).join("");
  const pendentes = Number((fcn.d.campos || {}).sugestoes_pendentes) || 0;
  return (a.total
    ? '<div class="fcn-tabela"><div class="fcn-tabela-cabeca"><span class="emc-kicker">Onde aparece</span><span class="vazio-flex"></span>' +
      "<small>" + fcn.ligar.size + " de " + a.total + " documento" + (a.total === 1 ? "" : "s") + " · os que entram na ficha</small></div>" +
      linhas +
      (sem > 0 || (!fcn.todos && a.documentos.length > 6)
        ? '<div class="fcn-tabela-pe"><small>' + (sem > 0 ? "mais " + plural(sem, "documento") + " citam o nome sem dado novo" : "") + "</small><span class=\"vazio-flex\"></span>" +
          (a.documentos.length > 6 ? '<button type="button" class="sv-ligacao" data-fcn-todos="1">' + (fcn.todos ? "Ver menos" : "Ver todos") + ic("chevron_right", 15) + "</button>" : "") + "</div>"
        : "") + "</div>"
    : "") +
    (pendentes
      ? '<div class="fcn-fila">' + ic("group", 16) + "<span>Ainda há <b>" + plural(pendentes, "nome") + "</b> lidos nos contratos sem ficha. " +
        (fcn.salva ? "" : "Posso preparar o próximo quando você salvar este.") + "</span>" +
        (fcn.salva && fcn.salva.proximo
          ? '<button type="button" class="emc-botao" data-fcn-proximo="1">Preparar ' + esc(fcn.salva.proximo) + "</button>"
          : '<button type="button" class="emc-botao" data-fcn-fila="1">Ver a fila</button>') + "</div>"
      : "");
}

function fcnFolhaDe(f) {
  return Number(f.salario_centavos) || 0;
}

function fcnAcessoDe(f) {
  const l = fcn.lista || {};
  const email = String(f.email || "").toLowerCase();
  if (!email) return ["sem e-mail", ""];
  const conta = (l.contas || []).find((c) => String(c.email || "").toLowerCase() === email);
  if (conta) return conta.papel === "titular" ? ["acesso total", "ok"] : ["entra no PAULUS", "ok"];
  const convite = (l.convites || []).find((c) => String(c.email || "").toLowerCase() === email && !c.usado);
  if (convite) return ["convite enviado", "ambar"];
  return ["sem acesso", ""];
}

function cartaoDaEquipe(semNova) {
  const v = semNova ? { tipo: "", nome: "", folha: false } : fcn.v;
  const fichas = ((fcn.lista || {}).fichas || []).slice().sort((a, b) => (a.tipo === b.tipo ? a.nome.localeCompare(b.nome) : a.tipo === "socio" ? -1 : 1));
  const linha = (nome, funcao, papel, acesso, folha, nova) =>
    '<div class="fcn-linha fcn-eq' + (nova ? " nova" : "") + '"><span class="fcn-quem"><span class="emc-avatar fcn-avatar-p">' + esc(fcnIniciais(nome)) + "</span>" +
    "<span><b>" + esc(nome || "(sem nome)") + "</b><small>" + esc(funcao || "") + "</small></span></span>" +
    '<span><span class="fcn-selo">' + esc(papel) + "</span></span>" +
    '<span><span class="fcn-selo ' + acesso[1] + '">' + esc(acesso[0]) + "</span></span>" +
    '<span class="fcn-num">' + (folha ? fcnReais(folha) : "—") + "</span></div>";
  const novoCentavos = !semNova && v.folha ? fcnCentavos(v.salario) : 0;
  const acessoNovo = v.convidar ? ["convite ao salvar", "ambar"] : (v.email ? ["sem acesso", ""] : ["sem e-mail", ""]);
  const inicio = v.inicio ? " · começa " + dataCurta(v.inicio) : "";
  const total = fichas.reduce((s, f) => s + fcnFolhaDe(f), 0) + novoCentavos;
  const socios = fichas.filter((f) => f.tipo === "socio").length + (v.tipo === "socio" ? 1 : 0);
  const colab = fichas.length - fichas.filter((f) => f.tipo === "socio").length + (v.tipo === "colaborador" ? 1 : 0);
  const mesDoInicio = v.inicio ? MESES_PT_LONGOS[Number(v.inicio.slice(5, 7)) - 1] : "";
  return '<div class="fcn-tabela"><div class="fcn-tabela-cabeca"><b>Equipe</b><span class="vazio-flex"></span><small>' +
    plural(socios, "sócio") + " · " + plural(colab, "colaborador", "colaboradores") + (semNova ? "" : " · a nova pessoa aparece marcada") + "</small></div>" +
    '<div class="fcn-linha fcn-eq fcn-titulos"><span>Nome e função</span><span>Papel</span><span>Acesso ao PAULUS</span><span class="fcn-num">Na folha</span></div>' +
    fichas.map((f) => linha(f.nome, f.observacao, f.tipo === "socio" ? "Sócio" : "Colaborador", fcnAcessoDe(f), fcnFolhaDe(f), false)).join("") +
    (semNova ? "" : linha(v.nome, (v.funcao || "") + inicio, v.tipo === "socio" ? "Sócio" : "Colaborador", acessoNovo, novoCentavos, true)) +
    '<div class="fcn-tabela-pe"><small>' + plural(fichas.length + (semNova ? 0 : 1), "pessoa") + "</small><span class=\"vazio-flex\"></span>" +
    (total ? "<small>folha <b class=\"fcn-num\">R$ " + fcnReais(total) + "</b>" + (mesDoInicio ? " a partir de " + mesDoInicio : "") + "</small>" : "") + "</div></div>";
}

const MESES_PT_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

function cartaoDasDespesas(semNova) {
  const v = semNova ? { nome: "", valor: "", dia: 0 } : fcn.v;
  const l = fcn.lista || { fichas: [], lancamentos: [] };
  const mes = MESES_PT_LONGOS[Number((l.mes || "2026-01").slice(5, 7)) - 1];
  const situacao = (f) => {
    const lanc = (l.lancamentos || []).find((x) => x.cadastro_id === f.id);
    if (!lanc) return ["—", ""];
    return lanc.liquidado_em ? ["pago", "ok"] : ["a pagar", lanc.atrasado ? "atraso" : "acc"];
  };
  const linha = (nome, sub, forn, dia, centavos, sit, nova) =>
    '<div class="fcn-linha fcn-desp' + (nova ? " nova" : "") + '"><span class="fcn-quem"><span><b>' + esc(nome || "(sem nome)") + "</b><small>" + esc(sub || "") + "</small></span></span>" +
    "<span>" + esc(forn || "—") + "</span>" +
    '<span class="fcn-mono">' + (dia ? "dia " + dia : "sem dia") + "</span>" +
    '<span class="fcn-num">' + (centavos ? fcnReais(centavos) : "—") + "</span>" +
    '<span><span class="fcn-selo ' + sit[1] + '">' + esc(sit[0]) + "</span></span></div>";
  const fichas = l.fichas || [];
  const novo = fcnCentavos(v.valor);
  const total = fichas.reduce((s, f) => s + fcnCentavos(f.honorario), 0) + novo;
  const comDia = fichas.filter((f) => Number(f.dia_vencimento)).length + (v.dia ? 1 : 0);
  return '<div class="fcn-tabela"><div class="fcn-tabela-cabeca"><b>Despesas fixas</b><span class="vazio-flex"></span><small>' + (semNova ? "" : "a nova despesa aparece marcada") + "</small></div>" +
    '<div class="fcn-linha fcn-desp fcn-titulos"><span>Despesa</span><span>Fornecedor</span><span>Vence</span><span class="fcn-num">Valor</span><span>' + esc(maiuscula(mes)) + "</span></div>" +
    (semNova ? "" : linha(v.nome, v.observacao, v.fornecedor, v.dia, novo, ["novo", "novo"], true)) +
    fichas.map((f) => linha(f.nome, f.observacao, f.fornecedor, Number(f.dia_vencimento), fcnCentavos(f.honorario), situacao(f), false)).join("") +
    '<div class="fcn-tabela-pe"><small>' + plural(fichas.length + (semNova ? 0 : 1), "despesa") + " · " + comDia + " com dia certo</small><span class=\"vazio-flex\"></span>" +
    '<small>por mês <b class="fcn-num">R$ ' + fcnReais(total) + "</b></small></div></div>";
}

function ligarCartaoDaFicha(alvo) {
  alvo.querySelectorAll("[data-fcn-ligar]").forEach((x) => {
    x.onchange = () => {
      const i = Number(x.dataset.fcnLigar);
      if (x.checked) fcn.ligar.add(i); else fcn.ligar.delete(i);
      desenharCartaoDaFicha();
      atualizarPeDaFicha();
    };
  });
  const todos = alvo.querySelector("[data-fcn-todos]");
  if (todos) todos.onclick = () => { fcn.todos = !fcn.todos; desenharCartaoDaFicha(); };
  const fila = alvo.querySelector("[data-fcn-fila]");
  if (fila) fila.onclick = () => { marcarDestino("cadastros"); mostrarCadastros(); };
  const proximo = alvo.querySelector("[data-fcn-proximo]");
  if (proximo) proximo.onclick = () => {
    $("pedido").value = "cadastra " + fcn.salva.proximo + " como cliente";
    enviar();
  };
}

/* --------------------------------------------- a ficha, na coluna */

function fcnNota(chave) {
  const v = fcn.v;
  const origem = ((fcn.d || {}).campos || {}).origem || {};
  if (fcn.novos.has(chave)) return '<em class="fcn-novo">novo</em>';
  if (chave === "documento" && v.documento) {
    const aviso = fcnAvisoDoDocumento();
    if (aviso) return '<em class="fcn-confira">' + esc(aviso) + "</em>";
  }
  if (origem[chave] && v.tipo === "cliente") return '<em class="fcn-lido">lido em ' + plural(origem[chave], "documento") + "</em>";
  if (origem[chave] && v.tipo === "despesa") return '<em class="fcn-lido">lido no contrato</em>';
  return "";
}

function fcnAvisoDoDocumento() {
  const v = fcn.v;
  const n = String(v.documento || "").replace(/\D/g, "");
  if (!n) return "";
  const cnpj = n.length === 14 || /[A-Z]/i.test(String(v.documento).replace(/[^\w]/g, "").slice(0, 12));
  if (v.tipo === "cliente" && v.pessoa === "juridica" && !cnpj && n.length === 11) return "confira: é um CPF, não um CNPJ";
  if (v.tipo === "cliente" && v.pessoa === "fisica" && cnpj) return "confira: é um CNPJ, não um CPF";
  if (n.length !== 11 && n.length !== 14) return "confira: faltam números";
  return "";
}

function fcnCampo(chave, rotulo, o) {
  o = o || {};
  const v = fcn.v;
  const valor = v[chave] === undefined ? "" : v[chave];
  const classe = "fcn-campo" + (o.meia ? " meia" : "");
  const entrada = o.opcoes
    ? '<select data-fcn="' + chave + '">' + o.opcoes.map(([x, r]) => '<option value="' + esc(x) + '"' + (String(x) === String(valor) ? " selected" : "") + ">" + esc(r) + "</option>").join("") + "</select>"
    : '<input type="' + (o.tipo || "text") + '" data-fcn="' + chave + '" value="' + esc(valor) + '" placeholder="' + esc(o.placeholder || "") + '"' +
      (o.mono ? ' class="fcn-mono"' : "") + (o.cnpjBusca ? ' data-cnpj-busca="1"' : "") + marcaCnpj(o.cnpj) + ' autocomplete="off">';
  return '<label class="' + classe + '"><span class="fcn-rotulo">' + esc(rotulo) + fcnNota(chave) + "</span>" + entrada + "</label>";
}

function fcnDias() {
  return [[0, "sem dia certo"]].concat(Array.from({ length: 31 }, (_, i) => [i + 1, "todo dia " + (i + 1)]));
}

function fcnInterruptor(chave, titulo, sub) {
  const ligado = Boolean(fcn.v[chave]);
  const classe = "interruptor-min" + (ligado ? " on" : "");
  return '<div class="fcn-liga"><span><b>' + esc(titulo) + "</b><small>" + esc(sub) + "</small></span>" +
    '<button type="button" class="' + classe + '" data-fcn-liga="' + chave + '" role="switch" aria-checked="' + ligado + '" aria-label="' + esc(titulo) + '"><i></i></button></div>';
}

function htmlDaFicha() {
  const v = fcn.v;
  let topo;
  let corpo;
  let pe;
  if (v.tipo === "cliente") {
    const pj = v.pessoa === "juridica";
    topo = fcnTopo('<span class="emc-avatar">' + esc(fcnIniciais(v.nome)) + "</span>", "Novo cliente", "Cadastros › Clientes") +
      '<span class="visoes fcn-abas"><button type="button" data-fcn-pessoa="juridica"' + (pj ? ' class="ativa"' : "") + ">Pessoa jurídica</button>" +
      '<button type="button" data-fcn-pessoa="fisica"' + (!pj ? ' class="ativa"' : "") + ">Pessoa física</button></span>";
    // O CNPJ digitado preenche nome, endereco e contato com os dados da Receita (js/39-campos.js).
    corpo = fcnCampo("nome", pj ? "Razão social ou nome" : "Nome", { cnpj: "razao_social" }) +
      fcnCampo("documento", pj ? "CNPJ / CPF" : "CPF / CNPJ", { placeholder: pj ? "00.000.000/0000-00" : "000.000.000-00", cnpjBusca: true }) +
      fcnCampo("endereco", "Endereço", { cnpj: "endereco" }) +
      '<div class="fcn-par">' + fcnCampo("telefone", "Telefone", { meia: true, placeholder: "(62) 99999-8888", mono: true, cnpj: "telefone" }) +
      fcnCampo("email", "E-mail para cobrança", { meia: true, placeholder: "nome@dominio.org", cnpj: "email" }) + "</div>" +
      '<span class="emc-kicker fcn-secao">Cobrança</span>' +
      '<div class="fcn-par">' + fcnCampo("honorario", "Honorário padrão", { meia: true, placeholder: "R$ 0,00", mono: true }) +
      fcnCampo("dia_vencimento", "Dia de vencimento", { meia: true, opcoes: fcnDias() }) + "</div>" +
      fcnCampo("avisar_dias", "Avisar antes", { opcoes: FCN_AVISAR });
    pe = '<button type="button" class="fantasma" data-fcn-nao="1">Ignorar</button>' +
      '<button type="button" class="primario" data-fcn-salvar="1">' + ic("check", 16) + "Salvar cadastro</button>";
  } else if (v.tipo === "despesa") {
    topo = fcnTopo('<span class="emc-avatar fcn-avatar-ic">' + ic("payments", 18) + "</span>", "Nova despesa fixa", "Cadastros › Despesas fixas");
    corpo = fcnCampo("nome", "Descrição") +
      '<div class="fcn-par">' + fcnCampo("valor", "Valor mensal", { meia: true, placeholder: "R$ 0,00", mono: true }) +
      fcnCampo("dia", "Dia de vencimento", { meia: true, opcoes: fcnDias() }) + "</div>" +
      '<span class="emc-kicker fcn-secao">Fornecedor</span>' +
      fcnCampo("fornecedor", "Nome", { cnpj: "razao_social" }) +
      fcnCampo("documento", "CNPJ / CPF do fornecedor", { mono: true, cnpjBusca: true }) +
      '<div class="fcn-par">' + fcnCampo("email", "E-mail", { meia: true, cnpj: "email" }) + fcnCampo("telefone", "Telefone", { meia: true, mono: true, cnpj: "telefone" }) + "</div>" +
      fcnCampo("observacao", "Anotação") +
      fcnCampo("avisar_dias", "Avisar antes", { opcoes: FCN_AVISAR }) +
      fcnInterruptor("lancar_mensal", "Lançar no Financeiro todo mês", "entra como conta a pagar do mês, vencendo no dia" + (v.dia ? " " + v.dia : " 1º"));
    pe = '<button type="button" class="fantasma" data-fcn-nao="1">Cancelar</button>' +
      '<button type="button" class="primario" data-fcn-salvar="1">' + ic("check", 16) + "Salvar cadastro</button>";
  } else {
    const socio = v.tipo === "socio";
    topo = fcnTopo('<span class="emc-avatar">' + esc(fcnIniciais(v.nome)) + "</span>", "Nova pessoa", "Cadastros › Equipe") +
      '<span class="visoes fcn-abas"><button type="button" data-fcn-papel="socio"' + (socio ? ' class="ativa"' : "") + ">Sócio</button>" +
      '<button type="button" data-fcn-papel="colaborador"' + (!socio ? ' class="ativa"' : "") + ">Colaborador</button></span>";
    const pode = podeDoPapel(socio);
    const local = (fcn.modulos || []).length > 0;
    corpo = fcnCampo("nome", "Nome") + fcnCampo("funcao", "Função") + fcnCampo("email", "E-mail Google", { placeholder: "nome@gmail.com" }) +
      '<div class="fcn-par">' + fcnCampo("documento", "CPF", { meia: true, placeholder: "000.000.000-00", mono: true }) +
      fcnCampo("telefone", "Telefone", { meia: true, placeholder: "(94) 99999-8888", mono: true }) + "</div>" +
      '<div class="fcn-caixa">' + fcnInterruptor("folha", "Entra na folha", "vira a folha do Financeiro, todo mês") +
      (v.folha
        ? '<div class="fcn-par">' + fcnCampo("salario", "Valor", { meia: true, placeholder: "R$ 0,00", mono: true }) +
          fcnCampo("inicio", "Desde", { meia: true, tipo: "date" }) + "</div>" +
          fcnCampo("vinculo", "Vínculo", { opcoes: FCN_VINCULOS })
        : "") + "</div>" +
      (local
        ? '<div class="fcn-caixa">' + fcnInterruptor("convidar", "Convidar para o PAULUS", "o link de entrada nasce quando você salvar") +
          (v.convidar ? '<span class="fcn-rotulo">O que este papel pode</span><ul class="fcn-pode">' + pode.map(([ok, texto]) =>
            '<li class="' + (ok ? "ok" : "nao") + '">' + ic(ok ? "check_circle" : "close", 15) + esc(texto) + "</li>").join("") + "</ul>" +
            '<small class="fcn-dica">Muda depois em Configurações › Acesso de fora › Pessoas.</small>' : "") + "</div>"
        : "");
    pe = '<button type="button" class="fantasma" data-fcn-nao="1">Cancelar</button>' +
      '<button type="button" class="primario" data-fcn-salvar="1">' + ic("check", 16) + (v.convidar && local ? "Salvar e convidar" : "Salvar") + "</button>";
  }
  return '<div class="fcn" data-fl-tipo="ficha">' + topo +
    '<div class="fcn-corpo" data-cnpj-grupo="1">' + corpo + "</div>" +
    '<div class="fcn-pe"><small class="fcn-resumo" data-fcn-resumo="1"></small><span class="dialogo-aviso" data-fcn-aviso="1"></span>' + pe + "</div></div>";
}

function fcnTopo(avatar, titulo, caminho) {
  return '<div class="fcn-topo">' + avatar + "<span><b>" + esc(titulo) + "</b><small>" + esc(caminho) + "</small></span></div>";
}

/* O que o colaborador pode, do padrao de Configuracoes › Acesso: o socio
   entra com tudo no nivel mais alto. */
function podeDoPapel(socio) {
  return (fcn.modulos || []).filter((m) => ["documentos", "cadastros", "agenda", "email", "aprovacoes", "financeiro"].includes(m.id)).map((m) => {
    const nivel = socio ? m.niveis[m.niveis.length - 1] : m.niveis.find((n) => n.id === m.nivel) || m.niveis[0];
    const rotulo = nivel.rotulo;
    return [nivel.id !== "nao", m.rotulo + ": " + rotulo];
  });
}

function resumoDaFichaNoLado() {
  const v = fcn.v;
  if (v.tipo === "cliente") return fcn.ligar.size ? "ligada a " + plural(fcn.ligar.size, "documento") : "sem documento ligado";
  if (v.tipo === "despesa") return (v.valor ? "– " + v.valor : "sem valor") + " · " + (v.dia ? "todo dia " + v.dia : "sem dia certo");
  return [v.tipo === "socio" ? "sócio" : "colaborador", v.folha ? "na folha" : "", v.convidar && (fcn.modulos || []).length ? "convite" : ""].filter(Boolean).join(" · ");
}

function atualizarPeDaFicha() {
  const r = document.querySelector("#lado-ferramenta [data-fcn-resumo]");
  if (r) r.textContent = resumoDaFichaNoLado();
}

function abrirFormularioDaFicha() {
  const v = fcn.v;
  abrirNoLado("formulario", {
    chave: "ficha",
    html: htmlDaFicha(),
    ligar: ligarFormularioDaFicha,
    aoFechar: () => { fcn.v = null; $("pedido").placeholder = "Pergunte outra coisa ou aponte outra pasta…"; },
  });
  $("pedido").placeholder = FCN_PEDIDO[v.tipo] || FCN_PEDIDO.cliente;
}

function redesenharFichaNoLado() {
  const lado = $("lado-ferramenta");
  if (!lado || papelDoLado() !== "formulario" || !fcn.v) return;
  const rolagem = (lado.querySelector(".fcn-corpo") || {}).scrollTop || 0;
  lado.innerHTML = htmlDaFicha();
  ligarFormularioDaFicha(lado);
  const corpo = lado.querySelector(".fcn-corpo");
  if (corpo) corpo.scrollTop = rolagem;
}

function ligarFormularioDaFicha(raiz) {
  atualizarPeDaFicha();
  raiz.querySelectorAll("[data-fcn]").forEach((x) => {
    const chave = x.dataset.fcn;
    const ler = () => {
      const numero = chave === "dia" || chave === "dia_vencimento" || chave === "avisar_dias";
      fcn.v[chave] = numero ? Number(x.value) || 0 : x.value;
      fcn.novos.delete(chave);
      atualizarPeDaFicha();
      if (fcn.v.tipo !== "cliente") desenharCartaoDaFicha();
    };
    x.addEventListener("input", ler);
    x.addEventListener("change", () => {
      ler();
      if (chave === "documento" || chave === "dia") redesenharFichaNoLado();
    });
  });
  raiz.querySelectorAll("[data-fcn-pessoa]").forEach((b) => { b.onclick = () => { fcn.v.pessoa = b.dataset.fcnPessoa; redesenharFichaNoLado(); }; });
  raiz.querySelectorAll("[data-fcn-papel]").forEach((b) => { b.onclick = () => { fcn.v.tipo = b.dataset.fcnPapel; redesenharFichaNoLado(); desenharCartaoDaFicha(); }; });
  raiz.querySelectorAll("[data-fcn-liga]").forEach((b) => {
    b.onclick = () => {
      const chave = b.dataset.fcnLiga;
      fcn.v[chave] = !fcn.v[chave];
      if (chave === "folha" && fcn.v.folha && !fcn.v.vinculo) fcn.v.vinculo = "clt";
      redesenharFichaNoLado();
      desenharCartaoDaFicha();
    };
  });
  raiz.querySelector("[data-fcn-nao]").onclick = naoSalvarFicha;
  raiz.querySelector("[data-fcn-salvar]").onclick = (e) => salvarFichaDaConversa(e.currentTarget);
}

async function naoSalvarFicha() {
  const v = fcn.v;
  const caixa = fcn.caixa;
  if (v && v.tipo === "cliente" && v.nome) {
    // Ignorar: o nome sai da fila dos nomes lidos sem ficha (volta por Cadastros).
    await fetch("/api/cadastros/sugestoes/ignorar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome: v.nome }) }).catch(() => null);
  }
  voltarAoContexto();
  if (caixa && caixa.isConnected) {
    caixa.insertAdjacentHTML("beforeend", '<p class="explica">' + (v && v.tipo === "cliente" ? "Tudo bem — não cadastrei, e o nome saiu da fila (volta em Cadastros › Sugestões)." : "Tudo bem — não cadastrei nada.") + "</p>");
  }
}

/* Os dados para POST /api/cadastros, no formato das fichas de sempre. */
function dadosDaFicha() {
  const v = fcn.v;
  if (v.tipo === "cliente") {
    return { tipo: "cliente", nome: v.nome, documento: v.documento, endereco: v.endereco, telefone: v.telefone, email: v.email,
      honorario: v.honorario, dia_vencimento: v.dia_vencimento, avisar_dias: v.avisar_dias };
  }
  if (v.tipo === "despesa") {
    return { tipo: "despesa", nome: v.nome, honorario: v.valor, dia_vencimento: v.dia, fornecedor: v.fornecedor, documento: v.documento,
      email: v.email, telefone: v.telefone, observacao: v.observacao, avisar_dias: v.avisar_dias, lancar_mensal: v.lancar_mensal ? 1 : 0 };
  }
  return { tipo: v.tipo, nome: v.nome, observacao: v.funcao, email: v.email, documento: v.documento, telefone: v.telefone,
    vinculo: v.folha ? v.vinculo || "clt" : "", salario_centavos: v.folha ? fcnCentavos(v.salario) : 0, inicio: v.folha ? v.inicio : "" };
}

async function salvarFichaDaConversa(botao) {
  const v = fcn.v;
  const aviso = document.querySelector("#lado-ferramenta [data-fcn-aviso]");
  const diz = (t) => { if (aviso) aviso.textContent = t; };
  if (!String(v.nome || "").trim()) { diz("falta o nome"); return; }
  if (v.tipo === "despesa" && !fcnCentavos(v.valor)) { diz("falta o valor"); return; }
  const local = (fcn.modulos || []).length > 0;
  const convidar = (v.tipo === "socio" || v.tipo === "colaborador") && v.convidar && local;
  if (convidar && !/@/.test(v.email || "")) { diz("o convite precisa do e-mail Google"); return; }
  botao.disabled = true;
  const r = await fetch("/api/cadastros", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dados: dadosDaFicha() }) }).catch(() => null);
  if (!r || !r.ok) { botao.disabled = false; diz("não salvei: " + (r ? await erroDe(r) : "sem resposta")); return; }
  const ficha = await r.json();
  // Os documentos marcados entram na ficha (o mesmo /vincular de Cadastros).
  let ligados = 0;
  if (v.tipo === "cliente") {
    const docs = (fcn.achados || {}).documentos || [];
    for (const i of fcn.ligar) {
      const x = docs[i];
      if (!x || !x.sha1) continue;
      const l = await fetch("/api/cadastros/" + ficha.id + "/vincular", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sha1: x.sha1, nome: x.nome }) }).catch(() => null);
      if (l && l.ok) ligados++;
    }
  }
  let convite = null;
  if (convidar) {
    const niveis = {};
    if (v.tipo === "socio") (fcn.modulos || []).forEach((m) => { niveis[m.id] = m.niveis[m.niveis.length - 1].id; });
    const c = await fetch("/api/acesso/convites", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome: v.nome, email: v.email, permissoes: niveis }) }).catch(() => null);
    if (c && c.ok) convite = await c.json();
    else avisoCert("a ficha foi salva, mas o convite não saiu: " + (c ? await erroDe(c) : "sem resposta"), { tom: "erro" });
  }
  const feito = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tipo: "ficha", campos: { id: ficha.id, ligados: ligados, convite: Boolean(convite) } }),
  }).then((x) => (x.ok ? x.json() : null)).catch(() => null);
  // O proximo nome da fila, para "Preparar o proximo".
  let proximo = "";
  if (v.tipo === "cliente" && Number((fcn.d.campos || {}).sugestoes_pendentes)) {
    try {
      const s = await (await fetch("/api/cadastros/sugestoes")).json();
      proximo = ((s.sugestoes || [])[0] || {}).nome || "";
    } catch (err) { /* sem o proximo, fica o "Ver a fila" */ }
  }
  fcn.salva = { ficha: ficha, proximo: proximo };
  const caixa = fcn.caixa;
  await carregarListaDaFicha();
  if (v.tipo === "cliente") desenharCartaoDaFicha();
  else if (caixa && caixa.isConnected) {
    caixa.innerHTML = ficha.tipo === "despesa" ? cartaoDasDespesas(true) : cartaoDaEquipe(true);
  }
  voltarAoContexto();
  notaDeFeitoNaConversa(feito && feito.resumo ? feito.resumo + "." : "Salvei a ficha.");
  if (convite && convite.link) mostrarConviteNaConversa(v, convite.link);
}

function mostrarConviteNaConversa(v, link) {
  const nota = document.createElement("div");
  nota.className = "resposta";
  nota.innerHTML = '<div class="fcn-convite">' + ic("link", 16) + "<span>O link de entrada de " + esc(v.nome) + " vale por 7 dias e para uma entrada. Mande para " +
    esc(v.email) + ".</span><code>" + esc(link) + '</code><button type="button" class="emc-botao" data-fcn-copiar="1">' + ic("content_copy", 15) + "Copiar o link</button></div>";
  $("centro").appendChild(nota);
  nota.querySelector("[data-fcn-copiar]").onclick = async () => {
    try { await navigator.clipboard.writeText(link); avisoCert("link copiado", { tom: "ok" }); } catch (err) { avisoCert("selecione e copie o link", { tom: "erro" }); }
  };
  rolar();
}

/* ------------------------------ a correcao escrita, com a ficha aberta */

function fichaAbertaNoLado() {
  return Boolean(fcn.v && papelDoLado() === "formulario" && document.querySelector("#lado-ferramenta [data-fl-tipo='ficha']"));
}

/* O gancho de enviar(): com a ficha aberta, a frase que traz um dado
   corrige o campo (selo "novo"); a que nao traz segue para a conversa. */
async function pedidoNaFicha(pedido) {
  if (!fichaAbertaNoLado()) return false;
  if (/^\s*(cadastr|coloc|lanc|lanç|registr|adicion|inclu|crie|abra|gere|como est)/i.test(pedido)) return false;
  const r = await fetch("/api/fichas/corrigir", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texto: pedido }) }).catch(() => null);
  const campos = r && r.ok ? (await r.json()).campos || {} : {};
  const v = fcn.v;
  const mapa = v.tipo === "despesa" ? { valor: "valor", dia: "dia" } : v.tipo === "cliente" ? { valor: "honorario", dia: "dia_vencimento" } : { valor: "salario" };
  const mudou = [];
  Object.keys(campos).forEach((k) => {
    const alvo = mapa[k] || k;
    if (!(alvo in v)) return;
    v[alvo] = campos[k];
    if (alvo === "salario") v.folha = true;
    fcn.novos.add(alvo);
    mudou.push(alvo);
  });
  if (!mudou.length) return false;
  const centro = $("centro");
  centro.insertAdjacentHTML("beforeend", bolhaPessoa(pedido));
  const rotulos = { documento: "o documento", telefone: "o telefone", email: "o e-mail", endereco: "o endereço", nome: "o nome", honorario: "o honorário",
    dia_vencimento: "o dia", valor: "o valor", dia: "o dia", salario: "o salário" };
  notaDeFeitoNaConversa("Mudei " + mudou.map((k) => rotulos[k] || k).join(", ") + " na ficha ao lado — confira e salve.");
  redesenharFichaNoLado();
  desenharCartaoDaFicha();
  return true;
}
