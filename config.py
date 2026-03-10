"""
Configurazione e costanti del simulatore IoT Smart Home
"""

# === TEMPO SIMULATO ===
ORA_SIMULATA_DEFAULT = 12
MINUTI_SIMULATI_DEFAULT = 12 * 60
VELOCITA_TEMPO_DEFAULT = 90
SIM_START_DATE = "2026-02-05"

# === LOGGING ===
LOG_DIR = "logs"

# === GIORNI SETTIMANA ===
GIORNI_SETTIMANA = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
GIORNO_SETTIMANA_DEFAULT = 0  # Lunedì
GIORNO_NUMERO_DEFAULT = 1

# === STAGIONI ===
STAGIONI = ["Inverno", "Primavera", "Estate", "Autunno"]
STAGIONE_DEFAULT = 1  # Primavera

MODIFICATORI_STAGIONE = {
    0: -18,  # Inverno
    1:   0,  # Primavera
    2: +12,  # Estate
    3:  -6   # Autunno
}

TEMP_TARGET_HEAT = {
    0: 23.0,  # Inverno
    1: 22.0,  # Primavera
    2: 21.0,  # Estate
    3: 22.0   # Autunno
}

TEMP_TARGET_COOL = {
    0: 22.0,  # Inverno
    1: 20.0,  # Primavera
    2: 19.0,  # Estate
    3: 20.0   # Autunno
}

# === METEO ===
CONDIZIONI_METEO_DEFAULT = "Sereno"
FATTORI_METEO = {
    "Sereno": {"luminosita": 1.0, "temp_offset": 0.0},
    "Nuvoloso": {"luminosita": 0.6, "temp_offset": -1.0},
    "Pioggia": {"luminosita": 0.45, "temp_offset": -2.0},
    "Temporale": {"luminosita": 0.3, "temp_offset": -3.0},
    "Neve": {"luminosita": 0.7, "temp_offset": -5.0},
    "Nebbia": {"luminosita": 0.5, "temp_offset": -1.5}
}

# === LIMITI TEMPERATURA ===
TEMP_MIN = -10.0
TEMP_MAX = 45.0
ISOLAMENTO_CASA = 2.0

# === RATE CONVERGENZA ===
RATE_HEAT = 0.008            # ~2-3°C/ora simulata con HVAC
RATE_COOL = 0.008
RATE_PASSIVO = 0.002         # ~1-2°C/ora simulata passiva (casa isolata)
RATE_FINESTRE_APERTE = 0.008 # ~4°C/ora simulata con finestre aperte

# === CACHE ===
CACHE_TEMP_MAX_ENTRIES = 100

# === N8N ===
N8N_INTERVAL_SECONDS_DEFAULT = 90
N8N_WEBHOOK_PRESENCE = "http://localhost:5678/webhook/presence"
N8N_WEBHOOK_SMART_HOME = "http://localhost:5678/webhook/smart-home-command"
N8N_WEBHOOK_TIMEOUT_PRESENCE = 20
N8N_WEBHOOK_TIMEOUT_SMART_HOME = 3
N8N_AGENT_TIMEOUT = 3

# === REGISTRO TIPI ATTUATORI ===
# Per aggiungere un nuovo tipo di attuatore: aggiungere una entry qui.
# Il resto del sistema (validazione, alias, stato iniziale) lo legge automaticamente.
#   stati_validi: lista degli stati accettati dall'API
#   stato_default: stato iniziale quando la casa viene creata
#   alias: dizionario alias -> stato_canonico (normalizzazione input agenti AI)
ACTUATOR_TYPES = {
    "luci": {
        "stati_validi": ["ON", "OFF"],
        "stato_default": "OFF",
        "alias": {}
    },
    "clima": {
        "stati_validi": ["OFF", "HEAT", "COOL"],
        "stato_default": "OFF",
        "alias": {}
    },
    "tapparelle": {
        "stati_validi": ["APERTE", "CHIUSE"],
        "stato_default": "CHIUSE",
        "alias": {}
    },
    "tv": {
        "stati_validi": ["ON", "OFF"],
        "stato_default": "OFF",
        "alias": {}
    },
    "ventilazione": {
        "stati_validi": ["ON", "OFF"],
        "stato_default": "OFF",
        "alias": {}
    },
    "irrigazione": {
        "stati_validi": ["ON", "OFF"],
        "stato_default": "OFF",
        "alias": {}
    },
    "finestre": {
        "stati_validi": ["APERTE", "CHIUSE"],
        "stato_default": "CHIUSE",
        "alias": {}
    },
    "porta_garage": {
        "stati_validi": ["ON", "OFF"],
        "stato_default": "OFF",
        "alias": {
            "OPEN": "ON", "OPENED": "ON", "APERTA": "ON", "APERTO": "ON",
            "CHIUSA": "OFF", "CHIUSO": "OFF", "CLOSE": "OFF", "CLOSED": "OFF"
        }
    }
}

# === REGISTRO TIPI SENSORI ===
# Per aggiungere un nuovo tipo di sensore: aggiungere una entry qui.
# state.py legge i default da qui automaticamente.
#   default: valore iniziale
#   unita: unità di misura (documentazione)
SENSOR_TYPES = {
    "temperatura": {"default": 20.0, "unita": "°C"},
    "luminosita":  {"default": 500,  "unita": "lux"},
    "umidita":     {"default": 50,   "unita": "%"},
    "presenza":    {"default": False, "unita": "bool"}
}

# === LOCK TEMPORANEO (Anti Race-Condition) ===
LOCK_COOLDOWN_MINUTES = 30  # Minuti di protezione dopo modifica di luigi/user

# === PREFERENZE UTENTE ===
PREFERENCES_FILE = "preferences.json"  # File di persistenza preferenze

# === FLASK ===
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000
FLASK_DEBUG = False
FLASK_RELOADER = False
