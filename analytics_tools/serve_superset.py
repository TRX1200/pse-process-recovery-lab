"""Serve the local Superset instance with Waitress on loopback only."""
import os
from analytics_tools.bootstrap_superset import environment
os.environ.update(environment())
from superset.app import create_app
from waitress import serve

if __name__ == '__main__':
    serve(create_app(), host='127.0.0.1', port=8088, threads=4)
