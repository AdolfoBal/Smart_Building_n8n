"""
Simulation utilities - Funzioni pure per calcoli di simulazione
"""
import random
from config import FATTORI_METEO, MODIFICATORI_STAGIONE, CACHE_TEMP_MAX_ENTRIES


def get_meteo_fattori_puro(condizioni_meteo):
    """
    Ritorna fattori meteo per luminosità e temperatura (versione pura).
    
    Args:
        condizioni_meteo (str): Condizione meteo corrente
        
    Returns:
        dict: Dizionario con 'luminosita' (float) e 'temp_offset' (float)
    """
    return FATTORI_METEO.get(condizioni_meteo, {"luminosita": 1.0, "temp_offset": 0.0})


def calcola_temperatura_esterna_pura(ora, condizioni_meteo, stagione_idx, cache=None):
    """
    Temperatura esterna simulata in base all'ora, meteo e stagione (versione pura con cache opzionale).
    
    Args:
        ora (int): Ora del giorno (0-23)
        condizioni_meteo (str): Condizione meteo corrente
        stagione_idx (int): Indice della stagione (0-3)
        cache (dict, optional): Dizionario cache per ottimizzazione
        
    Returns:
        float: Temperatura esterna calcolata
    """
    # Controlla cache se fornita
    if cache is not None:
        cache_key = f"{ora}_{condizioni_meteo}_{stagione_idx}"
        if cache_key in cache:
            return cache[cache_key]
    
    # Temperature base per ora del giorno
    if 6 <= ora < 8:
        base = 14
    elif 8 <= ora < 12:
        base = 18
    elif 12 <= ora < 16:
        base = 23
    elif 16 <= ora < 20:
        base = 19
    else:
        base = 12
    
    # Modificatori stagionali da config
    stagione_offset = MODIFICATORI_STAGIONE.get(stagione_idx, 0)
    meteo_offset = get_meteo_fattori_puro(condizioni_meteo)["temp_offset"]
    
    result = base + stagione_offset + meteo_offset
    
    # Aggiorna cache se fornita
    if cache is not None:
        cache[cache_key] = result
        
        # Limita dimensione cache
        if len(cache) > CACHE_TEMP_MAX_ENTRIES:
            cache.clear()
    
    return result


def calcola_luce_naturale_pura(ora_simulata):
    """
    Calcola la luminosità naturale in base all'ora simulata (versione pura).
    
    Args:
        ora_simulata (int): Ora simulata (0-23)
        
    Returns:
        int: Luminosità naturale (50-1200)
    """
    # Curva di luminosità durante il giorno
    if 6 <= ora_simulata < 8:  # Alba
        return random.randint(300, 500)
    elif 8 <= ora_simulata < 18:  # Giorno
        return random.randint(800, 1200)
    elif 18 <= ora_simulata < 20:  # Tramonto
        return random.randint(400, 600)
    else:  # Notte
        return random.randint(50, 150)
