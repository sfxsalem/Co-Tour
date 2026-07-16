from pathlib import Path
from unittest import TestCase

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class DefaultDeploymentTests(TestCase):
    def test_container_defaults_to_fastapi(self):
        dockerfile = (REPOSITORY_ROOT / "web_app" / "Dockerfile").read_text()

        self.assertIn('CMD ["uvicorn", "cotour_web.app:app"', dockerfile)
        self.assertNotIn('CMD ["gunicorn"', dockerfile)

    def test_compose_exposes_fastapi_as_web_and_django_as_rollback(self):
        compose = yaml.safe_load(
            (REPOSITORY_ROOT / "docker-compose.yml").read_text()
        )
        web = compose["services"]["web"]
        django = compose["services"]["django"]

        self.assertIn("FASTAPI_ALLOWED_HOSTS", web["environment"])
        self.assertNotIn("DJANGO_SECRET_KEY", web["environment"])
        self.assertEqual(django["profiles"], ["rollback"])
        self.assertIn("web_app.wsgi:application", django["command"])
