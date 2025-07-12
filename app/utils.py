from flask_mail import Message
from flask import current_app
from . import mail

def enviar_menu_por_correo(destinatario, asunto, cuerpo_html, adjunto_bytes=None, nombre_adjunto="menu_generado.pdf"):
    msg = Message(asunto, recipients=[destinatario])
    msg.html = cuerpo_html

    if adjunto_bytes:
        msg.attach(
            filename=nombre_adjunto,
            content_type="application/pdf",  # ✅ forzar envío como PDF
            data=adjunto_bytes
        )

    mail.send(msg)
