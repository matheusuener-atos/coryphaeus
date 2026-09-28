"""
PAULUS - Acesso de fora (`acesso-remoto/v0`).

O computador do escritorio continua sendo o PAULUS. O advogado so ganha um
caminho seguro ate ele, de casa ou do celular: documentos, metadata e modelo
nunca saem daqui; o que trafega e a interface, pelo tunel da Cloudflare.

O servidor continua escutando so em 127.0.0.1. O problema e que o agente do
tunel (cloudflared) tambem conecta de 127.0.0.1 - o endereco de origem nao
separa quem esta sentado na frente da maquina de quem chega pela internet. E
cabecalho (Cf-Connecting-IP, X-Forwarded-For) qualquer programa local forja.
Quem separa e a CHAVE DA JANELA (chave.py): sem ela, a requisicao e remota.

Os modulos:

    chave.py      a chave da janela e a sessao local (R1)
    porteiro.py   o middleware que classifica e barra cada requisicao
    contas.py     contas, senha, TOTP, sessoes remotas e forca bruta (R2)
    politicas.py  o que cada rota permite a quem esta de fora (R3)
    fila.py       a fila unica do modelo local (R4)
    tunel.py      o cloudflared como processo filho e a porta fixa (R6)
    provisao.py   a conversa com o Worker de paulus.ia.br (R7)
    auditoria.py  "quem acessou", com hash encadeado (R8)
    energia.py    nao deixar o Windows suspender; abrir com o Windows (R9)

Tudo atras da preferencia `acesso_remoto`, desligada de fabrica. Desligada,
toda requisicao sem a chave recebe 403 - inclusive a do navegador da propria
maquina. Isso fecha, de quebra, o acesso de qualquer outro programa do
computador ao PAULUS, que existia antes.
"""
