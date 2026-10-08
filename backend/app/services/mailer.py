"""메일 발송 — 사내 메일서버에 위임(SMTP + STARTTLS, 2026-10-08).

설정(`SMTP_HOST` 등)은 서버 env 에만 둔다. 호스트가 비어 있으면 발송하지 않고 `None` 을 돌려준다 —
호출 쪽은 지금처럼 링크 복사로 전달한다. 발송 실패가 요청 자체를 실패시키지 않게 예외 대신 결과를 돌려준다.
"""
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

from app.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class MailResult:
    sent: bool | None          # None = 발송 설정 없음
    error: str | None = None


def is_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_from)


def send(to: str, subject: str, body: str) -> MailResult:
    s = get_settings()
    if not is_configured():
        return MailResult(sent=None)
    msg = EmailMessage()
    msg["From"] = formataddr((s.smtp_from_name, s.smtp_from))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        log.warning("메일 발송 실패 to=%s: %s", to, e)
        return MailResult(sent=False, error=_reason(e))
    log.info("메일 발송 to=%s subject=%s", to, subject)
    return MailResult(sent=True)


def _reason(e: Exception) -> str:
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return "메일서버 인증 실패 — 발송 계정 설정을 확인하세요"
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return "받는 주소를 메일서버가 거부했습니다"
    if isinstance(e, OSError) and not isinstance(e, smtplib.SMTPException):
        return "메일서버에 연결할 수 없습니다"
    return "메일 발송 실패"


def _footer() -> str:
    return "\n\n— ICFR 내부회계관리 시스템 (발신 전용 메일입니다)"


def setup_link_mail(to: str, name: str, url: str, invite: bool, hours: int) -> MailResult:
    if invite:
        subject = "[ICFR] 계정 설정 안내"
        lead = "ICFR 내부회계관리 시스템 계정이 만들어졌습니다. 아래 링크에서 비밀번호를 정해 주세요."
    else:
        subject = "[ICFR] 비밀번호 재설정 안내"
        lead = "비밀번호 재설정 링크입니다. 요청하지 않았다면 이 메일을 무시해 주세요(기존 비밀번호는 그대로입니다)."
    body = f"{name} 님,\n\n{lead}\n\n{url}\n\n링크는 {hours}시간 동안 한 번만 쓸 수 있습니다." + _footer()
    return send(to, subject, body)


def invite_mail(to: str, name: str, organization: str, url: str, hours: int) -> MailResult:
    body = (f"{name} 님({organization}),\n\nICFR 내부회계관리 시스템에 초대되었습니다. 아래 링크에서 "
            f"비밀번호 설정·비밀유지 동의·2단계 인증 등록을 마치면 이용할 수 있습니다.\n\n{url}\n\n"
            f"링크는 {hours}시간 동안 한 번만 쓸 수 있습니다." + _footer())
    return send(to, "[ICFR] 외부 사용자 초대 안내", body)


def test_mail(to: str) -> MailResult:
    return send(to, "[ICFR] 메일 발송 시험", "ICFR 메일 발송 설정이 정상입니다." + _footer())
