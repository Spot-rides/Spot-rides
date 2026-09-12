# Backend Skill

## Purpose
Implement a Django/DRF feature from a task definition.

## Steps

1. Read task from `docs/plans/`.
2. Create or update app: `python manage.py startapp <name>`.
3. Define models in `<app>/models.py` and generate migrations.
4. Write serializer in `<app>/serializers.py`.
5. Write viewset/view in `<app>/views.py`.
6. Register URL under `api/` in `<app>/urls.py` and include in `config/urls.py`.
7. Write pytest tests in `<app>/tests/`.
8. Run `python manage.py check` and `pytest` before marking task complete.
