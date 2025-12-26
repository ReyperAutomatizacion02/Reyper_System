from flask import Blueprint, render_template, session, redirect, url_for
from constants import get_allowed_modules

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    user_roles = session.get('roles', [])
    allowed_modules = get_allowed_modules(user_roles)
                
    return render_template('dashboard.html', user=session['user'], roles=user_roles, modules=allowed_modules)
