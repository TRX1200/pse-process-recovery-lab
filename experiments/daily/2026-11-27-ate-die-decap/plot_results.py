"""Render the preserved PDN magnitude samples; no smoothing or peak fitting."""
from pathlib import Path
import argparse
import json
import platform
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
import PIL

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
root=parser.parse_args().data_dir;out=root/'figures';out.mkdir(exist_ok=True)
runs={c:json.loads((root/f'data/{c}.json').read_text(encoding='utf-8')) for c in ['A','B']}
summary=json.loads((root/'data/summary.json').read_text(encoding='utf-8'))
f=np.array(runs['A']['x']);z={c:np.array(r['traces'][0]) for c,r in runs.items()}
colors={'A':'#0072B2','B':'#B74500'};styles={'A':'-','B':'--'}
labels={'A':'A: die decap 10 nF','B':'B: die decap 30 nF'}
files=[]
footer='Educational simulation | Independent VDD_DIE fixture | No equipment calibration or extracted SI/PI'
def finish(fig,name,note):
    fig.text(.075,.10,note,fontsize=10,color='#374151')
    fig.text(.075,.025,footer,fontsize=9,color='#4B5563')
    p=out/name;fig.savefig(p,dpi=180,facecolor='white');plt.close(fig);files.append(p)

with plt.rc_context({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':13,
    'axes.spines.top':False,'axes.spines.right':False,'axes.axisbelow':True,
    'grid.color':'#DEE3E9','grid.linewidth':.7,'figure.facecolor':'white'}):
    fig,ax=plt.subplots(figsize=(12,6))
    fig.subplots_adjust(left=.08,right=.97,top=.82,bottom=.25)
    fig.suptitle('Die decoupling changes the entire impedance spectrum',x=.075,ha='left',fontsize=18,y=.96)
    ax.axvspan(1,100,color='#E7ECF2',zorder=-2,label='Predeclared analysis band: 1-100 MHz')
    for c in ['A','B']:
        ax.loglog(f,z[c],styles[c],lw=2,color=colors[c],label=labels[c])
        p=summary[c]['analysis_band_max']
        ax.scatter([p['frequency_mhz']],[p['z_abs_ohm']],marker='o' if c=='A' else 's',s=50,color=colors[c],zorder=4)
    ax.set(xlabel='Frequency (MHz, log scale)',ylabel='Driving-point |Z| (ohm, log scale)',xlim=(.1,3000))
    ax.grid(which='major');ax.legend(loc='upper left',fontsize=10)
    finish(fig,'01_full_impedance_spectrum.png','241 computed samples; lines join samples. Markers: analysis-band maxima. B full-band maximum is at the 3000 MHz endpoint.')

    fig,axes=plt.subplots(1,2,figsize=(12,6))
    fig.subplots_adjust(left=.08,right=.97,top=.80,bottom=.26,wspace=.28)
    fig.suptitle('Lower band maximum does not mean lower impedance everywhere',x=.075,ha='left',fontsize=17,y=.96)
    mask=(f>=1)&(f<=100)
    for c in ['A','B']:
        p=summary[c]['analysis_band_max']
        axes[0].semilogx(f[mask],z[c][mask],styles[c],lw=2,color=colors[c],label=f"{c}: {p['z_abs_ohm']:.3f} ohm at {p['frequency_mhz']:.2f} MHz")
        axes[0].scatter([p['frequency_mhz']],[p['z_abs_ohm']],marker='o' if c=='A' else 's',s=45,color=colors[c],zorder=4)
    axes[0].set(title='1-100 MHz detail (107 stored samples)',xlabel='Frequency (MHz, log scale)',ylabel='Driving-point |Z| (ohm)',xlim=(1,100),ylim=(0,None))
    axes[0].legend(loc='upper left',fontsize=9)
    axes[1].loglog(f,z['B']/z['A'],color='#4B3F72',lw=2)
    axes[1].axhline(1,color='#30343B',ls='--',lw=1,label='B/A = 1: unchanged')
    axes[1].set(title='All-frequency ratio: 30 nF / 10 nF',xlabel='Frequency (MHz, log scale)',ylabel='Magnitude ratio B/A (log scale)',xlim=(.1,3000))
    axes[1].legend(loc='upper left',fontsize=9)
    for ax in axes:ax.grid(which='major')
    finish(fig,'02_band_detail_and_ratio.png','A = 10 nF; B = 30 nF. Ratio above 1: B has higher impedance; below 1: B has lower impedance. No fitted peaks.')

metadata=[]
for p in files:
    with Image.open(p) as im:
        alpha=im.getchannel('A').getextrema() if im.mode=='RGBA' else None
        assert im.size==(2160,1080) and alpha in [None,(255,255)]
        metadata.append(dict(file=p.name,pixels=im.size,mode=im.mode,dpi=im.info.get('dpi'),alpha_extrema=alpha))
(out/'image_metadata.json').write_text(json.dumps(dict(python=platform.python_version(),numpy=np.__version__,matplotlib=matplotlib.__version__,pillow=PIL.__version__,
    files=metadata,transformations='Log axes explicitly labelled; ratio B/A; full-band figure retained; no smoothing or added samples.'),indent=2),encoding='utf-8')
print(json.dumps(metadata))
