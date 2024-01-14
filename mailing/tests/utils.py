from django.utils import timezone

from mailing.models import Mailing, Message, Period


def create_daily_mailing(freezer, datetime_at: str) -> Mailing:
    freezer.move_to(datetime_at)
    return create_mailing(period=Period.DAILY)


def create_mailing(*, period: Period = Period.DAILY) -> Mailing:
    message = Message.objects.create(subject='test subject', content='test content')
    now = timezone.now()
    return Mailing.objects.create(message=message, time=now.time(), period=period)
