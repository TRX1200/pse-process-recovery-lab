"""Plot stored TSV material arrays and interface metrics, without recomputation."""
from pathlib import Path
import argparse
import json
import platform
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm, to_rgba
from matplotlib.patches import Patch

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
    root=parser.parse_args().data_dir.resolve();out=root/'figures';out.mkdir(exist_ok=True)
    summary=json.loads((root/'data/summary.json').read_text(encoding='utf-8'))
    geometry=json.loads((root/'data/measurement_geometry.json').read_text(encoding='utf-8'))
    with np.load(root/'data/sections.npz',allow_pickle=False) as data:
        sections={k:data[k] for k in data.files}
    grids={}
    for case in ['A','B']:
        with np.load(root/f'data/{case}/final_state.npz',allow_pickle=False) as data:
            grids[case]=data['material']
    blue='#0072B2';orange='#B74500';teal='#176F60';gray='#526171'
    labels=['A / aligned','B / +8 um X offset']
    metadata=dict(label='Personal learning simulation; AI agent executed; no wafer/equipment/ATE measurement',
        source_files=['data/summary.json','data/sections.npz','data/A/final_state.npz','data/B/final_state.npz'],
        transformations=['nm to um: divide by 1000','nm^2 to um^2: divide by 1e6','ohm to milliohm: multiply by 1000'],
        uncertainty='Deterministic single 1 um grid; no statistical interval or mesh-convergence claim',
        versions=dict(python=platform.python_version(),numpy=np.__version__,matplotlib=matplotlib.__version__),figures=[])
    def save(fig,name,description):
        fig.text(.06,.025,'LEARNING SIMULATION  |  1 um material voxels  |  deterministic  |  no calibrated contact or reliability model',fontsize=9,color=gray)
        fig.savefig(out/name,dpi=180,facecolor='white')
        metadata['figures'].append(dict(file=name,description=description,size_inches=fig.get_size_inches().tolist(),dpi=180))
        plt.close(fig)
    with plt.rc_context({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,
        'axes.titleweight':'bold','axes.labelcolor':'#26384a','axes.edgecolor':'#98a4b3','grid.alpha':.2}):
        fig,axes=plt.subplots(1,2,figsize=(12,6.5),sharex=True,sharey=True)
        fig.subplots_adjust(left=.075,right=.975,bottom=.23,top=.76,wspace=.20)
        fig.suptitle('TSV | Cu face overlap at the upper bond interface',x=.06,ha='left',fontsize=18,fontweight='bold',y=.96)
        fig.text(.06,.895,'Same material-grid process flow; only upper-die X offset changes. Interface at Z = 37 um.',fontsize=11,color=gray)
        cmap=ListedColormap(['#F1F3F5',blue,orange,teal]);norm=BoundaryNorm(np.arange(5)-.5,4)
        for ax,case,label in zip(axes,['A','B'],labels):
            lower=sections[case+'_lower'];upper=sections[case+'_upper']
            classes=lower.astype(np.uint8)+2*upper.astype(np.uint8)
            ax.imshow(classes.T,origin='lower',extent=(-20,20,-20,20),interpolation='nearest',cmap=cmap,norm=norm,aspect='equal')
            s=summary[case]
            ax.set(title=f'{label}\nOverlap {s["bond_overlap_nm2"]/1e6:.0f} um2 / {s["overlap_of_lower_pad_pct"]:.2f}%',
                   xlabel='X (um)',xlim=(-20,20),ylim=(-20,20))
            ax.set_xticks([-20,-10,0,10,20]);ax.set_yticks([-20,-10,0,10,20])
        axes[0].set_ylabel('Y (um)')
        legend=[Patch(facecolor=c,label=t) for c,t in zip(cmap.colors,['Neither Cu face','Lower only','Upper only','Both / contact overlap'])]
        fig.legend(handles=legend,ncol=4,loc='lower center',bbox_to_anchor=(.5,.115),frameon=False,fontsize=10)
        fig.text(.06,.075,'Each displayed cell is 1 um2. Lower plane Z=36.5 um; upper plane Z=37.5 um. No smoothing.',fontsize=9,color=gray)
        save(fig,'01_bond_overlap.png','Actual adjacent-slice Cu footprints at Z=37 um, shared XY axes and categorical colors. A: 156 um2 overlap; B: 48 um2. Gray means neither slice has Cu, not necessarily a material void.')

        fig,axes=plt.subplots(1,2,figsize=(12,6))
        fig.subplots_adjust(left=.08,right=.97,bottom=.25,top=.76,wspace=.32)
        fig.suptitle('TSV | Less overlap, unchanged series-area resistance',x=.06,ha='left',fontsize=18,fontweight='bold',y=.96)
        fig.text(.06,.89,'Both cases remain connected by the 6-neighbor Cu test. This does not establish bond quality.',fontsize=11,color=gray)
        metrics=[('bond_overlap_nm2',1e-6,'Cu overlap area (um2)','01 / Geometric contact overlap'),
                 ('resistance_ohm',1000,'Series-area estimate (mOhm)','02 / Existing reduced resistance model')]
        for ax,(key,scale,ylabel,title) in zip(axes,metrics):
            values=[summary[c][key]*scale for c in ['A','B']]
            bars=ax.bar(['A / 0 um','B / 8 um'],values,color=[blue,orange],width=.52,edgecolor='white',linewidth=1)
            bars[1].set_hatch('//')
            ax.set(title=title,ylabel=ylabel,ylim=(0,max(values)*1.25));ax.grid(axis='y');ax.set_axisbelow(True)
            for bar,value in zip(bars,values):
                ax.text(bar.get_x()+bar.get_width()/2,value+max(values)*.035,f'{value:.3f}' if key=='resistance_ohm' else f'{value:.0f}',ha='center',fontweight='bold')
        fig.text(.06,.125,r'$R=\sum_z \rho\,\Delta z/A_z$ uses Cu area in each slice, not the shared face overlap at the interface.',fontsize=11,color=gray)
        fig.text(.06,.075,'Contact constriction and lateral current spreading are absent; equal computed R is not evidence of equal physical R.',fontsize=10,color=gray)
        save(fig,'02_overlap_and_resistance.png','Zero-baseline A/B bars from summary.json. Geometric overlap decreases while the existing 1D series-area estimate stays equal. The two panels use different physical quantities and are labeled separately.')

        fig=plt.figure(figsize=(12,7))
        fig.suptitle('TSV | Actual Cu voxels after ideal die stacking',x=.06,ha='left',fontsize=18,fontweight='bold',y=.96)
        fig.text(.06,.90,'Cu only: silicon and oxide hidden for display. Identical physical scales and orthographic cameras.',fontsize=10,color=gray)
        fig.subplots_adjust(left=.035,right=.94,bottom=.21,top=.83,wspace=.12)
        nx,ny,nz=geometry['shape'];dx=geometry['dx_nm']/1000
        X,Y,Z=np.meshgrid((np.arange(nx+1)-nx/2)*dx,(np.arange(ny+1)-ny/2)*dx,np.arange(nz+1)*dx,indexing='ij')
        shift=int(geometry['interface_z_nm']/geometry['dx_nm'])
        for i,case in enumerate(['A','B']):
            ax=fig.add_subplot(1,2,i+1,projection='3d',proj_type='ortho')
            grid=grids[case];face=np.empty(grid.shape+(4,));face[:]=to_rgba(blue);face[:,:,shift:]=to_rgba(orange)
            ax.voxels(X,Y,Z,grid==7,facecolors=face,edgecolor='#DCE2E8',linewidth=.13,shade=True)
            ax.set(title=labels[i],xlim=(-20,20),ylim=(-20,20),zlim=(0,80),xlabel='X (um)',ylabel='Y (um)',zlabel='Z (um)')
            ax.set_xticks([-10,0,10]);ax.set_yticks([-10,0,10]);ax.set_zticks([0,20,40,60,80])
            ax.set_box_aspect((40,40,80));ax.view_init(elev=22,azim=-58);ax.tick_params(labelsize=8)
        fig.legend(handles=[Patch(facecolor=blue,label='Lower die + bond continuation'),Patch(facecolor=orange,label='Upper die')],
                   ncol=2,loc='lower center',bbox_to_anchor=(.5,.12),frameon=False,fontsize=10)
        fig.text(.06,.08,'B clips outer Si/oxide at the domain boundary; no Cu cells are clipped. Every Cu voxel is retained in this view.',fontsize=9,color=gray)
        save(fig,'03_copper_voxels.png','Stored Cu voxels only, all included. Other materials are explicitly hidden. Lower Cu plus bond continuation is blue and upper-die Cu orange; common axes, orthographic view, no vertical exaggeration. Interface plan views provide the quantitative overlap.')
    (out/'figure_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps(metadata,indent=2))

if __name__=='__main__':main()
