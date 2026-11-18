# Anime Music Downloader

Cerca nel catalogo di [AnisongDB](https://anisongdb.com/) e scarica le tracce tramite browser o con la GUI desktop.

## Avvio con Docker

Installa e avvia Docker Desktop con i container Linux abilitati. In PowerShell, da questa cartella:

```powershell
docker compose up -d --build
```

Apri **http://localhost:8080** sul server oppure, da un altro dispositivo della rete, usa l'indirizzo IP del server, ad esempio **http://192.168.1.4:8080**. Sostituisci l'indirizzo con quello effettivo del server e consenti, se necessario, la porta TCP nel suo firewall. I download sono salvati nella cartella `downloads` del progetto sul computer che esegue Docker, non nella cartella predefinita del browser. FFmpeg è incluso nell'immagine.

### Indirizzo, porta e cartella

Modifica i valori predefiniti direttamente in `compose.yaml`:

```yaml
ports:
  - "0.0.0.0:8080:8080"
volumes:
  - "./downloads:/downloads"
```

Per esempio, sostituisci il primo `8080` per cambiare la porta del computer e `./downloads` con la cartella desiderata. Lascia invariati il secondo `8080` e `/downloads`, che sono i valori nel container. `0.0.0.0` pubblica la porta su tutte le interfacce IPv4; puoi sostituirlo con l'indirizzo IP locale del server per limitarla a quell'interfaccia, oppure con `127.0.0.1` per consentire solo accessi locali.

In alternativa, senza modificare il file, imposta le variabili `APP_BIND_ADDRESS`, `APP_PORT` e `DOWNLOAD_DIR` in un file `.env` nella stessa cartella di `compose.yaml`:

```dotenv
APP_BIND_ADDRESS=192.168.1.4
APP_PORT=8090
DOWNLOAD_DIR=./musica
```

`APP_BIND_ADDRESS` deve essere un indirizzo presente sul server; omettilo per usare `0.0.0.0`. Per un percorso assoluto su Windows, ad esempio: `DOWNLOAD_DIR=C:\Users\Nome\Music\Anime`. Accertati che il percorso sia accessibile e scrivibile da Docker Desktop. Dopo ogni modifica ricrea il container:

```powershell
docker compose up -d
```

Con l'esempio sopra apri **http://192.168.1.4:8090**; quando la porta è associata solo a quell'interfaccia, `localhost` potrebbe non funzionare. Per fermare il servizio usa `docker compose down`; i file scaricati restano nella cartella scelta.

Il servizio non ha autenticazione: chiunque possa raggiungerlo può usarlo e avviare download sul server. L'app accetta indirizzi IPv4 privati (10.x.x.x, 172.16–31.x.x e 192.168.x.x) e localhost, non nomi host personalizzati. Il controllo dell'indirizzo non sostituisce un firewall: limita l'accesso alla rete fidata e non esporre la porta su Internet. La pagina deve rimanere aperta durante i download selezionati.

## Utilizzo

1. Cerca per anime, titolo, artista, compositore o in tutti i campi.
2. Seleziona una o più tracce, oppure usa la casella nell'intestazione per selezionarle tutte.
3. Premi **Scarica selezionati**. Gli eventuali errori sono mostrati nella pagina.

La colonna **Season** mostra stagione e anno indicati da AnisongDB, mentre **Anno** mostra solo l'anno; se il dato non è disponibile, compare un trattino. Clicca sull'intestazione di una colonna per ordinare i risultati e clicca nuovamente per invertire l'ordine. L'ordinamento di **Season** è alfabetico; per l'ordine cronologico per anno usa **Anno**. I dati mancanti vengono mostrati in fondo.

Nella versione web, **Colonne** permette di scegliere i campi visibili e riordinarli con le frecce; visibilità e ordine sono salvati nel browser. La casella di selezione delle tracce rimane sempre all'inizio. La colonna **Info** apre i dettagli della traccia, mentre **Play Audio** consente l'ascolto. Le colonne per playlist e modifica delle righe presenti sul sito originale non sono incluse. In **Opzioni** si può scegliere se visualizzare il nome anime inglese o giapponese, usando l'altro quando quello scelto manca.

**Ricerca avanzata** permette di combinare anime, titolo, artista e compositore con corrispondenza parziale o esatta e distinzione maiuscole, AND/OR, duplicati e filtri per tipo di sigla, trasmissione, performance, tipo anime, stagione e difficoltà. Inserisci un termine in almeno uno dei campi avanzati; ciascun gruppo di filtri deve avere almeno un valore selezionato. I risultati e le informazioni dipendono dai dati disponibili su AnisongDB.

### Opzioni di output

Il pulsante **Opzioni** consente di scegliere il formato audio **Originale**, **MP3** o **AAC** e di personalizzare il modello del nome con i nomi delle colonne, ad esempio `{Anime} - {Song Name} - {Artist}`. Sono disponibili tutti i campi testuali e numerici elencati nella finestra, inclusi `{Season}`, `{Anno}`, `{Song Type}` e gli ID; le colonne con pulsanti o collegamenti non sono utilizzabili nel nome. `{Anime}` usa la lingua EN o JP scelta nelle opzioni, con ripiego sull'altra lingua se necessario. `{Row Number}` è il numero originario del risultato, non cambia ordinando le righe ed è disponibile nella versione web; nella versione desktop compare `Non disponibile`. I dati mancanti vengono indicati nel nome. I precedenti segnaposto minuscoli restano validi. Non inserire l'estensione nel modello: viene aggiunta automaticamente. I caratteri non validi nei nomi dei file vengono sostituiti.

Il formato predefinito conserva l'audio originale; per i video estrae un MP3. MP3 o AAC convertono l'audio se necessario tramite FFmpeg (incluso nel container), quindi possono comportare una ricodifica con perdita di qualità; se è già nel formato scelto, il file viene copiato senza conversione. Le opzioni web sono salvate nel browser e valgono per i successivi download; nella GUI desktop valgono fino alla chiusura dell'applicazione.

I file esistenti non vengono sovrascritti. Le tracce presenti nel database possono essere estratti brevi, non brani completi; alcune potrebbero non avere file disponibili. L'accessibilità dipende dal servizio e dalle sue eventuali limitazioni. Scarica e usa i contenuti soltanto quando disponi dei diritti o delle autorizzazioni necessarie, rispettando le condizioni dei servizi.

## Versione desktop

Rimane disponibile la GUI originale, senza Docker:

```powershell
python anime_music_downloader.py
```

Servono Python 3 con Tkinter e una connessione a Internet. FFmpeg nel `PATH` è necessario per estrarre l'audio dalle tracce disponibili solo come video.
