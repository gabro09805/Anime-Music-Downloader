# Anime Music Downloader

Cerca nel catalogo di [AnisongDB](https://anisongdb.com/) e scarica le tracce tramite browser o con la GUI desktop.

## Avvio con Docker

Installa e avvia Docker Desktop con i container Linux abilitati. In PowerShell, da questa cartella:

```powershell
docker compose up -d --build
```

Apri **http://localhost:8080**. I download sono salvati nella cartella `downloads` del progetto sul computer che esegue Docker, non nella cartella predefinita del browser. FFmpeg è incluso nell'immagine.

### Porta e cartella

Modifica i valori predefiniti direttamente in `compose.yaml`:

```yaml
ports:
  - "127.0.0.1:8080:8080"
volumes:
  - "./downloads:/downloads"
```

Per esempio, sostituisci il primo `8080` per cambiare la porta del computer e `./downloads` con la cartella desiderata. Lascia invariati il secondo `8080` e `/downloads`, che sono i valori nel container.

In alternativa, senza modificare il file, imposta le variabili `APP_PORT` e `DOWNLOAD_DIR` in un file `.env` nella stessa cartella di `compose.yaml`:

```dotenv
APP_PORT=8090
DOWNLOAD_DIR=./musica
```

Per un percorso assoluto su Windows, ad esempio: `DOWNLOAD_DIR=C:\Users\Nome\Music\Anime`. Accertati che il percorso sia accessibile e scrivibile da Docker Desktop. Dopo ogni modifica ricrea il container:

```powershell
docker compose up -d
```

Con l'esempio sopra apri **http://localhost:8090**. Per fermare il servizio usa `docker compose down`; i file scaricati restano nella cartella scelta.

Il servizio non ha autenticazione ed è pubblicato solo su localhost: non esporlo su Internet o sulla rete. La pagina deve rimanere aperta durante i download selezionati.

## Utilizzo

1. Cerca per anime, titolo, artista, compositore o in tutti i campi.
2. Seleziona una o più tracce, oppure usa la casella nell'intestazione per selezionarle tutte.
3. Premi **Scarica selezionati**. Gli eventuali errori sono mostrati nella pagina.

La colonna **Season** mostra stagione e anno indicati da AnisongDB, mentre **Anno** mostra solo l'anno; se il dato non è disponibile, compare un trattino. Clicca sull'intestazione di una colonna per ordinare i risultati e clicca nuovamente per invertire l'ordine. L'ordinamento di **Season** è alfabetico; per l'ordine cronologico per anno usa **Anno**. I dati mancanti vengono mostrati in fondo.

Nella versione web, **Colonne** permette di scegliere i campi visibili e riordinarli con le frecce; visibilità e ordine sono salvati nel browser. La casella di selezione delle tracce rimane sempre all'inizio. La colonna **Info** apre i dettagli della traccia, mentre **Play Audio** consente l'ascolto. Le colonne per playlist e modifica delle righe presenti sul sito originale non sono incluse. In **Opzioni** si può scegliere se visualizzare il nome anime inglese o giapponese, usando l'altro quando quello scelto manca.

**Ricerca avanzata** permette di combinare anime, titolo, artista e compositore con corrispondenza parziale o esatta e distinzione maiuscole, AND/OR, duplicati e filtri per tipo di sigla, trasmissione, performance, tipo anime, stagione e difficoltà. Inserisci un termine in almeno uno dei campi avanzati; ciascun gruppo di filtri deve avere almeno un valore selezionato. I risultati e le informazioni dipendono dai dati disponibili su AnisongDB.

### Opzioni di output

Il pulsante **Opzioni** consente di scegliere il formato audio **Originale**, **MP3** o **AAC** e di personalizzare il modello del nome. Ad esempio, `{anime} - {titolo} - {artista}` produce un nome come `Naruto - Rise - Artista.mp3`. Sono disponibili anche `{anno}`, `{season}` e `{tipo}`. Non inserire l'estensione nel modello: viene aggiunta automaticamente. I caratteri non validi nei nomi dei file vengono sostituiti.

Il formato predefinito conserva l'audio originale; per i video estrae un MP3. MP3 o AAC convertono l'audio se necessario tramite FFmpeg (incluso nel container), quindi possono comportare una ricodifica con perdita di qualità; se è già nel formato scelto, il file viene copiato senza conversione. Le opzioni web sono salvate nel browser e valgono per i successivi download; nella GUI desktop valgono fino alla chiusura dell'applicazione.

I file esistenti non vengono sovrascritti. Le tracce presenti nel database possono essere estratti brevi, non brani completi; alcune potrebbero non avere file disponibili. L'accessibilità dipende dal servizio e dalle sue eventuali limitazioni. Scarica e usa i contenuti soltanto quando disponi dei diritti o delle autorizzazioni necessarie, rispettando le condizioni dei servizi.

## Versione desktop

Rimane disponibile la GUI originale, senza Docker:

```powershell
python anime_music_downloader.py
```

Servono Python 3 con Tkinter e una connessione a Internet. FFmpeg nel `PATH` è necessario per estrarre l'audio dalle tracce disponibili solo come video.
