import os
import requests
import threading
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from constants import get_allowed_modules

sales_bp = Blueprint('sales', __name__, url_prefix='/dashboard/ventas')

# Caché en memoria para Ventas
CLIENTES_CACHE = {'data': [], 'timestamp': None, 'is_syncing': False}
USUARIOS_CACHE = {'data': [], 'timestamp': None, 'is_syncing': False}
PUESTOS_CACHE = {'data': [], 'timestamp': None, 'is_syncing': False}
AREAS_CACHE = {'data': [], 'timestamp': None, 'is_syncing': False}

def fetch_notion_db(token, db_id, property_name):
    """Auxiliar para consultar cualquier DB de Notion por una propiedad de título."""
    if not token or not db_id:
        return []

    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    results_list = []
    has_more = True
    next_cursor = None

    while has_more:
        payload = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.ok:
                data = response.json()
                results = data.get('results', [])
                for page in results:
                    props = page.get('properties', {})
                    # Intentar obtener por nombre exacto
                    title_prop = props.get(property_name)
                    
                    # Si no se encuentra por nombre, buscar la primera propiedad de tipo 'title'
                    if not title_prop:
                        for p_name, p_val in props.items():
                            if p_val.get('type') == 'title':
                                title_prop = p_val
                                break
                    
                    if not title_prop:
                        continue

                    content = ""
                    if title_prop.get('type') == 'title':
                        bits = title_prop.get('title', [])
                        if bits: content = bits[0].get('plain_text', '')
                    elif title_prop.get('type') == 'rich_text':
                        bits = title_prop.get('rich_text', [])
                        if bits: content = bits[0].get('plain_text', '')
                    elif title_prop.get('type') == 'select':
                        sel = title_prop.get('select')
                        if sel: content = sel.get('name', '')
                    elif title_prop.get('type') == 'formula':
                        formula = title_prop.get('formula', {})
                        f_type = formula.get('type')
                        if f_type == 'string':
                            content = formula.get('string', '')
                        elif f_type == 'number':
                            content = str(formula.get('number', ''))
                    
                    if content:
                        results_list.append(content)
                
                has_more = data.get('has_more', False)
                next_cursor = data.get('next_cursor')
            else:
                break
        except Exception as e:
            print(f"Error fetching Notion DB {db_id}: {e}")
            break
            
    return sorted(list(set(results_list)))

def refresh_sales_cache(force=False):
    """Sincroniza Clientes y Usuarios."""
    global CLIENTES_CACHE, USUARIOS_CACHE
    
    # Si ya está sincronizando, no hacer nada a menos que sea forzado (aunque is_syncing debería bloquear igual)
    if not force and (CLIENTES_CACHE['is_syncing'] or USUARIOS_CACHE['is_syncing']):
        return

    CLIENTES_CACHE['is_syncing'] = True
    USUARIOS_CACHE['is_syncing'] = True
    PUESTOS_CACHE['is_syncing'] = True
    AREAS_CACHE['is_syncing'] = True
    
    try:
        load_dotenv()
        token = os.getenv('NOTION_TOKEN_VENTAS')
        db_clientes = os.getenv('NOTION_DATABASE_ID_CLIENTES')
        db_usuarios = os.getenv('NOTION_DATABASE_ID_USUARIOS')
        db_cotizaciones = os.getenv('NOTION_DATABASE_ID_COTIZACIONES')
        
        print(f"DEBUG: Iniciando sincronización de Ventas... (Force={force})")
        
        if token:
            if db_clientes:
                # El usuario solicitó "RAZON SOCIAL" (tipo texto/rich_text)
                CLIENTES_CACHE['data'] = fetch_notion_db(token, db_clientes, "RAZON SOCIAL")
                CLIENTES_CACHE['timestamp'] = datetime.now()
                print(f"DEBUG: Clientes sincronizados ({len(CLIENTES_CACHE['data'])}) usando RAZON SOCIAL")
            
            if db_usuarios:
                # El usuario solicitó "NOMBRE COMPLETO" (tipo fórmula)
                USUARIOS_CACHE['data'] = fetch_notion_db(token, db_usuarios, "NOMBRE COMPLETO")
                USUARIOS_CACHE['timestamp'] = datetime.now()
                print(f"DEBUG: Usuarios sincronizados ({len(USUARIOS_CACHE['data'])}) usando NOMBRE COMPLETO")

            if db_cotizaciones:
                # El usuario solicitó "PUESTO" y "AREA"
                PUESTOS_CACHE['data'] = fetch_notion_db(token, db_cotizaciones, "PUESTO")
                PUESTOS_CACHE['timestamp'] = datetime.now()
                AREAS_CACHE['data'] = fetch_notion_db(token, db_cotizaciones, "AREA")
                AREAS_CACHE['timestamp'] = datetime.now()
                print(f"DEBUG: Puestos ({len(PUESTOS_CACHE['data'])}) y Áreas ({len(AREAS_CACHE['data'])}) sincronizados")
                
    except Exception as e:
        print(f"Error en refresh_sales_cache: {e}")
    finally:
        CLIENTES_CACHE['is_syncing'] = False
        USUARIOS_CACHE['is_syncing'] = False
        PUESTOS_CACHE['is_syncing'] = False
        AREAS_CACHE['is_syncing'] = False

def start_sales_sync():
    """Inicia el hilo de sincronización. Revisa cada 10 min si son las 6 AM."""
    def run():
        last_sync_date = None
        while True:
            now = datetime.now()
            # Si son las 6 AM (o pasadas las 6 y no hemos sincronizado hoy)
            if now.hour == 6 and last_sync_date != now.date():
                print(f"DEBUG: Sincronización programada de las 6 AM iniciada.")
                refresh_sales_cache()
                last_sync_date = now.date()
            
            # También sincronizar al inicio si la caché está vacía
            if CLIENTES_CACHE['timestamp'] is None:
                refresh_sales_cache()
                last_sync_date = now.date()

            time.sleep(600) # Revisar cada 10 minutos
    threading.Thread(target=run, daemon=True).start()

@sales_bp.route('/api/refresh')
@login_required
def refresh_data():
    """Endpoint para forzar la actualización manual."""
    # Ejecutar en hilo para no bloquear la respuesta
    threading.Thread(target=refresh_sales_cache, args=(True,), daemon=True).start()
    return jsonify({
        'success': True,
        'message': 'Sincronización iniciada en segundo plano...'
    })

@sales_bp.route('/api/clientes')
@login_required
def get_clientes():
    global CLIENTES_CACHE
    return jsonify({
        'success': True,
        'data': CLIENTES_CACHE['data'],
        'timestamp': CLIENTES_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if CLIENTES_CACHE['timestamp'] else None,
        'is_syncing': CLIENTES_CACHE['is_syncing']
    })

@sales_bp.route('/api/usuarios')
@login_required
def get_usuarios():
    global USUARIOS_CACHE
    return jsonify({
        'success': True,
        'data': USUARIOS_CACHE['data'],
        'timestamp': USUARIOS_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if USUARIOS_CACHE['timestamp'] else None,
        'is_syncing': USUARIOS_CACHE['is_syncing']
    })

@sales_bp.route('/api/puestos')
@login_required
def get_puestos():
    global PUESTOS_CACHE
    return jsonify({
        'success': True,
        'data': PUESTOS_CACHE['data'],
        'timestamp': PUESTOS_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if PUESTOS_CACHE['timestamp'] else None,
        'is_syncing': PUESTOS_CACHE['is_syncing']
    })

@sales_bp.route('/api/areas')
@login_required
def get_areas():
    global AREAS_CACHE
    return jsonify({
        'success': True,
        'data': AREAS_CACHE['data'],
        'timestamp': AREAS_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if AREAS_CACHE['timestamp'] else None,
        'is_syncing': AREAS_CACHE['is_syncing']
    })

# Herramientas del Módulo de Ventas
SALES_TOOLS = [
    {'name': 'cotizador', 'label': 'Nueva Cotización', 'icon': 'ph-file-plus', 'route': 'sales.new_quotation'}
]

@sales_bp.route('/')
@login_required
def home():
    current_roles = session.get('roles', [])
    if 'Ventas' not in current_roles and 'Admin' not in current_roles:
        flash('No tienes acceso al módulo de Ventas.', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('sales_home.html', 
                         user=current_user, 
                         roles=current_roles, 
                         tools=SALES_TOOLS)

@sales_bp.route('/cotizar')
@login_required
def new_quotation():
    current_roles = session.get('roles', [])
    if 'Ventas' not in current_roles and 'Admin' not in current_roles:
        return redirect(url_for('main.dashboard'))
        
    return render_template('sales_quotation.html', 
                         user=current_user, 
                         roles=current_roles, 
                         tools=SALES_TOOLS)

@sales_bp.route('/api/submit', methods=['POST']) 
def submit_quotation():
    """Recibe datos del formulario y los reenvía al Webhook de n8n."""
    if not current_user.is_authenticated: 
        return {'success': False, 'message': 'No autorizado'}, 401
    
    try:
        data = request.json
        webhook_url = os.getenv('N8N_WEBHOOK_URL')
        
        if not webhook_url:
            return {'success': False, 'message': 'URL de Webhook no configurada en .env'}, 500

        # Inyectar metadata de seguridad / contexto
        data['metadata'] = {
            'generated_by': current_user.email,
            'username': getattr(current_user, 'username', 'N/A'),
            'roles': getattr(current_user, 'roles', []),
            'source': 'AutoIntelli Web App'
        }

        # Enviar a n8n
        # Timeout corto para no colgar la UI si n8n tarda
        response = requests.post(webhook_url, json=data, timeout=10)
        
        if response.status_code == 200:
            return {'success': True, 'message': 'Cotización enviada exitosamente'}
        else:
            return {'success': False, 'message': f'Error en n8n: {response.text}'}, 500
            
    except Exception as e:
        return {'success': False, 'message': f'Error interno: {str(e)}'}, 500
