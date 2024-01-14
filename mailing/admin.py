from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from mailing.models import Client, Mailing, MailingLog, Message


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('email', 'fio')
    search_fields = ('email', 'fio')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'mailing_link')
    search_fields = ('subject',)

    @admin.display(description='Mailing', empty_value='-')
    def mailing_link(self, obj: Message) -> str:
        url = reverse('admin:mailing_mailing_change', args=(obj.mailing.pk,))
        return format_html(f'<a href={url}>link</a>')


class LogsInline(admin.TabularInline):
    model = MailingLog
    extra = 0
    can_delete = False
    readonly_fields = ('last_try_at', 'status', 'server_response')
    ordering = ('-last_try_at',)

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_add_permission(self, request, obj) -> bool:
        return False


@admin.register(Mailing)
class MailingAdmin(admin.ModelAdmin):
    list_display = ('id', 'period', 'status', 'message_link', 'clients_count')
    list_filter = ('period', 'status')
    search_fields = ('message__subject',)
    readonly_fields = ('status', 'last_run_at', 'next_run_at')
    inlines = (LogsInline,)

    @admin.display(description='Clients')
    def clients_count(self, obj: Mailing) -> int:
        return obj.clients.count()

    @admin.display(description='Message', empty_value='-')
    def message_link(self, obj: Mailing) -> str:
        url = reverse('admin:mailing_message_change', args=(obj.pk,))
        return format_html(f'<a href={url}>{obj.message.subject}</a>')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('message')
        qs = qs.prefetch_related('clients')
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'message':
            kwargs['queryset'] = db_field.related_model.objects.filter(mailing__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
