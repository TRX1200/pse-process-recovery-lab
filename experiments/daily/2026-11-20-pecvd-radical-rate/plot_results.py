"""Plot saved numerical arrays/triangles; no smoothing or synthetic surfaces."""
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parent)
    root = parser.parse_args().data_dir.resolve()
    figures = root / 'figures'
    figures.mkdir(exist_ok=True)
    runs = {key: json.loads(gzip.decompress((root/'data'/f'{key}.json.gz').read_bytes())) for key in ['A','B']}
    palette = {'A':'#0072B2', 'B':'#D55E00'}
    labels = {'A':'A | radical coefficient 0.8 nm/s', 'B':'B | radical coefficient 1.2 nm/s'}
    style = {'A':('-', 'o'), 'B':('--', 's')}
    metadata = dict(label='Personal learning simulation; agent executed; not wafer/equipment measurements',
        data='data/A.json.gz and data/B.json.gz', smoothing='none',
        line_segments='Connect saved samples for visual guidance, not extra solver time steps',
        figures=[], versions=dict(python=platform.python_version(),numpy=np.__version__,matplotlib=matplotlib.__version__))

    def save(fig, name, description):
        fig.text(.025,.025,'LEARNING SIMULATION  |  ViennaPS 4.6.2  |  grid 20 nm  |  seed 42  |  no physical calibration',fontsize=9,color='#4b5563')
        fig.savefig(figures/name,dpi=180,facecolor='white')
        metadata['figures'].append(dict(file=name,description=description,size_inches=fig.get_size_inches().tolist(),dpi=180))
        plt.close(fig)

    with plt.rc_context({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.titleweight':'bold','axes.labelcolor':'#26384a','axes.edgecolor':'#98a4b3','grid.alpha':.22}):
        fig,axes=plt.subplots(1,2,figsize=(12,5.5))
        fig.subplots_adjust(left=.075,right=.975,bottom=.18,top=.76,wspace=.30)
        fig.suptitle('PECVD | More radical growth does not imply a flatter trench',x=.075,ha='left',fontsize=18,fontweight='bold',y=.96)
        fig.text(.075,.88,'20 s deposition; only the radical growth coefficient changes. All axes are linear.',fontsize=11,color='#4b5563')
        first=runs['A']['frames'][0]['section']
        x=np.asarray(first['x_nm']); initial=np.asarray(first['z_nm'])
        axes[0].plot(x,initial,color='#6b7280',ls=':',lw=2,label='Initial surface')
        for key,run in runs.items():
            z=np.asarray(run['frames'][-1]['section']['z_nm'])
            line,mark=style[key]
            axes[0].plot(x,z,color=palette[key],ls=line,lw=2,label=labels[key])
            axes[1].plot(x,z-initial,color=palette[key],ls=line,lw=2,marker=mark,markevery=8,ms=4,label=key)
        axes[0].set(xlabel='X at Y = 0 (nm)',ylabel='Highest surface Z (nm)',title='01 / Central section',ylim=(-215,120))
        max_advance=max(np.max(np.asarray(run['frames'][-1]['section']['z_nm'])-initial) for run in runs.values())
        axes[1].set(xlabel='X at Y = 0 (nm)',ylabel='Vertical surface advance (nm)',title='02 / Final Z minus initial Z',ylim=(0,1.12*max_advance))
        axes[1].text(.50,.60,'Edge peaks reflect\na shifted intersection.\nNot local film thickness.',ha='center',transform=axes[1].transAxes,fontsize=9,color='#4b5563')
        for ax in axes: ax.grid(); ax.legend(fontsize=9,loc='upper left')
        save(fig,'01_surface_sections.png','Same central cut at Y=0: initial/A/B highest intersections and their vertical advances. 81 saved sample positions; not a film thickness map.')

        fig,axes=plt.subplots(1,2,figsize=(12,5.5))
        fig.subplots_adjust(left=.075,right=.975,bottom=.18,top=.76,wspace=.28)
        fig.suptitle('PECVD | Top and center advance at different rates',x=.075,ha='left',fontsize=18,fontweight='bold',y=.96)
        fig.text(.075,.88,'Saved solver frames every 5 s. Lines join samples; no uncertainty band or convergence claim.',fontsize=11,color='#4b5563')
        for key,run in runs.items():
            frames=[run['frames'][0]]+[f for f in run['frames'] if f['stage']=='pecvd']
            times=[f['at'] for f in frames]; baseline=frames[0]['metrics']
            line,mark=style[key]
            for ax,metric,title in zip(axes,['top_z_nm','center_z_nm'],['03 / Top probe: X=258, Y=0 nm','04 / Center probe: X=0, Y=0 nm']):
                values=[f['metrics'][metric]-baseline[metric] for f in frames]
                ax.plot(times,values,color=palette[key],ls=line,marker=mark,lw=2,label=key)
                ax.annotate(f'{key}  {values[-1]:.2f} nm',(times[-1],values[-1]),xytext=(-8,7),textcoords='offset points',ha='right',color=palette[key],fontsize=10)
                ax.set(title=title,xlabel='Process time (s)',ylabel='Vertical surface advance (nm)',xlim=(-.5,21),ylim=(0,36))
        for ax in axes: ax.grid(); ax.legend(loc='upper left')
        save(fig,'02_probe_time_series.png','Top surface advance and bottom-center advance across saved time frames, same Y limits and no fabricated uncertainty. Read full values from time_series.csv.')

        fig=plt.figure(figsize=(12,6))
        fig.suptitle('PECVD | Final computed 3D outer surfaces',x=.055,ha='left',fontsize=18,fontweight='bold',y=.97)
        fig.text(.055,.90,'Actual native triangles; orthographic view; common axes and height color scale. No mesh decimation.',fontsize=10,color='#4b5563')
        norm=colors.Normalize(vmin=-200,vmax=40); cmap=plt.get_cmap('cividis')
        for index,(key,run) in enumerate(runs.items()):
            ax=fig.add_subplot(1,2,index+1,projection='3d',proj_type='ortho')
            layer=run['frames'][-1]['layers'][-1]
            n=np.asarray(layer['positions_nm']).reshape(-1,3);t=np.asarray(layer['triangles']).reshape(-1,3)
            tri=n[t]
            mesh=Poly3DCollection(tri,facecolors=cmap(norm(tri[:,:,2].mean(axis=1))),edgecolor='none')
            ax.add_collection3d(mesh)
            ax.set(xlim=(-300,300),ylim=(-200,200),zlim=(-210,50),xlabel='X (nm)',ylabel='Y (nm)',zlabel='Z (nm)',title=labels[key])
            ax.set_box_aspect((600,400,260));ax.view_init(elev=29,azim=-62);ax.tick_params(labelsize=8)
        fig.subplots_adjust(left=.025,right=.88,bottom=.12,top=.80,wspace=.08)
        cax=fig.add_axes([.925,.25,.014,.46])
        fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=cax,label='Absolute surface Z (nm)')
        save(fig,'03_native_surfaces.png','Actual final SiO2 outer surface triangle meshes. Color is absolute Z, not film thickness or physical roughness. Shared dimensions and orthographic camera; sidewalls can occlude other faces.')
    (figures/'figure_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps(metadata,indent=2))

if __name__ == '__main__': main()
