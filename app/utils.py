from flask_mail import Message
from flask import current_app
from . import mail

def enviar_menu_por_correo(destinatario, asunto, cuerpo_html, adjunto_bytes=None, nombre_adjunto=None, tipo_mime="application/pdf"):
    msg = Message(asunto, recipients=[destinatario])
    msg.html = cuerpo_html

    if adjunto_bytes and nombre_adjunto:
        msg.attach(
            filename=nombre_adjunto,
            content_type=tipo_mime,
            data=adjunto_bytes
        )

    mail.send(msg)
