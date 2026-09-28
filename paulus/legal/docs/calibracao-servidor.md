# Calibração compartilhada: o endereço no servidor

A estimativa de quanto cada modelo de IA demora numa máquina (`src/maquina.py`) vem de **amostras**: uma máquina testada mais um modelo medido nela. As que vão com o programa (`src/calibracao_base.json`) são de uma máquina só. Quem escolhe **Participar da calibração** manda as amostras da própria máquina e recebe as de todos, e a estimativa melhora para todo mundo.

## O que existe

| Onde | O quê |
|---|---|
| `worker/index.js` (raiz do repositório) | `POST /api/calibracao` recebe amostras; `GET /api/calibracao` devolve todas |
| `src/calibracao_remota.py` | manda, baixa e confere as amostras de fora |
| `/api/calibracao` (programa) | a escolha de participar, e o "ver o que é enviado" |
| Configurações › Modelos e boas-vindas | o interruptor "Participar da calibração", **desligado de fábrica** |

## O que vai, exatamente

O que `maquina.amostra()` monta, e a tela mostra antes em "ver o que é enviado":

```json
{"maquina": {"id": "d42ce2e418a5", "versao": 2, "processador": "13th Gen Intel(R) Core(TM) i7-1360P",
             "nucleos": 12, "ram_total_gb": 16.9, "avx2": true, "banda_gbs": 42.8, "gflops": 279.1, "na_bateria": true},
 "gpu": false, "modelo": "llama3.2:3b", "tamanho_gb": 2.02, "parametros_b": 3.2, "quantizacao": "Q4_K_M",
 "escrita_tps": 11.3, "leitura_tps": 59.7}
```

O `id` é um resumo (SHA-1 cortado) de processador, núcleos e memória. Serve para trocar a amostra antiga da mesma máquina, e não identifica pessoa. Nada do escritório vai: nem documento, nem nome, nem e-mail.

## Quando

- Ligar o interruptor manda as amostras já medidas nesta máquina e baixa as de todos. Se o modelo padrão já está instalado e nunca foi medido, ele é medido uma vez, sozinho, uns 20 segundos depois, e a amostra vai.
- Um modelo que termina de baixar com o interruptor ligado também é medido sozinho, uma vez. É o caso de quem liga a chave no assistente de configuração: o modelo escolhido lá baixa, é medido e a amostra vai. Sem isso, só quem clicava em **Medir** mandava algo.
- Cada **Medir** manda a amostra nova.
- As de todos são relidas uma vez por dia, quando a tela de modelos ou a recomendação é aberta.
- Desligado, nada sai e nada é lido.

## O servidor

O Worker confere cada amostra campo a campo (tipos, faixas, formato do texto) e **joga fora o resto**: um campo a mais some. O pedido passa pelo mesmo limite das rotas de pagamento (10 por minuto por endereço de internet), e aceita até 50 amostras por pedido.

Tudo fica numa chave só do KV `APOIOS`, que o Worker já tem: `calibracao:todas`. É uma amostra por máquina e modelo, e medir de novo troca a antiga. Ficam as 5.000 mais recentes. Não há configuração nova no Cloudflare.

Duas gravações ao mesmo tempo podem perder uma delas (o KV não tem transação). Para medidas que se repetem a cada Medir, isso não pesa.

### Pôr no ar

O Worker vai ao ar com o site, **a cada push** no `main` (Cloudflare Workers Builds, `wrangler.jsonc`). Não há outro passo.

### Conferir o que chegou

```
npx wrangler kv key get --binding APOIOS "calibracao:todas" --remote
```

ou abrir `https://paulus.ia.br/api/calibracao` no navegador (a resposta fica em cache por uma hora).

### Apagar tudo

```
npx wrangler kv key delete --binding APOIOS "calibracao:todas" --remote
```

## Como o programa lê

- O endereço é `https://paulus.ia.br/api/calibracao`. Para testar com o Worker local (`npx wrangler dev`), abra o PAULUS com a variável `PAULUS_CALIBRACAO_URL=http://127.0.0.1:8787/api/calibracao`.
- As amostras de fora ficam em `dados/calibracao_servidor.json`.
- Antes de entrar na conta, cada amostra de fora é conferida: a escrita medida tem de ficar entre **0,2 e 5 vezes** o que a física calibrada prevê para aquela máquina e modelo. Amostra falsa ou de máquina com placa de vídeo fica de fora.
- A estimativa soma a base, as amostras daqui e as de fora conferidas. A correção pela medida desta máquina (`correcao_local`) continua valendo por cima.

## Levar a calibração de todos para dentro do programa

Para a versão seguinte já sair calibrada com as máquinas de todos, junte as amostras do servidor à base:

```
curl https://paulus.ia.br/api/calibracao -o todas.json
venv\Scripts\python.exe -c "import json; from pathlib import Path; b=json.loads(Path('src/calibracao_base.json').read_text(encoding='utf-8')); t=json.loads(Path('todas.json').read_text(encoding='utf-8')); b['amostras']+=t['amostras']; Path('src/calibracao_base.json').write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding='utf-8')"
```

Confira `tests/test_maquina.py` e `roteiro.py` depois.
