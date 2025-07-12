from flask_migrate import Migrate
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
import os

db = SQLAlchemy()
mail = Mail()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = 'supersecretkey'  # cámbialo en producción
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diet.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Configuración de correo (puedes usar Gmail u otro SMTP)
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'johnyv1305@gmail.com'
    app.config['MAIL_PASSWORD'] = 'xxvy dylw tvtt zbws'
    app.config['MAIL_DEFAULT_SENDER'] = 'johnyv1305@gmail.com'

    db.init_app(app)
    mail.init_app(app)
    migrate = Migrate(app, db)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from .models import User

    with app.app_context():
        db.create_all()

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app
