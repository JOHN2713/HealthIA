from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user
from .forms import MeasureForm
from . import db
from datetime import datetime, timedelta
from .diet import (
    load_foods, calculate_targets, solve_diet_lp,
    generate_menu, calcular_costo_total
)
import io
from xhtml2pdf import pisa  # Librería para convertir HTML a PDF
from flask import make_response
import markdown2
import pdfkit
from flask import session
from flask import Response
from .models import Menu, SeguimientoDia
from .utils import enviar_menu_por_correo
from flask_mail import Message
from . import mail
from weasyprint import HTML
import os
main = Blueprint('main', __name__)

@main.route('/')
def home():
    return redirect(url_for('auth.login'))

@main.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    form = MeasureForm()

    if form.validate_on_submit():
        current_user.weight = form.weight.data
        current_user.height = form.height.data
        current_user.age = form.age.data
        current_user.gender = form.gender.data
        current_user.alergias = request.form.get('alergias')  # 👈 aquí
        db.session.commit()
        flash("Medidas guardadas correctamente ✅", "success")
        return redirect(url_for('main.dashboard'))  # ← redirige después de guardar

    elif request.method == 'GET':
        form.weight.data = current_user.weight
        form.height.data = current_user.height
        form.age.data = current_user.age
        form.gender.data = current_user.gender
        form.alergias.data = current_user.alergias

    # ✅ Asegúrate de retornar el render siempre al final
    return render_template('dashboard.html', form=form, user=current_user, medidas=current_user, page_background="bg-plan")

@main.route('/diet_plan', methods=['GET', 'POST'])
@login_required
def plan():
    foods, alimentos_agrupados = load_foods()
    resultado = None
    colores = {
        "carnes": "#e74c3c",
        "frutas": "#1abc9c",
        "verduras": "#27ae60",
        "cereales": "#f1c40f",
        "bebidas": "#9b59b6",
        "otros": "#95a5a6"
    }
    if request.method == 'POST':
        # Obtener datos del usuario y del formulario
        objetivo = request.form.get("objetivo")
        duracion = int(request.form.get("duracion"))
        presupuesto = float(request.form.get("presupuesto"))
        alergias_formulario = request.form.getlist("alergias")  # Desde el checkbox
        alergias_guardadas = []
        if current_user.is_authenticated and current_user.alergias:
            alergias_guardadas = [a.strip().lower() for a in current_user.alergias.split(',')]
        # Combinar y eliminar duplicados
        alergias = list(set(alergias_formulario + alergias_guardadas))
        rutina = bool(request.form.get("rutina"))

        # Datos del usuario
        user_data = {
            "weight": current_user.weight,
            "height": current_user.height,
            "age": current_user.age,
            "gender": current_user.gender,
            "objective": objetivo,
            "rutina": rutina
        }

        # 1. Calcular metas nutricionales
        targets = calculate_targets(
            weight=current_user.weight,
            height=current_user.height,
            age=current_user.age,
            gender=current_user.gender,
            objective=objetivo
        )

        # 2. Resolver dieta con LP
        proportions, solution = solve_diet_lp(foods.copy(), targets, budget=presupuesto, banned_foods=alergias)

        # 3. Calcular costo total
        costo_total = calcular_costo_total(solution, foods)

        # 4. Generar menú con Gemini
        menu_html = generate_menu(proportions, user_data, duracion)

        # 5. Guardar menú en base de datos
        fecha_inicio = datetime.today().date()
        hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fecha_fin = fecha_inicio + timedelta(days=duracion - 1)

        nuevo_menu = Menu(
            user_id=current_user.id,
            html_content=menu_html,
            duration_days=duracion,
        )
        db.session.add(nuevo_menu)
        db.session.commit()

        # Crear seguimiento por cada día
        for i in range(duracion):
            dia = fecha_inicio + timedelta(days=i)
            seguimiento = SeguimientoDia(
                menu_id=nuevo_menu.id,
                fecha=dia
            )
            db.session.add(seguimiento)
        db.session.commit()

        # Guardar todo en una variable para pasar al template
        resultado = {
            "proportions": proportions,
            "solution": solution,
            "targets": targets,
            "costo_total": costo_total,
            "menu_html": menu_html,  # ← NUEVO para mostrar como HTML
            "duracion": duracion,
            "fecha_inicio": datetime.today().date(),
            "hora_actual": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "fecha_fin": fecha_inicio + timedelta(days=duracion - 1),
            "menu_id": nuevo_menu.id

        }
        session['menu_html'] = menu_html

    return render_template("diet_plan.html", user=current_user,
                           alimentos=alimentos_agrupados,
                           resultado=resultado, categoria_colores=colores, page_background="bg-historial")

    

@main.route('/descargar_menu', methods=['POST'])
@login_required
def descargar_menu():
    menu_html = session.get('menu_html')

    if not menu_html:
        return "No se recibió contenido para generar el PDF", 400

    # Agregar correo y hora actual
    correo_usuario = current_user.email
    hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    extra_info = f"""
    <div style='font-size: 14px; color: #444; margin-bottom: 20px;'>
        <strong>Correo:</strong> {correo_usuario}<br>
        <strong>Fecha y hora de descarga:</strong> {hora_actual}
    </div>
    """

    # Concatenar HTML
    html_final = extra_info + menu_html

    # Reemplazar rutas relativas de imágenes por rutas absolutas
    ruta_static_absoluta = os.path.abspath("app/static/img").replace("\\", "/")
    html_final = html_final.replace('/static/img/', f'file:///{ruta_static_absoluta}/')



    # 📄 Devolver como archivo HTML
    return Response(
        html_final,
        mimetype='text/html',
        headers={
            'Content-Disposition': 'attachment; filename=menu_visual.html'
        }
    )

@main.route('/historial_menus')
@login_required
def historial_menus():
    menus = Menu.query.filter_by(user_id=current_user.id).order_by(Menu.created_at.desc()).all()
    return render_template('historial_menus.html', menus=menus)

@main.route('/marcar_cumplido/<int:menu_id>')
@login_required
def marcar_cumplido(menu_id):
    menu = Menu.query.get_or_404(menu_id)
    if menu.user_id != current_user.id:
        abort(403)
    menu.cumplido = True
    db.session.commit()
    return redirect(url_for('main.historial_menus'))

@main.route('/descargar_menu/<int:menu_id>')
@login_required
def descargar_menu_guardado(menu_id):
    menu = Menu.query.get_or_404(menu_id)

    if menu.user_id != current_user.id:
        return "No autorizado", 403

    # Agregar correo y hora actual
    correo_usuario = current_user.email
    hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    extra_info = f"""
    <div style='font-size: 14px; color: #444; margin-bottom: 20px;'>
        <strong>Correo:</strong> {correo_usuario}<br>
        <strong>Fecha y hora de descarga:</strong> {hora_actual}
    </div>
    """
    estilos_pdf = """
        <style>
            body {
                font-family: Arial, sans-serif;
                font-size: 14px;
            }

            img {
                max-width: 100%;
                height: auto;
                display: block;
                margin: 0 auto;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
                font-size: 13px;
            }

            th, td {
                padding: 6px;
                text-align: left;
                border: 1px solid #ccc;
                word-wrap: break-word;
            }

            .meal-block {
                page-break-inside: avoid;
                margin-bottom: 30px;
            }

            h2, h3 {
                color: #333;
            }
        </style>
        """


    html_final = estilos_pdf + extra_info + menu.html_content

    # 🔁 Cambiar rutas de imágenes a absolutas si es necesario
    ruta_static_absoluta = os.path.abspath("app/static/img").replace("\\", "/")
    html_final = html_final.replace('static/img/', f'file:///{ruta_static_absoluta}/')

    # 📄 Devolver como archivo HTML
    return Response(
        html_final,
        mimetype='text/html',
        headers={
            'Content-Disposition': 'attachment; filename=menu_visual.html'
        }
    )


@main.route('/enviar_menu_email/<int:menu_id>', methods=['POST'])
@login_required
def enviar_menu_email(menu_id):
    menu = Menu.query.get_or_404(menu_id)

    if menu.user_id != current_user.id:
        return "No autorizado", 403

    # Agregar correo y hora actual
    correo_usuario = current_user.email
    hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    extra_info = f"""
    <div style='font-size: 14px; color: #444; margin-bottom: 20px;'>
        <strong>Correo:</strong> {correo_usuario}<br>
        <strong>Fecha y hora de descarga:</strong> {hora_actual}
    </div>
    """

    estilos_pdf = """
        <style>
            body {
                font-family: Arial, sans-serif;
                color: #333;
                padding: 20px;
            }
            .card {
                background-color: #f5f5f5;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 30px;
                page-break-inside: avoid;
            }
            .card-header {
                background-color: #f9d342;
                color: #333;
                font-weight: bold;
                padding: 10px;
                font-size: 18px;
                border-radius: 8px 8px 0 0;
                text-align: center;
            }
            .card img {
                max-width: 100%;
                border-radius: 8px;
                display: block;
                margin: 10px auto;
            }
            .dish-name {
                font-weight: bold;
                margin-top: 10px;
                margin-bottom: 5px;
            }
            .ingredients {
                margin-left: 20px;
                margin-bottom: 15px;
            }
            .ingredients li {
                margin-bottom: 5px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            table, th, td {
                border: 1px solid #ccc;
            }
            th {
                background-color: #27ae60;
                color: white;
                padding: 8px;
                font-size: 14px;
            }
            td {
                padding: 8px;
                font-size: 13px;
            }
        </style>
    """

    html_final = estilos_pdf + extra_info + menu.html_content

    try:
        # Generar el PDF desde HTML con WeasyPrint
        pdf = HTML(string=html_final, base_url=request.host_url).write_pdf()

        # Contenido del correo
        asunto = "📬 Tu menú generado con Diet Planner"
        cuerpo_html = f"""
            <p>Hola <strong>{correo_usuario}</strong>,</p>
            <p>Adjunto encontrarás el PDF de tu menú generado desde la plataforma Diet Planner.</p>
            <p>¡Gracias por confiar en nosotros!</p>
            <p>Saludos,<br><em>El equipo de Diet Planner</em></p>
        """

        enviar_menu_por_correo(
            destinatario=correo_usuario,
            asunto=asunto,
            cuerpo_html=cuerpo_html,
            adjunto_bytes=pdf,
            nombre_adjunto="menu_generado.pdf",
            tipo_mime="application/pdf"
        )

        flash("📧 Menú enviado al correo registrado exitosamente.", "success")
    except Exception as e:
        return f"Error al generar o enviar PDF: {e}", 500

    return redirect(url_for('main.historial_menus'))

@main.route('/descargar_menu_pdf/<int:menu_id>')
@login_required
def descargar_menu_pdf(menu_id):
    menu = Menu.query.get_or_404(menu_id)

    if menu.user_id != current_user.id:
        return "No autorizado", 403

    # Agregar correo y hora actual
    correo_usuario = current_user.email
    hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    extra_info = f"""
    <div style='font-size: 14px; color: #444; margin-bottom: 20px;'>
        <strong>Correo:</strong> {correo_usuario}<br>
        <strong>Fecha y hora de descarga:</strong> {hora_actual}
    </div>
    """

    estilos_pdf = """
        <style>
            body {
                font-family: Arial, sans-serif;
                color: #333;
                padding: 20px;
            }
            .card {
                background-color: #f5f5f5;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 30px;
                page-break-inside: avoid;
            }
            .card-header {
                background-color: #f9d342;
                color: #333;
                font-weight: bold;
                padding: 10px;
                font-size: 18px;
                border-radius: 8px 8px 0 0;
                text-align: center;
            }
            .card img {
                max-width: 100%;
                border-radius: 8px;
                display: block;
                margin: 10px auto;
            }
            .dish-name {
                font-weight: bold;
                margin-top: 10px;
                margin-bottom: 5px;
            }
            .ingredients {
                margin-left: 20px;
                margin-bottom: 15px;
            }
            .ingredients li {
                margin-bottom: 5px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            table, th, td {
                border: 1px solid #ccc;
            }
            th {
                background-color: #27ae60;
                color: white;
                padding: 8px;
                font-size: 14px;
            }
            td {
                padding: 8px;
                font-size: 13px;
            }
        </style>
    """

    # Construcción del HTML final
    html_final = estilos_pdf + extra_info + menu.html_content

    try:
        # Generar el PDF con WeasyPrint
        pdf = HTML(string=html_final, base_url=request.host_url).write_pdf()

        return Response(
            pdf,
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment; filename=menu_generado.pdf'}
        )
    except Exception as e:
        return f"Error al generar PDF: {e}", 500
