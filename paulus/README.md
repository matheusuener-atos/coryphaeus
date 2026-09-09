# PAULUS — Primeiro Produto Vertical da Atos

**PAULUS** é o primeiro produto vertical construído sobre **Coryphaeus** (Agent OS).

## Estrutura

\\\
Coryphaeus (Agent OS)
    └── PAULUS (Produto Vertical)
        └── Legal (Vertical Inicial: Escritórios Jurídicos)
\\\

## Verticals

### Legal ⚖️
Especializado em trabalho jurídico para escritórios de advocacia.

**Capacidades:**
- 🔍 Análise de contratos
- 📋 Gestão de prazos e vencimentos
- 📄 Criação de documentos jurídicos
- 🖊️ Assinatura digital (ICP-Brasil)
- 💾 Planilhas de gestão

**Stack:**
- LLM: Llama 2 7B (Ollama local)
- Backend: Python + FastAPI
- Busca: BM25 + Semantic Search (futuro)
- Database: SQLite (MVP) → PostgreSQL (produção)

**Timeline:** 4-6 semanas até primeira venda

---

## Quick Start

\\\ash
cd legal
python -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows
pip install -r requirements.txt

# Instalar Ollama: https://ollama.ai/download
ollama pull llama2:7b-chat

# Adicionar seus contratos
mkdir -p data/test_contracts
# Copie seus PDFs para data/test_contracts/

# Rodar MVP
python src/main.py
\\\

Veja [legal/docs/QUICKSTART.md](legal/docs/QUICKSTART.md) para detalhes.

---

**Mantra:** *"Atos builds Coryphaeus. Coryphaeus powers PAULUS."*
