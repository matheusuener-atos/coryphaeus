# Arquitetura - PAULUS Legal (MVP)

## Onde isso se encaixa

```
ATOS (empresa)
  └── CORYPHAEUS (Agent OS / orquestracao)
      └── PAULUS (produto)
          └── legal (vertical: escritorios juridicos)
```

## Fluxo de uma pergunta

```
pergunta do usuario
      |
      v
[search.py]  BM25 sobre trechos de contrato
      |
      v
trechos relevantes -> agrupados por contrato -> remontados na ordem original
      |
      v
[llama_client.py]  system prompt + contexto + pergunta -> Ollama (HTTP local)
      |
      v
resposta com citacao do arquivo de origem
```

Nada sai da maquina: extracao, indice e inferencia rodam localmente.

## Modulos

| Arquivo | Responsabilidade |
|---|---|
| `src/extract.py` | PDF/DOCX/TXT -> texto puro + cache por SHA-1 |
| `src/search.py` | chunking, tokenizacao PT-BR, indice BM25, montagem do contexto |
| `src/llama_client.py` | HTTP com o Ollama, system prompt, streaming, saida JSON |
| `src/main.py` | CLI: carga, REPL, comandos |

## Decisoes de projeto

**Por que trechos (chunks) e nao documentos inteiros?**
O BM25 penaliza documentos longos: um contrato de 40 paginas quase nunca vence
o ranking, mesmo contendo a resposta exata. E o contexto do LLM nao comporta
contratos inteiros. Chunks de ~1200 caracteres com 200 de sobreposicao resolvem
os dois problemas.

**Por que reagrupar os trechos por contrato antes de enviar ao LLM?**
Enviar trechos soltos do mesmo contrato faz o modelo trata-los como documentos
diferentes e repetir a resposta ("outro trecho..."), o que aumenta alucinacao.
`format_context()` agrupa por arquivo e `merge_chunks()` remonta na ordem
original, removendo a sobreposicao.

**Por que `per_doc_limit` na busca?**
Sem limite por documento, um unico contrato ocupa todos os slots de contexto.
Com 10 contratos, o usuario normalmente quer comparar.

**Por que BM25 e nao embeddings?**
Custo zero, sem modelo extra, sem banco vetorial, e funciona bem para o
vocabulario fechado de contratos ("rescisao", "multa", "vigencia"). Busca
semantica entra quando a acuracia do BM25 virar o gargalo medido - nao antes.

**Por que cache por SHA-1?**
Extrair PDF e lento. O cache (`data/extractions/index.json`) e chaveado pelo
hash do conteudo, entao renomear ou mover o arquivo nao invalida a extracao.

**Por que temperatura 0.1?**
Tarefa de extracao, nao de escrita criativa. Quanto mais deterministico, menos
invencao.

## Limites conhecidos do MVP

- **PDF escaneado nao funciona** (sem OCR). O arquivo e ignorado com aviso.
- **Alucinacao existe.** Modelos pequenos inventam numero de clausula. O system
  prompt mitiga, nao elimina. Sempre confira com `/trechos`.
- **Lento em CPU.** Dezenas de segundos a minutos por resposta com 3B.
- **Indice em memoria**, reconstruido a cada execucao (rapido, via cache).
- **Sem multiusuario, sem autenticacao, sem API.** Chega na Semana 3.

## Proximos passos

- Semana 2: `src/extract_expiring.py` - datas de vencimento -> Excel
- Semana 3: `src/api.py` (FastAPI) + interface web
- Semana 4-5: validacao com contratos reais, ajuste de prompt
- Semana 6: demo comercial
