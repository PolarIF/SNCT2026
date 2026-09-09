"""
Configuração do site da SNCT — IFRO Campus Ariquemes.

Tudo que muda entre a máquina de casa e o Railway vem de variável de
ambiente. Nada de senha ou chave escrita aqui dentro.
"""

from pathlib import Path
import os

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Lê o .env quando ele existe (desenvolvimento). No Railway as variáveis já
# chegam pelo ambiente e o arquivo simplesmente não está lá.
load_dotenv(BASE_DIR / ".env")


def env_bool(nome, padrao=False):
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "on", "sim"}


def env_list(nome):
    return [item.strip() for item in os.environ.get(nome, "").split(",") if item.strip()]


# --------------------------------------------------------------------- básico

DEBUG = env_bool("DEBUG", False)

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError(
            "Falta a variável de ambiente SECRET_KEY. "
            "Gere uma com: python -c \"import secrets; print(secrets.token_urlsafe(50))\""
        )
    # Chave fixa só para desenvolvimento, para não invalidar a sessão a cada reinício.
    SECRET_KEY = "django-insecure-apenas-para-desenvolvimento-local"

# Domínios que podem servir a aplicação. O Railway injeta a própria URL em
# RAILWAY_PUBLIC_DOMAIN, então ela entra sozinha na lista.
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS") or [
    "snctifroari.online",
    "www.snctifroari.online",
    "localhost",
    "127.0.0.1",
]

dominio_railway = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if dominio_railway and dominio_railway not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(dominio_railway)

# O POST de um formulário só é aceito vindo destas origens.
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}"
    for host in ALLOWED_HOSTS
    if host not in {"localhost", "127.0.0.1"} and "*" not in host
]

# ----------------------------------------------------------------- aplicações

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "eventos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # O WhiteNoise serve CSS, JS e imagens em produção, sem precisar de nginx.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------- banco

# Em produção o Railway define DATABASE_URL apontando para o PostgreSQL.
# Sem essa variável, cai no SQLite — o suficiente para rodar na própria máquina.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------ sessão e senha

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "painel:entrar"
LOGIN_REDIRECT_URL = "painel:lista"
LOGOUT_REDIRECT_URL = "home"

# Duas semanas: quem cadastra evento não precisa entrar de novo toda hora.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

# --------------------------------------------------------------- idioma e fuso

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Porto_Velho"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------- estáticos

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Em produção, comprime e põe hash no nome do arquivo, para o navegador poder
# cachear para sempre sem servir CSS velho depois de um deploy. Em
# desenvolvimento fica no armazenamento simples, que não exige collectstatic.
STATICFILES_STORAGE_PROD = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STATICFILES_STORAGE_DEV = "django.contrib.staticfiles.storage.StaticFilesStorage"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": STATICFILES_STORAGE_DEV if DEBUG else STATICFILES_STORAGE_PROD,
    },
}

# ------------------------------------------------------------------- segurança

if not DEBUG:
    # O Railway termina o HTTPS antes da aplicação; sem isso o Django acha
    # que a requisição chegou em HTTP e entra em laço de redirecionamento.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
