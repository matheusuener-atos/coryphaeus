# Levantamento Técnico — Coryphaeus / PAULUS Legal
> Gerado em 2026-09-14 · commit `968d39f` · branch `main`
>
> O repositório recebeu commits durante o levantamento (`c4df1b1` → `cfb1251` → `968d39f`, entre 00:04 e 00:30). Todos tocam só `frontend/css/{01,02,03,05}-*.css`, `frontend/js/01-conversas.js`, `frontend/js/02-casca.js` e `tests/test_tela.py` (`git diff --stat c4df1b1 968d39f`); nenhuma linha de `src/`, `habilidades/`, `config/` ou `frontend/js/03-assistente.js` mudou, então as citações de backend valem para `968d39f`. A suíte foi executada sobre uma cópia tirada por volta de 00:22 (`cfb1251` + edições de frontend ainda não commitadas).

Convenções deste documento: `caminho:linha` é relativo a `paulus/legal/` salvo quando começa pela raiz do repo. **IMPLEMENTADO** = lógica real presente; **ESQUELETO** = arquivo/assinatura/declaração existe, mas sem efeito real; **AUSENTE** = não existe. "Hipótese" marca o que não foi possível confirmar no código.

---

## 1. Sumário executivo

O repositório é, na prática, **um único produto**: o PAULUS Legal, um aplicativo desktop Windows local (FastAPI + pywebview + ~18 mil linhas de JS sem build) que faz chat sobre documentos jurídicos com Llama 3.2 3B via Ollama, busca BM25 e mais ~15 módulos de escritório (agenda, financeiro, e-mail, assinatura PAdES, gravação com Whisper local). "Coryphaeus" existe só como README na raiz — não há código de orquestração. A camada `legal-document/v0` foi escrita inteira em 13/09/2026 (commits `6e16ac1`→`2febd3e`), com nomes em português (`src/inteligencia/`), e **cobre em código os 7 passos do roadmap**. A suíte (27 arquivos-script, sem pytest) passa. As três coisas mais importantes que este levantamento encontrou:

1. **No nível 0, a resposta final ao usuário é texto livre do LLM, sem conferência mecânica contra os fatos verificados** (`habilidades/perguntar.py:182-212`). A camada verifica a citação na entrada, mas o modelo pode trocar um número, reescrever o CNJ ou responder "não consta" — e isso sai como resposta. Soma-se a isso que o *rótulo* do fato (valor "da causa", data "de assinatura") é heurística de proximidade gravada como `explicit`/`verified` (`extratores/base.py:101-108`, `regras_valores.py:63`).
2. **Determinismo e registry são parcialmente decorativos**: `temperature: 0` e `seed: 42` do `config/extratores.yaml` nunca chegam ao Ollama — o cliente usa `temperature=0.1` e não envia seed (`src/llama_client.py:101,126`); o `id` de modelo do YAML não escolhe o modelo. Sem isso, a promessa "medir se a troca de modelo melhorou" não se sustenta.
3. **Dados reais de cliente estão versionados**: um CPF com dígito verificador válido e nomes de partes do acervo real em `tests/test_inteligencia_regressao.py:77-126` (commit `2febd3e`). O `main` local está **114 commits à frente de `origin/main`** — ainda não foi enviado, o que torna a correção barata agora e cara depois do próximo `git push` (e significa também que quase todo o trabalho não tem cópia fora desta máquina).

---

## 2. Inventário técnico

### 2.1 Escopo do repositório

| Caminho | O que é | Código? |
|---|---|---|
| `/README.md` | Posiciona ATOS → CORYPHAEUS → PAULUS → legal | Não. **Não existe código "Coryphaeus"** (engine/Agent OS) em lugar nenhum |
| `/paulus/README.md` | Índice do produto | Não |
| `/paulus/legal/` | O produto inteiro: backend, frontend, testes, docs, mockups | Sim — todo o código |
| `/paulus/legal/docs/ui/` | 8 docs + 37 mockups `.dc.html` do redesenho | Documentação de intenção |
| `/paulus/legal/data/` | Estado de runtime da máquina (SQLite, acervo real, biblioteca de metadata, gravações, sessão de WhatsApp) | Gitignored, exceto `data/samples/` e `.gitkeep` |
| `/paulus/legal/venv/` | Ambiente Python 3.14.3 local | Gitignored |

Não há `.github/`, `Dockerfile*`, `docker-compose*`, `pyproject.toml`, `setup.py`, `pytest.ini`, `conftest.py`, `package.json` nem `.env.example` em lugar nenhum do repositório (busca em profundidade 4, excluindo `venv/`).

### 2.2 Tamanho e ritmo

| Medida | Valor |
|---|---|
| Arquivos versionados | 239 (em `paulus/legal`) |
| Python — `src/` (sem a camada) | 23.073 linhas |
| Python — `src/inteligencia/` | 5.611 linhas |
| Python — `habilidades/` | 569 linhas |
| Python — `tests/` | 11.496 linhas (2.147 só da camada) |
| JavaScript — `frontend/js/` (25 arquivos) | 17.966 linhas |
| CSS — `frontend/css/` (23 arquivos) | 4.397 linhas |
| Markdown versionado | 3.304 linhas |
| Mockups `.dc.html` | 3.927 linhas |
| Maior arquivo | `src/api.py` — 6.133 linhas, **253 rotas** `@app.*` |
| Commits | 117, de 2026-09-09 a 2026-09-14 (9 / 24 / 19 / 36 / 26 / 3 por dia) |
| Autores | um só autor humano (`git shortlog -sn`: "Matheus Uener Silva" e "matheusuener-atos", este com 1 commit) |
| Horário | 72 dos 117 commits entre 20h e 05h |
| Sincronia | `main` 114 commits à frente de `origin/main`, que tem 3 (GitHub, repo **privado**) |

### 2.3 Stack real vs. documentada

| Item | Documentação diz | Código/ambiente mostra |
|---|---|---|
| Python | "3.10+" (`CONTRIBUTING.md:47`) | venv em **3.14.3**; nada foi verificado em 3.10 (hipótese: pode funcionar, não testado) |
| Dependências | `requirements.txt`, todas com `>=` | **Nenhuma versão travada, nenhum lock**. Instalado: fastapi 0.141.1, uvicorn 0.52.4, pypdf 6.18.0, reportlab 5.0.1, cryptography 50.0.1, pyHanko 0.37.0, faster-whisper 1.2.1 |
| PyYAML | não listado | **usado** em `src/inteligencia/catalogo.py:79` (import fora do `try`). Só está no venv como dependência transitiva (hipótese forte: via `huggingface_hub` ← `faster-whisper`) |
| Playwright | comentado em `requirements.txt` | instalado (1.62.0) e usado por `tests/test_tela.py` |
| LLM | "Llama local via Ollama" | `llama3.2:3b` por padrão (`src/llama_client.py:17`); na máquina também há `llama3.2:3b-instruct-q8_0` e `alibayram/ministral-3b-instruct` (saída de `ollama list`) |
| Temperatura | "0.1" (`docs/ARCHITECTURE.md:238`) **e** "0" (`config/extratores.yaml:24-45`) | `0.1` em toda chamada (`src/llama_client.py:101,126`); o valor do YAML não é aplicado |
| Busca | BM25 | `rank-bm25` em `src/search.py` (único import) |
| Registro de habilidades | `src/habilidades.py` (`CONTRIBUTING.md:39`, `ARCHITECTURE.md:55,228`) | **não existe**; é `src/registro.py` + pasta `habilidades/` |
| Vencimentos → Excel | `src/extract_expiring.py` (`ARCHITECTURE.md:258`) | **não existe**; `habilidades/vencimentos.py:15` está `EM_BREVE` |
| Chave de desligar a camada | `INTELIGENCIA=0` (`src/inteligencia/__init__.py:19`) | **não existe variável de ambiente**; a chave é `"inteligencia"` em `data/preferencias.json` (`src/config.py:86`) |
| Interface | abas "Análise"/"Busca" (`docs/QUICKSTART.md:57-58`) | desenho novo com trilho e destinos (`frontend/js/08-destinos.js`); QUICKSTART desatualizado |

### 2.4 Pontos de entrada

| Comando | Arquivo | O que faz |
|---|---|---|
| `venv\Scripts\python.exe src\desktop.py` | `src/desktop.py:261` | Sobe uvicorn em thread (127.0.0.1, porta livre — `desktop.py:178-219`) e abre janela pywebview |
| `python src/api.py [--contracts --model --port]` | `src/api.py:6112-6133` | Servidor FastAPI em `127.0.0.1:8000` |
| `python src/main.py [--contracts --model --top --ask --reindex --no-stream]` | `src/main.py:189-221` | Chat de terminal. **Não usa a camada de inteligência** (nenhum import de `inteligencia` em `main.py`) |
| `python -m inteligencia.retomar [--pasta --secoes --limite --forcar --assistente --sidecar]` (de dentro de `src/`) | `src/inteligencia/retomar.py:90-170` | Backfill da biblioteca de metadata. Único caminho em que extratores de modelo rodam |
| `python src/transcricao.py baixar` | `src/transcricao.py:276` | Baixa modelo Whisper para `data/modelos/whisper` |
| `python tests/test_*.py` | 27 arquivos | Testes como scripts com `checar()` próprio; não há runner |

### 2.5 Mapa de módulos

**Núcleo de documentos e conversa**

| Arquivo | Linhas | Função |
|---|---|---|
| `src/api.py` | 6133 | Backend FastAPI: objeto global `Estado` (`api.py:148-301`), 253 rotas, SSE da pergunta (`api.py:1512`) |
| `src/desktop.py` | 262 | Janela pywebview + seletor de pasta nativo |
| `src/main.py` | 222 | CLI de chat (sem a camada) |
| `src/extract.py` | 233 | PDF/DOCX/TXT/MD → texto, marca `[pagina N]` (`extract.py:97-100`), cache por SHA-1 |
| `src/search.py` | 378 | Chunking, tokenização pt-BR, BM25, montagem de contexto |
| `src/llama_client.py` | 335 | HTTP com Ollama, prompts de sistema, streaming, `ask_json`, `digest()` |
| `src/intencao.py` | 747 | Classifica o pedido (pergunta vs. ação: agenda, serviço, abrir) por regra |
| `src/habilidade_base.py` | 209 | Contrato de habilidade e `Contexto` (inclui `saber`) |
| `src/registro.py` | 156 | Carrega `habilidades/*.py` |
| `src/jobs.py` | 333 | Conversas persistidas em `data/trabalhos/*.json` (guarda `nivel` e `inferencia` por mensagem, `jobs.py:57`) |
| `src/citacao.py` | 217 | Mostra o trecho citado na página do documento |
| `src/leitor_pdf.py` | 68 | Porta única para PDFium |
| `src/classify.py` | 529 | Tipo/partes/data/valor por regra, modelo no resíduo (usado pelo Organizador e pelo `llm_classificador`) |
| `src/scan.py` / `src/organize.py` / `src/pastas.py` | 219 / 391 / 146 | Varredura de disco, plano+diário+desfazer de movimentação, navegação de pastas |
| `src/acervo.py` | 346 | Marcas da biblioteca (fixar, etc.) |
| `src/ritmo.py` | 132 | Mede caracteres/s desta máquina para prever espera |
| `src/contextos.py` | 150 | "Ensinar o assistente": texto que entra no fim do prompt de sistema |
| `src/leis.py` | 566 | Códigos (CC, CPC…) em base local |
| `src/redacao.py` / `src/documento.py` / `src/planilha.py` | 348 / 1473 / 1164 | Editor jurídico, DOCX/PDF, planilha |

**Módulos de escritório** (fora do escopo da camada): `agenda.py` 274, `tarefas.py` 315, `cadastros.py` 241, `financeiro.py` 504, `extrato.py` 384 (OFX/CSV + conciliação), `escritorio.py` 563 (folha, notas, boletos), `relatorios.py` 362, `bemestar.py` 399, `aprovacoes.py` 200, `servicos.py` 318, `gravacoes.py` 298, `transcricao.py` 298 (faster-whisper), `certificado.py` 548 + `assinatura.py` 649 (PAdES), `correio.py` 810 + `correio_contas.py` 406 (IMAP/SMTP), `segredos.py` 90, `conexoes.py` 206, `lixeira.py` 187, `marca.py` 147, `destinos.py` 162, `recursos.py` 170, `config.py` 174, `base.py` 611 (SQLite + 19 migrações).

**Habilidades** (`habilidades/`): `perguntar.py` 313 (integra a camada), `abrir.py`, `buscar.py`, `classificar.py`, `organizar.py` — ativas; `assinar.py`, `ocr.py`, `redigir.py`, `vencimentos.py` — `EM_BREVE` (declaração sem ação).

**Camada `legal-document/v0`** (`src/inteligencia/`)

| Arquivo | Linhas | Corresponde na spec a | Função |
|---|---|---|---|
| `__init__.py` | 38 | — | Docstring + `VERSAO_ESQUEMA` |
| `esquema.py` | 390 | `schema.py` | `Fonte`, `Item`, `Secao`, `Metadata`, `problemas()` |
| `texto.py` | 180 | `text.py` | Mapa de páginas a partir de `[pagina N]`, normalização com mapa de volta |
| `guarda.py` | 473 | `store.py` | `Biblioteca`: registro/identidade, disco, espelho SQLite, `desatualizadas`, `envelhecer` |
| `alinhar.py` | 283 | `align.py` | Conferência de citação: exata → caixa → acento → fuzzy ancorado com trava de dígitos |
| `catalogo.py` | 160 | `registry.py` | Lê `config/extratores.yaml` |
| `roteador.py` | 837 | `router.py` | Classificação de intenção por regex, níveis 0–4, `Pacote`, prompts de nível 0/1 |
| `portas.py` | 298 | `api.py` | `analisar_documento` (hook 1), `Saber.montar_contexto` (hook 2), `fontes_da_resposta` (hook 3) |
| `retomar.py` | 170 | `backfill.py` | CLI de backfill |
| `extratores/base.py` | 191 | — | `Pedido`, `Resultado`, `item_do_span`, `escolher_kind` |
| `extratores/regras_processo.py` | 143 | `rules_case_number.py` | CNJ + DV mod 97 |
| `extratores/regras_datas.py` / `regras_valores.py` / `regras_leis.py` / `regras_juizo.py` | 122 / 85 / 187 / 122 | `rules_dates/amounts/...` | Regras nível 0 |
| `extratores/regras_{pedidos,decisoes,eventos,provas,teses,relacoes,pessoas,organizacoes}.py` + `frases.py`, `entidades.py` | — | coleções do passo 7 | Regras nível 0 das extensões; CPF/CNPJ com DV |
| `extratores/llm_classificador.py` | 122 | nível 1 | Tipo por vocabulário → nome do arquivo → modelo |
| `extratores/llm_partes.py` / `llm_resumo.py` | 161 / 75 | nível 2 | Partes e resumo por modelo |
| `extratores/verificador.py` | 99 | `extractors/verifier.py` | Conferidor SIM/NÃO por modelo |

### 2.6 Fluxo de dados de ponta a ponta (o que o código percorre hoje)

**Ingestão** (ao abrir o programa e a cada reindexação):

```
desktop.py / api.py  ──lifespan──▶ Estado.recarregar()                      api.py:263
                                     │
                                     ├─▶ extract.index_all_contracts()      extract.py:166
                                     │     pypdf / python-docx; "[pagina N]" por página com texto
                                     │     cache SHA-1 em data/extractions/index.json
                                     │     PDF sem texto (escaneado) → descartado em silêncio
                                     │
                                     ├─▶ search.ContractSearcher.build()    BM25 em memória
                                     │
                                     └─▶ analisar_em_segundo_plano(docs)    api.py:284  (thread, SEM client)
                                           └─▶ portas.analisar_documento()  portas.py:44
                                                 ├─▶ Biblioteca.registrar()          guarda.py:126
                                                 │     sha256 do arquivo → meta_versoes (SQLite)
                                                 │     data/conhecimento/documents/<doc>/versions/<ver>/
                                                 │        extracted/text.txt, layout.json, source.link
                                                 ├─▶ Biblioteca.desatualizadas()      guarda.py:390
                                                 ├─▶ para cada seção: catalogo.para_secao() → modulo.extrair(Pedido)
                                                 │     regra: item nasce verified=True  (base.py:101-108)
                                                 │     modelo sem client → seção "missing" (portas.py:77-83)
                                                 │     itens sem span → alinhar.verificar_todos + verificador
                                                 └─▶ Biblioteca.gravar()              guarda.py:275
                                                       metadata.json (atômico) + analysis-history.jsonl
                                                       + meta_secoes / meta_fatos (SQLite)
```

**Pergunta**:

```
frontend/js/03-assistente.js ──POST SSE──▶ /api/trabalhos/{id}/perguntar         api.py:1512
                                            intencao.ler() / _escopo_da_pergunta (ação? foco?)
                                            └─▶ habilidades/perguntar.executar()   perguntar.py:54
                                                  │
                                                  ├─▶ Saber.montar_contexto()       portas.py:227
                                                  │     metados_de(): sha1 → meta_versoes → metadata.json (JSON, não meta_fatos)
                                                  │     roteador.resolver()           roteador.py:421
                                                  │       classificar() por regex → nível 0 / 1 / (3|4 via _pelo_filtro) / 2
                                                  │
                                                  ├── responde_sozinho (nível 0/1)
                                                  │     _responder_do_que_ja_se_sabe()  perguntar.py:156
                                                  │       prompt de fatos → client.ask (não-stream, temp 0.1)
                                                  │       resposta começa com "ESCALAR"? → cai para o caminho de sempre
                                                  │       senão: resposta do LLM emitida como está  ◀── sem checagem contra os fatos
                                                  │
                                                  ├── estreita (nível 3/4): restringe `apenas` aos documentos do recorte
                                                  │
                                                  └── caminho de sempre (nível 2)
                                                        cabe inteiro? searcher.tudo() : searcher.search(BM25)
                                                        format_context → client.ask(stream) → tokens SSE
                                            api.py:1666-1669 grava mensagem (nivel, inferencia) em data/trabalhos/*.json
frontend: evento "fontes" desenha trechos (03-assistente.js:414-432) — ignora `inferencia`
```

### 2.7 Persistência

| Onde | Formato | Conteúdo | Migração |
|---|---|---|---|
| `data/paulus.db` (+WAL) | SQLite, conexão única com trava (`base.py`) | cadastros, tarefas, agenda, documentos, financeiro, leis, serviços, gravações, lixeira, contextos, **meta_documentos/meta_versoes/meta_secoes/meta_fatos** | 19 migrações numeradas aplicadas em ordem (`base.py:25-540`, loop em `base.py:572`); sem *down* |
| `data/conhecimento/documents/<doc>/document.json` + `versions/<ver>/{metadata.json, analysis-history.jsonl, source.link, extracted/text.txt, extracted/layout.json}` | JSON/JSONL/texto | A biblioteca `legal-document/v0` | **Nenhuma migração de metadata JSON**; `schema_version` fixo `"v0"` em `portas.py:132` e `guarda.py:416` |
| `data/extractions/index.json`, `classificacao.json` | JSON | Cache de texto extraído (SHA-1) e de classificação | versão por constante (`VERSAO_CLASSIFICADOR`, segundo `ARCHITECTURE.md:206-209`) |
| `data/trabalhos/*.json` | JSON | Conversas, com `nivel` e `inferencia` por resposta | — |
| `data/preferencias.json`, `aprovacoes.json`, `ritmo.json`, `contas_email.json`, `certificado/`, `sessoes/`, `gravacoes/`, `lixeira/`, `marca/`, `modelos/` | vários | Estado da máquina | — |
| Índice BM25 | memória | Reconstruído a cada `recarregar` | — |
| Índice vetorial | — | **AUSENTE** (decisão documentada, `ARCHITECTURE.md:174-177`) | — |

Estado real da biblioteca nesta máquina (leitura de `data/conhecimento`, sem alterar): 16 `metadata.json`; 14 com seções; `parties` e `summary` `missing` em 13 de 14; na única `parties` pronta, **0 de 3** itens são `verified+explicit`; 12 de 16 `layout.json` têm páginas numeradas (os demais são DOCX/TXT, página 0). `analysis-history.jsonl` soma 1.005 linhas; num documento amostrado, 66 de 71 linhas são "nada a fazer".

`meta_fatos` recebe `INSERT`/`DELETE` (`guarda.py:304,321,333`) mas **nenhum `SELECT` existe no código**; o comentário da migração diz o contrário ("é daqui que sai a resposta de nível 0", `base.py:517`).

### 2.8 Modelos de IA

| Uso | Modelo | Como é escolhido | Parâmetros efetivos |
|---|---|---|---|
| Chat (nível 2), nível 0/1, resumo, partes, classificador residual, conferidor | `llama3.2:3b` via Ollama HTTP (`llama_client.py:16-17`) | `PAULUS_MODEL` env → `--model` → `data/preferencias.json "modelo"` recria o client (`api.py:2540-2547`) | `temperature=0.1`, `num_ctx` dinâmico 8192–32768 (`llama_client.py:31-43`), **sem seed** |
| Transcrição | faster-whisper `turbo`/`small` int8 CPU (`src/transcricao.py`) | preferências `voz.modelo` | — |
| `config/extratores.yaml` → `modelos.{roteador,pequeno,grande}` | declara `llama3.2:3b`, temp 0, seed 42 | lido em `catalogo.py:91-96` | usado **só** para preencher `Secao.model` (`portas.py:126`); `temperature`/`seed`/`num_ctx` do YAML **não são lidos por ninguém** |

Acoplamento: o nome do modelo não está espalhado (default único em `llama_client.py:17`), mas os prompts estão colados nos módulos (`llama_client.py:57-88`, `perguntar.py:221-228`, `roteador.py:315-358`, `llm_partes.py:53-65`, `llm_resumo.py:28-43`, `verificador.py:34-44`). `prompt_version` é string manual no YAML; não há hash do texto do prompt, então editar `INSTRUCAO` sem mudar a string mantém seções antigas como atuais. `ask_json` usa o `SYSTEM_PROMPT` do chat ("cite o nome do arquivo…") também na extração de partes (`llama_client.py:262-265`). Não há interface de runtime além de Ollama (`runtime: ollama` é lido e ignorado).

### 2.9 Testes — resultado real

Executados em **cópia isolada** do projeto no scratchpad da sessão (sem `venv/`, com `data/modelos` ligado por junção só-leitura), porque `tests/test_tela.py` e `tests/test_gravacoes.py` sobem o servidor real sobre `data/` e apagam cache/reindexam, e qualquer `import api` instancia `Estado()` com efeitos em `data/paulus.db`. Interpretador: `paulus/legal/venv/Scripts/python.exe` (3.14.3). Ollama estava ligado.

**Resultado: 27 de 27 arquivos terminaram com código 0; 1.871 checagens `ok`; 0 `FALHA`; nenhuma parte pulada** (o Edge/Playwright e os modelos Whisper estavam disponíveis, então `test_tela` e `test_gravacoes` rodaram completos).

| Arquivo | Saída | Tempo | Checagens `ok` |
|---|---|---|---|
| `test_acervo` | 0 | 0 s | 64 |
| `test_assinatura` | 0 | 4 s | 113 |
| `test_base` | 0 | 0 s | 78 |
| `test_citacao` | 0 | 6 s | 33 |
| `test_contextos` | 0 | 0 s | 23 |
| `test_correio` | 0 | 1 s | 98 |
| `test_escrita` | 0 | 4 s | 206 |
| `test_escritorio` | 0 | 1 s | 49 |
| `test_extrato` | 0 | 1 s | 26 |
| `test_frontend` | 0 | 0 s | 18 |
| `test_gravacoes` | 0 | 198 s | 82 |
| `test_habilidades` | 0 | 0 s | 57 |
| `test_historia` | 0 | 0 s | 103 |
| `test_inteligencia` | 0 | 1 s | 48 |
| `test_inteligencia_extensao` | 0 | 5 s | 101 |
| `test_inteligencia_modelo` | 0 | 1 s | 41 |
| `test_inteligencia_regras` | 0 | 1 s | 44 |
| `test_inteligencia_regressao` | 0 | 2 s | 15 |
| `test_inteligencia_verificacao` | 0 | 0 s | 36 |
| `test_intencao` | 0 | 0 s | 138 |
| `test_leis` | 0 | 5 s | 97 |
| `test_marca` | 0 | 2 s | 21 |
| `test_organizador` | 0 | 0 s | 76 |
| `test_pipeline` | 0 | 1 s | 84 |
| `test_redacao` | 0 | 1 s | 49 |
| `test_ritmo` | 0 | 1 s | 19 |
| `test_tela` | 0 | 273 s | 152 |

A contagem de `ok` subestima o que é conferido em alguns arquivos: `test_inteligencia_regressao` só imprime linha por pergunta quando ela falha.

Cobertura, pelo que os arquivos declaram e fazem:

- **Camada**: `test_inteligencia.py` (passo 1: identidade, `text.txt`, mapa de páginas, normalização), `_regras.py` (DV do CNJ, datas, valores), `_verificacao.py` (alinhar, trava de dígitos), `_modelo.py` (extratores de modelo **com cliente falso**, digest), `_extensao.py` (coleções do passo 7, quase tudo negativo), `_regressao.py` (34 perguntas).
- **Golden set / regressão**: existe — `tests/test_inteligencia_regressao.py:63-128`, 34 perguntas com nível esperado. Limitações medidas no próprio arquivo: (a) mede **só a decisão do roteador**, nunca o texto da resposta nem compara camada ligada × desligada pergunta a pergunta (desligada roda só as 6 primeiras, `:224`); (b) depende de `data/test_contracts/` (gitignored) e **retorna 0 "pulado"** se a pasta não existir (`:210-212`) e ignora perguntas cujo documento sumiu (`:237-238`) — em qualquer outra máquina "passa" sem testar nada; (c) a medida "14 de 42 (33%) sem abrir documento" impressa **conta duas vezes** as 7 perguntas de nível 0, porque o laço de conferência (`:265-268`) chama `montar_contexto` de novo e cada chamada vira linha em `Saber.medidas`; no conjunto fixo a taxa real é **7/34 = 21%**; (d) nenhum teste exercita o LLM real na resposta de nível 0.
- **Resto**: pipeline de extração/busca, organizador, base SQLite, assinatura, e-mail (SMTP falso), escrita/editor, leis, extrato bancário, intenção, frontend estático (`test_frontend.py`), tela real com Playwright+Edge (`test_tela.py`), gravações/transcrição real (`test_gravacoes.py`).
- **Sem medição de cobertura** (nenhum `coverage` configurado).

### 2.10 CI/CD, Docker, deploy

**AUSENTE.** Sem workflows, sem Docker, sem instalador (a memória do projeto registra que o instalador foi adiado; o fluxo de uso é `venv\Scripts\python.exe src\desktop.py`). O único "deploy" é a própria máquina do desenvolvedor. Como 114 commits não foram enviados ao remoto, não há sequer backup externo do código recente.

### 2.11 Dependências

- **Pesadas**: `faster-whisper` puxa `ctranslate2`, `onnxruntime`, `av`, `tokenizers`, `huggingface_hub`, `numpy` (venv com 75 pacotes; modelos Whisper em `data/modelos` = 2,0 GB). `pyHanko`+`cryptography`+`pypdfium2` para assinatura. `pywebview` traz `pythonnet/clr_loader`.
- **Não declaradas mas usadas**: `PyYAML` (`catalogo.py:79`). `playwright` (teste).
- **Declaradas e usadas**: todas as de `requirements.txt` têm import no código (verificado por grep; `python-multipart` é usado indiretamente pelo FastAPI nos uploads).
- **Possivelmente sem manutenção** (conhecimento externo, não verificável no repo): `rank-bm25 0.2.2` não tem release desde 2022.
- **Sem pinagem**: todas `>=`; o ambiente real está várias versões maiores à frente do mínimo declarado (ex.: `reportlab>=4.0.0` → 5.0.1).

---

## 3. Estado real vs. arquitetura especificada

Não há documento `legal-document*`/`document-intelligence*` no repositório; a referência canônica usada é a checklist do pedido. `docs/ARCHITECTURE.md:62-154` descreve a camada e foi tratada como intenção, não como prova. Os nomes da spec (inglês, `app/intelligence/`) foram mapeados para os reais (português, `src/inteligencia/`).

| # | Item | Status | Onde | Observação |
|---|---|---|---|---|
| 1 | Hook 1 `analyze_document(source_path, sections, force)` idempotente, background | **IMPLEMENTADO** | `src/inteligencia/portas.py:44-100`; chamado em `src/api.py:281,284-301` | Assinatura difere: exige `texto`/`paginas` prontos do chamador (não extrai). Idempotente nas seções, **mas grava metadata e histórico mesmo sem mudança** (`portas.py:98`). Background roda sem `client`: seções de modelo nunca rodam no app. Docs adicionados enquanto `analisando=True` são ignorados (`api.py:285`) |
| 2 | Hook 2 `resolve_context(question, document_ids, token_budget) -> ContextBundle` | **IMPLEMENTADO** | `portas.py:227-244` → `roteador.py:421-500`; chamado em `habilidades/perguntar.py:83` | Sem `token_budget` (o orçamento é calculado à parte em `perguntar.py:44-51`); recebe objetos de documento, não ids. Nunca levanta exceção (fallback em `portas.py:240-242`) |
| 3 | Hook 3 `render_sources(bundle, answer)` — anexa fontes, rotula inferência | **ESQUELETO** | `portas.py:270-298` | **Nenhum chamador** no código. `perguntar.py:165-175` monta as fontes por conta própria, sem `char_start/char_end`. O rótulo de inferência só aparece ao **reabrir** a conversa (`frontend/js/03-assistente.js:146`); na resposta ao vivo o handler de `fontes` ignora `inferencia` (`03-assistente.js:414-432`). `fontes_da_resposta` ainda fixa `"inferencia": False` (`portas.py:296`) |
| 4 | Flag `INTELLIGENCE_LAYER` com fallback total | **IMPLEMENTADO** | `src/config.py:86`; `api.py:215-217,2549`; `portas.py:234-236` | É preferência de usuário, não env/config; **ligada por padrão**. `INTELIGENCIA=0` citado em `__init__.py:19` não existe. Fallback com a camada desligada é testado (`test_inteligencia_regressao.py:223-231`) |
| 5 | Texto normalizado persistido `extracted/text.txt` | **IMPLEMENTADO** | `guarda.py:203-208` | Grava o texto **extraído, não normalizado** (decisão explícita: é a régua dos offsets). Nunca é regravado para a mesma `version.id`, mesmo que `extract.py` mude (ver risco A2) |
| 6 | Mapa `char_offset → página` `layout.json` | **IMPLEMENTADO** | `texto.py:55-79`; gravado em `guarda.py:209-212` | Derivado das marcas `[pagina N]` (`extract.py:100`), não de coordenadas. Página = índice físico do pypdf, não "fls."; DOCX/TXT → página 0/None |
| 7 | Identidade `document.id` estável / `version.id` por SHA-256 | **IMPLEMENTADO** | `guarda.py:126-199` | `version` por sha256 do arquivo (ou do texto, se o arquivo não existe: `guarda.py:136`). `document` por **caminho** (`guarda.py:155-156`): renomear+editar cria documento novo. Dois arquivos idênticos em caminhos diferentes colapsam na mesma versão e o `caminho` alterna a cada registro (`guarda.py:141-151`) |
| 8 | `metadata.json` schema `legal-document/v0` | **IMPLEMENTADO** | `esquema.py:238-351`; validador `esquema.py:354-390` | Extensões sobem ao primeiro nível (`esquema.py:327-331`). `classification.certainty` recebe valores de *confiança* (`high`/`medium`) em vez de `CERTEZAS` (`llm_classificador.py:114`) — `problemas()` não valida seções-objeto |
| 9 | Índice SQLite para lookup rápido | **IMPLEMENTADO** (parcial) | migração `base.py:465-535`; escrita `guarda.py:300-340` | `meta_versoes`/`meta_documentos` são consultadas (`guarda.py:141,155,250,255`). **`meta_fatos` nunca é lido**; o roteador abre `metadata.json` por pergunta. `_indexar` assume `verified=True` quando a chave falta (`guarda.py:339`) |
| 10 | Extratores nível 0: CNJ, datas, valores, referências legais | **IMPLEMENTADO** | `extratores/regras_processo.py`, `regras_datas.py`, `regras_valores.py`, `regras_leis.py` (+ `regras_juizo.py` e 8 de extensão) | Todos declarados nível 0 no YAML (`config/extratores.yaml:50-99`) |
| 11 | DV do CNJ (ISO 7064 mod 97-10) | **IMPLEMENTADO** | `regras_processo.py:52-65` | Conta correta (`98 - int(corpo+"00") % 97`). Número com DV inválido vira `uncertain`/`verified: False` (`:139-142`). Escolhe o primeiro válido (`:115`) |
| 12 | Normalização pt-BR de valores e datas | **IMPLEMENTADO** | `regras_valores.py:30,44-50`; `regras_datas.py:39-43,64-70` | Valor **exige "R$"** (`:30`): "15.000,00 (quinze mil reais)" sem símbolo não entra — só 3 valores em 14 documentos reais. Datas: dd/mm/aaaa, extenso, ISO; "1º de março" não casa |
| 13 | Verificação de span: `quote` casando com o texto | **IMPLEMENTADO** | `alinhar.py:70-143, 242-273` | Aplicada **só a itens sem span** (vindos de modelo, `portas.py:148-150`). Itens de regra são `verified=True` por construção (`base.py:101-108`) — o span prova o número, não o rótulo |
| 14 | Fuzzy com limiar alto + mapa normalizado→original | **IMPLEMENTADO** | `alinhar.py:40` (0.92), `:113-137`; `texto.py:83-107` | Dígitos e números por extenso têm de bater (`alinhar.py:130`). Citação < 12 chars rejeitada (`:43,82`) |
| 15 | `verified: false` bloqueia uso factual | **IMPLEMENTADO** (parcial) | `esquema.py:178-187, 291-295`; `roteador.py:771` | Vale para coleções. **Seções-objeto só exigem `verified`, não `quote`/`source`**: a classificação por regra é `verified: True` sem citação (`llm_classificador.py:118`) e responde nível 0. O bloqueio não se estende à **resposta** do LLM |
| 16 | Verificador separado do extrator | **IMPLEMENTADO** | `extratores/verificador.py:59-99`; chamado em `portas.py:154-160` | Chamada separada, só rebaixa. **Fail-open**: erro ou resposta que não comece com NAO/NÃO/NO = aceito (`verificador.py:67-79`). Nunca roda no app (sem client em background) |
| 17 | Roteador em 6 níveis (0–5) com classificação de intenção | **IMPLEMENTADO** (parcial) | `roteador.py:49-54, 212-245, 421-761` | Níveis 0, 1, 2, 3 produzidos. **Nível 4 só muda o rótulo** — `perguntar.py:90-100` trata 3 e 4 igual. **Nível 5 é só constante** (`roteador.py:54`), nunca produzido. Intenção por regex (`roteador.py:69-188`) |
| 18 | Campo ausente escala, nunca vira negativa | **IMPLEMENTADO** (com brechas) | `roteador.py:460-482, 735-748` | Brechas: com `em_foco` e vários documentos, seção faltante em um deles **não escala** (`roteador.py:470`) e ambiguidade é ignorada (`:485`); truncamento silencioso a 12 fatos no ramo factual (`:494`), enquanto listas escalam (`:749`); e o LLM pode responder negativa no nível 0 sem ser barrado (risco B2) |
| 19 | `ESCALAR` na saída do nível 0 | **IMPLEMENTADO** | prompts `roteador.py:330,343,354`, `perguntar.py:227`; detecção `roteador.py:834-837`; refaz caminho `perguntar.py:84-89` | Detecta só se a resposta **começa** com "escalar" (40 primeiros chars). "Não sei. ESCALAR" ou "Não consta" passam como resposta |
| 20 | `bundle.trace` com decisões do roteador | **IMPLEMENTADO** | `roteador.py:304, 433-434` e cada ramo | Não é persistido nem exposto: `Pacote.resumo_para_tela()` (`:360-364`) não tem chamador; o evento SSE leva só `nivel` e `porque` |
| 21 | Registry YAML — trocar modelo sem tocar código | **IMPLEMENTADO** (parcial) | `config/extratores.yaml`; `catalogo.py:77-160` | Troca **extrator/módulo** por YAML, sim. Troca **modelo**, não: `modelos.*.id` não instancia cliente; o client é global (`api.py:152`, `retomar.py:127`) |
| 22 | `temperature: 0` + seed + `model_digest` + `prompt_version` por seção | **ESQUELETO** (parcial) | YAML `:24-45`; `portas.py:124-133`; `llama_client.py:101,126,288-307` | `model_digest` e `prompt_version` **são gravados** por seção. `temperature 0` e `seed` **não são aplicados** — client usa 0.1 e não envia seed. Metade do item é declaração sem efeito |
| 23 | `analysis.sections` com `ok/stale/failed/missing/skipped` | **IMPLEMENTADO** | `esquema.py:59, 190-235` | `skipped` é aceito no schema mas o código grava `missing` para "assistente desligado" (`portas.py:80`) |
| 24 | Invalidação seletiva por troca de extrator | **IMPLEMENTADO** (parcial) | `guarda.py:390-424`; `envelhecer` `guarda.py:365-388` | Funciona por **comparação na próxima análise** (extrator/prompt/esquema). `envelhecer()` **não tem chamador**. Troca de modelo/digest **só é detectada pelo CLI com `--assistente`**; no app o background passa digest e modelo vazios (`portas.py:68-70`) e seções de modelo antigas seguem `ok`. O roteador não consulta o catálogo, então há janela entre trocar o YAML e reanalisar |
| 25 | `analysis-history.jsonl` por documento | **IMPLEMENTADO** | `guarda.py:290-296` | Por **versão**, não por documento. Cresce a cada inicialização com "nada a fazer" (1.005 linhas / 16 docs na máquina) |
| 26 | Backfill CLI idempotente e retomável `--resume` | **IMPLEMENTADO** (sem a flag) | `retomar.py:90-170` | Não há `--resume`; "retomável" = idempotência de `analisar_documento`. Tem `--limite`, `--secoes`, `--forcar`, `--assistente`, `--sidecar` |
| 27 | Original nunca alterado/movido/copiado | **IMPLEMENTADO** | `guarda.py:126-229` só lê o original | Exceção opt-in: `--sidecar` escreve `<arquivo>.meta.json` **ao lado** do original (`retomar.py:80-83`). O Organizador (fora da camada) move originais por design, com diário |
| 28 | `source` suportando `text/audio/image` | **IMPLEMENTADO** (só no schema) | `esquema.py:74-122` | Nenhum produtor de `audio`/`image`: transcrições de `gravacoes.py` não entram na biblioteca; `ocr_used` é sempre `False` (`guarda.py:192`) |
| 29 | Suíte de regressão 30–50 perguntas reais anotadas | **IMPLEMENTADO** (frágil) | `tests/test_inteligencia_regressao.py:63-128` (34 perguntas) | Mede decisão, não resposta; não reproduzível fora desta máquina; contém PII real (risco B1); taxa impressa inflada (§2.9) |
| 30 | Instrumentação: % nível 0/1, tokens, latência, fallback | **IMPLEMENTADO** (parcial) | `portas.py:246-267`; exposto em `api.py:581-598`; `jobs.py:57` | Em memória, últimas 500, perdido ao reiniciar. `ms` é só do roteador. **Sem tokens** no nível 0 (chamada não-stream não emite `medida`, `perguntar.py:182`). **Sem contador** de "escalou depois do ESCALAR" (vai só como texto em `ctx.registrar`, `perguntar.py:89`). Nenhum `logging` na aplicação (único uso em `assinatura.py:502-505`) |

**Em qual passo do roadmap o projeto realmente está?** O código tem artefatos dos sete passos, todos commitados no mesmo dia (13/09/2026). Mas o critério de cada passo é ser **entregável, reversível e mensurável sozinho**, e por esse critério o projeto está **no passo 4, ainda não fechado**. Os passos 1 (texto + layout) e 3 (align) estão de pé, com a ressalva de proveniência do risco A2. O passo 2 funciona, mas grava rótulos heurísticos como fato verificado. O passo 4 (roteador nível 0 atrás de flag) está **ligado por padrão** e faltam três condições que o tornariam seguro e mensurável: a resposta do LLM não é conferida contra os fatos, a geração não é determinística e a medição não sobrevive a um reinício. O passo 5 existe em código, mas **não opera no produto**: extratores de modelo só rodam pelo CLI, e na biblioteca real `parties`/`summary` estão `missing` em 13 de 14 documentos, com 0 partes aproveitáveis. O passo 6 opera como filtro de documentos (nível 4 sem comportamento próprio, nível 5 inexistente). O passo 7 foi construído (só regras) antes de o 4 ter critério de saída.

---

## 4. Dívida técnica e riscos

Ordenados por gravidade. "Custo agora × depois" é estimativa de esforço, não medida.

### Bloqueante

**B1 — PII real de cliente versionada, prestes a ser enviada.**
`tests/test_inteligencia_regressao.py:126` contém um CPF de 11 dígitos com DV válido (conferido) extraído do acervo real, e `:77-125` nomes de arquivo com nomes de partes; comentários em `src/inteligencia/extratores/llm_classificador.py:61`, `llm_partes.py:81-84`, `regras_pessoas.py:13`, `entidades.py:111` e `tests/test_inteligencia_extensao.py:454-465` citam a organização cliente pelo nome. Introduzido em `2febd3e` e anteriores; `main` está 114 commits à frente do remoto. *Por que neste projeto*: o argumento de venda é privacidade (`CONTRIBUTING.md:23-26`, regra 1: "Nenhum documento de cliente no repositório"). *Agora*: trocar por fixtures sintéticas e reescrever o histórico local antes do primeiro push (horas). *Depois do push*: reescrita de histórico remoto, rotação de clones e possível incidente de dados pessoais.

**B2 — Nível 0 entrega texto livre do LLM sem conferência mecânica.**
`habilidades/perguntar.py:182-212`: os fatos verificados viram prompt, o llama3.2:3b escreve a frase e ela é emitida como `token` único. O único filtro é `pediu_escalar` (`roteador.py:834-837`), que só olha o prefixo. O modelo pode trocar "R$ 250.000,00" por "R$ 25.000,00", reescrever o número CNJ ou dizer "não há valor da causa" — e a tela mostra fontes com página ao lado, o que aumenta a confiança numa resposta errada. Isso fura a regra "o LLM aponta, não emite número" (`regras_processo.py:15-17`) justamente no caminho rápido. *Agora*: comparar dígitos/datas da resposta com os `Fato.valor` e rejeitar negativas, escalando em caso de divergência — ou, para perguntas de dado único, renderizar a resposta por template sem LLM (1–2 dias). *Depois*: cada demo com resposta errada citada com página custa credibilidade.

### Alto

**A1 — Rótulo heurístico gravado como fato verificado.**
`extratores/base.py:101-108` marca todo item de regra como `explicit`/`verified`. O `kind` vem de `escolher_kind` por proximidade de palavra-chave num raio de 70 caracteres (`base.py:146-188`; `regras_valores.py:63`; `regras_datas.py:99`). "Qual o valor da causa?" filtra por `kind == "claim"` (`roteador.py:73-74, 781`) e responde nível 0 com um valor cuja citação é só `"R$ 15.000,00"`: o span prova o número, não que ele seja o valor da causa. Mesmo padrão em `regras_juizo.py:68-75`: a primeira sigla de tribunal nos 4.000 primeiros caracteres (ex.: "Súmula 7 do STJ" num contrato) vira `court` explícito, com citação de 3 caracteres (`:115-118`). *Agora*: separar `verified` (span) de `label_certainty` e só aceitar nível 0 com filtro por `kind` quando a pista estiver dentro da própria citação ampliada (1 dia). *Depois*: exige reprocessar o acervo e mudar o schema gravado.

**A2 — Proveniência presa a uma extração que pode mudar.**
`text.txt` é gravado uma vez por `version.id` (sha256 do **arquivo**, `guarda.py:136,141-151`). Se `extract.py` mudar (ordem de leitura, `_texto_da_pagina`), o buscador passa a usar outro texto, mas a versão continua a mesma e os offsets/páginas do metadata apontam para o texto antigo. `provenance.text_sha256` é gravado (`guarda.py:193`) e **nunca comparado** (grep). Pior: `analisar_documento` roda extratores sobre o texto **novo** (`portas.py:116-119`) com `paginas` lidas do `layout.json` **antigo**. *Agora*: incluir versão do extrator de texto na identidade da versão ou comparar `text_sha256` e reextrair (meio dia). *Depois*: toda citação já gravada fica suspeita e a correção vira migração do acervo.

**A3 — Determinismo declarado, não aplicado; registry não troca modelo.**
`config/extratores.yaml:24-45` declara `temperature: 0`, `seed: 42`; `catalogo.py:91-96` lê; ninguém usa (grep: `temperature` só aparece em `llama_client.py:101,107,126` com 0.1). `modelos.*.id` só vai para `Secao.model` (`portas.py:126`). Sem seed e com temperatura 0.1, duas análises do mesmo documento podem divergir, e trocar modelo passa pela tela de preferências, não pelo YAML. *Agora*: `LlamaClient` aceitar `options` do perfil do catálogo e cada extrator de modelo receber seu próprio client (meio dia). *Depois*: nenhuma comparação A/B de modelo feita até lá é válida.

**A4 — Invalidação por troca de modelo não roda no produto.**
O background chama `analisar_documento` sem client (`api.py:293-295`) → `desatualizadas` recebe digest e modelo vazios (`portas.py:68-70`) → a comparação de `guarda.py:417-421` nunca dispara. `envelhecer()` não tem chamador. Um `ollama pull` ou a troca de modelo em Configurações deixa seções de modelo `ok` para sempre (hoje afeta 1 documento; afetará todos quando o passo 5 operar). *Agora*: calcular o digest do modelo configurado no background, mesmo sem rodar o modelo, e marcar `stale` (horas). *Depois*: respostas de nível 1 com resumo de modelo antigo sem aviso.

**A5 — Hook 3 não conectado; rótulo de inferência some na resposta ao vivo.**
`fontes_da_resposta` (`portas.py:270`) não tem chamador. O handler SSE de `fontes` (`frontend/js/03-assistente.js:414-432`) não lê `dados.inferencia`; o rótulo "leitura do assistente" só aparece ao reabrir a conversa (`:146`). No nível 1 o usuário lê um resumo do modelo sem saber que não é trecho do documento — o oposto do que `llm_resumo.py:4-8` promete. As fontes do nível 0 perdem `char_start/char_end` (`perguntar.py:165-175`), então "abrir na página" não tem o span. *Agora*: 10 linhas no JS e usar `fontes_da_resposta` em `perguntar.py` (horas). Barato, e está na frente do cliente.

**A6 — Brechas na regra de não-regressão com documentos em foco.**
`roteador.py:470`: `if sem_secao and not em_foco` — com dois documentos em foco e a seção faltando em um, responde só com o outro. `:485`: ambiguidade entre documentos é ignorada com `em_foco`. `:494`: `achados[:FATOS_MAX]` corta sem escalar, enquanto `_pela_lista` escala (`:749`). Classificação `verified: True` sem `quote` responde nível 0 (`llm_classificador.py:118`; `roteador.py:768-778` só checa `verified`). *Agora*: aplicar as mesmas travas com foco e exigir `quote`+`source` em seções-objeto (horas, com casos novos na regressão). *Depois*: cada uma vira bug de campo difícil de reproduzir.

**A7 — Suíte de regressão não protege o que diz proteger.**
Ver §2.9: pula com exit 0 sem o acervo (`test_inteligencia_regressao.py:210-212`), mede decisão e não resposta, conta em dobro (`:265-268`), e é a mesma que carrega PII (B1). Não existe caminho para rodar em outra máquina ou em CI. *Agora*: fixture sintética versionada com o mesmo conjunto de armadilhas + falhar (não pular) quando o acervo faltar em modo estrito (1 dia). *Depois*: o passo 5 (modelos) vai mudar respostas sem nenhuma rede de proteção.

**A8 — Trabalho sem cópia fora da máquina.**
`git rev-list --count origin/main..main` = 114. Seis dias de trabalho, o SQLite de desenvolvimento e a biblioteca de metadata existem num único disco. *Agora*: resolver B1 e dar push (minutos depois de B1). *Depois*: perda irrecuperável em caso de falha de disco.

### Médio

**M1 — `api.py` monolítico com efeitos colaterais no import.** 6.133 linhas, 253 rotas, `estado = Estado()` no import (`api.py:304`) abre `data/paulus.db`, esvazia a lixeira vencida (`api.py:224`), inicia thread de transcrição (`:225-227`). Qualquer teste que faz `import api` (`test_assinatura.py:485`, `test_correio.py:501`, `test_gravacoes.py:73`, `test_tela.py:100`) toca o estado real; `test_tela.py:680-689` apaga o cache de extração de verdade. *Agora*: `Estado` lazy + `BASE_DIR` configurável por env para testes (1 dia). *Depois*: cresce a cada tela.

**M2 — PyYAML não declarado.** `catalogo.py:79` importa fora do `try`; se a dependência transitiva sumir (troca de versão do `faster-whisper`/`huggingface_hub`), `Estado.__init__` (`api.py:213`) quebra e o programa não abre — o contrário do fallback prometido em `catalogo.py:86-89`. *Agora*: uma linha em `requirements.txt` + import dentro do `try` (minutos).

**M3 — Ambiente não reprodutível.** Sem pinagem nem lock; documentação diz 3.10+, ambiente é 3.14.3; nenhum teste em outra versão. Para a primeira instalação num cliente isso vira loteria de versões. *Agora*: `pip freeze` para um `requirements.lock` (minutos). *Depois*: bug de instalação no piloto.

**M4 — Colisão de identidade para arquivos idênticos.** `guarda.py:141-151`: dois arquivos byte a byte iguais em caminhos diferentes (caso que `extract.py:193-197` diz ser comum) viram a mesma versão; a cada inicialização o `caminho` alterna e grava "arquivo mudou de lugar"; `ler_por_caminho` falha para um deles. *Agora*: identidade de documento por (sha256, caminho) com vínculo explícito (meio dia). *Depois*: é mudança de identidade gravada em disco (migração).

**M5 — Histórico e disco crescendo sem mudança.** `portas.py:98` grava sempre; 66 de 71 linhas "nada a fazer" num documento em ~1 dia. Com acervo de centenas de documentos e várias aberturas por dia, vira I/O e ruído no único log de proveniência. *Agora*: gravar só se `analise.mudou` ou houve falha (minutos).

**M6 — Concorrência na análise em segundo plano.** `self.analisando = True` é definido dentro da thread (`api.py:289`), depois do `if` (`:285`): duas reindexações próximas podem abrir duas threads gravando o mesmo `metadata.json.novo` (`guarda.py:286-288`). Documentos adicionados durante uma análise são descartados até a próxima reindexação. Exceções são engolidas (`api.py:296-297`) sem registro. *Agora*: fila única com trava (horas).

**M7 — Instrumentação volátil.** `Saber.medidas` só em memória (`portas.py:199,253`); sem tokens no nível 0; sem contador de escalada pós-ESCALAR; sem `logging`. É impossível responder "a camada ajudou esta semana?" depois de reiniciar o programa. *Agora*: anexar a medida a um JSONL em `data/` (horas).

**M8 — `meta_fatos` é escrita morta e comentário enganoso.** `base.py:517` diz que o nível 0 sai dessa tabela; o código nunca a lê; `guarda.py:339` indexa `verified=1` por padrão. Custo de escrita a cada gravação e risco de alguém passar a consultá-la acreditando no comentário. *Agora*: remover a escrita ou corrigir o padrão e o comentário (minutos).

**M9 — Conferidor fail-open e prompt contaminado.** `verificador.py:67-79` aceita erro, vazio e qualquer resposta que não comece com NAO/NO. `ask_json` usa o `SYSTEM_PROMPT` do chat na extração de partes (`llama_client.py:262-265`). `prompt_version` é manual, sem hash do texto. Hoje o impacto é pequeno porque o passo 5 não opera; quando operar, vira a principal via de fato errado aceito. *Agora*: fail-closed no conferidor e hash do prompt na ficha (horas).

### Baixo

**L1 — Documentação divergente do código**: temperatura 0.1 × 0 (`ARCHITECTURE.md:238` × YAML), `src/habilidades.py` e `src/extract_expiring.py` inexistentes, `INTELIGENCIA=0` inexistente, QUICKSTART com abas antigas, README "Semana 1 concluída", README da raiz sem distinguir que "Coryphaeus" não tem código.
**L2 — Página física, não folha processual**: `extract.py:99-100` numera por índice do pypdf; processo judicial cita "fls.". PDF escaneado é descartado sem aviso na biblioteca (`extract.py:212-215`).
**L3 — Níveis 4 e 5**: nível 4 sem comportamento próprio (`perguntar.py:90`); nível 5 só constante (`roteador.py:54`).
**L4 — Pequenos defeitos**: variável `chave` sem uso (`regras_datas.py:100`); `skipped` nunca gravado; `.gitignore` da raiz é o template genérico de Python.

### Decisões difíceis de reverter (já gravadas em disco)

| Decisão | Onde | Por que é cara de mudar |
|---|---|---|
| Chaves JSON em inglês, extensões no primeiro nível | `esquema.py:10-15, 327-331` | Leitores externos/sidecars dependem do formato |
| Forma de `source` (`version_id`, `char_start/end`, `page`, `time_*`, `bbox`) | `esquema.py:74-122` | Toda citação do acervo usa |
| `version.id` = sha256 do arquivo (ou do texto, se o arquivo não existe) | `guarda.py:136` | Dois domínios de hash na mesma coluna; muda a identidade de tudo |
| `document.id` = caminho | `guarda.py:155-156` | Ver M4 |
| Offsets relativos ao texto com marcas `[pagina N]` | `texto.py:29`, `extract.py:100` | Trocar o extrator de PDF invalida todos os spans (A2) |
| `schema_version` fixo `"v0"` sem migrador | `portas.py:132`, `guarda.py:416` | A primeira mudança de schema não tem caminho |

### Segurança

- **Segredos versionados**: nenhum encontrado (`git grep` por chaves, tokens, PEM, AWS/GitHub; o único "senha" é fixture de teste, `test_correio.py:318`). `.pfx`, contas de e-mail, sessões de WhatsApp e `data/conhecimento/` estão no `.gitignore` (`paulus/legal/.gitignore`), e nenhum arquivo desses aparece no histórico (`git log --all --diff-filter=A`).
- **PII de cliente em arquivos versionados**: sim — B1.
- **PII local não versionada**: `data/preferencias.json` tem CPF, telefone, e-mail e endereço do usuário; `data/test_contracts/` tem 16 documentos reais; `data/sessoes/` (43 MB) tem sessão de WhatsApp. Tudo gitignored — correto, mas é uma única máquina sem backup nem criptografia em repouso (hipótese: sem BitLocker, não verificado).
- **Caminhos absolutos de máquina versionados**: nenhum (grep por `C:\Users`, `/c/Users`).
- **Superfície de rede**: servidor preso a `127.0.0.1` (`api.py:6129`, `desktop.py:178-219`); sem autenticação, o que qualquer processo local pode usar (documentado em `ARCHITECTURE.md:252-254`).

---

## 5. Próximos passos priorizados

Partem do estado real (passo 4 aberto, passos 5–7 em código mas não operando) e respeitam a regra: cada passo entregável, reversível e mensurável sozinho.

### Agora (próxima semana)

| # | O que fazer | Arquivos | Por que nesta ordem | Pronto quando |
|---|---|---|---|---|
| 1 | Tirar PII real do repositório e reescrever o histórico local; depois dar push | `tests/test_inteligencia_regressao.py`, `tests/test_inteligencia_extensao.py`, docstrings em `src/inteligencia/extratores/{llm_classificador,llm_partes,regras_pessoas,entidades}.py`, `src/contextos.py`, `src/intencao.py`, `tests/test_{contextos,correio,escrita,intencao}.py` | Só é barato antes do push (B1) e destrava o backup (A8) | `git log -p --all \| grep -E "<CPF>\|<nomes>"` vazio; `origin/main == main` |
| 2 | Fixture sintética versionada para a regressão, com as mesmas armadilhas; modo estrito que **falha** sem acervo; corrigir a contagem dupla | `tests/test_inteligencia_regressao.py`, novo `tests/fixtures/` | Sem rede de proteção reproduzível, qualquer mudança a seguir é fé (A7) | Clone limpo roda a regressão com ≥ 30 perguntas e 0 "pulado"; taxa impressa = nível 0 / tamanho do conjunto |
| 3 | Conferência mecânica da resposta do nível 0: todo número/data/CNJ da resposta tem de estar em `pacote.fatos`; negativa ou divergência → escala. Para perguntas de dado único, avaliar template sem LLM | `habilidades/perguntar.py:156-214`, `src/inteligencia/roteador.py` (nova função ao lado de `pediu_escalar`) | É o risco que mais pode causar dano visível na demo (B2) | Testes com cliente falso que troca um dígito, responde "não consta" e "Não sei. ESCALAR" → os três escalam |
| 4 | Aplicar `temperature`/`seed`/`num_ctx` do catálogo nas chamadas da camada | `src/llama_client.py:96-127`, `src/inteligencia/portas.py:111-133`, `habilidades/perguntar.py:182` | Pré-requisito para medir qualquer coisa do passo 5 (A3) | Payload enviado ao Ollama (teste com `requests` falso) contém `temperature: 0` e `seed: 42` nas chamadas da camada; mesma análise duas vezes = mesmo `metadata.json` |
| 5 | Ligar o Hook 3: rótulo de inferência ao vivo e fontes com span | `frontend/js/03-assistente.js:414-432`, `habilidades/perguntar.py:165-175` usando `portas.fontes_da_resposta` | Barato, e está na frente do usuário (A5) | `test_tela.py` com resposta de nível 1 mostra `.etiqueta-inferencia` **antes** de reabrir a conversa |
| 6 | Fechar as brechas com foco: seção faltante em qualquer documento em foco escala; truncamento escala; seção-objeto sem `quote`+`source` não responde nível 0 | `src/inteligencia/roteador.py:460-500, 764-784`, `src/inteligencia/extratores/llm_classificador.py:108-121` | Completa a regra de ouro do passo 4 (A6) | Casos novos na regressão sintética: 2 docs em foco com 1 sem seção → escala; 13 fatos → escala; "que tipo de documento é este?" sem citação → escala |
| 7 | Três correções de minutos: `PyYAML` no requirements + import no `try`; `requirements.lock`; gravar metadata só quando algo mudou | `requirements.txt`, `src/inteligencia/catalogo.py:79`, `src/inteligencia/portas.py:98` | Reduz risco de instalação do piloto (M2, M3, M5) | venv novo a partir do lock sobe o app; reiniciar o app duas vezes não acrescenta linha em `analysis-history.jsonl` |

### Em seguida (próximo mês)

| # | O que fazer | Arquivos | Pronto quando |
|---|---|---|---|
| 8 | Instrumentação persistente: JSONL com nível, fallback, escalada pós-ESCALAR, tokens e latência ponta a ponta por pergunta | `src/inteligencia/portas.py:246-267`, `habilidades/perguntar.py`, `src/api.py:581-598` | Depois de reiniciar, `/api/inteligencia` mostra as mesmas contagens; relatório semanal sai de um script |
| 9 | Separar certeza do span e certeza do rótulo; nível 0 por `kind` só com pista dentro da citação ampliada; tribunal só no cabeçalho real | `src/inteligencia/extratores/base.py`, `regras_valores.py`, `regras_datas.py`, `regras_juizo.py`, `esquema.py`, `roteador.py:780-784` | Regressão sintética com "multa ao lado de valor da causa" e "Súmula do STJ em contrato" → escala |
| 10 | Proveniência robusta: versão do extrator de texto + comparação de `text_sha256`; ao divergir, nova versão e seções `stale` | `src/extract.py`, `src/inteligencia/guarda.py:126-229` | Teste que muda `_texto_da_pagina` e confirma nova versão e spans recalculados |
| 11 | Invalidação por modelo no app: digest do modelo configurado no background; `envelhecer` chamado ao trocar modelo em Preferências | `src/api.py:284-301, 2535-2553`, `src/inteligencia/guarda.py:365-424` | Trocar o modelo na tela marca `summary`/`parties` como `stale` em todo o acervo |
| 12 | **Só então** operar o passo 5: rodar extratores de modelo em janela ociosa pelo app, conferidor fail-closed, hash do prompt na ficha, e medir a taxa de itens rebaixados por seção antes de deixar a seção responder nível 0 | `src/inteligencia/portas.py`, `extratores/verificador.py`, `extratores/llm_*.py`, `src/llama_client.py:251-279` | Por seção: % de itens verificados e % rebaixados publicados; seção só entra no roteador acima de um limiar definido |
| 13 | Identidade de documento para cópias idênticas | `src/inteligencia/guarda.py:141-156` | Dois arquivos iguais em pastas diferentes → dois caminhos estáveis, sem regravação a cada inicialização |
| 14 | Isolar efeitos de `import api` (Estado lazy, `BASE_DIR` por env) e tirar `test_tela`/`test_gravacoes` de cima de `data/` real | `src/api.py:106-304`, `tests/test_tela.py`, `tests/test_gravacoes.py` | Suíte inteira roda com `PAULUS_DATA=<tmp>` sem tocar `paulus/legal/data` |

### Depois

- Nível 4 com comportamento próprio (orçamento por documento na comparação) e nível 5 real a pedido.
- Produtores de `source.kind = audio` a partir das transcrições (o schema já comporta).
- CI mínimo (GitHub Actions Windows) rodando a suíte sintética.
- Quebrar `api.py` por domínio.
- Migrador de `metadata.json` antes da primeira mudança de schema.

### O que **não** fazer agora

- **Não expandir o passo 5 nem acrescentar coleções (passo 7) antes dos itens 2–6.** Hoje não há determinismo, nem conferência da resposta, nem regressão reproduzível; qualquer modelo novo mudaria respostas sem medida.
- **Não trocar de modelo (llama3.1:8b, ministral, q8) para "resolver" acurácia** antes do item 4: sem temperatura 0 e seed, a comparação não vale.
- **Não usar `meta_fatos` como fonte de resposta** sem antes corrigir `guarda.py:339` e o comentário da migração.
- **Não exportar sidecars (`--sidecar`) em pastas de cliente**: o próprio código avisa que o metadata é mais sensível que o documento (`retomar.py:65-70`).
- **Não dar `git push` antes do item 1.**
- **Não confiar na taxa "33% sem abrir documento"** da saída da regressão para material comercial: a medida real no conjunto é 21%, e mede decisão do roteador, não acerto de resposta.

---

## 6. Apêndice: comandos executados e saídas relevantes

Nenhum arquivo do projeto foi alterado, exceto este. Os testes rodaram numa cópia em `%TEMP%\claude\...\scratchpad\copia`.

```text
$ git rev-parse --short HEAD ; git branch --show-current
c4df1b1 (início) → cfb1251 (00:20) → 968d39f (00:30, entrega) ; main

$ git log --format='%ad' --date=short | sort | uniq -c
      9 2026-09-09
     24 2026-09-10
     19 2026-09-11
     36 2026-09-12
     26 2026-09-13
      3 2026-09-14

$ git shortlog -sn HEAD
   116  Matheus Uener Silva
     1  matheusuener-atos

$ git remote -v ; git rev-list --count origin/main..main
origin  https://github.com/matheusuener-atos/coryphaeus.git
114

$ gh repo view matheusuener-atos/coryphaeus --json visibility
{"isPrivate":true,"visibility":"PRIVATE"}

$ git log --oneline -30   (trecho da camada)
bca780d A camada aparece na tela: o que ja foi lido, a chave para desligar ...
eb495a8 A ficha da secao guarda o digest do modelo ...
e9a725c Camada de inteligencia, passo 6 ...
439bedc Camada de inteligencia, passo 5 ...
678fa2f Camada de inteligencia, passo 4: ... medido, 12,5 s no lugar de 57
786e3be Camada de inteligencia, passo 3 ...
4886cba Camada de inteligencia, passo 2 ...
6e16ac1 Camada de inteligencia, passo 1 ...
0f95196..2febd3e  Passo 7, colecoes 1 a 7
4cff619 As sete colecoes novas aparecem na tela, e o passo 7 entra na arquitetura

$ wc -l (por linguagem)
src/ (sem camada) 23073 · src/inteligencia 5611 · habilidades 569 · tests 11496
frontend/js 17966 · frontend/css 4397 · index.html 289 · *.md 3304 · mockups 3927
src/api.py 6133 ; grep -c "@app\." src/api.py → 253

$ grep TODO|FIXME|XXX|HACK|NotImplementedError (src, habilidades, tests, frontend/js)
nenhum marcador real (só `pass` em blocos except e o identificador TODO_O_ACERVO)

$ git grep (segredos: api_key/secret/token/PEM/AKIA/ghp_/sk-)
paulus/legal/tests/test_correio.py:318: senha = "senha-secreta-do-email"   (fixture)

$ git grep -c -i "coobramex|caroline|wanderson" -- src tests habilidades docs/*.md
12 arquivos em src/ e tests/ ; CPF real: tests/test_inteligencia_regressao.py:126 (DV válido)

$ grep -rn "temperature" src habilidades
src/llama_client.py:101 temperature: float = 0.1
src/llama_client.py:126 "options": {"temperature": self.temperature, "num_ctx": self.num_ctx}
src/inteligencia/catalogo.py:38,43,94  (lido do YAML, sem consumidor)

$ grep -rn "fontes_da_resposta|envelhecer(|FROM meta_fatos"
só definições; nenhum chamador / nenhum SELECT

$ venv/Scripts/python.exe --version ; pip list | wc -l
Python 3.14.3 ; 75 pacotes (PyYAML 6.0.3 presente, não declarado)

$ ollama list
llama3.2:3b-instruct-q8_0   3.4 GB
alibayram/ministral-3b-instruct:latest 3.5 GB
llama3.2:3b                 2.0 GB

$ leitura de data/conhecimento (script Python só-leitura)
14 docs com seções; parties missing 13/14, summary missing 13/14
itens verified+explicit/total: dates 25/25, people 18/19, organizations 9/10,
events 8/8, evidence 5/5, amounts 3/3, legal_references 6/6, parties 0/3
analysis-history.jsonl: 1005 linhas; amostra 66/71 "nada a fazer"

$ python tests/test_inteligencia_regressao.py   (na cópia)
acervo: 14 documentos analisados
  ...  7 respondidas do metadata, 27 pelo caminho de hoje (0.25 s no total)
  ...  14 de 42 perguntas (33%) sem abrir documento
  todos os testes passaram
```

```text
$ (na cópia) for t in tests/test_*.py; do timeout 1500 venv/Scripts/python.exe "$t"; done
27 arquivos, 27 com saída 0, 1871 linhas "ok", 0 linhas "FALHA"
maiores tempos: test_tela 273 s, test_gravacoes 198 s, test_citacao 6 s

$ python tests/test_gravacoes.py   (seções, todas concluídas)
servicos: a pasta de trabalho · planilha: trazer o Financeiro e os prazos ·
servicos: abrir pela conversa · gravacoes: importar, ouvir, marcar, anotar ·
transcricao nesta maquina (fila de fundo) · transcricao ao vivo (audio em pedacos) ·
lixeira: apagar guarda 30 dias, restaurar devolve tudo
  todos os testes passaram

$ python tests/test_tela.py   (25 blocos, incluindo "o que ja foi lido (camada de inteligencia)")
  14 contrato(s) carregado(s) de ...\scratchpad\copia\data\test_contracts
  (16 documentos em data/test_contracts; 2 PDFs de 1 página sem texto — escaneados — são descartados pela extração)
```
