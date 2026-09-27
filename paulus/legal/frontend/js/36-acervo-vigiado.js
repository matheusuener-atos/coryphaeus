/* ------------------------------------------------------ acervo vigiado */
/*
   O Acervo mostra as pastas do computador que ele VIGIA, onde elas estão
   (src/api.py, /api/acervo/*). Nada é movido nem copiado para dentro do
   PAULUS: incluir uma pasta é passar a lê-la; tirar é deixar de ler.

   - Incluir pasta: o seletor de pastas do PAULUS e "Vigiar esta pasta".
   - Tirar do Acervo (pasta ou documento): o arquivo fica no computador, só
     sai da leitura. O documento tirado volta pela lista "fora do Acervo" ou
     pelo Desfazer do aviso.
   - Excluir: a caixa da confirmação de tirar um documento, desmarcada por
     padrão. Vai para a Lixeira do Windows (src/lixeira_windows.py).
   - A vigia do servidor relê quando algo entra, sai ou muda nas pastas; esta
     tela pergunta a versão de tempos em tempos e se redesenha quando muda.
*/

async function carregarVigiadas() {
  try {
    const r = await fetch("/api/acervo/pastas");
    if (r.ok) bib.vigiadas = await r.json();
  } catch (err) { /* fica o que havia */ }
  return bib.vigiadas;
}

async function adicionarPastaAoAcervo() {
  marcarDestino("biblioteca");
  const escolha = await escolherPastaNossa({ titulo: "Incluir pasta no Acervo", contexto: "Acervo", confirmar: "Vigiar esta pasta" });
  if (!escolha || !escolha.pasta) return;
  const r = await fetch("/api/acervo/pastas", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminho: escolha.pasta }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  bib.vigiadas = d;
  avisoCert("“" + d.nome + "” está no Acervo: " + plural(d.arquivos, "documento") +
    " para ler, sem sair do lugar. O que entrar nela depois entra aqui sozinho.", { tom: "ok" });
  bib.todos = [];
  if (typeof buscarAcervo === "function") buscarAcervo();
  vigiarTelaDoAcervo();
}

/* A cada poucos segundos, com o Acervo na tela: mudou a versão (a vigia
   releu, alguém anexou), busca de novo; lendo, mostra o andamento. */
function vigiarTelaDoAcervo() {
  if (bib.relogioVigia) return;
  bib.relogioVigia = setInterval(async () => {
    if (!document.querySelector("#centro .ae-tela")) { clearInterval(bib.relogioVigia); bib.relogioVigia = null; return; }
    let v;
    try { v = await (await fetch("/api/acervo/versao")).json(); } catch (err) { return; }
    const antes = bib.vigiadas || {};
    const lendoAntes = JSON.stringify(antes.lendo || {});
    if (v.versao !== antes.versao) {
      bib.todos = [];
      await carregarVigiadas();
      buscarAcervo();
    } else if (JSON.stringify(v.lendo || {}) !== lendoAntes) {
      antes.lendo = v.lendo;
      desenharBiblioteca();
    }
  }, 4000);
}

/* As raízes da barra de pastas: cada pasta vigiada, mesmo vazia, com as
   subpastas que têm documento. Agrupa pelo caminho da raiz, e não pelo
   nome: duas pastas "Contratos" vigiadas são duas raízes. */
function raizesDoAcervo() {
  const vigiadas = ((bib.vigiadas || {}).pastas) || [];
  const raizes = new Map(vigiadas.map((v) => [v.caminho, Object.assign({}, v, { mapa: new Map() })]));
  bib.todos.forEach((x) => {
    const chave = x.raiz || x.pasta;
    let r = raizes.get(chave);
    if (!r) {
      r = { caminho: chave, nome: (x.pasta_curta || x.pasta).split(" › ")[0], programa: false, mapa: new Map() };
      raizes.set(chave, r);
    }
    const folha = (x.pasta_curta || "").split(" › ").slice(1).join(" › ");
    const p = r.mapa.get(x.pasta) || { pasta: x.pasta, folha: folha, n: 0, sem: 0 };
    p.n += 1;
    if ((x.analise || {}).estado !== "analisado") p.sem += 1;
    r.mapa.set(x.pasta, p);
  });
  return [...raizes.values()].map((r) => Object.assign(r, {
    pastas: [...r.mapa.values()].sort((a, b) => a.folha.localeCompare(b.folha)),
  }));
}

function cabecaDaRaiz(r, classe) {
  const total = r.pastas.reduce((s, p) => s + p.n, 0);
  const nota = r.sumiu ? "não encontrada" : (!total ? "vazia" : "");
  return '<div class="am-raiz-linha ' + (classe || "") + '"><span class="am-raiz corta" title="' + esc(r.caminho) + '">' + esc(r.nome) + "</span>" +
    (nota ? '<small class="am-raiz-nota">' + nota + "</small>" : "") +
    '<button type="button" class="mais-linha" data-ac-raiz="' + esc(r.caminho) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 16) + "</button></div>";
}

function rodapeDasPastas() {
  const v = bib.vigiadas || {};
  const l = v.lendo || {};
  const lendo = l.andando && l.total
    ? '<p class="am-lendo">' + ic("sync", 14) + "lendo " + l.feitos + " de " + l.total + "…</p>" : "";
  const fora = v.fora
    ? '<button type="button" class="am-fora" data-ac-fora="1">' + ic("folder_off", 14) + plural(v.fora, "documento") + " fora do Acervo</button>" : "";
  return lendo + fora;
}

function menuDaRaiz(botao, caminho) {
  const r = raizesDoAcervo().find((x) => x.caminho === caminho);
  if (!r) return;
  const itens = [{ rotulo: "Abrir no Windows", icone: "open_in_new", acao: () => fetch("/api/biblioteca/abrir-pasta", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminho: r.caminho }),
  }) }];
  if (!r.programa) {
    itens.push("-", { rotulo: "Tirar do Acervo", icone: "folder_off", acao: async () => {
      const total = r.pastas.reduce((s, p) => s + p.n, 0);
      const ok = await confirmar({
        titulo: "Tirar “" + r.nome + "” do Acervo?", contexto: "Acervo",
        texto: "Paro de vigiar esta pasta. " + (total ? "Os " + plural(total, "documento") + " dela continuam" : "Ela continua") +
          " no seu computador, onde estão; só saem do Acervo. Dá para incluir de novo depois.",
        confirmar: "Tirar do Acervo",
      });
      if (!ok) return;
      const resp = await fetch("/api/acervo/pastas/tirar", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminho: r.caminho }),
      });
      if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
      bib.vigiadas = await resp.json();
      bib.todos = [];
      bib.pastaFiltro = "";
      avisoCert("“" + r.nome + "” saiu do Acervo — os arquivos continuam no computador", { tom: "ok" });
      buscarAcervo();
    } });
  }
  menuNaLinha(botao, itens);
}

/* Tirar pergunta antes, e diz com todas as letras que NÃO exclui. Excluir é
   a caixa, desmarcada: o arquivo vai para a Lixeira do Windows, de onde se
   restaura - e o botão muda para dizer isso quando a caixa é marcada. */
async function tirarDoAcervo(caminhos) {
  const n = caminhos.length;
  const docs = caminhos.map(docDoAcervo).filter(Boolean);
  const quais = n === 1 && docs[0] ? "“" + docs[0].nome + "”" : plural(n, "documento");
  const pedido = dialogo({
    titulo: "Tirar " + quais + " do Acervo?", contexto: "Acervo",
    texto: (n === 1
      ? "O arquivo não é excluído: continua no computador, onde está, e só deixa de ser lido pelo PAULUS."
      : "Os arquivos não são excluídos: continuam no computador, onde estão, e só deixam de ser lidos pelo PAULUS.") +
      " Dá para devolver depois.",
    marcar: { rotulo: "Também excluir do computador (vai para a Lixeira do Windows)", marcada: false },
    confirmar: "Tirar do Acervo",
  });
  const caixa = document.getElementById("dialogo-marcar");
  const botao = document.querySelector('.dialogo [data-dialogo="confirmar"]') || document.querySelector('[data-dialogo="confirmar"]');
  if (caixa && botao) {
    caixa.onchange = () => {
      botao.textContent = caixa.checked ? "Tirar e excluir" : "Tirar do Acervo";
      botao.className = caixa.checked ? "perigo" : "primario";
    };
  }
  const resposta = await pedido;
  if (!resposta || !resposta.ok) return;

  const r = await fetch("/api/acervo/tirar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ caminhos: caminhos, excluir: Boolean(resposta.marcada) }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  bib.vigiadas = d;
  bib.escolhidos.clear();
  bib.todos = [];
  const partes = [];
  if (d.excluidos.length) partes.push(plural(d.excluidos.length, "documento") + " na Lixeira do Windows");
  if (d.caminhos.length) partes.push(plural(d.caminhos.length, "documento") + " fora do Acervo, ainda no computador");
  d.nao_excluidos.forEach((x) => partes.push("“" + x.nome + "” não foi excluído: " + x.motivo));
  avisoCert(partes.join(" · "), {
    tom: d.nao_excluidos.length ? "erro" : "ok",
    acao: d.caminhos.length ? { rotulo: "Desfazer", fazer: async () => { await devolverAoAcervo(d.caminhos); } } : undefined,
  });
  buscarAcervo();
}

async function devolverAoAcervo(caminhos) {
  const r = await fetch("/api/acervo/devolver", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminhos: caminhos }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  bib.vigiadas = d;
  bib.todos = [];
  avisoCert(plural(d.devolvidos, "documento") + (d.devolvidos === 1 ? " voltou" : " voltaram") + " ao Acervo", { tom: "ok" });
  buscarAcervo();
}

async function mostrarForaDoAcervo() {
  let itens = [];
  try { itens = (await (await fetch("/api/acervo/fora")).json()).itens || []; } catch (err) { itens = []; }
  if (!itens.length) { avisoCert("nada fora do Acervo"); return; }
  const linhas = itens.map((x, i) => '<div class="anx-linha am-fora-linha">' + ic("description", 17) +
    '<span class="duas-linhas"><b class="corta">' + esc(x.nome) + '</b><small class="corta">' + esc(x.existe ? x.pasta : "não está mais no disco") + "</small></span>" +
    (x.existe ? '<button data-devolver="' + i + '">Devolver</button>' : "") + "</div>").join("");
  const aberto = dialogo({
    titulo: "Fora do Acervo", contexto: "Acervo", classe: "dialogo-anexar",
    html: '<p class="dialogo-dica">Estes documentos continuam no computador; só não são lidos pelo PAULUS.</p><div class="anx-lista">' + linhas + "</div>",
    confirmar: "Devolver todos",
    aoConfirmar: () => dialogoAberto.fechar({ todos: true }),
  });
  document.querySelectorAll("[data-devolver]").forEach((b) => {
    b.onclick = async () => {
      b.disabled = true;
      await devolverAoAcervo([itens[Number(b.dataset.devolver)].caminho]);
      b.closest(".am-fora-linha").remove();
    };
  });
  const r = await aberto;
  if (r && r.todos) await devolverAoAcervo(itens.filter((x) => x.existe).map((x) => x.caminho));
}

/* Ligações da barra de pastas; chamada por quem desenha o Acervo. */
function ligarAcervoVigiado(raiz) {
  (raiz || document).querySelectorAll("[data-ac-raiz]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); menuDaRaiz(b, b.dataset.acRaiz); };
  });
  (raiz || document).querySelectorAll("[data-ac-fora]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); mostrarForaDoAcervo(); };
  });
  if (bib.vigiadas === undefined || bib.vigiadas === null) {
    bib.vigiadas = {};
    carregarVigiadas().then(() => desenharBiblioteca());
  }
  vigiarTelaDoAcervo();
}
