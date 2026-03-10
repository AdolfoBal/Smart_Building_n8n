# Smart Building n8n
Progetto di tesi di Adolfo Balzano dedicato alla simulazione di una casa intelligente.

## Panoramica

Questo progetto realizza un ambiente di **smart home simulata** in cui è possibile monitorare e controllare stanze, sensori e attuatori tramite una dashboard web e API Flask.

L'obiettivo è studiare in modo pratico l'integrazione tra:
- logica applicativa locale (simulazione casa e automazioni);
- orchestrazione esterna con n8n (workflow e webhook);
- interazione di agenti AI con tracciamento delle azioni.

## Funzionalità principali

- Gestione stato IoT per stanza (sensori/attuatori);
- Simulazione tempo, giorno e condizioni meteo;
- Controllo manuale da dashboard e da endpoint API;
- Integrazione n8n per scenari automatici e flussi operativi;
- Logging automatico delle azioni agente in file JSONL giornalieri.

## Finalità della tesi

La finalità del lavoro è validare un'architettura semplice ma estendibile per automazione domestica, osservabilità e coordinamento tra componenti software eterogenei (Flask, n8n, agenti AI).

## Agenti AI e responsabilità

Il progetto usa tre agenti con ruoli separati:

- **MARIO** — *Monitoring and Autonomous Response Intelligent Operator* (facility manager): ottimizzazione globale casa con priorità sicurezza, comfort, risparmio.
- **LUIGI** — *Live User Interaction Generic Interface* (reattivo): azioni rapide su singola stanza in base a trigger presenza/assenza.
- **LUKE** — *Learning User Knowledge Engine* (conversazionale): raccolta e aggiornamento preferenze utente.

File principali agenti:

- `n8n/Mario.json` + `n8n/Mario_System_Prompt.txt`
- `n8n/Luigi.json` + `n8n/Luigi_System_Prompt.txt`
- `n8n/Luke.json` + `n8n/Luke_System_Prompt.txt`

In sintesi operativa:

- **MARIO** legge stato completo (`/api/status`) e preferenze, poi applica policy generali.
- **LUIGI** lavora su stato stanza (`/api/status/<stanza>`) con comfort immediato.
- **LUKE** modifica `preferences.json` tramite endpoint preferenze.

## Inizializzazione ambiente Python/Flask

Prerequisiti consigliati:

- Python 3.10+ installato
- n8n raggiungibile su `http://localhost:5678`

### Setup (Windows PowerShell)

```powershell
cd C:\Users\adolf\Documents\n8n_Python_Flask
python -m venv venv
& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Avvio applicazione Flask

```powershell
& .\venv\Scripts\Activate.ps1
python hub_iot.py
```

Endpoint utili a runtime:

- Dashboard: `http://localhost:5000/`
- Stato AI agent: `http://localhost:5000/api/status`
- Stato dashboard: `http://localhost:5000/api/dashboard/status`
- Webhook smart-home atteso da Flask: `http://localhost:5678/webhook/smart-home-command`

## Import workflow in n8n

I workflow da importare sono già pronti nella cartella `n8n/`.

Ordine consigliato:

1. Avvia n8n.
2. In n8n apri `Workflows`.
3. Seleziona `Import from File`.
4. Importa i file:
	- `n8n/Mario.json`
	- `n8n/Luigi.json`
	- `n8n/Luke.json`
5. Verifica URL webhook nei nodi (devono puntare a `localhost:5000` lato Flask e `localhost:5678` lato n8n, coerenti con `config.py`).
   > **Nota Docker:** se si usa Docker, sostituire `localhost` con `host.docker.internal`.
6. Salva e attiva i workflow.

Se in un workflow il system prompt non è già inline nel nodo AI, copia il contenuto dal relativo file:

- `n8n/Mario_System_Prompt.txt`
- `n8n/Luigi_System_Prompt.txt`
- `n8n/Luke_System_Prompt.txt`

## Flusso di avvio consigliato

1. Avvia n8n.
2. Attiva i workflow importati.
3. Avvia Flask (`python hub_iot.py`).
4. Apri dashboard e verifica trigger/automazioni.

## Note pratiche

- Le preferenze persistono in `preferences.json`.
- I log runtime sono in `logs/`.
- I webhook e timeout n8n si configurano in `config.py`.
