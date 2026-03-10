"""
Core module - Stato globale e funzioni condivise dell'applicazione
"""
import json
import os
import random
from uuid import uuid4
from datetime import datetime, timedelta
from config import (
    GIORNI_SETTIMANA, STAGIONI,
    TEMP_TARGET_HEAT, TEMP_TARGET_COOL, TEMP_MIN, TEMP_MAX, ISOLAMENTO_CASA,
    RATE_HEAT, RATE_COOL, RATE_PASSIVO, RATE_FINESTRE_APERTE,
    VELOCITA_TEMPO_DEFAULT,
    N8N_INTERVAL_SECONDS_DEFAULT,
    SIM_START_DATE, LOG_DIR,
    LOCK_COOLDOWN_MINUTES,
    PREFERENCES_FILE
)
from models import get_initial_state, get_default_preferences
from models.preferences import normalize_preferences
from simulation import calcola_temperatura_esterna_pura, calcola_luce_naturale_pura, get_meteo_fattori_puro
from api import send_presence_webhook

# Stato globale dell'applicazione
ora_simulata = 12
minuti_simulati = 12 * 60
velocita_tempo = VELOCITA_TEMPO_DEFAULT
ultimo_update_tempo_reale = datetime.now()
giorni_settimana = GIORNI_SETTIMANA
giorno_settimana_idx = 0
giorno_numero = 1
stagioni = STAGIONI
stagione_idx = 1
condizioni_meteo = "Sereno"
ultimo_update_minuti_simulati = minuti_simulati
n8n_interval_seconds = N8N_INTERVAL_SECONDS_DEFAULT
scheduler = None
ultimo_update_n8n = None
ultimo_update_dati = None
_cache_temp_esterna = {}
_cache_meteo_fattori = None
_cache_meteo_condizione = None
stato_casa = get_initial_state()
preferenze_utente = get_default_preferences()
session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
debug_mode = False  # Modalità debug: azioni dashboard non lasciano traccia nei metadati
simulation_paused = False  # Pausa simulazione: blocca tempo simulato e scheduler n8n


# ---------------------------------------------------------------------------
# Persistenza preferenze su file JSON
# ---------------------------------------------------------------------------

def load_preferences():
    """Carica le preferenze da file JSON. Se il file non esiste, usa i default."""
    global preferenze_utente
    if os.path.exists(PREFERENCES_FILE):
        try:
            with open(PREFERENCES_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            preferenze_utente = normalize_preferences(loaded)
            print(f"📂 Preferenze caricate da {PREFERENCES_FILE}")
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Errore lettura {PREFERENCES_FILE}: {e} — uso default")
            preferenze_utente = get_default_preferences()
    else:
        print(f"📂 {PREFERENCES_FILE} non trovato — uso preferenze di default")


def save_preferences():
    """Salva le preferenze correnti su file JSON."""
    try:
        with open(PREFERENCES_FILE, 'w', encoding='utf-8') as f:
            json.dump(preferenze_utente, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"❌ Errore salvataggio preferenze: {e}")


# Carica preferenze da file all'avvio
load_preferences()


# ---------------------------------------------------------------------------
# Helper per attuatori con metadati
# ---------------------------------------------------------------------------

def get_actuator_value(stanza, dispositivo):
    """Ritorna SOLO il valore flat (stringa) di un attuatore.
    
    Compatibile col vecchio formato: se l'attuatore è ancora una stringa
    (edge-case durante la migrazione) la ritorna direttamente.
    """
    att = stato_casa[stanza]["attuatori"][dispositivo]
    if isinstance(att, dict):
        return att["stato"]
    return att  # fallback legacy


def update_actuator(stanza, dispositivo, nuovo_stato, source=None):
    """Aggiorna lo stato di un attuatore salvando i metadati di modifica.
    
    Args:
        stanza (str): Nome della stanza (es. 'soggiorno')
        dispositivo (str): Nome dell'attuatore (es. 'clima')
        nuovo_stato (str): Nuovo valore (es. 'ON', 'OFF', 'HEAT', 'COOL', 'APERTE', 'CHIUSE')
        source (str|None): Chi ha fatto la modifica ('mario', 'luigi', 'user') o None per sistema
    
    Returns:
        dict: Metadati completi dell'attuatore dopo l'aggiornamento
    """
    att = stato_casa[stanza]["attuatori"][dispositivo]
    
    # Migrazione automatica da formato legacy (stringa) a dict
    if not isinstance(att, dict):
        att = {
            "stato": att,
            "last_modified_at": None,
            "modified_by": None
        }
    
    att["stato"] = nuovo_stato
    # In debug mode le azioni non lasciano traccia (niente lock per mario)
    if not debug_mode:
        att["last_modified_at"] = get_simulated_datetime()
        att["modified_by"] = source
    
    stato_casa[stanza]["attuatori"][dispositivo] = att
    return att


def get_stato_casa_flat():
    """Ritorna una copia dello stato casa con gli attuatori in formato 'flat' (solo stringhe).
    
    Usato dalla dashboard e da tutti gli endpoint che non necessitano dei metadati.
    Mantiene la struttura: casa -> stanze -> attuatori (stringhe), sensori.
    """
    flat = {}
    for stanza, dati in stato_casa.items():
        # Copia sensori con temperatura arrotondata per la dashboard
        sensori_out = dict(dati["sensori"])
        sensori_out["temperatura"] = round(sensori_out["temperatura"], 1)
        flat[stanza] = {
            "sensori": sensori_out,
            "attuatori": {}
        }
        for nome, att in dati["attuatori"].items():
            if isinstance(att, dict):
                flat[stanza]["attuatori"][nome] = att["stato"]
            else:
                flat[stanza]["attuatori"][nome] = att  # fallback legacy
    return flat


def generate_agent_payload(requesting_agent=None):
    """Genera il payload JSON per un AI Agent.
    
    Struttura pulita: solo dati di stato con lock bidirezionale inline.
    Il lock è attivo se un ALTRO agent (o l'utente) ha modificato
    l'attuatore negli ultimi LOCK_COOLDOWN_MINUTES minuti simulati.
    
    Args:
        requesting_agent (str|None): ID dell'agent che richiede il payload
            (es. 'mario', 'luigi'). Se None, non calcola lock.
    
    Returns:
        dict: Payload {stanza: {sensori: {...}, attuatori: {nome: {stato, bloccato, ...}}}}
    """
    now = get_simulated_datetime()
    payload = {}
    
    for stanza, dati in stato_casa.items():
        attuatori_out = {}
        
        for nome, att in dati["attuatori"].items():
            if isinstance(att, dict):
                entry = {"stato": att["stato"], "bloccato": False}
                
                # Calcola lock bidirezionale se l'agent è specificato
                if requesting_agent and att["last_modified_at"] is not None:
                    delta = now - att["last_modified_at"]
                    minuti = max(0, int(delta.total_seconds() / 60))
                    
                    # Lock attivo se: un ALTRO agent o l'utente ha modificato
                    # e il cooldown non è scaduto
                    is_other_source = (
                        att["modified_by"] is not None
                        and att["modified_by"] != requesting_agent
                    )
                    if is_other_source and minuti < LOCK_COOLDOWN_MINUTES:
                        entry["bloccato"] = True
                        entry["modificato_da"] = att["modified_by"]
                        entry["minuti_fa"] = minuti
                
                attuatori_out[nome] = entry
            else:
                # fallback legacy
                attuatori_out[nome] = {"stato": att, "bloccato": False}
        
        # Copia sensori con temperatura arrotondata per output leggibile
        sensori_out = dict(dati["sensori"])
        sensori_out["temperatura"] = round(sensori_out["temperatura"], 1)
        
        payload[stanza] = {
            "sensori": sensori_out,
            "attuatori": attuatori_out
        }
    
    return payload


def reset_agent_logs_on_startup():
    """Elimina i log agenti della sessione precedente all'avvio dell'app."""
    os.makedirs(LOG_DIR, exist_ok=True)
    removed_count = 0

    for entry in os.listdir(LOG_DIR):
        if entry.startswith("agent-day-") and entry.endswith(".jsonl"):
            file_path = os.path.join(LOG_DIR, entry)
            if os.path.isfile(file_path):
                os.remove(file_path)
                removed_count += 1

    return removed_count


def aggiorna_tempo_simulato():
    """Aggiorna il tempo simulato in base alla velocità configurata e fa avanzare i giorni"""
    global minuti_simulati, ultimo_update_tempo_reale, velocita_tempo
    global giorno_settimana_idx, giorno_numero, ora_simulata, giorni_settimana
    
    now = datetime.now()
    
    # Se in pausa, aggiorna solo il riferimento temporale senza avanzare
    if simulation_paused:
        ultimo_update_tempo_reale = now
        return
    
    delta_sec = (now - ultimo_update_tempo_reale).total_seconds()
    if delta_sec <= 0:
        return

    delta_min_simulati = delta_sec * (velocita_tempo / 60.0)
    minuti_simulati = minuti_simulati + delta_min_simulati
    
    # Controlla se è passata la mezzanotte (cambio giorno)
    while minuti_simulati >= 24 * 60:
        minuti_simulati -= 24 * 60
        giorno_settimana_idx = (giorno_settimana_idx + 1) % 7
        giorno_numero += 1
        print(f"📅 [{datetime.now().strftime('%H:%M:%S')}] Nuovo giorno: {giorni_settimana[giorno_settimana_idx]} (Giorno #{giorno_numero})")
    
    ultimo_update_tempo_reale = now
    ora_simulata = int(minuti_simulati // 60)


def get_tempo_simulato():
    """Ritorna ora e minuto simulati"""
    global minuti_simulati
    ora = int(minuti_simulati // 60)
    minuto = int(minuti_simulati % 60)
    return ora, minuto


def get_giorno_settimana():
    """Ritorna il nome del giorno della settimana corrente"""
    global giorni_settimana, giorno_settimana_idx
    return giorni_settimana[giorno_settimana_idx]


def get_stagione():
    """Ritorna il nome della stagione corrente"""
    global stagioni, stagione_idx
    return stagioni[stagione_idx]


def _get_sim_start_date():
    try:
        return datetime.strptime(SIM_START_DATE, "%Y-%m-%d").date()
    except Exception:
        return datetime.now().date()


def get_simulated_datetime():
    """Ritorna il datetime simulato basato su giorno e ora simulati"""
    global giorno_numero
    base_date = _get_sim_start_date()
    ora, minuto = get_tempo_simulato()
    sim_date = base_date + timedelta(days=max(0, int(giorno_numero) - 1))
    return datetime(sim_date.year, sim_date.month, sim_date.day, ora, minuto, 0)


def log_agent_action(agent_id, action, payload):
    sim_dt = get_simulated_datetime()
    giorno_nome = giorni_settimana[giorno_settimana_idx]
    
    record = {
        "ts_sim": sim_dt.time().isoformat(),
        "agent_id": agent_id,
        "action": action,
        "giorno_numero": giorno_numero,
        "giorno_nome": giorno_nome,
        "payload": payload
    }
    os.makedirs(LOG_DIR, exist_ok=True)
    file_name = f"agent-day-{giorno_numero:02d}-{giorno_nome.lower()}.jsonl"
    file_path = os.path.join(LOG_DIR, file_name)
    with open(file_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def calcola_delta_minuti_simulati():
    """Calcola il delta di minuti simulati dall'ultimo aggiornamento"""
    global minuti_simulati, ultimo_update_minuti_simulati
    delta = minuti_simulati - ultimo_update_minuti_simulati
    if delta < 0:
        delta += 24 * 60
    ultimo_update_minuti_simulati = minuti_simulati
    return delta


def get_meteo_fattori():
    """Ritorna fattori meteo per luminosità e temperatura (con cache)"""
    global condizioni_meteo, _cache_meteo_condizione, _cache_meteo_fattori
    
    # Usa cache se meteo non è cambiato
    if _cache_meteo_condizione == condizioni_meteo and _cache_meteo_fattori:
        return _cache_meteo_fattori
    
    # Usa funzione pura da simulation
    _cache_meteo_fattori = get_meteo_fattori_puro(condizioni_meteo)
    _cache_meteo_condizione = condizioni_meteo
    return _cache_meteo_fattori


def calcola_temperatura_esterna(ora):
    """Temperatura esterna simulata in base all'ora, meteo e stagione (con cache)"""
    global condizioni_meteo, stagione_idx, _cache_temp_esterna
    return calcola_temperatura_esterna_pura(ora, condizioni_meteo, stagione_idx, _cache_temp_esterna)


def calcola_luce_naturale():
    """Calcola la luminosità naturale in base all'ora simulata"""
    global ora_simulata
    return calcola_luce_naturale_pura(ora_simulata)


def simula_letture_sensori():
    """Simula variazioni realistiche dei sensori"""
    global stato_casa, ultimo_update_dati, stagione_idx
    
    aggiorna_tempo_simulato()
    
    # Se in pausa, non aggiornare i sensori
    if simulation_paused:
        return
    
    delta_minuti_simulati = calcola_delta_minuti_simulati()
    ultimo_update_dati = datetime.now().isoformat()

    ora_corrente, _ = get_tempo_simulato()
    temperatura_esterna = calcola_temperatura_esterna(ora_corrente)
    meteo_fattori = get_meteo_fattori()
    
    for stanza in stato_casa:
        # Temperatura: varia in base al tempo simulato e al meteo
        # Nota: la temperatura interna è float a precisione piena per evitare
        # deadlock da arrotondamento (round solo in output, vedi generate_agent_payload/get_stato_casa_flat)
        temp_attuale = stato_casa[stanza]["sensori"]["temperatura"]
        
        if delta_minuti_simulati > 0:
            # Il giardino è sempre all'esterno - converge istantaneamente
            if stanza == "giardino":
                temp_attuale = temperatura_esterna
            else:
                # Determina la temperatura target e velocità di convergenza in base a clima e stagione
                clima_stato = get_actuator_value(stanza, "clima") if "clima" in stato_casa[stanza]["attuatori"] else "OFF"
                finestre_aperte = ("finestre" in stato_casa[stanza]["attuatori"]
                                   and get_actuator_value(stanza, "finestre") == "APERTE")
                
                # Finestre aperte: l'isolamento si riduce, la stanza converge verso temp esterna
                if finestre_aperte:
                    target_passivo = temperatura_esterna
                    rate_passivo = RATE_FINESTRE_APERTE
                else:
                    target_passivo = temperatura_esterna + ISOLAMENTO_CASA
                    rate_passivo = RATE_PASSIVO
                
                if clima_stato == "HEAT":
                    heat_target = TEMP_TARGET_HEAT.get(stagione_idx, 22.0)
                    if target_passivo < heat_target:
                        # HEAT necessario: la stanza sarebbe più fredda del target HVAC
                        target = heat_target
                        rate = RATE_HEAT * (0.4 if finestre_aperte else 1.0)
                    else:
                        # HEAT non necessario: convergenza passiva (ambiente già caldo)
                        target = target_passivo
                        rate = rate_passivo
                elif clima_stato == "COOL":
                    cool_target = TEMP_TARGET_COOL.get(stagione_idx, 20.0)
                    if target_passivo > cool_target:
                        # COOL necessario: la stanza sarebbe più calda del target HVAC
                        target = cool_target
                        rate = RATE_COOL * (0.4 if finestre_aperte else 1.0)
                    else:
                        # COOL non necessario: convergenza passiva (ambiente già fresco)
                        target = target_passivo
                        rate = rate_passivo
                else:
                    target = target_passivo
                    rate = rate_passivo

                # Calcola il passo verso il target
                delta = target - temp_attuale
                if abs(delta) > 0.01:
                    step = delta * min(rate * delta_minuti_simulati, 1.0)
                    temp_attuale = temp_attuale + step

        # Limita tra min e max da config (NO round: precisione piena per evitare deadlock)
        stato_casa[stanza]["sensori"]["temperatura"] = max(TEMP_MIN, min(TEMP_MAX, temp_attuale))
        
        # Luminosità varia in base a: luci artificiali, tapparelle/porta garage, ora del giorno
        luminosita_base = 0
        
        # Luci artificiali sempre a priorità massima
        luci_val = get_actuator_value(stanza, "luci") if "luci" in stato_casa[stanza]["attuatori"] else "OFF"
        if luci_val == "ON":
            luminosita_base = random.randint(700, 900)
        else:
            # Luce naturale in base a tapparelle o porta garage
            luce_naturale = int(calcola_luce_naturale() * meteo_fattori["luminosita"])
            
            if "tapparelle" in stato_casa[stanza]["attuatori"]:
                if get_actuator_value(stanza, "tapparelle") == "APERTE":
                    luminosita_base = luce_naturale
                else:
                    luminosita_base = int(luce_naturale * 0.2)
            elif "porta_garage" in stato_casa[stanza]["attuatori"]:
                if get_actuator_value(stanza, "porta_garage") == "ON":
                    luminosita_base = int(luce_naturale * 0.7)
                else:
                    luminosita_base = int(luce_naturale * 0.15)
            else:
                luminosita_base = luce_naturale
        
        stato_casa[stanza]["sensori"]["luminosita"] = max(50, min(1200, luminosita_base))
        stato_casa[stanza]["sensori"]["umidita"] = random.randint(40, 60)
    
    # Fine simulazione sensori
