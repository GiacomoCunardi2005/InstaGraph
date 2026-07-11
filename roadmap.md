# Roadmap — InstaGraph

## Decisione: lettura manuale del browser

Il prossimo flusso del prodotto è questo: l'utente apre Instagram nel proprio browser,
attiva esplicitamente una cattura e scorre normalmente una lista. Il companion locale
registra solo gli username che diventano visibili durante quella sessione. Non fa login,
non controlla il browser e non invia richieste a Instagram.

~~~text
pagina Instagram aperta e gestita dall'utente
        ↓  (cattura esplicitamente attiva)
companion locale: username visibili + contesto confermato
        ↓
anteprima e JSON v1 locale scelto dall'utente
        ↓
importer locale con convalida atomica
        ↓
SQLite: account, archi diretti e audit
        ↓
web/graph.json → viewer Cytoscape.js locale → chat opzionale
~~~

Il traffico verso Instagram resta quello normale del browser dell'utente. Il companion
non legge cookie, token, credenziali, storage, profili browser o sessioni e non conserva
HTML, screenshot, URL completi o contenuti della pagina.

Il companion non avvia mai uno scroll. Il browser non distingue però con certezza uno
scroll fisico da uno avviato dalla pagina: il vincolo verificabile è che l'estensione
non lo genera e cattura solo nella tab visibile durante una sessione attiva.

## Contratto della cattura

La cattura è disattivata per default. Prima di iniziarla, l'utente conferma il profilo
della lista e il suo tipo:

| Lista confermata | Arco esportato per ogni username visibile |
| --- | --- |
| following di @marco | marco → username |
| followers di @marco | username → marco |

Il companion osserva soltanto gli elementi della lista che entrano realmente nel
viewport mentre l'utente fa scroll. Contenuti nascosti, precaricati fuori schermo o
altri link della pagina non contano come visibili. Se il contesto non stabilisce con
certezza la direzione dell'arco, l'elemento non viene esportato.

Durante una sessione il companion deduplica gli username solo nella bozza locale e
mostra un indicatore di cattura attiva. Alla fine l'utente può cancellare la bozza o
rivederla ed esportarla. L'export ha il formato JSON v1 esistente:

~~~json
{
  "version": 1,
  "accounts": ["marco", "luca"],
  "follows": [{"source": "marco", "target": "luca"}]
}
~~~

Il file passa sempre da import_json_file(): l'importer conserva i limiti, la
normalizzazione tramite GraphStore.normalize_username, l'atomicità e l'audit. Il nome
del file o un'etichetta fissa come manual-visible-ui è la fonte auditata; non va
salvato l'URL della pagina.

## Limiti non negoziabili

- Nessun Playwright, Selenium, Instaloader, crawler DFS, auto-scroll, auto-click,
  auto-navigazione, auto-login o ricerca automatica.
- Nessuna richiesta diretta a Instagram, API/OAuth, intercettazione di rete, cookie,
  token, credenziale, browser profile o import di sessione.
- Nessun CAPTCHA/checkpoint handling, proxy, fingerprint rotation, retry di login,
  ritardi casuali o altra tecnica per aggirare controlli.
- Nessuna cattura di post, bio, foto, video, messaggi, commenti, like, metriche,
  schermate, DOM nascosto o testo della pagina fuori dalla lista visibile.
- Nessuna cattura in background: la sessione termina quando l'utente la ferma o la UI
  non è più riconosciuta.
- I selettori della UI falliscono in modo chiuso: su una pagina inattesa non si
  esportano username indovinati.
- I dati restano locali. L'invio a OpenAI richiede un opt-in esplicito e separato.

## Stato della prima tranche

- [x] SQLite conserva account, archi diretti e audit di import.
- [x] L'importer JSON v1 valida, deduplica, applica limiti e deriva bond single/double.
- [x] L'exporter genera il JSON Cytoscape e distribuisce il viewer statico locale.
- [x] Il client OpenAI diretto è opzionale, testato senza rete e non conserva chiavi.
- [x] Companion del browser per la cattura manuale degli elementi visibili. Il popup
  inietta un solo adapter DOM ristretto, verificato contro un riferimento locale della
  lista; un cambiamento di struttura viene rifiutato senza alcun fallback generico.
- [x] Tool di sola lettura e consenso esplicito per la chat OpenAI.

Il package distribuito resta soltanto instagraph. Il codice in src/osintgraph è
riferimento storico: non si importano Gemini, LangChain, Neo4j, Instaloader né
meccanismi legacy di sessione nel nuovo runtime.

## Architettura target

| Componente | Responsabilità | Non fa |
| --- | --- | --- |
| Companion del browser | Cattura visibili, deduplica temporanea, anteprima, JSON v1 | Login, rete, scroll/click, lettura di sessioni, scrittura nel DB |
| importer.py | Valida e importa il JSON in modo atomico | Leggere il browser o Instagram |
| store.py | accounts, follow_edges, import_runs | Salvare contenuti sociali o bond persistenti |
| exporter.py e viewer locale | Mostrare il grafo importato | Controllare Instagram |
| Client OpenAI opzionale | Query di sola lettura dopo opt-in | Ricevere il grafo senza consenso |

Il core Python resta offline e browser-independent. follow_edges rimane diretto; un
bond è calcolato alla lettura: A → B e B → A è double, altrimenti è single.

## Fasi

### 0. Formalizzare il perimetro della cattura

**Stato:** completata. `companion/tests/` contiene fixture locali per lista riconosciuta,
riga aggiunta, root assente/ambiguo e figlio inatteso; il runner e i test Node non
richiedono account, rete o browser profile.

- Documentare consenso per sessione, indicatore di cattura attiva e cancellazione della
  bozza locale.
- Definire il contesto obbligatorio profilo + tipo lista e la conversione in archi
  diretti.
- Preparare fixture HTML locali con elementi aggiunti mentre l'utente scorre.
- Definire il comportamento fail-closed quando la lista visibile non è riconosciuta.
- Mantenere i test totalmente offline: nessun account, sessione o chiamata Instagram.

**Uscita:** il comportamento consentito e quello vietato sono verificabili con fixture.

### 1. Costruire il companion minimo

**Stato:** completata nell'implementazione. Il companion MV3 locale usa soltanto
`activeTab` e `scripting`, con consenso, contesto, start/stop, indicatore, bozza
effimera, review ed export JSON v1. Il popup inietta `instagram-adapter.js`, un unico
adapter ristretto verificato contro un riferimento locale: accetta soltanto il dialog e
le righe strutturalmente corrispondenti. Username fuori viewport non vengono letti; un
mismatch, un link extra o un'origine inattesa falliscono in modo chiuso. Il contratto
`data-instagraph-*=v1` resta esclusivamente per le fixture offline del core.

- Creare una WebExtension locale con cattura disattivata per default.
- Consentire avvio e stop espliciti nella scheda scelta dall'utente.
- Durante la sessione, registrare soltanto gli username che diventano visibili mentre
  l'utente fa scroll manualmente.
- Richiedere e mostrare il contesto profilo + following/followers prima dell'export.
- Deduplicare nella sola bozza in memoria e permettere di eliminarla.
- Non chiedere né memorizzare credenziali, cookie, sessioni o storage del sito.

**Uscita:** l'utente scorre una lista manualmente e ottiene una bozza locale, senza
alcuna azione automatica del companion.

### 2. Esportare e importare il grafo locale

**Stato:** completata. Il companion produce il solo JSON v1 rivisto dall'utente e
l'importer lo valida e importa in modo atomico; fixture e test coprono le due direzioni,
la riga aggiunta, dati non validi e UI inattesa.

- Generare esclusivamente JSON v1 compatibile con l'importer esistente.
- Mantenere i limiti attuali: file da 10 MiB e 100.000 voci di input.
- Usare una revisione finale e un file selezionato dall'utente, non una scrittura
  diretta verso SQLite.
- Testare JSON valido, username duplicati/non validi, entrambe le direzioni, stop della
  cattura e UI inattesa con fixture locali.

**Uscita:** una cattura manuale produce solo accounts, follow_edges e import_runs tramite
il flusso locale esistente.

### 3. Visualizzare il grafo

**Stato:** completata per il viewer statico locale.

- Generare web/graph.json dopo ogni import riuscito.
- Servire il viewer solo su 127.0.0.1 con python -m http.server; non servono backend,
  WebSocket o CDN.
- Mostrare legami single/double e direzione corretta degli archi.
- Aggiungere NetworkX solo se la mappa base dimostra che servono comunità o centralità.

**Uscita:** il browser mostra l'ultimo grafo importato senza comandare Instagram.

### 4. Chat OpenAI opzionale e di sola lettura

**Stato:** completata nel core Python. `ask_graph()` richiede `consent=True` prima di
creare qualsiasi richiesta, usa `OPENAI_API_KEY` solo al momento della chiamata e passa
solo output di tool strettamente read-only al Responses API con `store=False`.

- Usare OPENAI_API_KEY dall'ambiente e l'SDK Responses diretto solo quando serve.
- Esporre pochi tool: get_account, get_neighbors, find_path, get_community e
  graph_summary.
- Non inviare username o l'intero grafo senza consenso esplicito; preferire dati
  aggregati quando bastano.
- Non aggiungere embedding o LangChain: username e archi non forniscono testo utile da
  indicizzare.

`get_community` restituisce la componente connessa locale, etichettata esplicitamente
come tale: non presenta una deduzione statistica come una comunità sociale. I membri
sono limitati a 100 nel risultato del tool; il conteggio resta completo.

**Uscita:** le domande leggono il database locale e rispettano il consenso dell'utente.

### 5. Ritirare il percorso legacy

**Stato:** completata. Il wheel e anche l'installazione editable espongono soltanto
`instagraph` (`dev-mode-exact = true`); `FinalAppIdea.md` è etichettato come storico e
il percorso utente è cattura manuale → JSON locale → import → mappa.

- Tenere src/osintgraph fuori dal package e dai nuovi comandi.
- Non migrare discover, explore, Instaloader, l'importatore di sessione, il crawler o
  il vecchio agente RAG.
- Rimuovere dipendenze e documentazione legacy quando il flusso locale è pronto.

**Uscita:** l'unico percorso utente è cattura manuale → JSON locale → import → mappa.

## Cose da non fare ora

- Non trasformare la cattura manuale in un crawler che visita profili o completa liste
  da solo.
- Non usare lo scroll manuale come pretesto per leggere il DOM non visibile o per
  mantenere la cattura attiva in background.
- Non aggiungere server, code, FastAPI, WebSocket, multi-agent o Neo4j al MVP.
- Non usare screenshot/OCR: il companion legge solo il testo degli elementi di lista
  realmente visibili.
- Non riportare nel nuovo prodotto il vecchio stack Gemini, LangChain o browser-session
  legacy.
