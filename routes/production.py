import os
import requests
import threading
import time
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

production_bp = Blueprint('production', __name__, url_prefix='/dashboard/produccion')

# Logger del módulo
logger = logging.getLogger(__name__)

# Herramientas del Módulo de Producción
PRODUCTION_TOOLS = [
    {'name': 'planeacion', 'label': 'Planeación', 'icon': 'ph-calendar-blank', 'route': 'production.planning'}
]

# Caché en memoria para Planeación
PLANEACION_CACHE = {
    'data': [],
    'timestamp': None,
    'is_syncing': False
}

def fetch_notion_planeacion(token, database_id):
    """Obtiene los registros de planeación de Notion."""
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    # Filtrar registros de hoy menos 3 días hacia adelante
    corte = (datetime.now() - timedelta(days=3)).isoformat()
    
    # Payload con filtro y ordenamiento
    payload = {
        "filter": {
            "property": "FECHA PLANEADA",
            "date": {
                "on_or_after": corte
            }
        },
        "sorts": [
            {
                "property": "FECHA DE CREACION",
                "direction": "ascending"
            }
        ]
    }
    
    results_list = []
    has_more = True
    next_cursor = None
    
    try:
        while has_more:
            if next_cursor:
                payload["start_cursor"] = next_cursor
                
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.ok:
                data = response.json()
                for page in data.get('results', []):
                    props = page.get('properties', {})
                    
                    # Extraer "N" (Title)
                    n_prop = props.get('N', {})
                    n_value = ""
                    if n_prop.get('type') == 'title':
                        title_list = n_prop.get('title', [])
                        if title_list:
                            n_value = title_list[0].get('plain_text', '')
                    
                    # Extraer "FECHA DE CREACION" (Fecha)
                    fecha_prop = props.get('FECHA DE CREACION', {})
                    fecha_value = None
                    if fecha_prop.get('type') == 'date':
                        date_obj = fecha_prop.get('date')
                        if date_obj:
                            fecha_value = date_obj.get('start')

                    # Extraer "FECHA PLANEADA" (Fecha)
                    planeada_prop = props.get('FECHA PLANEADA', {})
                    planeada_start = None
                    planeada_end = None
                    if planeada_prop.get('type') == 'date':
                        date_obj = planeada_prop.get('date')
                        if date_obj:
                            planeada_start = date_obj.get('start')
                            planeada_end = date_obj.get('end')
                    
                    # Extraer "MAQUINA" (Select)
                    maquina_prop = props.get('MAQUINA', {})
                    maquina_value = ""
                    if maquina_prop.get('type') == 'select':
                        select_obj = maquina_prop.get('select')
                        if select_obj:
                            maquina_value = select_obj.get('name', '')

                    # Extraer "OPERADOR" (Select)
                    operador_prop = props.get('OPERADOR', {})
                    operador_value = ""
                    if operador_prop.get('type') == 'select':
                        select_obj = operador_prop.get('select')
                        if select_obj:
                            operador_value = select_obj.get('name', '')

                    # Extraer "AREA" (Formula)
                    area_prop = props.get('AREA', {})
                    area_value = ""
                    if area_prop.get('type') == 'formula':
                        formula_obj = area_prop.get('formula', {})
                        if formula_obj.get('type') == 'string':
                            area_value = formula_obj.get('string', '')
                    
                    # Extraer "PARTIDA" (Relation) y "NOMBRE PIEZA" (Rollup)
                    partida_prop = props.get('PARTIDA', {})
                    partida_id = ""
                    if partida_prop.get('type') == 'relation':
                        relations = partida_prop.get('relation', [])
                        if relations:
                            partida_id = relations[0].get('id', '')

                    # Extraer "4Make" (Formula con el código 85-...)
                    make_prop = props.get('4Make', {})
                    partida_codigo = ""
                    if make_prop.get('type') == 'formula':
                        formula_obj = make_prop.get('formula', {})
                        if formula_obj.get('type') == 'string':
                            partida_codigo = formula_obj.get('string', '')

                    nombre_pieza_prop = props.get('NOMBRE PIEZA', {})
                    nombre_pieza_value = ""
                    if nombre_pieza_prop.get('type') == 'rollup':
                        rollup_data = nombre_pieza_prop.get('rollup', {})
                        if rollup_data.get('type') == 'array':
                            array_data = rollup_data.get('array', [])
                            if array_data:
                                # Usualmente el primer elemento tiene el texto
                                first_item = array_data[0]
                                if first_item.get('type') == 'title':
                                    title_list = first_item.get('title', [])
                                    if title_list:
                                        nombre_pieza_value = title_list[0].get('plain_text', '')
                                elif first_item.get('type') == 'rich_text':
                                    text_list = first_item.get('rich_text', [])
                                    if text_list:
                                        nombre_pieza_value = text_list[0].get('plain_text', '')

                    # Extraer "A MOSTRAR" (Files/Media)
                    imagen_prop = props.get('A MOSTRAR', {})
                    imagen_url = ""
                    if imagen_prop.get('type') == 'files':
                        files_list = imagen_prop.get('files', [])
                        if files_list:
                            first_file = files_list[0]
                            if first_file.get('type') == 'file':
                                imagen_url = first_file.get('file', {}).get('url', '')
                            elif first_file.get('type') == 'external':
                                imagen_url = first_file.get('external', {}).get('url', '')

                    if n_value:
                        results_list.append({
                            'id': page.get('id'),
                            'n': n_value,
                            'partida': partida_codigo or nombre_pieza_value or n_value, # Código 85-... o Nombre
                            'nombre_pieza': nombre_pieza_value or n_value,
                            'partida_id': partida_id,
                            'imagen_url': imagen_url,
                            'fecha_creacion': fecha_value,
                            'fecha_planeada': planeada_start,
                            'fecha_planeada_fin': planeada_end,
                            'maquina': maquina_value,
                            'operador': operador_value,
                            'area': area_value
                        })
                
                has_more = data.get('has_more', False)
                next_cursor = data.get('next_cursor')
            else:
                logger.error(f"Error API Notion Planeación: {response.text}")
                break
    except Exception as e:
        logger.error(f"Error en fetch_notion_planeacion: {e}")
        
    return results_list

def refresh_planeacion_cache(force=False):
    """Sincroniza la caché de planeación."""
    global PLANEACION_CACHE
    if not force and PLANEACION_CACHE['is_syncing']:
        return
        
    PLANEACION_CACHE['is_syncing'] = True
    try:
        load_dotenv()
        token = os.getenv('NOTION_TOKEN_PRODUCCION')
        db_planeacion = os.getenv('NOTION_DATABASE_ID_PLANEACION')
        
        if token and db_planeacion:
            logger.info("Iniciando sincronización de Planeación de Producción...")
            data = fetch_notion_planeacion(token, db_planeacion)
            PLANEACION_CACHE['data'] = data
            PLANEACION_CACHE['timestamp'] = datetime.now()
            logger.info(f"Sincronización de Planeación completada ({len(data)} registros)")
            if data:
                logger.info(f"DEBUG - Primeros 3 registros: {data[:3]}")
        else:
            logger.warning("Faltan credenciales de Producción en el archivo .env")
            
    except Exception as e:
        logger.exception(f"Error en refresh_planeacion_cache: {e}")
    finally:
        PLANEACION_CACHE['is_syncing'] = False

def start_production_sync():
    """Inicia el hilo de sincronización en segundo plano."""
    def run_sync():
        # Sincronización inicial
        refresh_planeacion_cache()
        
        while True:
            # Sincronizar cada hora
            time.sleep(3600)
            refresh_planeacion_cache()
            
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()

# Iniciar sincronización
start_production_sync()

@production_bp.route('/')
@login_required
def home():
    current_roles = session.get('roles', [])
    if 'Produccion' not in current_roles and 'Admin' not in current_roles:
        flash('No tienes acceso al módulo de Producción.', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('production_home.html', 
                          user=current_user, 
                          roles=current_roles, 
                          tools=PRODUCTION_TOOLS)

@production_bp.route('/planeacion')
@login_required
def planning():
    current_roles = session.get('roles', [])
    if 'Produccion' not in current_roles and 'Admin' not in current_roles:
        return redirect(url_for('main.dashboard'))
        
    return render_template('production_planning.html', 
                          user=current_user, 
                          roles=current_roles, 
                          tools=PRODUCTION_TOOLS)

@production_bp.route('/api/data')
@login_required
def get_all_data():
    """API que devuelve los datos de planeación."""
    global PLANEACION_CACHE
    
    force_sync = request.args.get('force') == 'true'
    if force_sync and not PLANEACION_CACHE['is_syncing']:
        # Iniciar sincronización en hilo para no bloquear la respuesta
        threading.Thread(target=refresh_planeacion_cache, args=(True,)).start()
        
    return jsonify({
        'success': True,
        'planeacion': {
            'data': PLANEACION_CACHE['data'],
            'timestamp': PLANEACION_CACHE['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if PLANEACION_CACHE['timestamp'] else None
        },
        'is_syncing': PLANEACION_CACHE['is_syncing']
    })
