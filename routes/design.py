import os
import requests
import threading
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

design_bp = Blueprint('design', __name__, url_prefix='/dashboard/diseno')

# Import partidas cache from logistics module
from routes.logistics import PARTIDAS_CACHE

# Herramientas del Módulo de Diseño
DESIGN_TOOLS = [
    {'name': 'accesorios', 'label': 'Accesorios y Tornillería', 'icon': 'ph-nut', 'route': 'design.accessories_capture'}
]

@design_bp.route('/')
@login_required
def home():
    current_roles = session.get('roles', [])
    if 'Diseño' not in current_roles and 'Admin' not in current_roles:
        flash('No tienes acceso al módulo de Diseño.', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('design_home.html', 
                         user=current_user, 
                         roles=current_roles, 
                         tools=DESIGN_TOOLS)

@design_bp.route('/accesorios')
@login_required
def accessories_capture():
    current_roles = session.get('roles', [])
    if 'Diseño' not in current_roles and 'Admin' not in current_roles:
        return redirect(url_for('main.dashboard'))
        
    return render_template('design_accessories.html', 
                         user=current_user, 
                         roles=current_roles, 
                         tools=DESIGN_TOOLS)

# Caché para Inventario de Diseño
INVENTARIO_CACHE = {
    'data': [],
    'timestamp': None,
    'is_syncing': False
}

# Caché para Proyectos que necesitan material
PROYECTOS_CACHE = {
    'data': [],
    'timestamp': None,
    'is_syncing': False
}

def refresh_inventory_cache():
    """Sincroniza datos de la base de datos de Inventario de Notion."""
    global INVENTARIO_CACHE
    if INVENTARIO_CACHE['is_syncing']:
        return
    
    INVENTARIO_CACHE['is_syncing'] = True
    try:
        load_dotenv()
        token = os.getenv('NOTION_TOKEN_DISENO')
        database_id = os.getenv('NOTION_DATABASE_ID_INVENTARIO')
        
        if not token or not database_id:
            print("DEBUG: Falta token o ID de inventario en .env")
            INVENTARIO_CACHE['is_syncing'] = False
            return

        # Para filtrar solo la propiedad "DESCRIPCIÓN", necesitamos su ID o nombre exacto.
        # Notion permite usar el nombre de la propiedad en el query parameter filter_properties.
        url = f"https://api.notion.com/v1/databases/{database_id}/query?filter_properties=DESCRIPCI%C3%93N"
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        new_items = []
        has_more = True
        next_cursor = None
        
        while has_more:
            payload = {}
            if next_cursor:
                payload["start_cursor"] = next_cursor
                
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.ok:
                data = response.json()
                for page in data.get('results', []):
                    props = page.get('properties', {})
                    # Buscamos la propiedad DESCRIPCIÓN (puede ser title o rich_text según la DB)
                    desc_prop = props.get('DESCRIPCIÓN', {})
                    text_list = desc_prop.get('title', []) if 'title' in desc_prop else desc_prop.get('rich_text', [])
                    
                    if text_list:
                        text = text_list[0].get('plain_text', '')
                        if text:
                            new_items.append(text)
                
                has_more = data.get('has_more', False)
                next_cursor = data.get('next_cursor')
            else:
                print(f"DEBUG: Error API Notion Inventario: {response.text}")
                break
        
        new_items = sorted(list(set(new_items))) # Eliminar duplicados y ordenar
        INVENTARIO_CACHE['data'] = new_items
        INVENTARIO_CACHE['timestamp'] = datetime.now()
        print(f"DEBUG: Sincronización de INVENTARIO completada. {len(new_items)} registros obtenidos.")
        
    except Exception as e:
        print(f"ERROR en sincronización de Inventario: {str(e)}")
    finally:
        INVENTARIO_CACHE['is_syncing'] = False

def refresh_projects_cache():
    """Sincroniza proyectos que necesitan material desde Notion."""
    global PROYECTOS_CACHE
    if PROYECTOS_CACHE['is_syncing']:
        return
    
    PROYECTOS_CACHE['is_syncing'] = True
    try:
        load_dotenv()
        token = os.getenv('NOTION_TOKEN_DISENO')
        database_id = os.getenv('NOTION_DATABASE_ID_PROYECTOS')
        
        if not token or not database_id:
            print("DEBUG: Falta token o ID de proyectos en .env")
            PROYECTOS_CACHE['is_syncing'] = False
            return

        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        new_projects = []
        has_more = True
        next_cursor = None
        
        while has_more:
            # Filtrar directamente en Notion con criterios estrictos
            payload = {
                "filter": {
                    "and": [
                        {
                            "property": "REQUIERE ACCESORIOS",
                            "select": {
                                "equals": "SI"
                            }
                        },
                        {
                            "property": "ESTATUS ACCESORIOS",
                            "formula": {
                                "string": {
                                    "contains": "pendientes"
                                }
                            }
                        },
                        {
                            "property": "ARCHIVADOS 2.0",
                            "formula": {
                                "number": {
                                    "does_not_equal": 1
                                }
                            }
                        }
                    ]
                }
            }
            
            if next_cursor:
                payload["start_cursor"] = next_cursor
                
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.ok:
                data = response.json()
                
                for i, page in enumerate(data.get('results', [])):
                    props = page.get('properties', {})
                    
                    # 1. Check REQUIERE ACCESORIOS
                    requiere_prop = props.get('REQUIERE ACCESORIOS', {})
                    requiere_value = ''
                    if requiere_prop.get('type') == 'select':
                        select_obj = requiere_prop.get('select', {})
                        if select_obj:
                            requiere_value = select_obj.get('name', '')
                    
                    # 2. Check ESTATUS ACCESORIOS
                    estatus_prop = props.get('ESTATUS ACCESORIOS', {})
                    estatus_text = ''
                    if estatus_prop.get('type') == 'formula':
                        formula_result = estatus_prop.get('formula', {})
                        if formula_result.get('type') == 'string':
                            estatus_text = formula_result.get('string', '')
                    
                    # 3. Check CODIGO PROYECTO E extraction
                    # Try to find property even if casing matches loosely
                    codigo_key = next((k for k in props.keys() if k.upper() == 'CODIGO PROYECTO E'), None)
                    codigo_val = 'Sin código'
                    
                    if codigo_key:
                        codigo_prop = props.get(codigo_key, {})
                        prop_type = codigo_prop.get('type')
                        if prop_type == 'title':
                            title_list = codigo_prop.get('title', [])
                            if title_list:
                                codigo_val = title_list[0].get('plain_text', 'Sin código')
                        elif prop_type == 'rich_text':
                            text_list = codigo_prop.get('rich_text', [])
                            if text_list:
                                codigo_val = text_list[0].get('plain_text', 'Sin código')
                        elif prop_type == 'formula':
                             # Handle formula just in case
                            formula_res = codigo_prop.get('formula', {})
                            if formula_res.get('type') == 'string':
                                codigo_val = formula_res.get('string', 'Sin código')

                    # --- DEBUG DIAGNOSTIC FOR "PENDIENTES" ---
                    # if 'pendientes' in estatus_text.lower():
                    #     print(f"DEBUG: Found 'pendientes' item. REQUIERE='{requiere_value}', CODIGO='{codigo_val}'")
                    
                    # --- FILTER LOGIC ---
                    
                    # Filter 1: REQUIERE ACCESORIOS = SI
                    # Ya filtrado por Notion API, pero mantenemos comprobación por seguridad
                    if requiere_value.upper().strip() != 'SI':
                        continue
                        
                    # Filter 2: ESTATUS ACCESORIOS contains "pendientes"
                    if 'pendientes' not in estatus_text.lower():
                        continue
                        
                    # If we passed filters, add to list
                    project_info = {
                        'id': page.get('id', ''),
                        'estatus_accesorios': estatus_text,
                        'codigo_proyecto': codigo_val
                    }
                    new_projects.append(project_info)
                
                has_more = data.get('has_more', False)
                next_cursor = data.get('next_cursor')
            else:
                print(f"DEBUG: Error API Notion Proyectos: {response.text}")
                break
        
        # Success path: save data
        PROYECTOS_CACHE['data'] = new_projects
        PROYECTOS_CACHE['timestamp'] = datetime.now()
        print(f"DEBUG: Sincronización de PROYECTOS completada. {len(new_projects)} proyectos con 'pendientes' obtenidos.")
        
    except Exception as e:
        print(f"ERROR en sincronización de Proyectos: {str(e)}")
        # Partial save on error
        if new_projects:
             print(f"DEBUG: GUARDANDO PARCIALMENTE: {len(new_projects)} proyectos obtenidos antes del error.")
             PROYECTOS_CACHE['data'] = new_projects
             PROYECTOS_CACHE['timestamp'] = datetime.now()
    finally:
        PROYECTOS_CACHE['is_syncing'] = False

def start_inventory_scheduler():
    """Inicia el hilo de sincronización diaria a las 7 AM."""
    def run_sync():
        # Sincronización inicial al arrancar
        refresh_inventory_cache()
        refresh_projects_cache()
        
        while True:
            now = datetime.now()
            # Calcular próxima ejecución a las 7 AM
            target = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            
            sleep_seconds = (target - now).total_seconds()
            print(f"DEBUG: Próxima sincronización en {sleep_seconds/3600:.2f} horas (a las 07:00 AM)")
            time.sleep(sleep_seconds)
            refresh_inventory_cache()
            refresh_projects_cache()
    
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()

# Iniciar el scheduler al importar el blueprint
start_inventory_scheduler()

@design_bp.route('/api/proyectos', methods=['GET'])
@login_required
def get_proyectos():
    """Sirve la lista de proyectos que necesitan material."""
    global PROYECTOS_CACHE
    try:
        force_refresh = request.args.get('force') == 'true'
        if force_refresh:
            threading.Thread(target=refresh_projects_cache, daemon=True).start()
            return jsonify({'success': True, 'proyectos': PROYECTOS_CACHE['data'], 'message': 'Sincronización iniciada...'})
        
        return jsonify({
            'success': True, 
            'proyectos': PROYECTOS_CACHE['data'], 
            'timestamp': PROYECTOS_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if PROYECTOS_CACHE['timestamp'] else None,
            'is_syncing': PROYECTOS_CACHE['is_syncing']
        })
    except Exception as e:
        print(f"ERROR in get_proyectos: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@design_bp.route('/api/partidas', methods=['GET'])
@login_required
def get_partidas():
    """Sirve la lista de partidas desde la caché del módulo de logística."""
    try:
        return jsonify({
            'success': True, 
            'partidas': PARTIDAS_CACHE['data'], 
            'timestamp': PARTIDAS_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if PARTIDAS_CACHE['timestamp'] else None,
            'is_syncing': PARTIDAS_CACHE['is_syncing']
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@design_bp.route('/api/inventario', methods=['GET'])
@login_required
def get_inventario():
    """Sirve la lista de inventario desde la caché."""
    global INVENTARIO_CACHE
    try:
        force_refresh = request.args.get('force') == 'true'
        if force_refresh:
            threading.Thread(target=refresh_inventory_cache, daemon=True).start()
            return jsonify({'success': True, 'items': INVENTARIO_CACHE['data'], 'message': 'Sincronización iniciada...'})

        return jsonify({
            'success': True, 
            'items': INVENTARIO_CACHE['data'], 
            'timestamp': INVENTARIO_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if INVENTARIO_CACHE['timestamp'] else None,
            'is_syncing': INVENTARIO_CACHE['is_syncing']
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@design_bp.route('/api/submit', methods=['POST']) 
@login_required
def submit_accessories():
    """Recibe datos del formulario de accesorios y los envía al Webhook."""
    try:
        load_dotenv() # Asegurar que las variables más recientes estén cargadas
        data = request.json
        
        # Priorizar la nueva variable específica
        webhook_url = os.getenv('ACCESORIOS_WEBHOOK_URL')
        
        if not webhook_url:
            webhook_url = os.getenv('N8N_WEBHOOK_URL_DISENO') or os.getenv('N8N_WEBHOOK_URL')

        print(f"DEBUG: Intentando enviar a Webhook: {webhook_url}")

        if not webhook_url:
            return jsonify({'success': False, 'message': 'URL de Webhook (ACCESORIOS_WEBHOOK_URL) no configurada en .env'}), 500

        # Inyectar metadata
        data['metadata'] = {
            'generated_by': current_user.email,
            'username': getattr(current_user, 'username', 'N/A'),
            'roles': getattr(current_user, 'roles', []),
            'source': 'AutoIntelli Design Module - Accesorios',
            'timestamp': datetime.now().isoformat()
        }

        print(f"DEBUG: Payload enviado: {data}")

        response = requests.post(webhook_url, json=data, timeout=15)
        
        print(f"DEBUG: Respuesta Webhook - Status: {response.status_code}, Body: {response.text}")

        if response.ok:
            return jsonify({'success': True, 'message': 'Solicitud enviada exitosamente'})
        else:
            return jsonify({
                'success': False, 
                'message': f'Error en el servidor de destino (Status: {response.status_code})',
                'details': response.text
            }), 500
            
    except Exception as e:
        import traceback
        print(f"ERROR en submit_accessories: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500
