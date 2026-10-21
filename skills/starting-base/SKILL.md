---
name: starting-base
description: Cerca se esiste già una base open source da cui partire prima di scrivere un client, un parser, un protocollo o una reimplementazione. Usa quando l'utente chiede se c'è già un repo, una base di partenza, un progetto reverse-engineered, o prima di reimplementare un'app, API, dispositivo, formato o protocollo chiuso. Chiama il MCP starting-base.
---

# Base di partenza

L'indice è [awesome-reverse-engineered](https://github.com/alexgaoth/awesome-reverse-engineered). Il MCP `starting-base` dice se uno di quei progetti è già una base utilizzabile.

## Quando usarla

Usa il MCP quando l'utente vuole sapere se esiste già qualcosa da cui partire, oppure prima di scrivere da zero un client, un parser, un driver o una reimplementazione di un sistema chiuso.

## Come rispondere

1. Chiama `assess_starting_base` con il nome del prodotto, del produttore o del protocollo. Da una frase tieni 1–4 parole significative. Se l'utente ha chiesto una lingua o una categoria, passa `language` e `category`.
2. Se il verdetto è `nessuna base` e la frase era lunga, riprova con meno parole. Se serve, chiama `list_categories` e ripeti con una categoria più adatta.
3. Per un repository già indicato, chiama `explain_repo`.
4. Rispondi in italiano. Prima il verdetto, poi ogni repository con link, stato, lingua, licenza, stelle e l'aiuto concreto: cosa copre, ruolo, cosa dicono le sezioni del README, limiti.
5. Non aggiungere capacità che non stanno in `cosa_copre`, `ruolo`, `dal_readme` o `inizio_readme`.
6. Non clonare un repository se l'utente non lo chiede.
7. Se il progetto è un client non ufficiale, di' che può violare i termini del servizio e che va usato con account, dispositivi e dati propri.

L'indice non contiene exploit, jailbreak, bypass o rimozione DRM. Non cercarli con questo strumento.
