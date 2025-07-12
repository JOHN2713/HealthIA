from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FloatField, IntegerField, SelectField, TextAreaField
from wtforms.validators import InputRequired, Email, Length, EqualTo


class RegisterForm(FlaskForm):
    email = StringField('Correo electrónico', validators=[InputRequired(), Email()])
    password = PasswordField('Contraseña', validators=[InputRequired(), Length(min=6)])
    confirm = PasswordField('Confirmar contraseña', validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField('Registrarse')

class LoginForm(FlaskForm):
    email = StringField('Correo electrónico', validators=[InputRequired(), Email()])
    password = PasswordField('Contraseña', validators=[InputRequired()])
    submit = SubmitField('Iniciar sesión')

class MeasureForm(FlaskForm):
    weight = FloatField('Peso (kg)', validators=[InputRequired()])
    height = FloatField('Estatura (cm)', validators=[InputRequired()])
    age = IntegerField('Edad', validators=[InputRequired()])
    gender = SelectField('Género', choices=[('masculino', 'Masculino'), ('femenino', 'Femenino')])
    alergias = TextAreaField('Alergias (separadas por coma)')
    submit = SubmitField('Guardar medidas')
