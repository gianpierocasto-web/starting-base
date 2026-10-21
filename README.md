# starting-base

Plugin Cursor. Interroga [awesome-reverse-engineered](https://github.com/alexgaoth/awesome-reverse-engineered) e dice se c'è già una base da cui partire. Skill e server MCP si installano insieme.

Sul PC serve [uv](https://docs.astral.sh/uv/) nel PATH. Poi, in una chat di Cursor:

```text
/add-plugin starting-base@https://github.com/gianpierocasto-web/starting-base
```

Scegli l'ambito utente. In alternativa, in Customize → Plugins → Import marketplace incolla `https://github.com/gianpierocasto-web/starting-base`.

Tre tool:

- `assess_starting_base` — verdetto (`base pronta`, `base parziale`, `nessuna base`) e, per ogni repo, cosa copre, che ruolo ha e cosa dice il README
- `explain_repo` — scheda di un `owner/repo`
- `list_categories` — categorie dell'indice

L'indice viene scaricato in `~/.cache/awesome-reverse-engineered/entries.json` e riusato per 24 ore. Il testo di aiuto usa solo la scheda e le sezioni Installation, Usage o Features del README.

Per avviare il server a mano, dalla cartella del plugin:

```bash
uv run starting-base
```
