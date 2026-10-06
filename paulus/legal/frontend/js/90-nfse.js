/* ------------------------------------------ Nota fiscal (NFS-e) — N1 */
/*
   Configurações › Nota fiscal: só na janela do escritório. Quem presta o
   serviço, o regime, o serviço padrão, as retenções (cada uma com "não sei,
   perguntar ao contador"), o IBS/CBS, o certificado A1 da nota e a
   verificação do município no Sistema Nacional (src/nfse/, src/rotas_nfse.py).

   Percentual e dinheiro vão como texto (`*_pct`, `*_reais`) e viram inteiro
   no servidor: nada de float no caminho do imposto.
*/

async function carregarNfse() {
  try {
    const [r, rec, prod, cli] = await Promise.all([fetch("/api/nfse"), fetch("/api/nfse/recorrencias"), fetch("/api/nfse/producao"),
      fetch("/api/nfse/teste/clientes")]);
    cfg.nfse = r.ok ? await r.json() : null;
    if (cfg.nfse) cfg.nfse.recorrencias = rec.ok ? (await rec.json()).recorrencias : [];
    if (cfg.nfse) cfg.nfse.producao = prod.ok ? await prod.json() : null;
    if (cfg.nfse) cfg.nfse.clientes = cli.ok ? (await cli.json()).clientes : [];
  } catch (err) { cfg.nfse = null; }
}

function pctNfse(bp) {
  const b = Number(bp || 0);
  if (!b) return "";
  return Math.floor(b / 100) + "," + String(b % 100).padStart(2, "0");
}

function reaisNfse(c) {
  const n = Number(c || 0);
  if (!n) return "";
  return Math.floor(n / 100).toLocaleString("pt-BR") + "," + String(n % 100).padStart(2, "0");
}

function campoNfse(caminho, rotulo, valor, dica, extra) {
  return '<div class="ag-campo"><label>' + esc(rotulo) + '</label><input type="text" data-nfse-campo="' + caminho + '" value="' +
    esc(valor == null ? "" : String(valor)) + '"' + (dica ? ' placeholder="' + esc(dica) + '"' : "") + (extra || "") + "></div>";
}

/* `rotulos` troca o texto oficial por um que a pessoa reconhece; sem ele, "código – texto oficial". */
function escolhaNfse(caminho, rotulo, opcoes, valor, rotulos) {
  const linhas = Object.entries(opcoes || {}).map(([k, v]) =>
    '<option value="' + esc(k) + '"' + (String(k) === String(valor) ? " selected" : "") + ">" +
    esc((rotulos && rotulos[k]) || (k === "" ? v : (k + " – " + v))) + "</option>").join("");
  return '<div class="ag-campo"><label>' + esc(rotulo) + '</label><select data-nfse-campo="' + caminho + '">' + linhas + "</select></div>";
}

function linhaNfse(rotulo, valor, tom) {
  return '<div class="word-linha"><span>' + esc(rotulo) + '</span><b class="' + (tom || "") + '">' + esc(valor) + "</b></div>";
}

/* Um passo do assistente: número, título, se está feito e o corpo. */
function passoNfse(n, titulo, feito, explica, corpo) {
  return '<section class="cfg-cartao nfse-passo' + (feito ? " feito" : "") + '" id="nfse-passo-' + n + '">' +
    '<header class="nfse-passo-cabeca"><span class="nfse-passo-num">' + (feito ? "✓" : n) + "</span><div><h3>" + esc(titulo) +
    "</h3>" + (explica ? '<p class="cfg-explica">' + explica + "</p>" : "") + "</div></header>" + corpo + "</section>";
}

function secaoNfse() {
  const n = cfg.nfse;
  if (!n) return aberturaCfg() + '<p class="cfg-explica">Não consegui ler a configuração da nota fiscal agora.</p>';
  const p = n.prestador || {};
  const d = p.dados || {};
  const o = p.opcoes || {};
  const cert = n.certificado || {};
  const c = cert.certificado || {};
  const mun = n.municipio || {};
  const pr = n.producao || { itens: [], recomendados: [] };
  const item = (id) => (pr.itens || []).find((i) => i.id === id) || {};
  const certOk = !!item("certificado").ok;
  const configOk = !!item("configuracao").ok;
  const munOk = !!item("municipio").ok;
  const testeOk = !!item("teste").ok;
  const emProducao = !!pr.liberada;

  /* O caminho: onde a pessoa está. */
  const etapas = [["Certificado", certOk], ["Escritório", configOk || (d.documento && d.municipio && munOk)], ["Impostos", configOk],
    ["Teste", testeOk], ["Produção", emProducao]];
  const caminho = '<ol class="nfse-caminho">' + etapas.map(([t, ok], i) =>
    '<li class="' + (ok ? "ok" : "") + '"><a href="#nfse-passo-' + (i + 1) + '">' + (ok ? "✓ " : (i + 1) + ". ") + esc(t) + "</a></li>").join("") + "</ol>" +
    '<p class="cfg-explica">' + (emProducao
      ? "<b>Emitindo em produção:</b> as notas valem de verdade. Cada uma passa por Aprovações antes de sair."
      : "Configure em quatro passos e faça um teste. Dando certo, o PAULUS avisa e você muda para produção. Até lá, nada vale de verdade.") + "</p>";

  /* 1. Certificado */
  const certCorpo = (cert.instalado
    ? linhaNfse("Titular", c.titular || "—") + linhaNfse("Documento", c.documento || "—") + linhaNfse("Validade", c.valido_ate ? "até " + c.valido_ate : "—", c.vencido ? "erro" : "") +
      linhaNfse("Senha", cert.senha_guardada ? "guardada nesta conta do Windows" : (cert.minutos_restantes ? "na memória por " + cert.minutos_restantes + " min" : "pedida a cada uso")) +
      (cert.avisos || []).map((a) => '<p class="cfg-explica"><b>' + esc(a) + "</b></p>").join("") +
      (cert.precisa_senha ? '<div class="ag-duas"><div class="ag-campo"><label>Senha do certificado</label><input type="password" id="nfse-senha-desbloquear"></div>' +
        '<div class="ag-campo"><label>&nbsp;</label><button data-nfse-acao="desbloquear">Usar a senha</button></div></div>' : "")
    : "") +
    (cert.instalado ? '<details class="nfse-trocar"><summary>Trocar ou tirar o certificado</summary>' : "") +
    '<div class="ag-duas"><div class="ag-campo"><label>Arquivo .pfx ou .p12</label><input type="file" id="nfse-pfx" accept=".pfx,.p12"></div>' +
    '<div class="ag-campo"><label>Senha do certificado</label><input type="password" id="nfse-pfx-senha" autocomplete="off"></div></div>' +
    '<label class="cfg-explica"><input type="checkbox" id="nfse-pfx-guardar" checked> Guardar a senha neste computador (cifrada; sem isso, ela vale 15 minutos)</label>' +
    '<div class="word-acoes"><button class="' + (cert.instalado ? "" : "primario") + '" data-nfse-acao="certificado">' + ic("upload", 16) +
    (cert.instalado ? "Trocar o certificado" : "Instalar o certificado") + "</button>" +
    (cert.instalado ? '<button data-nfse-acao="remover-certificado">Tirar o certificado</button>' : "") + "</div>" +
    (cert.instalado ? "</details>" : "");
  const passo1 = passoNfse(1, "O certificado digital do escritório", certOk,
    "O mesmo A1 (arquivo .pfx ou .p12) que o escritório usa na prefeitura: e-CNPJ da sociedade, ou e-CPF do advogado autônomo. " +
    "Dele o PAULUS já tira o CNPJ e o nome. Certificado em token (A3) não serve.", certCorpo);

  /* 2. Escritório */
  const end = d.endereco || {};
  const munFrase = mun.situacao === "conveniado" ? "✓ " + (mun.frase || "o município emite pelo nacional")
    : (mun.frase || "Depois de gravar, o PAULUS pergunta ao Sistema Nacional se o seu município emite por ele.");
  const passo2 = passoNfse(2, "Os dados do escritório", configOk || (!!d.documento && munOk), "Como aparecem na nota.",
    // O CNPJ digitado preenche nome, cidade, endereco e contato com os dados da Receita (js/39-campos.js).
    '<div class="cfg-campos" data-cnpj-grupo="1">' +
    '<div class="ag-duas">' + campoNfse("documento", "CNPJ (ou CPF do advogado autônomo)", d.documento, "só números", ' data-cnpj-busca="1"') +
    campoNfse("inscricao_municipal", "Inscrição municipal", d.inscricao_municipal, "está no alvará ou no carnê do ISS") + "</div>" +
    campoNfse("razao_social", "Nome (razão social)", d.razao_social, "como no CNPJ", marcaCnpj("razao_social")) +
    '<div class="ag-duas">' + campoNfse("municipio", "Cidade", d.municipio, "digite o nome e escolha", ' list="nfse-municipios" data-nfse-busca-municipio="1"' + marcaCnpj("codigo_municipio_ibge")) +
    '<div class="ag-campo"><label>&nbsp;</label><input type="text" readonly value="' + esc(p.municipio_nome || "") + '"></div></div>' +
    '<datalist id="nfse-municipios"></datalist>' +
    '<div class="ag-duas">' + campoNfse("endereco.cep", "CEP", end.cep, "00000000", marcaCnpj("cep")) + campoNfse("endereco.logradouro", "Rua", end.logradouro, "", marcaCnpj("logradouro")) + "</div>" +
    '<div class="ag-duas">' + campoNfse("endereco.numero", "Número", end.numero, "", marcaCnpj("numero")) + campoNfse("endereco.complemento", "Complemento", end.complemento, "", marcaCnpj("complemento")) + "</div>" +
    '<div class="ag-duas">' + campoNfse("endereco.bairro", "Bairro", end.bairro, "", marcaCnpj("bairro")) + campoNfse("telefone", "Telefone", d.telefone, "", marcaCnpj("telefone")) + "</div>" +
    campoNfse("email", "E-mail", d.email, "", marcaCnpj("email")) + "</div>" +
    '<p class="cfg-explica">' + esc(munFrase) + "</p>" +
    '<div class="word-acoes"><button class="primario" data-nfse-acao="salvar">' + ic("save", 16) + "Gravar e continuar</button>" +
    (d.municipio ? '<button data-nfse-acao="municipio">' + ic("search", 16) + "Consultar a cidade de novo</button>" : "") + "</div>");

  /* 3. Impostos: as perguntas que o escritório sabe responder; o resto em "Mais opções". */
  const s = d.servico || {};
  const nbsOpcoes = { "": "escolha a área" };
  (o.nbs_sugeridas || []).forEach((x) => { nbsOpcoes[x.codigo] = x.descricao; });
  const nbsRotulos = {};
  (o.nbs_sugeridas || []).forEach((x) => { nbsRotulos[x.codigo] = x.descricao; });
  const ib = d.ibscbs || {};
  const sug = (o.nbs_sugeridas || []).find((x) => x.codigo === s.nbs) || (o.nbs_sugeridas || [])[0];
  const cclassSug = ib.cclasstrib || (sug ? sug.cclasstrib : "");
  const cstSug = ib.cst || (cclassSug ? String(cclassSug).slice(0, 3) : "");
  const quando = o.quando_reter || {};
  const ret = d.retencoes || {};
  const linhasRet = Object.entries(o.retencoes || {}).map(([k, rot]) => {
    const r = ret[k] || {};
    return '<div class="nfse-retencao"><b>' + esc(rot) + '</b><small class="cfg-explica">' + esc((o.explica_retencao || {})[k] || "") + "</small>" +
      '<div class="ag-duas">' + escolhaNfse("retencoes." + k + ".quando", "Quando reter", quando, r.quando, quando) +
      (k === "iss" ? "" : campoNfse("retencoes." + k + ".aliquota_pct", "Alíquota (%)", pctNfse(r.aliquota_bp), "ex.: 1,5")) + "</div>" +
      (k === "iss" ? "" : campoNfse("retencoes." + k + ".minimo_reais", "Não reter abaixo de (R$)", reaisNfse(r.minimo_centavos), "vazio se não houver")) +
      "</div>";
  }).join("");
  const tt = d.total_tributos || {};
  const mais = '<details class="nfse-mais"><summary>Mais opções (para conferir com o contador)</summary>' +
    '<h4>Retenções</h4><p class="cfg-explica">Quando o cliente desconta imposto do pagamento. “Não sei — perguntar ao contador” deixa a retenção desligada, e o cartão da nota avisa.</p>' + linhasRet +
    '<h4>IBS e CBS (reforma tributária)</h4><div class="cfg-campos">' +
    '<div class="ag-toggle' + (ib.enviar ? " on" : "") + '" data-nfse-acao="ibscbs" role="switch" tabindex="0"><span class="duas-linhas"><b>Mandar o grupo IBS/CBS na nota</b>' +
    "<small>exigido desde 03/08/2026 fora do Simples; para o Simples, a partir de 2027. A Sefin calcula os valores.</small></span><i></i></div>" +
    '<div class="ag-duas">' + campoNfse("ibscbs.cst", "CST (3 dígitos)", cstSug) + campoNfse("ibscbs.cclasstrib", "cClassTrib (6 dígitos)", cclassSug) + "</div>" +
    campoNfse("ibscbs.cindop", "Indicador da operação (cIndOp)", ib.cindop || (sug ? sug.cindop : ""), "100301") +
    (sug ? '<p class="cfg-explica">Já vem preenchido com a sugestão da tabela oficial para a advocacia (“' + esc(sug.descricao_cclasstrib) + "”). Confirme com o contador.</p>" : "") + "</div>" +
    '<h4>Total aproximado de tributos (Lei 12.741)</h4><div class="cfg-campos">' +
    escolhaNfse("total_tributos.modo", "Como informar", { percentual: "percentuais federal, estadual e municipal", simples: "percentual do Simples (só ME/EPP)" }, tt.modo,
      { percentual: "Percentuais federal, estadual e municipal", simples: "Percentual do Simples (só ME/EPP)" }) +
    '<div class="ag-duas">' + campoNfse("total_tributos.federal_pct", "Federal (%)", pctNfse(tt.federal_bp)) + campoNfse("total_tributos.estadual_pct", "Estadual (%)", pctNfse(tt.estadual_bp)) + "</div>" +
    '<div class="ag-duas">' + campoNfse("total_tributos.municipal_pct", "Municipal (%)", pctNfse(tt.municipal_bp)) + campoNfse("total_tributos.simples_pct", "Simples (%)", pctNfse(tt.simples_bp)) + "</div></div>" +
    '<h4>Outros códigos</h4><div class="cfg-campos">' +
    '<div class="ag-duas">' + campoNfse("servico.ctribnac", "Código de tributação nacional", s.ctribnac, "171401 (advocacia)") +
    campoNfse("servico.ctribmun", "Código municipal (se a cidade usar)", s.ctribmun, "3 dígitos") + "</div>" +
    '<div class="ag-duas">' + campoNfse("pis_cofins.cst", "CST do PIS/COFINS (só com PIS/COFINS/CSLL retidos)", (d.pis_cofins || {}).cst) +
    campoNfse("regime_federal", "Regime federal (anotação)", d.regime_federal, "presumido, real…") + "</div>" +
    '<div class="ag-duas">' + campoNfse("contador.nome", "Contador (nome)", (d.contador || {}).nome) +
    campoNfse("contador.email", "E-mail do contador (para o arquivo do mês)", (d.contador || {}).email) + "</div></div></details>";
  const passo3 = passoNfse(3, "Os impostos", configOk, "Poucas perguntas. Na dúvida, pergunte ao contador; o resto já vem preenchido com o padrão da advocacia.",
    '<div class="cfg-campos">' +
    escolhaNfse("opcao_simples", "Como o escritório paga impostos?", o.opcao_simples, d.opcao_simples,
      { "1": "Lucro presumido ou lucro real", "3": "Simples Nacional (ME ou EPP)", "2": "MEI" }) +
    (String(d.opcao_simples) === "3" ? escolhaNfse("regime_apuracao_sn", "No Simples, o ISS é recolhido…", Object.assign({ "": "escolha" }, o.regime_apuracao_sn), d.regime_apuracao_sn,
      { "": "escolha", "1": "dentro do Simples (o mais comum)", "2": "fora do Simples (ISS pela regra do município)", "3": "federais e ISS fora do Simples" }) : "") +
    escolhaNfse("regime_especial", "O ISS do escritório é fixo por profissional?",
      Object.fromEntries(Object.entries(o.regime_especial || {}).filter(([k]) => ["0", "5", "6", String(d.regime_especial)].includes(k))), d.regime_especial,
      { "0": "Não — o ISS é um percentual da nota", "6": "Sim — sociedade de advogados (ISS fixo)", "5": "Sim — advogado autônomo (ISS fixo)" }) +
    escolhaNfse("servico.nbs", "Área de atuação do escritório", nbsOpcoes, s.nbs, nbsRotulos) +
    '<div class="ag-duas">' + campoNfse("servico.aliquota_iss_pct", "Alíquota do ISS da cidade (%)", pctNfse(s.aliquota_iss_bp), "ex.: 5 ou 2,5") +
    campoNfse("servico.descricao", "Texto padrão da nota", s.descricao || "Honorários advocatícios", "Honorários advocatícios") + "</div>" +
    "</div>" + mais +
    ((p.faltas || []).length ? '<p class="cfg-explica"><b>Ainda falta:</b> ' + esc(p.faltas.join("; ")) + ".</p>" : "") +
    '<div class="word-acoes"><button class="primario" data-nfse-acao="salvar">' + ic("save", 16) + "Gravar e continuar</button></div>");

  /* 4. Teste */
  const t = pr.teste || {};
  const prontoParaTestar = certOk && configOk && munOk;
  const clientes = n.clientes || [];
  const etapasTeste = (t.etapas || []).map((e) => linhaNfse((e.ok ? "✓ " : "✗ ") + e.titulo, e.detalhe || (e.ok ? "ok" : ""), e.ok ? "ok" : "erro")).join("");
  const resultado = t.em
    ? '<div class="nfse-resultado ' + (testeOk ? "ok" : "erro") + '"><p><b>' + esc(t.frase || "") + "</b></p>" + etapasTeste +
      (t.ok && !testeOk ? '<p class="cfg-explica">A configuração mudou depois deste teste: faça de novo.</p>' : "") + "</div>"
    : "";
  const passo4 = passoNfse(4, "O teste", testeOk,
    "O PAULUS emite uma nota de R$ 1,00 no ambiente de testes do governo (produção restrita, sem valor fiscal) e a cancela em seguida. " +
    "Nada é mandado ao cliente.",
    (prontoParaTestar
      ? '<div class="cfg-campos"><div class="ag-campo"><label>Em nome de qual cliente?</label><select id="nfse-teste-cliente">' +
        (clientes.length ? clientes.map((x) => '<option value="' + x.id + '">' + esc(x.nome) + "</option>").join("") : '<option value="">nenhum cliente com CPF/CNPJ no Cadastro</option>') +
        "</select></div></div>" +
        '<p class="cfg-explica">Use um cliente com endereço completo no Cadastro: a Sefin confere o CEP.</p>' +
        '<div class="word-acoes"><button class="primario" data-nfse-acao="teste"' + (clientes.length && !emProducao ? "" : " disabled") + ">" +
        ic("play_arrow", 16) + (t.em ? "Fazer o teste de novo" : "Fazer o teste") + "</button></div>"
      : '<p class="cfg-explica">Disponível depois dos passos 1 a 3' + (certOk && configOk && !munOk ? " e da confirmação de que a sua cidade emite pelo Sistema Nacional" : "") + ".</p>") +
    resultado);

  /* 5. Produção */
  const recs = (pr.recomendados || []).map((i) => linhaNfse((i.ok ? "✓ " : "· ") + i.titulo, i.detalhe, i.ok ? "ok" : "")).join("");
  const passo5 = passoNfse(5, "Produção", emProducao, "",
    (emProducao
      ? '<div class="nfse-resultado ok"><p><b>Em produção:</b> as notas novas valem de verdade. A primeira pede uma confirmação a mais.</p></div>' +
        '<div class="word-acoes"><button data-nfse-acao="voltar">Voltar para o ambiente de testes</button></div>'
      : (pr.pode_liberar
        ? '<div class="nfse-resultado ok"><p><b>Tudo certo!</b> O teste passou. Você já pode mudar para produção, e as notas passam a valer de verdade.</p></div>' +
          '<div class="word-acoes"><button class="primario" data-nfse-acao="liberar">Mudar para produção</button></div>'
        : '<p class="cfg-explica">Fica disponível quando o teste passar. Faltam: ' +
          esc((pr.itens || []).filter((i) => !i.ok).map((i) => i.titulo.toLowerCase()).join("; ")) + ".</p>")) +
    (recs ? '<h4 class="nfse-rec">Recomendado</h4>' + recs +
      (!emProducao && !(pr.recomendados || []).find((i) => i.id === "revisado" && i.ok)
        ? '<div class="word-acoes"><button data-nfse-acao="revisado">Registrar que o contador conferiu</button></div>' : "") : ""));

  /* Depois de configurar */
  const contador = cartaoCfg("Notas do mês e contador", metaCfg("relatório, XMLs e conferência"),
    '<p class="cfg-explica">O relatório do mês soma as notas, aponta recebimento sem nota e nota sem recebimento, e monta o .zip para o contador.</p>' +
    '<div class="word-acoes"><button data-nfse-acao="relatorio">' + ic("description", 16) + "Abrir o relatório do mês</button></div>");
  const recsLinhas = (n.recorrencias || []).map((x) => linhaNfse((x.servico_nome || x.cliente_nome || "—") + " · dia " + x.dia + " · " + x.valor,
    x.ativo ? "ligada" + (x.ultimo_mes ? " · último mês feito " + x.ultimo_mes : "") : "desligada") +
    (x.ativo ? '<div class="word-acoes"><button data-nfse-rec-desligar="' + x.id + '">Desligar</button></div>' : "")).join("");
  const recorrencias = cartaoCfg("Honorários recorrentes", metaCfg("rascunho no dia; nunca emite sozinho"),
    (recsLinhas || '<p class="cfg-explica">Nenhum. Ligue no Serviço, em Horas › Nota todo mês.</p>') +
    '<p class="cfg-explica">No dia, o PAULUS cria o rascunho da nota do mês e o põe em Aprovações.</p>');
  const tabs = (p.tabelas || []).map((x) => linhaNfse(x.titulo, "v" + x.versao + (x.data ? " · " + x.data : "") + " · " + x.itens + " itens")).join("");
  const tabelas = cartaoCfg("Tabelas oficiais", metaCfg("Portal da NFS-e"),
    tabs + '<p class="cfg-explica">Quando o portal publicar uma versão nova das planilhas, importe aqui.</p>' +
    '<div class="word-acoes"><input type="file" id="nfse-planilha" accept=".xlsx"><button data-nfse-acao="planilha">Importar planilha</button></div>');
  const hist = (p.historico || []).map((h) => linhaNfse("versão " + h.id + " · " + (h.motivo || ""), (h.criado_em || "").slice(0, 16).replace("T", " "))).join("");
  const historico = hist ? cartaoCfg("Histórico da configuração", "", hist) : "";
  const ligar = cartaoCfg("Emissão", "",
    '<div class="ag-toggle' + (n.ligado ? " on" : "") + '" data-nfse-acao="ligar" role="switch" tabindex="0" aria-checked="' + n.ligado + '">' +
    '<span class="duas-linhas"><b>Emitir NFS-e pelo PAULUS</b><small>desligada, o botão “Emitir nota” some do Financeiro e dos Serviços. O teste liga sozinho.</small></span><i></i></div>');
  const depois = '<details class="nfse-mais nfse-depois"' + (emProducao ? " open" : "") + "><summary>Depois de configurar: contador, recorrentes, tabelas e histórico</summary>" +
    ligar + contador + recorrencias + tabelas + historico + "</details>";

  return aberturaCfg() + caminho + passo1 + passo2 + passo3 + passo4 + passo5 + depois;
}

function dadosDoFormNfse() {
  const dados = {};
  document.querySelectorAll("[data-nfse-campo]").forEach((el) => {
    const partes = el.dataset.nfseCampo.split(".");
    let alvo = dados;
    partes.slice(0, -1).forEach((p) => { alvo[p] = alvo[p] || {}; alvo = alvo[p]; });
    alvo[partes[partes.length - 1]] = el.value;
  });
  const ib = document.querySelector('[data-nfse-acao="ibscbs"]');
  if (ib) { dados.ibscbs = dados.ibscbs || {}; dados.ibscbs.enviar = ib.classList.contains("on"); }
  return dados;
}

async function acaoNfse(acao) {
  const json = async (url, corpo) => {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: corpo ? JSON.stringify(corpo) : undefined });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
    return r.json();
  };
  const arquivo = async (url, campos) => {
    const fd = new FormData();
    Object.entries(campos).forEach(([k, v]) => fd.append(k, v));
    const r = await fetch(url, { method: "POST", body: fd });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
    return r.json();
  };
  let d = null;
  if (acao === "relatorio") { if (typeof abrirRelatorioNfse === "function") abrirRelatorioNfse(); return; }
  if (acao === "revisado") {
    const r = await dialogo({ titulo: "Quem conferiu a configuração?", contexto: "Nota fiscal › Produção",
      campo: { rotulo: "Nome", placeholder: "o contador" }, confirmar: "Registrar" });
    if (!r || !r.ok) return;
    const x = await json("/api/nfse/producao/revisado", { por: r.valor });
    if (x) { await carregarNfse(); desenharConfig(); }
    return;
  }
  if (acao === "teste") {
    const sel = document.getElementById("nfse-teste-cliente");
    const id = sel ? Number(sel.value || 0) : 0;
    if (!id) { avisoCert("escolha o cliente da nota de teste", { tom: "erro" }); return; }
    const b = document.querySelector('[data-nfse-acao="teste"]');
    if (b) { b.disabled = true; b.textContent = "Testando com o Sistema Nacional…"; }
    const x = await json("/api/nfse/teste", { cadastro_id: id });
    if (x) avisoCert(x.teste && x.teste.ok ? "teste feito: tudo certo" : "o teste não passou; veja o motivo no passo 4", { tom: x.teste && x.teste.ok ? "ok" : "erro" });
    await carregarNfse(); desenharConfig();
    const alvo = document.getElementById(x && x.pode_liberar ? "nfse-passo-5" : "nfse-passo-4");
    if (alvo) alvo.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (acao === "liberar") {
    const ok = await dialogo({ titulo: "Mudar para produção?", contexto: "Nota fiscal › Produção",
      texto: "Depois disto, as notas novas valem de verdade e vão para o Sistema Nacional de produção. Dá para voltar para o ambiente de testes a qualquer momento.",
      confirmar: "Mudar para produção", perigo: true });
    if (!ok || !ok.ok) return;
    const x = await json("/api/nfse/producao/liberar", { confirmo: true });
    if (x) { avisoCert("em produção: as notas valem de verdade", { tom: "ok" }); await carregarNfse(); desenharConfig(); }
    return;
  }
  if (acao === "voltar") {
    const x = await json("/api/nfse/producao/voltar");
    if (x) { avisoCert("de volta ao ambiente de testes", { tom: "ok" }); await carregarNfse(); desenharConfig(); }
    return;
  }
  if (acao === "ligar") d = await json("/api/nfse/ligar", { ligado: !(cfg.nfse && cfg.nfse.ligado) });
  else if (acao === "ibscbs") {
    const b = document.querySelector('[data-nfse-acao="ibscbs"]');
    if (b) b.classList.toggle("on");
    return;
  } else if (acao === "salvar") {
    d = await json("/api/nfse/prestador", { dados: dadosDoFormNfse() });
    if (d) {
      avisoCert("configuração gravada", { tom: "ok" });
      // Cidade nova ou nunca consultada: pergunta ao Sistema Nacional sozinho.
      const m = d.municipio || {};
      if ((d.prestador || {}).dados && d.prestador.dados.municipio && d.certificado && d.certificado.instalado && (!m.consultado_em || m.situacao !== "conveniado")) {
        const r2 = await fetch("/api/nfse/municipio/consultar", { method: "POST" }).catch(() => null);
        if (r2 && r2.ok) d = await r2.json();
      }
      await carregarNfse(); desenharConfig(); return;
    }
  } else if (acao === "certificado") {
    const f = document.getElementById("nfse-pfx");
    if (!f || !f.files || !f.files[0]) { avisoCert("escolha o arquivo .pfx ou .p12", { tom: "erro" }); return; }
    d = await arquivo("/api/nfse/certificado", { arquivo: f.files[0], senha: (document.getElementById("nfse-pfx-senha") || {}).value || "",
      guardar: (document.getElementById("nfse-pfx-guardar") || {}).checked ? "1" : "" });
    if (d) { avisoCert("certificado instalado", { tom: "ok" }); await carregarNfse(); desenharConfig(); return; }
  } else if (acao === "desbloquear") {
    d = await json("/api/nfse/certificado/senha", { senha: (document.getElementById("nfse-senha-desbloquear") || {}).value || "" });
  } else if (acao === "remover-certificado") {
    const ok = await dialogo({ titulo: "Tirar o certificado da nota?", contexto: "Configurações › Nota fiscal",
      texto: "A cópia do .pfx e a senha guardada saem deste computador. Para emitir de novo, instale outra vez.", confirmar: "Tirar", perigo: true });
    if (!ok || !ok.ok) return;
    d = await json("/api/nfse/certificado/remover");
  } else if (acao === "municipio") {
    avisoCert("perguntando ao Sistema Nacional…", { tom: "info" });
    d = await json("/api/nfse/municipio/consultar");
  } else if (acao === "planilha") {
    const f = document.getElementById("nfse-planilha");
    if (!f || !f.files || !f.files[0]) { avisoCert("escolha a planilha .xlsx do portal", { tom: "erro" }); return; }
    const r = await arquivo("/api/nfse/tabelas/importar", { arquivo: f.files[0] });
    if (r) { avisoCert("tabela importada", { tom: "ok" }); await carregarNfse(); desenharConfig(); }
    return;
  }
  if (d) { await carregarNfse(); desenharConfig(); }
}

document.addEventListener("click", async (e) => {
  const rec = e.target.closest("[data-nfse-rec-desligar]");
  if (rec) {
    const r = await fetch("/api/nfse/recorrencias/" + rec.dataset.nfseRecDesligar + "/desligar", { method: "POST" });
    if (r.ok) { await carregarNfse(); desenharConfig(); }
    return;
  }
  const b = e.target.closest("[data-nfse-acao]");
  if (!b) return;
  acaoNfse(b.dataset.nfseAcao);
});
document.addEventListener("keydown", (e) => {
  const b = e.target.closest && e.target.closest('[data-nfse-acao="ligar"], [data-nfse-acao="ibscbs"]');
  if (b && (e.key === " " || e.key === "Enter")) { e.preventDefault(); acaoNfse(b.dataset.nfseAcao); }
});

/* O município pelo nome: a lista oficial do IBGE (src/nfse/tabelas.py). */
let nfseBuscaRelogio = 0;
document.addEventListener("input", (e) => {
  const el = e.target;
  if (!el.matches || !el.matches("[data-nfse-busca-municipio]")) return;
  const q = el.value.trim();
  if (q.length < 3 || /^\d{7}$/.test(q)) return;
  clearTimeout(nfseBuscaRelogio);
  nfseBuscaRelogio = setTimeout(async () => {
    const r = await fetch("/api/nfse/municipios?q=" + encodeURIComponent(q)).catch(() => null);
    if (!r || !r.ok) return;
    const itens = (await r.json()).itens || [];
    const lista = document.getElementById("nfse-municipios");
    if (lista) lista.innerHTML = itens.map((m) => '<option value="' + esc(m.codigo) + '">' + esc(m.nome + "/" + m.uf) + "</option>").join("");
  }, 250);
});
