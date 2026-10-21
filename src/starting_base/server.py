"""Server MCP stdio: base di partenza da awesome-reverse-engineered."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from starting_base.index import assess, explain, list_categories as categories

mcp = MCPServer(
    "starting-base",
    instructions=(
        "Cerca in awesome-reverse-engineered se esiste già una base open source. "
        "Rispondi in italiano partendo dal campo verdetto. "
        "Usa solo cosa_copre, ruolo, dal_readme e limiti: non inventare funzioni. "
        "Non clonare un repository se l'utente non lo chiede. "
        "Un client non ufficiale può violare i termini del servizio."
    ),
)


@mcp.tool()
def assess_starting_base(
    query: str,
    language: str | None = None,
    category: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Dice se esiste già una base di partenza per un prodotto, protocollo o formato chiuso.

    query può essere una frase: restano i nomi significativi. language filtra la lingua in modo
    esatto; category è una sottostringa della categoria. Restituisce il verdetto
    (base pronta, base parziale, nessuna base) e, per ogni repo, come può essere usata.
    """
    try:
        return assess(query, language=language, category=category, limit=limit)
    except FileNotFoundError as exc:
        return {"verdetto": "nessuna base", "motivo": str(exc), "risultati": []}


@mcp.tool()
def explain_repo(repo: str) -> dict[str, Any]:
    """Scheda di un owner/repo già scelto: stato, licenza e aiuto concreto dal README.

    repo accetta owner/name oppure l'URL GitHub. Se non è nell'indice, il verdetto è nessuna base.
    """
    try:
        return explain(repo)
    except FileNotFoundError as exc:
        return {"verdetto": "nessuna base", "motivo": str(exc), "risultati": []}


@mcp.tool()
def list_categories() -> dict[str, Any]:
    """Elenca le categorie dell'indice, con il numero di progetti e il ruolo di ciascuna."""
    try:
        return categories()
    except FileNotFoundError as exc:
        return {"verdetto": "nessuna base", "motivo": str(exc), "categorie": []}


def main() -> None:
    mcp.run()
