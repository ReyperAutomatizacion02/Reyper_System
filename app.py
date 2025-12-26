import os
import re
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Definición de Módulos del Sistema
SYSTEM_MODULES = [
    {'name': 'Administracion', 'icon': 'ph-briefcase', 'label': 'Administración'},
    {'name': 'Almacen', 'icon': 'ph-package', 'label': 'Almacén'},
    {'name': 'Logistica', 'icon': 'ph-truck', 'label': 'Logística'},
    {'name': 'Produccion', 'icon': 'ph-factory', 'label': 'Producción'},
    {'name': 'Diseño', 'icon': 'ph-paint-brush', 'label': 'Diseño'},
    {'name': 'Ventas', 'icon': 'ph-shopping-cart', 'label': 'Ventas'},
    {'name': 'Compras', 'icon': 'ph-shopping-bag', 'label': 'Compras'},
    {'name': 'Recursos Humanos', 'icon': 'ph-users', 'label': 'RRHH'},
    {'name': 'Contabilidad', 'icon': 'ph-currency-dollar', 'label': 'Contabilidad'}
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            user_id = response.user.id
            
            # Verificar estado en la tabla de perfiles
            profile_response = supabase.table('profiles').select('*').eq('id', user_id).execute()
            
            # Si no existe perfil, crearlo (fallback)
            if not profile_response.data:
                supabase.table('profiles').insert({"id": user_id, "email": email, "status": "Pendiente"}).execute()
                profile_status = 'Pendiente'
                user_roles = []
            else:
                profile_data = profile_response.data[0]
                profile_status = profile_data.get('status', 'Pendiente')
                user_roles = profile_data.get('roles', [])
                if user_roles is None: user_roles = [] # Asegurar lista si es nulo
            
            # Validar estado
            if profile_status != 'Aprobado':
                supabase.auth.sign_out()
                if profile_status == 'Pendiente':
                    flash('Tu cuenta está pendiente de aprobación por un administrador.', 'error')
                else:
                    flash('El acceso a tu cuenta ha sido denegado o cancelado.', 'error')
                return redirect(url_for('login'))

            session['user'] = response.user.email
            session['roles'] = user_roles
            
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Error al iniciar sesión: {str(e)}', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        username = request.form.get('username')

        # 0. Validar contraseñas
        if password != confirm_password:
            flash('Las contraseñas no coinciden.', 'error')
            return render_template('register.html')

        # Reglas de complejidad: 1 mayus, 1 minus, 1 num, 1 especial, min 10 chars
        if not (len(password) >= 10 and
                re.search(r'[A-Z]', password) and
                re.search(r'[a-z]', password) and
                re.search(r'\d', password) and
                re.search(r'[!@#$%^&*(),.?":{}|<>]', password)):
            flash('La contraseña no cumple con los requisitos de seguridad.', 'error')
            return render_template('register.html')
        
        # 1. Verificar unicidad de username
        try:
            existing_user = supabase.table('profiles').select('username').eq('username', username).execute()
            if existing_user.data:
                flash('El nombre de usuario ya está en uso.', 'error')
                return render_template('register.html') 
                
            response = supabase.auth.sign_up({"email": email, "password": password})
            
            if response.user:
                # Actualizar perfil con datos extra
                supabase.table('profiles').upsert({
                    "id": response.user.id,
                    "email": email,
                    "status": "Pendiente",
                    "full_name": full_name,
                    "username": username
                }).execute()
                
                flash('Registro exitoso. Tu cuenta está pendiente de aprobación.', 'success')
                return redirect(url_for('login'))
                
        except Exception as e:
            flash(f'Error al registrarse: {str(e)}', 'error')
            
    return render_template('register.html')

def get_allowed_modules(user_roles):
    """Filtra los módulos del sistema basado en los roles del usuario."""
    if 'Admin' in user_roles:
        return SYSTEM_MODULES
    return [m for m in SYSTEM_MODULES if m['name'] in user_roles]

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user_roles = session.get('roles', [])
    allowed_modules = get_allowed_modules(user_roles)
                
    return render_template('dashboard.html', user=session['user'], roles=user_roles, modules=allowed_modules)

# Herramientas del Módulo de Ventas
SALES_TOOLS = [
    {'name': 'cotizador', 'label': 'Nueva Cotización', 'icon': 'ph-file-plus', 'route': 'sales_new_quotation'}
]

@app.route('/dashboard/ventas')
def sales_dashboard():
    if 'user' not in session: return redirect(url_for('login'))
    
    current_roles = session.get('roles', [])
    if 'Ventas' not in current_roles and 'Admin' not in current_roles:
        flash('No tienes acceso al módulo de Ventas.', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('sales_home.html', 
                         user=session['user'], 
                         roles=current_roles, 
                         tools=SALES_TOOLS)

@app.route('/dashboard/ventas/cotizar')
def sales_new_quotation():
    if 'user' not in session: return redirect(url_for('login'))
    
    current_roles = session.get('roles', [])
    if 'Ventas' not in current_roles and 'Admin' not in current_roles:
        return redirect(url_for('dashboard'))
        
    return render_template('sales_quotation.html', 
                         user=session['user'], 
                         roles=current_roles, 
                         tools=SALES_TOOLS)

@app.route('/admin/users')
def admin_users():
    if 'user' not in session: return redirect(url_for('login'))
    
    # Verificar Rol Admin
    current_roles = session.get('roles', [])
    if 'Admin' not in current_roles:
        flash('Acceso restringido a Administradores.', 'error')
        return redirect(url_for('dashboard'))

    # Obtener todos los perfiles
    try:
        users_res = supabase.table('profiles').select('*').order('created_at', desc=True).execute()
        profiles = users_res.data
    except Exception as e:
        flash(f'Error al cargar usuarios: {str(e)}', 'error')
        profiles = []
    
    # Lista de roles disponibles para asignar
    # Combinamos los roles de modulos + el rol Admin
    available_roles = ['Admin'] + [m['name'] for m in SYSTEM_MODULES]

    # Pasamos también 'modules' filter para el sidebar del admin (ve todo)
    return render_template('admin_users.html', 
                         profiles=profiles, 
                         available_roles=available_roles,
                         user=session['user'],
                         roles=current_roles,
                         modules=SYSTEM_MODULES)

@app.route('/admin/users/update', methods=['POST'])
def admin_user_update():
    if 'user' not in session: return redirect(url_for('login'))
    if 'Admin' not in session.get('roles', []):
        flash('No tienes permisos.', 'error')
        return redirect(url_for('dashboard'))
        
    target_id = request.form.get('user_id')
    new_status = request.form.get('status')
    new_roles = request.form.getlist('roles') # Obtiene lista de checkboxes seleccionados
    
    try:
        supabase.table('profiles').update({
            "status": new_status,
            "roles": new_roles
        }).eq('id', target_id).execute()
        flash('Usuario actualizado correctamente.', 'success')
    except Exception as e:
        flash(f'Error al actualizar: {str(e)}', 'error')
        
    return redirect(url_for('admin_users'))

@app.route('/logout')
def logout():
    supabase.auth.sign_out()
    session.pop('user', None)
    session.pop('roles', None)
    return redirect(url_for('index'))


import requests

# ... imports existentes ...

@app.route('/api/quotation/submit', methods=['POST'])
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

if __name__ == '__main__':
    app.run(debug=True)
