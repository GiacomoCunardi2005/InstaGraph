# Companion locale

Carica `companion/` come estensione non pacchettizzata. La cattura è disattivata
finché l'utente non conferma owner, direzione e consenso nel popup.

Senza `instagram-adapter.js`, il core accetta esclusivamente il contratto fixture
`data-instagraph-*=v1`. Quando il popup lo inietta, l'adapter richiede invece un unico
dialog con righe dalla struttura verificata; un mismatch cancella la bozza.
Gli `href` controllano soltanto che gli uno o due link di una riga indichino lo stesso
percorso locale monosegmento, senza query o hash: lo username viene sempre dal solo
testo renderizzato della foglia verificata. Non esistono fallback su testo o link
generici.

Verifiche completamente locali:

```bash
node --test companion/tests/capture-core.test.js
node --check companion/instagram-adapter.js
```

Dopo aver caricato l'estensione, apri `tests/fixture-runner.html` dalla pagina
dell'estensione per eseguire le fixture DOM senza account, rete o server.

La bozza vive soltanto nel content script della tab. Navigazione o reload la perde;
un DOM inatteso la cancella. L'export crea solo il JSON v1 da importare manualmente.

Il companion non avvia mai uno scroll e registra solo righe nel viewport dopo eventi
di scroll fidati. Il browser non può però provare con certezza che uno scroll fidato
sia stato fisicamente compiuto dall'utente.
