"""Carry the native level sets between two supported physical process models.

Mask removal is an ideal Boolean operation. Surface chemistry is reinitialized;
only geometry/material state is carried. This is not an arbitrary-material TCAD.
"""
import hashlib
import json
import time
from pathlib import Path

from native_lab.engine import initialize, make_domain, evolve, capture, environment
from native_lab.geometry import intersections
from native_lab.sequence_schema import split_request
from native_lab.storage import write_json

VERSION = 'native-sequence-0.1.0'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def simulate(payload, output_dir=None, progress=None):
    request, etch_request, ald_request = split_request(payload)
    initialize()
    started = time.perf_counter()
    domain = make_domain(etch_request)
    root = Path(output_dir) if output_dir else None

    def directory(name):
        if root is None:
            return None
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def report(stage, fraction, frame):
        if progress:
            progress(fraction, {**frame, 'stage': stage})

    etch = evolve(etch_request, domain, directory('01_etch'),
                  lambda f, frame: report('etch', .5*f, frame))
    # MakeTrench stores Mask FIRST, wrapped by the Si level set. Removing the
    # top level set would delete Si. removeWrapped=True subtracts mask volume.
    materials = [layer['material'] for layer in etch['frames'][-1]['layers']]
    if materials != ['Mask', 'Si']:
        raise ValueError(f'Unsupported material stack for sequence: {materials}')
    domain.removeLevelSet(0, True)
    stripped = capture(domain, ['Si'], 'etch', etch_request['params'], 0, 'ideal_mask_strip')
    stripped['metrics'].pop('mask_loss_nm', None)
    contour = stripped['layers'][0]['paths_nm']
    depth = max(0, -max(intersections(contour, 0, 0)))
    # Depth is derived, not a user-imposed replacement geometry. It may be below
    # the standalone-trench input minimum, including zero for a no-etch run.
    ald_request['params']['depth_nm'] = depth
    import viennaps as ps
    domain.duplicateTopLevelSet(ps.Material.Al2O3)
    report('strip', .5, stripped)
    ald = evolve(ald_request, domain, directory('03_ald'),
                 lambda f, frame: report('ald', .5+.5*f, frame))
    ald['numerics']['initial_geometry'] = 'same native domain after etch and ideal mask strip'
    # A geometry-dependent identity is required: different etch histories can
    # produce the same centre depth but different ALD transport boundaries.
    handoff_hash = digest(stripped['layers'])
    ald['run_hash'] = digest({'base': ald['run_hash'], 'handoff': handoff_hash})
    assumptions = [
        'Si/SF6-O2 etch and TMA-limited Al2O3 ALD use ViennaPS transport, coverage and level-set evolution.',
        'Mask strip is instantaneous Boolean removal, with no wet chemistry, selectivity or substrate damage.',
        'The same native level-set domain is retained. No rectangular reconstruction, smoothing or invented roughness.',
        'Only geometry/material interfaces carry over. Surface termination, native oxide, residues and nucleation delay do not.',
        'The RF circuit/plasma reactor is not coupled; incident flux/energy remain boundary inputs.',
        'This is a 2D feature sequence, not a calibrated equipment model or an electrical transistor simulation.',
    ]
    identity = {'request': request, 'version': VERSION, 'environment': environment(),
                'source_sha256': {name: hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                                  for name in ('sequence.py', 'engine.py', 'geometry.py', 'schema.py', 'sequence_schema.py')}}
    result = {'format': 'native-sequence-run-v1', 'model': 'sequence', 'implementation': VERSION,
              'run_hash': digest(identity), **identity, 'etch': etch, 'strip': stripped, 'ald': ald,
              'handoff': {'geometry_sha256': handoff_hash,
                          'si_contour_preserved': contour == ald['frames'][0]['layers'][0]['paths_nm'],
                          'derived_depth_nm': depth},
              'elapsed_s': time.perf_counter()-started, 'assumptions': assumptions,
              'warnings': etch['warnings'] + ald['warnings'],
              'validation': {'physical_calibration': 'not_performed', 'equipment_match': 'not_established'}}
    if not result['handoff']['si_contour_preserved']:
        raise RuntimeError('ALD initial Si interface differs from stripped etch result')
    if root:
        write_json(root/'02_strip.json', stripped)
    json.dumps(result, allow_nan=False)
    return result
