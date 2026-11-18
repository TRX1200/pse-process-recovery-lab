"""Render stored material arrays with discrete colors and physical nm axes."""
from pathlib import Path
import json
import platform
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm, to_rgba
from matplotlib.patches import Patch
import numpy as np

HERE=Path(__file__).resolve().parent;OUT=HERE/'figures';OUT.mkdir(exist_ok=True)
summary=json.loads((HERE/'data/summary.json').read_text(encoding='utf-8'))
result=json.loads((HERE/'data/result.json').read_text(encoding='utf-8'))
with np.load(HERE/'data/sections.npz') as f:sections={k:f[k] for k in f.files}
NAVY='#253e53';GRAY='#5a6c79';SI='#648da8';SIGE='#c17d9e';OXIDE='#d3dce3';VOID='#f7f9fb';TEAL='#277d7e'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'text.color':NAVY,'axes.labelcolor':NAVY,
    'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#bbc8d1',
    'grid.color':'#e1e7ec','savefig.facecolor':'white'})
cmap=ListedColormap([VOID,SI,SIGE,OXIDE]);norm=BoundaryNorm(np.arange(5)-.5,4)
legend=[Patch(facecolor=SI,label='Si'),Patch(facecolor=SIGE,label='SiGe (sacrificial)'),Patch(facecolor=OXIDE,label='SiO2 (BOX)'),Patch(facecolor=VOID,edgecolor='#ccd5dd',label='Void')]
fig,axes=plt.subplots(1,3,figsize=(14,6.2),sharex=True,sharey=True)
fig.subplots_adjust(left=.06,right=.98,top=.70,bottom=.19,wspace=.11)
fig.suptitle('03 / GAA release: shorter etch leaves SiGe between the sheets',x=.06,y=.96,ha='left',fontsize=19,fontweight='bold')
fig.text(.06,.90,'Only release time changes: A = 14 s, B = 7 s. Same upstream stack, mask, 2 nm/s rate and selectivity 100.',fontsize=11)
fig.text(.06,.85,f"Actual voxel section at X = {result['sections']['yz_x_nm']:g} nm / 4 nm cells / nearest-neighbor rendering",fontsize=10,color=GRAY)
extent=(-72,72,0,192)
titles=['Before release','A / 14 s: no SiGe voxels remain','B / 7 s: 20% SiGe remains']
for ax,key,title in zip(axes,['before_yz','A_yz','B_yz'],titles):
    ax.imshow(sections[key].T,origin='lower',extent=extent,cmap=cmap,norm=norm,interpolation='nearest',aspect='equal')
    ax.set_title(title,fontsize=12,pad=12,fontweight='bold');ax.set_xlabel('Y (nm)')
    ax.set_xlim(-72,72);ax.set_ylim(0,112);ax.set_xticks([-64,-32,0,32,64]);ax.set_yticks([0,24,32,52,72,92,112])
axes[0].set_ylabel('Z (nm)')
fig.legend(handles=legend,ncol=4,loc='lower center',bbox_to_anchor=(.5,.08),frameon=False)
fig.text(.06,.035,'Educational grid morphology. Zero resolved Si loss does not establish zero physical damage; no transistor electrical prediction.',fontsize=9,color=GRAY)
fig.savefig(OUT/'01_release_sections.png',dpi=160);plt.close(fig)

fig,(vol,pct)=plt.subplots(1,2,figsize=(13,7),gridspec_kw={'width_ratios':[1.1,1]})
fig.subplots_adjust(left=.10,right=.96,top=.77,bottom=.22,wspace=.35)
fig.suptitle('SiGe removal and residual volume from the material grid',x=.06,y=.96,ha='left',fontsize=18,fontweight='bold')
fig.text(.06,.90,'Pre-release SiGe = 184,320 nm3. All values below come from counting stored material voxels.',fontsize=11)
values=[summary['A']['before_sige_nm3'],summary['A']['remaining_sige_nm3'],summary['B']['remaining_sige_nm3']]
bars=vol.bar(['Before','A / 14 s','B / 7 s'],np.array(values)/1000,color=[GRAY,TEAL,SIGE],width=.6)
vol.set_ylim(0,215);vol.set_ylabel('Remaining SiGe volume (10^3 nm3)');vol.grid(axis='y',alpha=.7);vol.set_axisbelow(True)
for bar,value in zip(bars,values):vol.text(bar.get_x()+bar.get_width()/2,value/1000+5,f'{value:,.0f} nm3',ha='center',fontsize=11)
for y,case in enumerate(['A','B']):
    removed=summary[case]['sige_removed_pct'];remaining=100-removed
    pct.barh(y,removed,color=TEAL,height=.45,label='Removed' if y==0 else None)
    pct.barh(y,remaining,left=removed,color=SIGE,height=.45,label='Remaining' if y==0 else None)
    pct.text(removed/2,y,f'{removed:.0f}%',ha='center',va='center',color='white',fontweight='bold')
    if remaining:pct.text(removed+remaining/2,y,f'{remaining:.0f}%',ha='center',va='center',color='white',fontweight='bold')
pct.set_yticks([0,1],['A / 14 s','B / 7 s']);pct.invert_yaxis();pct.set_xlim(0,100)
pct.set_xlabel('Fraction of initial SiGe (%)');pct.legend(loc='lower center',bbox_to_anchor=(.5,1.02),ncol=2,frameon=False)
fig.text(.06,.115,'Original Si in the channel ROI: 122,880 nm3 before and after in both cases. Loss below the 4 nm grid is unresolved.',fontsize=10,color=GRAY)
fig.text(.06,.064,'Numerical detail: 14 s -> 7 front steps; 7 s -> 4 steps (14 nm budget rounds to 16 nm of front-step distance).',fontsize=10,color=GRAY)
fig.text(.06,.022,'No mesh-convergence claim, calibrated process chemistry, gate-stack simulation, or device-current prediction.',fontsize=9,color=GRAY)
fig.savefig(OUT/'02_release_metrics.png',dpi=160);plt.close(fig)

# Show only the predeclared channel region. Substrate and S/D anchors are omitted for display, not recalculated.
grids={}
with np.load(HERE/'data/A/final_state.npz') as f:grids['A']=f['material']
with np.load(HERE/'data/B/final_state.npz') as f:grids['B']=f['material']
fig=plt.figure(figsize=(13,6.8))
fig.suptitle('Stored 3D material voxels / release-region cutaway',x=.06,y=.96,ha='left',fontsize=19,fontweight='bold')
fig.text(.06,.90,'Display crop: -32 < X < 32 nm, 32 <= Z < 92 nm. S/D anchors and substrate omitted from this view.',fontsize=11)
fig.subplots_adjust(left=.02,right=.98,top=.85,bottom=.13,wspace=.04)
X,Y,Z=np.meshgrid(np.arange(17)*4-32,np.arange(37)*4-72,np.arange(16)*4+32,indexing='ij')
for i,case in enumerate(['A','B'],1):
    ax=fig.add_subplot(1,2,i,projection='3d')
    grid=grids[case][16:32,:,8:23]
    colors=np.empty(grid.shape+(4,));colors[:]=to_rgba(SI);colors[grid==2]=to_rgba(SIGE)
    assert set(np.unique(grid))<={0,1,2}
    ax.voxels(X,Y,Z,grid!=0,facecolors=colors,edgecolor='#eeeeee',linewidth=.12,shade=True)
    ax.set_title(f"{case} / {summary[case]['release_time_s']:.0f} s",fontsize=13,fontweight='bold')
    ax.set_xlabel('X (nm)');ax.set_ylabel('Y (nm)');ax.set_zlabel('Z (nm)')
    ax.set_xlim(-32,32);ax.set_ylim(-72,72);ax.set_zlim(32,92);ax.set_box_aspect((64,144,60));ax.view_init(elev=24,azim=-52)
fig.legend(handles=legend[:2],loc='lower center',bbox_to_anchor=(.5,.055),ncol=2,frameon=False)
fig.text(.06,.015,'Actual 4 nm material cells, same view and scale. Geometric release only; mechanical stability and electrical behavior are not solved.',fontsize=9,color=GRAY)
fig.savefig(OUT/'03_release_roi_3d.png',dpi=160);plt.close(fig)
(OUT/'render_environment.json').write_text(json.dumps(dict(python=platform.python_version(),matplotlib=matplotlib.__version__,numpy=np.__version__,
    source='Stored section arrays, final_state.npz and summary.json; no model recomputation or generative imagery'),indent=2),encoding='utf-8')
print('Rendered 3 figures from actual stored voxel results.')
