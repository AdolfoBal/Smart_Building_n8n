"""
Models package - Contiene le strutture dati dell'applicazione
"""
from .state import get_initial_state
from .preferences import get_default_preferences

__all__ = ['get_initial_state', 'get_default_preferences']
