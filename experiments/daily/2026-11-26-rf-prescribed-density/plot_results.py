"""Plot saved RF arrays only; no smoothing, optimization, or hidden samples."""
from pathlib import Path
import argparse
import gzip
import json
import platform
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
root=parser.parse_args().data_dir
out=root/'figures';out.mkdir(exist_ok=True)
runs={c:json.loads(gzip.decompress((root/f'data/{c}.json.gz').read_bytes())) for c in ['A','B']}
colors={'A':'#0072B2','B':'#B74500'}
labels={'A':r'A: $n_e=2\times10^{16}$ m$^{-3}$','B':r'B: $n_e=3\times10^{16}$ m$^{-3}$'}
styles={'A':'-','B':'--'}
footer='Educational simulation | Prescribed load; fixed matching C/L | No equipment calibration'
files=[]
def finish(fig,name,note):
    fig.text(.07,.105,note,fontsize=10,color='#374151')
    fig.text(.07,.025,footer,fontsize=9,color='#4B5563')
    path=out/name
    fig.savefig(path,dpi=180,facecolor='white')
    plt.close(fig);files.append(path)

with plt.rc_context({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':13,
    'axes.spines.top':False,'axes.spines.right':False,'axes.axisbelow':True,
    'grid.color':'#DEE3E9','grid.linewidth':.7,'figure.facecolor':'white'}):
    fig,axes=plt.subplots(1,2,figsize=(12,6))
    fig.subplots_adjust(left=.075,right=.97,top=.80,bottom=.25,wspace=.26)
    fig.suptitle('Fixed matcher, different prescribed plasma density',x=.075,ha='left',fontsize=19,y=.96)
    for case,r in runs.items():
        band=r['frequency_sweep'];f=[v['frequency_mhz'] for v in band]
        for ax,key in zip(axes,['s11_db','bulk_w']):
            ax.plot(f,[v[key] for v in band],styles[case],color=colors[case],lw=2,label=labels[case])
            ax.scatter([13.56],[r['operating_point'][key]],marker='o' if case=='A' else 's',s=38,color=colors[case],zorder=4)
    for ax in axes:
        ax.axvline(13.56,color='#596574',lw=1,ls=':');ax.grid();ax.set(xlim=(8.56,18.56),xlabel='Frequency (MHz)')
    axes[0].set(title='Reflection at generator plane',ylabel=r'$S_{11}=20\log_{10}|\Gamma|$ (dB)')
    axes[1].set(title='Power dissipated in bulk resistance',ylabel='Bulk absorbed power (W)',ylim=(0,None))
    axes[0].legend(fontsize=10,loc='lower left')
    finish(fig,'01_frequency_response.png','201 steady-state samples, 0.05 MHz spacing. Markers: 13.56 MHz. Lines join computed samples.')

    fig,ax=plt.subplots(figsize=(12,6))
    fig.subplots_adjust(left=.075,right=.97,top=.76,bottom=.27)
    fig.suptitle('Where the 300 W forward power goes',x=.075,ha='left',fontsize=19,y=.96)
    keys=['reflected_w','bulk_w','coil_loss_w','capacitor_loss_w']
    names=['Reflected','Bulk absorption','Coil loss','Capacitor loss']
    palette=['#667085','#0072B2','#B74500','#A78900']
    hatch=['','///','\\\\','xx'];left=np.zeros(2)
    for key,name,color,h in zip(keys,names,palette,hatch):
        vals=np.array([runs[c]['operating_point'][key] for c in ['A','B']])
        ax.barh([1,0],vals,left=left,height=.48,color=color,label=name,hatch=h,edgecolor='white')
        for y,start,value in zip([1,0],left,vals):
            if value>=10: ax.text(start+value/2,y,f'{value:.2f}',ha='center',va='center',color='white',fontsize=10,fontweight='bold')
        left+=vals
    ax.set(yticks=[1,0],yticklabels=['A','B'],xlabel='Power (W)',xlim=(0,310),ylim=(-.6,1.6))
    ax.grid(axis='x');ax.legend(ncol=4,loc='upper left',bbox_to_anchor=(0,1.22),fontsize=10)
    ca=runs['A']['operating_point']['capacitor_loss_w'];cb=runs['B']['operating_point']['capacitor_loss_w']
    finish(fig,'02_power_budget.png',f'13.56 MHz; A = 2e16, B = 3e16 m^-3. Small capacitor-loss segments: A {ca:.2f} W, B {cb:.2f} W.')

    fig,axes=plt.subplots(1,3,figsize=(12,6))
    fig.subplots_adjust(left=.075,right=.97,top=.78,bottom=.26,wspace=.35)
    fig.suptitle('Density changes the load; current stays nearly the same here',x=.075,ha='left',fontsize=17,y=.96)
    for ax,key,title,unit in zip(axes,['bulk_r_ohm','bulk_l_nh','coil_current_rms_a'],
        ['Bulk resistance','Bulk inertial inductance','Series-branch current'],['Resistance (ohm)','Inductance (nH)','Current (A RMS)']):
        vals=[runs[c]['operating_point'][key] for c in ['A','B']]
        bars=ax.bar(['A','B'],vals,color=[colors['A'],colors['B']],width=.55)
        bars[1].set_hatch('//')
        ax.bar_label(bars,labels=[f'{v:.4f}' for v in vals],padding=5)
        ax.set(title=title,ylabel=unit,ylim=(0,max(vals)*1.25));ax.grid(axis='y')
    finish(fig,'03_load_and_current.png','A = 2e16, B = 3e16 m^-3. Bulk R and L scale as 1/density; sheath C is fixed.')

metadata=[]
for path in files:
    with Image.open(path) as im:
        alpha=im.getchannel('A').getextrema() if im.mode=='RGBA' else None
        assert im.size==(2160,1080)
        assert alpha in [None,(255,255)]
        metadata.append(dict(file=path.name,pixels=im.size,mode=im.mode,dpi=im.info.get('dpi'),alpha_extrema=alpha))
(out/'image_metadata.json').write_text(json.dumps(dict(python=platform.python_version(),numpy=np.__version__,matplotlib=matplotlib.__version__,
    files=metadata,transformations='No smoothing, clipping, interpolation or added uncertainty; lines join computed frequency samples.'),indent=2),encoding='utf-8')
print(json.dumps(metadata))
