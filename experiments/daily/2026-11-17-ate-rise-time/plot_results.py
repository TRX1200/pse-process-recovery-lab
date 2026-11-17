"""Plot the stored, complete numerical captures without changing the model."""
from pathlib import Path
import csv
import gzip
import json
import platform
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent
OUT=HERE/'figures';OUT.mkdir(exist_ok=True)
captures=json.loads(gzip.decompress((HERE/'data/captures.json.gz').read_bytes()))
summary=json.loads((HERE/'data/summary.json').read_text(encoding='utf-8'))['cases']
with (HERE/'data/decision_samples.csv').open(encoding='utf-8-sig',newline='') as f:
    decisions=list(csv.DictReader(f))
with (HERE/'data/phase_envelopes.csv').open(encoding='utf-8-sig',newline='') as f:
    envelopes=list(csv.DictReader(f))
NAVY='#243c57';TEAL='#147d83';ORANGE='#c26029';GRAY='#5c6e7d'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
    'axes.spines.right':False,'text.color':NAVY,'axes.labelcolor':NAVY,'axes.edgecolor':'#c0cbd4',
    'grid.color':'#e2e8ec','grid.alpha':.8,'savefig.facecolor':'white'})
all_values=np.concatenate([np.array(c['traces']).ravel() for c in captures.values()])
limits=(min(-.05,float(all_values.min())-.03),max(1.05,float(all_values.max())+.03))
fig,axes=plt.subplots(1,2,figsize=(13,7),sharex=True,sharey=True)
fig.subplots_adjust(left=.07,right=.97,top=.72,bottom=.18,wspace=.16)
fig.suptitle('02 / ATE experiment: slower edges, less receiver margin',x=.07,y=.96,ha='left',fontsize=20,fontweight='bold')
fig.text(.07,.90,'One change: source 10-90% rise time 35 ps -> 70 ps. Same channel, source bits and jitter.',fontsize=12)
fig.text(.07,.85,'DQ0_RX  /  8 Gb/s  /  125 ps per UI  /  seed 42  /  237 overlapping two-UI traces',fontsize=11,color=GRAY)
for ax,case,color in zip(axes,['A','B'],[TEAL,ORANGE]):
    capture=captures[case];values=np.array(capture['traces']);m=summary[case]
    assert values.shape==(237,129)
    ax.plot(capture['x'],values.T,color=color,alpha=.12,lw=.8)
    ax.axhline(.5,color=NAVY,lw=1,ls='--');ax.axvline(.5,color=GRAY,lw=1,ls=':')
    ax.plot([.5,.5],[m['max_zero_v'],m['min_one_v']],color=NAVY,lw=2.5,marker='_',markersize=14)
    ax.set_title(f"{case} / {m['rise_ps']:.0f} ps\nCentral opening: {m['opening_v']:.3f} V",loc='left',fontsize=13,pad=12,fontweight='bold')
    ax.set_xlim(0,2);ax.set_ylim(*limits);ax.set_xlabel('Aligned time (UI)');ax.grid(zorder=0)
axes[0].set_ylabel('Receiver voltage (V)')
fig.text(.07,.105,'Dashed horizontal: 0.5 V decision threshold. Dotted vertical: fixed sample at 0.5 UI.',fontsize=10,color=GRAY)
fig.text(.07,.052,'Educational synthetic fixture; no measured chip data, calibrated channel loss, clock recovery, or statistical BER.',fontsize=9,color=GRAY)
fig.savefig(OUT/'01_eye_comparison.png',dpi=160);plt.close(fig)

fig,(ranges,phase)=plt.subplots(2,1,figsize=(13,9),gridspec_kw={'height_ratios':[.9,1.2]})
fig.subplots_adjust(left=.14,right=.95,top=.77,bottom=.13,hspace=.55)
fig.suptitle('Decision errors stayed at zero. The margin did not.',x=.07,y=.96,ha='left',fontsize=20,fontweight='bold')
fig.text(.07,.90,'A: 0 / 237 mismatches      B: 0 / 237 mismatches      |      Finite pattern only, not a BER estimate.',fontsize=11,color=GRAY)
for case,y in [('A',1),('B',0)]:
    m=summary[case]
    for bit,color in [(0,ORANGE),(1,TEAL)]:
        values=[float(r['sample_v']) for r in decisions if r['case']==case and int(r['expected_bit'])==bit]
        ranges.plot([min(values),max(values)],[y,y],lw=12,color=color,solid_capstyle='butt')
    ranges.annotate('',xy=(m['min_one_v'],y+.19),xytext=(m['max_zero_v'],y+.19),
                    arrowprops={'arrowstyle':'<->','color':NAVY,'lw':1.3})
    ranges.text(.5,y+.30,f"Opening {m['opening_v']:.3f} V  /  worst threshold margin {m['worst_threshold_margin_v']:.3f} V",
                ha='center',fontsize=10)
ranges.axvline(.5,color=NAVY,ls='--',lw=1)
ranges.set_yticks([1,0],['A / 35 ps','B / 70 ps'])
ranges.set_ylim(-.3,1.7);ranges.set_xlim(-.05,1.05)
ranges.set_xlabel('Voltage at fixed sampling instant (V)')
ranges.set_title('Observed level ranges: orange = expected 0, teal = expected 1',loc='left',fontsize=12,pad=12)
ranges.grid(axis='x');ranges.set_axisbelow(True)
for case,color,ls in [('A',TEAL,'-'),('B',ORANGE,'--')]:
    entries=[r for r in envelopes if r['case']==case]
    x=np.array([float(r['phase_ui']) for r in entries]);y=np.array([float(r['opening_v']) for r in entries])
    phase.plot(x,y,color=color,lw=2,ls=ls,label=f"{case}: {summary[case]['rise_ps']:.0f} ps")
    phase.plot(.5,summary[case]['opening_v'],'o',color=color)
phase.axhline(0,color=GRAY,lw=1);phase.axvline(.5,color=GRAY,lw=1,ls=':')
phase.set_xlim(0,1);phase.set_xlabel('Phase within the first UI')
phase.set_ylabel('Worst 1 minus worst 0 (V)');phase.grid()
phase.set_title('Vertical separation across phase (diagnostic only; sampling phase was not optimized)',loc='left',fontsize=12,pad=12)
phase.legend(loc='lower center',frameon=False,ncol=2)
fig.text(.07,.04,'Single fixed-seed realization; all metrics use the stored arrays. A negative separation means level ranges overlap.',fontsize=9,color=GRAY)
fig.savefig(OUT/'02_sampling_margin.png',dpi=160);plt.close(fig)
(OUT/'render_environment.json').write_text(json.dumps(dict(python=platform.python_version(),matplotlib=matplotlib.__version__,numpy=np.__version__,
    source='Stored captures.json.gz, decision_samples.csv and phase_envelopes.csv; no recomputation of model outputs'),indent=2),encoding='utf-8')
print('Rendered 2 figures from stored numerical captures.')
