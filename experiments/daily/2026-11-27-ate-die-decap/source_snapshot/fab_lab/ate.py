"""Educational port-resolved SI/PI bench, independent of Fab Flow voxel nets."""
import math
import numpy as np
from rf_lab.practice import bounded, strict_dict

# Fixture conductor lengths [mm], from source pad through board to package pad.
LANES = {'DQ0': (24., 8.), 'DQ1': (42., 12.)}
PORTS = {f'{lane}_{end}' for lane in LANES for end in ('TX','RX')} | {'VDD_BOARD','VDD_DIE'}
VELOCITY = 160.0  # prescribed fixture propagation speed [mm/ns]


def line_response(source, dt_ns, lengths, impedances, rs, rl):
    """Bidirectional voltage waves. One junction, two lossless lines, finite Rs/RL."""
    z1,z2=impedances
    d1,d2=[max(1,round(length/VELOCITY/dt_ns)) for length in lengths]
    gs=(rs-z1)/(rs+z1)
    gl=(rl-z2)/(rl+z2)
    gj=(z2-z1)/(z2+z1)
    n=len(source)
    fs=np.zeros(n+d1+d2); bs=np.zeros_like(fs)
    fl=np.zeros_like(fs); bl=np.zeros_like(fs)
    near=np.empty(n); far=np.empty(n)
    for k,vs in enumerate(source):
        forward=vs*z1/(rs+z1)+gs*bs[k]
        near[k]=forward+bs[k]
        fs[k+d1]=forward
        far[k]=(1+gl)*fl[k]
        bl[k+d2]=gl*fl[k]
        bs[k+d1]=gj*fs[k]+(1-gj)*bl[k]
        fl[k+d2]=(1+gj)*fs[k]-gj*bl[k]
    return near,far,(d1,d2)


def simulate(raw):
    strict_dict(raw,['port','mode','seed','rate_gbps','load_ohm','package_z','jitter_ui','rise_ps','strobe_ui','threshold_v','decap_nf'])
    port=raw.get('port','DQ0_RX'); mode=raw.get('mode','eye')
    if not isinstance(port,str) or port not in PORTS or mode not in ('eye','tdr','pdn'):
        raise ValueError('Select a valid port and measurement')
    if (mode=='pdn') != port.startswith('VDD'):
        raise ValueError('Eye/TDR require a DQ port; PDN requires a power port')
    seed=bounded(raw,'seed',42,0,2**31-1,True)
    rate=bounded(raw,'rate_gbps',8,1,16)
    load=bounded(raw,'load_ohm',50,10,200)
    z=bounded(raw,'package_z',65,25,100)
    jitter=bounded(raw,'jitter_ui',0.04,0,0.25)
    rise=bounded(raw,'rise_ps',35,5,250)
    decap=bounded(raw,'decap_nf',10,0.2,100)
    strobe=bounded(raw,'strobe_ui',.5,.05,.95)
    threshold=bounded(raw,'threshold_v',.5,0,2)
    config=dict(strobe_ui=strobe,threshold_v=threshold,port=port,mode=mode,seed=seed,rate_gbps=rate,load_ohm=load,package_z=z,jitter_ui=jitter,rise_ps=rise,decap_nf=decap)
    report=dict(model='ate-two-line-pdn-v1',config=config,port=port,mode=mode)
    if mode=='pdn':
        freq=np.geomspace(1e5,3e9,241)
        jw=2j*np.pi*freq
        def par(a,b):
            return a*b/(a+b)
        # Two locally grounded nodes, zeroed ideal VRM. Series-RLC decouplers.
        supply=.025+jw*.8e-9
        board=par(supply,.018+jw*.35e-9+1/(jw*100e-9))
        link=.012+jw*.55e-9
        die=.012+jw*.08e-9+1/(jw*decap*1e-9)
        zp=par(board,link+die) if port=='VDD_BOARD' else par(die,link+board)
        mag=np.abs(zp); peak=int(np.argmax(mag))
        return {**report,'x':(freq/1e6).tolist(),'traces':[mag.tolist()],'x_unit':'MHz','y_unit':'Ω',
                'reading':{'대역 최대 |Z| (Ω)':float(mag[peak]),'해당 주파수 (MHz)':float(freq[peak]/1e6)}}
    lane,end=port.split('_'); lengths=LANES[lane]; zs=(50.,z)
    if mode=='tdr':
        # Matched 50-ohm instrument, 2 V Thevenin step -> 1 V incident reference.
        if end=='RX': lengths=lengths[::-1]; zs=zs[::-1]
        dt=.002  # ns
        t=np.arange(1601)*dt
        near,_,delays=line_response(2*np.ones(t.size),dt,lengths,zs,50.,load)
        rho=near-1
        apparent=50*(1+rho)/(1-rho)
        return {**report,'x':t.tolist(),'traces':[apparent.tolist()],'x_unit':'ns','y_unit':'Ω',
                'reading':{'초기 임피던스 (Ω)':float(apparent[0]),'종단 정착값 (Ω)':float(apparent[-1]),
                '첫 접합 왕복 (ns)':2*delays[0]*dt,'종단 왕복 (ns)':2*sum(delays)*dt}}
    # 256 seeded random NRZ bits (not a standardized PRBS compliance pattern).
    rng=np.random.default_rng(seed); bits=rng.integers(0,2,256)
    spui=64; ui=1/rate; dt=ui/spui
    t=np.arange(len(bits)*spui)*dt
    boundaries=(np.arange(1,len(bits))+rng.uniform(-jitter,jitter,len(bits)-1))*ui
    logic=bits[np.searchsorted(boundaries,t,side='right')]
    # First-order source shaping: 10–90% rise time = ln(9)*tau. Driver 0/2 V into 50 ohm.
    gain=-math.expm1(-dt*math.log(9)/(rise*.001)); drive=np.empty(len(t)); v=0.
    for k,b in enumerate(logic):
        v+=gain*(2*int(b)-v); drive[k]=v
    near,far,delays=line_response(drive,dt,lengths,zs,50.,load)
    wave=near if end=='TX' else far; offset=0 if end=='TX' else sum(delays)
    # Align to nominal launched clock plus quantized flight time, no CDR/eye optimization.
    indices=np.arange(16,(len(wave)-offset-2*spui-1)//spui+1); starts=indices*spui+offset
    rows=np.stack([wave[k:k+2*spui+1] for k in starts])
    samples=rows[:,spui//2]; levels=bits[indices]
    opening=float(np.min(samples[levels==1])-np.max(samples[levels==0]))
    sample_index=round(strobe*spui)
    observed=rows[:,sample_index]>=threshold
    misses=int(np.count_nonzero(observed!=levels))
    return {**report,'x':(np.arange(2*spui+1)/spui).tolist(),'traces':rows.tolist(),'x_unit':'UI','y_unit':'V',
            'reading':{'중앙 수직 여유 (V)':opening,'UI (ps)':1000*ui,'정렬 지연 (ps)':1000*offset*dt,'판정 시각 (UI)':sample_index/spui,'패턴 불일치 (bit)':misses,'검사한 비트':int(len(rows))}}
