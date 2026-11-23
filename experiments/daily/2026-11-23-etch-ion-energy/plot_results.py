"""Render only saved Etch samples and native triangles, without smoothing."""
from pathlib import Path
import argparse
import csv
import gzip
import json
import platform
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import colors
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
    root=parser.parse_args().data_dir.resolve()
    figures=root/'figures';figures.mkdir(exist_ok=True)
    runs={k:json.loads(gzip.decompress((root/'data'/f'{k}.json.gz').read_bytes())) for k in ['A','B']}
    with (root/'data/time_series.csv').open(encoding='utf-8',newline='') as f:
        series=list(csv.DictReader(f))
    palette={'A':'#0072B2','B':'#B74500'}
    labels={'A':'A / 100 eV','B':'B / 150 eV'}
    styles={'A':('-', 'o'),'B':('--','s')}
    meta=dict(label='Personal learning simulation; agent executed; not wafer or equipment measurements',
        raw_sources=['data/A.json.gz','data/B.json.gz','data/time_series.csv'],
        transformation='Highest vertical intersections; recession = initial Z minus final Z; no smoothing',
        line_segments='Connect stored samples only; not additional solver steps',
        uncertainty='Single seed and grid; no confidence interval or physical calibration',
        versions=dict(python=platform.python_version(),numpy=np.__version__,matplotlib=matplotlib.__version__),figures=[])
    def save(fig,name,description):
        fig.text(.06,.025,'LEARNING SIMULATION  |  ViennaPS 4.6.2  |  grid 20 nm  |  seed 42  |  not calibrated equipment data',fontsize=9,color='#485260')
        fig.savefig(figures/name,dpi=180,facecolor='white')
        meta['figures'].append(dict(file=name,description=description,size_inches=fig.get_size_inches().tolist(),dpi=180))
        plt.close(fig)

    with plt.rc_context({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
        'axes.spines.right':False,'axes.titleweight':'bold','axes.labelcolor':'#26384a',
        'axes.edgecolor':'#98a4b3','grid.alpha':.2}):
        fig,axes=plt.subplots(1,2,figsize=(12,5.8))
        fig.subplots_adjust(left=.075,right=.975,bottom=.24,top=.75,wspace=.30)
        fig.suptitle('Etch | Ion energy and the computed opening profile',x=.075,ha='left',fontsize=18,fontweight='bold',y=.96)
        fig.text(.075,.88,'4 s / fixed incident fluxes. Only mean ion energy changes: 100 to 150 eV.',fontsize=11,color='#485260')
        section=runs['A']['frames'][0]['section']
        x=np.array(section['x_nm']);initial=np.array(section['z_nm'])
        inside=np.abs(x)<=80
        axes[0].plot(x,initial,color='#666666',ls=':',lw=2,label='Initial surface')
        for key,run in runs.items():
            final=np.array(run['frames'][-1]['section']['z_nm'])
            line,mark=styles[key]
            axes[0].plot(x,final,color=palette[key],ls=line,lw=2,label=labels[key])
            axes[1].plot(x[inside],(initial-final)[inside],color=palette[key],ls=line,
                         marker=mark,ms=4,lw=2,label=labels[key])
        axes[0].set(title='01 / Full central section',xlabel='X at Y = 0 (nm)',ylabel='Highest surface Z (nm)')
        axes[0].margins(y=.18)
        axes[1].set(title='02 / Inside opening: |X| <= 80 nm',xlabel='X at Y = 0 (nm)',ylabel='Vertical recession (nm)')
        axes[1].set_ylim(bottom=0)
        for position in [0,70]: axes[1].axvline(position,color='#7f8997',lw=.8,ls=':')
        fig.text(.075,.105,'Mask is included outside the opening. Right panel is an explicitly cropped view of the same saved section.',fontsize=9,color='#485260')
        for ax in axes: ax.grid();ax.legend(fontsize=9,loc='lower left' if ax==axes[0] else 'lower center')
        save(fig,'01_surface_sections.png','Full Y=0 highest-intersection section, including numerical mask; right panel shows recession only within |X|<=80 nm. Saved samples are connected, not smoothed. Dotted vertical lines locate X=0 and X=70 nm probes.')

        fig,axes=plt.subplots(1,2,figsize=(12,5.8))
        fig.subplots_adjust(left=.075,right=.975,bottom=.24,top=.75,wspace=.28)
        fig.suptitle('Etch | Center and near-edge recession over time',x=.075,ha='left',fontsize=18,fontweight='bold',y=.96)
        fig.text(.075,.88,'Five stored frames per case / common vertical scale / depth positive downward from initial Z.',fontsize=11,color='#485260')
        highest=max(float(r[m]) for r in series if r['case'] in ['A','B'] for m in ['center_recession_nm','near_edge_recession_nm'])
        for key in ['A','B']:
            records=[r for r in series if r['case']==key]
            time=[float(r['time_s']) for r in records]
            line,mark=styles[key]
            for ax,metric,title in zip(axes,['center_recession_nm','near_edge_recession_nm'],['03 / Center: X=0, Y=0 nm','04 / Near edge: X=70, Y=0 nm']):
                values=[float(r[metric]) for r in records]
                ax.plot(time,values,color=palette[key],ls=line,marker=mark,lw=2,label=f'{labels[key]}: {values[-1]:.2f} nm')
                ax.set(title=title,xlabel='Process time (s)',ylabel='Vertical recession (nm)',xlim=(-.15,4.2),ylim=(0,highest*1.18))
        for ax in axes: ax.grid();ax.legend(loc='upper left',fontsize=9)
        fig.text(.075,.105,'1 s is the output interval. Internal adaptive steps are not plotted; no uncertainty interval was estimated.',fontsize=9,color='#485260')
        save(fig,'02_probe_time_series.png','Center and near-edge vertical recession computed from raw native triangle intersections, with a common zero baseline and Y range. Lines connect actual output times 0,1,2,3,4 s.')

        surfaces={}
        for key,run in runs.items():
            layer=run['frames'][-1]['layers'][-1]
            nodes=np.asarray(layer['positions_nm']).reshape(-1,3)
            tri=np.asarray(layer['triangles']).reshape(-1,3)
            surfaces[key]=(nodes,tri)
        all_nodes=np.concatenate([s[0] for s in surfaces.values()])
        lower=all_nodes.min(axis=0);upper=all_nodes.max(axis=0)
        norm=colors.Normalize(vmin=float(lower[2]),vmax=float(upper[2]));cmap=plt.get_cmap('cividis')
        fig=plt.figure(figsize=(12,6))
        fig.suptitle('Etch | Final native 3D surface meshes',x=.055,ha='left',fontsize=18,fontweight='bold',y=.97)
        fig.text(.055,.90,'All outer-surface triangles / orthographic view / common physical aspect and height color scale.',fontsize=10,color='#485260')
        for index,key in enumerate(['A','B']):
            ax=fig.add_subplot(1,2,index+1,projection='3d',proj_type='ortho')
            nodes,triangles=surfaces[key];tri=nodes[triangles]
            ax.add_collection3d(Poly3DCollection(tri,facecolors=cmap(norm(tri[:,:,2].mean(axis=1))),edgecolor='none'))
            ax.set(xlim=(lower[0],upper[0]),ylim=(lower[1],upper[1]),zlim=(lower[2]-5,upper[2]+5),
                   xlabel='X (nm)',ylabel='Y (nm)',zlabel='Z (nm)',title=labels[key])
            ax.set_box_aspect((upper-lower)+[0,0,10]);ax.view_init(elev=33,azim=-62);ax.tick_params(labelsize=8)
        fig.subplots_adjust(left=.025,right=.88,bottom=.15,top=.80,wspace=.08)
        cax=fig.add_axes([.925,.27,.014,.43])
        fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=cax,label='Absolute surface Z (nm)')
        fig.text(.055,.105,'Outer envelope includes mask outside the opening. Mesh/ray irregularity is not predicted physical roughness.',fontsize=9,color='#485260')
        save(fig,'03_native_surfaces.png','Actual final outer native meshes; every triangle included. Identical orthographic camera, coordinate limits, box aspect and absolute-height color scale. Occlusion is inherent; quantitative values are provided in sections and CSV.')
    (figures/'figure_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps(meta,indent=2))

if __name__=='__main__': main()
