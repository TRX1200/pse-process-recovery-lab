"""Initialize the genuine Apache Superset package in its isolated environment."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT/'local/superset'


def environment():
    return {**os.environ, 'SUPERSET_CONFIG_PATH': str(ROOT/'analytics_tools/superset_config.py'),
            'SUPERSET_HOME': str(PRIVATE), 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
            'FLASK_APP': 'superset'}


def main():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    path = PRIVATE/'credentials.json'
    if not path.exists():
        path.write_text(json.dumps({'username': 'lab_admin', 'password': secrets.token_urlsafe(24),
                                   'secret_key': secrets.token_urlsafe(64)}), encoding='utf-8')
    os.environ.update(environment())
    cli = Path(sys.executable).with_name('superset.exe' if os.name == 'nt' else 'superset')
    subprocess.run([str(cli), 'db', 'upgrade'], check=True, env=environment())
    subprocess.run([str(cli), 'init'], check=True, env=environment())
    from superset.app import create_app
    from superset import security_manager
    app = create_app()
    with app.app_context():
        creds = json.loads(path.read_text(encoding='utf-8'))
        if not security_manager.find_user(username=creds['username']):
            security_manager.add_user(username=creds['username'], first_name='Process', last_name='Lab',
                email='lab-admin@localhost.invalid', role=security_manager.find_role('Admin'), password=creds['password'])
    print('Superset initialized. Private admin credentials: local/superset/credentials.json')


if __name__ == '__main__':
    main()
