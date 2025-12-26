from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, login_required
from extensions import supabase
from models import User
import re
import os

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
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
                username = None
            else:
                profile_data = profile_response.data[0]
                profile_status = profile_data.get('status', 'Pendiente')
                user_roles = profile_data.get('roles', []) or []
                username = profile_data.get('username')
            
            # Validar estado
            if profile_status != 'Aprobado':
                supabase.auth.sign_out()
                if profile_status == 'Pendiente':
                    flash('Tu cuenta está pendiente de aprobación por un administrador.', 'error')
                else:
                    flash('El acceso a tu cuenta ha sido denegado o cancelado.', 'error')
                return redirect(url_for('auth.login'))

            # Create User object and login
            user = User(id=user_id, email=email, username=username, roles=user_roles)
            login_user(user)
            
            # Legacy session support (optional but good for modules reading session directly)
            session['roles'] = user_roles
            
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            flash(f'Error al iniciar sesión: {str(e)}', 'error')
    
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # ... (Registration logic remains mostly the same, redirecting to login)
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

        # Reglas de complejidad
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
                return redirect(url_for('auth.login'))
                
        except Exception as e:
            flash(f'Error al registrarse: {str(e)}', 'error')
            
    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    supabase.auth.sign_out()
    logout_user() # Flask-Login logout
    session.pop('roles', None)
    return redirect(url_for('main.index'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        try:
            # Use SITE_URL from env or fallback to local
            site_url = os.getenv('SITE_URL', url_for('main.index', _external=True)).rstrip('/')
            reset_path = url_for('auth.reset_password')
            redirect_url = f"{site_url}{reset_path}"
            
            supabase.auth.reset_password_for_email(email, {"redirect_to": redirect_url})
            flash('Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    return render_template('forgot_password.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    # Capture code from URL (PKCE Flow)
    code = request.args.get('code')
    print(f"DEBUG: Reset password GET. Code in URL: {'Present' if code else 'Missing'}")
    
    if request.method == 'POST':
        new_password = request.form.get('password')
        form_code = request.form.get('code') or request.args.get('code')
        print(f"DEBUG: Reset password POST. Code: {'Present' if form_code else 'Missing'}")
        
        if not form_code:
            flash('Error de seguridad: No se detectó el código de validación. Por favor, usa el enlace del correo nuevamente.', 'error')
            return render_template('reset_password.html', code=None)
            
        try:
            # 1. Exchange token for session using verify_otp (most robust for recovery links)
            print("DEBUG: Verifying OTP/Token...")
            # We try verify_otp with recovery type. 
            # This usually works with token_hash or the code from the link.
            supabase.auth.verify_otp({"token_hash": form_code, "type": "recovery"})
            
            # 2. Update the password
            supabase.auth.update_user({"password": new_password})
            
            flash('Contraseña actualizada exitosamente. Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            print(f"DEBUG: Error in reset_password: {str(e)}")
            flash(f'Error al actualizar contraseña: {str(e)}', 'error')
            return render_template('reset_password.html', code=form_code)

    return render_template('reset_password.html', code=code)
