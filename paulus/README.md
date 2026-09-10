# PAULUS — Primeiro Produto Vertical da Atos

**PAULUS** e o primeiro produto vertical construido sobre o
[**Coryphaeus**](../README.md) (Agent OS).

Um co-worker de IA que roda na infraestrutura do proprio cliente,
especializado por vertical. Nenhum dado sai do servidor.

## Estrutura

```
Coryphaeus (Agent OS)
    └── PAULUS (Produto Vertical)
        └── Legal (Vertical Inicial: Escritorios Juridicos)
```

## Verticais

| Vertical | Status | Pasta |
|---|---|---|
| **Legal** — escritorios juridicos | MVP: Semana 1 concluida | [legal/](legal/) |

### Legal

**Capacidades:**

| Capacidade | Status |
|---|---|
| Analise de contratos (pergunta e resposta com citacao da fonte) | Pronto |
| Busca por palavra-chave nos contratos | Pronto |
| Gestao de prazos e vencimentos (planilha) | Semana 2 |
| Interface web | Semana 3 |
| Criacao de documentos juridicos | Backlog |
| Assinatura digital (ICP-Brasil) | Backlog |

**Stack:**

- LLM: Llama local via Ollama (`llama3.2:3b` por padrao, configuravel)
- Backend: Python; FastAPI a partir da Semana 3
- Busca: BM25 sobre trechos; busca semantica so se a acuracia medida exigir
- Persistencia: cache em JSON no MVP; SQLite quando houver estado a guardar

**Timeline:** 4-6 semanas ate a primeira venda.

## Quick Start

```bash
cd legal

python -m venv venv
venv\Scripts\activate         # Windows
source venv/bin/activate      # Mac/Linux
pip install -r requirements.txt

# Instalar Ollama: https://ollama.ai/download
ollama pull llama3.2:3b

# Testar com os contratos ficticios de exemplo
python src/main.py --contracts data/samples --ask "Qual o prazo de vigencia de cada contrato?"

# Usar com seus contratos (essa pasta fica fora do git)
mkdir -p data/test_contracts
python src/main.py
```

Veja [legal/docs/QUICKSTART.md](legal/docs/QUICKSTART.md) para detalhes e
[legal/docs/ARCHITECTURE.md](legal/docs/ARCHITECTURE.md) para as decisoes de projeto.

---

**Mantra:** *"Atos builds Coryphaeus. Coryphaeus powers PAULUS."*
