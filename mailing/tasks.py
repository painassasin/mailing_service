import logging
from datetime import timedelta
from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count
from django.utils import timezone

from mailing.models import Mailing, MailingLog, Status

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def start_mailing():
    now = timezone.now()

    start = now.replace(second=0, microsecond=0)
    end = start + timedelta(minutes=1)

    qs = Mailing.objects.filter(next_run_at__gte=start, next_run_at__lt=end)
    qs = qs.exclude(status=Status.RUNNING)
    qs = qs.annotate(clients_count=Count('clients')).exclude(clients_count=0)

    for mailing in qs.only('id'):
        send_mailing.delay(mailing_id=mailing.id)


@shared_task(ignore_result=True)
def send_mailing(mailing_id: int) -> None:
    mailing = Mailing.objects.select_related('message').get(pk=mailing_id)

    logger.info('Start mailing %s', mailing.id)
    mailing.change_status(status=Status.RUNNING)

    try:
        send_mail(
            subject=mailing.message.subject,
            message=mailing.message.content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=list(mailing.clients.values_list('email', flat=True)),
            fail_silently=False,
        )
    except SMTPException as e:
        MailingLog.log_error(mailing=mailing, error=str(e))
    else:
        MailingLog.log_success(mailing=mailing)
    finally:
        mailing.change_status(status=Status.FINISHED)
        mailing.recalculate_next_time_run()
