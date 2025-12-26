from flask import Blueprint, render_template, session, redirect, url_for, flash, request
import os
import requests
from constants import get_allowed_modules

sales_bp = Blueprint('sales', __name__, url_prefix='/dashboard/ventas')

# Herramientas del Módulo de Ventas
SALES_TOOLS = [
    {'name': 'cotizador', 'label': 'Nueva Cotización', 'icon': 'ph-file-plus', 'route': 'sales.new_quotation'}
]

@sales_bp.route('/')
def home():
    if 'user' not in session: return redirect(url_for('auth.login'))
    
    current_roles = session.get('roles', [])
    if 'Ventas' not in current_roles and 'Admin' not in current_roles:
        flash('No tienes acceso al módulo de Ventas.', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('sales_home.html', 
                         user=session['user'], 
                         roles=current_roles, 
                         tools=SALES_TOOLS)

@sales_bp.route('/cotizar')
def new_quotation():
    if 'user' not in session: return redirect(url_for('auth.login'))
    
    current_roles = session.get('roles', [])
    if 'Ventas' not in current_roles and 'Admin' not in current_roles:
        return redirect(url_for('main.dashboard'))
        
    return render_template('sales_quotation.html', 
                         user=session['user'], 
                         roles=current_roles, 
                         tools=SALES_TOOLS)

@sales_bp.route('/api/submit', methods=['POST']) 
# Note: The route in app.py was /api/quotation/submit. We might want to keep it global or namespaced.
# If namespaced under /dashboard/ventas, it would be /dashboard/ventas/api/submit.
# But existing JS calls /api/quotation/submit.
# I will create a separate Blueprint for API or keep this strict.
# Let's override the url_prefix for this specific route if possible, or just create an 'api' blueprint?
# Or just put it here with the absolute path?
# Flask blueprints can accept absolute paths starting with /.
def submit_quotation():
    """Recibe datos del formulario y los reenvía al Webhook de n8n."""
    if 'user' not in session: 
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
