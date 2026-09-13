# Arquitetura - PAULUS Legal (MVP)

## Onde isso se encaixa

```
ATOS (empresa)
  └── CORYPHAEUS (Agent OS / orquestracao)
      └── PAULUS (produto)
          └── legal (vertical: escritorios juridicos)
```

## Interfaces

Duas portas de entrada para a mesma logica:

- `src/desktop.py` - janela nativa do Windows (pywebview) sobre a mesma interface
- `src/api.py` + `frontend/` - servidor local, tambem acessivel pelo navegador
- `src/main.py` - chat no terminal

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
| `src/api.py` | Backend web (FastAPI): upload, busca, resposta em streaming |
| `frontend/index.html` | Interface: a pagina (marcacao e o script do tema), sem build, sem dependencia externa |
| `frontend/css/`, `frontend/js/` | O CSS e o JS da interface, um arquivo por tela, na ordem em que a pagina os liga; scripts classicos com escopo global compartilhado |
| `src/desktop.py` | Janela nativa + ponte para o seletor de pasta do Windows |
| `src/scan.py` | Varredura de pastas, poda de pastas de sistema |
| `src/classify.py` | Metadados por documento: regra primeiro, modelo no que sobra |
| `src/organize.py` | Padrao de pastas, plano, aplicacao, diario e desfazer |
| `src/habilidades.py` | Registro do que o programa sabe fazer - fonte unica |
| `src/jobs.py` | Trabalhos (conversas) com etapas, atividade e persistencia |
| `src/recursos.py` | Medidores reais da maquina |
| `src/pastas.py` | Navegacao de pastas para a escolha do escopo |

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

**Por que a interface e um servidor local e nao uma pagina hospedada?**
O navegador so alcanca o Ollama se a pagina vier da mesma maquina. O servidor
escuta em `127.0.0.1` (nao em `0.0.0.0`): documento de cliente nao deve ficar
exposto nem na rede local do escritorio.

**Por que a resposta declara quais contratos ficaram de fora?**
A busca pode nao achar trecho relevante em parte dos contratos. Se a tela nao
disser isso, o advogado le "nao ha clausula de penalidade" onde o certo e "nao
procurei nesse contrato". Num produto de prazos, silencio vira prazo perdido.

**Por que ha um fallback por contagem de termos na busca?**
O IDF do BM25 so e positivo para termos presentes em menos da metade dos
trechos indexados. Com um ou dois contratos - o caso de quem acabou de subir o
primeiro - termos relevantes zeram e a busca devolvia vazio. Quando nenhum
trecho pontua, caimos para "quantos termos da pergunta aparecem aqui".

**Por que regra antes de modelo na classificacao?**
Medido em 2026-09-09: ~20-27s por documento quando o llama3.2:3b e chamado. Um
acervo de 300 documentos daria quase 2 horas. Data, valor e CPF/CNPJ saem por
expressao regular em milissegundos e sem chance de alucinacao. O modelo fica
para tipo e partes, e so quando a regra nao decidiu - nos contratos de teste,
isso cortou as chamadas pela metade.

**Por que o cache de classificacao tem versao?**
O cache e por SHA-1 do conteudo, entao melhorar o classificador nao invalidaria
nada: o arquivo nao mudou, mas a regra mudou. `VERSAO_CLASSIFICADOR` sobe a cada
alteracao de heuristica, prompt ou vocabulario, e o cache inteiro e descartado.

**Por que o plano nao toca em disco?**
Reorganizar o acervo de um escritorio e destrutivo e dificil de conferir no
olho. `montar_plano` e uma funcao pura: produz a tabela origem -> destino e nao
cria nem uma pasta. O usuario corrige cliente e tipo, desmarca o que nao quer, e
so entao `aplicar_plano` executa.

**Por que o diario e gravado ANTES de cada movimento?**
Se o processo morrer no meio do lote, o diario ja contem o que foi feito - e o
desfazer funciona mesmo assim. Gravar depois deixaria arquivos movidos sem
registro, que e exatamente o estado impossivel de reverter.

**Por que colisao vira sufixo em vez de sobrescrever?**
Dois contratos com o mesmo nome de arquivo em pastas diferentes sao comuns num
acervo. Sobrescrever apagaria um documento de cliente em silencio. O segundo
entra como `nome (2).pdf`.

**Por que um registro de habilidades?**
Cada coisa que o programa faz e uma entrada em `src/habilidades.py`, com
estado, requisitos e expectativa de tempo. A pagina "O que eu sei fazer", as
portas de entrada da tela inicial e os tipos de trabalho leem dai. Sem isso,
acrescentar capacidade obriga a mexer em tres lugares e a interface passa a
oferecer coisa que nao funciona.

**Por que o catalogo lista o que ainda nao existe?**
Marcado como "em breve", sem botao. Esconder o roadmap faria a pessoa procurar
uma funcao que nao esta la; listar promessa como se funcionasse e pior ainda.

**Por que temperatura 0.1?**
Tarefa de extracao, nao de escrita criativa. Quanto mais deterministico, menos
invencao.

## Limites conhecidos do MVP

- **PDF escaneado nao funciona** (sem OCR). O arquivo e ignorado com aviso.
- **Alucinacao existe.** Modelos pequenos inventam numero de clausula. O system
  prompt mitiga, nao elimina. Sempre confira com `/trechos`.
- **Quem e "o cliente" e palpite.** O programa nao tem como saber qual das
  partes do contrato e cliente do escritorio; ele elege a primeira citada no
  documento. Por isso a tabela do organizador e editavel antes de mover.
- **Lento em CPU.** Dezenas de segundos a minutos por resposta com 3B.
- **Indice em memoria**, reconstruido a cada execucao (rapido, via cache).
- **Sem multiusuario e sem autenticacao.** A interface pressupoe uma pessoa
  na propria maquina. Antes de rodar no servidor do escritorio, isso precisa
  existir.

## Proximos passos

- `src/extract_expiring.py` - datas de vencimento -> Excel
- Semana 4-5: validacao com contratos reais, ajuste de prompt
- Semana 6: demo comercial
