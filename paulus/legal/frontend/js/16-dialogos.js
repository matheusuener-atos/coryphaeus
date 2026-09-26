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
             sugestoes, obrigatorio (padrao sim), selecionar (padrao sim),
             max (limite de caracteres) },
   o.marcar { rotulo, marcada }, o.confirmar, o.cancelar, o.perigo, o.sucesso (botao verde: aprovar), o.larga,
   o.classe (uma classe a mais no cartao, para dialogos com miolo proprio),
   o.depois (HTML depois dos campos: listas, texto longo, botoes - o que
   tiver `data-dialogo-chave` volta em `valores`), o.rodape (HTML a esquerda
   do rodape), o.aoConfirmar (quem chama salva e fecha: Confirmar e Enter
   chamam a funcao e o dialogo fica aberto - para formularios que avisam o
   erro sem perder o que foi escrito).

   Enter confirma, Esc fecha, o foco fica preso dentro e volta para o
   elemento de origem ao fechar. So um dialogo aberto por vez. As teclas
   continuam valendo, mas nao sao mais escritas no rodape (pedido).
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
    const classe = "dialogo" + (o.larga ? " larga" : "") + (o.classe ? " " + o.classe : "");
    const paragrafos = o.texto ? String(o.texto).split("\n").map((p) => p.trim()).filter(Boolean).map((p) => "<p>" + esc(p) + "</p>").join("") : "";
    let miolo = "";
    campos.forEach((c, i) => {
      const id = i ? "dialogo-campo-" + i : "dialogo-campo";
      miolo += '<div class="dialogo-campo">' + (c.rotulo ? '<label for="' + id + '">' + esc(c.rotulo) + "</label>" : "") +
        '<div class="dialogo-caixa">' + (c.icone ? ic(c.icone, 18) : "") +
        '<input id="' + id + '" data-dialogo-chave="' + esc(c.chave) + '" type="' + (c.tipo || "text") + '" value="' + esc(c.valor || "") + '" placeholder="' + esc(c.placeholder || "") + '"' + (c.max ? ' maxlength="' + Number(c.max) + '"' : "") + ' autocomplete="off" spellcheck="false">' +
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
      '<div class="dialogo-corpo">' + paragrafos + (o.html || "") + miolo + (o.depois || "") + "</div>" +
      '<div class="dialogo-pe">' + (o.rodape || "") + '<span class="cresce"></span>' +
      '<button type="button" class="dialogo-cancelar" data-dialogo="cancelar">' + esc(o.cancelar || "Cancelar") + "</button>" +
      '<button type="button" class="primario' + (o.perigo ? " perigo" : (o.sucesso ? " sucesso" : "")) + '" data-dialogo="confirmar">' + esc(o.confirmar || "Confirmar") + "</button></div></div>";
    document.body.appendChild(veu);
    veu.querySelectorAll(".dialogo-caixa select").forEach(melhorarSelect);

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
      fecharListaDeEscolha();
      // O dialogo sai andando, como entrou. Fechado e fechado na hora: perde
      // o id e deixa de receber clique enquanto some, senao quem procura o
      // dialogo (ou clica atras dele) ainda o encontra na tela.
      veu.id = "";
      veu.classList.add("saindo");
      sairDoAr(caixa, { para: "translateY(6px) scale(.985)" });
      sairDoAr(veu, { para: "none", aoFim: () => veu.remove() });
      dialogoAberto = null;
      if (origem && origem.focus && document.contains(origem)) origem.focus();
      resolve(resultado);
    };
    const confirmarAgora = () => {
      if (o.aoConfirmar) { o.aoConfirmar(); return; }
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
        // Enter num botao que nao e o Confirmar (um chip, Excluir, uma acao da
        // exibicao) aperta aquele botao.
        if (alvo && alvo.tagName === "BUTTON" && alvo.dataset.dialogo !== "confirmar") return;
        // No texto longo, Enter quebra a linha.
        if (alvo && alvo.tagName === "TEXTAREA") return;
        e.preventDefault();
        e.stopPropagation();
        confirmarAgora();
        return;
      }
      if (e.key === "Tab") {
        const focaveis = Array.from(caixa.querySelectorAll("button:not(:disabled), input:not([type=hidden]), select:not([hidden]), textarea"));
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

/* A ficha do pop-up de exibicao: rotulo a esquerda, valor a direita, uma
   linha por dado. Linha nula sai; valor vazio vira travessao. */
function fichaDoDialogo(linhas) {
  return '<dl class="dialogo-ficha">' + linhas.filter(Boolean).map(([rotulo, valor]) =>
    "<div><dt>" + esc(rotulo) + "</dt><dd>" + esc(valor || "—") + "</dd></div>").join("") + "</dl>";
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

/* O aviso de todas as telas. Era um toast no rodape; agora todo aviso sai na
   barra de titulo (`avisoNaJanela`, em 02-casca.js), e este nome ficou porque
   e o que as telas chamam. `opcoes.acao` = { rotulo, fazer } poe o Desfazer;
   `opcoes.tom` = "erro" ou "ok"; `opcoes.icone` troca o icone. */
function avisoCert(texto, opcoes) {
  const o = opcoes || {};
  avisoNaJanela(texto, {
    tom: o.tom === "erro" ? "erro" : "",
    icone: o.icone || (o.tom === "ok" ? "check_circle" : ""),
    acao: o.acao ? { rotulo: o.acao.rotulo || "Desfazer", fazer: o.acao.fazer } : null,
  });
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


/* ----------------------------------------------------- calendario popover */
/*
   O calendariozinho que abre de um botao: dias, e clicando no titulo meses,
   e de novo anos - o mesmo caminho dos seletores de data que as pessoas ja
   conhecem. As REGRAS moram nele: dia fora de `min`..`max` nao se escolhe
   (fica apagado), entao prazo no passado ou ano digitado errado nao passam
   despercebidos. `marcados` poe um ponto nos dias que ja tem algo.

   calendarioPopover(ancora, { valor, min, max, marcados, limpar, passado,
                              atalhos, aoEscolher })
   `atalhos` poe a barra de cima - Hoje, Amanha, Proxima segunda. Calendario
   e hora sao dois: a data se escolhe aqui, a hora no relogio do campo dela.
   `passado`: os dias antes de hoje podem ser escolhidos, mas vêm em vinho -
   quem escolhe vê que a data já passou.
   valor/min/max em ISO (AAAA-MM-DD). aoEscolher(iso) - "" quando limpou.
*/

const NOMES_DOS_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
  "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const INICIAIS_DA_SEMANA = ["Do", "Se", "Te", "Qu", "Qu", "Se", "Sa"];

let calendarioAberto = null;

function isoDoDia(ano, mes, dia) {
  return ano + "-" + String(mes + 1).padStart(2, "0") + "-" + String(dia).padStart(2, "0");
}

function hojeIso() {
  const d = new Date();
  return isoDoDia(d.getFullYear(), d.getMonth(), d.getDate());
}

function somarAnosIso(iso, anos) {
  const [a, m, d] = iso.split("-").map(Number);
  return isoDoDia(a + anos, m - 1, Math.min(d, 28));
}

function fecharCalendario() {
  if (!calendarioAberto) return;
  calendarioAberto.remover();
  calendarioAberto = null;
}

function calendarioPopover(ancora, opcoes) {
  fecharCalendario();
  const o = opcoes || {};
  const min = o.min || "";
  const max = o.max || "";
  const marcados = new Set(o.marcados || []);
  const inicio = (o.valor || (min && hojeIso() < min ? min : hojeIso())).split("-").map(Number);
  const vista = { modo: "dias", ano: inicio[0], mes: inicio[1] - 1 };
  let escolhido = o.valor || "";
  const caixa = document.createElement("div");
  caixa.className = "calendario";
  caixa.setAttribute("role", "dialog");
  caixa.setAttribute("aria-label", "Escolher a data");
  document.body.appendChild(caixa);

  const fora = (iso) => (min && iso < min) || (max && iso > max);
  const mesFora = (ano, mes) => (min && isoDoDia(ano, mes, 31) < min) || (max && isoDoDia(ano, mes, 1) > max);
  const anoFora = (ano) => (min && ano + "-12-31" < min) || (max && ano + "-01-01" > max);

  const desenhar = () => {
    let titulo, grade, classeGrade;
    if (vista.modo === "dias") {
      titulo = NOMES_DOS_MESES[vista.mes] + " " + vista.ano;
      const primeiro = new Date(vista.ano, vista.mes, 1).getDay();
      const inicioGrade = new Date(vista.ano, vista.mes, 1 - primeiro);
      const hoje = hojeIso();
      let dias = "";
      for (let i = 0; i < 42; i++) {
        const d = new Date(inicioGrade.getFullYear(), inicioGrade.getMonth(), inicioGrade.getDate() + i);
        const iso = isoDoDia(d.getFullYear(), d.getMonth(), d.getDate());
        const classe = "cal-dia" + (d.getMonth() !== vista.mes ? " fora-do-mes" : "") + (iso === hoje ? " hoje" : "") +
          (iso === escolhido ? " escolhido" : "") + (marcados.has(iso) ? " marcado" : "") + (o.passado && iso < hoje ? " passado" : "");
        dias += '<button type="button" class="' + classe + '" data-cal-dia="' + iso + '"' + (fora(iso) ? " disabled" : "") +
          ' aria-label="' + d.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) + '">' +
          d.getDate() + "</button>";
      }
      grade = INICIAIS_DA_SEMANA.map((x) => '<span class="cal-semana">' + x + "</span>").join("") + dias;
      classeGrade = "cal-grade dias";
    } else if (vista.modo === "meses") {
      titulo = String(vista.ano);
      grade = NOMES_DOS_MESES.map((nome, m) => {
        const classe = "cal-celula" + (escolhido && escolhido.slice(0, 7) === isoDoDia(vista.ano, m, 1).slice(0, 7) ? " escolhido" : "");
        return '<button type="button" class="' + classe + '" data-cal-mes="' + m + '"' + (mesFora(vista.ano, m) ? " disabled" : "") + ">" + nome.slice(0, 3) + "</button>";
      }).join("");
      classeGrade = "cal-grade meses";
    } else {
      const decada = Math.floor(vista.ano / 10) * 10;
      titulo = decada + "–" + (decada + 9);
      grade = "";
      for (let a = decada - 1; a <= decada + 10; a++) {
        const classe = "cal-celula" + (a < decada || a > decada + 9 ? " fora-do-mes" : "") + (escolhido && Number(escolhido.slice(0, 4)) === a ? " escolhido" : "");
        grade += '<button type="button" class="' + classe + '" data-cal-ano="' + a + '"' + (anoFora(a) ? " disabled" : "") + ">" + a + "</button>";
      }
      classeGrade = "cal-grade anos";
    }
    // Os atalhos do dia a dia, na barra de cima: hoje, amanha e a proxima
    // segunda, cada um dizendo em que dia cai.
    let atalhos = "";
    if (o.atalhos) {
      const hoje = new Date();
      const segunda = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() + ((8 - hoje.getDay()) % 7 || 7));
      const opcoes = [
        ["Hoje", new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate())],
        ["Amanhã", new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() + 1)],
        ["Próxima segunda", segunda],
      ];
      atalhos = '<div class="cal-atalhos">' + opcoes.map(([nome, d]) => {
        const iso = isoDoDia(d.getFullYear(), d.getMonth(), d.getDate());
        if (fora(iso)) return "";
        const classe = "cal-atalho" + (iso === escolhido ? " escolhido" : "");
        return '<button type="button" class="' + classe + '" data-cal-dia="' + iso + '"><span>' + nome + "</span>" +
          '<small>' + INICIAIS_DA_SEMANA[d.getDay()] + " " + d.getDate() + "/" + String(d.getMonth() + 1).padStart(2, "0") + "</small></button>";
      }).join("") + "</div>";
    }
    const pe = [];
    if (!fora(hojeIso()) && !o.atalhos) pe.push('<button type="button" class="cal-rodape-botao" data-cal-hoje="1">Hoje</button>');
    if (o.limpar && escolhido) pe.push('<button type="button" class="cal-rodape-botao" data-cal-limpar="1">Sem data</button>');

    caixa.innerHTML = atalhos + '<div class="cal-topo">' +
      '<button type="button" class="cal-seta" data-cal-passo="-1" aria-label="Anterior">' + ic("chevron_left", 18) + "</button>" +
      '<button type="button" class="cal-titulo" data-cal-subir="1">' + titulo + "</button>" +
      '<button type="button" class="cal-seta" data-cal-passo="1" aria-label="Próximo">' + ic("chevron_right", 18) + "</button></div>" +
      '<div class="' + classeGrade + '">' + grade + "</div>" +
      (pe.length ? '<div class="cal-pe">' + pe.join("") + "</div>" : "");
  };

  const escolher = (iso) => {
    fecharCalendario();
    if (o.aoEscolher) o.aoEscolher(iso);
  };

  caixa.addEventListener("click", (e) => {
    e.stopPropagation();
    const b = e.target.closest("button");
    if (!b || b.disabled) return;
    if (b.dataset.calDia) return escolher(b.dataset.calDia);
    if (b.dataset.calMes) { vista.mes = Number(b.dataset.calMes); vista.modo = "dias"; return desenhar(); }
    if (b.dataset.calAno) { vista.ano = Number(b.dataset.calAno); vista.modo = "meses"; return desenhar(); }
    if (b.dataset.calHoje) return escolher(hojeIso());
    if (b.dataset.calLimpar) return escolher("");
    if (b.dataset.calSubir) { vista.modo = vista.modo === "dias" ? "meses" : "anos"; return desenhar(); }
    if (b.dataset.calPasso) {
      const passo = Number(b.dataset.calPasso);
      if (vista.modo === "dias") {
        const d = new Date(vista.ano, vista.mes + passo, 1);
        vista.ano = d.getFullYear();
        vista.mes = d.getMonth();
      } else {
        vista.ano += passo * (vista.modo === "meses" ? 1 : 10);
      }
      desenhar();
    }
  });

  desenhar();
  // Abaixo do botão; sem espaço embaixo, em cima. Nunca fora da janela.
  const r = ancora.getBoundingClientRect();
  const largura = caixa.offsetWidth;
  const altura = caixa.offsetHeight;
  const topo = r.bottom + 6 + altura > innerHeight ? Math.max(8, r.top - 6 - altura) : r.bottom + 6;
  caixa.style.top = topo + "px";
  caixa.style.left = Math.max(8, Math.min(r.left, innerWidth - largura - 8)) + "px";
  if (animacoesLigadas()) {
    caixa.animate([{ opacity: 0, transform: "translateY(-4px)" }, { opacity: 1, transform: "none" }], { duration: 180, easing: CURVA_ENTRA });
  }

  const cliqueFora = (e) => { if (!caixa.contains(e.target) && !ancora.contains(e.target)) fecharCalendario(); };
  const teclas = (e) => { if (e.key === "Escape") { e.stopPropagation(); fecharCalendario(); } };
  setTimeout(() => document.addEventListener("mousedown", cliqueFora), 0);
  document.addEventListener("keydown", teclas, true);
  calendarioAberto = {
    remover: () => {
      document.removeEventListener("mousedown", cliqueFora);
      document.removeEventListener("keydown", teclas, true);
      sairDoAr(caixa, { para: "translateY(-4px)" });
    },
  };
}


/* ---------------------------------------------------- caixa de escolha */
/*
   O <select> com a cara do campo. A lista nativa é desenhada pelo sistema -
   no Windows, branca, com a letra do sistema e fora do tema. Aqui o select
   fica escondido e continua sendo quem guarda o valor (quem lê o formulário
   não muda nada); na frente dele, um botão com o rótulo e uma lista no
   padrão dos menus do programa. Setas andam, Enter escolhe, Esc fecha só a
   lista.
*/

let listaDeEscolha = null;

function fecharListaDeEscolha() {
  if (!listaDeEscolha) return;
  listaDeEscolha.remover();
  listaDeEscolha = null;
}

function melhorarSelect(select) {
  if (select.dataset.melhorado) return;
  select.dataset.melhorado = "1";
  select.hidden = true;
  const botao = document.createElement("button");
  botao.type = "button";
  // O botao leva as classes do select: o que a tela desenhou para o campo
  // (largura, cor, tamanho) continua valendo nele.
  botao.className = "escolha-botao" + (select.className ? " " + select.className : "");
  botao.setAttribute("aria-haspopup", "listbox");
  if (select.id) {
    const rotulo = document.querySelector('label[for="' + select.id + '"]');
    if (rotulo) rotulo.htmlFor = select.id + "-botao";
    botao.id = select.id + "-botao";
  }
  botao.innerHTML = '<span class="escolha-rotulo"></span>' + ic("expand_more", 18);
  select.after(botao);
  const rotular = () => {
    const opcao = select.options[select.selectedIndex];
    botao.querySelector(".escolha-rotulo").textContent = opcao ? opcao.text : "";
  };
  rotular();
  select.addEventListener("change", rotular);
  botao.setAttribute("aria-expanded", "false");
  botao.onclick = (e) => { e.stopPropagation(); if (listaDeEscolha && listaDeEscolha.botao === botao) fecharListaDeEscolha(); else abrirListaDeEscolha(select, botao); };
  botao.onkeydown = (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); abrirListaDeEscolha(select, botao); }
  };
}

function abrirListaDeEscolha(select, botao) {
  fecharListaDeEscolha();
  botao.setAttribute("aria-expanded", "true");
  const lista = document.createElement("div");
  lista.className = "menu-conversa escolha-lista";
  lista.setAttribute("role", "listbox");
  lista.innerHTML = Array.from(select.options).map((o, i) => {
    const classe = i === select.selectedIndex ? "atual" : "";
    return '<button type="button" role="option" class="' + classe + '" data-escolha="' + i + '"' + (o.disabled ? " disabled" : "") + ">" + esc(o.text) + "</button>";
  }).join("");
  document.body.appendChild(lista);

  // A lista tem a largura da caixa do campo e abre embaixo dela (ou em cima,
  // sem espaço embaixo).
  const caixa = (botao.closest(".dialogo-caixa") || botao).getBoundingClientRect();
  // Nunca mais estreita que um rotulo legivel: campo curto (o corpo "12")
  // abria uma lista de 30 px com o texto quebrado letra a letra.
  lista.style.width = Math.max(caixa.width, 170) + "px";
  lista.style.left = Math.max(8, Math.min(caixa.left, innerWidth - Math.max(caixa.width, 170) - 8)) + "px";
  const altura = lista.offsetHeight;
  lista.style.top = (caixa.bottom + 4 + altura > innerHeight ? Math.max(8, caixa.top - 4 - altura) : caixa.bottom + 4) + "px";
  if (animacoesLigadas()) {
    lista.animate([{ opacity: 0, transform: "translateY(-4px)" }, { opacity: 1, transform: "none" }], { duration: 160, easing: CURVA_ENTRA });
  }

  const itens = () => Array.from(lista.querySelectorAll("button:not(:disabled)"));
  const escolher = (i) => {
    select.selectedIndex = i;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    fecharListaDeEscolha();
    botao.focus();
  };
  lista.querySelectorAll("[data-escolha]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); escolher(Number(b.dataset.escolha)); };
  });
  const atual = lista.querySelector(".atual") || itens()[0];
  if (atual) { atual.focus(); atual.scrollIntoView({ block: "nearest" }); }

  // Na janela e na captura: antes do diálogo, que fecharia com o Esc e
  // confirmaria com o Enter.
  const teclas = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); fecharListaDeEscolha(); botao.focus(); return; }
    if (e.key === "Enter" || e.key === " ") {
      const foco = document.activeElement;
      if (foco && foco.dataset && foco.dataset.escolha !== undefined) { e.preventDefault(); e.stopPropagation(); escolher(Number(foco.dataset.escolha)); }
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Tab") {
      e.preventDefault();
      e.stopPropagation();
      const lista_ = itens();
      const i = lista_.indexOf(document.activeElement);
      const passo = e.key === "ArrowUp" || (e.key === "Tab" && e.shiftKey) ? -1 : 1;
      const proximo = lista_[(i + passo + lista_.length) % lista_.length];
      if (proximo) proximo.focus();
    }
  };
  const cliqueFora = (e) => { if (!lista.contains(e.target) && e.target !== botao && !botao.contains(e.target)) fecharListaDeEscolha(); };
  window.addEventListener("keydown", teclas, true);
  setTimeout(() => document.addEventListener("mousedown", cliqueFora), 0);
  listaDeEscolha = {
    botao: botao,
    remover: () => {
      window.removeEventListener("keydown", teclas, true);
      document.removeEventListener("mousedown", cliqueFora);
      botao.setAttribute("aria-expanded", "false");
      sairDoAr(lista, { para: "translateY(-4px)", duracao: 120 });
    },
  };
}

/* ------------------------------------------------------------ o relogio */
/*
   A HORA NO PADRAO DO PROGRAMA. O campo de hora do navegador e uma caixinha
   de sistema - fundo claro, setinhas minusculas, o relogio do Windows - que
   nao combina com o tema escuro nem com o resto dos campos. No lugar dele:
   um botao com a hora e, ao clicar, um popover com a hora grande e duas
   reguas, horas e minutos, como no desenho pedido.

   relogioPopover(ancora, { valor, aoEscolher, limpar, passo })
   valor "HH:MM" (ou vazio), aoEscolher(hora) - "" quando limpou.
   `passo` e o pulo dos minutos (5 por padrao).
*/

let relogioAberto = null;

function fecharRelogio() {
  if (!relogioAberto) return;
  relogioAberto.remover();
  relogioAberto = null;
}

function horaAgora() {
  const d = new Date();
  return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
}

function relogioPopover(ancora, opcoes) {
  fecharRelogio();
  const o = opcoes || {};
  const passo = Number(o.passo) || 5;
  const partes = /^(\d{1,2}):(\d{2})$/.exec(o.valor || "");
  let h = partes ? Math.min(23, Number(partes[1])) : 9;
  let m = partes ? Math.min(59, Number(partes[2])) : 0;

  const caixa = document.createElement("div");
  caixa.className = "relogio-pop";
  caixa.innerHTML =
    '<div class="relogio-mostrador"><b data-rel-h>00</b><i>:</i><b data-rel-m>00</b></div>' +
    '<label class="relogio-regua"><span>Horas</span>' +
    '<input type="range" min="0" max="23" step="1" data-rel-range="h"></label>' +
    '<label class="relogio-regua"><span>Minutos</span>' +
    '<input type="range" min="0" max="59" step="' + passo + '" data-rel-range="m"></label>' +
    '<div class="relogio-pe"><button type="button" data-rel="agora">Agora</button>' +
    (o.limpar ? '<button type="button" data-rel="limpar">Limpar</button>' : "") +
    '<span class="cresce"></span><button type="button" class="primario" data-rel="pronto">Pronto</button></div>';
  document.body.appendChild(caixa);

  // Abre embaixo do campo (ou em cima, sem espaco embaixo), alinhado a ele.
  const ondeEsta = ancora.getBoundingClientRect();
  const altura = caixa.offsetHeight;
  caixa.style.left = Math.max(8, Math.min(ondeEsta.left, innerWidth - caixa.offsetWidth - 8)) + "px";
  caixa.style.top = (ondeEsta.bottom + 4 + altura > innerHeight ? Math.max(8, ondeEsta.top - 4 - altura) : ondeEsta.bottom + 4) + "px";
  if (animacoesLigadas()) {
    caixa.animate([{ opacity: 0, transform: "translateY(-4px)" }, { opacity: 1, transform: "none" }], { duration: 160, easing: CURVA_ENTRA });
  }

  const reguaH = caixa.querySelector('[data-rel-range="h"]');
  const reguaM = caixa.querySelector('[data-rel-range="m"]');
  const texto = () => String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0");
  const mostrar = () => {
    caixa.querySelector("[data-rel-h]").textContent = String(h).padStart(2, "0");
    caixa.querySelector("[data-rel-m]").textContent = String(m).padStart(2, "0");
    reguaH.value = h;
    reguaM.value = m;
    // A parte andada da regua fica em tinta; o resto, no fio.
    reguaH.style.setProperty("--andado", (h / 23 * 100) + "%");
    reguaM.style.setProperty("--andado", (m / 59 * 100) + "%");
  };
  mostrar();
  reguaH.oninput = () => { h = Number(reguaH.value); mostrar(); };
  reguaM.oninput = () => { m = Number(reguaM.value); mostrar(); };

  const responder = (valor) => { fecharRelogio(); if (o.aoEscolher) o.aoEscolher(valor); };
  caixa.querySelector('[data-rel="pronto"]').onclick = () => responder(texto());
  caixa.querySelector('[data-rel="agora"]').onclick = () => {
    const agora = horaAgora().split(":").map(Number);
    h = agora[0];
    m = Math.round(agora[1] / passo) * passo;
    if (m > 59) m = 59 - (59 % passo);
    mostrar();
  };
  const limpar = caixa.querySelector('[data-rel="limpar"]');
  if (limpar) limpar.onclick = () => responder("");

  const teclas = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); fecharRelogio(); ancora.focus(); return; }
    if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); responder(texto()); }
  };
  const cliqueFora = (e) => { if (!caixa.contains(e.target) && e.target !== ancora && !ancora.contains(e.target)) responder(texto()); };
  window.addEventListener("keydown", teclas, true);
  setTimeout(() => document.addEventListener("mousedown", cliqueFora), 0);
  reguaH.focus();
  relogioAberto = {
    ancora: ancora,
    remover: () => {
      window.removeEventListener("keydown", teclas, true);
      document.removeEventListener("mousedown", cliqueFora);
      sairDoAr(caixa, { para: "translateY(-4px)" });
    },
  };
}

/* O campo de hora, como a lista: o input continua guardando o valor (quem le
   o formulario nao muda nada) e some; na frente dele, o botao com a hora. */
function melhorarHora(campo) {
  if (campo.dataset.melhorado) return;
  campo.dataset.melhorado = "1";
  campo.hidden = true;
  const botao = document.createElement("button");
  botao.type = "button";
  botao.className = "escolha-botao relogio-botao" + (campo.className ? " " + campo.className : "");
  if (campo.id) {
    const rotulo = document.querySelector('label[for="' + campo.id + '"]');
    if (rotulo) rotulo.htmlFor = campo.id + "-botao";
    botao.id = campo.id + "-botao";
  }
  botao.innerHTML = '<span class="escolha-rotulo"></span>' + ic("schedule", 18);
  campo.after(botao);
  const rotular = () => {
    const vazio = !campo.value;
    botao.querySelector(".escolha-rotulo").textContent = campo.value || "--:--";
    botao.classList.toggle("vazio", vazio);
  };
  rotular();
  campo.addEventListener("change", rotular);
  botao.onclick = (e) => {
    e.stopPropagation();
    if (relogioAberto && relogioAberto.ancora === botao) { fecharRelogio(); return; }
    relogioPopover(botao, {
      valor: campo.value, limpar: !campo.required,
      aoEscolher: (valor) => {
        campo.value = valor;
        rotular();
        campo.dispatchEvent(new Event("change", { bubbles: true }));
      },
    });
  };
}

/* O campo de data, como o de hora: o input continua guardando o valor e
   some, e na frente dele fica o botao com a data. O calendario que abre e o
   do programa, com os atalhos. Calendario e hora sao dois: a hora tem o
   relogio dela, no campo ao lado. */
function melhorarData(campo) {
  if (campo.dataset.melhorado) return;
  campo.dataset.melhorado = "1";
  campo.hidden = true;
  const botao = document.createElement("button");
  botao.type = "button";
  botao.className = "escolha-botao data-botao" + (campo.className ? " " + campo.className : "");
  if (campo.id) {
    const rotulo = document.querySelector('label[for="' + campo.id + '"]');
    if (rotulo) rotulo.htmlFor = campo.id + "-botao";
    botao.id = campo.id + "-botao";
  }
  botao.innerHTML = '<span class="escolha-rotulo"></span>' + ic("calendar_month", 18);
  campo.after(botao);
  const rotular = () => {
    botao.querySelector(".escolha-rotulo").textContent = campo.value ? campo.value.split("-").reverse().join("/") : "--/--/----";
    botao.classList.toggle("vazio", !campo.value);
  };
  rotular();
  campo.addEventListener("change", rotular);
  botao.onclick = (e) => {
    e.stopPropagation();
    if (calendarioAberto) { fecharCalendario(); return; }
    calendarioPopover(botao, {
      valor: campo.value, limpar: !campo.required, passado: true, atalhos: true,
      aoEscolher: (data) => {
        campo.value = data;
        rotular();
        campo.dispatchEvent(new Event("change", { bubbles: true }));
      },
    });
  };
}

/* TODA LISTA E TODA HORA DA TELA no padrao do programa - a caixa de escolha
   e o relogio -, inclusive as que aparecem depois, quando uma tela se
   redesenha. E por isso que a melhora passa por um observador: cada tela
   monta o HTML dela do jeito dela, e nenhuma precisa lembrar de chamar. */
function melhorarCampos(raiz) {
  const onde = raiz || document;
  onde.querySelectorAll("select:not([multiple]):not([data-melhorado])").forEach((s) => {
    if (!s.size || s.size <= 1) melhorarSelect(s);
  });
  onde.querySelectorAll('input[type="time"]:not([data-melhorado])').forEach(melhorarHora);
  onde.querySelectorAll('input[type="date"]:not([data-melhorado])').forEach(melhorarData);
}

const olhoDosCampos = new MutationObserver(() => melhorarCampos(document));
document.addEventListener("DOMContentLoaded", () => {
  melhorarCampos(document);
  olhoDosCampos.observe(document.body, { childList: true, subtree: true });
});
