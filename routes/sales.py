from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from flask_login import login_required, current_user
import os
import requests
from constants import get_allowed_modules

sales_bp = Blueprint('sales', __name__, url_prefix='/dashboard/ventas')

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
            'generated_by': session['user'],
            'roles': session.get('roles', []),
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
