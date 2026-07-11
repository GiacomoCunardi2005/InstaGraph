# InstaGraph

InstaGraph costruisce un grafo locale da un JSON scelto e rivisto dall'utente. Conserva
solo username, archi follow diretti e audit di import in SQLite.

Non effettua login, richieste a Instagram, crawling, auto-scroll, lettura di cookie o
raccolta di contenuti sociali.

```bash
python -m pip install -e .
```

## Flusso locale

1. Carica `companion/` come estensione non pacchettizzata.
2. Il companion ricava il profilo dal pathname della tab attiva; conferma tipo di lista
   e consenso, poi cattura solo username nel viewport quando la lista soddisfa il suo
   contratto DOM verificato.
3. Rivedi ed esporta `manual-visible-ui.json`.
4. Metti gli export JSON v1 in una cartella scelta da te e importa i soli file `.json`
   immediati (senza scansione ricorsiva):

```bash
python -m instagraph import-folder /percorso/cartella-export
```

Ogni import riuscito genera `web/graph.json` accanto al database e distribuisce il
viewer locale. Per visualizzarlo solo in locale:

```bash
python -m instagraph view
```

La chat OpenAI è opzionale: `ask_graph(..., consent=True)` usa il Responses API solo
dopo consenso esplicito e con tool in sola lettura. Dettagli e limiti sono in
[roadmap.md](roadmap.md).

## Verifiche

```bash
PYTHONPATH=src python -m unittest discover -v
node --test companion/tests/capture-core.test.js
```
