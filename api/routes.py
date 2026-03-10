"""
API Routes - Flask Blueprint con tutti gli endpoint API

================================================================================
                           URL COMPLETI PER n8n
================================================================================

1. GET http://localhost:5000/
   - Restituisce: Dashboard HTML
   - Descrizione: Pagina principale con visualizzazione stato casa

2. GET http://localhost:5000/api/status
   - Header opzionale: X-Agent-Id: <id_agent> (per lock bidirezionale)
   - Restituisce: JSON con stato simulazione - SOLO dati per AI Agent
   - Descrizione: Dati puntuali e ordinati. Comandi/preferenze nel system prompt dell'agent.
   - Campi: ora, giorno, giorno_numero, stagione, meteo, temperatura_esterna, stanze
   - Ogni attuatore ha: stato + bloccato (+ modificato_da, minuti_fa se bloccato)

3. GET http://localhost:5000/api/dashboard/status
   - Restituisce: JSON con stato completo + metadati configurazione
   - Descrizione: Stato completo per Dashboard UI
   - Campi aggiuntivi: indici, velocità, intervalli, timestamps

4. POST http://localhost:5000/api/agent/action
   - Header: X-Agent-Id: <id_agent>
   - Body: {"action": "...", ...}
   - Descrizione: Log azioni dell'AI Agent con timestamp simulato

5. POST http://localhost:5000/api/soggiorno/luci
   POST http://localhost:5000/api/camera/luci
   POST http://localhost:5000/api/cucina/luci
   POST http://localhost:5000/api/stanza/clima
   POST http://localhost:5000/api/stanza/tapparelle
   POST http://localhost:5000/api/stanza/tv
   - Body: {"azione": "ON/OFF"} o {"azione": "APERTE/CHIUSE"} o {"azione": "HEAT/COOL/OFF"}
   - Descrizione: Controlla luci, tapparelle, clima, TV di una stanza

6. POST http://localhost:5000/api/time
   - Body: {"ora": 0-23}
   - Descrizione: Imposta manualmente l'ora simulata

7. POST http://localhost:5000/api/time-speed
   - Body: {"velocita": 0-600}
   - Descrizione: Imposta velocità scorrimento tempo (minuti simulati per minuto reale)

8. POST http://localhost:5000/api/presence
   - Body: {"stanza": "nome_stanza", "presenza": true/false}
   - Descrizione: Registra presenza/assenza in una stanza

9. POST http://localhost:5000/api/n8n-interval
   - Body: {"seconds": 10-300}
   - Descrizione: Imposta intervallo di esecuzione AI Agent (n8n)

10. POST http://localhost:5000/api/day
   - Body: {"giorno": 0-6} o {"giorno": "Lunedì/Martedì/..."}
   - Descrizione: Imposta manualmente il giorno della settimana

11. POST http://localhost:5000/api/season
   - Body: {"stagione": 0-3} o {"stagione": "Inverno/Primavera/..."}
   - Descrizione: Imposta manualmente la stagione

12. POST http://localhost:5000/api/weather
    - Body: {"condizione": "Sereno/Nuvoloso/Pioggia/Temporale/Neve/Nebbia"}
    - Descrizione: Imposta condizioni meteo

13. POST http://localhost:5000/api/query
    - Body: {"type": "all/temperature/luci/problemi"}
    - Descrizione: Query intelligente dello stato con filtri

14. POST http://localhost:5000/api/actions/scenario/buongiorno
    POST http://localhost:5000/api/actions/scenario/buonanotte
    POST http://localhost:5000/api/actions/scenario/cinema
    POST http://localhost:5000/api/actions/scenario/via_da_casa
    - Body: {}
    - Descrizione: Applica scenari predefiniti

15. GET http://localhost:5000/health
    - Restituisce: JSON status healthy
    - Descrizione: Health check per verificare servizio attivo

16. GET http://localhost:5000/api/preferences
    - Restituisce: JSON con tutte le preferenze utente (note_generali + per stanza)
    - Descrizione: Ritorna le preferenze complete

17. GET http://localhost:5000/api/preferences/<stanza>
    - Restituisce: JSON con preferenze stanza specifica
    - Descrizione: Usato dagli AI Agent tramite tool ottieni_preferenze

18. PUT http://localhost:5000/api/preferences
    - Body: {"cucina": {"temperatura_ideale": 23, "blocco_finestre": "bloccate"}, "note_generali": "..."}
    - Descrizione: Aggiorna preferenze (merge parziale)

19. PUT http://localhost:5000/api/preferences/<stanza>
    - Body: {"temperatura_ideale": 23, "blocco_finestre": "auto", "note": "..."}
    - Descrizione: Aggiorna preferenze di una singola stanza

20. GET http://localhost:5000/api/status/<stanza>
    - Header opzionale: X-Agent-Id: <id_agent> (per lock bidirezionale)
    - Restituisce: JSON con stato della sola stanza + contesto_esterno
    - Descrizione: Endpoint ottimizzato per agent reattivi stanza-centrici (es. Luigi)

21. GET http://localhost:5000/api/status/esterno
    - Restituisce: JSON con ora, giorno, stagione, meteo, temperatura_esterna, luminosita_giardino
    - Descrizione: Contesto esterno/temporale minimo per decisioni rapide

================================================================================
"""
from flask import Blueprint, jsonify, render_template, request, send_file
from datetime import datetime
from apscheduler.triggers.interval import IntervalTrigger
import json
import core
from api import send_presence_webhook
from io import BytesIO
from models.preferences import (
    VALID_LUCI_INGRESSO,
    VALID_TAPPARELLE,
    VALID_BLOCCO_FINESTRE,
    STANZE_CON_CLIMA,
    STANZE_CON_TAPPARELLE,
    STANZE_CON_FINESTRE,
)
from config import ACTUATOR_TYPES
# ACTUATOR_TYPES usato solo per validazione interna nell'endpoint controlla_attuatore

# Crea il Blueprint
api_bp = Blueprint('api', __name__)


@api_bp.route('/favicon.ico')
def favicon():
    """Serve favicon vuoto per evitare 404"""
    # Crea un favicon ICO minimalista (1x1 pixel trasparente)
    favicon_data = (
        b'\x00\x00\x01\x00\x01\x00\x01\x00\x00\x00\x01\x00'
        b'\x18\x00\x00\x00\x16\x00\x00\x00\x28\x00\x00\x00'
        b'\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x18\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\xff\xff\xff\x00'
    )
    return send_file(
        BytesIO(favicon_data),
        mimetype='image/x-icon',
        as_attachment=False,
        download_name='favicon.ico'
    )


@api_bp.route('/')
def dashboard():
    core.simula_letture_sensori()
    ora_corrente, minuto_corrente = core.get_tempo_simulato()
    temp_esterna = core.calcola_temperatura_esterna(ora_corrente)
    tempo_corrente = f"{ora_corrente:02d}:{minuto_corrente:02d}"
    return render_template(
        "dashboard.html",
        data=core.get_stato_casa_flat(),
        ora_corrente=ora_corrente,
        minuto_corrente=minuto_corrente,
        tempo_corrente=tempo_corrente,
        velocita_tempo=core.velocita_tempo,
        ui_update_interval_seconds=2,
        n8n_interval_seconds=core.n8n_interval_seconds,
        condizioni_meteo=core.condizioni_meteo,
        giorno_settimana=core.get_giorno_settimana(),
        giorno_settimana_idx=core.giorno_settimana_idx,
        giorno_numero=core.giorno_numero,
        stagione=core.get_stagione(),
        stagione_idx=core.stagione_idx,
        temp_esterna=temp_esterna
    )


@api_bp.route('/api/status', methods=['GET'])
def get_status_completo():
    """Ritorna lo stato della simulazione per AI Agent.
    
    Dati puntuali e ordinati: contesto temporale + stanze (sensori + attuatori con lock).
    Comandi e preferenze risiedono nel system prompt dell'agent, non qui.
    Il lock è bidirezionale: calcolato in base all'header X-Agent-Id.
    """
    core.simula_letture_sensori()
    core.aggiorna_tempo_simulato()
    ora_corrente, minuto_corrente = core.get_tempo_simulato()
    temp_esterna = core.calcola_temperatura_esterna(ora_corrente)
    
    # Identifica l'agent richiedente per calcolo lock bidirezionale
    agent_id = request.headers.get('X-Agent-Id')
    requesting_agent = agent_id.lower() if agent_id else None
    
    return jsonify({
        "ora": f"{ora_corrente:02d}:{minuto_corrente:02d}",
        "giorno": core.get_giorno_settimana(),
        "giorno_numero": core.giorno_numero,
        "stagione": core.get_stagione(),
        "meteo": core.condizioni_meteo,
        "temperatura_esterna": round(temp_esterna, 1),
        "stanze": core.generate_agent_payload(requesting_agent)
    })


def _build_external_status():
    """Ritorna il contesto esterno/temporale minimo per gli agent."""
    ora_corrente, minuto_corrente = core.get_tempo_simulato()
    temp_esterna = core.calcola_temperatura_esterna(ora_corrente)
    payload = core.generate_agent_payload(None)
    giardino = payload.get("giardino", {})
    sensori_giardino = giardino.get("sensori", {})

    return {
        "ora": f"{ora_corrente:02d}:{minuto_corrente:02d}",
        "giorno": core.get_giorno_settimana(),
        "giorno_numero": core.giorno_numero,
        "stagione": core.get_stagione(),
        "meteo": core.condizioni_meteo,
        "temperatura_esterna": round(temp_esterna, 1),
        "luminosita_giardino": sensori_giardino.get("luminosita")
    }


@api_bp.route('/api/status/esterno', methods=['GET'])
def get_status_esterno():
    """Ritorna solo contesto esterno/temporale per agent reattivi (es. Luigi)."""
    core.simula_letture_sensori()
    core.aggiorna_tempo_simulato()
    return jsonify(_build_external_status())


@api_bp.route('/api/status/<stanza>', methods=['GET'])
def get_status_stanza(stanza):
    """Ritorna solo i dati della stanza richiesta + contesto esterno minimo."""
    core.simula_letture_sensori()
    core.aggiorna_tempo_simulato()

    agent_id = request.headers.get('X-Agent-Id')
    requesting_agent = agent_id.lower() if agent_id else None
    stanze_payload = core.generate_agent_payload(requesting_agent)

    if stanza not in stanze_payload:
        return jsonify({
            "errore": f"Stanza '{stanza}' non trovata",
            "stanze_disponibili": list(stanze_payload.keys())
        }), 404

    return jsonify({
        "stanza": stanza,
        "dati_stanza": stanze_payload[stanza],
        "contesto_esterno": _build_external_status()
    })


@api_bp.route('/api/dashboard/status', methods=['GET'])
def get_dashboard_status():
    """Ritorna lo stato completo per Dashboard UI - include metadati di configurazione.
    Gli attuatori vengono serializzati in formato flat (solo stringhe) per compatibilità con il frontend."""
    core.simula_letture_sensori()
    core.aggiorna_tempo_simulato()
    ora_corrente, minuto_corrente = core.get_tempo_simulato()
    temp_esterna = core.calcola_temperatura_esterna(ora_corrente)
    return jsonify({
        "ora": ora_corrente,
        "minuto": minuto_corrente,
        "giorno_settimana": core.get_giorno_settimana(),
        "giorno_settimana_idx": core.giorno_settimana_idx,
        "giorno_numero": core.giorno_numero,
        "stagione": core.get_stagione(),
        "stagione_idx": core.stagione_idx,
        "meteo": core.condizioni_meteo,
        "temperatura_esterna": round(temp_esterna, 1),
        "velocita_tempo": core.velocita_tempo,
        "n8n_interval_seconds": core.n8n_interval_seconds,
        "ultimo_update_dati": core.ultimo_update_dati,
        "ultimo_update_n8n": core.ultimo_update_n8n,
        "debug_mode": core.debug_mode,
        "simulation_paused": core.simulation_paused,
        "casa": core.get_stato_casa_flat()
    })


@api_bp.route('/api/agent/action', methods=['POST'])
def log_agent_action():
    """Registra una modifica eseguita dall'AI Agent"""
    data = request.get_json() or {}
    agent_id = request.headers.get('X-Agent-Id', 'unknown')
    action = data.get('action') or data.get('type') or 'unspecified'
    core.log_agent_action(agent_id, action, data)
    return jsonify({
        "status": "success"
    })


@api_bp.route('/api/<stanza>/<attuatore>', methods=['POST'])
def controlla_attuatore(stanza, attuatore):
    """Controlla un attuatore specifico (luci, clima, ecc.)"""
    
    if stanza not in core.stato_casa:
        return jsonify({"errore": f"Stanza '{stanza}' non trovata"}), 404
    
    if attuatore not in core.stato_casa[stanza]["attuatori"]:
        return jsonify({
            "errore": f"Attuatore '{attuatore}' non trovato in {stanza}",
            "attuatori_disponibili": list(core.stato_casa[stanza]["attuatori"].keys())
        }), 404
    
    data = request.get_json()
    if not data or 'azione' not in data:
        return jsonify({"errore": "Manca il parametro 'azione' (ON/OFF o APERTE/CHIUSE)"}), 400
    
    azione_raw = str(data['azione']).strip().upper()

    # Validazione e normalizzazione guidata dal registro ACTUATOR_TYPES
    tipo_reg = ACTUATOR_TYPES.get(attuatore)
    if tipo_reg:
        # Normalizza alias (es. OPEN -> ON per porta_garage)
        nuovo_stato = tipo_reg["alias"].get(azione_raw, azione_raw)
        if nuovo_stato not in tipo_reg["stati_validi"]:
            return jsonify({
                "errore": f"Stato '{nuovo_stato}' non valido per {attuatore}. "
                          f"Valori accettati: {', '.join(tipo_reg['stati_validi'])}"
            }), 400
    else:
        # Attuatore presente nella stanza ma non nel registro: fallback ON/OFF
        nuovo_stato = azione_raw
        if nuovo_stato not in ['ON', 'OFF']:
            return jsonify({"errore": f"Stato non valido per {attuatore}. Usa ON o OFF"}), 400
    
    # Determina la sorgente della modifica (source)
    agent_id = request.headers.get('X-Agent-Id')
    if agent_id:
        source = agent_id.lower()  # 'mario', 'luigi', ecc.
    else:
        source = 'user'  # Dashboard / utente umano
    
    # Aggiorna stato con metadati di modifica
    core.update_actuator(stanza, attuatore, nuovo_stato, source=source)
    
    # Log automatico se è un agente
    if agent_id:
        core.log_agent_action(agent_id, f"control_{attuatore}", {
            "stanza": stanza,
            "attuatore": attuatore,
            "azione": nuovo_stato
        })
    
    print(f"🏠 [{datetime.now().strftime('%H:%M:%S')}] {stanza.upper()}/{attuatore.upper()} → {nuovo_stato} (source: {source})")
    
    return jsonify({
        "status": "success",
        "stanza": stanza,
        "attuatore": attuatore,
        "nuovo_stato": nuovo_stato,
        "source": source,
        "messaggio": f"{attuatore.capitalize()} in {stanza} impostato a {nuovo_stato}"
    })


@api_bp.route('/api/time', methods=['POST'])
def set_time():
    """Imposta l'ora simulata del giorno"""
    data = request.get_json()
    if not data or 'ora' not in data:
        return jsonify({"errore": "Manca il parametro 'ora' (0-23)"}), 400
    
    nuova_ora = int(data['ora'])
    
    if not 0 <= nuova_ora <= 23:
        return jsonify({"errore": "Ora non valida. Usa un valore tra 0 e 23"}), 400
    
    core.ora_simulata = nuova_ora
    core.minuti_simulati = nuova_ora * 60
    core.ultimo_update_tempo_reale = datetime.now()
    
    # Forza ricalcolo sensori con nuova ora
    core.simula_letture_sensori()
    
    print(f"⏰ [{datetime.now().strftime('%H:%M:%S')}] Ora simulata impostata a {nuova_ora}:00")
    
    return jsonify({
        "status": "success",
        "ora_simulata": core.ora_simulata,
        "messaggio": f"Ora simulata impostata alle {nuova_ora}:00"
    })


@api_bp.route('/api/time-speed', methods=['POST'])
def set_time_speed():
    """Imposta la velocità di scorrimento del tempo simulato"""
    data = request.get_json()
    if not data or 'velocita' not in data:
        return jsonify({"errore": "Manca il parametro 'velocita'"}), 400

    nuova_velocita = int(data['velocita'])
    if not 0 <= nuova_velocita <= 600:
        return jsonify({"errore": "Velocità non valida. Usa un valore tra 0 e 600"}), 400

    # Allinea tempo simulato prima di cambiare velocità
    core.aggiorna_tempo_simulato()
    core.velocita_tempo = nuova_velocita

    print(f"⏩ [{datetime.now().strftime('%H:%M:%S')}] Velocità tempo simulato impostata a {nuova_velocita} min/min")

    return jsonify({
        "status": "success",
        "velocita_tempo": core.velocita_tempo,
        "messaggio": f"Velocità tempo impostata a {nuova_velocita} min sim / min reale"
    })


@api_bp.route('/api/presence', methods=['POST'])
def set_presence():
    """Imposta la presenza in una stanza e notifica n8n"""
    data = request.get_json() or {}
    stanza = data.get('stanza')
    presenza_raw = data.get('presenza')

    if stanza not in core.stato_casa:
        return jsonify({"errore": f"Stanza '{stanza}' non trovata"}), 404

    if presenza_raw is None:
        return jsonify({"errore": "Manca il parametro 'presenza' (true/false)"}), 400

    if isinstance(presenza_raw, bool):
        presenza = presenza_raw
    elif isinstance(presenza_raw, str):
        val = presenza_raw.strip().lower()
        if val in ('true', '1', 'yes', 'on', 'si', 'sì'):
            presenza = True
        elif val in ('false', '0', 'no', 'off'):
            presenza = False
        else:
            return jsonify({"errore": "Valore 'presenza' non valido. Usa true/false"}), 400
    elif isinstance(presenza_raw, (int, float)):
        if presenza_raw in (0, 1):
            presenza = bool(presenza_raw)
        else:
            return jsonify({"errore": "Valore 'presenza' non valido. Usa true/false"}), 400
    else:
        return jsonify({"errore": "Valore 'presenza' non valido. Usa true/false"}), 400

    core.stato_casa[stanza]["sensori"]["presenza"] = presenza

    # Log automatico se è un agente
    agent_id = request.headers.get('X-Agent-Id')
    if agent_id:
        core.log_agent_action(agent_id, "toggle_presence", {
            "stanza": stanza,
            "presenza": presenza
        })

    # Notifica n8n
    send_presence_webhook(stanza, presenza)

    stato = 'rilevata' if presenza else 'assente'
    print(f"👀 [{datetime.now().strftime('%H:%M:%S')}] Presenza {stato} in {stanza}")

    return jsonify({
        "status": "success",
        "stanza": stanza,
        "presenza": presenza,
        "messaggio": f"Presenza {stato} in {stanza}"
    })


@api_bp.route('/api/n8n-interval', methods=['POST'])
def set_n8n_interval():
    """Imposta l'intervallo di esecuzione dell'AI Agent (n8n) in secondi"""
    data = request.get_json()
    if not data or 'seconds' not in data:
        return jsonify({"errore": "Manca il parametro 'seconds'"}), 400

    nuovi_secondi = int(data['seconds'])
    if not 10 <= nuovi_secondi <= 300:
        return jsonify({"errore": "Intervallo non valido. Usa un valore tra 10 e 300 secondi"}), 400

    core.n8n_interval_seconds = nuovi_secondi

    if core.scheduler is not None:
        core.scheduler.reschedule_job(
            'ai_agent_loop',
            trigger=IntervalTrigger(seconds=core.n8n_interval_seconds)
        )

    print(f"🤖 [{datetime.now().strftime('%H:%M:%S')}] Intervallo AI Agent impostato a {core.n8n_interval_seconds}s")

    return jsonify({
        "status": "success",
        "n8n_interval_seconds": core.n8n_interval_seconds,
        "messaggio": f"Intervallo AI Agent impostato a {core.n8n_interval_seconds} secondi"
    })


@api_bp.route('/api/day', methods=['POST'])
def set_day():
    """Imposta manualmente il giorno della settimana"""
    data = request.get_json()
    if not data or 'giorno' not in data:
        return jsonify({"errore": "Manca il parametro 'giorno' (0-6 o nome)"}), 400
    
    giorno = data['giorno']
    
    # Accetta sia indice (0-6) che nome del giorno
    if isinstance(giorno, int):
        if not 0 <= giorno <= 6:
            return jsonify({"errore": "Indice giorno non valido. Usa un valore tra 0 (Lunedì) e 6 (Domenica)"}), 400
        core.giorno_settimana_idx = giorno
    elif isinstance(giorno, str):
        try:
            core.giorno_settimana_idx = core.giorni_settimana.index(giorno.capitalize())
        except ValueError:
            return jsonify({
                "errore": f"Nome giorno non valido. Usa uno tra: {', '.join(core.giorni_settimana)}"
            }), 400
    else:
        return jsonify({"errore": "Formato non valido"}), 400
    
    # Log automatico se è un agente
    agent_id = request.headers.get('X-Agent-Id')
    if agent_id:
        core.log_agent_action(agent_id, "set_day", {
            "giorno_settimana": core.get_giorno_settimana(),
            "giorno_settimana_idx": core.giorno_settimana_idx,
            "giorno_numero": core.giorno_numero
        })
    
    print(f"📅 [{datetime.now().strftime('%H:%M:%S')}] Giorno impostato manualmente a {core.get_giorno_settimana()}")
    
    return jsonify({
        "status": "success",
        "giorno_settimana": core.get_giorno_settimana(),
        "giorno_settimana_idx": core.giorno_settimana_idx,
        "giorno_numero": core.giorno_numero,
        "messaggio": f"Giorno impostato a {core.get_giorno_settimana()}"
    })


@api_bp.route('/api/season', methods=['POST'])
def set_season():
    """Imposta manualmente la stagione"""
    data = request.get_json()
    if not data or 'stagione' not in data:
        return jsonify({"errore": "Manca il parametro 'stagione' (0-3 o nome)"}), 400
    
    stagione = data['stagione']
    
    # Accetta sia indice (0-3) che nome della stagione
    if isinstance(stagione, int):
        if not 0 <= stagione <= 3:
            return jsonify({"errore": "Indice stagione non valido. Usa un valore tra 0 (Inverno) e 3 (Autunno)"}), 400
        core.stagione_idx = stagione
    elif isinstance(stagione, str):
        try:
            core.stagione_idx = core.stagioni.index(stagione.capitalize())
        except ValueError:
            return jsonify({
                "errore": f"Nome stagione non valido. Usa uno tra: {', '.join(core.stagioni)}"
            }), 400
    else:
        return jsonify({"errore": "Formato non valido"}), 400
    
    # Invalida cache temperatura
    core._cache_temp_esterna.clear()
    
    # Log automatico se è un agente
    agent_id = request.headers.get('X-Agent-Id')
    if agent_id:
        core.log_agent_action(agent_id, "set_season", {
            "stagione": core.get_stagione(),
            "stagione_idx": core.stagione_idx
        })
    
    print(f"🌿 [{datetime.now().strftime('%H:%M:%S')}] Stagione impostata a {core.get_stagione()}")
    
    return jsonify({
        "status": "success",
        "stagione": core.get_stagione(),
        "stagione_idx": core.stagione_idx,
        "messaggio": f"Stagione impostata a {core.get_stagione()}"
    })


@api_bp.route('/api/weather', methods=['POST'])
def set_weather():
    """Imposta le condizioni atmosferiche"""
    data = request.get_json()
    if not data or 'condizione' not in data:
        return jsonify({"errore": "Manca il parametro 'condizione'"}), 400

    condizione = data['condizione']
    opzioni = ['Sereno', 'Nuvoloso', 'Pioggia', 'Temporale', 'Neve', 'Nebbia']
    if condizione not in opzioni:
        return jsonify({"errore": "Condizione non valida"}), 400

    core.condizioni_meteo = condizione
    
    # Invalida cache
    core._cache_temp_esterna.clear()
    core._cache_meteo_fattori = None
    core._cache_meteo_condizione = None
    
    core.simula_letture_sensori()

    # Log automatico se è un agente
    agent_id = request.headers.get('X-Agent-Id')
    if agent_id:
        core.log_agent_action(agent_id, "set_weather", {
            "condizioni_meteo": core.condizioni_meteo
        })

    print(f"⛅ [{datetime.now().strftime('%H:%M:%S')}] Meteo impostato a {core.condizioni_meteo}")

    return jsonify({
        "status": "success",
        "condizioni_meteo": core.condizioni_meteo,
        "messaggio": f"Meteo impostato a {core.condizioni_meteo}"
    })


@api_bp.route('/api/query', methods=['POST'])
def query_stato():
    """Query intelligente dello stato casa per AI Agent"""
    data = request.get_json()
    query_type = data.get('type', 'all')
    
    if query_type == 'temperature':
        temps = {stanza: dati["sensori"]["temperatura"] 
                for stanza, dati in core.stato_casa.items()}
        return jsonify({"temperature": temps})
    
    elif query_type == 'luci':
        luci = {stanza: core.get_actuator_value(stanza, "luci")
               for stanza, dati in core.stato_casa.items()
               if "luci" in dati["attuatori"]}
        return jsonify({"luci": luci})
    
    elif query_type == 'problemi':
        problemi = []
        for stanza, dati in core.stato_casa.items():
            temp = dati["sensori"]["temperatura"]
            lux = dati["sensori"]["luminosita"]
            
            if temp < 18:
                problemi.append(f"{stanza}: temperatura troppo bassa ({temp}°C)")
            if temp > 26:
                problemi.append(f"{stanza}: temperatura troppo alta ({temp}°C)")
            if lux < 200 and 8 <= core.ora_simulata < 20:
                luci_val = core.get_actuator_value(stanza, "luci") if "luci" in dati["attuatori"] else "OFF"
                if luci_val == "OFF":
                    problemi.append(f"{stanza}: troppo buio durante il giorno ({lux} lux)")
        
        return jsonify({"problemi": problemi, "count": len(problemi)})
    
    else:
        return jsonify({"casa": core.get_stato_casa_flat(), "ora_simulata": core.ora_simulata})


@api_bp.route('/api/logs/agent', methods=['GET'])
def get_agent_logs():
    """Ritorna i log degli agenti - opzionalmente filtrati per data"""
    import os
    from config import LOG_DIR
    
    date_filter = request.args.get('date')  # YYYY-MM-DD format
    agent_filter = request.args.get('agent')
    
    log_dir = LOG_DIR
    if not os.path.exists(log_dir):
        return jsonify({"logs": [], "messaggio": "Nessun log trovato"})
    
    logs = []
    
    # Se specificata una data, leggi quel file specifico
    if date_filter:
        log_file = os.path.join(log_dir, f"agent-{date_filter}.jsonl")
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            record = json.loads(line)
                            if not agent_filter or record.get('agent_id') == agent_filter:
                                logs.append(record)
                        except json.JSONDecodeError:
                            pass
    else:
        # Leggi gli ultimi 3 giorni
        for filename in sorted(os.listdir(log_dir), reverse=True)[:3]:
            if filename.startswith('agent-') and filename.endswith('.jsonl'):
                log_file = os.path.join(log_dir, filename)
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                record = json.loads(line)
                                if not agent_filter or record.get('agent_id') == agent_filter:
                                    logs.append(record)
                            except json.JSONDecodeError:
                                pass
    
    return jsonify({"logs": logs, "count": len(logs)})


@api_bp.route('/api/logs/agent', methods=['DELETE'])
def delete_agent_logs():
    """Elimina tutti i log degli agenti"""
    import os
    import shutil
    from config import LOG_DIR
    
    log_dir = LOG_DIR
    
    try:
        if os.path.exists(log_dir):
            # Elimina tutti i file .jsonl nella directory
            deleted_count = 0
            for filename in os.listdir(log_dir):
                if filename.startswith('agent-') and filename.endswith('.jsonl'):
                    file_path = os.path.join(log_dir, filename)
                    os.remove(file_path)
                    deleted_count += 1
            
            print(f"🗑️ [{datetime.now().strftime('%H:%M:%S')}] {deleted_count} file log eliminati")
            
            return jsonify({
                "status": "success",
                "messaggio": f"Log eliminati: {deleted_count} file",
                "files_deleted": deleted_count
            })
        else:
            return jsonify({
                "status": "success",
                "messaggio": "Directory log non trovata",
                "files_deleted": 0
            })
    
    except Exception as e:
        print(f"❌ Errore eliminazione log: {e}")
        return jsonify({
            "status": "error",
            "messaggio": f"Errore nell'eliminazione: {str(e)}"
        }), 500


@api_bp.route('/api/logs/agent/delete', methods=['DELETE'])
def delete_single_log():
    """Elimina un singolo log specifico"""
    import os
    from config import LOG_DIR
    
    ts_sim = request.args.get('ts_sim')  # es: 2026-02-05T08:30:00
    agent_id = request.args.get('agent_id')
    giorno_numero = request.args.get('giorno_numero')
    giorno_nome = request.args.get('giorno_nome')
    
    if not ts_sim or not agent_id or not giorno_numero or not giorno_nome:
        return jsonify({
            "status": "error",
            "messaggio": "Mancano i parametri ts_sim, agent_id, giorno_numero, giorno_nome"
        }), 400
    
    try:
        from datetime import datetime
        
        log_dir = LOG_DIR
        # Formato nuovo: agent-day-01-lunedi.jsonl
        log_file = os.path.join(log_dir, f"agent-day-{giorno_numero:0>2s}-{giorno_nome.lower()}.jsonl")
        
        if not os.path.exists(log_file):
            return jsonify({
                "status": "error",
                "messaggio": "File log non trovato"
            }), 404
        
        # Leggi il file e filtra le righe
        remaining_logs = []
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        # Mantieni il log solo se NON corrisponde a quello da eliminare
                        if not (record.get('ts_sim') == ts_sim and record.get('agent_id') == agent_id):
                            remaining_logs.append(line.rstrip('\n'))
                    except json.JSONDecodeError:
                        pass
        
        # Riscrivi il file
        if remaining_logs:
            with open(log_file, 'w', encoding='utf-8') as f:
                for line in remaining_logs:
                    f.write(line + '\n')
        else:
            # Se non ci sono più log, elimina il file
            os.remove(log_file)
        
        print(f"🗑️ [{datetime.now().strftime('%H:%M:%S')}] Log eliminato: {ts_sim} da {agent_id}")
        
        return jsonify({
            "status": "success",
            "messaggio": "Log eliminato",
            "ts_sim": ts_sim,
            "agent_id": agent_id
        })
    
    except Exception as e:
        print(f"❌ Errore eliminazione log singolo: {e}")
        return jsonify({
            "status": "error",
            "messaggio": f"Errore nell'eliminazione: {str(e)}"
        }), 500


@api_bp.route('/api/actions/scenario/<scenario_name>', methods=['POST'])
def applica_scenario(scenario_name):
    """Applica scenari predefiniti"""
    azioni = []
    
    # Determina la sorgente della modifica
    agent_id = request.headers.get('X-Agent-Id')
    source = agent_id.lower() if agent_id else 'user'
    
    if scenario_name == "buongiorno":
        for stanza, dati in core.stato_casa.items():
            if "tapparelle" in dati["attuatori"]:
                core.update_actuator(stanza, "tapparelle", "APERTE", source=source)
                azioni.append(f"Tapparelle aperte in {stanza}")
            if "clima" in dati["attuatori"]:
                if core.stagione_idx == 0:  # Inverno
                    core.update_actuator(stanza, "clima", "HEAT", source=source)
                    azioni.append(f"Riscaldamento attivato in {stanza}")
                else:
                    core.update_actuator(stanza, "clima", "OFF", source=source)
    
    elif scenario_name == "buonanotte":
        for stanza, dati in core.stato_casa.items():
            if "luci" in dati["attuatori"]:
                core.update_actuator(stanza, "luci", "OFF", source=source)
                azioni.append(f"Luci spente in {stanza}")
            if "tapparelle" in dati["attuatori"]:
                core.update_actuator(stanza, "tapparelle", "CHIUSE", source=source)
                azioni.append(f"Tapparelle chiuse in {stanza}")
            if "finestre" in dati["attuatori"]:
                core.update_actuator(stanza, "finestre", "CHIUSE", source=source)
                azioni.append(f"Finestre chiuse in {stanza}")
            if "tv" in dati["attuatori"]:
                core.update_actuator(stanza, "tv", "OFF", source=source)
    
    elif scenario_name == "cinema":
        if "soggiorno" in core.stato_casa:
            core.update_actuator("soggiorno", "luci", "OFF", source=source)
            core.update_actuator("soggiorno", "tv", "ON", source=source)
            core.update_actuator("soggiorno", "tapparelle", "CHIUSE", source=source)
            azioni.append("Modalità cinema attivata in soggiorno")
    
    elif scenario_name == "via_da_casa":
        for stanza, dati in core.stato_casa.items():
            if "luci" in dati["attuatori"]:
                core.update_actuator(stanza, "luci", "OFF", source=source)
            if "tv" in dati["attuatori"]:
                core.update_actuator(stanza, "tv", "OFF", source=source)
            if "clima" in dati["attuatori"]:
                core.update_actuator(stanza, "clima", "OFF", source=source)
            if "tapparelle" in dati["attuatori"]:
                core.update_actuator(stanza, "tapparelle", "CHIUSE", source=source)
            if "finestre" in dati["attuatori"]:
                core.update_actuator(stanza, "finestre", "CHIUSE", source=source)
        azioni.append("Casa in modalità 'Via da casa'")
    
    # Aggiorna timestamp
    
    # Log automatico se è un agente
    agent_id = request.headers.get('X-Agent-Id')
    if agent_id:
        core.log_agent_action(agent_id, f"scenario_{scenario_name}", {
            "azioni_eseguite": azioni
        })
    
    return jsonify({
        "status": "success",
        "scenario": scenario_name,
        "azioni_eseguite": azioni,
        "timestamp": datetime.now().isoformat()
    })


@api_bp.route('/api/logs/analysis', methods=['GET'])
def get_logs_analysis():
    """Ritorna tutti i log con analisi e statistiche per gli AI Agents"""
    import os
    from collections import defaultdict
    from config import LOG_DIR
    
    try:
        log_dir = LOG_DIR
        if not os.path.exists(log_dir):
            return jsonify({
                "status": "success",
                "logs": [],
                "statistics": {
                    "total_logs": 0,
                    "agents": {},
                    "actions": {},
                    "days": []
                },
                "timeline": {}
            })
        
        all_logs = []
        agents_count = defaultdict(int)
        actions_count = defaultdict(int)
        days_data = defaultdict(list)
        timeline = defaultdict(list)
        
        # Leggi tutti i file log
        for filename in sorted(os.listdir(log_dir)):
            if filename.startswith('agent-day-') and filename.endswith('.jsonl'):
                log_file = os.path.join(log_dir, filename)
                
                # Estrai il giorno dal filename (agent-day-01-lunedi.jsonl)
                parts = filename.replace('agent-day-', '').replace('.jsonl', '').split('-')
                giorno_numero = parts[0]
                giorno_nome = parts[1] if len(parts) > 1 else 'unknown'
                
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                record = json.loads(line)
                                
                                # Aggiungi metadata utili
                                record['file'] = filename
                                record['giorno_numero'] = int(record.get('giorno_numero', giorno_numero))
                                record['giorno_nome'] = record.get('giorno_nome', giorno_nome)
                                
                                all_logs.append(record)
                                
                                # Aggiorna statistiche
                                agent = record.get('agent_id', 'unknown')
                                action = record.get('action', 'unknown')
                                
                                agents_count[agent] += 1
                                actions_count[action] += 1
                                
                                days_data[f"{record.get('giorno_numero', 'N/A')}-{record.get('giorno_nome', 'unknown')}"].append(record)
                                
                                timeline[f"{record.get('giorno_numero', 'N/A')}-{record.get('giorno_nome', 'unknown')}"].append({
                                    "time": record.get('ts_sim'),
                                    "agent": agent,
                                    "action": action
                                })
                                
                            except json.JSONDecodeError:
                                pass
        
        # Ordina i log per giorno e orario
        all_logs.sort(key=lambda x: (x.get('giorno_numero', 0), x.get('ts_sim', '')))
        
        # Calcola statistiche aggregate
        stats_by_agent = {}
        for agent, count in agents_count.items():
            agent_logs = [log for log in all_logs if log.get('agent_id') == agent]
            action_types = defaultdict(int)
            for log in agent_logs:
                action_types[log.get('action')] += 1
            
            stats_by_agent[agent] = {
                "total_actions": count,
                "actions_by_type": dict(action_types)
            }
        
        return jsonify({
            "status": "success",
            "logs": all_logs,
            "statistics": {
                "total_logs": len(all_logs),
                "total_agents": len(agents_count),
                "total_actions": len(actions_count),
                "agents": dict(agents_count),
                "agents_detailed": stats_by_agent,
                "actions": dict(actions_count),
                "days_count": len(days_data)
            },
            "timeline": dict(timeline),
            "days_summary": {
                day: {
                    "log_count": len(logs),
                    "unique_agents": len(set(log.get('agent_id') for log in logs))
                }
                for day, logs in days_data.items()
            }
        })
    
    except Exception as e:
        print(f"❌ Errore analisi log: {e}")
        return jsonify({
            "status": "error",
            "messaggio": f"Errore nell'analisi: {str(e)}"
        }), 500


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check per verificare che il servizio sia attivo"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "stanze_attive": len(core.stato_casa)
    })


# ============================================================================
# PREFERENZE UTENTE
# ============================================================================

@api_bp.route('/api/preferences', methods=['GET'])
@api_bp.route('/api/preferences/', methods=['GET'])
def get_all_preferences():
    """Ritorna tutte le preferenze utente (note_generali + per stanza).
    
    Usato dalla dashboard per visualizzare/editare tutte le preferenze,
    e dagli AI Agent per ottenere il quadro completo.
    """
    return jsonify(core.preferenze_utente)


@api_bp.route('/api/preferences/<stanza>', methods=['GET'])
@api_bp.route('/api/preferences/<stanza>/', methods=['GET'])
def get_room_preferences(stanza):
    """Ritorna le preferenze per una stanza specifica.
    
    Questo è l'endpoint che gli AI Agent (Mario/Luigi) chiamano
    tramite il tool `ottieni_preferenze`.
    """
    stanza_prefs = core.preferenze_utente.get(stanza)
    
    if stanza_prefs is None or not isinstance(stanza_prefs, dict):
        return jsonify({
            "errore": f"Nessuna preferenza trovata per la stanza '{stanza}'",
            "stanze_disponibili": [k for k in core.preferenze_utente.keys() if k != "note_generali"]
        }), 404
    
    risposta = {**stanza_prefs, "stanza": stanza}
    return jsonify(risposta)


@api_bp.route('/api/preferences', methods=['PUT'])
@api_bp.route('/api/preferences/', methods=['PUT'])
def update_all_preferences():
    """Aggiorna più preferenze in una sola richiesta (merge parziale).
    
    Body: {"cucina": {"temperatura_ideale": 23, "blocco_finestre": "bloccate"}, "note_generali": "..."}
    Solo i campi specificati vengono sovrascritti; gli altri restano invariati.
    """
    data = request.get_json()
    if not data:
        return jsonify({"errore": "Body JSON mancante"}), 400
    
    errori = []
    aggiornate = []
    
    for chiave, valori in data.items():
        if chiave == "note_generali":
            if not isinstance(valori, str):
                errori.append("'note_generali' deve essere una stringa")
                continue
            core.preferenze_utente["note_generali"] = valori
            aggiornate.append("note_generali")
        elif chiave in core.preferenze_utente and isinstance(core.preferenze_utente[chiave], dict):
            if not isinstance(valori, dict):
                errori.append(f"'{chiave}': il valore deve essere un oggetto JSON")
                continue
            err = _valida_stanza(chiave, valori)
            if err:
                errori.extend(err)
                continue
            core.preferenze_utente[chiave].update(valori)
            aggiornate.append(chiave)
        else:
            errori.append(f"'{chiave}' non è una chiave valida")
    
    # Log source
    source = request.headers.get('X-Agent-Id', 'user')
    print(f"📝 [{datetime.now().strftime('%H:%M:%S')}] Preferenze aggiornate: {aggiornate} (source: {source})")
    
    # Salva su file
    if aggiornate:
        core.save_preferences()
        core.log_agent_action(source, "update_preferences_bulk", {
            "aggiornate": aggiornate,
            "payload": {k: data[k] for k in aggiornate if k in data}
        })
    
    result = {"status": "success", "aggiornate": aggiornate}
    if errori:
        result["errori"] = errori
        result["status"] = "partial" if aggiornate else "error"
    
    status_code = 200 if aggiornate else 400
    return jsonify(result), status_code


@api_bp.route('/api/preferences/<stanza>', methods=['PUT'])
@api_bp.route('/api/preferences/<stanza>/', methods=['PUT'])
def update_room_preferences(stanza):
    """Aggiorna le preferenze di una singola stanza o le note_generali (merge parziale).
    
    Body: {"temperatura_ideale": 23, "blocco_finestre": "auto", "note": "Preferisco luce soffusa"}
    Se stanza == "note_generali": Body: {"note_generali": "testo"}
    """
    # Gestione note_generali come caso speciale
    if stanza == "note_generali":
        data = request.get_json()
        if not data:
            return jsonify({"errore": "Body JSON mancante"}), 400
        nuovo_valore = data.get("note_generali", data.get("note", ""))
        if not isinstance(nuovo_valore, str):
            return jsonify({"errore": "note_generali deve essere una stringa"}), 400
        core.preferenze_utente["note_generali"] = nuovo_valore
        core.save_preferences()
        source = request.headers.get('X-Agent-Id', 'user')
        core.log_agent_action(source, "update_note_generali", {"note_generali": nuovo_valore})
        return jsonify({"status": "success", "note_generali": nuovo_valore})

    if stanza not in core.preferenze_utente or not isinstance(core.preferenze_utente.get(stanza), dict):
        return jsonify({
            "errore": f"Stanza '{stanza}' non trovata",
            "stanze_disponibili": [k for k in core.preferenze_utente.keys() if k != "note_generali"]
        }), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"errore": "Body JSON mancante"}), 400
    
    err = _valida_stanza(stanza, data)
    if err:
        return jsonify({"errore": err}), 400
    
    core.preferenze_utente[stanza].update(data)
    
    core.save_preferences()
    
    source = request.headers.get('X-Agent-Id', 'user')
    core.log_agent_action(source, "update_preferences_room", {
        "stanza": stanza,
        "preferenze": data
    })
    print(f"📝 [{datetime.now().strftime('%H:%M:%S')}] Preferenze {stanza} aggiornate (source: {source})")
    
    return jsonify({
        "status": "success",
        "stanza": stanza,
        "preferenze": core.preferenze_utente[stanza]
    })


@api_bp.route('/api/preferences', methods=['DELETE'])
@api_bp.route('/api/preferences/', methods=['DELETE'])
def reset_preferences():
    """Ripristina tutte le preferenze ai valori di default."""
    from models.preferences import get_default_preferences
    core.preferenze_utente = get_default_preferences()
    core.save_preferences()
    source = request.headers.get('X-Agent-Id', 'user')
    core.log_agent_action(source, "reset_preferences", {
        "status": "default_restored"
    })
    print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Preferenze ripristinate ai default")
    return jsonify({"status": "success", "messaggio": "Preferenze ripristinate ai valori di default"})


@api_bp.route('/api/preferences/<stanza>', methods=['DELETE'])
@api_bp.route('/api/preferences/<stanza>/', methods=['DELETE'])
def reset_room_preferences(stanza):
    """Ripristina preferenze stanza, note_generali, o tutte le preferenze via alias."""
    from models.preferences import get_default_preferences

    defaults = get_default_preferences()
    source = request.headers.get('X-Agent-Id', 'user')

    stanza_norm = (stanza or "").strip().lower()

    # Alias robusti per reset totale (utile per tool n8n che richiede sempre <stanza>)
    if stanza_norm in ("all", "tutte", "totale", "total", "*", "casa"):
        core.preferenze_utente = defaults
        core.save_preferences()
        core.log_agent_action(source, "reset_preferences", {
            "status": "default_restored",
            "mode": "alias_total",
            "alias": stanza
        })
        print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Preferenze ripristinate ai default (alias: {stanza}, source: {source})")
        return jsonify({
            "status": "success",
            "mode": "total",
            "messaggio": "Preferenze ripristinate ai valori di default"
        })

    # Alias per reset sole note generali
    if stanza_norm in ("note_generali", "generali", "globali"):
        core.preferenze_utente["note_generali"] = defaults.get("note_generali", "")
        core.save_preferences()
        core.log_agent_action(source, "reset_note_generali", {
            "status": "default_restored",
            "alias": stanza
        })
        print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Note generali ripristinate (alias: {stanza}, source: {source})")
        return jsonify({
            "status": "success",
            "mode": "note_generali",
            "note_generali": core.preferenze_utente["note_generali"],
            "messaggio": "Note generali ripristinate ai valori di default"
        })

    if stanza not in core.preferenze_utente or not isinstance(core.preferenze_utente.get(stanza), dict):
        return jsonify({
            "errore": f"Stanza '{stanza}' non trovata",
            "stanze_disponibili": [k for k in core.preferenze_utente.keys() if k != "note_generali"]
        }), 404

    if stanza not in defaults:
        return jsonify({"errore": f"Nessun default per '{stanza}'"}), 404

    core.preferenze_utente[stanza] = defaults[stanza]
    core.save_preferences()
    core.log_agent_action(source, "reset_preferences_room", {
        "stanza": stanza,
        "status": "default_restored"
    })
    print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Preferenze {stanza} ripristinate ai default (source: {source})")

    return jsonify({
        "status": "success",
        "stanza": stanza,
        "preferenze": core.preferenze_utente[stanza],
        "messaggio": f"Preferenze '{stanza}' ripristinate ai valori di default"
    })


def _valida_stanza(stanza, data):
    """Valida i campi delle preferenze di una stanza. Ritorna lista errori o []."""
    # Compatibilità legacy: finestre_con_clima -> blocco_finestre
    if "finestre_con_clima" in data and "blocco_finestre" not in data:
        legacy = str(data["finestre_con_clima"]).strip().lower()
        data["blocco_finestre"] = "bloccate" if legacy in ("sempre_chiuse", "bloccate") else "auto"
    if "finestre_con_clima" in data:
        del data["finestre_con_clima"]

    if "blocco_finestre" in data:
        val_norm = str(data["blocco_finestre"]).strip().lower()
        data["blocco_finestre"] = "bloccate" if val_norm in ("sempre_chiuse", "bloccate") else "auto"

    errori = []
    if "temperatura_ideale" in data:
        if stanza not in STANZE_CON_CLIMA:
            errori.append(f"{stanza}: temperatura_ideale non applicabile (stanza senza clima)")
        val = data["temperatura_ideale"]
        if not isinstance(val, (int, float)) or val < 10 or val > 30:
            errori.append(f"{stanza}: temperatura_ideale deve essere tra 10 e 30")
    if "luci_ingresso" in data:
        val = data["luci_ingresso"]
        if val not in VALID_LUCI_INGRESSO:
            errori.append(f"{stanza}: luci_ingresso deve essere uno tra {VALID_LUCI_INGRESSO}")
    if "tapparelle_giorno" in data:
        if stanza not in STANZE_CON_TAPPARELLE:
            errori.append(f"{stanza}: tapparelle_giorno non applicabile (stanza senza tapparelle)")
        val = data["tapparelle_giorno"]
        if val not in VALID_TAPPARELLE:
            errori.append(f"{stanza}: tapparelle_giorno deve essere APERTE o CHIUSE")
    if "tapparelle_notte" in data:
        if stanza not in STANZE_CON_TAPPARELLE:
            errori.append(f"{stanza}: tapparelle_notte non applicabile (stanza senza tapparelle)")
        val = data["tapparelle_notte"]
        if val not in VALID_TAPPARELLE:
            errori.append(f"{stanza}: tapparelle_notte deve essere APERTE o CHIUSE")
    if "blocco_finestre" in data:
        if stanza not in STANZE_CON_FINESTRE:
            errori.append(f"{stanza}: blocco_finestre non applicabile (stanza senza finestre)")
        val = data["blocco_finestre"]
        if val not in VALID_BLOCCO_FINESTRE:
            errori.append(f"{stanza}: blocco_finestre deve essere uno tra {VALID_BLOCCO_FINESTRE}")
    return errori


@api_bp.route('/api/debug', methods=['POST'])
def toggle_debug():
    """Attiva/disattiva la modalità debug.
    In debug mode le azioni dalla dashboard non lasciano traccia nei metadati
    (modified_by/last_modified_at), così Mario non vede lock temporanei."""
    data = request.get_json() or {}
    
    if 'enabled' in data:
        core.debug_mode = bool(data['enabled'])
    else:
        core.debug_mode = not core.debug_mode  # Toggle
    
    stato = 'attivata' if core.debug_mode else 'disattivata'
    print(f"\U0001f41b [{datetime.now().strftime('%H:%M:%S')}] Modalit\u00e0 DEBUG {stato}")
    
    return jsonify({
        "status": "success",
        "debug_mode": core.debug_mode,
        "messaggio": f"Modalit\u00e0 debug {stato}"
    })


@api_bp.route('/api/pause', methods=['POST'])
def toggle_pause():
    """Mette in pausa o riprende la simulazione.
    Blocca sia il tempo simulato sia l'esecuzione dello scheduler n8n."""
    data = request.get_json(silent=True) or {}
    
    if 'paused' in data:
        core.simulation_paused = bool(data['paused'])
    else:
        core.simulation_paused = not core.simulation_paused  # Toggle
    
    # Riallinea il riferimento temporale per evitare salti al resume
    core.ultimo_update_tempo_reale = datetime.now()
    
    stato = 'in pausa' if core.simulation_paused else 'ripresa'
    print(f"\u23f8\ufe0f [{datetime.now().strftime('%H:%M:%S')}] Simulazione {stato}")
    
    return jsonify({
        "status": "success",
        "simulation_paused": core.simulation_paused,
        "messaggio": f"Simulazione {stato}"
    })
