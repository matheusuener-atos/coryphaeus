# Painel admin do PAVLVS - o contrato das rotas

O painel mora em `site/admin/` (estatico) e fala com `worker/admin.js` por
`/api/admin/*`. Desenho: handoff "Painel Admin" (03/10/2026). Este arquivo e o
contrato entre a pagina e o Worker; quem mudar um lado muda o outro e este texto.

## Portas

1. **Cloudflare Access** na frente de `paulus.ia.br/admin*` e `paulus.ia.br/api/admin*`
   (politica: e-mail @paulus.ia.br, codigo de uso unico). O Worker confere o JWT
   `Cf-Access-Jwt-Assertion` em toda rota `/api/admin/*` (as chaves de
   `https://<ACCESS_TEAM>/cdn-cgi/access/certs`, `aud` = `ACCESS_AUD`). Sem
   `ACCESS_TEAM`/`ACCESS_AUD` configurados, o painel fica fechado (503).
2. **GitHub** (OAuth App "PAVLVS Admin", `GITHUB_CLIENT_ID` em vars,
   `GITHUB_CLIENT_SECRET` segredo): permissao `push` em
   `matheusuener-atos/coryphaeus`. A sessao (cookie `pv_admin`, HttpOnly,
   Secure, SameSite=Lax, 24 h) fica no KV `APOIOS` em `admin:sessao:<id>`.
3. O papel (`dono` | `financeiro` | `suporte`) vem de `ADMIN_EQUIPE` (JSON
   `[{email, nome, papel}]`) ou, depois de publicado, de `admin:equipe` no KV.

Toda resposta e JSON com `cache-control: no-store`. Erro: `{erro: "frase"}`
com o status. Sem a sessao do GitHub: 401 `{erro, passo: "github"}`; sem o
Access: 401 `{erro, passo: "access"}`; papel sem permissao: 403
`{erro: "o papel X nao pode ..."}`.

## Sessao

- `GET /api/admin/sessao` - nunca 401: `{access: {ok, email}, github: {ok, login},
  papel, nome, worker: "0.x", pronto: bool, config: {access, github, email, nfse,
  tuneis, mercado_pago, nuvem}}` (cada `config.x` = `{ligado: bool, falta: "frase"}`).
- `GET /api/admin/github/entrar` - 302 para o GitHub (state no KV, 10 min).
- `GET /api/admin/github/retorno?code&state` - confere o push e grava a sessao;
  302 para `/admin/` (ou `/admin/?erro=frase`).
- `POST /api/admin/sair` - apaga a sessao; a pagina vai depois a
  `/cdn-cgi/access/logout`.

## Leitura

Datas em ISO 8601 (UTC); dinheiro em reais (numero); tokens em unidades.

- `GET /api/admin/visao` -> `{agora, kpi: {receita_mes, receita_assinaturas, receita_recargas,
  custo_usd_mes, cambio, entrada_mes, saida_mes, contas, contas_ativas, escritorios, tokens_hoje},
  dias: [{dia: "AAAA-MM-DD", turno: 0|1|2, total, saida}] (42, do mais antigo ao mais novo),
  pendencias: [{icone, titulo, sub, tela, filtro?}],
  avisos: [{quando, tipo, texto, valor, tom: "entrada"|"recusado"|"cancelado"|"neutro"}]}`
- `GET /api/admin/contas` -> `{contas: [Conta], escritorios: [{nome, slug, documento,
  contas: [id], tokens_mes, receita_mes}]}` onde
  `Conta = {id, nome, email, escritorio: {nome, slug, documento}, oab, plano: {id, nome, valor, tokens},
  situacao: "ativa"|"vencida"|"cortesia"|"pendente"|"cancelada", restantes, usados, extra,
  ultimo_uso, google: {escopos: [], conferido} | null}`
- `GET /api/admin/contas/:id` -> `Conta + {criada, ciclo: {inicio, fim, tokens, usados} | null,
  cadastro: {documento, telefone, oab, termos, quando} | null, consentimento: {versao, quem, quando} | null,
  assinatura: {id, situacao, valor, desde} | null, plano_proximo, instalacoes: [{instalacao, hash8, criado}],
  pagamentos: [{tipo: "assinatura"|"recarga", valor, quando, ref}], recargas, google_pendente | null}`
- `GET /api/admin/tuneis` -> `{tuneis: [{slug, nome, responsavel, estado: "healthy"|"degraded"|"inactive"|"down"|"desativado",
  ultima_conexao, criado_em, tunnel_id, porta, ativo, limpeza: {dias, motivo} | null,
  historico: [{quando, texto}]}], livres: [slug], cf: {ligado, falta}}`
- `GET /api/admin/tuneis/disponivel?nome=` -> `{ok, motivo}` (as regras de `escritorio/index.html`)
- `GET /api/admin/renovacoes` -> `{abertas: [Renovacao], tratadas: [Renovacao], config: {email, resumo, whats, tol}}`
  onde `Renovacao = {id (da conta), nome, email, plano: {nome, valor}, fim, dias_vencido, tolerancia_dias (o total: 5 com a assinatura autorizada, 0 sem), motivo, lembrete_em}`
- `GET /api/admin/campanhas` -> `{campanhas: [{id, nome, situacao: "enviada"|"agendada"|"na fila"|"enviando"|"rascunho",
  publico: {id, label}, enviados, abertos, cliques, devolvidos, quando}], publicos: [{id, label, n, gmail}],
  stats: {enviados, abertura, cliques, devolvidos}, envio: {ligado, falta, de: "contato@paulus.ia.br", ritmo: 50}}`
- `GET /api/admin/cupons` -> `{cupons: [{codigo, descricao, desconto, meses, brinde, limite, usos, validade, planos: [id], ativo}]}`
- `GET /api/admin/tokens?visao=geral|escritorio|conta&periodo=mes|30|ano` ->
  `{kpis: {entrada, saida, custo_usd, receita, contas}, linhas: [{nome, entrada, saida, custo_usd, receita}],
  precos: {entrada, saida, cambio}}` (custo em US$; a pagina converte pelo cambio)
- `GET /api/admin/planos` -> `{planos: [{id, nome, valor, tokens, assinantes}], padrao: "escritorio",
  recarga: {valor, tokens}, precos: {entrada, saida, cambio}, json: "..."}`
- `GET /api/admin/materiais` -> `{materiais: [{id, slug, tipo: "artigo"|"modelo"|"tabela", titulo, areas, licenca,
  autor, oab, enviado, situacao: "fila"|"ajustes"|"publicado"|"recusado", palavras, texto, resumo,
  varredura: {cpf, cnpj, processo, nomes}}]}`
- `GET /api/admin/nfse` -> `{config: {auto, email}, emissor: {ligado, falta}, fatos: [{k, v}],
  notas: [{id, quando, tipo: "mensalidade"|"recarga pix", cliente, doc, valor, nota: "pendente"|"emitida"|"erro",
  numero, erro}]}`
- `GET /api/admin/equipe` -> `{membros: [{email, nome, papel, ultimo}], matriz: [{acao, dono, financeiro, suporte}]}`
- `GET /api/admin/busca?q=` -> `{contas: [...], escritorios: [...], tuneis: [...], cupons: [...], planos: [...],
  materiais: [...]}` (ate 6 por grupo; cada item `{titulo, desc, tela, alvo}`)
- `GET /api/admin/alteracoes` -> `{pendentes: [Alteracao], publicacoes: [{quando, commit, resumo, n, por}]}`
  onde `Alteracao = {id, quando, tela, tipo, alvo, dados, texto}`

## Na hora (sem passar pela fila)

Comunicacao e marcacao, que nao mudam o que esta no ar:

- `POST /api/admin/tuneis/:slug/avisar` -> e-mail ao responsavel com o prazo da limpeza
- `POST /api/admin/renovacoes/:id/lembrete` -> e-mail "seu plano nao renovou"
- `POST /api/admin/renovacoes/:id/tratar` / `.../reabrir`
- `POST /api/admin/renovacoes/config` `{email, resumo, whats, tol}`
- `POST /api/admin/campanhas/teste` `{campanha}` -> um e-mail de teste para quem esta na sessao
- Sem o provedor de e-mail (`RESEND_API_KEY`), essas rotas respondem 503
  `{erro: "o envio de e-mail ainda nao esta ligado: falta RESEND_API_KEY"}`.

## A fila (Confirmar alteracoes)

Tudo o que muda o que esta no ar entra na fila da sessao e so acontece em "Commitar e pushar":

- `POST /api/admin/alteracoes` `{tela, tipo, alvo, dados, texto}` -> `{pendentes}`.
  `texto` e a frase no passado que a lista mostra ("Apaguei moura-associados").
- `DELETE /api/admin/alteracoes/:id` -> `{pendentes}`
- `POST /api/admin/publicar` `{confirmacao: "comitar e pushar"}` ->
  `{ok, resultados: [{id, ok, erro}], publicacao: {quando, commit, resumo, n, por}}`.
  Aplica em ordem; uma que falha nao desfaz as outras, e volta com o motivo.

Tipos (`tipo` -> `dados`), e o papel que pode:

| tipo | dados | papel |
| --- | --- | --- |
| `conta.creditar` | `{id, tokens}` | dono, financeiro |
| `conta.instalacao.apagar` | `{id, hash8}` | dono, suporte |
| `conta.cancelar` | `{id}` | dono, financeiro |
| `google.servicos` | `{id, ligados: [escopo]}` | dono, suporte |
| `google.desvincular` | `{id}` | dono, suporte |
| `tunel.apagar` | `{slug}` | dono, suporte |
| `tunel.endereco` | `{slug, novo}` | dono, suporte |
| `tunel.ativo` | `{slug, ativo}` | dono, suporte |
| `campanha.disparar` | `{nome, publico, assunto, pre, titulo, texto, botao, link, quando: "agora"|"amanha"|"segunda"}` | todos |
| `cupom.criar` | `{codigo, desconto, meses, brinde, limite, planos, validade}` | dono, financeiro |
| `cupom.ativo` | `{codigo, ativo}` | dono, financeiro |
| `plano.editar` | `{id, valor, tokens}` | dono, financeiro |
| `plano.criar` | `{id, nome, valor, tokens}` | dono, financeiro |
| `material.situacao` | `{id, situacao: "publicado"|"ajustes"|"recusado", recado}` | todos |
| `nfse.config` | `{auto, email}` | dono, financeiro |
| `nfse.emitir` | `{ids: [id]}` | dono, financeiro |
| `equipe.papel` | `{email, papel}` | dono |

Ver contas, tokens e receita, mandar e-mails e lembretes: todos os papeis.
