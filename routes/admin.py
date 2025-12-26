from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from extensions import supabase
from constants import SYSTEM_MODULES

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/users')
def users():
    if 'user' not in session: return redirect(url_for('auth.login'))
    
    # Verificar Rol Admin
    current_roles = session.get('roles', [])
    if 'Admin' not in current_roles:
        flash('Acceso restringido a Administradores.', 'error')
        return redirect(url_for('main.dashboard'))

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

@admin_bp.route('/users/update', methods=['POST'])
def user_update():
    if 'user' not in session: return redirect(url_for('auth.login'))
    if 'Admin' not in session.get('roles', []):
        flash('No tienes permisos.', 'error')
        return redirect(url_for('main.dashboard'))
        
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
        
    return redirect(url_for('admin.users'))
