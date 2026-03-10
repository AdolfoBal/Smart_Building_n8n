"""
State model - Definizione dello stato iniziale della casa smart

Ogni attuatore è un dizionario con metadati per il sistema di Lock Temporaneo:
  - stato: valore corrente (es. "ON", "OFF", "HEAT", "COOL", "APERTE", "CHIUSE")
  - last_modified_at: datetime dell'ultima modifica (None = mai modificato)
  - modified_by: sorgente dell'ultima modifica ("mario", "luigi", "user", None)

SCALABILITÀ:
  - Per aggiungere un TIPO di attuatore/sensore: modificare ACTUATOR_TYPES/SENSOR_TYPES in config.py
  - Per aggiungere una STANZA o cambiare i dispositivi di una stanza: modificare get_initial_state() qui
"""
from config import ACTUATOR_TYPES, SENSOR_TYPES


def _attuatore(tipo):
    """Crea un attuatore con metadati di default, leggendo stato_default dal registro.
    
    Args:
        tipo (str): Chiave in ACTUATOR_TYPES (es. 'luci', 'clima')
    """
    if tipo not in ACTUATOR_TYPES:
        raise KeyError(f"Tipo attuatore '{tipo}' non registrato in ACTUATOR_TYPES (config.py)")
    return {
        "stato": ACTUATOR_TYPES[tipo]["stato_default"],
        "last_modified_at": None,
        "modified_by": None
    }


def _sensori_default():
    """Crea il blocco sensori standard leggendo i default da SENSOR_TYPES."""
    return {nome: info["default"] for nome, info in SENSOR_TYPES.items()}


def get_initial_state():
    """Ritorna lo stato iniziale della casa con tutti i sensori e attuatori (con metadati).
    
    Sensori: generati da SENSOR_TYPES (config.py) — uguali per ogni stanza.
    Attuatori: ogni stanza dichiara i tipi che possiede; lo stato_default viene
               letto automaticamente da ACTUATOR_TYPES (config.py).
    """
    return {
        "cucina": {
            "sensori": _sensori_default(),
            "attuatori": {
                "luci": _attuatore("luci"),
                "clima": _attuatore("clima"),
                "tapparelle": _attuatore("tapparelle"),
                "finestre": _attuatore("finestre")
            }
        },
        "camera": {
            "sensori": _sensori_default(),
            "attuatori": {
                "luci": _attuatore("luci"),
                "clima": _attuatore("clima"),
                "tapparelle": _attuatore("tapparelle"),
                "finestre": _attuatore("finestre")
            }
        },
        "soggiorno": {
            "sensori": _sensori_default(),
            "attuatori": {
                "luci": _attuatore("luci"),
                "clima": _attuatore("clima"),
                "tv": _attuatore("tv"),
                "tapparelle": _attuatore("tapparelle"),
                "finestre": _attuatore("finestre")
            }
        },
        "bagno": {
            "sensori": _sensori_default(),
            "attuatori": {
                "luci": _attuatore("luci"),
                "clima": _attuatore("clima"),
                "ventilazione": _attuatore("ventilazione"),
                "tapparelle": _attuatore("tapparelle"),
                "finestre": _attuatore("finestre")
            }
        },
        "garage": {
            "sensori": _sensori_default(),
            "attuatori": {
                "luci": _attuatore("luci"),
                "porta_garage": _attuatore("porta_garage")
            }
        },
        "giardino": {
            "sensori": _sensori_default(),
            "attuatori": {
                "luci": _attuatore("luci"),
                "irrigazione": _attuatore("irrigazione")
            }
        }
    }
