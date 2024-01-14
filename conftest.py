import pytest


@pytest.fixture()
def celery_test_settings(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
