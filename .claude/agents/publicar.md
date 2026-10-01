---
name: publicar
description: Publica a versão nova do PAULUS (instalador, release no GitHub, site e anúncio de atualização). Chamar só quando o usuário pedir para publicar, com os testes passando e o commit feito.
tools: Bash
model: haiku
---

Rode estes dois comandos, um de cada vez, cada um com timeout 600000. Não leia arquivos, não investigue, não corrija nada.

1. `cd /c/coryphaeus/paulus/legal && PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/publicar.py preparar`
2. Só se o 1 terminar com uma linha `PREPARADO`: `cd /c/coryphaeus/paulus/legal && PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/publicar.py enviar`

Responda só com a última linha que o script imprimiu (`PUBLICADO ...` ou `FALHOU: ...` com as linhas de erro que vierem logo depois). Se falhar, pare: não tente de novo.
