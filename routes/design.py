import os
import requests
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

design_bp = Blueprint('design', __name__, url_prefix='/dashboard/diseno')

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

@design_bp.route('/api/submit', methods=['POST']) 
@login_required
def submit_accessories():
    """Recibe datos del formulario de accesorios y los envía al Webhook."""
    try:
        data = request.json
        webhook_url = os.getenv('N8N_WEBHOOK_URL_DISENO') # Webhook específico para diseño
        
        if not webhook_url:
            # Fallback al webhook general si no hay uno específico
            webhook_url = os.getenv('N8N_WEBHOOK_URL')

        if not webhook_url:
            return {'success': False, 'message': 'URL de Webhook no configurada'}, 500

        # Inyectar metadata
        data['metadata'] = {
            'generated_by': current_user.email,
            'username': getattr(current_user, 'username', 'N/A'),
            'roles': getattr(current_user, 'roles', []),
            'source': 'AutoIntelli Design Module'
        }

        response = requests.post(webhook_url, json=data, timeout=10)
        
        if response.ok:
            return {'success': True, 'message': 'Solicitud enviada exitosamente'}
        else:
            return {'success': False, 'message': f'Error en el servidor de destino: {response.text}'}, 500
            
    except Exception as e:
        return {'success': False, 'message': f'Error interno: {str(e)}'}, 500
