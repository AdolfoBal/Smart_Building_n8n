"""
API package - Contiene le funzioni per comunicazione con servizi esterni e route API
"""
from .webhooks import send_presence_webhook, controlla_casa_automaticamente

__all__ = ['send_presence_webhook', 'controlla_casa_automaticamente']
