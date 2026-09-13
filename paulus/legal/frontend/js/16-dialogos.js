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
    const campo = o.campo || null;
    const veu = document.createElement("div");
    veu.className = "veu-dialogo";
    veu.id = "veu-dialogo";
    const classe = "dialogo" + (o.larga ? " larga" : "");
    const paragrafos = o.texto ? String(o.texto).split("\n").map((p) => p.trim()).filter(Boolean).map((p) => "<p>" + esc(p) + "</p>").join("") : "";
    let miolo = "";
    if (campo) {
      miolo += '<div class="dialogo-campo">' + (campo.rotulo ? '<label for="dialogo-campo">' + esc(campo.rotulo) + "</label>" : "") +
        '<div class="dialogo-caixa">' + (campo.icone ? ic(campo.icone, 18) : "") +
        '<input id="dialogo-campo" type="' + (campo.tipo || "text") + '" value="' + esc(campo.valor || "") + '" placeholder="' + esc(campo.placeholder || "") + '" autocomplete="off" spellcheck="false">' +
        (campo.sufixo ? '<span class="dialogo-sufixo">' + esc(campo.sufixo) + "</span>" : "") + "</div>" +
        (campo.sugestoes && campo.sugestoes.length
          ? '<div class="dialogo-sugestoes">' + campo.sugestoes.map((s) => '<button type="button" data-dialogo-sugestao="' + esc(s) + '">' + esc(s) + "</button>").join("") + "</div>"
          : "") +
        (campo.dica ? '<span class="dialogo-dica">' + esc(campo.dica) + "</span>" : "") + "</div>";
    }
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
      fechar({ ok: true, valor: entrada ? entrada.value.trim() : "", marcada: marcar ? marcar.checked : false });
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
      b.onclick = () => { entrada.value = b.dataset.dialogoSugestao; conferir(); entrada.focus(); };
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

