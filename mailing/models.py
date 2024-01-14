from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.db import models
from django.utils import timezone


class Client(models.Model):
    email = models.EmailField(unique=True)
    fio = models.CharField(max_length=255, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email


class Message(models.Model):
    subject = models.CharField(max_length=255)
    content = models.TextField()

    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'

    def __str__(self) -> str:
        return self.subject


class Period(models.IntegerChoices):
    DAILY = 1, 'Daily'
    WEEKLY = 2, 'Weekly'
    MONTHLY = 3, 'Monthly'

    @property
    def as_relative_delta(self) -> relativedelta:
        match self:
            case self.DAILY:
                return relativedelta(days=1)
            case self.WEEKLY:
                return relativedelta(weeks=1)
            case self.MONTHLY:
                return relativedelta(months=1)
            case _:
                raise NotImplementedError


class Status(models.IntegerChoices):
    FINISHED = 1, 'Finished'
    CREATED = 2, 'Created'
    RUNNING = 3, 'Running'


class Mailing(models.Model):
    time = models.TimeField()
    period = models.PositiveSmallIntegerField(choices=Period.choices)
    status = models.PositiveSmallIntegerField(choices=Status.choices, default=Status.CREATED)
    clients = models.ManyToManyField(Client)
    message = models.OneToOneField(Message, on_delete=models.PROTECT, related_name='mailing')
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Mailing'
        verbose_name_plural = 'Mailings'

    def __str__(self) -> str:
        return f'[{self.pk}] {self.get_period_display()} mailing at {self.time}'

    def save(self, *args, **kwargs) -> None:
        self.__set_next_time_run()
        super().save()

    def __set_next_time_run(self):
        now = timezone.now()
        tz_info = timezone.get_current_timezone()

        if not self.id:
            next_date_run = (now + Period(self.period).as_relative_delta).date()
            self.next_run_at = datetime.combine(next_date_run, self.time, tzinfo=tz_info)
        else:
            old_mailing = self.__class__.objects.get(pk=self.id)
            if Period(old_mailing.period) != self.period:
                next_date_run = (now + Period(self.period).as_relative_delta).date()
                self.next_run_at = datetime.combine(next_date_run, old_mailing.time, tzinfo=tz_info)
            if old_mailing.time != self.time:
                next_date_run = self.next_run_at.date()
                self.next_run_at = datetime.combine(next_date_run, self.time, tzinfo=tz_info)

    def change_status(self, status: Status) -> None:
        self.status = status
        self.save(update_fields=['status'])

    def recalculate_next_time_run(self) -> None:
        self.next_run_at += Period(self.period).as_relative_delta
        self.save(update_fields=['next_run_at'])


class MailingLog(models.Model):
    SUCCESS = 0
    FAILED = 1
    STATUS_CHOICES = [(SUCCESS, 'Success'), (FAILED, 'Failed')]

    last_try_at = models.DateTimeField(db_index=True, auto_now_add=True)
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES)
    server_response = models.TextField(null=True, blank=True)
    mailing = models.ForeignKey(Mailing, on_delete=models.CASCADE, related_name='logs')

    class Meta:
        verbose_name = 'Log'
        verbose_name_plural = 'Logs'
        constraints = [
            models.CheckConstraint(
                name='%(app_label)s_%(class)s_not_empty_response_on_failure',
                check=models.Q(status=1, server_response__isnull=False) | ~models.Q(status=1),
            )
        ]

    def __str__(self):
        return f'log-{self.status}-{self.last_try_at}'

    @classmethod
    def log_success(cls, mailing: Mailing) -> None:
        cls.objects.create(status=MailingLog.SUCCESS, mailing=mailing)

    @classmethod
    def log_error(cls, mailing: Mailing, error: str) -> None:
        cls.objects.create(status=MailingLog.FAILED, mailing=mailing, server_response=error)
