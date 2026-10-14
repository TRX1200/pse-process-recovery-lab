"""Bounded physical sequence: Si etch -> ideal mask strip -> Al2O3 ALD."""
from native_lab.schema import ETCH, ALD, validate

HIDDEN = {'surface_profile', 'corrugation_amplitude_nm', 'corrugation_count', 'depth_nm'}
ETCH_KEYS = {f['key'] for f in ETCH} - HIDDEN
ALD_KEYS = {f['key'] for f in ALD} - HIDDEN
FIELDS = [{**f, 'group': 'geometry' if f['group'] == 'geometry' else
           'numerics' if f['group'] == 'numerics' else 'etch'}
          for f in ETCH if f['key'] in ETCH_KEYS]
FIELDS += [{**f, 'group': 'numerics' if f['group'] == 'numerics' else 'ald'}
           for f in ALD if f['key'] in ALD_KEYS - ETCH_KEYS]


def validate_sequence(payload):
    if not isinstance(payload, dict) or set(payload) - {'model', 'params'} or payload.get('model') != 'sequence':
        raise ValueError('Expected sequence model and params only')
    raw = payload.get('params', {})
    keys = ETCH_KEYS | ALD_KEYS
    if not isinstance(raw, dict) or set(raw) - keys:
        raise ValueError('Unknown sequence parameter')
    etch = validate({'model': 'etch', 'params': {k: v for k, v in raw.items() if k in ETCH_KEYS}})
    ald = validate({'model': 'ald', 'params': {k: v for k, v in raw.items() if k in ALD_KEYS}})
    return {'model': 'sequence', 'params': {
        **{k: v for k, v in etch['params'].items() if k in ETCH_KEYS},
        **{k: v for k, v in ald['params'].items() if k in ALD_KEYS - ETCH_KEYS}}}


def split_request(payload):
    request = validate_sequence(payload)
    p = request['params']
    return request, validate({'model': 'etch', 'params': {k: v for k, v in p.items() if k in ETCH_KEYS}}), \
        validate({'model': 'ald', 'params': {k: v for k, v in p.items() if k in ALD_KEYS}})
