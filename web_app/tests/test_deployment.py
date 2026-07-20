from pathlib import Path
from unittest import TestCase

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class DefaultDeploymentTests(TestCase):
    def test_container_is_fastapi_only(self):
        dockerfile = (REPOSITORY_ROOT / "web_app" / "Dockerfile").read_text()

        self.assertIn('CMD ["uvicorn", "cotour_web.app:app"', dockerfile)
        self.assertIn('"--no-access-log"', dockerfile)
        self.assertIn("http://127.0.0.1:8000/health/ready", dockerfile)
        for retired in ("gunicorn", "manage.py", "collectstatic", "DJANGO_"):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, dockerfile)

    def test_compose_exposes_only_fastapi(self):
        compose = yaml.safe_load(
            (REPOSITORY_ROOT / "docker-compose.yml").read_text()
        )
        self.assertEqual(set(compose["services"]), {"web"})
        web = compose["services"]["web"]

        self.assertIn("FASTAPI_ALLOWED_HOSTS", web["environment"])
        self.assertNotIn("DJANGO_SECRET_KEY", web["environment"])

    def test_retired_framework_is_absent_from_deployed_application(self):
        web_directory = REPOSITORY_ROOT / "web_app"
        self.assertFalse((web_directory / "manage.py").exists())
        self.assertFalse((web_directory / "web_app").exists())
        self.assertFalse((web_directory / "webapp").exists())

        requirements = (web_directory / "requirements.in").read_text().lower()
        for retired in ("django", "folium", "gunicorn", "whitenoise", "geopy"):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, requirements)
        self.assertIn("jinja2", requirements)
        self.assertIn("pyyaml", requirements)
