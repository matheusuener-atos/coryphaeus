# PROGRESSO — A Biblioteca do escritório

Retomada do plano `prompt-biblioteca-v0.md` (M0…M7). Uma conversa nova, com o
mesmo prompt, continua da primeira etapa que não estiver `feita`.

| Etapa | O quê | Estado | Commit | Portão (medido) |
| --- | --- | --- | --- | --- |
| M0 | Levantamento + conjunto da biblioteca | feita | ver git log (m0) | base: R@6 0,581 · MRR@6 0,543 · ruído 0,375 · sinônimo 1/7 · acerto 32/44 · roteiro 41/41 |
| M1 | Material no pipeline híbrido (regime C) | feita | ver git log (m1) | R@6 0,839 · ruído 0,375 · sinônimo 4/7 · τ 0,625 · roteiro 40/41 (= controle) |
| M2 | Triagem, ficha e as leis que faltam | feita | ver git log (m2) | ruído 0,0 · 5 fichas, 0 campo errado · CDC em PDF = Planalto · 50 artigos sorteados conferem |
| M3 | Ponte doutrina ↔ lei (Código anotado) | feita | ver git log (m3) | 26 anotações conferidas à mão: 26 páginas certas, 0 código errado · dispositivo R@6 1,0 · roteiro 40/41 |
| M4 | Resposta em camadas | feita | ce4841d | R@6 0,903 (lei 1,0) · ruído 0,0 · 0 citação inventada · 0 doutrina como lei (6 atribuídas) · roteiro 40/41 (depois da correção do rótulo, ver abaixo) |
| M5 | Leitura em segundo plano (glossário e teses) | feita; chave desligada de fábrica | ce4841d | 3B: teses 28/30, conceitos 23/52, 62% no total (< 80%) · 0 frase fora do livro |
| M6 | Aviso de obra anterior à redação | feita | ce4841d | 30 artigos: alterado_em certo em 30 |
| M7 | O que o PAULUS sabe (tela e fora da cobertura) | feita | ce4841d | 5/5 fora com aviso; 0 aviso nas outras 39 (regra) |
| Pacote | `.paulus-material` local (Compartilhamento futuro) | feito | ce4841d | ida e volta: mesmos chunk_id e anotações |

## Antes e depois (as 44 perguntas, llama3.2:3b, nesta máquina)

Depois: os padrões de fábrica (híbrida, triagem, anotações, camadas,
defasagem, mapa e pacote ligados; leitura desligada), 30/09 04:09.

| Medida | Antes (M0) | Depois |
| --- | --- | --- |
| Recall@6 | 0,581 | **0,903** |
| MRR@6 | 0,543 | 0,718 |
| Ruído (material onde não devia) | 0,375 | **0,0** |
| Sinônimos achados | 1/7 | 4/7 |
| Acerto da resposta | 32/44 | 36/44 |
| "Não encontrei" indevido | 6 | 2 |
| Citação inventada | 0 | 0 |
| Doutrina dita como lei | — | 0 (6 atribuídas ao autor) |
| Aviso "fora do que a biblioteca cobre" | — | 5/5, 0 indevido |
| Aviso de obra anterior à redação | — | 3/3 (+1 fora do gabarito, correto: a Lei 14.181/2021 incluiu incisos no art. 4º do CDC) |
| Latência p50 / p95 | 15,6 s / 46,1 s | 14,3 s / 37,7 s |
| Roteiro `--tudo` | 41/41 | 40/41 (= controle: a árvore principal, sem nada disto, também dá 40/41 hoje) |

**A regressão que a medição final achou (e foi corrigida):** com as camadas
ligadas, o roteiro deu 39/41. "O percentual de êxito do contrato do João
Batista está dentro da tabela do escritório?" errou 3 vezes em 3 ("o
contrato não traz o percentual"), com o contrato e a tabela no contexto. A
única diferença para antes era o rótulo do manual: o bloco "MATERIAL DE
CONSULTA" das camadas era mais curto que o de antes ("…Ao usar, cite o
material e a página.") e a etiqueta de cada trecho tinha mudado. Agora o
material sem ficha vai ao modelo letra por letra como antes das camadas, sem
o título "DOCUMENTOS —" (novo teste em `tests/test_m4_camadas.py`). A
pergunta voltou a acertar, e o roteiro a 40/41.

O que continua errado (8 de 44):
- **5 sinônimos.** Em 3 a busca não acha a obra e traz a cláusula de um
  contrato do cliente (loja ou fábrica; perder um direito por não usar;
  agir contra o que fez antes). Em 1 o roteador pede "qual contrato?"
  (imprevisto que deixa o contrato caro). Em 1 a obra vem, mas o 3B não usa
  a palavra do livro (inadimplemento mínimo).
- **2 por dispositivo** (art. 26, § 3º, do CDC; art. 422 do CC): o trecho
  certo está entre os 6, e o 3B responde que não achou.
- **1 do manual** que o roteador manda para a Agenda por causa de
  "audiência" (ver "Fora do foco").

## Na sequência

Pedido do dono em 30/09/2026: logo depois da Biblioteca, o briefing
`docs/prompt-ideias-umbrel-v0.md` — levantamento, a tabela em
`docs/DECISAO-UMBREL.md` com até três ideias para fazer agora, e a
implementação. O dono pediu depois para seguir **direto, como na
Biblioteca** ("irei dormir, quando acordar quero o resultado pronto"): as
pausas do briefing não param. Em troca, a regra de quem implementa: nada que
faça conteúdo do escritório sair da máquina ou abra porta de rede nova vem
ligado de fábrica - fica atrás de chave desligada, ou para depois, com o motivo.

## Como este trabalho está sendo feito (30/09/2026)

- **Pedido do dono:** "siga em frente fazendo e implementando tudo… quando eu
  acordar quero tudo pronto, commitado e publicado, inclusive a parte do
  blog". Por isso as pausas do plano (⏸ M0) não param: a M0 seguiu pelo
  caminho previsto no prompt para "segue com a demo" (ver M0 abaixo).
- **Outra sessão trabalhava na mesma pasta** (`coryphaeus-db`, publicando a
  0.9.17 em `main`, com versao.py alterado e um stash). Para não misturar
  commits, este trabalho corre num worktree próprio,
  `C:\coryphaeus-biblioteca`, com as branches empilhadas (m1 sai da m0, e
  assim por diante). O merge em `main` é feito quando a outra sessão não
  estiver no meio de uma operação.
- **"A parte do blog":** lida como a seção "Compartilhamento futuro" do
  prompt (pacote `.paulus-material`, só o autor exporta, camada COMUNIDADE,
  texto importado é dado). O blog online (contas de autor, curadoria,
  moderação, publicação) o próprio prompt reserva para a frente futura; ver
  "Compartilhamento futuro" no fim.

## M0 — o prompt supõe × o código tem hoje

Lido em 30/09/2026, no commit 7d3c5fd.

| Item do prompt | O código tem hoje | Consequência |
| --- | --- | --- |
| §1.1 modelo `llama3.2:3b` em CPU | igual; o Ollama tem também `bge-m3`, `llama3.2:1b`, `llama3.2:3b-instruct-q8_0`, o ministral 3B e um Qwen 9B F16 | a conversa e a leitura (M5) medem com o 3B |
| §1.1 `habilidades/perguntar.py` | igual; o material entra por `CABECA_MATERIAL` depois dos documentos, com até min(2400, orçamento/3) caracteres | as camadas (M4) entram aqui |
| §1.1 `tools/demo/roteiro.py --tudo` e `tools/medir.py` | iguais: roteiro com 41 perguntas (16 básicas, 20 difíceis, 5 do manual); medir com `--real` e `--so-busca` | `--conjunto biblioteca` é acréscimo |
| §1.2 lembretes (`contextos.py`) | iguais: 600 por lembrete, 2400 no total, 4 gavetas (Regras de redação, Modelos, Clientes, Correções); entram como `ensinado` no fim da instrução | a camada REGRA DA CASA junta lembrete e manual |
| §1.2 material (`material.py`) | igual ao descrito: `chunk_document` (1.200 caracteres) por página, `ContractSearcher` BM25 em memória refeito ao abrir, `MIN_COBERTURA = 0.45`, `MIN_DA_MELHOR = 0.35`, regra dos nomes e das palavras de pergunta | M1 a fazer |
| §1.2 leis (`leis.py`) | CC, CPC, CP e CLT, do Planalto, artigo por artigo, com revogado marcado e `alterado_por` só da 1ª nota do caput. Nesta máquina os quatro estão instalados (10/09) | M2 acrescenta códigos; M6 precisa do ano de todas as notas |
| §1.2 `trechos.py` | regime A (artigo) e B (seção), `chunk_id` estável, `text_embed` com caminho; `fatiar` escolhe o regime sozinho (`regime_de`) | M1 acrescenta o regime C e a escolha do regime por fora |
| §1.2 `lexico.py` / `denso.py` | `IndiceLexico(caminho)` e `IndiceDenso(caminho)` já recebem o caminho; `Backfill` cede a vez por `ceder` | o material usa as classes sem mudar nada no Acervo |
| §1.2 `recuperacao.py` | RRF k=60, `minimo_rrf` = 1/(60+20), orçamento de 6 trechos; `reranquear` existe como parâmetro, mas **ninguém passa** (reranker continua fora) | a biblioteca usa a mesma RRF, sem reranker |
| §1.2 `citacoes.py` | contrato `[Tn]`; **`ia.citacao` vem desligada de fábrica** (decisão do dono na I8), "codigo" passou no portão | M4 põe as marcas em código só quando a biblioteca entra na resposta |
| §1.2 `alinhar.py` | `conferir(texto, citacao)` com limiar 0,92 | M3 e M5 conferem as quotes por ele |
| §1.2 `regras_leis.py` | já conhece CDC, CF, CTN, ECA, CPP, CTB (`INSTRUMENTOS`); não conhece a Lei do Inquilinato por sigla (só "Lei 8.245/1991") | M3 usa como está; M2 acrescenta "Lei do Inquilinato" por extenso |
| §1.5 `jobs.py` "tarefa de fundo" | `jobs.py` são os **trabalhos da conversa**, não uma fila de fundo. O que roda em segundo plano são fios (`threading`) que cedem a vez pela `fila_modelo` (o `Backfill` é o exemplo) | **Adaptação da M5:** a leitura é um fio no molde do `Backfill`, retomável por arquivo de estado |
| §1.2 tela da lei | não há "tela da lei" própria: há o painel "Citar a lei" do editor (`22-leis.js`) e o cartão "Códigos de lei" em Configurações › Modelos | **Adaptação da M3:** a seção "Na biblioteca do escritório" entra no cartão de cada artigo do painel e na tela Biblioteca (M7) |
| §1.2 tela de material | cartão "Material de consulta" em Configurações › Aprendizado (`35-material.js`) | M7 transforma a seção em Biblioteca |
| §1.3.1 material fora do pipeline novo | confirmado | M1 |
| §1.3.2 doutrina e sinônimo | confirmado: a busca densa só atende o Acervo | M1 |
| §1.3.3 CDC como material é cortado | confirmado: CDC não está em `leis.CODIGOS` | M2 |
| §1.3.4 sem ficha nem área | confirmado: o item guarda nome, arquivo, sha1, páginas, caracteres | M2 |
| §1.3.5 sem hierarquia de fonte | confirmado: um bloco único "MATERIAL DE CONSULTA" | M4 |
| §1.3.6 doutrina e lei não se ligam | confirmado | M3 |
| §1.3.7 tempo | confirmado: `alterado_por` guarda a 1ª nota do caput, sem ano | M6 |

**Situação das etapas:** M1–M7 **a fazer**. A M2 está **em parte** num ponto
só: o Código Civil já é importado do Planalto e é o modelo dos códigos novos.

## M0 — o conjunto da biblioteca

- **"segue com a demo"**: o dono foi dormir pedindo para seguir sem parar. O
  conjunto usa o material da demonstração (manual de rotinas), o CDC do
  Planalto (público) e **duas obras de doutrina fictícias** escritas aqui
  (Brandão, *Vícios do produto e do serviço*, 2ª ed., 2015; Teles, *Teoria
  geral dos contratos*, 2022), marcadas como fictícias na folha de rosto.
  **Limitação:** as perguntas e as obras foram escritas por quem escreveu o
  código; um conjunto com obras reais e perguntas do escritório pode dar
  números diferentes. Como montar um: `docs/medicao.md`, "O conjunto da
  Biblioteca".
- `tools/demo/biblioteca_demo.py` monta `data/demo-biblioteca` e escreve o
  conjunto (44 perguntas: 7 sinônimo, 6 dispositivo, 6 lei, 7 manual, 8 sem
  material, 5 fora, 5 temporal) em `data/medicao/conjunto-biblioteca.jsonl`.
  `--sem-triagem` refaz o estado da linha de base (tudo como material).
- O terceiro caso de `material.py` ("em quanto tempo devemos responder o
  e-mail") é um caso que **deve** trazer o manual: entrou em `manual`, não em
  `sem_material`.
- **Linha de base (30/09, 00:39–00:53):** Recall@6 0,581 · MRR@6 0,543 ·
  ruído 0,375 (3/8: o CDC como material aparecia na procuração da Dra.
  Helena, na multa do contrato e no reajuste do aluguel) · sinônimo 1/7 ·
  acerto 32/44 (dispositivo 3/6, lei 5/6, manual 6/7, sinônimo 1/7, temporal
  4/5, sem material 8/8, fora 5/5) · 6 "não encontrei" indevidos · 0 citação
  inventada · p50 15,6 s, p95 46,1 s. Roteiro `--tudo`: 41/41.

## M1 — o que foi medido e decidido

- Varredura da regra (τ de 0,45 a 0,70): τ = 0,625 → Recall@6 0,839, MRR@6
  0,707, ruído 0,375, sinônimo 4/7. Com τ 0,45 o Recall@6 ia a 0,903, mas o
  ruído a 0,75: a regra não deixa.
- Portão: Recall@6 ≥ 0,80 e acima da base ✓; ruído não maior ✓; sinônimo
  +3 ✓; ids estáveis, regime C, três casos, índices separados
  (`tests/test_m1_material.py`) ✓.
- **Roteiro:** 40/41 com a chave ligada (duas rodadas). A pergunta que cai
  ("qual a multa por atraso no aluguel da Clínica?") não recebe material em
  nenhum dos modos, e cai igual, com a mesma resposta, (a) com a chave
  desligada no worktree, (b) na árvore principal sem nenhuma mudança da
  Biblioteca, (c) com o bge-m3 descarregado. O 3B mudou a resposta dela entre
  a linha de base (00:1x) e as 01:xx. A referência passa a ser o controle:
  40/41.
- Orçamento: o material continua com min(2400, orçamento/3) na pergunta; a
  M4 reparte por camadas.
- **Adaptação:** o "limiar novo" é o cosseno τ da evidência densa; a
  evidência léxica continua sendo a cobertura de antes. O corte relativo (0,35
  do melhor) passou a ser sobre a nota RRF.

## M2 — o que foi medido e decidido

- Endereços conferidos no Planalto em 30/09/2026 (todos respondem 200):
  CDC `…/leis/l8078compilado.htm`; CF `…/constituicao/constituicaocompilado.htm`;
  CTN `…/leis/l5172compilado.htm`; ECA `…/leis/l8069compilado.htm`; Lei do
  Inquilinato `…/leis/l8245compilado.htm`. O CC continua em
  `…/leis/2002/l10406compilada.htm`.
- Contagens lidas: CC 2083 · CPC 1074 · CP 434 · CLT 1012 · CDC 130 · CF 424
  (276 do corpo + 148 do ADCT) · CTN 231 · ECA 329 · Inquilinato 91.
- **Decisão:** o que vem antes do primeiro Título só é descartado se a
  numeração recomeça depois dele (a CLT recomeça no art. 1º do corpo; o CTN
  segue no art. 2º). Sem sinal por código.
- **Decisão:** o CDC entregue em PDF quando o CDC do Planalto já está
  guardado não substitui o oficial: a tela diz que já está.
- **Decisão:** a ficha de uma lei que o PAULUS não conhece leva o aviso "lei
  guardada sem conferência de vigência".
- Fichas: 30 campos certos, 0 errados, nas 5 fichas de teste; as duas obras
  da demonstração saem com título, autor, edição, ano, editora, ISBN e áreas.
- Busca depois da M2: ruído 0,0 · fora com material 0/5 · dispositivo 0,83 ·
  temporal 1,0 · sinônimo 4/7 · lei 0,17 (esperado até a M4) · Recall@6 0,71.
- A conferência "10 artigos sorteados contra o Planalto" é o teste
  `test_codigos_novos`: o começo de cada artigo sorteado está no texto do
  Planalto logo depois do "Art. N", e o texto dele não engole o seguinte.

## M1 — a regra do limiar (escrita antes de medir o híbrido)

Um trecho do material entra na pergunta quando:

1. está entre os 20 primeiros da fusão RRF (léxico 50 + denso 50), isto é,
   passa o `recuperacao.minimo_rrf`;
2. **e** tem evidência de uma das duas buscas:
   - **léxica**: a cobertura de sempre (≥ 0,45 das palavras de assunto da
     pergunta, pelo menos 2 em comum, nome próprio conta no total e não
     casa);
   - **densa**: cosseno entre a pergunta e o trecho ≥ τ;
3. **e** tem pelo menos 0,35 da nota RRF do melhor trecho (o corte relativo
   de sempre);
4. a regra dos nomes continua: pergunta que é só nome próprio não consulta.

**Como τ é escolhido:** na grade 0,45; 0,475; …; 0,70, sobre o conjunto
inteiro, fica o τ que dá o **maior Recall@6 − ruído**, entre os que têm
ruído menor ou igual ao da linha de base. Empate: o τ maior (o mais
conservador). Nenhuma pergunta é olhada sozinha.

## M3 — o que foi medido e decidido

- **Adaptação:** não há "tela da lei" própria; a seção "Na biblioteca do
  escritório" entra no cartão de cada artigo do painel "Citar a lei" (os 5
  primeiros resultados) e, na M7, na tela Biblioteca.
- **Adaptação:** "30 anotações sorteadas de uma obra real" virou "todas as 26
  anotações das duas obras fictícias", conferidas por quem escreveu o código
  (gabarito em `tests/test_m3_anotacoes.py`). Com obras reais, conferir de
  novo.
- "abrir na página": o PDF do escritório abre num diálogo com o visor de PDF
  do programa (`/api/material/{id}/arquivo#page=N`).
- `regras_leis` passou a ler "art. 1.228" como 1.228 (antes, art. 1 sem
  código): sem isso, doutrina de Código Civil perdia as anotações dos artigos
  de quatro dígitos.
- **Limitação conhecida da regra de cobertura** (de antes, mantida): pergunta
  curta de documento de cliente pode casar com um trecho de obra por duas
  palavras ("comprador" ~ "compra" pelo radical de 6 letras, e "contrato").
  No conjunto o ruído medido é 0; não foi ajustada olhando uma pergunta só.

## Fora do foco

- **Roteador:** "quanto o escritório cobra para acompanhar uma audiência
  avulsa?" vai para a Agenda (programa) por causa de "audiência"; "quando um
  acontecimento imprevisto deixa o contrato caro demais, dá para desfazer?"
  vira o cartão "qual contrato?". As duas são do conjunto da Biblioteca e
  contam como erro nele.
- `tests/test_inteligencia_regressao.py` já falhava na árvore principal
  ("cada decisao virou uma linha de medida") antes deste trabalho.
- **A máquina ficou sem memória** às 01:30: um `svchost` com 16,8 GB
  privados e o CrossDeviceService com 5,4 GB. Testes que abrem janela
  (`test_tela`) deram `MemoryError` até na árvore principal. Descarregar o 3B
  e o bge-m3 do Ollama devolveu 3 GB.
- Os testes que leem os contratos reais de `data/test_contracts` (fora do
  git) só rodam no worktree com a pasta ligada (junção para a da árvore
  principal).

## Compartilhamento futuro

A curadoria, a moderação, as contas de autor e a publicação online são da
frente futura. Aqui entra só o pacote local.
