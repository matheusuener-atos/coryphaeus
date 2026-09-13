/* ------------------------------------------------------------ dialogos */
/*
   Dialogos do sistema (docs/ui/05-interacoes-e-estados.md, mockup P -
   Popups). Um padrao para confirmar, perguntar um nome e avisar, no lugar
   do confirm() e do prompt() do navegador - que na janela do programa
   apareciam como "localhost diz" e nao tinham a cara do PAULUS.

   dialogo(o)  -> Promise com { ok, valor, marcada } ou null se cancelou
   confirmar(o) -> Promise<boolean>
   perguntar(o) -> Promise<string | null>

   o.titulo, o.contexto (onde estou), o.texto (paragrafos), o.html (extra),
   o.campo { rotulo, valor, placeholder, sufixo, icone, tipo, dica,
             sugestoes, obrigatorio (padrao sim), selecionar (padrao sim) },
   o.marcar { rotulo, marcada }, o.confirmar, o.cancelar, o.perigo, o.larga.

   Enter confirma, Esc fecha, o foco fica preso dentro e volta para o
   elemento de origem ao fechar. So um dialogo aberto por vez.
*/

let dialogoAberto = null;

function dialogo(o) {
  return new Promise((resolve) => {
    if (dialogoAberto) dialogoAberto.fechar(null);
    const origem = document.activeElement;
    // Um campo (o.campo) ou varios (o.campos, cada um com `chave`); o primeiro
    // e o de sempre - id dialogo-campo, foco, `valor` no resultado.
    const campos = (o.campos || (o.campo ? [o.campo] : [])).map((c, i) => Object.assign({ chave: "valor" + (i ? i : "") }, c));
    const campo = campos[0] || null;
    const veu = document.createElement("div");
    veu.className = "veu-dialogo";
    veu.id = "veu-dialogo";
    const classe = "dialogo" + (o.larga ? " larga" : "");
    const paragrafos = o.texto ? String(o.texto).split("\n").map((p) => p.trim()).filter(Boolean).map((p) => "<p>" + esc(p) + "</p>").join("") : "";
    let miolo = "";
    campos.forEach((c, i) => {
      const id = i ? "dialogo-campo-" + i : "dialogo-campo";
      miolo += '<div class="dialogo-campo">' + (c.rotulo ? '<label for="' + id + '">' + esc(c.rotulo) + "</label>" : "") +
        '<div class="dialogo-caixa">' + (c.icone ? ic(c.icone, 18) : "") +
        '<input id="' + id + '" data-dialogo-chave="' + esc(c.chave) + '" type="' + (c.tipo || "text") + '" value="' + esc(c.valor || "") + '" placeholder="' + esc(c.placeholder || "") + '" autocomplete="off" spellcheck="false">' +
        (c.sufixo ? '<span class="dialogo-sufixo">' + esc(c.sufixo) + "</span>" : "") + "</div>" +
        (c.sugestoes && c.sugestoes.length
          ? '<div class="dialogo-sugestoes">' + c.sugestoes.map((s) => '<button type="button" data-dialogo-sugestao="' + esc(s) + '" data-dialogo-para="' + id + '">' + esc(s) + "</button>").join("") + "</div>"
          : "") +
        (c.dica ? '<span class="dialogo-dica">' + esc(c.dica) + "</span>" : "") + "</div>";
    });
    if (o.marcar) {
      miolo += '<label class="dialogo-marcar"><input type="checkbox" id="dialogo-marcar"' + (o.marcar.marcada ? " checked" : "") + "><span>" + esc(o.marcar.rotulo) + "</span></label>";
    }
    veu.innerHTML = '<div class="' + classe + '" role="dialog" aria-modal="true" aria-labelledby="dialogo-titulo">' +
      '<div class="dialogo-cabeca"><span class="dialogo-titulos"><h2 id="dialogo-titulo">' + esc(o.titulo || "") + "</h2>" +
      (o.contexto ? '<span class="dialogo-contexto">' + esc(o.contexto) + "</span>" : "") + "</span>" +
      '<button type="button" class="dialogo-fechar" data-dialogo="cancelar" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>" +
      '<div class="dialogo-corpo">' + paragrafos + (o.html || "") + miolo + "</div>" +
      '<div class="dialogo-pe">' + (campo ? '<span class="dialogo-teclas"><kbd>Enter</kbd> confirma · <kbd>Esc</kbd> cancela</span>' : "") +
      '<span class="cresce"></span>' +
      '<button type="button" class="dialogo-cancelar" data-dialogo="cancelar">' + esc(o.cancelar || "Cancelar") + "</button>" +
      '<button type="button" class="primario' + (o.perigo ? " perigo" : "") + '" data-dialogo="confirmar">' + esc(o.confirmar || "Confirmar") + "</button></div></div>";
    document.body.appendChild(veu);

    const caixa = veu.firstElementChild;
    const entrada = veu.querySelector("#dialogo-campo");
    const marcar = veu.querySelector("#dialogo-marcar");
    const botaoOk = veu.querySelector('[data-dialogo="confirmar"]');
    const obrigatorio = Boolean(campo) && campo.obrigatorio !== false;
    const conferir = () => { if (entrada && obrigatorio) botaoOk.disabled = !entrada.value.trim(); };
    let fechado = false;
    const fechar = (resultado) => {
      if (fechado) return;
      fechado = true;
      document.removeEventListener("keydown", teclas, true);
      veu.remove();
      dialogoAberto = null;
      if (origem && origem.focus && document.contains(origem)) origem.focus();
      resolve(resultado);
    };
    const confirmarAgora = () => {
      if (entrada && obrigatorio && !entrada.value.trim()) { entrada.focus(); return; }
      const valores = {};
      let falta = null;
      veu.querySelectorAll("[data-dialogo-chave]").forEach((el, i) => {
        valores[el.dataset.dialogoChave] = el.value.trim();
        const espec = campos[i] || {};
        if (i && espec.obrigatorio && !el.value.trim() && !falta) falta = el;
      });
      if (falta) { falta.focus(); return; }
      fechar({ ok: true, valor: entrada ? entrada.value.trim() : "", valores: valores, marcada: marcar ? marcar.checked : false });
    };
    const teclas = (e) => {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); fechar(null); return; }
      if (e.key === "Enter") {
        const alvo = e.target;
        if (alvo && alvo.tagName === "BUTTON" && alvo.dataset.dialogo === "cancelar") return;
        if (alvo && alvo.tagName === "BUTTON" && alvo.dataset.dialogoSugestao !== undefined) return;
        e.preventDefault();
        e.stopPropagation();
        confirmarAgora();
        return;
      }
      if (e.key === "Tab") {
        const focaveis = Array.from(caixa.querySelectorAll("button:not(:disabled), input:not([type=hidden])"));
        if (!focaveis.length) return;
        const i = focaveis.indexOf(document.activeElement);
        if (e.shiftKey && i <= 0) { e.preventDefault(); focaveis[focaveis.length - 1].focus(); }
        else if (!e.shiftKey && i === focaveis.length - 1) { e.preventDefault(); focaveis[0].focus(); }
      }
    };
    document.addEventListener("keydown", teclas, true);
    veu.onclick = (e) => { if (e.target === veu) fechar(null); };
    veu.querySelectorAll('[data-dialogo="cancelar"]').forEach((b) => { b.onclick = () => fechar(null); });
    botaoOk.onclick = confirmarAgora;
    veu.querySelectorAll("[data-dialogo-sugestao]").forEach((b) => {
      b.onclick = () => {
        const alvo = veu.querySelector("#" + b.dataset.dialogoPara) || entrada;
        alvo.value = b.dataset.dialogoSugestao;
        conferir();
        alvo.focus();
      };
    });
    if (entrada) {
      entrada.oninput = conferir;
      conferir();
      entrada.focus();
      if (campo.selecionar !== false && entrada.value) entrada.setSelectionRange(0, entrada.value.length);
    } else {
      botaoOk.focus();
    }
    dialogoAberto = { fechar: fechar };
  });
}

function confirmar(o) {
  return dialogo(o).then((r) => Boolean(r && r.ok));
}

function perguntar(o) {
  return dialogo(o).then((r) => (r && r.ok ? r.valor : null));
}

/* Carregando (docs/ui/05): um esqueleto com a forma do conteudo, em --fill,
   sem giro e sem brilho. "lista" sao linhas de tabela; "cartoes", tres
   cartoes; "texto", um paragrafo. */
function esqueleto(tipo) {
  if (tipo === "cartoes") {
    return '<div class="esqueleto esq-cartoes" aria-busy="true">' +
      '<div class="esq-cartao"><i class="esq-linha curta"></i><i class="esq-linha"></i><i class="esq-linha media"></i></div>'.repeat(3) + "</div>";
  }
  if (tipo === "texto") return '<div class="esqueleto" aria-busy="true"><i class="esq-linha"></i><i class="esq-linha"></i><i class="esq-linha media"></i></div>';
  return '<div class="esqueleto esq-lista" aria-busy="true">' +
    '<div class="esq-fila"><i class="esq-bolinha"></i><span><i class="esq-linha media"></i><i class="esq-linha curta"></i></span></div>'.repeat(6) + "</div>";
}

/* ------------------------------------------------------------- lixeira */
/*
   Apagar guarda por 30 dias (docs/ui/05). Cada DELETE devolve o numero da
   entrada na lixeira e a frase do aviso; o aviso traz Desfazer, que chama
   restaurar e depois a funcao que redesenha a tela de onde a coisa saiu.
*/

const LIXEIRA_TEXTO = "Vai para a Lixeira por 30 dias; dá para restaurar em Configurações › Lixeira.";

async function avisarLixeira(resposta, depois) {
  let r = null;
  try { r = await resposta.json(); } catch (err) { r = null; }
  if (!r || !r.lixeira) { avisoCert("apagado"); return; }
  avisoCert(r.aviso || "foi para a lixeira", { tom: "ok", acao: { rotulo: "Desfazer", fazer: () => restaurarDaLixeira(r.lixeira, depois) } });
}

async function restaurarDaLixeira(id, depois) {
  const r = await fetch("/api/lixeira/" + id + "/restaurar", { method: "POST" });
  if (!r.ok) { avisoCert("não consegui restaurar: " + (await erroDe(r)), { tom: "erro" }); return null; }
  const d = await r.json();
  avisoCert(d.aviso || "restaurado", { tom: "ok" });
  if (depois) depois(d);
  return d;
}

/* O aviso no rodape. `opcoes.acao` = { rotulo, fazer } poe o Desfazer;
   `opcoes.tom` = "erro" faz o aviso branco com borda vinho; `opcoes.icone`
   troca o icone (info por padrao, check_circle com tom "ok"). */
function avisoCert(texto, opcoes) {
  const o = opcoes || {};
  let faixa = $("aviso-toast");
  if (!faixa) {
    faixa = document.createElement("div");
    faixa.id = "aviso-toast";
    document.body.appendChild(faixa);
  }
  faixa.className = "aviso-toast" + (o.tom === "erro" ? " erro" : "");
  const icone = o.icone || (o.tom === "erro" ? "error" : (o.tom === "ok" ? "check_circle" : "info"));
  faixa.innerHTML = ic(icone, 18) + "<span></span>" + (o.acao ? '<button type="button">' + esc(o.acao.rotulo || "Desfazer") + "</button>" : "");
  faixa.querySelector("span:not(.ic)").textContent = texto;
  if (o.acao) faixa.querySelector("button").onclick = () => { faixa.classList.remove("visivel"); o.acao.fazer(); };
  faixa.classList.add("visivel");
  clearTimeout(faixa.relogio);
  faixa.relogio = setTimeout(() => faixa.classList.remove("visivel"), o.acao ? 8000 : 4200);
}

async function erroDe(resposta) {
  try {
    const d = await resposta.json();
    return d.detail || "não deu certo";
  } catch (err) {
    return "não deu certo";
  }
}

/* Ler uma resposta que chega em pedaços.
   O servidor manda andamento em eventos porque as leituras longas levam
   minutos; sem isto a tela ficaria parada e pareceria travada. */
async function lerEventos(resposta, aoEvento) {
  const leitor = resposta.body.getReader();
  const dec = new TextDecoder();
  let buffer = "";

  while (true) {
    const passo = await leitor.read();
    if (passo.done) break;
    buffer += dec.decode(passo.value, { stream: true });
    const partes = buffer.split("\n\n");
    buffer = partes.pop();

    for (const parte of partes) {
      const mt = parte.match(/^event: (.+)$/m);
      const md = parte.match(/^data: (.*)$/m);
      if (!mt || !md) continue;
      aoEvento(mt[1], JSON.parse(md[1]));
    }
  }
}

function dataBR(iso) {
  if (!iso || iso.length < 10) return iso || "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return d + "/" + m + "/" + a;
}

function quandoCurto(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso.slice(0, 10);
  return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

