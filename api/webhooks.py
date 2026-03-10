"""
Webhooks - Gestione chiamate ai webhook N8n
"""
import requests
import threading
from datetime import datetime
from config import (
    N8N_WEBHOOK_PRESENCE, N8N_WEBHOOK_SMART_HOME,
    N8N_WEBHOOK_TIMEOUT_PRESENCE, N8N_WEBHOOK_TIMEOUT_SMART_HOME
)


def send_presence_webhook(stanza, presenza):
    """
    Invia la notifica di presenza/assenza a n8n in background.
    
    Args:
        stanza (str): Nome della stanza
        presenza (bool): True se presenza rilevata, False altrimenti
    """
    def _send():
        try:
            payload = {
                "stanza": stanza,
                "presenza": presenza
            }
            response = requests.post(N8N_WEBHOOK_PRESENCE, json=payload, timeout=N8N_WEBHOOK_TIMEOUT_PRESENCE)
            if response.status_code == 200:
                print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Webhook presence inviato a n8n: {stanza} = {presenza}")
            else:
                print(f"⚠️ Webhook presenza n8n risponde {response.status_code}: {response.text}")
        except requests.exceptions.ConnectionError:
            print("❌ Webhook n8n non raggiungibile (presence)")
        except Exception as e:
            print(f"❌ Errore invio webhook presenza: {str(e)}")
    
    # Esegui in background per non bloccare la risposta
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


def controlla_casa_automaticamente(stato_callback, session_id):
    """
    Chiama il webhook n8n per controllare automaticamente la casa.
    
    Args:
        stato_callback (callable): Funzione callback che riceve l'ultimo timestamp di update.
                                   Signature: callback(timestamp_iso_string) -> None
        session_id (str): Identificativo di sessione da inoltrare a n8n
    """
    try:
        payload = {
            "message": "Controlla la casa e applica le preferenze automaticamente",
            "sessionId": session_id
        }
        
        response = requests.post(N8N_WEBHOOK_SMART_HOME, json=payload, timeout=N8N_WEBHOOK_TIMEOUT_SMART_HOME)
        
        if response.status_code == 200:
            timestamp = datetime.now().isoformat()
            stato_callback(timestamp)
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] AI Agent eseguito automaticamente (da N8n)")
        else:
            print(f"⚠️ [{datetime.now().strftime('%H:%M:%S')}] AI Agent: risposta N8n {response.status_code}")
    except requests.exceptions.Timeout:
        timestamp = datetime.now().isoformat()
        stato_callback(timestamp)
        print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] AI Agent trigger inviato a n8n (risposta asincrona)")
    except requests.exceptions.ConnectionError:
        print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] N8n non raggiungibile - skipping automatismo")
    except Exception as e:
        print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] Errore AI Agent: {str(e)}")
