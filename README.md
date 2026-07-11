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
2. Conferma profilo, tipo di lista e consenso; il companion cattura solo username nel
   viewport quando la lista soddisfa il suo contratto DOM verificato.
3. Rivedi ed esporta `manual-visible-ui.json`.
4. Importa il file localmente:

```python
from instagraph import GraphStore, import_json_file

with GraphStore() as store:
    report = import_json_file(store, "/percorso/manual-visible-ui.json")
    print(report.run.status, store.database_path)
```

Ogni import riuscito genera `web/graph.json` accanto al database e distribuisce il
viewer locale. Servilo solo in locale, per esempio con `python -m http.server --bind
127.0.0.1 --directory /percorso/web 8000`.

La chat OpenAI è opzionale: `ask_graph(..., consent=True)` usa il Responses API solo
dopo consenso esplicito e con tool in sola lettura. Dettagli e limiti sono in
[roadmap.md](roadmap.md).

## Verifiche

```bash
PYTHONPATH=src python -m unittest discover -v
node --test companion/tests/capture-core.test.js
```
