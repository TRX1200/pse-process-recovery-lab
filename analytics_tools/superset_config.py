"""Local learning instance only; never use these settings on a public server."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT/'local/superset'
credentials = json.loads((PRIVATE/'credentials.json').read_text(encoding='utf-8'))
SECRET_KEY = credentials['secret_key']
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + (PRIVATE/'metadata.sqlite').as_posix()
WTF_CSRF_ENABLED = True
TALISMAN_ENABLED = False  # Loopback HTTP with no external service exposure.
PUBLIC_ROLE_LIKE = 'Public'
# Only an admin can add databases. The preconfigured analytical connection is
# a read-only SQLite file owned by this project, not an uploaded arbitrary URI.
PREVENT_UNSAFE_DB_CONNECTIONS = False
FEATURE_FLAGS = {'DASHBOARD_RBAC': True}
DATA_CACHE_CONFIG = {'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 1}
CACHE_CONFIG = {'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 1}
THUMBNAIL_CACHE_CONFIG = {'CACHE_TYPE': 'NullCache'}
SQLLAB_ASYNC_TIME_LIMIT_SEC = 60
SQLLAB_TIMEOUT = 30
ENABLE_PROXY_FIX = False
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'
