# Contribuindo - PAULUS Legal

## Ambiente

```bash
cd paulus/legal
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
```

## Antes de abrir PR

```bash
python tests/test_pipeline.py      # extracao, busca, contexto
python tests/test_organizador.py   # varredura, classificacao, plano, desfazer
```

## Regras que nao se negociam

1. **Nenhum documento de cliente no repositorio.** Contratos reais ficam em
   `data/test_contracts/`, que e ignorada pelo git. Para exemplos, use dados
   ficticios em `data/samples/`.
2. **Nada de chamada de API externa.** O produto vende privacidade: toda
   inferencia roda local, via Ollama. Nenhuma dependencia de nuvem entra aqui.
3. **O LLM so responde a partir do contexto recuperado.** Se uma mudanca
   permitir que ele responda "de cabeca", ela esta errada.
4. **Nenhuma operacao destrutiva sem plano, diario e desfazer.** O organizador
   move arquivos do cliente. Mudanca que remova a etapa de conferencia, o
   registro do movimento ou a reversao nao entra. Nada e apagado, nada e
   sobrescrito.
5. **Regra antes de modelo.** Data, valor e CPF/CNPJ saem por expressao
   regular. Chamar o LLM para isso custa 20s por documento e ainda arrisca
   alucinacao.

## Estilo

- Python 3.10+, type hints nos parametros e retornos publicos
- Comentario explica **por que**, nao **o que**
- Mensagens ao usuario em portugues; codigo e identificadores sem acento
  (evita dor de cabeca com encoding no console do Windows)

## Estrutura

Veja [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Reportando bugs

Abra uma issue com: comando executado, saida completa, versao do Python,
modelo Ollama usado. **Nunca cole trecho de contrato real na issue.**
