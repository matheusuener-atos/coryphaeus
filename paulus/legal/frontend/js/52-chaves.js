/* ------------------------------------------------------------ chaves */
/*
   Os interruptores da Biblioteca (Configurações › Biblioteca) e das ideias do
   umbrelOS (Configurações › Conexões), src/rotas_chaves.py. Cada um liga na
   hora, sem o "Salvar alterações": é uma escolha de comportamento, e a tela
   diz o que cada um faz - e o que sai da máquina, quando sai.

   E o MCP das leis (src/mcp_leis.py): as conexões dos assistentes de fora,
   com o token mostrado uma vez só.
*/

const CHAVES_BIBLIOTECA = [
  ["hibrida", "Busca por sentido no material", "o material é procurado pela palavra e pelo sentido, e o livro é cortado por capítulo"],
  ["triagem", "Triagem ao entrar", "lei conhecida vai para as leis em casa; o resto ganha a ficha (autor, obra, ano)"],
  ["anotacoes", "Código anotado", "cada artigo citado por uma obra mostra o que ela diz, com a página"],
  ["camadas", "Resposta em camadas", "lei, doutrina e regra da casa separadas na resposta; opinião de autor nunca sai como texto de lei"],
  ["defasagem", "Aviso de obra antiga", "avisa quando a obra é anterior à redação atual do artigo que ela comenta"],
  ["mapa", "O que eu sei", "diz no fim da resposta quando a biblioteca não tem nada da área da pergunta"],
  ["leitura", "Glossário e teses", "o modelo de leitura lê cada obra em segundo plano; só fica o que a frase do livro confirma"],
  ["pacote", "Pacote .paulus-material", "exportar o que é seu e importar o de outro advogado, por arquivo, sem rede"],
];

async function ligarChave(bloco, chave, ligada) {
  const r = await fetch("/api/chaves", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bloco: bloco, chave: chave, ligada: ligada }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  const d = await r.json();
  cfg.chaves = d;
  if (bloco === "umbrel") window.PAULUS_UMBREL = d.umbrel;
  if (bloco === "conversa") {
    window.PAULUS_CONVERSA = d.conversa;
    document.documentElement.classList.toggle("pensando", Boolean(d.conversa.pensando));
  }
  return d;
}

function interruptor(bloco, chave, titulo, sub) {
  const ligada = Boolean(((cfg.chaves || {})[bloco] || {})[chave]);
  return '<div class="ag-toggle' + (ligada ? " on" : "") + '" data-chave-bloco="' + bloco + '" data-chave="' + chave + '">' +
    '<span class="duas-linhas"><b>' + esc(titulo) + "</b><small>" + esc(sub) + "</small></span><i></i></div>";
}

function cartaoChavesBiblioteca() {
  if (!cfg.chaves) return "";
  return cartaoCfg("Como a biblioteca trabalha", metaCfg("liga e desliga na hora"),
    '<div class="cfg-sub">' + CHAVES_BIBLIOTECA.map(([k, t, s]) => interruptor("biblioteca", k, t, s)).join("") + "</div>" +
    '<p class="cfg-explica">Nada da biblioteca sai desta máquina: nem o texto das obras, nem as perguntas. O glossário e as teses usam o modelo de leitura escolhido em Modelos.</p>');
}

function cartaoUmbrel() {
  if (!cfg.chaves) return "";
  const m = cfg.mcp || { conexoes: [], ferramentas: [] };
  const ligado = Boolean((cfg.chaves.umbrel || {}).mcp);
  const conexoes = (m.conexoes || []).map((c) =>
    '<div class="cfg-lei"><span class="duas-linhas"><b>' + esc(c.nome) + "</b><small>" + esc(c.ferramentas.join(", ")) +
    " · criada em " + esc(c.criada_em) + (c.ultimo_uso ? " · usada em " + esc(c.ultimo_uso) + " (" + plural(c.chamadas || 0, "chamada") + ")" : " · ainda não usada") +
    '</small></span><button data-mcp-revogar="' + esc(c.id) + '">Revogar</button></div>').join("");
  return cartaoCfg("Fotografar e assistentes de fora", metaCfg("desligados de fábrica"),
    '<div class="cfg-sub">' +
    interruptor("umbrel", "captura", "Fotografar documento", "no celular, pelo acesso de fora, a câmera vira um PDF no Acervo; de fora, passa antes por Aprovações") +
    interruptor("umbrel", "mcp", "Leis para assistentes de fora (MCP)", "o Claude ou outro assistente deste computador pede ao PAULUS o texto oficial de um artigo") + "</div>" +
    (ligado
      ? '<p class="cfg-explica"><b>O que sai:</b> só texto de lei do Planalto, que é público, para o assistente que você conectar - e dali para a empresa dele. ' +
        "<b>O que não sai:</b> documentos, biblioteca, cadastros, prazos. Só atende este computador (nunca pelo acesso de fora), e cada chamada fica no registro de acessos.</p>" +
        '<p class="cfg-explica">Endereço: <code>' + esc(m.endereco || "") + "</code></p>" +
        (conexoes ? '<div class="cfg-linhas">' + conexoes + "</div>" : '<p class="nota">Nenhuma conexão ainda.</p>') +
        '<div class="cfg-botoes"><button data-mcp-criar="1">' + ic("add", 16) + "Nova conexão</button></div>"
      : ""));
}

async function carregarChaves() {
  try {
    const r = await fetch("/api/chaves");
    if (r.ok) cfg.chaves = await r.json();
    if (cfg.chaves && (cfg.chaves.umbrel || {}).mcp) {
      const m = await fetch("/api/mcp");
      if (m.ok) cfg.mcp = await m.json();
    }
  } catch (err) { /* sem as chaves, os cartões não aparecem */ }
}

async function criarConexaoMcp() {
  const nome = await perguntar({ titulo: "Nova conexão MCP", contexto: "Configurações › Conexões",
    texto: "O nome é para você reconhecer depois (Claude Desktop, Claude Code, outro). A conexão recebe as três ferramentas das leis; revogar corta na hora.",
    campo: { rotulo: "Nome", placeholder: "Claude Desktop", icone: "link" }, confirmar: "Criar" });
  if (!nome) return;
  const r = await fetch("/api/mcp/conexoes", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome: nome, ferramentas: (cfg.mcp.ferramentas || []).map((f) => f.id) }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  cfg.mcp = d;
  await dialogo({
    titulo: "Token da conexão “" + d.conexao.nome + "”", contexto: "Aparece só agora",
    texto: "Copie o token e ponha na configuração do assistente, como cabeçalho Authorization: Bearer <token>, no endereço abaixo. Ele não aparece de novo: se perder, revogue e crie outra.",
    html: '<p><code class="mcp-token">' + esc(d.token) + "</code></p><p><code>" + esc(d.endereco) + "</code></p>",
    confirmar: "Já copiei", semCancelar: true,
  });
  desenharConfig();
}

function ligarChaves() {
  const raiz = $("cfg-tela");
  if (!raiz) return;
  raiz.querySelectorAll("[data-chave-bloco]").forEach((el) => {
    el.onclick = async () => {
      const d = await ligarChave(el.dataset.chaveBloco, el.dataset.chave, !el.classList.contains("on"));
      if (!d) return;
      if (el.dataset.chaveBloco === "umbrel" && el.dataset.chave === "mcp") await carregarChaves();
      desenharConfig();
    };
  });
  raiz.querySelectorAll("[data-mcp-criar]").forEach((b) => { b.onclick = criarConexaoMcp; });
  raiz.querySelectorAll("[data-mcp-revogar]").forEach((b) => {
    b.onclick = async () => {
      if (!(await confirmar({ titulo: "Revogar esta conexão?", contexto: "Configurações › Conexões",
        texto: "O assistente perde o acesso na hora. Para voltar, é criar outra conexão.", confirmar: "Revogar", perigo: true }))) return;
      const r = await fetch("/api/mcp/conexoes/" + encodeURIComponent(b.dataset.mcpRevogar), { method: "DELETE" });
      if (r.ok) cfg.mcp = await r.json();
      desenharConfig();
    };
  });
}
