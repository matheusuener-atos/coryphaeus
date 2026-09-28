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
| R6 | Túnel dentro do PAULUS | feita | branch `r6-tunel` | 29 checagens; token fora da linha de comando e do log; reinício; JWT (5 casos de recusa); porta ocupada; versão lida do cloudflared 2026.9.3 real |
| R7 | Instalador + assistente de conexão | feita | branch `r7-assistente` | 28 checagens; fluxo com Worker de mentira; assinatura: cloudflared real aceito, Python/Edge/falso recusados; tela do instalador fotografada |
| R8 | Auditoria "quem acessou" | feita | branch `r8-auditoria` | 9 ações de fora registradas; edição à mão acusada na linha certa; poda de 1 ano com âncora; PDF |
| R9 | Celular, energia, iniciar com o Windows | feita | branch `r9-celular` | 4 telas em 390 px pelo caminho de fora (sem rolagem lateral, 44 px de toque); 9/9 respostas em streaming com os cabeçalhos; energia e Run testados |
| R10 | Política, documentação, roteiro do teste real | textos feitos; ⏸ teste no 4G | branch `r10-politica` (docs) e `r10-politica-site` (site, fora do main) | política e termos com a seção nova; manual com solução de problemas; roteiro de 9 passos abaixo |
| I1 | Ajustes de inferência | feita | branch `i1-inferencia` | roteiro `--tudo` 40/41 antes e depois (a mesma de ausência falha nas duas); p50 documentos 8,5 s → 8,9 s; entrada p50 2.366 tokens; 0 cortes; mesma pergunta 2× = mesma resposta |
| I2 | Medição com documentos reais | ferramenta feita; ⏸ conjunto real | branch `i2-medicao` | demo (27 perguntas, 9 de continuação): 25/27 · p50 6,6 s · p95 39,3 s · entrada p50 2.362 · R@20 0,96 · R@6 0,96 · MRR@6 0,86 · no contexto 0,90 |
| I3 | Nível 0 por molde | feita | branch `i3-molde` | 5 factuais sem modelo, mediana 5 ms, sem fila; dígito trocado rejeitado; roteiro 40/41; demo 25/27, p50 6,2 s, p95 17,2 s |
| I4 | Memória da conversa | feita | branch `i4-memoria` | 9/9 continuações herdam o sujeito, 18/18 outras intactas; histórico ≤ 600 tokens; demo 26/27 (continuação 9/9, era 8/9); roteiro 40/41 |
| I5 | Chunking estrutural | feita | branch `i5-trechos` | ids estáveis (mesmo doc e reindexação); toda página; nenhuma seção cortada; roteiro 40/41 (mediana 8,8 s); demo 26/27, p50 9,2 s, R@6 0,95; suíte 71 ok |
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
- **R6** **Desvio do contrato, de propósito:** a porta fixa não é a porta da janela. É um segundo ouvinte uvicorn (mesmo app, `lifespan="off"`, também só em 127.0.0.1) aberto quando o acesso está ligado. Motivos: a conexão feita pelo assistente vale na hora, sem reiniciar o PAULUS para ele passar a escutar na porta nova; e a janela local nunca depende da porta fixa (o contrato já pedia que a janela abrisse "em outra porta como hoje" quando a fixa estivesse ocupada). Com a porta fixa ocupada, o túnel não liga.
- **R6** Versão mínima do `cloudflared`: 2025.4.0 (preferência `acesso_remoto.cloudflared_minimo`), a partir da qual o túnel gerenciado remotamente aceita o token por `TUNNEL_TOKEN`/`TUNNEL_TOKEN_FILE`.
- **R6** O conferidor do JWT só existe com `aud` e `team_domain` gravados (vêm do Worker na conexão). Sem eles, nenhuma requisição de fora passa — mesmo com o módulo ligado.
- **R7** Versão fixa do `cloudflared` no instalador: `VERSAO_CLOUDFLARED = "2026.9.3"` em `Instalador.cs` (quem publica atualiza a mão). A conferência de assinatura pode ser rodada sozinha: `PAULUS-instalador.exe /conferir-assinatura=<arquivo>` → código 0 se é da Cloudflare, 3 se não.
- **R7** A revogação do certificado não é consultada (`WTD_REVOKE_NONE`): pede rede e trava instalação offline; a cadeia até a raiz confiável continua conferida pelo Windows.
- **R7** O e-mail do titular no assistente é escolhido entre as contas de titular com autenticador confirmado — sem ela, o assistente leva até Contas em vez de conectar.
- **R7** A lista de e-mails do Access é a de todas as contas do PAULUS (até 10), sincronizada a cada criar/mudar/remover conta. Falha de rede na sincronização vira aviso na tela, não erro.
- **R7** Remover também encerra todas as sessões de fora.
- **R7** `--configurar-acesso` vira `#acesso` no endereço da janela, e a tela abre em Configurações › Acesso de fora.
- **R8** "Documento aberto" = ver o documento do editor, a página de um arquivo do Acervo e o trecho citado (`ROTAS_DE_VER_DOCUMENTO` em `politicas.py`); a mesma pessoa no mesmo documento vira uma linha a cada 10 min.
- **R8** O alvo é gravado pelo nome (documento, planilha, gravação, conversa, arquivo), resolvido na hora de anotar; o que não se traduz fica com o endereço.
- **R8** Retenção: a poda roda ao abrir o programa; o hash da última linha podada fica em `acessos.ancora`.
- **R9** Celular: as regras entram abaixo de 600 px (a janela do programa tem mínimo de 900). O trilho vira barra inferior rolável, sem o menu flutuante (que abre ao passar o mouse). Não refiz as telas uma a uma para o desenho M1–M16 de `docs/ui/04-telas-mobile.md`: as quatro telas do contrato ficaram usáveis; as outras seguem as regras gerais (tabela vira lista, cabeçalho quebra).
- **R9** O aviso de 403 ("Disponível só no computador do escritório") só aparece para pedidos que alteram algo; leituras de fundo que dão 403 ficam caladas.
- **R9** "Abrir o PAULUS com o Windows" só existe no programa instalado (o `PAULUS.exe` fica duas pastas acima de `app/src`); no código-fonte a opção aparece travada, com a frase.
- **Suíte** O worktree precisa dos exemplos de `data/test_contracts` (não versionados), copiados do repositório principal. `test_tela.py` sai às vezes com segfault (código 139) — acontece também no repositório principal, sem as mudanças desta rodada. A checagem "segurar numa conversa marca" é intermitente: medida em 3 rodadas seguidas na árvore desta rodada, falhou 1 e passou 2 (a lista de conversas abre animada em 460 ms e pode se redesenhar enquanto o teste segura a linha). `test_gravacoes.py` falha quando a máquina tem menos de ~1,9 GB livres para o modelo de voz — é a causa da falha da linha de base.
- **I1** A janela fixa de fábrica é 16384 (perfil `conversa` em `config/extratores.yaml`), como pede o contrato; `janela_para` saiu. A chave `ia.opcoes_fixas` desligada volta à temperatura 0,1 sem semente/teto/keep_alive — mas não traz de volta a janela que crescia com o acervo (ela era a causa das recargas).
- **I1** O teto de 700 tokens vale só para a pergunta sobre documentos (a habilidade `perguntar` manda `tarefa="conversa"`); editor, resumos e e-mail escrevem sem teto. JSON (ferramentas, folha) tem 800.
- **I1** A linha de base do roteiro nesta rodada foi 40/41, e não 41/41: a pergunta de ausência da multa do aluguel falhou com as opções antigas também. A régua é "não cair" em relação a 40/41.
- **I1** `perguntas.jsonl` guarda também a resposta pelo programa (`caminho: programa`) e a recusa por regra (`regra`); a pergunta parada no meio não entra (como no ritmo: leitura cortada não é medida).
- **I1** Um dicionário vazio no `PADRAO` passou a ser mapa livre em `_fundir` (senão `janela_por_modelo` perdia as chaves ao reabrir).
- **I2** Sem resposta à ⏸ PAUSA I2 (o usuário estava dormindo), segui como o contrato manda para "segue com a demo": o conjunto da demonstração com as perguntas de continuação. **Limitação:** todos os números das etapas I3–I9 abaixo são da demonstração (8 documentos, 9 trechos, cabe inteira na leitura) — a busca quase não é exercitada, e o Recall é teto.
- **I2** `tools/medir.py` não mudou nada do programa (só ferramenta, conjunto e documentação): não rodei o roteiro nem a suíte inteira de novo nesta etapa; `tests/test_i2_medir.py` confere as contas e que toda frase esperada existe na demo.
- **I2** "No contexto" mede nas fontes que a conversa mostrou; resposta sem fontes (a recusa por regra, 0 s) conta zero — por isso 0,90 e não 0,96.
- **I3** Molde só para o que o contrato lista (processo, valor, tribunal, partes, assinatura, leis). CPF/CNPJ e prazos seguem pelo modelo com a conferência mecânica. Tribunal: o molde responde só "qual o tribunal/juízo?"; vara, comarca e foro (o foro de eleição de um contrato) vão ao modelo.
- **I3** `ia.molde` desliga as duas coisas (molde e conferência). A pergunta que sai sem modelo não entra na fila: a conversa pergunta à habilidade (`sem_modelo`) antes de pegar a vez.
- **I3** A suíte teve o `test_tela` falhando uma vez em "segurar numa conversa marca" (intermitente, já visto antes da I3); rodado de novo isolado.
- **I4** A reescrita é por regra, nunca pelo modelo (custaria uma leitura a mais por pergunta). Quando a regra não reconhece a continuação, a pergunta segue como foi escrita — o histórico ainda vai junto.
- **I4** O nível 0 (fatos) não leva histórico: ele responde de fatos, e a conversa de antes só aumentaria o prompt.
- **I5** A versão do `chunk_id` é o sha1 do arquivo + o nome, e não o `version_id` da biblioteca (um ULID sorteado no registro): com o ULID, reindexar do zero mudaria todos os ids. Cópias iguais com nomes diferentes ganham ids próprios.
- **I5** Documento sem página (DOCX, TXT) fica com página vazia — o mesmo que o mapa de layout diz; inventar "p. 1" num .txt seria prometer uma página que ninguém acha. "Todo trecho tem página" vale para os documentos paginados.
- **I5** O material de consulta continua fatiado por página (src/material.py): é por página que ele cita, e ele está 5/5 no roteiro. O regime A vale para lei que estiver no Acervo.
- **I5** Três trechos inspecionados (dos 20 de cada regime impressos por `tests/test_i5_trechos.py --mostrar`):
  - B, cláusula longa em janelas: `[chunk_… p.2-3] Contrato ACME > CLÁUSULA 7ª - DA OBRIGAÇÃO NÚMERO 7 / no mês 57, com a assinatura do responsável. Item 58 da cláusula sétima…` — a janela continua dentro da cláusula 7 e atravessa a quebra de página.
  - B, cláusulas curtas juntas: `[chunk_… p.1-1] Contrato ACME > CLÁUSULA 2ª … + CLÁUSULA 3ª …` — duas inteiras, nenhuma cortada.
  - A, artigo com parágrafo e incisos: `[chunk_… ] Lei 99999 > Art. 3º / Art. 3º O teste número 3… § 1º O parágrafo do artigo 3… I - inciso primeiro…`.

## Pendente do usuário

(o que depende de painel, conta, teste no celular ou decisão de produto)

### ⏸ I2 — o conjunto real de perguntas

De 30 a 50 perguntas sobre 10 a 20 documentos do escritório, em
`data/medicao/conjunto-real.jsonl` (na pasta de dados; fora do git). Como
anotar, com exemplo: `docs/medicao.md` e `tools/demo/conjunto-demo.jsonl`.
Depois: `tools\medir.py --real --so-busca` (confere as frases, segundos) e
`tools\medir.py --real` (com o Ollama). Os números das etapas I3–I9 foram
medidos na demonstração até lá.

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
   - Policy: nome "Qualquer e-mail confirmado", Action **Allow**, Include → **Everyone** — quem pode conectar é decidido pelo Worker, que exige que o e-mail confirmado seja o do titular do pedido.
   - Login method: One-time PIN.
   - Depois de salvar, abra a aplicação e copie o **Application Audience (AUD) Tag**.
7. **Os segredos do Worker**, na pasta do repositório:

   ```text
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

### ⏸ R10 — o teste real, do celular em 4G (depois da pausa da R5)

Pré-requisitos: os passos da R5 feitos (painel, KV, segredos, `TUNEL_ATIVO`, push); o PAULUS desta versão instalado no computador do escritório **marcando "Acesso de fora pelo celular"** (ou com o `cloudflared` no PATH, como já está nesta máquina); o celular **fora do Wi-Fi do escritório**, no 4G.

1. **Conectar pelo assistente.** No computador: Configurações › Acesso de fora › Contas › *Criar a conta do titular* (leia o QR com o autenticador, guarde os códigos de recuperação). Depois, em Conectar: confira o nome e o e-mail, *Conectar*. No navegador que abrir, entre com o e-mail do titular (chega um código), confira o código `XXXX-XXXX` e *Confirmar*. **Esperado:** em até ~10 s o PAULUS mostra `https://<escritório>.paulus.ia.br` e "conectado".
2. **Abrir o endereço** no celular (4G). **Esperado:** a página da Cloudflare pedindo o e-mail.
3. **Passar pelo Access:** o e-mail do titular e o código que chega. **Esperado:** a tela "Entrar no PAULUS do escritório".
4. **Login + TOTP:** senha, depois o código do autenticador. **Esperado:** a tela inicial, com "De fora como <nome>" e *Sair* no alto e a barra de destinos embaixo.
5. **Perguntar sobre um documento** (anexe pelo "/" ou pergunte citando o nome). **Esperado:** "lendo…" e depois a resposta **aparecendo palavra a palavra**, não de uma vez. Se vier de uma vez só no fim, anote: é buffer no caminho.
6. **Tentar assinar:** abra Assinatura no menu. **Esperado:** a tela "Disponível só no computador do escritório". Tente também apagar um documento do Acervo: o aviso com a mesma frase.
7. **Baixar um documento** (Documentos › abra um › PDF ou DOCX). **Esperado:** o arquivo baixa. No computador: Configurações › Acesso de fora › Quem acessou — a linha "baixou “<nome>” (PDF)" com o seu e-mail, a hora e o IP do celular; e "registro íntegro".
8. **Desligar** no computador (Acesso de fora › Endereço › *Desligar*). **Esperado:** no celular, a próxima ação falha e, recarregando, a Cloudflare mostra erro de túnel (o endereço para de responder).
9. **Remover** (Acesso de fora › *Remover o acesso de fora*). **Esperado:** "acesso de fora removido"; recarregando no celular, o endereço não existe mais; no painel da Cloudflare, o túnel, o DNS e a aplicação do Access sumiram.

Para cada passo que não sair como o esperado: o número do passo, o que apareceu (print do celular ajuda) e as últimas linhas de `%LOCALAPPDATA%\PAULUS\dados\logs\tunel.log` do computador. Cada correção volta com teste.

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
