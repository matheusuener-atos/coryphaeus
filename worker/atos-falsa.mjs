// Para os testes: a Atos de mentira que entrega as NFS-e dos clientes ao PAVLVS (GET atos.dev.br/api/cobranca/v1/notas
// e .../notas/<id>/pdf|xml, com Bearer e ?produto=pavlvs&sub=), como C:\atos\worker\cobranca\api.js responde.
//   const atos = atosDasNotas("segredo");
//   atos.notas.set("sub-da-ana", [{ id, numero, competencia, valor, descricao, emitida_em, ambiente, cancelada, pdf, xml }]);
//   const r = atos.atender(url, init);   // Response, ou null se o pedido nao e para ela
export function atosDasNotas(segredo) {
  const notas = new Map();
  const pedidos = [];
  let fora = false;
  function atender(url, init = {}) {
    const u = new URL(String(url));
    if (u.origin !== "https://atos.dev.br" || !u.pathname.startsWith("/api/cobranca/v1/notas")) return null;
    pedidos.push(u.pathname + u.search);
    if (fora) return new Response("{}", { status: 503 });
    const auth = (init.headers && (init.headers.authorization || init.headers.Authorization)) || "";
    if (auth !== "Bearer " + segredo || u.searchParams.get("produto") !== "pavlvs") return new Response(JSON.stringify({ erro: "produto não autenticado" }), { status: 401 });
    const lista = notas.get(u.searchParams.get("sub") || "") || [];
    const m = /^\/api\/cobranca\/v1\/notas\/([^/]+)\/(pdf|xml)$/.exec(u.pathname);
    if (!m) return Response.json({ notas: lista.map(({ pdf, xml, ...meta }) => meta) });
    const n = lista.find((x) => x.id === m[1]);
    if (!n || !n[m[2]]) return new Response(JSON.stringify({ erro: "essa nota não existe" }), { status: 404 });
    return new Response(n[m[2]], { status: 200, headers: { "content-type": m[2] === "pdf" ? "application/pdf" : "application/xml" } });
  }
  return { notas, pedidos, atender, set fora(v) { fora = v; } };
}
