from flask import Blueprint, render_template, session, redirect, url_for
from flask_login import login_required, current_user
from constants import get_allowed_modules

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    user_roles = session.get('roles', [])
    # Alternatively use current_user.roles if we added it to the user object persistence
    # But since we kept session['roles'] in auth.py, this is fine.
    # Better to rely on current_user if possible, but our User model just holds what we give it.
    
    allowed_modules = get_allowed_modules(user_roles)
                
    return render_template('dashboard.html', user=current_user, roles=user_roles, modules=allowed_modules)
