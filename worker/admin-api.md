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
  notas: [{id, quando, tipo: "mensalidade"|"recarga pix", cliente, doc, valor, nota: "pendente"|"emitida"|"cancelada"|"erro",
  numero, erro}]}`. `emissor.ligado` = existe `NFSE_CASA_TOKEN` (a ponte da casa, abaixo); o fato
  "Emissor" diz "PAULUS da casa · última conexão <data>", "PAULUS da casa · nunca conectou" ou
  "ponte desligada (falta NFSE_CASA_TOKEN)". O painel nao emite nota.
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
| `nfse.emitir` | `{ids: [id]}` | dono, financeiro - sempre falha com "a emissão é feita na tela \"Notas do PAVLVS\" do PAULUS da casa": o painel nao emite |
| `equipe.papel` | `{email, papel}` | dono |

Ver contas, tokens e receita, mandar e-mails e lembretes: todos os papeis.

## Ponte da NFS-e (PAULUS da casa)

Quem emite as NFS-e dos assinantes e o PAULUS da casa (tela "Notas do PAVLVS",
no servidor do dono). Codigo em `worker/nfse-casa.js`; teste em
`worker/teste-nfse-casa.mjs`.

- Prefixo `/api/nfse-casa/`, **fora** do Cloudflare Access (que cobre so `/admin*`
  e `/api/admin*`) e fora da sessao do GitHub.
- Porta: `Authorization: Bearer <NFSE_CASA_TOKEN>` (segredo do Worker:
  `npx wrangler secret put NFSE_CASA_TOKEN`; o mesmo valor vai na configuracao do
  PAULUS da casa). Comparacao em tempo constante. Sem o segredo no Worker: 503
  `{erro: "a ponte da NFS-e não está configurada (NFSE_CASA_TOKEN)"}`; token errado ou
  ausente: 401. Cada chamada valida grava `admin:nfse-casa:visto` = ISO de agora.

Rotas:

- `GET /api/nfse-casa/ping` -> `{ok: true, hora, contas: n}`.
- `GET /api/nfse-casa/clientes` -> `{clientes: [{id, nome, email, telefone, oab, plano: {id, nome, valor} | null,
  situacao: "ativa"|"cortesia"|"cancelada"|"vencida"|"pendente", ajustado: bool, tomador: {nome, documento,
  email, telefone, logradouro, numero, complemento, bairro, cep, cmun, uf, inscricao_municipal}}]}`.
  O `tomador` vem do cadastro da conta (nome_escritorio, documento so digitos, e-mail da conta
  Google, telefone) fundido com o ajuste em `nfse:tomador:<conta>` no KV; o ajuste vence.
- `POST /api/nfse-casa/clientes/:id` `{tomador: {...}}` -> o cliente (como acima). So os campos
  enviados mudam; `""` apaga o ajuste daquele campo (volta o do cadastro). Conferido:
  documento CPF/CNPJ com digito verificador, `cep` 8 digitos, `cmun` 7 digitos (IBGE), `uf`
  sigla valida, `email` com @, telefone com DDD; textos limpos e cortados. Erro: 400 `{erro}`;
  conta inexistente: 404. **Nao altera o cadastro original da conta** (o que o cliente
  preencheu em /cadastro): grava so o ajuste em `nfse:tomador:<conta>`.
- `GET /api/nfse-casa/pagamentos` -> `{pagamentos: [{id, conta, cliente, tipo: "mensalidade"|"recarga pix",
  valor, quando, nota: "pendente"|"emitida"|"cancelada"|"erro", numero}], config: {auto, email}}`, mais novos
  primeiro. `config` e a escolha do painel (Notas fiscais): emitir ao confirmar / mandar ao cliente.
- `POST /api/nfse-casa/notas` `{id, conta, pagamento?, numero, chave, competencia: "AAAA-MM", valor (reais),
  descricao, ambiente: "producao"|"producao_restrita", emitida_em, pdf_b64, xml_b64}` -> `{ok: true}`.
  `id` = id da nota na casa (`[A-Za-z0-9_.-]{1,64}`). A meta vai em `nfse:nota:<conta>:<id>`, o PDF em
  `nfse:nota-pdf:<conta>:<id>` e o XML em `nfse:nota-xml:<conta>:<id>` (base64). Cada arquivo ate 2 MB
  (senao 413). Com `pagamento`, marca `admin:nfse:<pagamento>` com `nota: "emitida"` e o `numero`.
  Reenviar o mesmo `id` substitui. Conta que nao existe: 404; campo invalido: 400.
- `POST /api/nfse-casa/notas/:id/cancelada` `{conta}` -> `{ok: true}`; marca `cancelada` na meta (e o
  pagamento ligado vira `nota: "cancelada"`). Nota inexistente: 404.

O PAULUS do cliente busca as proprias notas em `worker/ia.js`, com o segredo da
instalacao (`Authorization: Bearer pia_<conta>_...`, como as outras `/api/ia/*`):

- `GET /api/ia/nfse` -> `{notas: [{id, numero, competencia, valor, descricao, emitida_em, ambiente, cancelada}]}`
  so da conta autenticada.
- `GET /api/ia/nfse/:id/pdf` e `GET /api/ia/nfse/:id/xml` -> os bytes (`application/pdf` /
  `application/xml`, `Content-Disposition: attachment; filename="NFS-e <numero>.pdf"`); 404 se a nota
  nao for da conta ou nao tiver o arquivo.
