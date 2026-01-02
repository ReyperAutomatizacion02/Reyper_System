from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import os
import requests
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
    'data': None,
    'timestamp': None
}
CACHE_TTL = 600 # 10 minutos en segundos

@logistics_bp.route('/api/partidas', methods=['GET'])
@login_required
def get_partidas():
    """Obtiene la lista de partidas desde Notion con caché."""
    global PARTIDAS_CACHE
    try:
        force_refresh = request.args.get('force') == 'true'
        now = datetime.now()

        # Verificar si hay datos válidos en caché
        if not force_refresh and PARTIDAS_CACHE['data'] is not None:
            if PARTIDAS_CACHE['timestamp'] and (now - PARTIDAS_CACHE['timestamp']).seconds < CACHE_TTL:
                return jsonify({'success': True, 'partidas': PARTIDAS_CACHE['data'], 'cached': True})

        load_dotenv()
        token = os.getenv('NOTION_TOKEN_LOGISTICA')
        database_id = os.getenv('NOTION_DATABASE_ID_LOGISTICA')
        
        if not token or not database_id:
            return jsonify({'success': False, 'message': 'Credenciales de Notion no configuradas'}), 500

        today = datetime.now()
        one_year_ago = (today - timedelta(days=365)).strftime('%Y-%m-%d')
        one_year_ahead = (today + timedelta(days=365)).strftime('%Y-%m-%d')

        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        payload = {
            "filter": {
                "and": [
                    {"property": "FECHA DE CREACION", "date": {"on_or_after": one_year_ago}},
                    {"property": "FECHA DE CREACION", "date": {"on_or_before": one_year_ahead}},
                    {"property": "06-ESTATUS GENERAL", "select": {"does_not_equal": "D7-ENTREGADA"}},
                    {"property": "06-ESTATUS GENERAL", "select": {"does_not_equal": "D1-TERMINADA"}},
                    {"property": "06-ESTATUS GENERAL", "select": {"does_not_equal": "D8-CANCELADA"}},
                    {"property": "CAPTURA DE MATERIAL", "relation": {"is_empty": True}}
                ]
            }
        }

        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        partidas = []
        has_more = True
        next_cursor = None

        while has_more:
            if next_cursor:
                payload["start_cursor"] = next_cursor
                
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if response.ok:
                data = response.json()
                results = data.get('results', [])
                for page in results:
                    props = page.get('properties', {})
                    title_prop = props.get('01-CODIGO PIEZA', {}).get('title', [])
                    if title_prop:
                        text_content = title_prop[0].get('plain_text', '')
                        if text_content:
                            partidas.append(text_content)
                
                has_more = data.get('has_more', False)
                next_cursor = data.get('next_cursor')
            else:
                return jsonify({'success': False, 'message': f'Error de Notion: {response.status_code}'}), 500
            
        partidas.sort()
        
        # Actualizar caché
        PARTIDAS_CACHE['data'] = partidas
        PARTIDAS_CACHE['timestamp'] = now
        
        return jsonify({'success': True, 'partidas': partidas, 'cached': False})
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

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
