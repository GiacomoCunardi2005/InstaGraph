> **Documento storico / non implementare.** Questa nota descrive il precedente approccio
> crawler. Il prodotto corrente segue esclusivamente [roadmap.md](roadmap.md): cattura
> manuale e locale, JSON selezionato dall'utente, nessuna automazione del browser o
> interazione diretta con Instagram.

Esatto. Quello che descrivi è un **crawler depth-first**, cioè una visita in profondità con ritorno indietro quando un ramo non è accessibile.

## Algoritmo corretto

Si parte dal tuo profilo:

```text
TU
├── seguito_1
├── seguito_2
├── seguito_3
└── seguito_4
```

Il programma esegue:

1. apre i tuoi **Seguiti**;
2. aggiunge ogni account come bolla;
3. aggiunge una freccia `TU → account`;
4. prende il primo account non ancora analizzato;
5. apre prima i suoi **Seguiti**;
6. aggiunge nuove bolle e collegamenti;
7. apre poi i suoi **Follower**;
8. aggiunge i collegamenti `follower → account`;
9. prende il primo nuovo profilo accessibile;
10. continua finché possibile;
11. quando un profilo non permette di vedere le liste, torna al precedente e prova il secondo.

Esempio:

```text
TU
└── Marco
    ├── Luca
    │   ├── Andrea
    │   │   └── profilo non accessibile
    │   │
    │   └── torna a Luca
    │       └── Giulia
    │
    └── torna a Marco
        └── Sara
```

Questo richiede una **pila di navigazione**, non una semplice lista.

## Informazioni da salvare

Per ogni account:

```json
{
  "username": "marco",
  "following_scanned": true,
  "followers_scanned": true,
  "following_accessible": true,
  "followers_accessible": false
}
```

Per ogni collegamento:

```json
{
  "source": "marco",
  "target": "luca",
  "relationship": "follows"
}
```

Nel database non serve salvare post, fotografie, storie, biografie o messaggi.

## Gestione del ritorno indietro

La logica sarebbe questa:

```python
def esplora(account):
    if account in visitati:
        return

    visitati.add(account)

    seguiti = leggi_lista(account, "following")

    if seguiti.accessibile:
        aggiungi_collegamenti(account, seguiti)

        for seguito in seguiti:
            if seguito not in visitati:
                esplora(seguito)

    followers = leggi_lista(account, "followers")

    if followers.accessibile:
        aggiungi_collegamenti_inversi(followers, account)

        for follower in followers:
            if follower not in visitati:
                esplora(follower)

    # Nessun altro profilo accessibile:
    # la funzione termina e torna automaticamente al nodo precedente.
```

Però conviene non fare immediatamente la ricorsione mentre la finestra di Instagram è ancora aperta. La versione più robusta sarebbe:

1. acquisire completamente la lista;
2. salvarla;
3. chiudere la finestra;
4. inserire gli account in una coda/pila;
5. passare al profilo successivo.

## Evitare cicli infiniti

È fondamentale avere `visitati`, perché quasi subito comparirebbero cicli:

```text
Marco → Luca
Luca → Marco
```

Senza il controllo, il programma farebbe:

```text
Marco → Luca → Marco → Luca → Marco...
```

Ogni account deve quindi avere uno stato:

| Stato            | Significato                |
| ---------------- | -------------------------- |
| `discovered`     | Trovato, non ancora aperto |
| `following_done` | Seguiti acquisiti          |
| `followers_done` | Follower acquisiti         |
| `blocked`        | Liste non visibili         |
| `failed`         | Errore temporaneo          |
| `complete`       | Analisi terminata          |

## Attenzione all’espansione

Seguendo ricorsivamente **tutti** gli account trovati, il programma potrebbe uscire molto rapidamente dalla tua cerchia.

Esempio:

```text
tu segui 500 persone
ognuna segue mediamente 500 persone
secondo livello teorico: 250.000 account
```

Molti saranno duplicati, ma celebrità, pagine, negozi e creator potrebbero trascinare il crawler verso milioni di profili.

La soluzione migliore è continuare la visita soltanto per gli account che rispettano almeno uno di questi criteri:

* li segui tu;
* seguono te;
* hanno almeno 2–3 collegamenti con persone già presenti;
* appartengono chiaramente alla componente sociale che stai analizzando;
* non superano una soglia, per esempio 5.000 follower o seguiti.

Gli account esclusi possono comunque apparire come bolle periferiche, senza essere ulteriormente esplorati.

## Ordine consigliato

Per ottenere presto una mappa utile:

```text
1. I tuoi seguiti
2. I tuoi follower
3. Profili reciproci
4. Profili con più collegamenti comuni
5. Altri profili accessibili
6. Profili periferici
```

Questo è più efficiente rispetto a scegliere sempre letteralmente il primo elemento mostrato da Instagram, perché l’ordinamento della piattaforma non rappresenta necessariamente la vicinanza sociale.

Possiamo comunque mantenere la modalità richiesta:

```text
DFS puro:
primo → primo → primo → ramo bloccato → indietro → secondo
```

e aggiungere una modalità alternativa:

```text
DFS prioritario:
profilo con più collegamenti comuni → esplorazione
```

## Mappa a bolle durante la scansione

La visualizzazione si aggiorna progressivamente:

* bolla grigia: scoperta ma non analizzata;
* bolla piena: analisi completata;
* bordo tratteggiato: profilo non accessibile;
* linea sottile: follow singolo;
* linea spessa: follow reciproco;
* bolle vicine: molti collegamenti condivisi;
* gruppi separati: comunità differenti.

La posizione delle bolle non dovrebbe essere fissata appena vengono trovate. Ogni volta che arrivano nuovi collegamenti, il layout ricalcola gradualmente le posizioni.

## Limite reale di Instagram

Per gli account privati, follower e seguiti sono normalmente visibili solo agli utenti approvati dal proprietario dell’account. Quindi il comportamento “non accessibile → torna indietro” è coerente con la struttura del crawler. ([Instagram Aiuto][1])

L’API ufficiale di Instagram è rivolta principalmente agli account professionali e non offre la visita generale delle liste sociali necessaria per questo progetto. Servirebbe quindi controllare un browser già autenticato. ([Sviluppatori Facebook][2])

Il programma dovrebbe fermarsi automaticamente davanti a:

* CAPTCHA;
* richiesta di verifica;
* logout;
* limitazione temporanea;
* pagina “riprova più tardi”;
* cambiamenti imprevisti dell’interfaccia.

Non dovrebbe tentare di aggirare questi controlli.

La struttura definitiva sarebbe quindi:

```text
Browser Playwright
       ↓
Crawler DFS con backtracking
       ↓
SQLite con nodi, collegamenti e stati
       ↓
Analisi comunità
       ↓
Mappa interattiva Cytoscape.js
```

Questa implementazione corrisponde al comportamento che hai descritto: **segue un ramo fino a quando può, torna indietro quando trova una lista inaccessibile e riparte dal successivo profilo disponibile**.

[1]: https://help.instagram.com/667810236572057/?utm_source=chatgpt.com "Manage privacy on Instagram"
[2]: https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/get-started?utm_source=chatgpt.com "Get Started - Meta for Developers - Facebook"
.

## Tipi di collegamento

### Single-bonded

Una sola persona segue l’altra:

```text
A → B
```

Esempio:

```text
Marco segue Luca
Luca non segue Marco
```

Nella mappa:

* linea singola;
* freccia verso la persona seguita;
* collegamento più sottile.

### Double-bonded

Entrambe le persone si seguono:

```text
A ↔ B
```

Esempio:

```text
Marco segue Luca
Luca segue Marco
```

Nella mappa:

* linea doppia oppure più spessa;
* nessuna freccia, oppure frecce in entrambe le direzioni;
* peso maggiore nel calcolo della vicinanza sociale.

## Come aggiornarlo durante la scansione

Quando il crawler trova:

```text
Marco → Luca
```

crea inizialmente un collegamento `single`.

Successivamente, se analizzando Luca trova:

```text
Luca → Marco
```

non crea un secondo collegamento separato: aggiorna quello esistente a `double`.

```python
if relazione_esistente(target, source):
    relazione.tipo = "double"
else:
    crea_relazione(
        source=source,
        target=target,
        tipo="single"
    )
```

## Schema del database

Una struttura semplice:

```sql
CREATE TABLE relationships (
    account_a TEXT NOT NULL,
    account_b TEXT NOT NULL,
    a_follows_b BOOLEAN NOT NULL DEFAULT FALSE,
    b_follows_a BOOLEAN NOT NULL DEFAULT FALSE,
    bond_type TEXT NOT NULL,
    PRIMARY KEY (account_a, account_b)
);
```

Esempio:

| account_a | account_b | a_follows_b | b_follows_a | bond_type |
| --------- | --------- | ----------: | ----------: | --------- |
| marco     | luca      |           1 |           0 | single    |
| anna      | giulia    |           1 |           1 | double    |

Gli username devono essere ordinati sempre nello stesso modo, per esempio alfabeticamente, così `Marco-Luca` e `Luca-Marco` non diventano due righe diverse.

## Peso nella mappa

Puoi assegnare:

```text
single-bonded = peso 1
double-bonded = peso 2
```

Oppure dare più importanza alla reciprocità:

```text
single-bonded = peso 1
double-bonded = peso 3
```

Il peso influenza:

* quanto le bolle vengono avvicinate;
* lo spessore della linea;
* il rilevamento delle comitive;
* la centralità della persona;
* il punteggio di vicinanza.

Una relazione reciproca non dimostra necessariamente un’amicizia, ma è generalmente un segnale più forte di una relazione unidirezionale.

## Visualizzazione consigliata

```text
A ───▶ B       single-bonded

A ═════ B       double-bonded
```

Cliccando sulla linea si potrebbero mostrare:

```text
Marco ↔ Luca
Relazione reciproca
12 collegamenti comuni
Stessa comunità rilevata
```

Quindi il crawler conserva le direzioni reali, mentre la mappa le rappresenta come **single bond** o **double bond**.



---------------------------------------------------------------------------------


## Risultato della ricerca

**Esiste già qualcosa di molto vicino alla tua idea**, ma non ho trovato un progetto pronto che faccia esattamente:

```text
Seguiti → follower → primo account → DFS profondo
→ backtracking quando una lista non è visibile
→ single bond / double bond
→ mappa a bolle aggiornata in tempo reale
```

La strada migliore è combinare parti di più progetti.

## 1. OSINTGraph: il progetto più vicino

**OSINTGraph** raccoglie follower e seguiti di un profilo, salva account e relazioni in **Neo4j** e permette di visualizzarli come grafo interattivo. Ha anche un comando `explore` che visita ricorsivamente i seguiti degli account e salva progressivamente il lavoro, così una scansione interrotta può riprendere senza ricominciare. ([GitHub][1])

È quasi ciò che cerchi, ma presenta quattro differenze:

| Funzione               | OSINTGraph                             | Tuo progetto                       |
| ---------------------- | -------------------------------------- | ---------------------------------- |
| Acquisizione seguiti   | Sì                                     | Sì                                 |
| Acquisizione follower  | Sì                                     | Sì                                 |
| Esplorazione ricorsiva | Solo attraverso i seguiti              | Seguiti e follower                 |
| Ordine                 | Priorità agli account con più follower | Primo account, poi primo del primo |
| Algoritmo              | Esplorazione prioritizzata             | DFS con backtracking               |
| Dati raccolti          | Anche post, commenti e profilo         | Soltanto username e collegamenti   |

Nel tuo caso si potrebbero disattivare post, commenti e analisi AI tramite le opzioni `--skip`, mantenendo soltanto follower, seguiti e relazioni. Il comando `explore`, però, andrebbe riscritto per seguire la pila DFS e analizzare entrambe le liste. ([GitHub][1])

Non lo considererei completamente pronto: risultano segnalazioni aperte riguardanti sessioni Instagram, raccolta bloccata, configurazione Neo4j e ordinamento non funzionante come dichiarato. È una buona base da studiare, non un programma da installare e lasciare acceso senza modifiche. ([GitHub][2])

## 2. Progetto già orientato alla mappa di amicizie

Il repository **network-analysis-using-graph-theory** acquisisce follower e seguiti tramite Instaloader, costruisce il grafo con NetworkX, rileva gruppi sociali e visualizza la rete con Plotly. Considera collegate due persone quando il follow è reciproco. ([GitHub][3])

Questo corrisponde direttamente ai tuoi **double bond**:

```text
A → B
B → A

risultato:

A ═════ B
```

Il limite è che scarta le relazioni unidirezionali, mentre tu vuoi conservare anche:

```text
A ───▶ B
```

Quindi il codice di visualizzazione e clustering è utile, ma il modello delle relazioni deve essere modificato per includere entrambi i casi.

## 3. Scraper che lavora direttamente dentro Instagram

**instagram-users-scraper** è un piccolo script JavaScript eseguito nella console del browser. Riconosce le finestre follower e seguiti, salva gli username trovati e li esporta in CSV. Mantiene anche una cache se la pagina o il browser vengono chiusi. ([GitHub][4])

Il funzionamento attuale è parzialmente manuale:

1. apri la finestra follower o seguiti;
2. scorri la lista;
3. lo script intercetta gli account caricati;
4. esporta il risultato.

È utile perché contiene la parte più fragile: riconoscere gli account dentro la finestra dinamica di Instagram. Per il tuo progetto, lo scorrimento e il passaggio da un profilo all’altro andrebbero comandati da Playwright.

## 4. Instaloader

Instaloader permette da Python di ottenere `get_followers()` e `get_followees()` dopo avere caricato una sessione autenticata. La versione documentata più recente è **4.15.2, pubblicata il 5 luglio 2026**. ([instaloader.github.io][5])

È il sistema utilizzato anche da OSINTGraph, ma non è sempre affidabile. Nel repository sono state segnalate risposte `401 Unauthorized`, messaggi “Please wait a few minutes” e problemi durante l’estrazione di follower e seguiti, anche con account autenticati. ([GitHub][6])

Per questo progetto vedo due possibili motori:

| Motore      | Vantaggio                                       | Svantaggio                                    |
| ----------- | ----------------------------------------------- | --------------------------------------------- |
| Instaloader | Più semplice e rapido da programmare            | Endpoint non ufficiali instabili              |
| Playwright  | Vede esattamente ciò che appare nel tuo browser | Più lento e sensibile alle modifiche grafiche |

Dato che il tuo criterio è **“raccogli solo quello che il mio account riesce a vedere”**, Playwright è più coerente.

## Cosa emerge da Reddit

Le esperienze riportate confermano tre problemi tecnici.

La finestra follower/seguiti usa caricamento progressivo: non contiene subito tutti gli account, deve essere fatta scorrere e può anche riproporre elementi già incontrati. Servono quindi deduplicazione degli username e una condizione di arresto basata sul fatto che più scorrimenti consecutivi non producano account nuovi. ([Reddit][7])

Un utente che usava Selenium riferiva che lo script funzionava sul computer abituale, mentre su una macchina nuova Instagram richiedeva un codice di verifica. Questo rende necessario conservare la sessione del browser e fermare il programma quando compare un controllo manuale. ([Reddit][8])

Altri utenti riportano limitazioni e sospensioni anche con pause tra le richieste e sessioni autenticate. Sono esperienze aneddotiche, ma concordano con i numerosi errori presenti negli issue tracker di Instaloader. ([Reddit][9])

## Architettura che sceglierei

Non userei OSINTGraph integralmente. Userei:

```text
Playwright
    ↓
Crawler DFS persistente
    ↓
SQLite
    ↓
NetworkX per comunità e metriche
    ↓
Cytoscape.js per la mappa a bolle
```

### Algoritmo

Per ogni account:

```text
1. Apri il profilo
2. Apri Seguiti
3. Scorri fino a completamento
4. Salva account → seguito
5. Apri Follower
6. Scorri fino a completamento
7. Salva follower → account
8. Seleziona il primo account non visitato
9. Entra in quel profilo
10. Se non è accessibile, torna indietro e prova il successivo
```

La pila deve essere salvata nel database:

```text
Marco
 ├─ fase: followers completata
 ├─ prossimo account: indice 8
 └─ account figlio attuale: Luca
```

Così, in caso di chiusura:

```text
riapertura programma
→ carica pila
→ torna a Marco
→ riparte dall’account numero 8
```

## Relazioni

Internamente si salvano sempre le due direzioni separatamente:

```text
marco → luca
luca → marco
```

La visualizzazione le combina:

```text
solo marco → luca
= single-bonded

marco → luca + luca → marco
= double-bonded
```

Database minimo:

```sql
nodes(
    username,
    following_status,
    followers_status,
    accessibility_status
)

directed_edges(
    source_username,
    target_username
)

crawl_stack(
    depth,
    username,
    phase,
    next_index
)
```

## Conclusione

La base più vicina è **OSINTGraph**, soprattutto per Neo4j, salvataggio progressivo e visita ricorsiva. Il progetto sulla **network analysis con NetworkX e Plotly** contiene invece la parte più vicina alla mappa di comitive. Lo scraper da console contiene una buona logica per leggere le finestre Instagram.

La combinazione più adatta è quindi:

```text
logica di OSINTGraph
+ raccolta tramite Playwright
+ DFS con backtracking
+ single/double bond
+ Cytoscape.js
```

Non userei l’API ufficiale Meta: non fornisce normalmente l’elenco nominativo completo dei follower e dei seguiti necessario per costruire questa rete. ([Sviluppatori Facebook][10])

Rimane il rischio per l’account: Instagram vieta nei propri Termini la raccolta automatizzata senza autorizzazione e dichiara che lo scraping può portare a restrizioni. Il programma dovrebbe quindi fermarsi davanti a CAPTCHA, checkpoint o richieste di verifica, senza tentare di superarli. ([help.instagram.com][11])

[1]: https://github.com/XD-MHLOO/Osintgraph "GitHub - XD-MHLOO/Osintgraph: About Osintgraph is an open-source tool that collects Instagram data, followers, and followees, storing them in Neo4j. It helps you easily map and analyze a target's social network, revealing interests, connections, and affiliations for effective OSINT. · GitHub"
[2]: https://github.com/XD-MHLOO/Osintgraph/issues "Issues · XD-MHLOO/Osintgraph · GitHub"
[3]: https://github.com/sachin-duhan/network-analysis-using-graph-theory "GitHub - sachin-duhan/network-analysis-using-graph-theory: This project helps us to better understand our Instagram network by detecting and analysing clusters within our Instagram friends. · GitHub"
[4]: https://github.com/floriandiud/instagram-users-scraper "GitHub - floriandiud/instagram-users-scraper: Instagram Scraper. Scrape Instagram followers, following list, and post authors. Download CSV files with Instagram users from followers, following, tag and location pages. · GitHub"
[5]: https://instaloader.github.io/as-module.html?utm_source=chatgpt.com "Python Module instaloader — Instaloader documentation"
[6]: https://github.com/instaloader/instaloader/issues/2473?utm_source=chatgpt.com "Can't seem to fetch followers and followees · Issue #2473"
[7]: https://www.reddit.com/r/learnpython/comments/gxfppa/scraping_followers_names_from_instagram_using/?utm_source=chatgpt.com "Scraping followers names from instagram using selenium"
[8]: https://www.reddit.com/r/learnpython/comments/1fairy2/using_selenium_to_scrape_instagram/?utm_source=chatgpt.com "Using Selenium to scrape Instagram : r/learnpython"
[9]: https://www.reddit.com/r/DataHoarder/comments/1m3e0h7/how_to_reliably_scrape_instagram_posts/?utm_source=chatgpt.com "How to reliably scrape Instagram posts? : r/DataHoarder"
[10]: https://developers.facebook.com/community/threads/554226092217406/?utm_source=chatgpt.com "Is there an API that can be used to extract followers list from ..."
[11]: https://help.instagram.com/740480200552298/?utm_source=chatgpt.com "Why your account has been restricted for data scraping ..."
