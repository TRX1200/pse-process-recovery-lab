"""Separate measured-grid diagnostics and explicitly independent compact circuits."""
import numpy as np
from scipy import ndimage as ndi


def mos_current(vgs, vds, threshold, beta):
    over=max(0.,vgs-threshold); v=max(0.,vds)
    return beta*(over*v-.5*v*v) if v<over else .5*beta*over*over


def copper_path(grid, dx, rho):
    metal=grid==7
    solid=np.argwhere(grid!=0)
    if not len(solid) or not metal.any(): return dict(available=False,connected=False,reason='No Cu / no structure')
    bottom=int(solid[:,2].min()); top=int(solid[:,2].max())
    labels,_=ndi.label(metal,structure=ndi.generate_binary_structure(3,1))
    a=set(np.unique(labels[:,:,bottom]))-{0}; b=set(np.unique(labels[:,:,top]))-{0}
    through=a&b
    if not through: return dict(available=True,connected=False,resistance_ohm=None,reason='No Cu component joins bottom and top planes')
    connected=np.isin(labels,list(through))
    area=connected[:,:,bottom:top+1].sum(axis=(0,1))*(dx*1e-9)**2
    # One-dimensional series-area approximation; no lateral spreading/contact R.
    resistance=float(np.sum(rho*dx*1e-9/area))
    return dict(available=True,connected=True,resistance_ohm=resistance,
                length_nm=(top-bottom+1)*dx,min_area_nm2=float(area.min()/1e-18),
                reason='6-neighbor connectivity; R=sum(rho*dz/Az), no spreading/contact resistance')


def channel_sections(state):
    """Central X cut, active Si components and straight normal gate rays.

    This is a geometry coverage diagnostic, not electrostatic gate control.
    BOX-facing Fin/SOI undersides remain in the denominator deliberately.
    """
    plane=state.g[state.g.shape[0]//2]
    active=(plane==1)&(state.z[None,:]>=state.d['substrate']+state.d['box'])
    labels,count=ndi.label(active,structure=ndi.generate_binary_structure(2,1))
    result=[]
    for component in range(1,count+1):
        cells=np.argwhere(labels==component); faces=0; covered=0
        for y,z in cells:
            for dy,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                yy,zz=y+dy,z+dz
                if 0<=yy<plane.shape[0] and 0<=zz<plane.shape[1] and labels[yy,zz]==component: continue
                faces+=1; dielectric=False
                while 0<=yy<plane.shape[0] and 0<=zz<plane.shape[1]:
                    mat=plane[yy,zz]
                    if mat in (3,4): dielectric=True;yy+=dy;zz+=dz;continue
                    if mat==5 and dielectric:covered+=1
                    break
        result.append(dict(area_nm2=len(cells)*state.dx**2,
                           width_nm=(int(cells[:,0].max())-int(cells[:,0].min())+1)*state.dx,
                           height_nm=(int(cells[:,1].max())-int(cells[:,1].min())+1)*state.dx,
                           gate_normal_coverage_pct=100*covered/max(1,faces)))
    return result


def evaluate(state,p):
    grid=state.g; vdd=p['vdd']; v=np.linspace(0,vdd,81)
    cox=3.9*8.8541878128e-12/(p['eot']*1e-9)
    bn=p['mun']*1e-4*cox*p['W']/p['L']; bp=p['mup']*1e-4*cox*p['W']/p['L']
    output=[]
    for vin in v:
        lo,hi=0.,vdd
        for _ in range(60):
            out=(lo+hi)/2
            n=mos_current(vin,out,p['vtn'],bn)
            q=mos_current(vdd-vin,vdd-out,p['vtp'],bp)
            if n>q: hi=out
            else: lo=out
        output.append((lo+hi)/2)
    if p['fault']=='open': output=[vdd for _ in v]  # explicitly synthetic stuck-high
    if p['fault']=='short': output=[0. for _ in v]  # explicitly synthetic stuck-low
    gate=grid==5; si=grid==1
    neighbor=ndi.binary_dilation(si,structure=ndi.generate_binary_structure(3,1))
    contact=bool(np.any(gate&neighbor))
    checks=[dict(name='TiN–Si 직접 접촉 없음',status='FAIL' if contact else 'PASS' if gate.any() and si.any() else 'N/A',
                 detail='6-neighbor 재료 인접 검사. PASS는 누설 전류·절연 신뢰성 보증이 아닙니다.'),
            dict(name='SiGe 잔류',status='INFO',detail=f'{np.count_nonzero(grid==2)*state.dx**3:g} nm³ — release 의도일 때 확인하세요.'),
            dict(name='Donor / acceptor 주입',status='INFO',detail=f'{state.n.sum()*(state.dx*1e-7)**3:.3g} / {state.p.sum()*(state.dx*1e-7)**3:.3g} expected ions'),
            dict(name='CMOS 논리 0 → 1',status='PASS' if output[0]>.8*vdd else 'FAIL',detail='독립 compact model: Vout > 0.8 VDD'),
            dict(name='CMOS 논리 1 → 0',status='PASS' if output[-1]<.2*vdd else 'FAIL',detail='독립 compact model: Vout < 0.2 VDD')]
    if p['kind']=='tsv': checks=[]
    channels=channel_sections(state) if p['kind']!='tsv' else []
    if channels:
        checks.insert(1,dict(name='중앙 X 채널 / gate 피복',status='INFO',
                      detail=f"{len(channels)} Si sections · normal-ray coverage {min(c['gate_normal_coverage_pct'] for c in channels):.1f}–{max(c['gate_normal_coverage_pct'] for c in channels):.1f}%. BOX 아래 면 포함; 전기적 gate control 아님."))
    path=copper_path(grid,state.dx,p['rho']) if p['kind'] in ('tsv','both') else dict(available=False,connected=False,reason='TSV test not selected')
    if p['kind'] in ('tsv','both'):
        checks.append(dict(name='Cu 관통 연결',status='PASS' if path['connected'] else 'FAIL',detail=path['reason']))
    return dict(checks=checks,copper=path,channel_sections=channels,compact=dict(voltage_v=v.tolist(),
                id_n_uA=[mos_current(x,vdd,p['vtn'],bn)*1e6 for x in v],
                inverter_v=output,parameters=p,origin='Independent long-channel square-law circuit, not extracted device simulation') if p['kind']!='tsv' else None,
                warning='FinFET/GAA의 단채널·양자·3D 전기장은 계산하지 않습니다. IC test는 학습용 구조 검사와 독립 회로 실습입니다.')
