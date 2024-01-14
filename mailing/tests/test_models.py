import pytest
from django.utils import timezone

from mailing.models import Period

from .utils import create_daily_mailing, create_mailing


@pytest.mark.django_db
class TestMailingModel:
    def test_initial_daily_mailing(self, freezer):
        freezer.move_to('2000-01-01 10:00:00')

        mailing = create_mailing(period=Period.DAILY)

        assert mailing.last_run_at is None
        assert mailing.next_run_at.isoformat() == '2000-01-02T10:00:00+00:00'

    def test_initial_weekly_mailing(self, freezer):
        freezer.move_to('2000-01-01 10:00:00')

        mailing = create_mailing(period=Period.WEEKLY)

        assert mailing.last_run_at is None
        assert mailing.next_run_at.isoformat() == '2000-01-08T10:00:00+00:00'

    def test_initial_monthly_mailing(self, freezer):
        freezer.move_to('2000-01-01 10:00:00')

        mailing = create_mailing(period=Period.MONTHLY)

        assert mailing.last_run_at is None
        assert mailing.next_run_at.isoformat() == '2000-02-01T10:00:00+00:00'

    def test_change_period_for_already_existing_mailing(self, freezer):
        mailing = create_daily_mailing(freezer, '2000-01-01 10:00:00')
        freezer.move_to('2000-01-02 12:00:00')

        mailing.period = Period.WEEKLY
        mailing.save()

        assert mailing.next_run_at.isoformat() == '2000-01-09T10:00:00+00:00'

    def test_change_time_for_already_existing_mailing(self, freezer):
        mailing = create_daily_mailing(freezer, '2000-01-01 10:00:00')
        freezer.move_to('2000-01-02 09:00:00')

        mailing.time = timezone.now().time()
        mailing.save()

        assert mailing.next_run_at.isoformat() == '2000-01-02T09:00:00+00:00'
