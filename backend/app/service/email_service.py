"""
邮件服务 — 通过腾讯 QQ 邮箱 SMTP 发送 OTP 验证码

配置说明（backend/.env）：
    SMTP_USER=QQ号@qq.com
    SMTP_PASSWORD=邮箱授权码（QQ邮箱→设置→账户→POP3/SMTP→生成授权码）
    SMTP_HOST=smtp.qq.com
    SMTP_PORT=587          ← 推荐 587 (STARTTLS)，465 (SSL) 在部分系统会握手超时
"""

import ssl
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings

logger = logging.getLogger(__name__)


def _build_message(to_email: str, otp: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Woloong AI 验证码：{otp}"
    msg["From"]    = f"{settings.smtp_from_name} <{settings.smtp_user}>"
    msg["To"]      = to_email

    html_body = f"""
    <html>
    <body>
    <div style="font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
                max-width: 480px; margin: 0 auto; padding: 32px 24px;
                background: #fff; border-radius: 12px;">
        <div style="font-size: 22px; font-weight: 700; color: #D97706; margin-bottom: 24px;">
            &#9889; Woloong AI
        </div>
        <p style="color: #444; font-size: 15px; margin-bottom: 8px;">您好！</p>
        <p style="color: #444; font-size: 15px; margin-bottom: 24px;">
            您的注册验证码是（10 分钟内有效）：
        </p>
        <div style="display: inline-block; background: #FEF3C7;
                    border: 2px solid #D97706; border-radius: 8px;
                    padding: 16px 40px; margin-bottom: 24px;">
            <span style="font-size: 40px; font-weight: 800;
                         letter-spacing: 12px; color: #92400E;">
                {otp}
            </span>
        </div>
        <p style="color: #888; font-size: 13px; line-height: 1.6;">
            请勿将验证码告知任何人。<br>
            如非本人操作，请忽略此邮件。
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
        <p style="color: #bbb; font-size: 12px;">Woloong AI — AI 品牌咨询平台</p>
    </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def _try_starttls(msg: MIMEMultipart, to_email: str) -> None:
    """尝试 STARTTLS 方式（587 端口）"""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with smtplib.SMTP(settings.smtp_host, 587, timeout=20) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.ehlo()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, [to_email], msg.as_string())


def _try_ssl(msg: MIMEMultipart, to_email: str) -> None:
    """备用：直连 SSL 方式（465 端口）"""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with smtplib.SMTP_SSL(settings.smtp_host, 465, context=ctx, timeout=20) as server:
        server.ehlo()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, [to_email], msg.as_string())


def send_otp_email(to_email: str, otp: str) -> None:
    """
    发送 OTP 验证码邮件。
    优先尝试 STARTTLS(587)，失败后自动回退到 SSL(465)。
    未配置 SMTP 时打印到终端（开发模式）。
    """
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP 未配置 — 开发模式，验证码打印到终端")
        print(f"\n{'='*44}")
        print(f"  [DEV] OTP for {to_email}: {otp}")
        print(f"{'='*44}\n", flush=True)
        return

    msg = _build_message(to_email, otp)

    # 优先用 STARTTLS(587)
    try:
        _try_starttls(msg, to_email)
        logger.info("OTP 邮件发送成功 (STARTTLS): to=%s", to_email)
        return
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP 授权码错误")
        raise ValueError("邮箱授权码错误，请重新生成后配置")
    except Exception as e:
        logger.warning("STARTTLS 发送失败，尝试 SSL: %s", str(e))

    # 回退：SSL(465)
    try:
        _try_ssl(msg, to_email)
        logger.info("OTP 邮件发送成功 (SSL): to=%s", to_email)
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP 授权码错误")
        raise ValueError("邮箱授权码错误，请重新生成后配置")
    except Exception as e:
        logger.error("邮件发送最终失败: %s", str(e))
        raise ValueError(f"邮件发送失败，请检查网络或稍后重试（{str(e)}）")
