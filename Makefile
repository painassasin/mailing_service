format:
	isort .
	black .

load_fixtures:
	python3 manage.py loaddata mailing/fixtures/clients.json
	python3 manage.py loaddata mailing/fixtures/messages.json

test:
	pytest . -W ignore::DeprecationWarning
