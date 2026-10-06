"""Durable RF results and an analytical SQLite database for local Superset."""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid
from rf_lab.model import simulate
from native_lab.storage import write_json

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / 'outputs' / 'analytics' / 'lab.sqlite'
CASE_COLUMNS = ['frequency_mhz', 'cp_pf', 'cs_pf', 'density_1e15_m3', 'forward_w',
                'reflected_pct', 'bulk_w', 'coil_loss_w', 'capacitor_loss_w',
                'coil_current_rms_a', 'series_cap_rms_v', 'sheath_rms_v', 'power_residual_w']


def connect(path=WAREHOUSE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript('''
      CREATE TABLE IF NOT EXISTS rf_runs (
        run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, version TEXT NOT NULL,
        source_sha256 TEXT NOT NULL, config_hash TEXT NOT NULL, params_json TEXT NOT NULL,
        evidence TEXT NOT NULL CHECK(evidence='simulation'));
      CREATE TABLE IF NOT EXISTS rf_frequency (
        run_id TEXT REFERENCES rf_runs(run_id), case_name TEXT, frequency_mhz REAL,
        s11_db REAL, reflected_pct REAL, bulk_w REAL);
      CREATE TABLE IF NOT EXISTS process_results (
        source_id TEXT PRIMARY KEY, model TEXT, provenance TEXT, evidence TEXT,
        center_depth_nm REAL, width_half_depth_nm REAL, top_film_nm REAL,
        bottom_film_nm REAL, bottom_top_pct REAL, config_json TEXT);
      CREATE TABLE IF NOT EXISTS rf_coupled_cases (
        run_id TEXT, created_at TEXT, version TEXT, case_name TEXT, status TEXT,
        density_m3 REAL, te_ev REAL, ion_flux_m2_s REAL, bulk_w REAL,
        reflected_pct REAL, coil_loss_w REAL, cp_pf REAL, cs_pf REAL,
        config_hash TEXT, source_sha256 TEXT, rf_json TEXT, gas_json TEXT);
      CREATE TABLE IF NOT EXISTS surface_results (
        source_id TEXT PRIMARY KEY, model TEXT, profile INTEGER, provenance TEXT,
        grid_nm REAL, rays_per_point INTEGER, seed INTEGER, amplitude_nm REAL,
        wavelength_nm REAL, mean_advance_nm REAL, rq_initial_nm REAL, rq_final_nm REAL,
        left_rq_initial_nm REAL, left_rq_final_nm REAL,
        right_rq_initial_nm REAL, right_rq_final_nm REAL, params_json TEXT);
    ''')
    con.execute('CREATE TABLE IF NOT EXISTS rf_cases (run_id TEXT REFERENCES rf_runs(run_id), '
                'case_name TEXT, ' + ', '.join(c+' REAL' for c in CASE_COLUMNS) + ')')
    con.executescript('''
      CREATE VIEW IF NOT EXISTS rf_latest_cases AS SELECT * FROM rf_cases
        WHERE run_id=(SELECT run_id FROM rf_runs ORDER BY created_at DESC, rowid DESC LIMIT 1);
      CREATE VIEW IF NOT EXISTS rf_latest_frequency AS SELECT * FROM rf_frequency
        WHERE run_id=(SELECT run_id FROM rf_runs ORDER BY created_at DESC, rowid DESC LIMIT 1);
      CREATE VIEW IF NOT EXISTS rf_case_history AS
        SELECT r.created_at, r.version, r.evidence,
               json_extract(r.params_json, '$.coil_q') AS coil_q,
               json_extract(r.params_json, '$.capacitor_q') AS capacitor_q, c.*
        FROM rf_cases AS c JOIN rf_runs AS r ON c.run_id=r.run_id;
    ''')
    return con


def persist(result, database=WAREHOUSE):
    now = datetime.now(timezone.utc).isoformat()
    run_id = uuid.uuid4().hex
    source = hashlib.sha256((ROOT/'rf_lab/model.py').read_bytes()).hexdigest()
    with closing(connect(database)) as con, con:
        con.execute('INSERT INTO rf_runs VALUES (?,?,?,?,?,?,?)',
                    (run_id, now, result['version'], source, result['config_hash'],
                     json.dumps(result['params']), 'simulation'))
        rows = [dict(result['manual'], case_name='00 수동 설정',
                     density_1e15_m3=result['params']['density_1e15_m3']), *result['comparison']]
        for row in rows:
            values = [run_id, row['case_name']] + [row.get(k) for k in CASE_COLUMNS]
            con.execute('INSERT INTO rf_cases VALUES ('+','.join('?' for _ in values)+')', values)
        for key, label in [('manual', '수동 설정'), ('matched', '자동 정합')]:
            con.executemany('INSERT INTO rf_frequency VALUES (?,?,?,?,?,?)',
                [(run_id, label, r['frequency_mhz'], r['s11_db'], r['reflected_pct'], r['bulk_w'])
                 for r in result['frequency'][key]])
    return {**result, 'run_id': run_id, 'created_at': now, 'source_sha256': source, 'evidence': 'simulation'}


def run_request(payload, database=WAREHOUSE, output_root=None):
    if not isinstance(payload, dict) or set(payload) != {'params'}:
        raise ValueError('Expected a params object')
    result = persist(simulate(payload['params']), database)
    directory = (Path(output_root) if output_root is not None else ROOT/'outputs/rf_lab')/result['run_id']
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory/'result.json', result)
    return result


def run_coupled(payload, database=WAREHOUSE, output_root=None):
    from rf_lab.coupled import simulate as solve_coupled
    result = solve_coupled(payload)
    run_id, now = uuid.uuid4().hex, datetime.now(timezone.utc).isoformat()
    sources = ['rf_lab/coupled.py','rf_lab/model.py','sim_app/models/etch.py']
    digest = hashlib.sha256(b''.join((ROOT/path).read_bytes() for path in sources)).hexdigest()
    result.update(run_id=run_id, created_at=now, source_sha256=digest)
    directory = (Path(output_root) if output_root is not None else ROOT/'outputs/rf_coupled')/run_id
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory/'result.json',result)
    with closing(connect(database)) as con, con:
        for name,label in [('manual','수동 C · 결합 수지'),('matched','재정합 · 결합 수지')]:
            state = result[name]['selected'] or {}
            circuit = state.get('circuit',{})
            values = (run_id,now,result['version'],label,result[name]['status'],
                      state.get('density_m3'),state.get('te_ev'),state.get('ion_flux_m2_s'),
                      circuit.get('bulk_w'),circuit.get('reflected_pct'),circuit.get('coil_loss_w'),
                      circuit.get('cp_pf'),circuit.get('cs_pf'),result['config_hash'],digest,
                      json.dumps(result['rf_params']),json.dumps(result['gas']))
            con.execute('INSERT INTO rf_coupled_cases VALUES ('+','.join('?' for _ in values)+')',values)
    return result


def import_process_results(database=WAREHOUSE):
    paths = list((ROOT/'outputs/native_lab').glob('*/result.json'))
    paths += list((ROOT/'sim_app/frontend/public/native').glob('*.json'))
    with closing(connect(database)) as con, con:
        for path in paths:
            result = json.loads(path.read_text(encoding='utf-8'))
            if result.get('format') != 'native-feature-run-v1':
                continue
            m = result['frames'][-1]['metrics']
            source_id = path.parent.name if path.name == 'result.json' else path.stem
            con.execute('INSERT OR REPLACE INTO process_results VALUES (?,?,?,?,?,?,?,?,?,?)',
                (source_id, result['model'], 'local run' if path.name == 'result.json' else 'recorded example',
                 'simulation', m.get('center_depth_nm'), m.get('width_half_depth_nm'),
                 m.get('top_film_nm'), m.get('bottom_film_nm'), m.get('bottom_top_pct'),
                 json.dumps(result['params'])))
            p = result['params']
            if p.get('surface_profile',0):
                initial = result['frames'][0]['metrics']
                extent = p['pitch_nm'] if p['surface_profile']==1 else p['depth_nm']
                values = (source_id,result['model'],p['surface_profile'],
                          'local run' if path.name=='result.json' else 'recorded example',
                          p['grid_nm'],p['rays_per_point'],p['seed'],p['corrugation_amplitude_nm'],
                          extent/p['corrugation_count'],m.get('mean_advance_nm',m.get('etch_advance_nm')),
                          initial.get('roughness_rq_nm'),m.get('roughness_rq_nm'),
                          initial.get('left_wall_rq_nm'),m.get('left_wall_rq_nm'),
                          initial.get('right_wall_rq_nm'),m.get('right_wall_rq_nm'),json.dumps(p))
                con.execute('INSERT OR REPLACE INTO surface_results VALUES ('+','.join('?' for _ in values)+')',values)


def recent(database=WAREHOUSE):
    with closing(connect(database)) as con, con:
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute('SELECT run_id,created_at,version,config_hash,evidence FROM rf_runs ORDER BY created_at DESC LIMIT 25')]
    return rows
