"""Execute the fixed A/B plan using the bundled, unchanged model snapshot."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import gzip
import hashlib
import json
import platform
import sys
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source_snapshot'))
import numpy as np
import scipy
from fab_lab.ate import simulate, line_response


def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def stimulus(config):
    rng=np.random.default_rng(config['seed'])
    bits=rng.integers(0,2,256)
    boundaries=(np.arange(1,256)+rng.uniform(-config['jitter_ui'],config['jitter_ui'],255))/config['rate_gbps']
    return bits,boundaries


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit('Choose an empty output directory; existing artifacts are preserved.')
    out.mkdir(parents=True,exist_ok=True)
    plan=json.loads((HERE/'plan.json').read_text(encoding='utf-8'))
    for path,expected in plan['source_sha256'].items():
        assert hashlib.sha256((HERE/'source_snapshot'/path).read_bytes()).hexdigest()==expected,path
    a_config,b_config=plan['conditions']['A'],plan['conditions']['B']
    assert {k for k in a_config if a_config[k]!=b_config[k]}=={'rise_ps'}
    started=datetime.now(timezone.utc).isoformat()
    captures={case:simulate(config) for case,config in plan['conditions'].items()}
    for case,config in plan['conditions'].items():
        assert captures[case]==simulate(config),'Exact seeded replay'
    bits,boundaries=stimulus(a_config)
    bits_b,boundaries_b=stimulus(b_config)
    assert np.array_equal(bits,bits_b) and np.array_equal(boundaries,boundaries_b)
    assert captures['A']['x']==captures['B']['x']
    ui_ns=1/a_config['rate_gbps'];dt_ns=ui_ns/64
    delays=[round(length/160/dt_ns) for length in (24,8)]
    offset=sum(delays)
    indices=np.arange(16,(256*64-offset-2*64-1)//64+1)
    levels=bits[indices]
    metrics={};sample_records=[];envelope_records=[]
    for case,capture in captures.items():
        rows=np.asarray(capture['traces']);x=np.asarray(capture['x'])
        assert rows.shape==(len(indices),129)
        assert np.isfinite(rows).all() and np.isfinite(x).all()
        np.testing.assert_allclose(np.diff(x),1/64,rtol=0,atol=1e-15)
        sample_index=round(capture['config']['strobe_ui']*64)
        samples=rows[:,sample_index];threshold=capture['config']['threshold_v']
        high=samples[levels==1];low=samples[levels==0]
        opening=float(high.min()-low.max())
        signed=np.where(levels==1,samples-threshold,threshold-samples)
        mismatch=int(np.count_nonzero((samples>=threshold)!=levels))
        assert abs(opening-capture['reading']['중앙 수직 여유 (V)'])<1e-12
        assert mismatch==capture['reading']['패턴 불일치 (bit)']
        assert len(indices)==capture['reading']['검사한 비트']
        metrics[case]=dict(rise_ps=capture['config']['rise_ps'],opening_v=opening,
            min_one_v=float(high.min()),max_zero_v=float(low.max()),
            worst_threshold_margin_v=float(signed.min()),finite_pattern_mismatches=mismatch,
            sampled_bits=len(indices),ui_ps=ui_ns*1000,dt_ps=dt_ns*1000,
            alignment_delay_ps=offset*dt_ns*1000,
            nominal_source_bandwidth_ghz=float(np.log(9)/(2*np.pi*capture['config']['rise_ps']*.001)))
        for bit_index,bit,value,margin in zip(indices,levels,samples,signed):
            sample_records.append(dict(case=case,bit_index=int(bit_index),expected_bit=int(bit),
                sample_v=float(value),threshold_v=threshold,signed_margin_v=float(margin)))
        for phase_index in range(65):
            one=rows[levels==1,phase_index];zero=rows[levels==0,phase_index]
            envelope_records.append(dict(case=case,phase_ui=float(x[phase_index]),
                min_one_v=float(one.min()),max_zero_v=float(zero.max()),opening_v=float(one.min()-zero.max())))

    # Independent known limit: a matched, lossless line reproduces a delayed half-amplitude source.
    source=np.zeros(1200);source[20:300]=2;source[600:900]=1
    near,far,known_delays=line_response(source,dt_ns,(24,8),(50,50),50,50)
    expected=np.zeros_like(source);flight=sum(known_delays);expected[flight:]=source[:-flight]/2
    np.testing.assert_allclose(near,source/2,rtol=0,atol=1e-12)
    np.testing.assert_allclose(far,expected,rtol=0,atol=1e-12)
    ideal=simulate({**a_config,'package_z':50,'rise_ps':5,'jitter_ui':0})
    assert ideal['reading']['중앙 수직 여유 (V)']>.99
    assert ideal['reading']['패턴 불일치 (bit)']==0
    invalid_threshold=simulate({**a_config,'threshold_v':1.9})
    assert invalid_threshold['reading']['패턴 불일치 (bit)']>0
    assert invalid_threshold['traces']==captures['A']['traces'],'Threshold must not change analog waveforms'
    checks=dict(source_hashes='PASS',single_parameter_change='PASS',exact_seed_replay='PASS',
        identical_source_bits_and_jitter='PASS',identical_time_axis='PASS',shape_and_finite_values='PASS',
        independent_metric_recalculation='PASS',matched_line_delay_and_amplitude='PASS',
        ideal_eye_control='PASS',threshold_only_negative_control='PASS',
        matched_line_max_abs_error_v=float(np.max(np.abs(far-expected))),
        ideal_eye_opening_v=ideal['reading']['중앙 수직 여유 (V)'],
        negative_control_mismatches=invalid_threshold['reading']['패턴 불일치 (bit)'],
        sample_rate_convergence='NOT_RUN: model fixes 64 samples/UI; not modified in this experiment',
        seed_ensemble='NOT_RUN: one seed',physical_validation='NOT_PERFORMED',statistical_ber='NOT_ESTIMATED')
    summary=dict(cases=metrics,delta_B_minus_A={k:metrics['B'][k]-metrics['A'][k]
        for k in ['opening_v','worst_threshold_margin_v','finite_pattern_mismatches']})
    result=dict(experiment_id=plan['experiment_id'],execution_id=uuid.uuid4().hex,server_job_id=None,
        execution_note='Direct Python function execution; generated execution_id is not a server job ID.',
        started_at_utc=started,finished_at_utc=datetime.now(timezone.utc).isoformat(),
        environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        cases={k:{key:value for key,value in capture.items() if key not in ('traces','x')} for k,capture in captures.items()},
        raw_captures='captures.json.gz: gzip-compressed full JSON returned by the model, including every x and trace sample',
        numerical_sampling=dict(samples_per_ui=64,source_bits=256,retained_bits=len(indices),
            ui_ps=ui_ns*1000,dt_ps=dt_ns*1000,line_delay_samples=delays,
            actual_alignment_ps=offset*dt_ns*1000,physical_nominal_flight_ps=200),
        summary=summary,checks=checks)
    raw=json.dumps(captures,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
    (out/'captures.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    assert json.loads(gzip.decompress((out/'captures.json.gz').read_bytes()))==captures
    dump(out/'result.json',result);dump(out/'summary.json',summary);dump(out/'checks.json',checks)
    dump(out/'stimulus.json',dict(seed=42,bits=bits.tolist(),boundary_time_ns=boundaries.tolist(),
        retained_source_indices=indices.tolist(),note='Reconstructed with the exact RNG call order in the frozen model.'))
    for filename,records in [('decision_samples.csv',sample_records),('phase_envelopes.csv',envelope_records)]:
        with (out/filename).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    print(json.dumps(dict(execution_id=result['execution_id'],summary=summary,checks=checks),indent=2,ensure_ascii=False))


if __name__=='__main__':main()
