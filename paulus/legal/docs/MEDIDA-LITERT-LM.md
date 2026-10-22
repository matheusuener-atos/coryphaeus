# LiteRT-LM (Google AI Edge) contra o Ollama — medido em 22/10/2026

Pergunta: vale trocar o motor da IA local (Ollama + llama3.2:3b) pelo LiteRT-LM
do Google AI Edge? Medido nesta máquina: 16 GB de RAM, 16 núcleos, GPU Intel
Iris Xe, sem placa NVIDIA.

Como foi medido: `tools/litert_ponte.py` imita a API do Ollama com o LiteRT-LM
por trás. O PAULUS e o banco de provas rodaram sem nenhuma mudança: só trocou
quem escreve e julga, e a busca continuou no bge-m3 do Ollama. Pacote
`litert-lm` 0.18.1 (pip, com versão para Windows), modelo `gemma-4-E2B-it` do
`litert-community` (2,4 GB para CPU e 1,9 GB para GPU). Não existe Llama 3.2 3B
em LiteRT: mudaram o motor e o modelo ao mesmo tempo.

## Banco de provas (`tools/demo/roteiro.py --tudo`, 41 perguntas)

| | certas | documentos: mediana | documentos: máximo |
|---|---|---|---|
| Ollama + llama3.2:3b (CPU) | **41/41** | 18,5 s | 57,7 s |
| LiteRT + Gemma 4 E2B (CPU) | 37/41 | 19,7 s | 31,3 s |
| LiteRT + Gemma 4 E2B (GPU Iris Xe) | 37/41 | **5,7 s** | **13,7 s** |

As 4 falhas do Gemma são do modelo, não da ponte, e são as mesmas na CPU e na
GPU (temperatura zero):

- multa por atraso no aluguel da Clínica (o contrato não prevê): **inventou** "3
  aluguéis", tirado da cláusula de devolução antecipada;
- prazo da notificação à Rio Fresco ("10 (dez) dias"): respondeu uma data
  inventada;
- viagens somando o aditivo: citou 8 + 2, mas não deu o total;
- valor da causa do João Batista (não consta): disse que não consta só no fim.

## Leitura do prompt (o gargalo em CPU)

Prompt de ~3.900 tokens, fora do cache:

| | leitura | escrita |
|---|---|---|
| Ollama + llama3.2:3b (CPU) | 73–77 s (~53 tok/s) | ~8 tok/s |
| LiteRT + Gemma 4 E2B (CPU) | 19 s | 13 tok/s |
| LiteRT + Gemma 4 E2B (GPU) | 4,6–8,9 s | 20 tok/s |

O Ollama só lê de graça quando o começo do prompt se repete (o cache dele). O
LiteRT 0.18.1 não guarda nada entre conversas.

## Juiz de uma letra (`tests/medir_juiz.py`, 24 frases)

| | no limiar 0,55 | mediana |
|---|---|---|
| Ollama + llama3.2:3b | 23/24, nenhuma desviada | 2,3 s |
| LiteRT + Gemma 4 E2B (CPU) | 21/24, 2 tiradas dos documentos | 6,9 s |

O Gemma espalha mais as notas (de 0,00 a 0,77), mas erra com convicção: só chega
a 23/24 a partir do limiar 0,80. Na 0.18.1, `run_text_scoring` aceita um alvo
por chamada e não há `Session.clone`, então cada letra lê o prompt de novo. Na
GPU, a nota não existe (`UNIMPLEMENTED ... GpuArtisan`).

## O que funcionou e o que não

- Funcionou: instalação por pip no Windows (25 MB, sem amarra de versão do
  Python), carga em menos de 5 s, português correto e JSON forçado por esquema
  (`ResponseFormat.json` + LLGuidance), com CPF e valor certos.
- Não funcionou: o download pelo cliente do Hugging Face (`hf`) travou, e o
  curl com retomada resolveu. A nota de letras não existe na GPU.

## Segunda rodada: modelos maiores no mesmo motor

| | certas | documentos: mediana | documentos: máximo |
|---|---|---|---|
| Ollama + llama3.2:3b (CPU) | 41/41 | 18,5 s | 57,7 s |
| LiteRT + Gemma 4 E2B (GPU) | 37/41 | 5,7 s | 13,7 s |
| LiteRT + Gemma 4 E4B (GPU, 2,8 GB) | 40/41* | 14,5 s | 31,7 s |
| LiteRT + Qwen3-4B-Instruct-2507 | inviável | | |

\* A única "falha" do E4B é uma resposta certa: "Não achei o valor da causa...
nos documentos". A checagem aceita "não encontrei" e "não consta", mas não "não
achei". Na prática, foram 41/41. A régua não foi mudada para caber o
candidato.

O Qwen3-4B do `litert-community` foi convertido com janela fixa de 2.048 tokens
(`litert-lm describe`: Max Context Tokens 2048, Is Dynamic Context NO). As
perguntas do PAULUS têm 2.500–2.800 tokens, e o motor as recusa. Além disso, o
template de conversa embutido nesse arquivo não roda na 0.18.1, e a ponte ganhou
`--template chatml` para isso. Converter com janela maior exige o `litert-torch`,
que não converte no Windows. Num teste solto, o Qwen ainda disse que o prazo de
contestação no CPC é de 30 dias (são 15 úteis).

O juiz do E4B não foi medido: na GPU não há nota de letras, e só a versão GPU
foi baixada (a de CPU tem 3,4 GB).

## Conclusão

O motor é bom; a troca inteira ainda não compensa.

- O LiteRT-LM lê o prompt 4x mais rápido na CPU e de 8 a 16x mais rápido numa
  GPU Intel comum de notebook, que o Ollama não usa aqui.
- O Gemma 4 E2B é rápido, mas inventa onde o llama3.2:3b diz "não consta".
  Isso é inaceitável num produto jurídico.
- O Gemma 4 E4B na GPU acerta tanto quanto o llama3.2:3b. O ganho, porém, é
  modesto: mediana de 14,5 s contra 18,5 s, e pior caso caindo pela metade.
- Trocar de vez exigiria ainda:
  - levar os embeddings para o LiteRT (EmbeddingGemma 2 no lugar do bge-m3,
    com reindexação e uma nova medida da busca);
  - manter um segundo motor na CPU só para o juiz.

  Sem isso, o Ollama continua instalado do mesmo jeito.
- Como a nuvem é o padrão e o modelo local é só reserva, a troca não paga o
  custo hoje.

O que pode valer depois: o E4B na GPU como opção de reserva para quem tem GPU
Intel, ao lado do Ollama; e o LiteRT-LM para a web no "Pensar no aparelho", no
lugar do wllama, quando sair do "early preview".
