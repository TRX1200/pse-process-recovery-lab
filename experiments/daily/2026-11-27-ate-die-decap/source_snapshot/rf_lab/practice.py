"""Reproducible slow load fluctuations with quasi-static RMS circuit solves."""
import math
from numbers import Real
import numpy as np
from rf_lab.model import point, validate


def bounded(inputs, key, default, low, high, integer=False):
    value = inputs.get(key, default)
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f'{key}: finite number required')
    if not low <= value <= high or (integer and int(value) != value):
        raise ValueError(f'{key}: expected {low}..{high}')
    return int(value) if integer else float(value)


def strict_dict(raw, keys):
    if not isinstance(raw, dict) or set(raw) - set(keys):
        raise ValueError('Invalid input fields')


def simulate(raw):
    strict_dict(raw, ['seed','sigma','tau_s','base_density','cp_pf','cs_pf','power_w','schedule'])
    seed = bounded(raw,'seed',42,0,2**31-1,True)
    sigma = bounded(raw,'sigma',0.18,0,0.6)
    tau = bounded(raw,'tau_s',1.4,0.1,10)
    density = bounded(raw,'base_density',20,1,50)
    cp = bounded(raw,'cp_pf',500,10,3000)
    cs = bounded(raw,'cs_pf',120,10,3000)
    power = bounded(raw,'power_w',300,0,2000)
    # Manual actions are latched at 0.1 s sample boundaries; no look-ahead controller.
    actions = raw.get('schedule',[])
    if not isinstance(actions,list) or len(actions)>40:
        raise ValueError('At most 40 tuning events')
    schedule = {}
    for event in actions:
        strict_dict(event,['tick','cp_pf','cs_pf'])
        if set(event)!={'tick','cp_pf','cs_pf'}:
            raise ValueError('Incomplete tuning event')
        tick = bounded(event,'tick',0,1,200,True)
        if tick in schedule:
            raise ValueError('Duplicate tuning time')
        schedule[tick] = (bounded(event,'cp_pf',cp,10,3000),bounded(event,'cs_pf',cs,10,3000))
    rng=np.random.default_rng(seed)
    dt=0.1
    a=math.exp(-dt/tau)
    gain=math.sqrt(-math.expm1(-2*dt/tau))
    x=y=0.0
    p=validate({'density_1e15_m3':density,'forward_w':power,'cp_pf':cp,'cs_pf':cs})
    cp0,cs0=cp,cs
    rows=[]
    for k in range(201):
        if k:
            u,v=rng.standard_normal(2)
            x=a*x+gain*u
            y=a*y+gain*v
        # Log fluctuations: positive multiplicative density and weakly anti-correlated
        # sheath thickness. Coefficients are synthetic scenario parameters, not fitted.
        state={**p,'density_1e15_m3':density*math.exp(sigma*x),
               'sheath_total_mm':p['sheath_total_mm']*math.exp(sigma*(-0.35*x+0.15*y))}
        cp,cs=schedule.get(k,(cp,cs))
        r=point(state,cp_pf=cp,cs_pf=cs)
        reference=point(state,cp_pf=cp0,cs_pf=cs0) if (cp,cs)!=(cp0,cs0) else r
        rows.append(dict(t_s=k*dt,cp_pf=cp,cs_pf=cs,density_1e15_m3=state['density_1e15_m3'],
                         sheath_mm=state['sheath_total_mm'],load_r_ohm=r['z_load'][0],load_x_ohm=r['z_load'][1],
                         reflected_pct=r['reflected_pct'],fixed_pct=reference['reflected_pct'],
                         reflected_w=r['reflected_w'],bulk_w=r['bulk_w'],coil_loss_w=r['coil_loss_w'],
                         capacitor_loss_w=r['capacitor_loss_w'],power_residual_w=r['power_residual_w']))
    return dict(model='manual-stochastic-match-v1',dt_s=dt,seed=seed,rows=rows,
                config=dict(seed=seed,sigma=sigma,tau_s=tau,base_density=density,cp_pf=cp0,
                            cs_pf=cs0,power_w=power,schedule=[dict(tick=k,cp_pf=c,cs_pf=s) for k,(c,s) in sorted(schedule.items())]),
                circuit_inputs=p,mean_reflected_pct=float(np.mean([r['reflected_pct'] for r in rows])),
                mean_fixed_pct=float(np.mean([r['fixed_pct'] for r in rows])))
