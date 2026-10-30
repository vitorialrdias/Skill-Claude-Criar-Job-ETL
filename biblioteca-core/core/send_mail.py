"""Envio de e-mail de erro via SMTP.

credenciais['email'] = {"smtp_host": "...", "smtp_port": 587, "usar_tls": true,
                        "usuario": "...", "senha": "...", "remetente": "...",
                        "destinatarios": ["a@x.com", "b@x.com"]}
Se "habilitado" for false, apenas registra no log.
"""
import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class EmailSender:
    @staticmethod
    def enviar_email(assunto: str, mensagem: str, cfg: dict) -> bool:
        if not cfg or not cfg.get("habilitado", True):
            logger.warning(f"E-mail desabilitado. Assunto: {assunto} | {mensagem}")
            return False
        try:
            msg = EmailMessage()
            msg["Subject"] = assunto
            msg["From"] = cfg.get("remetente", cfg.get("usuario"))
            msg["To"] = ", ".join(cfg["destinatarios"])
            msg.set_content(str(mensagem))
            with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587)), timeout=30) as s:
                if cfg.get("usar_tls", True):
                    s.starttls()
                if cfg.get("usuario"):
                    s.login(cfg["usuario"], cfg["senha"])
                s.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar e-mail '{assunto}': {e}")
            return False
