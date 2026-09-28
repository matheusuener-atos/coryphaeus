# Medição da conversa sobre documentos

O banco de provas de sempre (`tools/demo/roteiro.py`) mede o PAULUS nos
documentos fictícios da demonstração — os mesmos usados para ajustar o
prompt. É teto, não medida. A medição de verdade é sobre documentos reais do
escritório, com perguntas que alguém do escritório faria.

`tools/medir.py` roda um conjunto de perguntas com resposta conhecida e
imprime:

| Número | O que é |
| --- | --- |
| acerto | quantas respostas passaram na conferência (`alguma`, `todas`, `nunca`) |
| latência p50 / p95 | segundos da pergunta até o fim da resposta |
| entrada p50 / p95 | tokens que o modelo leu (o `prompt_eval_count` do Ollama) |
| Recall@20, Recall@6 | das frases esperadas, a fração que a busca põe entre os 20 / 6 primeiros trechos |
| MRR@6 | 1 ÷ a posição do primeiro trecho, entre os 6 primeiros, que traz uma frase esperada |
| no contexto | das frases esperadas, a fração que estava no que foi de fato mandado ao modelo |

```text
venv\Scripts\python.exe tools\medir.py              conjunto da demonstração
venv\Scripts\python.exe tools\medir.py --real       conjunto real
venv\Scripts\python.exe tools\medir.py --so-busca   só a busca, sem o modelo (segundos)
```

O resultado vai para `<dados>/medicao/medir-<conjunto>-<data>.json`. Cada
pergunta feita pela conversa também deixa uma linha em
`<dados>/medicao/perguntas.jsonl` (modelo, janela, tokens, tempos, caminho) —
só números, nunca o texto. **Nada disso sai da máquina.**

## Onde fica o conjunto real

`data/medicao/conjunto-real.jsonl`, na pasta de dados do PAULUS (no programa
instalado, `%LOCALAPPDATA%\PAULUS\dados\medicao\`). **Fora do git**: são
perguntas sobre documentos de cliente, e as frases esperadas são trechos
deles.

## O formato

Uma pergunta por linha, em JSON. Linha começando com `//` é comentário. O
exemplo completo, sobre a demonstração, está em
`tools/demo/conjunto-demo.jsonl`.

```json
{"pergunta": "qual o foro do contrato de transporte?", "tipo": "fato", "alguma": ["Santarém"], "trechos_esperados": ["foro da Comarca de Santarém"]}
```

| Campo | Para que serve |
| --- | --- |
| `pergunta` | como a pessoa perguntaria, com as palavras dela |
| `tipo` | `fato`, `lista`, `ausencia`, `consequencia`, `comparacao` ou `continuacao` |
| `alguma` | a resposta passa se trouxer **pelo menos um** destes textos |
| `todas` | lista de listas: **cada** grupo precisa aparecer (um dos textos do grupo basta) |
| `nunca` | a resposta **falha** se trouxer algum destes (o valor de outro contrato, o nome errado) |
| `minimo` | `[n, grupos]`: pelo menos `n` dos grupos aparecem |
| `trechos_esperados` | frases **literais e curtas** do documento que têm de estar no contexto para a pergunta ter resposta |
| `documentos` | opcional: a pergunta é só sobre estes arquivos (o nome do arquivo, como aparece em Documentos) |
| `continua` | opcional: `true` quando a pergunta depende da anterior e vai na mesma conversa |
| `caminho` | opcional: `documentos` (padrão), `programa` ou `pergunta` |

A conferência ignora acento e maiúscula. `trechos_esperados` também ignora
quebra de linha e espaço duplo.

## Como anotar, na prática

1. **Escolha de 10 a 20 documentos** que o escritório usa de verdade:
   contratos, petições, procurações, notificações, decisões. Misture tamanhos
   — um de duas páginas e um de trinta medem coisas diferentes.
2. **Escreva de 30 a 50 perguntas** sobre eles, como alguém do escritório
   perguntaria ao PAULUS. Cubra os seis tipos:
   - **fato** — "qual o valor da causa?", "quem assina pela ré?";
   - **lista** — "quais são os pedidos?", "quais as datas das parcelas?";
   - **ausência** — algo que o documento **não** diz: "qual a multa por atraso
     no aluguel?" num contrato sem essa multa. A resposta certa é dizer que
     não está lá; em `alguma` vão as formas de dizer isso ("não há", "não
     prevê", "não menciona"…) e em `nunca` o número que o modelo inventaria;
   - **consequência** — "o que acontece se a ré não pagar no prazo?";
   - **comparação entre dois documentos** — "o que o aditivo mudou no
     contrato?";
   - **continuação** — de 8 a 10 perguntas que só fazem sentido depois da
     anterior ("e a multa?", "e o foro?"), com `"continua": true`. A primeira
     da sequência vai sem `continua`.
3. **Para cada pergunta, copie do documento a frase que responde** e ponha
   em `trechos_esperados` — curta (de 4 a 12 palavras), **literal**, sem
   corrigir erro de digitação do original. Frase, e não número de página ou
   de trecho: os trechos mudam de tamanho nas próximas etapas, e a frase
   continua a mesma. Na ausência, a frase é a da cláusula onde a resposta
   estaria se existisse (a do aluguel, quando se pergunta da multa do
   aluguel).
4. **Em `alguma`/`todas`, ponha o que tem de aparecer na resposta**, com as
   variações de escrita ("10 dias", "dez dias", "10 (dez)").
5. Rode `tools\medir.py --real --so-busca` primeiro: em segundos ele diz se
   alguma frase esperada não existe em documento nenhum — quase sempre é
   frase copiada errada (Recall@20 zerado numa pergunta).
6. Depois `tools\medir.py --real`, com o Ollama ligado. Leva de 30 s a 1 min
   por pergunta nesta máquina.

## O que cada etapa do plano de IA registra

Cada etapa a partir da I2 roda `tools/medir.py` e anota os números em
`docs/PROGRESSO-IMPLEMENTACAO.md`: acerto, p50/p95, tokens de entrada e os
números da busca. É assim que se sabe se uma mudança melhorou ou só mudou.
