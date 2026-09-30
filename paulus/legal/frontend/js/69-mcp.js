/* ------------------------------------------ MCP além das leis (L7) */
/*
   A conexão MCP nova escolhe as ferramentas - as públicas (leis, súmulas e
   temas do STJ) e, se quiser, as do escritório (documentos, busca nos
   trechos, cartão, posição da casa) - e, para estas, o escopo (o Acervo
   inteiro, pastas ou Serviços) e o "entendi que sai" (src/mcp_leis.py).
*/

function escopoDaConexao(c) {
  const e = c.escopo || {};
  if (e.tudo) return "o Acervo inteiro";
  const partes = [];
  if ((e.pastas || []).length) partes.push(plural(e.pastas.length, "pasta"));
  if ((e.servicos || []).length) partes.push(plural(e.servicos.length, "Serviço", "Serviços"));
  return partes.join(" e ");
}

async function novaConexaoMcp() {
  const ferramentas = (cfg.mcp && cfg.mcp.ferramentas) || [];
  let servicos = [];
  try { servicos = ((await (await fetch("/api/servicos?filtro=todos")).json()).servicos) || []; } catch (err) { servicos = []; }
  const caixa = (f) => '<label class="mcp-opcao"><input type="checkbox" data-mcp-f="' + esc(f.id) + '"' + (f.publica ? " checked" : "") + ">" +
    '<span class="duas-linhas"><b>' + esc(f.id) + "</b><small>" + esc(f.descricao) + "</small></span></label>";
  const html = '<div class="ag-campo"><label>Nome</label><input type="text" id="mcp-nome" placeholder="Claude Desktop" autocomplete="off"></div>' +
    '<h4 class="mcp-sub">Públicas</h4>' + ferramentas.filter((f) => f.publica).map(caixa).join("") +
    '<h4 class="mcp-sub">Do escritório — só leitura</h4>' + ferramentas.filter((f) => !f.publica).map(caixa).join("") +
    '<div id="mcp-escopo" hidden><h4 class="mcp-sub">Escopo</h4>' +
    '<label class="mcp-opcao"><input type="checkbox" id="mcp-tudo"><span>O Acervo inteiro</span></label>' +
    '<div class="ag-campo"><label>ou estas pastas do Acervo (uma por linha)</label><textarea id="mcp-pastas" rows="2" placeholder="Clientes\\Alfa"></textarea></div>' +
    (servicos.length ? '<p class="cfg-explica">ou os Serviços:</p>' + servicos.map((s) =>
      '<label class="mcp-opcao"><input type="checkbox" data-mcp-s="' + s.id + '"><span>' + esc(s.nome) + "</span></label>").join("") : "") +
    '<label class="mcp-opcao mcp-entendi"><input type="checkbox" id="mcp-entendi"><span><b>Entendi que sai do escritório:</b> os trechos e os fatos desses documentos ' +
    "vão para o assistente conectado e, dali, para a empresa dele (a Anthropic, a OpenAI…). Casos marcados “só no escritório” nunca saem.</span></label></div>";
  const aberto = dialogo({ titulo: "Nova conexão MCP", contexto: "Configurações › Conexões", html: html, confirmar: "Criar", classe: "mcp-dialogo" });
  const lido = { nome: "", ferramentas: new Set(ferramentas.filter((f) => f.publica).map((f) => f.id)), tudo: false, pastas: "", servicos: new Set(), entendi: false };
  const mostrarEscopo = () => { const e = $("mcp-escopo"); if (e) e.hidden = !ferramentas.some((f) => !f.publica && lido.ferramentas.has(f.id)); };
  const nome = $("mcp-nome");
  if (nome) { nome.addEventListener("input", () => { lido.nome = nome.value; }); nome.focus(); }
  document.querySelectorAll("[data-mcp-f]").forEach((el) => el.addEventListener("change", () => {
    if (el.checked) lido.ferramentas.add(el.dataset.mcpF); else lido.ferramentas.delete(el.dataset.mcpF);
    mostrarEscopo();
  }));
  document.querySelectorAll("[data-mcp-s]").forEach((el) => el.addEventListener("change", () => {
    if (el.checked) lido.servicos.add(Number(el.dataset.mcpS)); else lido.servicos.delete(Number(el.dataset.mcpS));
  }));
  const liga = (id, k) => { const el = $(id); if (el) el.addEventListener("change", () => { lido[k] = el.checked; }); };
  liga("mcp-tudo", "tudo");
  liga("mcp-entendi", "entendi");
  const pastas = $("mcp-pastas");
  if (pastas) pastas.addEventListener("input", () => { lido.pastas = pastas.value; });
  const r = await aberto;
  if (!r || !r.ok) return;
  const corpo = { nome: lido.nome.trim() || "Assistente", ferramentas: [...lido.ferramentas], entendi: lido.entendi,
    escopo: { tudo: lido.tudo, pastas: lido.pastas.split(/\r?\n/).map((x) => x.trim()).filter(Boolean), servicos: [...lido.servicos] } };
  const resp = await fetch("/api/mcp/conexoes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
  if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
  const d = await resp.json();
  cfg.mcp = d;
  await dialogo({
    titulo: "Token da conexão “" + d.conexao.nome + "”", contexto: "Aparece só agora",
    texto: "Copie o token e ponha na configuração do assistente, como cabeçalho Authorization: Bearer <token>, no endereço abaixo. Ele não aparece de novo: se perder, revogue e crie outra.",
    html: '<p><code class="mcp-token">' + esc(d.token) + "</code></p><p><code>" + esc(d.endereco) + "</code></p>",
    confirmar: "Já copiei", semCancelar: true,
  });
  desenharConfig();
}
