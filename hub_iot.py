"""
Hub IoT - Orchestratore Flask principale
Entry point dell'applicazione smart home
"""
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, FLASK_RELOADER
import core
from api import controlla_casa_automaticamente as webhook_controlla_casa
from api.routes import api_bp

# Inizializza Flask app
app = Flask(__name__)

# Registra il Blueprint con tutte le route
app.register_blueprint(api_bp)


# --- BACKGROUND THREAD PER AI AGENT AUTONOMO ---
def controlla_casa_automaticamente():
    """Wrapper per il webhook n8n che aggiorna lo stato globale.
    Se la simulazione è in pausa, salta l'esecuzione.
    Logga il trigger con snapshot dello stato casa nei log agenti."""
    if core.simulation_paused:
        return
    
    # Cattura snapshot dello stato casa al momento del trigger
    core.simula_letture_sensori()
    core.aggiorna_tempo_simulato()
    ora_corrente, minuto_corrente = core.get_tempo_simulato()
    temp_esterna = core.calcola_temperatura_esterna(ora_corrente)
    
    status_snapshot = {
        "ora": f"{ora_corrente:02d}:{minuto_corrente:02d}",
        "giorno": core.get_giorno_settimana(),
        "giorno_numero": core.giorno_numero,
        "stagione": core.get_stagione(),
        "meteo": core.condizioni_meteo,
        "temperatura_esterna": round(temp_esterna, 1),
        "stanze": core.generate_agent_payload("__system__")
    }
    
    # Logga il trigger con lo snapshot inviato
    core.log_agent_action("scheduler", "n8n_trigger", {
        "session_id": core.session_id,
        "status_snapshot": status_snapshot
    })
    
    def update_timestamp(timestamp):
        core.ultimo_update_n8n = timestamp
    
    # Chiama la funzione webhook con callback per aggiornare stato
    webhook_controlla_casa(update_timestamp, core.session_id)


def start_scheduler():
    """Avvia lo scheduler per il controllo automatico della casa"""
    core.scheduler = BackgroundScheduler()
    core.scheduler.add_job(
        controlla_casa_automaticamente,
        IntervalTrigger(seconds=core.n8n_interval_seconds),
        id='ai_agent_loop',
        name='AI Agent autonomo',
        misfire_grace_time=10
    )
    core.scheduler.start()
    print(f" AI Agent autonomo avviato (ogni {core.n8n_interval_seconds} secondi)")
    return core.scheduler


if __name__ == '__main__':
    removed_logs = core.reset_agent_logs_on_startup()
    print(f"🧹 Log agent resettati all'avvio: {removed_logs} file rimossi")
    print(f"🆔 Session ID corrente: {core.session_id}")

    print(" Avvio simulatore IoT...")
    print(" Dashboard: http://localhost:5000")
    print("🤖 API AI Agent: http://localhost:5000/api/status")
    print("🖥️  API Dashboard: http://localhost:5000/api/dashboard/status")
    print(" Docker: http://host.docker.internal:5000")
    print(" N8n Webhook: http://localhost:5678/webhook/smart-home-command")
    
    # Avvia scheduler AI Agent
    scheduler = start_scheduler()
    
    try:
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, use_reloader=FLASK_RELOADER)
    finally:
        scheduler.shutdown()
