# QUICKSTART - PAULUS Legal

Do zero ao primeiro "pergunta e resposta" sobre seus contratos.

## 1. Pre-requisitos

- Python 3.10 ou superior
- [Ollama](https://ollama.ai/download) instalado

```bash
ollama pull llama3.2:3b     # ~2 GB, roda em CPU
```

> Modelos maiores (`llama3.1:8b`, `qwen2.5:7b-instruct`) respondem melhor, mas
> ficam bem mais lentos em CPU. Comece com o 3b.

## 2. Instalar

```bash
cd paulus/legal

python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux

pip install -r requirements.txt
```

## 3. Testar com os contratos de exemplo

Os arquivos em `data/samples/` sao ficticios e servem para validar a instalacao:

```bash
python src/main.py --contracts data/samples --ask "Qual e o prazo de vigencia de cada contrato?"
```

## 4. Usar com seus contratos

```bash
# Copie PDFs/DOCXs para data/test_contracts/  (essa pasta NAO vai para o git)
python src/main.py
```

## 5. Comandos do chat

| Comando | O que faz |
|---|---|
| `/docs` | lista os contratos carregados |
| `/buscar TEXTO` | busca por palavra-chave, sem chamar o LLM (instantaneo) |
| `/trechos` | mostra os trechos usados na ultima resposta |
| `/top N` | quantos trechos vao para o LLM (padrao 5) |
| `/reindex` | reextrai a pasta (use depois de adicionar arquivos) |
| `/sair` | encerra |

## 6. Flags

```bash
python src/main.py --contracts ../outra/pasta   # outra pasta de contratos
python src/main.py --model llama3.1:8b          # outro modelo
python src/main.py --ask "pergunta"             # uma pergunta e sai
python src/main.py --reindex                    # ignora o cache de extracao
python src/main.py --no-stream                  # nao imprime token a token
```

Tambem da para fixar o modelo por variavel de ambiente:

```bash
set PAULUS_MODEL=llama3.1:8b        # Windows
export PAULUS_MODEL=llama3.1:8b     # Mac/Linux
```

## Problemas comuns

**"Ollama nao respondeu"** - rode `ollama serve` em outro terminal.

**"sem texto extraivel (PDF escaneado?)"** - o PDF e uma imagem. Precisa de OCR
(fora do escopo do MVP; por ora converta o arquivo antes).

**Resposta demorou minutos** - normal em CPU. Reduza com `/top 3`, use um modelo
menor, ou rode em maquina com GPU.

**Resposta errada ou inventada** - confira com `/trechos` se o trecho certo
chegou ao modelo. Se nao chegou, o problema e a busca (tente outras palavras).
Se chegou e a resposta esta errada, o problema e o modelo (tente um maior).
