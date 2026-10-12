/* CONFIGURACOES › NOTA FISCAL, NO MOLDE DO EMISSOR DO SITE (pedido de
   11/10/2026; base: /admin/#nfse do paulus.ia.br). Quatro abas - Notas,
   Emitir NFS-e, Clientes e Parametros -, o ambiente e o "Testar comunicacao"
   na mesma linha; cartoes com o rotulo em monoespaco. Reaproveita as acoes
   de js/90-nfse.js (data-nfse-acao) e os blocos de Parametros que ja
   existiam (impostos, teste e producao, contador, recorrentes, tabelas). */
(function () {
  if (typeof secaoNfse !== "function") return;
  const nfv = { aba: "", notas: null, filtro: "todos", busca: "", tomador: {} };
  try { nfv.aba = localStorage.getItem("paulus.nfse.aba") || "notas"; } catch (e) { nfv.aba = "notas"; }
  const pref = (k, p) => { try { const v = localStorage.getItem("paulus.nfse." + k); return v === null ? p : v === "1"; } catch (e) { return p; } };

  const carregarAntes = carregarSecao;
  carregarSecao = async function () {   // eslint-disable-line no-func-assign
    await carregarAntes.apply(this, arguments);
    if (cfg.secao !== "nfse") return;
    try { const r = await fetch("/api/nfse/notas"); nfv.notas = r.ok ? ((await r.json()).notas || []) : []; } catch (e) { nfv.notas = []; }
  };

  const kv = (rot, val, tom) => '<div class="nfv-kv"><span>' + esc(rot) + '</span><b class="' + (tom || "") + '">' + esc(val || "—") + "</b></div>";
  const liga = (attrs, titulo, sub, on) => '<div class="ag-toggle' + (on ? " on" : "") + '" ' + attrs + ' role="switch" tabindex="0" aria-checked="' + Boolean(on) + '">' +
    '<span class="duas-linhas"><b>' + esc(titulo) + "</b><small>" + esc(sub) + "</small></span><i></i></div>";
  const campo = (k, rot, v, dica, largo) => '<div class="ag-campo' + (largo ? " nfv-largo" : "") + '"><label>' + esc(rot) + '</label><input type="text" data-nfv-campo="' + k + '" value="' +
    esc(v || "") + '"' + (dica ? ' placeholder="' + esc(dica) + '"' : "") + "></div>";
  // Um passo antigo vira cartao: o cabecalho numerado sai, o titulo vai para o rotulo.
  const comoCartao = (sec, titulo, meta) => {
    if (!sec) return "";
    const cab = sec.querySelector(".nfse-passo-cabeca");
    const explica = cab && cab.querySelector(".cfg-explica");
    if (cab) cab.remove();
    return cartaoCfg(titulo, meta ? metaCfg(meta) : "", (explica ? explica.outerHTML : "") + sec.innerHTML);
  };

  function abaNotas(n) {
    const cert = n.certificado || {};
    const c = cert.certificado || {};
    const p = n.prestador || {};
    const d = p.dados || {};
    const s = d.servico || {};
    const mun = n.municipio || {};
    const certificado = cartaoCfg("Certificado digital A1", metaCfg(cert.instalado ? "instalado" : "falta instalar"),
      zonaCertificado(cert.instalado) +
      '<div class="nfv-cert-linha">' +
      '<input type="password" id="nfse-pfx-senha" placeholder="senha do certificado" autocomplete="off">' +
      '<input type="checkbox" id="nfse-pfx-guardar" checked hidden>' +
      '<button class="com-icone" data-nfse-acao="certificado">' + ic(cert.instalado ? "sync" : "check", 16) + (cert.instalado ? "Trocar" : "Instalar") + "</button></div>" +
      '<p class="cfg-explica">O .pfx e a senha ficam neste computador, cifrados. O mesmo A1 que o escritório usa na prefeitura; token (A3) não serve.</p>' +
      (cert.instalado ? '<div class="nfv-kvs">' + kv("Nome", c.titular) + kv("CNPJ/CPF", c.documento) +
        kv("Vencimento", c.valido_ate, c.vencido ? "erro" : "") +
        kv("Senha", cert.senha_guardada ? "guardada neste computador" : (cert.minutos_restantes ? "na memória por " + cert.minutos_restantes + " min" : "pedida a cada uso")) + "</div>" : "") +
      (cert.avisos || []).map((a) => '<p class="nfv-alerta">' + ic("error", 16) + esc(a) + "</p>").join("") +
      (cert.instalado ? '<div class="cfg-botoes"><button class="com-icone" data-nfse-acao="remover-certificado">' + ic("close", 16) + "Tirar o certificado</button></div>" : ""));
    const chaves = '<div class="cfg-cartao nfv-chaves"><div class="cfg-cartao-corpo"><div class="cfg-campos">' +
      liga('data-nfse-acao="ligar"', "Emitir NFS-e pelo Paulus", "desligada, o “Emitir nota” some do Financeiro e dos Serviços", n.ligado) +
      liga('data-nfv-pref="ao_receber"', "Preparar a nota ao receber", "quando um recebimento entra no Financeiro, o rascunho da nota vai para Aprovações", pref("ao_receber", false)) +
      liga('data-nfv-pref="por_email"', "Mandar também por e-mail", "PDF e XML anexos, para o e-mail fiscal do cliente, depois do seu sim", pref("por_email", false)) +
      "</div></div></div>";
    const resumo = '<div class="cfg-cartao nfv-resumo"><div class="cfg-cartao-corpo"><div class="nfv-kvs">' +
      kv("Prestador", [d.razao_social, d.documento].filter(Boolean).join(" · ")) +
      kv("Serviço", [s.ctribnac || s.codigo ? "cTribNac " + (s.ctribnac || s.codigo) : "", s.nbs ? "NBS " + s.nbs : "", s.aliquota ? "ISS " + s.aliquota + "%" : ""].filter(Boolean).join(" · ")) +
      kv("Município", mun.frase || p.municipio_nome || d.municipio, mun.situacao === "conveniado" ? "" : "acc") +
      kv("Próxima DPS", d.proxima_dps ? "nº " + d.proxima_dps + " · série " + (d.serie || 1) : "") + "</div></div></div>";
    const notas = nfv.notas || [];
    /* A lista no padrao da lista de conversas (lc-linha, js/01): a linha abre
       a nota; o "..." traz o que da para fazer nela, conforme a situacao. */
    const TOM = { autorizada: "ok", emitida: "ok", rascunho: "atencao", aguardando: "atencao", rejeitada: "erro" };
    const linhas = notas.length ? notas.slice(0, ULTIMAS).map(linhaDaNota).join("") : '<p class="nfv-vazio">Nenhuma nota ainda.</p>';
    const verTodas = notas.length > ULTIMAS ? '<button type="button" class="nfv-ver-todas" data-nfv-todas="1"><span>Ver todas as ' + notas.length + " notas</span>" + ic("arrow_forward", 16) + "</button>" : "";
    const tabela = cartaoCfg("Últimas notas", metaCfg(notas.length > ULTIMAS ? ULTIMAS + " de " + notas.length : (notas.length === 1 ? "1 nota" : notas.length + " notas")),
      '<div class="nfv-lista">' + linhas + "</div>" + verTodas);
    /* O certificado mora em Conexoes: aqui so o resumo e o atalho. */
    const resumoCert = '<div class="cfg-cartao nfv-cert-resumo"><div class="cfg-cartao-corpo"><div class="cfx-aponta">' + ic("workspace_premium", 22) +
      '<span class="duas-linhas"><b>' + esc(cert.instalado ? (c.titular || "Certificado instalado") : "Nenhum certificado para as notas") + "</b><small>" +
      esc(cert.instalado ? ["certificado A1", c.documento, c.valido_ate ? "vence em " + c.valido_ate : ""].filter(Boolean).join(" · ") : "instale o A1 em Configurações › Certificado digital") + "</small></span>" +
      '<button class="com-icone" data-cfx-ir="1">' + ic("settings", 16) + (cert.instalado ? "Gerenciar certificado" : "Instalar certificado") + "</button></div></div></div>";
    return resumoCert + '<div class="nfv-duas">' + chaves + resumo + "</div>";
  }

  const ULTIMAS = 5;
  function linhaDaNota(x) {
      const cliente = x.tomador_nome || (x.rascunho && x.rascunho.tomador && x.rascunho.tomador.nome) || "sem cliente";
      const comp = x.competencia || (x.rascunho && x.rascunho.competencia) || "";
      const mes = comp ? comp.split("-").reverse().join("/") : "";
      return '<div class="lc-linha nfv-nota" role="button" tabindex="0" data-nfv-nota="' + esc(x.id) + '" data-estado="' + esc(x.estado || "") + '">' +
        '<span class="nfv-quem"><b>' + esc(cliente) + "</b><small>" + esc([x.numero_nfse || "rascunho", mes].filter(Boolean).join(" · ")) + "</small></span>" +
        '<span class="nfv-valor">' + esc(x.valor || "") + "</span>" +
        '<span class="nfv-sit ' + esc(x.estado || "") + '"><i></i>' + esc(x.estado_rotulo || x.estado || "") + "</span>" +
        '<button class="lc-mais" data-nfv-menu="1" title="Mais" aria-label="Mais">' + ic("more_horiz", 17) + "</button></div>" +
        (String(nfv.aberta) === String(x.id) ? detalheDaNota(x, cliente, comp) : "");
  }

  /* A TELA DAS NOTAS EMITIDAS (pedido de 11/10/2026): a lista inteira, com
     filtro por periodo (competencia), tomador, situacao e ambiente, e a soma
     do que esta na tela. Abre pelo "Ver todas"; a seta volta para as abas. */
  const filtro = { periodo: "tudo", situacao: "todas", termo: "", de: "", ate: "", pagina: 1, porPagina: 10 };
  const PERIODOS = [["tudo", "Todo o período"], ["mes", "Este mês"], ["anterior", "Mês passado"], ["3m", "Últimos 3 meses"], ["ano", "Este ano"], ["outro", "Outro período"]];
  const isoD = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  // Os atalhos preenchem o De e o Ate; mexer nas datas vira "Outro periodo".
  function aplicarPeriodo(p) {
    const h = new Date(), a = h.getFullYear(), m = h.getMonth();
    const faixa = { tudo: ["", ""], mes: [new Date(a, m, 1), h], anterior: [new Date(a, m - 1, 1), new Date(a, m, 0)], "3m": [new Date(a, m - 2, 1), h], ano: [new Date(a, 0, 1), h] }[p];
    filtro.periodo = p;
    if (faixa) { filtro.de = faixa[0] ? isoD(faixa[0]) : ""; filtro.ate = faixa[1] ? isoD(faixa[1]) : ""; }
    filtro.pagina = 1;
  }
  window.nfvAplicarPeriodo = aplicarPeriodo;
  const SITUACOES = [["todas", "Todas as situações"], ["autorizada", "Autorizadas"], ["rascunho", "Rascunhos"], ["aguardando", "Aguardando aprovação"], ["cancelada", "Canceladas"], ["substituida", "Substituídas"], ["rejeitada", "Rejeitadas"]];
  const reaisNum = (v) => typeof v === "number" ? v : Number(String(v || "0").replace(/[^\d,]/g, "").replace(",", ".")) || 0;
  // Pela data de emissao (o rascunho, pela competencia).
  function noPeriodo(x, comp) {
    if (!filtro.de && !filtro.ate) return true;
    const d = String(x.emitida_em || (comp ? comp + "-01" : "")).slice(0, 10);
    if (!d) return false;
    return (!filtro.de || d >= filtro.de) && (!filtro.ate || d <= filtro.ate);
  }
  // O calendario do sistema (calendarioPopover, js/16), sem os atalhos de
  // prazo nem o passado em vermelho: aqui o passado e o normal.
  const dataBRc = (iso) => iso ? iso.split("-").reverse().join("/") : "";
  function botaoData(k, rot) {
    const v = filtro[k];
    return '<button type="button" class="escolha-botao data-botao nfv-cal' + (v ? "" : " vazio") + '" data-nfv-cal="' + k + '" aria-label="' + rot + '">' +
      '<span class="escolha-rotulo">' + esc(v ? dataBRc(v) : rot) + "</span>" + ic("calendar_month", 18) + "</button>";
  }
  window.nfvCalendario = (botao) => {
    const k = botao.dataset.nfvCal;
    if (typeof calendarioAberto !== "undefined" && calendarioAberto) { fecharCalendario(); return; }
    calendarioPopover(botao, { valor: filtro[k], limpar: true,
      aoEscolher: (data) => {
        filtro[k] = data || "";
        if (filtro.de && filtro.ate && filtro.de > filtro.ate) { const t = filtro.de; filtro.de = filtro.ate; filtro.ate = t; }
        filtro.periodo = filtro.de || filtro.ate ? "outro" : "tudo"; filtro.pagina = 1;
        redesenhar();
      } });
  };
  function telaTodas() {
    const q = filtro.termo.trim().toLowerCase();
    const todas = nfv.notas || [];
    const lista = todas.filter((x) => {
      const cliente = x.tomador_nome || (x.rascunho && x.rascunho.tomador && x.rascunho.tomador.nome) || "";
      const comp = x.competencia || (x.rascunho && x.rascunho.competencia) || "";
      return noPeriodo(x, comp) && (filtro.situacao === "todas" || x.estado === filtro.situacao) &&
        (!q || [cliente, x.tomador_documento, x.numero_nfse, x.servico].join(" ").toLowerCase().includes(q));
    });
    const soma = lista.filter((x) => x.estado !== "cancelada" && x.estado !== "substituida").reduce((s, x) => s + reaisNum(x.valor), 0);
    const total = lista.length, porPag = filtro.porPagina, paginas = Math.max(1, Math.ceil(total / porPag));
    filtro.pagina = Math.min(Math.max(1, filtro.pagina), paginas);
    const ini = (filtro.pagina - 1) * porPag, pagina = lista.slice(ini, ini + porPag);
    const opc = (lst, v) => lst.map(([k, r]) => '<option value="' + k + '"' + (k === v ? " selected" : "") + ">" + r + "</option>").join("");
    return '<section class="sv-secao nf-secao nfv-emitidas" aria-labelledby="nf-t-emitidas"><div class="sv-secao-cabeca">' +
      '<span class="sv-secao-titulo" id="nf-t-emitidas">' + ic("receipt_long", 16) + "Notas do escritório para os clientes</span>" +
      '<span class="sv-secao-meta">' + esc((total === 1 ? "1 nota" : total + " notas") + " · soma " + soma.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })) + "</span></div>" +
      '<div class="nfv-filtros">' +
        '<label class="nfv-busca">' + ic("search", 16) + '<input type="search" data-nfv-termo="1" placeholder="tomador, CPF/CNPJ, número ou serviço" value="' + esc(filtro.termo) + '"></label>' +
        '<div class="ag-campo nfv-filtro"><select data-nfv-filtro-sel="periodo">' + opc(PERIODOS, filtro.periodo) + "</select></div>" +
        '<div class="nfv-datas">' + botaoData("de", "De") + "<span>até</span>" + botaoData("ate", "Até") + "</div>" +
        '<div class="ag-campo nfv-filtro"><select data-nfv-filtro-sel="situacao">' + opc(SITUACOES, filtro.situacao) + "</select></div>" +
      "</div>" +
      (pagina.length ? '<div class="nf-rolagem"><table class="nf-tabela nfv-tabela-em"><thead><tr><th>Competência</th><th>Nº</th><th>Tomador</th><th>Valor</th><th>Situação</th><th>Ambiente</th><th></th></tr></thead><tbody>' +
        pagina.map(linhaTabela).join("") + "</tbody></table></div>" : '<p class="nfv-vazio">Nenhuma nota com estes filtros.</p>') +
        (total ? '<div class="nfv-paginas"><span class="nfv-pag-conta">' + (ini + 1) + "–" + Math.min(ini + porPag, total) + " de " + total + "</span>" +
          '<div class="ag-campo nfv-por-pag"><select data-nfv-por-pagina="1" aria-label="Notas por página">' + [10, 20, 50, 100].map((n) => '<option value="' + n + '"' + (n === porPag ? " selected" : "") + ">" + n + " por página</option>").join("") + "</select></div>" +
          '<span class="cresce"></span>' +
          '<button type="button" class="botao-icone" data-nfv-pag="-1" aria-label="Página anterior"' + (filtro.pagina <= 1 ? " disabled" : "") + ">" + ic("chevron_left", 18) + "</button>" +
          '<span class="nfv-pag-num">' + filtro.pagina + " / " + paginas + "</span>" +
          '<button type="button" class="botao-icone" data-nfv-pag="1" aria-label="Página seguinte"' + (filtro.pagina >= paginas ? " disabled" : "") + ">" + ic("chevron_right", 18) + "</button></div>" : "") +
      "</section>";
  }
  /* A linha da tabela de Emitidas, no molde da de Recebidas (js/93): as mesmas
     colunas e situacao/ambiente; o clique abre a nota embaixo e o "..." traz
     as acoes. */
  function linhaTabela(x) {
    const cliente = x.tomador_nome || (x.rascunho && x.rascunho.tomador && x.rascunho.tomador.nome) || "sem cliente";
    const comp = x.competencia || (x.rascunho && x.rascunho.competencia) || "";
    const aberta = String(nfv.aberta) === String(x.id);
    const estado = x.estado === "autorizada" ? "emitida" : x.estado;
    return '<tr class="nfv-nota' + (aberta ? " aberta" : "") + '" role="button" tabindex="0" data-nfv-nota="' + esc(x.id) + '" data-estado="' + esc(x.estado || "") + '">' +
      "<td>" + esc(competenciaPorExtenso(comp)) + '</td><td class="nf-num">' + esc(x.numero_nfse || "—") + "</td>" +
      '<td class="nfv-tomador">' + esc(cliente) + '</td><td class="nf-valor">' + esc(x.valor || "") + "</td>" +
      '<td><span class="nf-estado' + nfClasseEstado(estado) + '">' + esc(x.estado_rotulo || x.estado || "") + "</span></td>" +
      "<td>" + nfAmbiente(x.ambiente) + "</td>" +
      '<td class="nf-acoes"><button class="lc-mais" data-nfv-menu="1" title="Mais" aria-label="Mais">' + ic("more_horiz", 17) + "</button></td></tr>" +
      (aberta ? '<tr class="nfv-det-linha"><td colspan="7">' + detalheDaNota(x, cliente, comp) + "</td></tr>" : "");
  }
  window.nfvVerTodas = () => { if (typeof mostrarNotasFiscais === "function") mostrarNotasFiscais("emitidas"); };
  window.nfvFiltro = filtro;

  function abaEmitir(n) {
    const clientes = n.clientes || [];
    const t = nfv.tomador;
    const lista = clientes.length ? clientes.map((x) => '<option value="' + esc(x.id) + '"' + (String(t.cadastro_id) === String(x.id) ? " selected" : "") + ">" + esc(x.nome) + "</option>").join("") : "";
    return cartaoCfg("Cliente", "",
      '<div class="cfg-campos"><div class="ag-campo"><label>Cliente (do Cadastro)</label><select data-nfv-cliente="1"><option value="">preencher à mão</option>' + lista + "</select></div></div>") +
      cartaoCfg("Tomador", "", '<div class="cfg-campos nfv-grade">' + campo("nome", "Nome ou razão social", t.nome) + campo("documento", "CPF ou CNPJ", t.documento) +
        campo("email", "E-mail", t.email) + campo("telefone", "Telefone", t.telefone) + campo("inscricao_municipal", "Inscrição municipal (se houver)", t.inscricao_municipal) + "</div>") +
      cartaoCfg("Endereço", "", '<div class="cfg-campos nfv-grade">' + campo("cep", "CEP", t.cep) + campo("logradouro", "Rua", t.logradouro) +
        campo("numero", "Número", t.numero) + campo("complemento", "Complemento", t.complemento) + campo("bairro", "Bairro", t.bairro) + campo("municipio", "Município", t.municipio, "digite o nome") + "</div>") +
      cartaoCfg("Serviço", "", '<div class="cfg-campos nfv-grade">' + campo("descricao", "Descrição", t.descricao, "Honorários advocatícios · outubro", true) +
        campo("valor", "Valor (R$)", t.valor, "0,00") + campo("competencia", "Competência", t.competencia, "2026-10") + "</div>" +
        '<div class="cfg-botoes"><button class="primario com-icone" data-nfv-emitir="1">' + ic("receipt_long", 16) + "Preparar a nota</button></div>" +
        '<p class="cfg-explica">A nota vai para Aprovações. Só sai depois do seu sim.</p>');
  }

  function abaClientes(n) {
    const todos = n.clientes || [];
    const falta = (x) => (x.faltas || []).length;
    const q = nfv.busca.toLowerCase();
    const lista = todos.filter((x) => (nfv.filtro === "todos" || (nfv.filtro === "faltando" ? falta(x) : !falta(x))) &&
      (!q || [x.nome, x.documento, x.email].join(" ").toLowerCase().includes(q)));
    const seg = (id, rot) => { const classe = nfv.filtro === id ? "ativa" : ""; return '<button type="button" class="' + classe + '" data-nfv-filtro="' + id + '">' + rot + "</button>"; };
    const linhas = lista.length ? lista.map((x) => '<div class="nfv-linha nfv-cli">' +
      '<span class="duas-linhas"><b>' + esc(x.nome || "—") + '</b><small class="mono">' + esc(x.email || "") + "</small></span>" +
      '<span class="mono">' + esc(x.documento || "—") + "</span>" +
      '<span class="' + (falta(x) ? "nfv-falta" : "nfv-ok") + '">' + esc(falta(x) ? "falta " + x.faltas.join(", ") : "completo") + "</span>" +
      '<button class="com-icone" data-nfv-cadastro="' + esc(x.id) + '">' + ic("edit", 16) + "Editar</button></div>").join("")
      : '<p class="nfv-vazio">' + (todos.length ? "Nenhum cliente neste filtro." : "Nenhum cliente no Cadastro ainda.") + "</p>";
    return '<p class="cfg-explica">Os clientes vêm do Cadastro. O que falta para a nota aparece aqui; editar abre a ficha.</p>' +
      '<div class="nfv-filtros"><div class="visoes">' + seg("todos", "Todos") + seg("faltando", "Com dados faltando") + seg("completos", "Completos") + "</div>" +
      '<label class="nfv-busca">' + ic("search", 16) + '<input type="search" data-nfv-busca="1" placeholder="nome, CPF/CNPJ ou e-mail" value="' + esc(nfv.busca) + '"></label></div>' +
      cartaoCfg("Clientes", metaCfg(todos.length === 1 ? "1 cliente" : todos.length + " clientes"),
        '<div class="nfv-tabela"><div class="nfv-linha nfv-cli nfv-cab"><span>Cliente</span><span>CPF/CNPJ</span><span>Dados fiscais</span><span></span></div>' + linhas + "</div>");
  }

  function abaParametros(caixa) {
    const prestador = caixa.querySelector("#nfse-passo-2");
    const det = caixa.querySelector("details.nfse-depois");
    const pegar = (nome) => { const c = det && det.querySelector('[data-cartao="' + nome + '"]'); return c ? c.outerHTML : ""; };
    // O prestador nao aparece (vem de Dados e informacoes); os campos dele
    // ficam escondidos para o "Gravar" dos impostos mandar o prestador inteiro.
    const ocultos = prestador ? [...prestador.querySelectorAll("input[data-nfse-campo]")].map((i) => { i.type = "hidden"; return i.outerHTML; }).join("") : "";
    return '<div hidden>' + ocultos + "</div>" +
      comoCartao(caixa.querySelector("#nfse-passo-3"), "Tributação e serviço", "o contador confere") +
      comoCartao(caixa.querySelector("#nfse-passo-4"), "Teste", "ambiente de testes") +
      comoCartao(caixa.querySelector("#nfse-passo-5"), "Produção", "notas com valor fiscal") +
      pegar("notas-do-mes-e-contador") + pegar("honorarios-recorrentes") + pegar("tabelas-oficiais").replace(/<div class="word-acoes"><input type="file" id="nfse-planilha"[^>]*><button data-nfse-acao="planilha">Importar planilha<\/button><\/div>/,
        zonaArquivo("nfse-planilha", "A planilha .xlsx do Portal da NFS-e", ".xlsx")) + pegar("historico-da-configuracao");
  }

  const antes = secaoNfse;
  secaoNfse = function () {   // eslint-disable-line no-func-assign
    const n = cfg.nfse;
    if (!n) return antes.apply(this, arguments);
    const caixa = document.createElement("div");
    caixa.innerHTML = antes.apply(this, arguments);
    const pr = n.producao || {};
    /* Configuracoes fica com o que e ajuste: certificado, chaves, resumo e os
       parametros. As notas (lista, emitir, recebidas) moram em Escritorio ›
       Notas fiscais (js/93, redesenhada abaixo). */
    const barra = '<div class="nfv-barra"><button type="button" class="com-icone" data-nfv-ir-notas="1">' + ic("receipt_long", 16) + "Ver as notas fiscais</button>" +
      '<span class="cresce"></span><button class="com-icone" data-nfse-acao="municipio">' + ic("lan", 16) + "Testar comunicação</button></div>";
    const corpo = abaNotas(n) + abaParametros(caixa);
    // O ambiente vai no subtitulo da pagina, depois da frase da secao.
    const amb = pr.liberada ? "Em produção: as notas têm valor fiscal." : "Em ambiente de testes: as notas ainda não têm valor fiscal.";
    const abertura = aberturaCfg().replace(/(<p class="sv-resumo-corpo">)([\s\S]*?)(<\/p>)/, (m, i, t, f) => i + t + ' <span class="nfv-amb-sub' + (pr.liberada ? " prod" : "") + '">' + esc(amb) + "</span>" + f);
    return abertura + '<div class="nfv">' + barra + corpo + "</div>";
  };

  const redesenhar = () => { if (document.getElementById("nf-tela") && window.nfvDesenharEscritorio) nfvDesenharEscritorio(); else if (typeof desenharConfig === "function") desenharConfig(); };
  window.nfvNotas = () => nfv.notas;

  /* ESCRITORIO › NOTAS FISCAIS: Emitidas (a lista com filtros e paginas),
     Emitir NFS-e, Recebidas (a de js/93) e Clientes, que leva a Cadastros. */
  if (typeof mostrarNotasFiscais === "function") {
    try { const a = localStorage.getItem("paulus.nf.aba"); if (["emitidas", "emitir", "recebidas"].includes(a)) nf.aba = a; } catch (e) { /* */ }
    const SAI = '<svg class="nfv-sai" width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7 7 3M3.5 3H7v3.5"/></svg>';
    const carregarNf = nfCarregarNotas;
    nfCarregarNotas = async function () {   // eslint-disable-line no-func-assign
      if (nf.aba === "recebidas") return carregarNf.apply(this, arguments);
      if (typeof cfg !== "undefined" && !cfg.nfse && typeof carregarNfse === "function") await carregarNfse();
      try { const r = await fetch("/api/nfse/notas"); nfv.notas = r.ok ? ((await r.json()).notas || []) : []; } catch (e) { nfv.notas = []; }
    };
    cabecalhoNotas = function () {   // eslint-disable-line no-func-assign
      const pr = ((typeof cfg !== "undefined" && cfg.nfse) || {}).producao || {};
      $("conversa-meta").innerHTML = nf.aba === "recebidas" ? "As NFS-e que o Paulus emitiu para o escritório pela assinatura"
        : 'As NFS-e que o escritório emite para os clientes · <span class="nfv-amb-sub' + (pr.liberada ? " prod" : "") + '">' + (pr.liberada ? "em produção" : "em ambiente de testes, sem valor fiscal") + "</span>";
      const aba = (v, r) => '<button class="' + (v === nf.aba ? "ativa" : "") + '" data-nf-aba="' + v + '" role="tab" aria-selected="' + (v === nf.aba) + '"><span>' + r + "</span>" + (v === "clientes" ? SAI : "") + "</button>";
      $("nav-tela").innerHTML = '<div class="visoes nf-abas" role="tablist">' + aba(nf.aba === "emitir" ? "emitir" : "emitidas", "Emitidas") + aba("recebidas", "Recebidas") + aba("clientes", "Clientes") + "</div>";
      $("acoes-tela").innerHTML = nf.aba === "recebidas" ? "" : '<button class="com-icone" data-nfv-testar="1">' + ic("lan", 16) + "Testar comunicação</button>" +
        (nf.aba === "emitidas" ? '<button class="com-icone primario" data-nf-ir-emitir="1">' + ic("add", 16) + "Emitir nota</button>" : "");
      document.querySelectorAll("[data-nf-aba]").forEach((b) => {
        b.onclick = async () => {
          if (b.dataset.nfAba === "clientes") { if (typeof mostrarCadastros === "function") mostrarCadastros("clientes"); return; }
          nf.aba = b.dataset.nfAba === "emitir" ? "emitidas" : b.dataset.nfAba; nfv.aberta = "";
          try { localStorage.setItem("paulus.nf.aba", nf.aba); } catch (e) { /* */ }
          cabecalhoNotas(); cascaNotas('<p class="nota">lendo…</p>');
          await nfCarregarNotas(); nfDesenharNotas();
        };
      });
      const em = document.querySelector("[data-nf-ir-emitir]");
      if (em) em.onclick = () => { nf.aba = "emitir"; redesenhar(); };
    };
    window.nfvDesenharEscritorio = () => {
      if (!$("nf-tela")) return;
      cabecalhoNotas();
      if (nf.aba === "recebidas") { cascaNotas(blocoRecebidas()); ligarNotas(); return; }
      const n = (typeof cfg !== "undefined" && cfg.nfse) || {};
      cascaNotas('<div class="nfv">' + (nf.aba === "emitir" ? abaEmitir(n) : telaTodas()) + "</div>");
      ligarNotas();
      if (typeof melhorarSelect === "function") document.querySelectorAll("#nf-tela .nfv select").forEach((s) => { if (!s.dataset.melhorado) melhorarSelect(s); });
      if (typeof melhorarData === "function") document.querySelectorAll('#nf-tela .nfv input[type="date"]').forEach((x) => { if (!x.dataset.melhorado) melhorarData(x); });
    };
    nfDesenharNotas = window.nfvDesenharEscritorio;   // eslint-disable-line no-func-assign
  }
  /* Abrir e fechar a nota na lista com movimento: a altura vai de 0 ao
     natural (e volta), com o conteudo aparecendo junto. */
  const anima = () => typeof animacoesLigadas !== "function" || animacoesLigadas();
  const DUR = 220, CURVA = "cubic-bezier(.2, .7, .2, 1)";
  const recolher = (el) => new Promise((ok) => {
    if (!el || !anima()) { ok(); return; }
    const h = el.offsetHeight;
    const an = el.animate([{ height: h + "px", opacity: 1 }, { height: "0px", opacity: 0, paddingTop: "0px", paddingBottom: "0px" }], { duration: DUR - 40, easing: CURVA });
    el.style.overflow = "hidden";
    an.onfinish = ok;
  });
  const expandir = (el) => {
    if (!el || !anima()) return;
    const h = el.offsetHeight;
    el.style.overflow = "hidden";
    const an = el.animate([{ height: "0px", opacity: 0, paddingTop: "0px", paddingBottom: "0px" }, { height: h + "px", opacity: 1 }], { duration: DUR, easing: CURVA });
    an.onfinish = () => { el.style.overflow = ""; };
  };
  window.nfvAlternar = async (id) => {
    const aberto = document.querySelector(".nfv-detalhe");
    const fechar = String(nfv.aberta) === String(id);
    await recolher(aberto);
    nfv.aberta = fechar ? "" : id;
    redesenhar();
    if (!fechar) expandir(document.querySelector('[data-nfv-nota-det="' + CSS.escape(String(id)) + '"]'));
  };
  window.nfvAbrirEmitir = (t) => { nfv.tomador = t; if (document.getElementById("nf-tela")) { nf.aba = "emitir"; redesenhar(); } else if (typeof mostrarNotasFiscais === "function") mostrarNotasFiscais("emitir"); };
  document.addEventListener("click", async (e) => {
    if (!document.getElementById("nf-tela") && (typeof cfg === "undefined" || cfg.secao !== "nfse")) return;
    if (e.target.closest("[data-nfv-ir-notas]")) { if (typeof mostrarNotasFiscais === "function") mostrarNotasFiscais("emitidas"); return; }
    if (e.target.closest("[data-nfv-testar]")) { if (typeof acaoNfse === "function") acaoNfse("municipio"); return; }
    const aba = e.target.closest("[data-nfv-aba]");
    // Clientes e a tela de Cadastros (a mesma lista e a mesma ficha), nao uma copia.
    if (aba) { nfv.aba = aba.dataset.nfvAba; try { localStorage.setItem("paulus.nfse.aba", nfv.aba); } catch (x) { /* */ } redesenhar(); return; }
    if (e.target.closest("[data-nfv-todas]")) { nfv.aba = "todas"; nfv.aberta = ""; redesenhar(); const rb = document.querySelector("[data-rola-borda]"); if (rb) rb.scrollTop = 0; return; }
    if (e.target.closest("[data-nfv-voltar]")) { nfv.aba = "notas"; nfv.aberta = ""; redesenhar(); return; }
    const cal = e.target.closest("[data-nfv-cal]");
    if (cal) { e.stopPropagation(); setTimeout(() => nfvCalendario(cal), 0); return; }
    const pg = e.target.closest("[data-nfv-pag]");
    if (pg && !pg.disabled) { nfvFiltro.pagina += Number(pg.dataset.nfvPag); redesenhar(); const rb = document.querySelector("[data-rola-borda]"); if (rb) rb.scrollTop = 0; return; }
    const f = e.target.closest("[data-nfv-filtro]");
    if (f) { nfv.filtro = f.dataset.nfvFiltro; redesenhar(); return; }
    const pf = e.target.closest("[data-nfv-pref]");
    if (pf) { const on = !pf.classList.contains("on"); pf.classList.toggle("on", on); pf.setAttribute("aria-checked", String(on)); try { localStorage.setItem("paulus.nfse." + pf.dataset.nfvPref, on ? "1" : "0"); } catch (x) { /* */ } return; }
    const cad = e.target.closest("[data-nfv-cadastro]");
    if (cad) { if (typeof abrirDestino === "function") abrirDestino("cadastros"); return; }
    if (e.target.closest("[data-nfv-emitir]")) {
      document.querySelectorAll("[data-nfv-campo]").forEach((el) => { nfv.tomador[el.dataset.nfvCampo] = el.value.trim(); });
      if (!nfv.tomador.nome || !nfv.tomador.valor) { avisoCert("falta o nome do cliente e o valor", { tom: "erro" }); return; }
      if (typeof novaNotaFiscal === "function") { await novaNotaFiscal({ tomador: nfv.tomador }, "manual"); nfv.tomador = {}; redesenhar(); }
    }
  });
  document.addEventListener("change", (e) => {
    if (e.target.id === "nfse-pfx") { const s = document.querySelector("[data-nfv-arquivo-nome]"); if (s) s.textContent = (e.target.files[0] || {}).name || "Escolher o .pfx"; }
    if (e.target.matches && e.target.matches("[data-nfv-filtro-sel]")) {
      const k = e.target.dataset.nfvFiltroSel;
      if (k === "periodo") { if (e.target.value !== "outro") nfvAplicarPeriodo(e.target.value); else nfvFiltro.periodo = "outro"; }
      else { nfvFiltro[k] = e.target.value; nfvFiltro.pagina = 1; }
      redesenhar(); return;
    }
    if (e.target.matches && e.target.matches("[data-nfv-data]")) { nfvFiltro[e.target.dataset.nfvData] = e.target.value; nfvFiltro.periodo = "outro"; nfvFiltro.pagina = 1; redesenhar(); return; }
    if (e.target.matches && e.target.matches("[data-nfv-por-pagina]")) { nfvFiltro.porPagina = Number(e.target.value); nfvFiltro.pagina = 1; redesenhar(); return; }
    if (e.target.matches && e.target.matches("[data-nfv-cliente]")) {
      const x = ((cfg.nfse || {}).clientes || []).find((c) => String(c.id) === e.target.value) || {};
      nfv.tomador = Object.assign({}, nfv.tomador, { cadastro_id: x.id || "", nome: x.nome || "", documento: x.documento || "", email: x.email || "" }, x.endereco || {});
      redesenhar();
    }
  });
  document.addEventListener("input", (e) => {
    if (e.target.matches && e.target.matches("[data-nfv-termo]")) {
      nfvFiltro.termo = e.target.value; nfvFiltro.pagina = 1;
      const pos = e.target.selectionStart;
      redesenhar();
      const b = document.querySelector("[data-nfv-termo]"); if (b) { b.focus(); b.setSelectionRange(pos, pos); }
      return;
    }
    if (e.target.matches && e.target.matches("[data-nfv-busca]")) {
      nfv.busca = e.target.value;
      const pos = e.target.selectionStart;
      redesenhar();
      const b = document.querySelector("[data-nfv-busca]"); if (b) { b.focus(); b.setSelectionRange(pos, pos); }
    }
  });

  // A lista de escolha do sistema nos selects da secao (melhorarSelect, js/16).
  const ligarAntes = ligarConfig;
  ligarConfig = function () {   // eslint-disable-line no-func-assign
    ligarAntes.apply(this, arguments);
    if (cfg.secao === "nfse" && typeof melhorarSelect === "function") document.querySelectorAll("#cfg-tela .nfv select").forEach((s) => { if (!s.dataset.melhorado) melhorarSelect(s); });
  };

  const sec = CFG_SECOES.find((s) => s[0] === "nfse");
  if (sec) sec[2] = "A NFS-e do escritório pelo Padrão Nacional, com o certificado A1. Cada nota passa por Aprovações antes de sair.";
})();

/* O RELATORIO DO MES (abrirRelatorioNfse, js/91): os totais com nome de gente
   numa ficha de duas colunas, sem tabela com rolagem dentro do dialogo. */
(function () {
  if (typeof htmlDoRelatorioNfse !== "function") return;
  const NOMES = { v_serv: "Serviços", v_iss: "ISS", v_irrf: "IRRF", v_csll_pcc: "CSLL, PIS e Cofins", v_cp: "INSS",
    v_total_ret: "Total retido", v_ibs: "IBS", v_cbs: "CBS", v_liq: "Líquido" };
  htmlDoRelatorioNfse = function (d) {   // eslint-disable-line no-func-assign
    const r = d.relatorio || {};
    const t = r.totais || {};
    const c = r.contagem || {};
    const kv = (rot, val, forte) => '<div class="nfr-kv' + (forte ? " forte" : "") + '"><span>' + esc(rot) + "</span><b>" + esc(val) + "</b></div>";
    const totais = Object.keys(NOMES).map((k) => kv(NOMES[k], centavosTexto(t[k] || 0), k === "v_liq" || k === "v_serv")).join("");
    const achados = (d.achados || []).map((a) => "<li><b>" + esc(a.titulo) + "</b>" + (a.detalhe ? " · " + esc(a.detalhe) : "") + "</li>").join("");
    const notas = (r.linhas || []).map((l) => '<div class="nfr-nota"><span class="mono">' + esc(l.numero) + "</span><b>" + esc(l.tomador) + '</b><span class="mono">' +
      esc(centavosTexto(l.v_serv)) + '</span><button type="button" class="sv-ligacao" data-nfse-abrir="' + l.id + '">Abrir</button></div>').join("");
    return '<div class="nfr">' +
      '<div class="nfr-contagem"><span><b>' + (c.emitida || 0) + "</b> emitidas</span><span><b>" + (c.cancelada || 0) + "</b> canceladas</span><span><b>" +
      (c.substituida || 0) + "</b> substituídas</span></div>" +
      '<div class="nfr-grade">' + totais + "</div>" +
      '<div class="nfr-recebido">' + kv("Recebido no mês", centavosTexto(r.recebido || 0), true) + kv("Diferença (recebido − faturado)", centavosTexto(r.diferenca || 0)) + "</div>" +
      (achados ? '<div class="nfr-avisos"><b>Para conferir</b><ul>' + achados + "</ul></div>" : '<p class="nfr-ok">' + ic("check_circle", 16) + "A conferência não achou nada para olhar neste mês.</p>") +
      (notas ? '<div class="nfr-notas">' + notas + "</div>" : '<p class="cfg-explica">Nenhuma nota com competência neste mês.</p>') + "</div>";
  };
})();

/* ARQUIVOS DA NOTA FISCAL (pedido de 11/10/2026): a zona de arrastar fica no
   proprio cartao; "procurar" abre o navegador de pastas do Paulus (o mesmo
   desenho do Anexar › Meu computador, /api/pastas?arquivos=1), filtrado pela
   extensao. O arquivo escolhido la vem do servidor por
   /api/arquivos/bruto?caminho= e entra no campo como se tivesse sido solto. */
const procurarArq = { caminho: "", aceita: [], escolhido: null };
function procurarArquivoPaulus(o) {
  const op = o || {};
  procurarArq.caminho = ""; procurarArq.escolhido = null;
  procurarArq.aceita = String(op.aceita || "").split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);
  const aberto = dialogo({
    titulo: op.titulo || "Procurar arquivo", contexto: op.contexto || "Este computador", classe: "dialogo-anexar dialogo-pasta", confirmar: op.confirmar || "Usar este arquivo",
    html: '<div class="anx"><div class="anx-migalhas" id="pa-migalhas"></div><div class="anx-lista" id="pa-lista"><p class="anx-vazio">abrindo…</p></div>' +
      '<div class="anx-rodape"><span class="ep-onde" id="pa-onde">' + esc(procurarArq.aceita.length ? "mostrando só " + procurarArq.aceita.join(", ") : "") + "</span></div></div>",
    aoConfirmar: () => { if (procurarArq.escolhido) dialogoAberto.fechar({ ok: true, arquivo: procurarArq.escolhido }); },
  });
  const ok = document.querySelector('#veu-dialogo [data-dialogo="confirmar"]');
  if (ok) ok.disabled = true;
  irProcurarArq("");
  return aberto.then((r) => (r && r.ok ? r.arquivo : null));
}
async function irProcurarArq(caminho) {
  procurarArq.caminho = caminho;
  const lista = document.getElementById("pa-lista"), mig = document.getElementById("pa-migalhas");
  if (!lista) return;
  let d;
  try { d = await (await fetch("/api/pastas?arquivos=1&caminho=" + encodeURIComponent(caminho))).json(); }
  catch (err) { d = { erro: "não consegui abrir: " + err }; }
  mig.innerHTML = '<button type="button" data-pa-ir="">Este computador</button>' +
    (d.migalhas || []).map((m) => '<span class="lc-sep">›</span><button type="button" data-pa-ir="' + esc(m.caminho) + '">' + esc(m.nome) + "</button>").join("");
  const pasta = (p, icone) => '<div class="anx-linha anx-pasta" data-pa-ir="' + esc(p.caminho) + '">' + ic(icone, 17) +
    '<span class="duas-linhas"><b class="corta">' + esc(p.nome) + "</b></span>" + ic("chevron_right", 16) + "</div>";
  const serve = (n) => !procurarArq.aceita.length || procurarArq.aceita.some((x) => n.toLowerCase().endsWith(x));
  let html = "";
  if ((d.atalhos || []).length) html += '<div class="nav-grupo">Começar por</div>' + d.atalhos.map((a) => pasta(a, "folder")).join("");
  if ((d.unidades || []).length) html += '<div class="nav-grupo">Unidades</div>' + d.unidades.map((u) => pasta(u, "desktop_windows")).join("");
  html += (d.pastas || []).map((p) => pasta(p, "folder")).join("");
  html += (d.arquivos || []).filter((a) => serve(a.nome)).map((a) => '<div class="anx-linha" data-pa-arq="' + esc(a.caminho) + '" data-nome="' + esc(a.nome) + '">' +
    ic("description", 17) + '<span class="duas-linhas"><b class="corta">' + esc(a.nome) + "</b></span>" +
    '<span class="anx-quando">' + esc(typeof dataCurta === "function" ? dataCurta(a.modificado) : "") + "</span></div>").join("");
  if (d.erro) html += '<p class="anx-vazio">' + esc(d.erro) + "</p>";
  else if (!html) html = '<p class="anx-vazio">Nenhum arquivo ' + esc(procurarArq.aceita.join(" ou ")) + " nesta pasta.</p>";
  lista.innerHTML = html;
}
document.addEventListener("click", (e) => {
  const ir = e.target.closest("[data-pa-ir]");
  if (ir && document.getElementById("pa-lista")) { irProcurarArq(ir.dataset.paIr); return; }
  const arq = e.target.closest("[data-pa-arq]");
  if (arq) {
    document.querySelectorAll("[data-pa-arq].escolhida").forEach((x) => x.classList.remove("escolhida"));
    arq.classList.add("escolhida");
    procurarArq.escolhido = { caminho: arq.dataset.paArq, nome: arq.dataset.nome };
    const ok = document.querySelector('#veu-dialogo [data-dialogo="confirmar"]'); if (ok) ok.disabled = false;
    const onde = document.getElementById("pa-onde"); if (onde) onde.textContent = arq.dataset.nome;
  }
});
document.addEventListener("dblclick", (e) => { if (e.target.closest("[data-pa-arq]") && dialogoAberto && procurarArq.escolhido) dialogoAberto.fechar({ ok: true, arquivo: procurarArq.escolhido }); });

/* A zona de arrastar, no cartao. */
function zonaArquivo(id, rotulo, aceita) {
  return '<div class="arq-zona" role="button" tabindex="0" data-arq-zona="' + id + '" data-aceita="' + esc(aceita) + '">' + ic("upload", 22) +
    '<span class="duas-linhas"><b data-arq-nome>' + esc(rotulo) + "</b><small>arraste aqui ou " +
    '<span class="arq-link">procure no computador</span></small></span>' +
    '<input type="file" id="' + id + '" hidden accept="' + esc(aceita) + '"></div>';
}
(function () {
  const porNoInput = (id, f) => { const el = document.getElementById(id); if (!el) return; const dt = new DataTransfer(); dt.items.add(f); el.files = dt.files; el.dispatchEvent(new Event("change", { bubbles: true })); };
  const marcar = (zona, f) => {
    const exts = String(zona.dataset.aceita || "").split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);
    if (exts.length && !exts.some((x) => f.name.toLowerCase().endsWith(x))) { avisoCert("esperava um arquivo " + exts.join(" ou "), { tom: "erro" }); return false; }
    zona.classList.add("tem"); zona.querySelector("[data-arq-nome]").textContent = f.name;
    porNoInput(zona.dataset.arqZona, f);
    return true;
  };
  document.addEventListener("dragover", (e) => { const z = e.target.closest && e.target.closest("[data-arq-zona]"); if (z) { e.preventDefault(); z.classList.add("sobre"); } });
  document.addEventListener("dragleave", (e) => { const z = e.target.closest && e.target.closest("[data-arq-zona]"); if (z) z.classList.remove("sobre"); });
  document.addEventListener("drop", (e) => { const z = e.target.closest && e.target.closest("[data-arq-zona]"); if (!z) return; e.preventDefault(); z.classList.remove("sobre"); const f = e.dataTransfer.files[0]; if (f && marcar(z, f) && z.dataset.arqZona === "nfse-planilha") acaoNfse("planilha"); });
  document.addEventListener("keydown", (e) => { const z = e.target.closest && e.target.closest("[data-arq-zona]"); if (z && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); z.click(); } });
  document.addEventListener("click", async (e) => {
    // A zona inteira abre o procurar (nao so o link).
    const zona = e.target.closest("[data-arq-zona]");
    if (!zona || e.target.closest("[data-nfv-windows]")) return;
    e.preventDefault(); e.stopPropagation();
    const id = zona.dataset.arqZona;
    const a = await procurarArquivoPaulus({ titulo: id === "nfse-pfx" ? "Certificado digital A1" : "Importar planilha", contexto: "Nota fiscal", aceita: zona.dataset.aceita,
      confirmar: id === "nfse-pfx" ? "Usar este certificado" : "Importar" });
    if (!a) return;
    try {
      const r = await fetch("/api/arquivos/bruto?caminho=" + encodeURIComponent(a.caminho));
      if (!r.ok) throw new Error("não consegui ler " + a.nome);
      const f = new File([await r.blob()], a.nome);
      if (marcar(zona, f)) { if (id === "nfse-planilha") acaoNfse("planilha"); else { const s = document.getElementById("nfse-pfx-senha"); if (s) s.focus(); } }
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
  }, true);
})();

/* O certificado da NFS-e no desenho da Assinatura › Certificado digital
   (js/15): arrastar, escolher no computador (o navegador do Paulus) ou usar
   um ja instalado no Windows - a chave continua no Windows. */
function zonaCertificado(instalado) {
  return '<div class="arq-zona as-solta nfv-solta" role="button" tabindex="0" data-arq-zona="nfse-pfx" data-aceita=".pfx,.p12">' +
    "<span data-arq-nome>" + (instalado ? "Arraste outro certificado aqui para trocar" : "Arraste o arquivo do certificado aqui") + "</span>" +
    "<small>.pfx ou .p12 · até 8 MB</small>" +
    '<span class="as-solta-acoes"><button type="button" class="primario com-icone">' + ic("folder_open", 16) + "Escolher no computador</button>" +
    '<button type="button" class="com-icone" data-nfv-windows="1">' + ic("desktop_windows", 16) + "Usar um já instalado no Windows</button></span>" +
    '<input type="file" id="nfse-pfx" hidden accept=".pfx,.p12"></div>';
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-nfv-windows]");
  if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation();
  if (typeof abrirCertificadosDoWindows !== "function") return;
  abrirCertificadosDoWindows({ contexto: "Nota fiscal › Certificado", rota: "/api/nfse/certificado/windows",
    aoUsar: (d) => { avisoCert((d && d.aviso) || "certificado do Windows pronto para as notas", { tom: "ok" }); if (typeof mostrarConfig === "function") mostrarConfig("nfse"); } });
}, true);

/* O menu da nota (menu-conversa, js/01): o que cabe em cada situacao. Os
   botoes data-nota-* reaproveitam as acoes de js/91-nfse-nota.js. */
/* A nota aberta na propria lista (sem pop-up): os dados e as acoes. */
function botoesDaNota(id, estado) {
  const b = (attrs, icone, rot, perigo) => '<button type="button" class="com-icone' + (perigo ? " perigo" : "") + '" ' + attrs + ">" + ic(icone, 16) + rot + "</button>";
  if (estado === "rascunho" || estado === "rejeitada")
    return b('data-nfv-a="editar"', "edit", "Editar") + b('data-nfv-a="enviar"', "send", "Enviar para aprovação") + b('data-nota-descartar="' + id + '"', "delete", "Excluir", true);
  if (estado === "autorizada" || estado === "emitida")
    return b('data-nfv-a="imprimir"', "print", "Imprimir") + b('data-nota-danfse="' + id + '"', "picture_as_pdf", "Baixar PDF") + b('data-nfv-a="xml"', "code", "Baixar XML") +
      b('data-nfv-a="email"', "mail", "Enviar ao cliente") + b('data-nota-substituir="' + id + '"', "swap_horiz", "Substituir") + b('data-nota-cancelar="' + id + '"', "block", "Cancelar a nota", true);
  return b('data-nota-danfse="' + id + '"', "picture_as_pdf", "Baixar PDF") + b('data-nfv-a="xml"', "code", "Baixar XML");
}
function detalheDaNota(x, cliente, comp) {
  const kv = (r, v) => v ? '<div class="nfv-kv"><span>' + esc(r) + "</span><b>" + esc(v) + "</b></div>" : "";
  return '<div class="nfv-detalhe" data-nfv-nota-det="' + esc(x.id) + '"><div class="nfv-kvs">' +
    kv("Cliente", cliente) + kv("CPF/CNPJ", x.tomador_documento) + kv("Serviço", x.servico) + kv("Competência", comp) + kv("Valor", x.valor) +
    kv("NFS-e", x.numero_nfse ? x.numero_nfse + (x.serie ? " · série " + x.serie : "") : "") + kv("Chave de acesso", x.chave) + "</div>" +
    '<div class="cfg-botoes">' + botoesDaNota(x.id, x.estado) + "</div></div>";
}
function editarNotaNaAba(id) {
  const x = (nfvNotas() || []).find((n) => String(n.id) === String(id)) || {};
  const t = (x.rascunho && x.rascunho.tomador) || {};
  nfvAbrirEmitir({ nome: x.tomador_nome || t.nome || "", documento: x.tomador_documento || t.documento || "", descricao: x.servico || "",
    valor: String(x.valor || "").replace(/^R\$\s*/, ""), competencia: x.competencia || (x.rascunho && x.rascunho.competencia) || "", editando: id });
}
function menuDaNota(linha) {
  if (typeof fecharMenu === "function") fecharMenu();
  const id = linha.dataset.nfvNota, estado = linha.dataset.estado;
  const b = (attrs, icone, rot, perigo) => '<button type="button" ' + attrs + (perigo ? ' class="perigo"' : "") + ">" + ic(icone, 16) + rot + "</button>";
  const risco = '<div class="menu-risco"></div>';
  let html;
  if (estado === "rascunho" || estado === "rejeitada") {
    html = b('data-nfv-a="editar"', "edit", "Editar") + b('data-nfv-a="enviar"', "send", "Enviar para aprovação") + risco +
      b('data-nota-descartar="' + id + '"', "delete", "Excluir", true);
  } else if (estado === "autorizada" || estado === "emitida") {
    html = b('data-nfv-a="imprimir"', "print", "Imprimir") +
      b('data-nota-danfse="' + id + '"', "picture_as_pdf", "Baixar PDF") + b('data-nfv-a="xml"', "code", "Baixar XML") +
      b('data-nfv-a="email"', "mail", "Enviar ao cliente") + risco +
      b('data-nota-substituir="' + id + '"', "swap_horiz", "Substituir") + b('data-nota-cancelar="' + id + '"', "block", "Cancelar a nota", true);
  } else {
    html = b('data-nota-danfse="' + id + '"', "picture_as_pdf", "Baixar PDF") + b('data-nfv-a="xml"', "code", "Baixar XML");
  }
  const menu = document.createElement("div");
  menu.className = "menu-conversa recem nfv-menu";
  menu.innerHTML = html;
  // No body, em posicao fixa: o cartao corta o que passa da borda. Abre para
  // cima quando nao cabe embaixo da linha.
  menu.style.position = "fixed"; menu.style.visibility = "hidden";
  document.body.appendChild(menu);
  const mais = linha.querySelector("[data-nfv-menu]").getBoundingClientRect();
  const h = menu.offsetHeight, w = menu.offsetWidth;
  const cabe = mais.bottom + 4 + h <= window.innerHeight - 8;
  menu.style.top = (cabe ? mais.bottom + 4 : Math.max(8, mais.top - 4 - h)) + "px";
  menu.style.left = Math.max(8, mais.right - w) + "px";
  menu.style.right = "auto";
  menu.dataset.nfvNota = linha.dataset.nfvNota;
  menu.style.visibility = "";
  setTimeout(() => menu.classList.remove("recem"), 0);
  const fechar = () => { menu.remove(); window.removeEventListener("scroll", fechar, true); };
  window.addEventListener("scroll", fechar, true);
}
document.addEventListener("click", async (e) => {
  const menuAberto = e.target.closest && (e.target.closest(".nfv-menu") || e.target.closest("[data-nfv-nota-det]"));
  const linha = e.target.closest && e.target.closest(".nfv-nota");
  if (!linha && !menuAberto) return;
  const id = (linha || menuAberto).dataset.nfvNota || menuAberto.dataset.nfvNotaDet;
  if (linha && e.target.closest("[data-nfv-menu]")) { e.stopPropagation(); menuDaNota(linha); return; }
  const a = e.target.closest("[data-nfv-a]");
  if (a) {
    const qual = a.dataset.nfvA;
    if (qual === "editar") editarNotaNaAba(id);
    else if (qual === "enviar") { const r = await fetch("/api/nfse/notas/" + id); if (r.ok) await pedirAprovacaoDaNota(await r.json()); }
    else if (qual === "imprimir") { const w = window.open("/api/nfse/notas/" + id + "/danfse", "_blank"); if (w) w.addEventListener("load", () => w.print()); }
    else if (qual === "xml") window.open("/api/nfse/notas/" + id + "/xml?baixar=1", "_blank");
    else if (qual === "email") { const r = await fetch("/api/nfse/notas/" + id + "/enviar-email", { method: "POST" }); avisoCert(r.ok ? "envio por e-mail em Aprovações" : await erroDe(r), { tom: r.ok ? "ok" : "erro" }); }
    return;
  }
  if (e.target.closest(".menu-conversa") || !linha) return;   // data-nota-* seguem para js/91
  nfvAlternar(id);
});
document.addEventListener("keydown", (e) => {
  const l = e.target.closest && e.target.closest(".nfv-nota");
  if (l && e.target === l && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); nfvAlternar(l.dataset.nfvNota); }
});

/* Clientes leva a Cadastros. Na captura: outro ouvinte das abas (.visoes)
   parava o clique antes de chegar ao de cima. */
document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest('[data-nfv-aba="clientes"]');
  if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation();
  window.__nfvCli = (window.__nfvCli || 0) + 1;
  setTimeout(() => { if (typeof mostrarCadastros === "function") mostrarCadastros("clientes"); }, 0);
}, true);
