from smtplib import SMTPException
from unittest.mock import call

import pytest
from dateutil.relativedelta import relativedelta
from pytest_mock import MockerFixture

from mailing.models import Client, MailingLog, Period, Status
from mailing.tasks import send_mailing, start_mailing

from .utils import create_daily_mailing, create_mailing


@pytest.fixture()
def client():
    return Client.objects.create(email='test@example.com')


@pytest.fixture()
def mocked_send_mailing_task(mocker: MockerFixture):
    return mocker.patch('mailing.tasks.send_mailing')


@pytest.fixture()
def mocked_send_mail(mocker: MockerFixture):
    return mocker.patch('mailing.tasks.send_mail')


@pytest.fixture()
def mailing_with_client(client):
    mailing = create_mailing()
    mailing.clients.add(client)
    return mailing


@pytest.mark.django_db
@pytest.mark.usefixtures('celery_test_settings')
class TestStartMailingTask:
    @pytest.mark.parametrize(
        'run_at',
        ['2000-01-02 10:00:00.05', '2000-01-02 10:00:00.15', '2000-01-02 10:00:00.25'],
        ids=['early', 'middle', 'later'],
    )
    def test_all_task_at_current_minute_runs(self, freezer, mocked_send_mailing_task, run_at, client):
        mailing_1 = create_daily_mailing(freezer, '2000-01-01 10:00:00.10')
        mailing_2 = create_daily_mailing(freezer, '2000-01-01 10:00:00.20')
        mailing_1.clients.add(client)
        mailing_2.clients.add(client)

        freezer.move_to(run_at)
        start_mailing.delay()

        calls = [call(mailing_id=mailing_1.id), call(mailing_id=mailing_2.id)]
        assert mocked_send_mailing_task.delay.call_count == len(calls)
        mocked_send_mailing_task.delay.assert_has_calls(calls)

    def test_send_mail_with_clients(self, freezer, settings, mocked_send_mail):
        mailing = create_daily_mailing(freezer, '2000-01-01 10:00:00.10')
        mailing.clients.create(email='alice@example.com')
        mailing.clients.create(email='bob@example.com')

        freezer.move_to('2000-01-02 10:00:00')
        start_mailing.delay()

        mocked_send_mail.assert_called_once_with(
            subject=mailing.message.subject,
            message=mailing.message.content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['alice@example.com', 'bob@example.com'],
            fail_silently=False,
        )

    def test_send_mail_without_clients(self, freezer, mocked_send_mail):
        mailing = create_daily_mailing(freezer, '2000-01-01 10:00:00.10')
        mailing.clients.clear()

        freezer.move_to('2000-01-02 10:00:00')
        start_mailing.delay()

        mocked_send_mail.assert_not_called()

    def test_send_mail_only_mailing_with_client(self, freezer, client, mocked_send_mailing_task):
        mailing_with_client = create_daily_mailing(freezer, '2000-01-01 10:00:00.10')
        create_daily_mailing(freezer, '2000-01-01 10:00:00.20')
        mailing_with_client.clients.add(client)

        freezer.move_to('2000-01-02 10:00:00')
        start_mailing.delay()

        mocked_send_mailing_task.delay.assert_called_once_with(mailing_id=mailing_with_client.id)

    @pytest.mark.usefixtures('mocked_send_mailing_task')
    def test_queries_count(self, django_assert_num_queries, freezer, client):
        mailing_1 = create_daily_mailing(freezer, '2000-01-01 10:00:00.10')
        mailing_2 = create_daily_mailing(freezer, '2000-01-01 10:00:00.20')
        mailing_1.clients.add(client)
        mailing_2.clients.add(client)

        freezer.move_to('2000-01-02 10:00:00')
        with django_assert_num_queries(1):
            start_mailing.delay()


@pytest.mark.django_db
@pytest.mark.usefixtures('celery_test_settings', 'mocked_send_mail')
class TestSendMailing:
    def test_change_status_to_finish(self, mailing_with_client):
        send_mailing.delay(mailing_id=mailing_with_client.id)
        mailing_with_client.refresh_from_db()
        assert mailing_with_client.status == Status.FINISHED.value

    def test_send_mail_for_clients_to_finish(self, mailing_with_client, mocked_send_mail):
        send_mailing.delay(mailing_id=mailing_with_client.id)
        mailing_with_client.refresh_from_db()
        mocked_send_mail.assert_called_once()

    def test_log_error(self, mailing_with_client, mocked_send_mail):
        mocked_send_mail.side_effect = SMTPException('Something went wrong')

        send_mailing.delay(mailing_id=mailing_with_client.id)

        mailing_log = MailingLog.objects.get()
        assert mailing_log.status == MailingLog.FAILED
        assert mailing_log.mailing_id == mailing_with_client.id
        assert mailing_log.server_response == 'Something went wrong'

    def test_log_success(self, mailing_with_client):
        send_mailing.delay(mailing_id=mailing_with_client.id)

        mailing_log = MailingLog.objects.get()
        assert mailing_log.status == MailingLog.SUCCESS
        assert mailing_log.mailing_id == mailing_with_client.id
        assert mailing_log.server_response is None

    @pytest.mark.parametrize(
        ['period', 'delta'],
        [
            (Period.DAILY, relativedelta(days=1)),
            (Period.WEEKLY, relativedelta(weeks=1)),
            (Period.MONTHLY, relativedelta(months=1)),
        ],
        ids=['daily', 'weekly', 'monthly'],
    )
    def test_recalculate_next_time_run(self, client, period, delta):
        mailing = create_mailing(period=period)
        mailing.clients.add(client)
        expected_next_time_run = mailing.next_run_at + delta

        send_mailing.delay(mailing_id=mailing.id)

        mailing.refresh_from_db()
        assert mailing.next_run_at == expected_next_time_run
