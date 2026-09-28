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
|---|---|---|
| `test_gravacoes.py` | `test_ao_vivo`: resposta vazia ao enviar o áudio com sessão ao vivo | pré-existente |
| `test_inteligencia_regressao.py` | "as 0 citações entregues existem literalmente" e "cada decisão virou uma linha de medida" | pré-existente |
| `test_planilha_excel.py` | nenhum: imprime "tudo certo" no lugar de "todos os testes passaram" | falso alarme do verificador; sai com código 0 |

## Etapas

| Id | Etapa | Estado | Commit | Portão / medidas |
|---|---|---|---|---|
| R1 | Chave da janela local | feita | branch `r1-chave-da-janela` | 363 rotas de `app.routes`, todas 403 sem chave; 23 checagens |
| R2 | Contas, senha, TOTP, sessões | pendente | | |
| R3 | Permissões por rota | pendente | | |
| R4 | Fila do modelo | pendente | | |
| R5 | Provisionamento no Worker | pendente | | |
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
- **Suíte** O worktree precisa dos exemplos de `data/test_contracts` (não versionados), copiados do repositório principal. `test_tela.py` sai às vezes com segfault (código 139) — acontece também no repositório principal, sem as mudanças desta rodada; a checagem "segurar numa conversa marca" falha por tempo às vezes.

## Pendente do usuário

(o que depende de painel, conta, teste no celular ou decisão de produto)
