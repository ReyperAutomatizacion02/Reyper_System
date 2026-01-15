from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import os
import requests
import threading
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta

logistics_bp = Blueprint('logistics', __name__, url_prefix='/dashboard/logistica')

# Herramientas del Módulo de Logística
LOGISTICS_TOOLS = [
    {'name': 'captura', 'label': 'Captura de Materiales', 'icon': 'ph-clipboard-text', 'route': 'logistics.capture_materials'}
]

@logistics_bp.route('/')
@login_required
def home():
    current_roles = session.get('roles', [])
    if 'Logistica' not in current_roles and 'Admin' not in current_roles:
        flash('No tienes acceso al módulo de Logística.', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('logistics_home.html', 
                         user=current_user, 
                         roles=current_roles, 
                         tools=LOGISTICS_TOOLS)

@logistics_bp.route('/captura')
@login_required
def capture_materials():
    current_roles = session.get('roles', [])
    if 'Logistica' not in current_roles and 'Admin' not in current_roles:
        return redirect(url_for('main.dashboard'))
        
    return render_template('logistics_capture.html', 
                         user=current_user, 
                         roles=current_roles, 
                         tools=LOGISTICS_TOOLS)

# Caché en memoria para evitar consultas excesivas a Notion
PARTIDAS_CACHE = {
    'data': [],
    'timestamp': None,
    'is_syncing': False
}

MATERIALES_CACHE = {
    'data': [],
    'timestamp': None,
    'is_syncing': False
}

from concurrent.futures import ThreadPoolExecutor

def fetch_logistics_data_parallel(token, database_id, material_db_id):
    """Función auxiliar para realizar las peticiones a Notion en paralelo."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    def fetch_partidas():
        url = f"https://api.notion.com/v1/databases/{database_id}/query?filter_properties=title"
        today = datetime.now()
        one_year_ago = (today - timedelta(days=365)).strftime('%Y-%m-%d')
        one_year_ahead = (today + timedelta(days=365)).strftime('%Y-%m-%d')
        payload = {
            "filter": {
                "and": [
                    {"property": "CAPTURA DE MATERIAL", "relation": {"is_empty": True}},
                    {"property": "06-ESTATUS GENERAL", "select": {"does_not_equal": "D7-ENTREGADA"}},
                    {"property": "06-ESTATUS GENERAL", "select": {"does_not_equal": "D1-TERMINADA"}},
                    {"property": "06-ESTATUS GENERAL", "select": {"does_not_equal": "D8-CANCELADA"}},
                    {"property": "FECHA DE CREACION", "date": {"on_or_after": one_year_ago}},
                    {"property": "FECHA DE CREACION", "date": {"on_or_before": one_year_ahead}}
                ]
            }
        }
        
        results_list = []
        has_more = True
        next_cursor = None
        MAX_PAGES = 100
        pages_fetched = 0

        while has_more and pages_fetched < MAX_PAGES:
            if next_cursor: payload["start_cursor"] = next_cursor
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.ok:
                data = response.json()
                for page in data.get('results', []):
                    title_prop = page.get('properties', {}).get('01-CODIGO PIEZA', {}).get('title', [])
                    if title_prop:
                        text = title_prop[0].get('plain_text', '')
                        if text: results_list.append(text)
                has_more = data.get('has_more', False)
                next_cursor = data.get('next_cursor')
                pages_fetched += 1
            else: break
        return sorted(results_list)

    def fetch_materiales():
        if not material_db_id: return []
        url = f"https://api.notion.com/v1/databases/{material_db_id}/query?filter_properties=title"
        payload = {"filter": {"property": "MATERIAL", "title": {"is_not_empty": True}}}
        
        results_list = []
        has_more = True
        next_cursor = None
        MAX_PAGES = 100
        pages_fetched = 0

        while has_more and pages_fetched < MAX_PAGES:
            if next_cursor: payload["start_cursor"] = next_cursor
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.ok:
                data = response.json()
                for page in data.get('results', []):
                    title_prop = page.get('properties', {}).get('MATERIAL', {}).get('title', [])
                    if title_prop:
                        text = title_prop[0].get('plain_text', '')
                        if text: results_list.append(text)
                has_more = data.get('has_more', False)
                next_cursor = data.get('next_cursor')
                pages_fetched += 1
            else: break
        return sorted(results_list)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_partidas = executor.submit(fetch_partidas)
        f_materiales = executor.submit(fetch_materiales)
        return f_partidas.result(), f_materiales.result()

def refresh_notion_cache():
    """Función para sincronizar datos de Notion (Partidas y Materiales) en paralelo."""
    global PARTIDAS_CACHE, MATERIALES_CACHE
    if PARTIDAS_CACHE['is_syncing'] or MATERIALES_CACHE['is_syncing']:
        return
    
    PARTIDAS_CACHE['is_syncing'] = True
    MATERIALES_CACHE['is_syncing'] = True
    try:
        load_dotenv()
        token = os.getenv('NOTION_TOKEN_LOGISTICA')
        database_id = os.getenv('NOTION_DATABASE_ID_LOGISTICA')
        material_db_id = os.getenv('NOTION_DATABASE_ID_MATERIAL')
        
        if not token or not database_id:
            return

        partidas, materiales = fetch_logistics_data_parallel(token, database_id, material_db_id)
        
        now = datetime.now()
        PARTIDAS_CACHE['data'] = partidas
        PARTIDAS_CACHE['timestamp'] = now
        MATERIALES_CACHE['data'] = materiales
        MATERIALES_CACHE['timestamp'] = now
        
    except Exception as e:
        print(f"ERROR en sincronización de Notion: {str(e)}")
    finally:
        PARTIDAS_CACHE['is_syncing'] = False
        MATERIALES_CACHE['is_syncing'] = False

def start_background_sync():
    """Inicia el hilo de sincronización cada 3 horas."""
    def run_sync():
        while True:
            refresh_notion_cache()
            time.sleep(10800) # 3 horas
    
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()

@logistics_bp.route('/api/partidas', methods=['GET'])
@login_required
def get_partidas():
    """Sirve la lista de partidas desde la caché sincronizada."""
    global PARTIDAS_CACHE
    try:
        force_refresh = request.args.get('force') == 'true'
        
        if force_refresh:
            # Iniciar sincronización en segundo plano pero avisar al usuario
            threading.Thread(target=refresh_notion_cache, daemon=True).start()
            return jsonify({
                'success': True, 
                'partidas': PARTIDAS_CACHE['data'], 
                'message': 'Sincronización iniciada en segundo plano...'
            })

        return jsonify({
            'success': True, 
            'partidas': PARTIDAS_CACHE['data'], 
            'timestamp': PARTIDAS_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if PARTIDAS_CACHE['timestamp'] else None,
            'is_syncing': PARTIDAS_CACHE['is_syncing']
        })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@logistics_bp.route('/api/materiales', methods=['GET'])
@login_required
def get_materiales():
    """Sirve la lista de materiales desde la caché sincronizada."""
    global MATERIALES_CACHE
    try:
        return jsonify({
            'success': True, 
            'materiales': MATERIALES_CACHE['data'], 
            'timestamp': MATERIALES_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if MATERIALES_CACHE['timestamp'] else None,
            'is_syncing': MATERIALES_CACHE['is_syncing']
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@logistics_bp.route('/api/data')
@login_required
def get_all_data():
    """Endpoint unificado para obtener todos los datos de logística."""
    global PARTIDAS_CACHE, MATERIALES_CACHE
    return jsonify({
        'success': True,
        'partidas': {
            'data': PARTIDAS_CACHE['data'],
            'timestamp': PARTIDAS_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if PARTIDAS_CACHE['timestamp'] else None
        },
        'materiales': {
            'data': MATERIALES_CACHE['data'],
            'timestamp': MATERIALES_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if MATERIALES_CACHE['timestamp'] else None
        },
        'is_syncing': PARTIDAS_CACHE['is_syncing'] or MATERIALES_CACHE['is_syncing']
    })

@logistics_bp.route('/api/submit', methods=['POST']) 
@login_required
def submit_capture():
    """Recibe datos del formulario de materiales y los reenvía al Webhook de n8n."""
    try:
        load_dotenv() # Forzar recarga de .env
        data = request.json
        # Nueva variable de entorno específica para logística
        webhook_url = os.getenv('LOGISTICA_WEBHOOK_URL')
        if not webhook_url:
            return jsonify({'success': False, 'message': 'URL de Webhook (LOGISTICA_WEBHOOK_URL) no configurada en .env'}), 500

        # Inyectar metadata de seguridad / contexto
        data['metadata'] = {
            'generated_by': current_user.email,
            'username': getattr(current_user, 'username', 'N/A'),
            'roles': getattr(current_user, 'roles', []),
            'source': 'AutoIntelli Web App - Logística'
        }

        # Enviar a n8n
        response = requests.post(webhook_url, json=data, timeout=15)
        print(f"DEBUG: Webhook response status: {response.status_code}")
        
        if response.ok: # Acepta cualquier 2xx
            return jsonify({'success': True, 'message': 'Materiales registrados exitosamente'})
        else:
            print(f"DEBUG: Webhook error body: {response.text}")
            return jsonify({'success': False, 'message': f'Error en el servidor de destino (Status: {response.status_code}): {response.text[:100]}'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500
