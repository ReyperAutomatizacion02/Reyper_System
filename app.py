import os
from dotenv import load_dotenv
from flask import Flask
from routes.auth import auth_bp
from routes.main import main_bp
from routes.sales import sales_bp
from routes.admin import admin_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(admin_bp)

if __name__ == '__main__':
    app.run(debug=True)
