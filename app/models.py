from . import db
from flask_login import UserMixin
from datetime import datetime
from . import login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    weight = db.Column(db.Float)
    height = db.Column(db.Float)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    alergias = db.Column(db.Text)  # Puedes guardarlo como string separado por comas

class Menu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    html_content = db.Column(db.Text, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    cumplido = db.Column(db.Boolean, default=False)

    seguimiento = db.relationship('SeguimientoDia', backref='menu', lazy=True)

class SeguimientoDia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menu.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    cumplido = db.Column(db.Boolean, default=False)
    notas = db.Column(db.Text, nullable=True)
    rutina_ejercicio = db.Column(db.Text, nullable=True)