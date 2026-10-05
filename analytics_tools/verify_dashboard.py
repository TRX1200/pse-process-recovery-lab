"""Reconcile live, anonymous Superset chart responses with the source SQLite DB."""
import json
import math
from pathlib import Path
import sqlite3
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    with sqlite3.connect(ROOT/'local/superset/metadata.sqlite') as metadata:
        charts = metadata.execute(
            "SELECT id, slice_name, datasource_name FROM slices "
            "WHERE slice_name LIKE 'RF · %' OR slice_name LIKE 'ALD / Etch · %'"
        ).fetchall()
    assert len(charts) == 5, f'Expected five provisioned charts, got {len(charts)}'
    with sqlite3.connect(ROOT/'outputs/analytics/lab.sqlite') as source:
        source.row_factory = sqlite3.Row
        expected_cases = {r['case_name']: dict(r) for r in source.execute('SELECT * FROM rf_latest_cases')}
        expected_frequency = {(r['frequency_mhz'], r['case_name']): r['bulk_w'] for r in source.execute('SELECT * FROM rf_latest_frequency')}
        assert len(expected_cases) == 4 and len(expected_frequency) == 362
        for chart_id, title, dataset in charts:
            with urlopen(f'http://127.0.0.1:8088/api/v1/chart/{chart_id}/data/?force=true', timeout=30) as response:
                payload = json.load(response)['result'][0]
            assert payload['status'] == 'success', (title, payload.get('error'))
            assert not payload.get('error') and payload['data'], title
            if dataset == 'rf_latest_cases':
                assert len(payload['data']) == 4
                mapping = {'Reflected / %':'reflected_pct', 'Bulk / W':'bulk_w',
                           'Coil loss / W':'coil_loss_w', 'Cap loss / W':'capacitor_loss_w'}
                for row in payload['data']:
                    for label, column in mapping.items():
                        if label in row:
                            assert math.isclose(row[label], expected_cases[row['case_name']][column], rel_tol=1e-10, abs_tol=1e-12)
            elif dataset == 'rf_latest_frequency':
                assert len(payload['data']) == 362
                for row in payload['data']:
                    assert math.isclose(row['Bulk / W'], expected_frequency[(row['frequency_mhz'], row['case_name'])], rel_tol=1e-10, abs_tol=1e-12)
            else:
                # Only the two fixed datasets provisioned by this module are queried.
                assert dataset in ('rf_case_history', 'process_results')
                count = source.execute(f'SELECT COUNT(*) FROM {dataset}').fetchone()[0]
                assert len(payload['data']) == min(count, 1000)
            print(f'PASS: chart {chart_id}, {dataset}, {len(payload["data"])} rows')
    print('Live Superset queries reconcile with the simulation source database.')


if __name__ == '__main__':
    main()
