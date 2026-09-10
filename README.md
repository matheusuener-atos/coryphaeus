# Coryphaeus

Agent OS for orchestrating local AI agents and tools.

```
ATOS (empresa)
  └── CORYPHAEUS (Agent OS / engine de orquestracao)
      └── PAULUS (produto vertical)
          └── legal (escritorios juridicos)
```

> Atos builds Coryphaeus. Coryphaeus powers PAULUS.

## Produtos

| Produto | Vertical | Status |
|---|---|---|
| [PAULUS Legal](paulus/legal/) | Escritorios juridicos | MVP - Semana 1 concluida |

## Comecando

```bash
cd paulus/legal
python -m venv venv && venv\Scripts\activate     # Windows
pip install -r requirements.txt
ollama pull llama3.2:3b

python src/main.py --contracts data/samples --ask "Qual o prazo de vigencia de cada contrato?"
```

Guia completo: [paulus/legal/docs/QUICKSTART.md](paulus/legal/docs/QUICKSTART.md)

## Principios

- **Local por padrao.** Nenhum dado de cliente sai da infraestrutura de quem usa.
- **Sem dependencia de nuvem.** Inferencia via Ollama, na maquina do cliente.
- **Resposta rastreavel.** Toda afirmacao cita o documento de origem.
