import os
from dotenv import load_dotenv
from flask import Flask
from routes.auth import auth_bp
from routes.main import main_bp
from routes.sales import sales_bp
from routes.admin import admin_bp
from routes.logistics import logistics_bp

from flask_login import LoginManager
from models import User
from extensions import supabase

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = "Por favor inicia sesión para acceder a esta página."
login_manager.login_message_category = "error"

@login_manager.user_loader
def load_user(user_id):
    try:
        # Fetch profile from Supabase
        response = supabase.table('profiles').select('*').eq('id', user_id).execute()
        if response.data:
            data = response.data[0]
            return User(
                id=data['id'], 
                email=data['email'], 
                username=data.get('username'),
                roles=data.get('roles', [])
            )
    except Exception:
        return None
    return None

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(logistics_bp)

if __name__ == '__main__':
    app.run(debug=True)
