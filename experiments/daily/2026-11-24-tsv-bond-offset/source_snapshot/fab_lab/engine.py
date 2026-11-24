"""Exclusive material voxels [x,y,z], z upward. No periodic boundaries.

All geometry is nm; impurity fields cm^-3. This is a grid morphology / reduced
physics model, not a drift-diffusion device solver or a calibrated fab model.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import scipy
from scipy import ndimage as ndi
from scipy.special import ndtr
from fab_lab.schema import MATERIALS, validate

IDS = {m['name']: m['id'] for m in MATERIALS}
SIX = ndi.generate_binary_structure(3, 1)
VERSION = 'fab-grid-v1'


def rle(values):
    a = np.asarray(values).ravel(order='C')
    starts = np.r_[0, np.flatnonzero(a[1:] != a[:-1])+1]
    return np.column_stack((a[starts], np.diff(np.r_[starts, len(a)]))).ravel().astype(int).tolist()


def accessible(grid):
    empty = grid == 0
    seed = np.zeros_like(empty)
    seed[:, :, -1] = empty[:, :, -1]
    return ndi.binary_propagation(seed, structure=SIX, mask=empty)


def diffusion_step(c, silicon, coefficient):
    """Conservative face flux, dimensionless coefficient D*dt/dx^2 <= 1/6."""
    out = c.copy()
    for axis in range(3):
        left = [slice(None)]*3; right = [slice(None)]*3
        left[axis] = slice(None, -1); right[axis] = slice(1, None)
        a, b = tuple(left), tuple(right)
        flux = coefficient*(c[b]-c[a])*(silicon[a] & silicon[b])
        out[a] += flux; out[b] -= flux
    return out


class State:
    def __init__(self, domain):
        self.d = domain; self.dx = domain['dx']
        shape = tuple(domain[k] for k in ('nx','ny','nz'))
        self.g = np.zeros(shape, dtype=np.uint8)
        self.n = np.zeros(shape); self.p = np.zeros(shape)
        self.an = np.zeros(shape); self.ap = np.zeros(shape)
        self.mask = np.ones(shape[:2], dtype=bool)
        self.x = (np.arange(shape[0])+.5-shape[0]/2)*self.dx
        self.y = (np.arange(shape[1])+.5-shape[1]/2)*self.dx
        self.z = (np.arange(shape[2])+.5)*self.dx
        a,b,c = domain['substrate'],domain['box'],domain['active']
        self.g[:,:,self.z<a] = IDS['Si']
        self.g[:,:,(self.z>=a)&(self.z<a+b)] = IDS['SiO2']
        self.g[:,:,(self.z>=a+b)&(self.z<a+b+c)] = IDS['Si']
        self.warnings = []; self.notes = {}; self.test = None

    def cells(self, distance):
        # Nearest-cell representation; disclose resolution instead of forcing a cell.
        return max(0, int(math.floor(distance/self.dx+.5)))

    def set_mask(self, p):
        x=self.x[:,None]-p['cx']; y=self.y[None,:]-p['cy']
        lanes = np.zeros((len(self.x), len(self.y)), dtype=bool)
        for i in range(p['count']):
            lanes |= np.abs(y-(i-(p['count']-1)/2)*p['pitch']) < p['length']/2
        kind=p['pattern']
        if kind=='all': m=np.ones_like(lanes)
        elif kind=='circle': m=x*x+y*y < (p['width']/2)**2
        elif kind=='rectangle': m=(np.abs(x)<p['width']/2)&(np.abs(y)<p['length']/2)
        elif kind=='lines': m=(np.abs(x)<p['width']/2)&lanes
        else: m=(np.abs(x)>p['width']/2)&lanes
        self.mask = ~m if p['invert']=='outside' else m

    def coat(self, material, distance):
        n = self.cells(distance)
        if distance > 0 and n == 0: self.warnings.append('증착 두께가 반 셀보다 작아 형상에 반영되지 않았습니다. 격자를 줄여 보세요.')
        if n > 256: raise ValueError('Coating exceeds 256 grid layers; reduce thickness or use a coarser grid')
        # 6-neighbor front: conservative accessibility, no diagonal corner leaks.
        for _ in range(n):
            gas = accessible(self.g)
            front = gas & ndi.binary_dilation(self.g != 0, structure=SIX) & self.mask[:,:,None]
            if not front.any(): break
            self.g[front] = material

    def etch(self, p):
        target = [IDS['Si'], IDS['SiGe']] if p['material']=='Si+SiGe' else [IDS[p['material']]]
        depth = p['rate']*p['time']; n=self.cells(depth)
        if depth>0 and n==0: self.warnings.append('식각 거리가 반 셀보다 작아 형상 변화가 없습니다.')
        if p['mode']=='directional':
            budget = np.full(self.mask.shape, depth/self.dx)
            for k in range(self.g.shape[2]-1, -1, -1):
                layer=self.g[:,:,k]; solid=layer!=0
                cost=np.where(np.isin(layer,target), 1., p['selectivity'])
                remove=self.mask & solid & (budget >= cost-.00000001)
                layer[remove]=0
                # An incompletely removed cell blocks everything below it.
                budget=np.where(self.mask & solid, np.maximum(0,budget-cost),budget)
        else:
            if n>256: raise ValueError('Isotropic etch exceeds 256 front steps')
            for i in range(n):
                gas=accessible(self.g)
                front=ndi.binary_dilation(gas,structure=SIX)&(self.g!=0)&self.mask[:,:,None]
                remove=front & np.isin(self.g,target)
                if (i+1)//p['selectivity'] > i//p['selectivity']: remove |= front
                self.g[remove]=0
        if 0 < depth/p['selectivity'] < self.dx:
            self.warnings.append('비대상 재료 손실은 1셀 미만입니다. 선택비 효과가 격자에서 분해되지 않을 수 있습니다.')

    def oxidize(self, p):
        increments=[]; converted=0; gas=accessible(self.g)
        for i,j in np.argwhere(self.mask):
            solid=np.flatnonzero(self.g[i,j])
            if not len(solid): continue
            top=int(solid[-1]); si=top
            while si>=0 and self.g[i,j,si]==IDS['SiO2']: si-=1
            if si<0 or self.g[i,j,si]!=IDS['Si']: continue
            if top+1>=len(self.z) or not gas[i,j,top+1]: continue
            old=(top-si)*self.dx
            new=(-p['A']+math.sqrt((p['A']+2*old)**2+4*p['B']*p['time']))/2
            delta=max(0,new-old); increments.append(delta)
            consume=self.cells(.44*delta); outward=self.cells(.56*delta)
            for k in range(si, max(-1,si-consume), -1):
                if self.g[i,j,k]!=IDS['Si']: break
                self.g[i,j,k]=IDS['SiO2']; converted+=1
            self.g[i,j,top+1:min(len(self.z),top+outward+1)]=IDS['SiO2']
        self.notes['analytic_oxide_increment_nm']=float(np.mean(increments)) if increments else 0.
        self.notes['consumed_si_nm3']=converted*self.dx**3
        self.warnings.append('Deal–Grove 평면 근사: 초박막·곡면 응력 미보정. 0.44 Si 소비 / 0.56 외향 성장은 셀 단위로 양자화됩니다.')

    def implant(self, p):
        target=self.n if p['species']=='donor' else self.p
        deposited=0.
        for i,j in np.argwhere(self.mask):
            solid=np.flatnonzero(self.g[i,j])
            if not len(solid): continue
            top=int(solid[-1])
            # This reduced model does not transport ions through masks/dielectrics.
            if self.g[i,j,top]!=IDS['Si']: continue
            bottom=top
            while bottom>0 and self.g[i,j,bottom-1]==IDS['Si']: bottom-=1
            depths=(top-np.arange(top+1))*self.dx
            fractions=ndtr((depths+self.dx-p['rp'])/p['sigma'])-ndtr((depths-p['rp'])/p['sigma'])
            concentration=p['dose']*fractions/(self.dx*1e-7)
            concentration*=self.g[i,j,:top+1]==IDS['Si']
            concentration[:bottom]=0  # no transport through a buried dielectric
            target[i,j,:top+1]+=concentration
            deposited+=float(concentration.sum())*(self.dx*1e-7)**3
        self.notes['implanted_ions_expected']=deposited
        if p['dose'] and not deposited: self.warnings.append('노출된 Si가 없어 주입량이 0입니다. 마스크와 절연막을 확인하세요.')

    def anneal(self, p):
        # Boltzmann constant eV/K, explicit reference coefficient, not a material fit.
        D=p['Dref']*math.exp(-p['Ea']/8.617333262e-5*(1/p['temperature']-1/1100.))
        ratio=D*p['time']/self.dx**2
        steps=max(1,math.ceil(6*ratio))
        if steps>2000: raise ValueError('Diffusion requires >2000 stable substeps; reduce D, temperature or time')
        si=self.g==IDS['Si']
        for _ in range(steps):
            self.n=diffusion_step(self.n,si,ratio/steps)
            self.p=diffusion_step(self.p,si,ratio/steps)
            self.an=diffusion_step(self.an,si,ratio/steps)
            self.ap=diffusion_step(self.ap,si,ratio/steps)
        self.an=np.maximum(self.an,p['activation']*self.n)
        self.ap=np.maximum(self.ap,p['activation']*self.p)
        self.notes.update(D_nm2_s=D, diffusion_substeps=steps)

    def bond(self, p):
        occupied=np.argwhere(self.g!=0)
        if not len(occupied): raise ValueError('Nothing to stack')
        height=int(occupied[:,2].max())+1; gap=self.cells(p['gap']); shift=height+gap
        if shift+height>self.g.shape[2]: raise ValueError('적층 높이가 Z 도메인을 넘습니다. Z 셀 수를 늘려 주세요.')
        ix=int(round(p['offset_x']/self.dx)); iy=int(round(p['offset_y']/self.dx))
        nx,ny,_=self.g.shape
        xs=slice(max(0,ix),min(nx,nx+ix)); sx=slice(max(0,-ix),min(nx,nx-ix))
        ys=slice(max(0,iy),min(ny,ny+iy)); sy=slice(max(0,-iy),min(ny,ny-iy))
        if abs(ix)>=nx or abs(iy)>=ny: raise ValueError('Bond alignment moves the entire die out of the domain')
        # Oxide bonding layer, Cu continuation only where the lower die has a pad.
        copper=self.g[:,:,height-1]==IDS['Cu']
        self.g[:,:,height:shift]=IDS['SiO2']
        self.g[:,:,height:shift][np.broadcast_to(copper[:,:,None],(nx,ny,gap))]=IDS['Cu']
        for a in (self.g,self.n,self.p,self.an,self.ap):
            a[xs,ys,shift:shift+height]=a[sx,sy,:height].copy()
        if ix or iy: self.warnings.append('정렬 이동으로 도메인 밖으로 나간 위 다이 셀은 잘립니다. 측면 여유 공간을 확인하세요.')
        self.notes.update(bond_shift_z_nm=shift*self.dx, alignment_x_nm=ix*self.dx, alignment_y_nm=iy*self.dx)

    def apply(self, step):
        op=step['op']; p=step['params']; self.warnings=[]; self.notes={}
        if op=='mask': self.set_mask(p)
        elif op=='deposit':
            thickness=p['cycles']*p['gpc']*(-math.expm1(-p['k']*p['exposure']))
            self.notes['analytic_deposit_nm']=thickness
            self.coat(IDS[p['material']],thickness)
        elif op=='epitaxy':
            n=self.cells(p['thickness'])
            for i,j in np.argwhere(self.mask):
                solid=np.flatnonzero(self.g[i,j]); top=int(solid[-1])+1 if len(solid) else 0
                if top+n>len(self.z): raise ValueError('Epitaxy exceeds Z domain')
                self.g[i,j,top:top+n]=IDS[p['material']]
        elif op=='etch': self.etch(p)
        elif op=='oxidize': self.oxidize(p)
        elif op=='implant': self.implant(p)
        elif op=='anneal': self.anneal(p)
        elif op=='fill':
            self.g[(self.g==0)&self.mask[:,:,None]&(self.z[None,None,:]<p['height'])]=IDS[p['material']]
        elif op=='bond': self.bond(p)
        elif op=='test':
            from fab_lab.electrical import evaluate
            self.test=evaluate(self,p)
        # Removed silicon removes its dopants; newly formed films contain none.
        for a in (self.n,self.p,self.an,self.ap): a[self.g!=IDS['Si']]=0
        if np.any(self.g[:,:,-1]): self.warnings.append('구조가 Z 상단에 닿았습니다. 도메인을 늘려야 증착/접근성 결과를 신뢰할 수 있습니다.')

    def frame(self, index, label, op):
        volumes={m['name']:int(np.count_nonzero(self.g==m['id']))*self.dx**3 for m in MATERIALS[1:]}
        counts=np.count_nonzero(self.g,axis=2)
        heights=np.max(np.where(self.g!=0,self.z[None,None,:]+self.dx/2,0),axis=2)
        void=(self.g==0)&~accessible(self.g)
        # Sections store signed net active doping. No log of a signed number.
        net=self.an-self.ap
        mid=int(np.unravel_index(np.abs(net).argmax(),net.shape)[1]) if np.any(net) else self.g.shape[1]//2
        return dict(index=index,label=label,op=op,grid=rle(self.g),mask=rle(self.mask.astype('uint8')),
                    volume_nm3=volumes, top_z_nm=float(heights.max()),
                    sealed_void_nm3=int(void.sum())*self.dx**3,
                    solid_cells=int(counts.sum()),
                    donor_ions=float(self.n.sum())*(self.dx*1e-7)**3,
                    acceptor_ions=float(self.p.sum())*(self.dx*1e-7)**3,
                    active_peak_cm3=float(np.abs(net).max()),
                    doping_y_index=mid,
                    doping_xz_cm3=net[:,mid,:].ravel().tolist(),
                    warnings=list(dict.fromkeys(self.warnings)),notes=self.notes.copy(),test=self.test if op=='test' else None)


def simulate(raw, directory=None, progress=None):
    request=validate(raw); state=State(request['domain'])
    frames=[state.frame(0,'초기 wafer / SOI','wafer')]
    enabled=[(i,s) for i,s in enumerate(request['steps']) if s['enabled']]
    if progress: progress(0,frames[-1])
    for count,(i,s) in enumerate(enabled,1):
        state.apply(s); frame=state.frame(i+1,s['label'],s['op']); frames.append(frame)
        if progress: progress(count/max(1,len(enabled)),frame)
    if directory:
        np.savez_compressed(Path(directory)/'final_state.npz',material=state.g,donor_cm3=state.n,
                            acceptor_cm3=state.p,active_donor_cm3=state.an,active_acceptor_cm3=state.ap,mask=state.mask)
    digest=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(version=VERSION,request=request,run_hash=digest,frames=frames,
                implementation_sha256={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                                       for name in ('engine.py','schema.py','electrical.py','presets.py')},
                runtime=dict(numpy=np.__version__,scipy=scipy.__version__),
                conventions=dict(axis='x,y horizontal; z upward; C-order [nx,ny,nz]',length='nm',concentration='cm^-3',
                                 boundary='closed sides; gas access from top; diffusion no flux outside Si',randomness='none'),
                limitations=['Uncalibrated grid morphology, no commercial TCAD equivalence.',
                             'No lithography or CMP. Starting wafer/SOI is an input, not crystal growth.',
                             'No 3D Poisson, quantum transport, stress, thermal field or reactive plasma chemistry.',
                             'MOS electrical dimensions and EOT are explicitly supplied, not extracted from these voxels.',
                             'Coating/etch fronts are 6-neighbor grid approximations; perform grid convergence studies.'])
