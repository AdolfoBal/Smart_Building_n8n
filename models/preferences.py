"""Preferences model - Preferenze utente per stanza."""

from copy import deepcopy


# Campi validi per validazione
VALID_LUCI_INGRESSO = ("auto", "sempre_on", "sempre_off")
VALID_TAPPARELLE = ("APERTE", "CHIUSE")
VALID_BLOCCO_FINESTRE = ("auto", "bloccate")


def _derive_room_capabilities():
    """Deriva dinamicamente le capability stanza da models.state."""
    from models.state import get_initial_state

    stato = get_initial_state()
    stanze_con_clima = tuple(s for s, d in stato.items() if "clima" in d["attuatori"])
    stanze_con_tapparelle = tuple(s for s, d in stato.items() if "tapparelle" in d["attuatori"])
    stanze_con_finestre = tuple(s for s, d in stato.items() if "finestre" in d["attuatori"])
    return stato, stanze_con_clima, stanze_con_tapparelle, stanze_con_finestre


_STATO_INIZIALE, STANZE_CON_CLIMA, STANZE_CON_TAPPARELLE, STANZE_CON_FINESTRE = _derive_room_capabilities()


def _default_temperature_for_room(stanza):
    defaults = {
        "cucina": 22.0,
        "camera": 20.0,
        "soggiorno": 22.0,
        "bagno": 23.0,
    }
    return defaults.get(stanza, 22.0)


def _default_room_preferences(stanza, attuatori):
    """Crea preferenze default in base agli attuatori realmente presenti."""
    prefs = {
        "luci_ingresso": "auto",
        "note": "",
    }

    if "clima" in attuatori:
        prefs["temperatura_ideale"] = _default_temperature_for_room(stanza)
    if "tapparelle" in attuatori:
        prefs["tapparelle_giorno"] = "APERTE"
        prefs["tapparelle_notte"] = "CHIUSE"
    if "finestre" in attuatori:
        prefs["blocco_finestre"] = "auto"

    return prefs


def get_default_preferences():
    """Ritorna le preferenze di default per tutte le stanze."""
    prefs = {"note_generali": ""}
    for stanza, dati in _STATO_INIZIALE.items():
        prefs[stanza] = _default_room_preferences(stanza, dati["attuatori"])
    return prefs


def _normalize_blocco_value(value):
    """Normalizza valori legacy di blocco finestre."""
    raw = str(value).strip().lower()
    if raw in ("sempre_chiuse", "bloccate", "true", "1", "on", "si", "sì"):
        return "bloccate"
    return "auto"


def normalize_preferences(data):
    """Normalizza e migra preferenze da strutture legacy alla struttura corrente."""
    defaults = get_default_preferences()
    normalized = deepcopy(defaults)

    if not isinstance(data, dict):
        return normalized

    note_generali = data.get("note_generali")
    if isinstance(note_generali, str):
        normalized["note_generali"] = note_generali

    for stanza, default_room in defaults.items():
        if stanza == "note_generali":
            continue

        current = data.get(stanza)
        if not isinstance(current, dict):
            continue

        room_out = deepcopy(default_room)

        # Legacy alias field rename: finestre_con_clima -> blocco_finestre
        if stanza in STANZE_CON_FINESTRE:
            if "blocco_finestre" in current:
                room_out["blocco_finestre"] = _normalize_blocco_value(current["blocco_finestre"])
            elif "finestre_con_clima" in current:
                room_out["blocco_finestre"] = _normalize_blocco_value(current["finestre_con_clima"])

        if "luci_ingresso" in current and current["luci_ingresso"] in VALID_LUCI_INGRESSO:
            room_out["luci_ingresso"] = current["luci_ingresso"]

        if "note" in current and isinstance(current["note"], str):
            room_out["note"] = current["note"]

        if stanza in STANZE_CON_CLIMA and "temperatura_ideale" in current:
            val = current["temperatura_ideale"]
            if isinstance(val, (int, float)):
                room_out["temperatura_ideale"] = float(val)

        if stanza in STANZE_CON_TAPPARELLE:
            for key in ("tapparelle_giorno", "tapparelle_notte"):
                if key in current and current[key] in VALID_TAPPARELLE:
                    room_out[key] = current[key]

        normalized[stanza] = room_out

    return normalized
