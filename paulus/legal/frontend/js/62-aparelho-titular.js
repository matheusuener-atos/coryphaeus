/* ------------------------------ pensar no aparelho: o que o titular controla (D5) */
/*
   O cartão "Escrever no aparelho" em Configurações › Acesso de fora, só na
   janela do escritório (as rotas também só respondem aqui):

   - ligar e desligar para o escritório (a chave aparelho.ligado). Desligar
     para na hora toda resposta que um aparelho estiver escrevendo: ela
     termina aqui;
   - por conta, a liberação fica em Contas › Permissões ("Escrever a
     resposta no próprio aparelho"); o cartão mostra quem está liberado;
   - "só no escritório": clientes, Serviços e pastas cujo conteúdo nunca vai
     para aparelho - a regra vale na montagem do pacote, no servidor;
   - o relatório: por pessoa, quantas respostas foram escritas no aparelho,
     quantas foram refeitas pela conferência e quantas o escritório terminou.
*/

const aparelhoTitular = { chaves: null, marcas: [], servicos: [], clientes: [], relatorio: null, erro: "" };

async function carregarAparelhoTitular() {
  aparelhoTitular.erro = "";
  try {
    const [c, m, r] = await Promise.all([fetch("/api/chaves"), fetch("/api/aparelho/so-no-escritorio"), fetch("/api/aparelho/relatorio")]);
    aparelhoTitular.chaves = c.ok ? await c.json() : null;
    const d = m.ok ? await m.json() : {};
    aparelhoTitular.marcas = d.marcas || [];
    aparelhoTitular.servicos = d.servicos || [];
    aparelhoTitular.clientes = d.clientes || [];
    aparelhoTitular.relatorio = r.ok ? await r.json() : null;
  } catch (err) {
    aparelhoTitular.erro = "não consegui ler: " + ((err && err.message) || err);
  }
}

const TIPOS_DA_MARCA = { cliente: "Cliente", servico: "Serviço", pasta: "Pasta" };

function cartaoAparelhoTitular() {
  if (!acessoDeFora.local) return "";
  const a = aparelhoTitular;
  const ligado = Boolean(a.chaves && a.chaves.aparelho && a.chaves.aparelho.ligado);
  const liberadas = (acessoCfg.contas || []).filter((c) => c.papel !== "titular" && (c.permissoes || {}).aparelho === "faz");

  const chave = '<div class="apt-linha"><span class="duas-linhas"><b>Para o escritório: ' + (ligado ? "ligado" : "desligado") + "</b><small>" +
    (ligado ? "desligar para na hora toda resposta que um aparelho estiver escrevendo; ela termina aqui"
      : "desligado, toda resposta é escrita aqui, venha de onde vier a pergunta") + "</small></span>" +
    '<button data-apt-ligar="' + (ligado ? "0" : "1") + '"' + (ligado ? ' class="perigo"' : "") + ">" + (ligado ? "Desligar" : "Ligar") + "</button></div>" +
    '<p class="cfg-explica">Por conta: em Contas › Permissões, “Escrever a resposta no próprio aparelho”. ' +
    (liberadas.length ? "Liberadas: " + liberadas.map((c) => esc(c.nome)).join(", ") + "." : "Nenhuma conta liberada.") +
    " A pergunta que vai ao aparelho lê por trechos, só ela; ler o documento inteiro, editar, redigir e e-mail ficam sempre aqui.</p>";

  const opcoes = ['<option value="">Escolha um cliente ou Serviço…</option>']
    .concat(a.clientes.map((c) => '<option value="cliente:' + c.id + '">Cliente · ' + esc(c.nome) + "</option>"))
    .concat(a.servicos.map((s) => '<option value="servico:' + s.id + '">Serviço · ' + esc(s.nome) + (s.cliente ? " (" + esc(s.cliente) + ")" : "") + "</option>"));
  const marcas = a.marcas.length
    ? '<div class="apt-marcas">' + a.marcas.map((m, i) =>
      '<div class="apt-marca"><span class="duas-linhas"><b>' + esc(m.rotulo) + "</b><small>" + esc(TIPOS_DA_MARCA[m.tipo] || m.tipo) + "</small></span>" +
      '<button data-apt-tirar="' + i + '">' + ic("close", 16) + "Tirar</button></div>").join("") + "</div>"
    : '<p class="cfg-explica">Nada marcado: todo caso que a conta vê pode ir ao aparelho dela.</p>';
  const so = marcas +
    '<div class="apt-nova"><select id="apt-escolha" aria-label="Cliente ou Serviço">' + opcoes.join("") + "</select>" +
    '<button data-apt-marcar="1">Marcar</button></div>' +
    '<div class="apt-nova"><input type="text" id="apt-pasta" placeholder="ou uma pasta do Acervo (ex.: Clientes\\Fusão)" aria-label="Pasta do Acervo">' +
    '<button data-apt-pasta="1">Marcar a pasta</button></div>' +
    '<p class="cfg-explica">Pergunta cujos trechos saem de um caso marcado é escrita aqui, mesmo com a escrita no aparelho ligada, e a pessoa vê o motivo. Um cliente marcado vale para todos os Serviços dele, inclusive os que abrirem depois.</p>';

  const r = a.relatorio || { pessoas: [], total: {} };
  const rel = r.pessoas.length
    ? '<div class="apt-relatorio"><div class="apt-rel-cab"><span>Pessoa</span><span>No aparelho</span><span>Refeitas</span><span>Terminadas aqui</span></div>' +
      r.pessoas.map((p) => '<div class="apt-rel-linha"><span>' + esc(p.pessoa) + "</span><b>" + p.no_aparelho + "</b><b>" + p.refeitas + "</b><b>" + p.no_escritorio + "</b></div>").join("") +
      "</div>" +
      '<p class="cfg-explica">Refeitas: o texto do aparelho não passou na conferência e o escritório escreveu de novo. Terminadas aqui: o aparelho parou, o pacote venceu ou a escrita foi desligada. Cada linha está em “Quem acessou”, abaixo.</p>'
    : '<p class="cfg-explica">Nenhuma resposta escrita em aparelho ainda.</p>';

  return cartaoCfg("Escrever no aparelho", metaCfg("respostas escritas no aparelho de quem está de fora"),
    '<div class="apt" id="apt">' + (a.erro ? '<p class="cfg-explica">' + esc(a.erro) + "</p>" : "") +
    chave + '<h4 class="apt-sub">Só no escritório</h4>' + so + '<h4 class="apt-sub">Relatório</h4>' + rel + "</div>");
}

async function guardarMarcasDoAparelho(marcas) {
  const r = await fetch("/api/aparelho/so-no-escritorio", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ marcas: marcas.map((m) => ({ tipo: m.tipo, valor: m.valor })) }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return false; }
  aparelhoTitular.marcas = (await r.json()).marcas || [];
  return true;
}

function ligarAparelhoTitular() {
  const caixa = $("apt");
  if (!caixa) return;
  const redesenhar = () => { if (typeof desenharConfig === "function") desenharConfig(); };
  const ligar = caixa.querySelector("[data-apt-ligar]");
  if (ligar) ligar.onclick = async () => {
    const r = await fetch("/api/chaves", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bloco: "aparelho", chave: "ligado", ligada: ligar.dataset.aptLigar === "1" }) });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    aparelhoTitular.chaves = await r.json();
    avisoCert(aparelhoTitular.chaves.aparelho.ligado ? "Escrita no aparelho ligada para o escritório."
      : "Escrita no aparelho desligada: o que estava sendo escrito termina aqui.", { tom: "ok" });
    redesenhar();
  };
  caixa.querySelectorAll("[data-apt-tirar]").forEach((b) => {
    b.onclick = async () => {
      const i = Number(b.dataset.aptTirar);
      if (await guardarMarcasDoAparelho(aparelhoTitular.marcas.filter((_, j) => j !== i))) redesenhar();
    };
  });
  const marcar = caixa.querySelector("[data-apt-marcar]");
  if (marcar) marcar.onclick = async () => {
    const v = ($("apt-escolha") || {}).value || "";
    if (!v) return;
    const [tipo, valor] = v.split(":");
    if (await guardarMarcasDoAparelho(aparelhoTitular.marcas.concat([{ tipo: tipo, valor: Number(valor) }]))) redesenhar();
  };
  const pasta = caixa.querySelector("[data-apt-pasta]");
  if (pasta) pasta.onclick = async () => {
    const v = (($("apt-pasta") || {}).value || "").trim();
    if (!v) return;
    if (await guardarMarcasDoAparelho(aparelhoTitular.marcas.concat([{ tipo: "pasta", valor: v }]))) redesenhar();
  };
}
