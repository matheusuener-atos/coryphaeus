"""
O número da DPS: sem repetir e sem buraco.

A série e o número compõem a identidade da DPS (TSIdDPS), e a Sefin recusa
a segunda DPS com a mesma série, número, município e CNPJ que já gerou nota
(E0014). Repetir número, então, é ter a segunda nota recusada — ou, pior,
confundir duas notas. Pular número não é ilegal, mas o prompt pede sem
buraco, e o contador agradece.

O número é reservado numa transação só (BEGIN IMMEDIATE), na hora de
assinar — não no rascunho, que pode ser descartado. A nota rejeitada fica com
o número dela para a nova tentativa (mesma identidade). A nota descartada
antes de virar NFS-e devolve o número, e o próximo a reservar pega o menor
devolvido primeiro.

Fica tudo na base (paulus.db), que vai inteira no backup.
"""

from __future__ import annotations


def reservar(base, ambiente: str, serie: str) -> int:
    serie = str(int(serie))

    def _faz(con) -> int:
        livre = con.execute(
            "SELECT numero FROM nfse_numeros_livres WHERE ambiente = ? AND serie = ? ORDER BY numero LIMIT 1",
            (ambiente, serie)).fetchone()
        if livre:
            con.execute("DELETE FROM nfse_numeros_livres WHERE ambiente = ? AND serie = ? AND numero = ?",
                        (ambiente, serie, livre[0]))
            return int(livre[0])
        con.execute("INSERT OR IGNORE INTO nfse_numeracao (ambiente, serie, ultimo) VALUES (?, ?, 0)",
                    (ambiente, serie))
        con.execute("UPDATE nfse_numeracao SET ultimo = ultimo + 1 WHERE ambiente = ? AND serie = ?",
                    (ambiente, serie))
        return int(con.execute("SELECT ultimo FROM nfse_numeracao WHERE ambiente = ? AND serie = ?",
                               (ambiente, serie)).fetchone()[0])

    return base.transacao(_faz)


def devolver(base, ambiente: str, serie: str, numero: int) -> None:
    """Só para número de nota que NUNCA virou NFS-e (descartada depois de rejeitada)."""
    serie = str(int(serie))
    base.escrever("INSERT OR IGNORE INTO nfse_numeros_livres (ambiente, serie, numero) VALUES (?,?,?)",
                  (ambiente, serie, int(numero)))


def proximo(base, ambiente: str, serie: str) -> int:
    """O número que a próxima reserva daria (só para mostrar; não reserva)."""
    serie = str(int(serie))
    livre = base.um("SELECT MIN(numero) n FROM nfse_numeros_livres WHERE ambiente = ? AND serie = ?", (ambiente, serie))
    if livre and livre["n"]:
        return int(livre["n"])
    linha = base.um("SELECT ultimo FROM nfse_numeracao WHERE ambiente = ? AND serie = ?", (ambiente, serie))
    return (int(linha["ultimo"]) if linha else 0) + 1
