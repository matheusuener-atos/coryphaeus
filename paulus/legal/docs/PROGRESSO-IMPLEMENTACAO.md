# Progresso da implementação — Acesso de fora + Melhoria da IA

Contrato: `prompt-paulus-acesso-e-ia.md` (R1…R10, I1…I9). Este arquivo existe
para uma conversa nova retomar de onde a anterior parou: continue da primeira
etapa que não estiver `feita`.

## Como esta rodada foi conduzida (28/09/2026)

- O usuário pediu para trabalhar a noite inteira **sem parar nas ⏸ PAUSAS**:
  fazer tudo o que não depende dele e, no fim, listar o que ficou para ele
  decidir. As pausas viraram itens da seção "Pendente do usuário" abaixo.
- O trabalho roda num **git worktree** (`C:\coryphaeus-acesso`), com uma branch
  por etapa e `merge --ff-only` no `main` ao fim de cada uma. Motivo: havia
  outra sessão do Claude commitando no `main` na mesma hora (34ccf7a, e4357e3).
- Sem `git push` e sem chamar o agente `publicar`.
- Os testes rodam com o venv do repositório principal
  (`C:\coryphaeus\paulus\legal\venv`) e `PAULUS_MODELOS` apontando para os
  modelos de lá.

### Linha de base da suíte, antes da R1

56 de 59 passam. Três já falhavam antes de qualquer mudança desta rodada:

| Teste | O que falha | Situação |
| --- | --- | --- |
| `test_gravacoes.py` | `test_ao_vivo`: resposta vazia ao enviar o áudio com sessão ao vivo | pré-existente |
| `test_inteligencia_regressao.py` | "as 0 citações entregues existem literalmente" e "cada decisão virou uma linha de medida" | pré-existente |
| `test_planilha_excel.py` | nenhum: imprime "tudo certo" no lugar de "todos os testes passaram" | falso alarme do verificador; sai com código 0 |

## Etapas

| Id | Etapa | Estado | Commit | Portão / medidas |
| --- | --- | --- | --- | --- |
| R1 | Chave da janela local | feita | branch `r1-chave-da-janela` | 363 rotas de `app.routes`, todas 403 sem chave; 23 checagens |
| R2 | Contas, senha, TOTP, sessões | feita | branch `r2-contas` | 36 checagens; RFC 6238 confere; bloqueio 15→30 min; sessão 30 min/12 h; login remoto conferido em navegador (390 px) |
| R3 | Permissões por rota | feita | branch `r3-permissoes` | 376 rotas declaradas (114 permitido, 19 propor, 9 download, 1 titular, 10 público, 223 bloqueado); tabela testada com colaborador e titular |
| R4 | Fila do modelo | feita | branch `r4-fila-do-modelo` | 2 pessoas: nunca 2 respostas juntas, sem palavra trocada, ordem de chegada; 3ª da mesma pessoa 429; parar A e B termina |
| R5 | Provisionamento no Worker | código feito; ⏸ painel | branch `r5-worker-tunel` | `worker/teste-tunel.mjs`: 40 checagens (fluxo, JWT, desfazer, limites) |
| R6 | Túnel dentro do PAULUS | pendente | | |
| R7 | Instalador + assistente de conexão | pendente | | |
| R8 | Auditoria "quem acessou" | pendente | | |
| R9 | Celular, energia, iniciar com o Windows | pendente | | |
| R10 | Política, documentação, roteiro do teste real | pendente | | |
| I1 | Ajustes de inferência | pendente | | |
| I2 | Medição com documentos reais | pendente | | |
| I3 | Nível 0 por molde | pendente | | |
| I4 | Memória da conversa | pendente | | |
| I5 | Chunking estrutural | pendente | | |
| I6 | FTS5 com normalização jurídica | pendente | | |
| I7 | Denso + RRF + reranker, virada do "ler tudo" | pendente | | |
| I8 | Contrato de resposta `[Tn]` | pendente | | |
| I9 | A IA ajuda sem ser perguntada | pendente | | |

## Decisões tomadas

(uma linha por decisão, com a etapa)

- **R1** `/entrar-local` é tratado pelo porteiro e não é rota do app: assim é a única coisa alcançável sem chave, e o teste "todas as rotas de `app.routes` dão 403" continua sem exceção.
- **R1** O endereço com a chave vale uma vez por execução; o cabeçalho `X-PAULUS-Chave` vale sempre (clientes sem janela). Endereço vaza em histórico; cabeçalho não.
- **R1** O retorno OAuth (Google/Microsoft) não precisou de exceção: cai no servidor temporário de `correio_oauth.py`.
- **R1** Rota inexistente também dá 403 para quem é de fora (e não 404): nada se descobre por tentativa.
- **R2** O QR sai do reportlab (`reportlab.graphics.barcode.qr`), que já é dependência: nenhuma dependência nova.
- **R2** O e-mail do JWT do Access tem de ser o e-mail da conta do PAULUS, no login e em cada pedido. A lista do Access é montada a partir das contas (R7), então os dois coincidem por construção; se divergirem, nenhum vale.
- **R2** O código do autenticador vale uma vez só (o último passo usado fica gravado), inclusive dentro da janela de folga.
- **R2** O bloqueio conta por e-mail digitado, com ou sem conta, e o scrypt roda igual quando a conta não existe: sem oráculo de "este e-mail tem conta".
- **R2** Sessões ficam no SQLite (`data/acesso/contas.db`), só o hash: reiniciar o PAULUS não derruba quem está de fora.
- **R2** Rotas do acesso registradas direto no `app` (não `include_router`): esta versão do FastAPI embrulha o roteador incluído e as rotas somem de `app.routes`.
- **R2** Cookie `SameSite=Strict` não vai na navegação que volta do login do Cloudflare Access (outro site). A tela de entrar pergunta `/api/acesso/eu` e segue para o app se a sessão existir.
- **R3** Registro central (`src/acesso/politicas.py`) em vez de decorador nas 10 mil linhas do `api.py`: a tabela inteira cabe numa leitura; o teste falha se uma rota de `app.routes` não estiver nela.
- **R3** Política nova `propor` para "Agenda, tarefas, cadastros: ver e propor (tudo via fila)": o pedido de fora não grava; o porteiro guarda método, caminho e corpo num item da fila (`acesso.proposta`), responde 202, e o sim refaz o pedido pela janela local (conferindo de novo que a rota é das que se propõem). O `POST /api/trabalhos/{id}/fazer` (gravar o que a conversa entendeu: compromisso, tarefa, ficha) também é `propor`.
- **R3** Aprovar de fora: o titular não aprova de fora o que a tabela proíbe fazer de fora (`organizar.mover`, `acervo.apagar`, `acervo.exportar`, `assinatura.*`); `correio.enviar`, `google.drive.enviar` e proposta com sala do Meet pedem o código do autenticador de novo (vale para todos os itens daquela decisão).
- **R3** E-mail de fora vai sempre para a fila, mesmo com "enviar sem confirmar" ligado; senha de e-mail vinda de fora é 403.
- **R3** `GET /api/preferencias` é permitido de fora (a tela lê o nome e o tema); gravar preferências é bloqueado.
- **R3** A documentação automática do FastAPI (`/openapi.json`, `/api/docs`, `/redoc`) é bloqueada de fora: é o mapa da API.
- **R3** O 401 do porteiro vem com `X-PAULUS-Sessao: acabou`; só ele manda a tela de volta ao login (outras rotas usam 401 para "falta a senha do e-mail").
- **R4** A fila vale para a conversa do Assistente (`/api/trabalhos/{id}/perguntar`) e para a conversa de um Serviço (`/api/servicos/{id}/conversar`). Outras chamadas ao modelo (editor, e-mail, resumo) não entram: não são conversa, e o contrato fala da fila "para as chamadas de conversa".
- **R4** A vez é pega dentro do gerador da resposta, não na rota: se a página fechar antes de o streaming começar, nada fica preso. A 3ª pergunta é recusada na rota (429) antes de gravar a pergunta no histórico.
- **R4** Previsão = posição × mediana de (leitura + escrita) do `ritmo.json`, descontado o que a resposta em andamento já andou. Sem medida, só a posição.
- **R4** `ceder()` existe para o segundo plano; hoje a ingestão (camada de inteligência) só roda extratores de regra, sem modelo, então quem vai usar é o backfill de vetores da I7.
- **R5** Caminhos da API da Cloudflare usados (conferidos na documentação em 28/09/2026): `POST /accounts/{a}/cfd_tunnel` `{name, config_src:"cloudflare"}`; `PUT .../cfd_tunnel/{t}/configurations` `{config:{ingress:[{hostname, service, originRequest}, {service:"http_status:404"}]}}`; `GET .../cfd_tunnel/{t}/token` (result é a string); `GET .../cfd_tunnel/{t}` (`status`: inactive/degraded/healthy/down); `DELETE .../cfd_tunnel/{t}/connections` e depois `DELETE .../cfd_tunnel/{t}`; `POST /zones/{z}/dns_records` `{type:"CNAME", name, content:"<t>.cfargotunnel.com", proxied:true, ttl:1}`; `POST /accounts/{a}/access/policies` `{name, decision:"allow", include:[{email:{email}}]}` e `PUT` com o corpo inteiro; `POST /accounts/{a}/access/apps` `{name, domain, type:"self_hosted", session_duration:"12h", policies:[{id, precedence:1}]}` (devolve `aud`).
- **R5** JWT do Access: `Cf-Access-Jwt-Assertion`; chaves em `https://<time>.cloudflareaccess.com/cdn-cgi/access/certs` (escolhidas pelo `kid`; giram a cada 6 semanas); `aud` vem como lista; `iss` = `https://<time>.cloudflareaccess.com`.
- **R5** Limites do plano gratuito do Zero Trust (página account-limits, 28/09/2026): 500 aplicações Access, 1.000 regras por aplicação, 1.000 e-mails por regra, 1.000 túneis por conta. **Assentos: 50 usuários** (fonte secundária — a página de preços é montada por JS; conferir no painel). Passado o limite de assentos, logins novos são bloqueados. Esse limite é da conta do Atos, compartilhado por todos os escritórios: com até 10 e-mails por escritório, são ~5 escritórios cheios. `MAX_ESCRITORIOS` controla isso.
- **R5** Segredo a mais além dos do contrato: `ACCESS_AUD_CONECTAR` (o AUD da aplicação do Access que protege `/conectar`), sem o qual o Worker não confere o JWT daquela página.
- **R5** O KV `ESCRITORIOS` ficou **comentado** no `wrangler.jsonc`: declarar com id que não existe quebraria o deploy do site no próximo push. `/conectar` entrou no `run_worker_first`.
- **R5** O pedido "pronto" guarda no KV o token do túnel e o segredo até o PAULUS buscar (no máximo 15 min, TTL do KV); depois da entrega é apagado.
- **Suíte** O worktree precisa dos exemplos de `data/test_contracts` (não versionados), copiados do repositório principal. `test_tela.py` sai às vezes com segfault (código 139) — acontece também no repositório principal, sem as mudanças desta rodada; a checagem "segurar numa conversa marca" falha por tempo às vezes.

## Pendente do usuário

(o que depende de painel, conta, teste no celular ou decisão de produto)

### ⏸ R5 — o que fazer no painel da Cloudflare (só o dono da conta)

O código do Worker já está no repositório e **não liga nada** até o passo 7.

1. **Token de API.** Painel → My Profile → API Tokens → Create Token → Custom token. Permissões:
   - Account → **Cloudflare Tunnel** → Edit
   - Account → **Access: Apps and Policies** → Edit
   - Zone → **DNS** → Edit, com *Zone Resources* = Include → Specific zone → `paulus.ia.br`

   Guarde o token (aparece uma vez).
2. **Account ID e Zone ID.** Painel → `paulus.ia.br` → Overview: na coluna da direita, "Account ID" e "Zone ID".
3. **Team domain do Zero Trust.** Painel → Zero Trust → Settings → Custom Pages (ou Settings → General): o "Team domain" é `<algo>.cloudflareaccess.com`. Se ainda não houver, o Zero Trust pede para criar um time (plano Free) na primeira visita.
4. **Login por código no e-mail.** Zero Trust → Settings → Authentication → Login methods: confirme que **One-time PIN** está habilitado.
5. **O KV `ESCRITORIOS`.** Painel → Storage & Databases → Workers KV → Create → nome `ESCRITORIOS`. Copie o **ID** e, no `wrangler.jsonc`, descomente a linha `{ "binding": "ESCRITORIOS", "id": "..." }` colando o id.
6. **A aplicação do Access de `/conectar`.** Zero Trust → Access → Applications → Add an application → **Self-hosted**:
   - Application domain: `paulus.ia.br`, path `conectar`
   - Session duration: 15 min (basta para confirmar)
   - Policy: nome "Qualquer e-mail confirmado", Action **Allow**, Include → **Emails ending in** → `@` *(ou "Everyone")* — quem pode é decidido pelo Worker, que exige que o e-mail seja o do titular do pedido.
   - Login method: One-time PIN.
   - Depois de salvar, abra a aplicação e copie o **Application Audience (AUD) Tag**.
7. **Os segredos do Worker**, na pasta do repositório:
   ```
   npx wrangler secret put CF_API_TOKEN          (o token do passo 1)
   npx wrangler secret put CF_ACCOUNT_ID         (passo 2)
   npx wrangler secret put CF_ZONE_ID            (passo 2)
   npx wrangler secret put ACCESS_TEAM_DOMAIN    (passo 3, só o domínio: xxx.cloudflareaccess.com)
   npx wrangler secret put ACCESS_AUD_CONECTAR   (passo 6)
   npx wrangler secret put MAX_ESCRITORIOS       (sugestão: 5 — ver o limite de 50 usuários acima)
   npx wrangler secret put TUNEL_ATIVO           (1 — é o que liga as rotas)
   ```
8. **Push** do `main` (publica o Worker com o KV). Conferir: `https://paulus.ia.br/api/tunel/estado` com POST `{}` deve responder `{"estado":"expirado"}` (antes do passo 7, 404).
9. No painel, conferir que **nenhuma rota do Worker pega `*.paulus.ia.br`** (Workers & Pages → paulus → Settings → Domains & Routes: só `paulus.ia.br` e, se houver, `www`).

### R3 — rotas bloqueadas de fora por não se encaixarem com clareza na tabela

Estão em `BLOQUEADO`, no último grupo de `src/acesso/politicas.py`. Para
liberar alguma, basta mudar a linha dela de grupo (e o teste da R3 continua
exigindo que toda rota tenha política):

- **Financeiro inteiro** (`/api/financeiro/*`, 26 rotas): dinheiro não está na tabela; ver o extrato de fora pode ser útil, mas é decisão de produto.
- **Relatórios** (`/api/relatorios*`): somam financeiro e aprovações.
- **Foco e bem-estar** (`/api/bemestar*`): é da pessoa na frente do computador.
- **Serviços — gravar** (criar, etapas, anotações, vincular, prazos): ver e conversar sobre o serviço estão liberados.
- **Gravações — gravar e transcrever** (inclui gravar ao vivo pelo microfone do celular): ver a lista e ouvir/baixar estão liberados (download registrado).
- **Enviar arquivo** (`POST /api/upload`) e **trazer para o editor** (`POST /api/documentos/importar`, que aceita caminho do disco): o segundo, liberado, leria qualquer arquivo do computador pelo caminho.
- **Guardar documento do editor no Acervo** (`POST /api/documentos/{id}/biblioteca`) e **guardar anexo de e-mail no Acervo** (`POST /api/email/anexo/guardar`): gravam arquivo no disco.
- **Apoiar** (`/api/apoio/*`): pagamento.
