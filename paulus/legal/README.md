# PAULUS Legal

Co-worker de IA para escritorios juridicos. Le seus contratos, responde
perguntas sobre eles e cita a fonte. **100% local** - nenhum documento sai da
sua maquina.

Parte do [PAULUS](../README.md), produto vertical construido sobre o
[Coryphaeus](../../README.md).

## Em 30 segundos

```bash
cd paulus/legal
python -m venv venv && venv\Scripts\activate     # Windows
pip install -r requirements.txt
ollama pull llama3.2:3b

python src/desktop.py      # janela do programa
python src/api.py          # ou a interface no navegador (localhost:8000)
python src/main.py         # ou o chat no terminal
```

Detalhes em [docs/QUICKSTART.md](docs/QUICKSTART.md).

## O que ele faz hoje

- **Organiza o acervo**: varre as pastas que voce escolher, le cada documento,
  classifica por conteudo (tipo, partes, data, valor) e monta a arvore de
  pastas que voce definir - `{cliente}/{tipo}`, `{ano}/{mes}/{tipo}`, o que for.
  Voce confere e corrige a tabela antes de qualquer arquivo sair do lugar, e
  todo lote pode ser desfeito.
- **Janela do Windows**, nao aba de navegador
- Adicionar contratos, perguntar, buscar
- Le contratos em **PDF, DOCX, TXT e MD**
- Indexa por **BM25** com tokenizacao de portugues (acento e stopwords tratados)
- Responde perguntas com **Llama local via Ollama**, citando o arquivo de origem
- Mostra os trechos que o modelo leu, e **avisa quais contratos ficaram de fora**
  da analise
- Chat no terminal, para quem prefere

## O que ele ainda nao faz

- OCR de PDF escaneado
- Planilha de vencimentos

## Organizar o acervo

1. **Onde procurar** - marque as pastas (Documentos, Desktop, um caminho seu)
2. **Classificar** - regra resolve data, valor e CPF/CNPJ na hora; o modelo so
   entra no que sobra (~20s por documento nesses casos)
3. **Conferir** - tabela editavel: corrija cliente e tipo, desmarque o que nao
   deve entrar. Nada foi movido ate aqui
4. **Estrutura** - escolha o padrao de pastas e o destino, e veja o plano
5. **Aplicar** - so agora os arquivos se movem, com diario e botao de desfazer

Nada e apagado. Nada e sobrescrito - colisao de nome ganha sufixo.

## Exemplos de pergunta

```
Voce: Quais sao as clausulas de penalidade?
Voce: Qual e o prazo de vigencia do contrato da ACME?
Voce: Quanto e a multa por rescisao antecipada?
Voce: Quem sao as partes de cada contrato?
Voce: /buscar rescisao
```

## Seus dados

- `data/test_contracts/` - seus contratos reais. **Ignorada pelo git.**
- `data/samples/` - contratos ficticios, versionados, so para teste.
- `data/extractions/` - cache de texto extraido. Ignorada pelo git.

O `.gitignore` bloqueia commit acidental de documento de cliente. Confira com
`git status` antes de qualquer push.

## Aviso

PAULUS localiza e resume o que esta escrito nos documentos. Nao presta
consultoria juridica e pode errar - toda resposta deve ser conferida contra o
contrato original. Use `/trechos` para ver exatamente o que o modelo leu.

## Documentacao

- [ETAPAS.md](docs/ETAPAS.md) - o caminho das 16 telas prontas as 20 do manual
- [QUICKSTART.md](docs/QUICKSTART.md) - instalacao e uso
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - como funciona e por que
- [CONTRIBUTING.md](CONTRIBUTING.md) - como contribuir
