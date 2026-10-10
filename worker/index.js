// O Worker do paulus.ia.br: o site (pasta site/), a nuvem do PAULUS, o
// acesso de fora e a calibracao dos modelos.
//
// A cobranca e da Atos (atos.dev.br, com o Mercado Pago dela): o PAVLVS nao fala com o Mercado Pago. O plano
// chega pelos avisos da Atos (worker/atos.js), e o cadastro e o pagamento antigos (/cadastro) levam ao checkout dela.
//
//   POST /api/mp/aviso        o webhook do Mercado Pago de antes da Atos: respondido e ignorado
//   POST /api/calibracao      medidas de maquina e modelo, de quem escolheu
//                             participar (so numeros; veja receberCalibracao)
//   GET  /api/calibracao      todas as medidas, para o programa estimar melhor
//
// Todo o resto e o site estatico.
//
// As notas fiscais (NFS-e do PAVLVS) sao emitidas pelo painel admin, em
// /api/admin/nfse/* (worker/admin.js -> worker/nfse/api.js -> o Durable Object
// EmissorNFSe). A antiga ponte com o PAULUS da casa (/api/nfse-casa/*) saiu.
//
// O acesso de fora (worker/tunel.js): /conectar e /api/tunel/*, que criam o
// caminho de cada escritorio ate o PAULUS dele. Desligado sem TUNEL_ATIVO.
//
// A cobranca pela Atos (worker/atos.js): POST /api/atos/eventos, os eventos
// assinados da Atos Cobranca (o plano pago, a recarga). Sem EVENTOS_SEGREDO_PAVLVS, 503.
//
// A nuvem do PAULUS (worker/ia.js): /api/ia/*, o portao ate os provedores dos
// modelos (DeepInfra, Mistral, Anthropic) com o medidor de creditos. Desligada sem IA_ATIVA.
//
// O KV APOIOS guarda hoje so a calibracao (chave "calibracao:todas"). O nome
// vem do antigo "Apoiar o projeto", que saiu; o binding ficou com o nome para
// nao pedir configuracao nova no Cloudflare. As chaves antigas do apoio que
// ainda estiverem la ("pix:", "assinatura:", "cartao:") vencem sozinhas.

import { atenderTunel, ehRotaDoTunel, limparEscritorios } from "./tunel.js";
import { atenderIA, ehRotaDaIA } from "./ia.js";
import { atenderConta, ehRotaDaConta } from "./conta.js";
import { atenderAdmin, ehRotaDoAdmin, comPlanosDoPainel, enviarCampanhas, enviarEmail } from "./admin.js";
import { depoisPendentes } from "./nfse/api.js";
import { atenderIdentidade, ehRotaDaIdentidade } from "./identidade.js";
import { atenderAtos, checkoutDaAtos, ehRotaDaAtos } from "./atos.js";

// O medidor da nuvem do PAULUS (worker/ia.js): um Durable Object por conta.
export { ContaIA } from "./ia.js";
// O emissor de NFS-e da nuvem (worker/nfse/emissor.js): a classe do Durable
// Object (o binding EMISSOR_NFSE pede). As rotas ficam no painel admin.
export { EmissorNFSe } from "./nfse/emissor.js";


export default {
  async fetch(request, envOriginal, ctx) {
    const url = new URL(request.url);
    // Os planos publicados pelo painel admin (KV) valem no lugar de IA_PLANOS.
    const env = url.pathname.startsWith("/api/") ? await comPlanosDoPainel(envOriginal) : envOriginal;
    // O Worker nunca atende <escritorio>.paulus.ia.br: esse trafego e do tunel
    // de cada escritorio, direto da Cloudflare ao computador dele. Se uma rota
    // curinga um dia apontar para ca por engano, nada passa por aqui.
    if (url.hostname.endsWith(".paulus.ia.br") && url.hostname !== "www.paulus.ia.br") {
      return new Response("não encontrado", { status: 404 });
    }
    if (ehRotaDoTunel(url)) {
      try {
        return await atenderTunel(request, env, url, { dentroDoLimite });
      } catch (erro) {
        return json({ erro: "falha no servidor do acesso externo" }, 500);
      }
    }
    if (ehRotaDoAdmin(url)) {
      try {
        return await atenderAdmin(request, env, url, ctx, { dentroDoLimite });
      } catch (erro) {
        return json({ erro: "falha no servidor do painel" }, 500);
      }
    }
    // Os eventos da Atos Cobranca (worker/atos.js): o plano pago na Atos chega aqui.
    if (ehRotaDaAtos(url)) {
      try {
        return await atenderAtos(request, env, url);
      } catch (erro) {
        return json({ erro: "falha ao aplicar o evento da Atos" }, 500);
      }
    }
    if (ehRotaDaIA(url)) {
      try {
        return await atenderIA(request, env, url, ctx, { dentroDoLimite });
      } catch (erro) {
        return json({ erro: "falha no servidor da nuvem" }, 500);
      }
    }
    // A conta PAVLVS por e-mail e senha (worker/identidade.js): a alternativa ao Google.
    if (ehRotaDaIdentidade(url)) {
      try {
        return await atenderIdentidade(request, env, url, { dentroDoLimite, enviarEmail });
      } catch (erro) {
        return json({ erro: "falha no servidor da conta" }, 500);
      }
    }
    // A Minha conta (worker/conta.js): a sessao do site, o plano, o pagamento e o escritorio.
    if (ehRotaDaConta(url)) {
      try {
        return await atenderConta(request, env, url, ctx, { dentroDoLimite });
      } catch (erro) {
        return json({ erro: "falha no servidor da Minha conta" }, 500);
      }
    }
    if (url.pathname === "/cadastro" || url.pathname.startsWith("/cadastro/")) {
      // As vendas pela Atos: o cadastro e o pagamento antigos levam ao checkout dela, com o mesmo plano e periodo.
      return Response.redirect(checkoutDaAtos(url.searchParams.get("plano"), url.searchParams.get("periodo")), 302);
    }
    // A Minha conta: a CSP dela (so scripts do site; a Conta Atos abre em outra janela).
    if (/^\/(minha-conta|en\/my-account)(\/|$)/.test(url.pathname)) return comCSP(await env.ASSETS.fetch(request));
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    try {
      // O app do Mercado Pago de antes da Atos ainda pode avisar: 200, para ele nao repetir, e nada muda.
      if (url.pathname === "/api/mp/aviso" && request.method === "POST") return json({ ignorado: "a cobrança do PAVLVS é pela Atos" });
      if (url.pathname === "/api/calibracao" && request.method === "POST") {
        if (!(await dentroDoLimite(request, env))) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
        return await receberCalibracao(request, env);
      }
      if (url.pathname === "/api/calibracao" && request.method === "GET") return await entregarCalibracao(env);
      return json({ erro: "rota não existe" }, 404);
    } catch (erro) {
      return json({ erro: "falha no servidor" }, 500);
    }
  },

  // O Cron Trigger diario (wrangler.jsonc): libera os enderecos do acesso de
  // fora que nunca conectaram em 7 dias ou estao parados ha mais de 180.
  // Sem TUNEL_ATIVO e sem o KV, nao faz nada.
  // O Cron de cada minuto manda a proxima leva das campanhas do painel admin
  // (50 por minuto; sem RESEND_API_KEY, nada) e faz o PDF (e o e-mail) de uma
  // NFS-e emitida que ainda nao tem (worker/nfse/api.js, depoisPendentes; sem
  // nota esperando, uma leitura do KV).
  async scheduled(controller, envOriginal, ctx) {
    const env = await comPlanosDoPainel(envOriginal);
    if (controller && controller.cron === "* * * * *") {
      ctx.waitUntil(enviarCampanhas(env));
      ctx.waitUntil(depoisPendentes(env).catch(() => null));
    } else {
      ctx.waitUntil(limparEscritorios(env));
    }
  },
};

/* A Minha conta (site/minha-conta e /en/my-account): so rodam scripts do proprio site; um script injetado e
   bloqueado pelo navegador. Nenhum script inline roda (o do tema e o assets/tema-cedo.js). O pagamento nao e mais
   daqui (e da Atos): sem os campos do Mercado Pago. A Conta Atos entra numa janela de atos.dev.br (window.open). */
export const CSP_MINHA_CONTA = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com data:",
  "img-src 'self' data:",
  "connect-src 'self' https://viacep.com.br https://brasilapi.com.br",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

function comCSP(resposta) {
  const r = new Response(resposta.body, resposta);
  if ((r.headers.get("content-type") || "").includes("text/html")) {
    r.headers.set("content-security-policy", CSP_MINHA_CONTA);
    r.headers.set("referrer-policy", "strict-origin-when-cross-origin");
    r.headers.set("x-content-type-options", "nosniff");
  }
  return r;
}

function json(dados, status = 200) {
  return new Response(JSON.stringify(dados), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

async function dentroDoLimite(request, env) {
  if (!env.LIMITE) return true;
  const chave = request.headers.get("cf-connecting-ip") || "sem-ip";
  const { success } = await env.LIMITE.limit({ key: chave });
  return success;
}

async function lerPedido(request) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

// ------------------------------------------------------------ calibracao
//
// A estimativa de quanto cada modelo de IA demora numa maquina
// (paulus/legal/src/maquina.py) melhora com medidas de muitas maquinas. Quem
// escolhe participar, no programa, manda as medidas da maquina dele e recebe
// as de todos. So numeros da maquina e do modelo: processador, memoria, as
// duas velocidades medidas, o modelo e as palavras por segundo dele. Nada do
// escritorio, nada de pessoa. Cada amostra e conferida campo a campo; o que
// nao cabe no formato e jogado fora.
//
// Tudo numa chave so do KV APOIOS (prefixo "calibracao:"), para nao pedir
// configuracao nova no Cloudflare. Uma amostra por maquina e modelo: medir de
// novo troca a antiga. Guarda as 5000 mais recentes.

const CAL_CHAVE = "calibracao:todas";
const CAL_MAXIMO = 5000;
const CAL_POR_PEDIDO = 50;

function calNumero(v, min, max) {
  return typeof v === "number" && Number.isFinite(v) && v >= min && v <= max;
}

function calTexto(v, max, re) {
  return typeof v === "string" && v.length <= max && (!re || re.test(v));
}

function limparAmostra(a) {
  if (!a || typeof a !== "object") return null;
  const m = a.maquina || {};
  const ok =
    calTexto(m.id, 32, /^[0-9a-f]{6,32}$/) && calNumero(m.versao, 1, 99) &&
    calTexto(m.processador, 120, /^[\x20-\x7EÀ-ſ]*$/) && calNumero(m.nucleos, 1, 512) &&
    calNumero(m.ram_total_gb, 0.5, 4096) && calNumero(m.banda_gbs, 0.1, 2000) && calNumero(m.gflops, 0.1, 100000) &&
    calTexto(a.modelo, 120, /^[a-z0-9][a-z0-9._:\/-]*$/i) && calNumero(a.tamanho_gb, 0.01, 500) &&
    calNumero(a.parametros_b, 0.01, 2000) && calTexto(a.quantizacao || "", 20, /^[A-Za-z0-9_]*$/) &&
    calNumero(a.escrita_tps, 0.01, 10000) && calNumero(a.leitura_tps || 0, 0, 100000);
  if (!ok) return null;
  return {
    maquina: {
      id: m.id, versao: m.versao, processador: m.processador, nucleos: m.nucleos, ram_total_gb: m.ram_total_gb,
      avx2: m.avx2 === true ? true : m.avx2 === false ? false : null, banda_gbs: m.banda_gbs, gflops: m.gflops,
      na_bateria: m.na_bateria === true ? true : m.na_bateria === false ? false : null,
    },
    gpu: a.gpu === true,
    modelo: a.modelo, tamanho_gb: a.tamanho_gb, parametros_b: a.parametros_b, quantizacao: a.quantizacao || "",
    escrita_tps: a.escrita_tps, leitura_tps: a.leitura_tps || 0,
    quando: new Date().toISOString().slice(0, 16).replace("T", " "),
  };
}

async function receberCalibracao(request, env) {
  if (!env.APOIOS) return json({ erro: "armazenamento indisponível" }, 503);
  const corpo = await lerPedido(request);
  const lista = Array.isArray(corpo && corpo.amostras) ? corpo.amostras.slice(0, CAL_POR_PEDIDO) : [];
  const limpas = lista.map(limparAmostra).filter(Boolean);
  if (!limpas.length) return json({ erro: "nenhuma amostra válida" }, 400);
  let todas = [];
  try {
    todas = JSON.parse((await env.APOIOS.get(CAL_CHAVE)) || "[]");
  } catch {
    todas = [];
  }
  for (const a of limpas) {
    const i = todas.findIndex((x) => x.maquina.id === a.maquina.id && x.modelo === a.modelo);
    if (i >= 0) todas.splice(i, 1);
    todas.push(a);
  }
  todas = todas.slice(-CAL_MAXIMO);
  await env.APOIOS.put(CAL_CHAVE, JSON.stringify(todas));
  return json({ recebidas: limpas.length, total: todas.length });
}

async function entregarCalibracao(env) {
  const bruto = env.APOIOS ? await env.APOIOS.get(CAL_CHAVE) : null;
  let amostras = [];
  try {
    amostras = bruto ? JSON.parse(bruto) : [];
  } catch {
    amostras = [];
  }
  return new Response(JSON.stringify({ versao: 1, amostras }), {
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=3600" },
  });
}
