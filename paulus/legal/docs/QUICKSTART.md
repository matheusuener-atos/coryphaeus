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

## 4. Abrir o programa

```bash
python src/desktop.py
```

Abre uma janela do Windows com a interface. E o formato para usar no dia a dia
e para demonstrar - sem barra de endereco, sem cara de site. A janela tambem da
acesso ao seletor de pasta do proprio Windows, que o navegador nao permite.

Se preferir o navegador (ou se o pywebview nao instalar), a mesma interface
roda em <http://localhost:8000>:

## 5. Interface no navegador

```bash
python src/api.py
```

Abra <http://localhost:8000>. Pela tela voce adiciona contratos (botao
"Adicionar contratos"), pergunta na aba **Analise** e faz busca instantanea na
aba **Busca**.

O servidor escuta so em `127.0.0.1` de proposito: ninguem na rede local
alcanca os documentos. Para parar, Ctrl+C no terminal.

```bash
python src/api.py --contracts data/samples   # abrir com os exemplos
python src/api.py --port 8080                # outra porta
python src/api.py --model llama3.1:8b        # outro modelo
```

Toda resposta traz **"Trechos que o modelo leu"**. Abra antes de confiar: e o
texto exato que o modelo recebeu. Se um contrato nao tiver trecho relevante
para a pergunta, a tela avisa quais ficaram de fora - a resposta nao fala por
eles.

## 6. Organizar o acervo

A aba **Organizar** varre suas pastas, le cada documento e monta a estrutura de
pastas que voce definir.

1. **Onde procurar** - marque as pastas sugeridas ou digite um caminho
   (`D:\Escritorio\Contratos`). Pastas de sistema sao puladas: nao ha contrato
   dentro de `Windows/` ou `AppData/`.
2. **Classificar** - tipo, partes, data, valor e CPF/CNPJ. Data e valor saem por
   regra, instantaneos. O modelo entra so quando a regra nao decide o tipo ou
   nao acha as partes, e ai custa ~20s por documento. O resultado fica em cache
   por conteudo: reclassificar o mesmo acervo e instantaneo.
3. **Conferir** - a tabela e editavel. Cliente e tipo sao palpite do programa;
   corrija o que estiver errado e desmarque o que nao deve entrar. **Nada foi
   movido ate aqui.**
4. **Estrutura** - escolha o padrao (`{cliente}/{tipo_rotulo}`,
   `{ano}/{mes_nome}/{tipo_rotulo}`, e por ai) e a pasta de destino. "Ver o
   plano" mostra exatamente quais pastas serao criadas.
5. **Aplicar** - so aqui os arquivos se movem.

Campos disponiveis no padrao: `{cliente}`, `{tipo}`, `{tipo_rotulo}`, `{ano}`,
`{mes}`, `{mes_nome}`, `{confianca}`. Texto fixo tambem vale:
`Contratos/{ano}/{cliente}`.

Documento sem o campo do padrao (sem data, sem cliente) cai numa pasta
`_A revisar` em vez de sumir no meio do acervo.

### Desfazer

Todo lote aplicado vira um diario em `data/diarios/`. O botao **Desfazer**
devolve cada arquivo exatamente ao caminho de origem e limpa as pastas que
ficaram vazias. Nada e apagado e nada e sobrescrito: se ja existir arquivo com
o mesmo nome no destino, o novo entra como `nome (2).pdf`.

## 7. Usar com seus contratos (pelo terminal)

```bash
# Copie PDFs/DOCXs para data/test_contracts/  (essa pasta NAO vai para o git)
python src/main.py
```

## 8. Comandos do chat (CLI)

| Comando | O que faz |
|---|---|
| `/docs` | lista os contratos carregados |
| `/buscar TEXTO` | busca por palavra-chave, sem chamar o LLM (instantaneo) |
| `/trechos` | mostra os trechos usados na ultima resposta |
| `/top N` | quantos trechos vao para o LLM (padrao 5) |
| `/reindex` | reextrai a pasta (use depois de adicionar arquivos) |
| `/sair` | encerra |

## 9. Flags do CLI

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
