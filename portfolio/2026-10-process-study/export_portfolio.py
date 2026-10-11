"""Export portfolio figures and traceable tables from existing solved examples.

No solver output is synthesized or smoothed. Run with Python + matplotlib + numpy.
"""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'sim_app/frontend/public'
OUT = HERE / 'ready-to-use'
OUT.mkdir(exist_ok=True)
(OUT / 'data').mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
from native_lab.geometry import intersections

FONT = Path('C:/Windows/Fonts/malgun.ttf')
if FONT.exists():
    font_manager.fontManager.addfont(str(FONT))
    plt.rcParams['font.family'] = [font_manager.FontProperties(fname=FONT).get_name(), 'DejaVu Sans']
else:
    raise RuntimeError('Install a Korean font and set FONT before rendering.')
plt.rcParams.update({'font.size': 11, 'axes.titlesize': 13, 'axes.labelsize': 11,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.edgecolor': '#ABB7BF', 'axes.labelcolor': '#233747',
                     'xtick.color': '#536472', 'ytick.color': '#536472',
                     'text.color': '#233747', 'svg.fonttype': 'path',
                     'axes.unicode_minus': False, 'savefig.facecolor': 'white'})
NAVY, ORANGE, TEAL, GREY = '#274F70', '#BD6137', '#287E88', '#AAB6BF'
COLORS = [NAVY, ORANGE]
GIT = 'https://github.com/TRX1200/pse-process-recovery-lab'
manifest = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'source_kind': 'previously solved examples; re-exported, not rerun',
            'physical_validation': 'not performed', 'sources': {}, 'figures': [],
            'renderer': {'python': platform.python_version(), 'matplotlib': matplotlib.__version__, 'numpy': np.__version__}}
native_rows, surface_rows, rf_rows, curve_rows = [], [], [], []
checks = []


def load(relative):
    path = SOURCE / relative
    dst = OUT / 'data' / path.name
    shutil.copyfile(path, dst)
    manifest['sources'][relative] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'copy': str(dst.relative_to(OUT))}
    result = json.loads(path.read_text(encoding='utf-8'))
    if 'frames' in result:
        for frame in result['frames']:
            for metric, value in frame['metrics'].items():
                # The saved initial 0/0 coverage placeholder is not a valid ratio.
                if metric == 'bottom_top_pct' and frame['metrics']['top_film_nm'] <= 1e-6:
                    value = None
                native_rows.append(dict(case=path.stem, at=frame['at'], axis_unit=result['axis_unit'],
                                        metric=metric, value=value, run_hash=result['run_hash']))
            for layer in frame['layers']:
                for index, contour in enumerate(layer['paths_nm']):
                    for point, (x, y) in enumerate(contour):
                        assert np.isfinite([x, y]).all()
                        surface_rows.append(dict(case=path.stem, at=frame['at'], material=layer['material'],
                                                 contour=index, point=point, x_nm=x, y_nm=y))
            outer = frame['layers'][-1]['paths_nm']
            centre = max(intersections(outer, 0, 0))
            m = frame['metrics']
            if result['model'] == 'etch':
                assert abs(max(0, -centre) - m['center_depth_nm']) < 1e-6
            else:
                assert abs(max(0, result['params']['depth_nm'] - max(0, -centre)) - m['bottom_film_nm']) < 1e-6
                if m['top_film_nm'] > 1e-6:
                    assert abs(100*m['bottom_film_nm']/m['top_film_nm'] - m['bottom_top_pct']) < 1e-8
        checks.append(f"{path.name}: all contour coordinates finite; frame centre metrics reconciled")
    return result


def page(number, title, subtitle):
    fig = plt.figure(figsize=(16, 9), facecolor='white')
    fig.text(.055, .948, f'PROCESS STUDY  /  {number:02d}', color=TEAL, fontsize=11, weight='bold')
    fig.text(.055, .892, title, fontsize=24, weight='bold')
    fig.text(.055, .853, subtitle, fontsize=11, color='#657583')
    fig.add_artist(Line2D([.055, .945], [.824, .824], transform=fig.transFigure, color='#CAD4DA', lw=.8))
    fig.text(.055, .035, 'PERSONAL SIMULATION STUDY  |  ViennaPS integration + Python RF model  |  Equipment validation: not performed', fontsize=8, color='#6E7C88')
    fig.text(.945, .035, f'{number:02d}  /  TRX1200', ha='right', fontsize=8, color='#6E7C88')
    return fig


def axes(fig, box, title, xlabel='', ylabel=''):
    ax = fig.add_axes(box)
    ax.set_title(title, loc='left', pad=12, weight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis='y', color='#E5EBEF', lw=.7)
    ax.set_axisbelow(True)
    return ax


def footer(fig, question, observation, limit):
    fig.add_artist(Line2D([.055, .945], [.171, .171], transform=fig.transFigure, color='#CAD4DA', lw=.8))
    fig.text(.055, .134, '질문  '+question, fontsize=12, weight='bold')
    fig.text(.055, .099, '관찰  '+observation, fontsize=11)
    fig.text(.055, .065, '범위  '+limit, fontsize=9, color='#657583')


def save(fig, name):
    for ext in ('png', 'svg'):
        fig.savefig(OUT / f'{name}.{ext}', dpi=200)
    manifest['figures'].append({'file': name, 'pixels': [3200, 1800]})
    plt.close(fig)


def geometry(ax, run, color, floor):
    final = run['frames'][-1]
    if run['model'] == 'ald':
        for layer, face in [(final['layers'][-1], '#E9B995'), (final['layers'][0], '#E4E9ED')]:
            for contour in layer['paths_nm']:
                a = np.asarray(contour)
                if a[0,0] > a[-1,0]: a = a[::-1]
                ax.fill(np.r_[a[:,0], a[-1,0], a[0,0]], np.r_[a[:,1], floor, floor], color=face, lw=0)
        for contour in final['layers'][-1]['paths_nm']:
            a=np.asarray(contour); ax.plot(a[:,0], a[:,1], color=color, lw=1.7)
    else:
        for layer in final['layers']:
            for contour in layer['paths_nm']:
                a=np.asarray(contour)
                if a[0,0] > a[-1,0]: a=a[::-1]
                if layer['material'] == 'Si':
                    ax.fill(np.r_[a[:,0],a[-1,0],a[0,0]],np.r_[a[:,1],floor,floor],color='#E4E9ED',lw=0)
                ax.plot(a[:,0],a[:,1],color=color if layer['material']=='Si' else GREY,lw=1.8)
    for layer in run['frames'][0]['layers']:
        if layer['material']=='Si':
            for contour in layer['paths_nm']:
                a=np.asarray(contour);ax.plot(a[:,0],a[:,1],color='#768590',ls='--',lw=.9)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xlim(-205,205);ax.set_ylim(floor,90 if run['model']=='etch' else 45)
    ax.set_xticks([-200,0,200]);ax.grid(False)


def main():
    ald=[load('native/ald-variant.json'),load('native/ald-reference.json')]
    etch=[load('native/etch-reference.json'),load('native/etch-variant.json')]
    rf=load('rf/coupled-reference.json')
    # 01: one controlled variable, pulse duration.
    fig=page(1,'ALD | 노출 시간과 단차 피복성','Al₂O₃ · TMA 제한 반응 모델  /  200 cycles · 3 Pa · 300 °C · 초기 홈 100 × 600 nm (AR 6)')
    for i,r in enumerate(ald):
        ax=axes(fig,[.06+i*.23,.285,.20,.475],f"{r['params']['pulse_s']*1000:g} ms / cycle",'x (nm)','y (nm)' if i==0 else '')
        geometry(ax,r,COLORS[i],-635)
        m=r['frames'][-1]['metrics']
        fig.text(.16+i*.23,.211,f"상단 {m['top_film_nm']:.1f} nm · 바닥 {m['bottom_film_nm']:.1f} nm",ha='center',fontsize=10,color=COLORS[i])
    fig.text(.065,.187,'점선: 초기 Si · 실선: 계산된 표면 / x, y 동일 축척',fontsize=8,color='#657583')
    ax=axes(fig,[.57,.535,.36,.225],'사이클에 따른 막 두께','ALD cycles','Film thickness (nm)')
    for i,r in enumerate(ald):
        t=[f['at'] for f in r['frames']]
        for key,style,label in [('top_film_nm','-','상단'),('bottom_film_nm','--','바닥')]:
            ax.plot(t,[f['metrics'][key] for f in r['frames']],style,color=COLORS[i],lw=2,label=f"{r['params']['pulse_s']*1000:g} ms · {label}")
    ax.set_ylim(bottom=0);ax.legend(frameon=False,fontsize=9,ncol=2,loc='upper left')
    ax=axes(fig,[.57,.258,.36,.16],'바닥 / 상단 두께비','Thickness ratio (%)','')
    values=[r['frames'][-1]['metrics']['bottom_top_pct'] for r in ald]
    ax.barh([1,0],values,color=COLORS,height=.43)
    ax.set_yticks([1,0],['2 ms','50 ms']);ax.set_xlim(0,112)
    for y,v in zip([1,0],values):ax.text(v+1.3,y,f'{v:.1f}%',va='center',weight='bold')
    footer(fig,'같은 사이클 수라도 전구체 노출 시간이 짧으면 홈 바닥까지 충분히 성장할까?',
           f'2 → 50 ms에서 바닥/상단 두께비 {values[0]:.1f}% → {values[1]:.1f}%. 두께와 피복성을 함께 비교했다.',
           '격자 5 nm · 300 rays/point · seed 20261003. 2 ms 막 두께는 격자보다 얇아 정량 해석에 주의. 완전한 TMA/H₂O 반응은 제외.')
    save(fig,'01_ALD_exposure_conformality')
    # 02: deliberately label the confounded two-factor comparison.
    fig=page(2,'ETCH | 깊이만으로 공정을 판단할 수 있을까?','Si · SF₆/O₂ feature model  /  5 s · 이온 100 eV · 초기 개구 100 nm · 두 조건에서 방향성 n과 O 공급량이 함께 변화')
    labels=['A  n=500 · O=100','B  n=20 · O=20']
    for i,r in enumerate(etch):
        ax=axes(fig,[.06+i*.24,.27,.21,.48],labels[i],'x (nm)','y (nm)' if i==0 else '')
        geometry(ax,r,COLORS[i],-295)
        m=r['frames'][-1]['metrics']
        fig.text(.165+i*.24,.217,f"깊이 {m['center_depth_nm']:.1f} nm · CD {m['width_half_depth_nm']:.1f} nm",ha='center',fontsize=10,color=COLORS[i])
    fig.text(.065,.187,'점선: 초기 형상 · 실선: 계산된 표면 / y > 0: 마스크 / x, y 동일 축척',fontsize=8,color='#657583')
    for j,(key,title,ylabel) in enumerate([('center_depth_nm','중앙 식각 깊이','Depth (nm)'),('width_half_depth_nm','절반 깊이에서의 홈 폭','CD at half depth (nm)')]):
        ax=axes(fig,[.60,.545-j*.29,.33,.205],title,'Etch time (s)',ylabel)
        for i,r in enumerate(etch):
            fs=[f for f in r['frames'] if key!='width_half_depth_nm' or f['at']>0]
            ax.plot([f['at'] for f in fs],[f['metrics'][key] for f in fs],color=COLORS[i],lw=2,marker='o',ms=3,label=labels[i])
        ax.set_ylim(bottom=0);ax.legend(frameon=False,fontsize=9,loc='upper left')
    a,b=[r['frames'][-1]['metrics'] for r in etch]
    footer(fig,'식각이 진행됐다는 사실만으로 원하는 형상을 얻었다고 볼 수 있을까?',
           f"A/B 깊이 {a['center_depth_nm']:.1f}/{b['center_depth_nm']:.1f} nm, CD {a['width_half_depth_nm']:.1f}/{b['width_half_depth_nm']:.1f} nm. 깊이와 측방 확장을 함께 확인했다.",
           'n은 cosⁿθ 방향성 지수, O 단위는 10¹⁵ cm⁻² s⁻¹. 두 변수를 함께 바꾼 비교로 단일 원인 분리는 불가. 격자 5 nm, 실제 거칠기 검증 아님.')
    save(fig,'02_Etch_profile_tradeoff')
    # 03: distinguish reflection from bulk absorption, with an explicit power balance.
    states=[rf[k]['selected'] for k in ('manual','matched')]
    fig=page(3,'RF–PLASMA | 반사 전력 0%가 고효율을 뜻할까?','13.56 MHz · 300 W · Ar 20 mTorr · 350 K · coil Q=100  /  선형 RF 회로와 0D 정상상태 입자·전력 수지 결합')
    ax=axes(fig,[.07,.55,.49,.20],'입력 300 W의 전력 분배','Power (W)','')
    keys=['reflected_w','coil_loss_w','capacitor_loss_w','bulk_w']
    power_colors=['#AAB6BF',ORANGE,'#CEB378',TEAL]
    titles=['반사','코일 손실','커패시터 손실','벌크 흡수']
    left=np.zeros(2)
    for key,color,label in zip(keys,power_colors,titles):
        v=np.array([s['circuit'][key] for s in states])
        ax.barh([1,0],v,left=left,height=.42,color=color,label=label)
        for y,x,w in zip([1,0],left,v):
            if w>22:ax.text(x+w/2,y,f'{w:.1f}',ha='center',va='center',color='white' if color in [TEAL,ORANGE] else '#233747',fontsize=10)
        left+=v
    ax.set_yticks([1,0],['수동 C','재정합 C']);ax.set_xlim(0,305)
    handles,labels=ax.get_legend_handles_labels()
    fig.legend(handles,labels,frameon=False,fontsize=9,ncol=4,loc='center left',bbox_to_anchor=(.065,.473))
    ax=axes(fig,[.70,.55,.23,.20],'평균 전자밀도','',r'$n_e$ ($10^{16}$ m$^{-3}$)')
    v=[s['density_m3']/1e16 for s in states]
    bars=ax.bar([0,1],v,color=COLORS,width=.48);ax.set_xticks([0,1],['수동 C','재정합 C']);ax.set_ylim(0,max(v)*1.25)
    ax.bar_label(bars,fmt='%.2f',padding=4)
    ax=axes(fig,[.07,.265,.49,.15],'수동 C에서 가열과 손실의 교점',r'$n_e$ (m$^{-3}$)','Power (W)')
    curve=rf['balance_curve'];x=10**np.asarray(curve['log10_density'])
    ax.semilogx(x,curve['rf_bulk_w'],color=NAVY,label='회로 벌크 가열',lw=2)
    ax.semilogx(x,curve['loss_w'],color=ORANGE,label='전역 손실',lw=2,ls='--')
    ax.set_xlim(1e15,2e17);ax.set_ylim(0,60)
    ax.scatter(states[0]['density_m3'],states[0]['loss_w'],color=NAVY,s=45,zorder=5)
    ax.legend(frameon=False,fontsize=9,loc='upper left')
    for xval,heat,loss in zip(x,curve['rf_bulk_w'],curve['loss_w']):
        curve_rows.append(dict(density_m3=xval,bulk_heating_w=heat,global_loss_w=loss))
    fig.text(.69,.405,'재정합 후에도 벌크 흡수는',fontsize=13,weight='bold')
    fig.text(.69,.352,f"{states[1]['circuit']['bulk_w']:.2f} W / 300 W",fontsize=22,color=TEAL,weight='bold')
    fig.text(.69,.308,f"벌크 전달 효율 {states[1]['circuit']['bulk_efficiency_pct']:.2f}%",fontsize=13)
    fig.text(.69,.267,f"Tₑ = {states[0]['te_ev']:.2f} eV (두 해에서 동일)",fontsize=11,color='#657583')
    for label,state in zip(['manual','matched'],states):
        c=state['circuit'];residual=c['forward_w']-sum(c[k] for k in keys)
        assert abs(residual)<1e-8
        assert state['power_relative_residual']<1e-8
        assert abs(c['bulk_efficiency_pct']-100*c['bulk_w']/c['forward_w'])<1e-8
        rf_rows.append(dict(state=label,ne_m3=state['density_m3'],Te_eV=state['te_ev'],ion_flux_m2_s=state['ion_flux_m2_s'],
                            **{k:c[k] for k in keys+['cp_pf','cs_pf','reflected_pct','bulk_efficiency_pct','coil_current_rms_a','series_cap_rms_v']},
                            independent_power_residual_w=residual,config_hash=rf['config_hash']))
    checks.append('RF: independently summed forward/reflected/coil/capacitor/bulk powers; global balance residual < 1e-8; efficiency ratio reconciled')
    footer(fig,'RF 정합을 개선하면 전력이 모두 플라즈마에 전달될까?',
           f"반사는 {states[0]['circuit']['reflected_pct']:.2f}% → 약 0%, 밀도는 {v[0]:.2f} → {v[1]:.2f} ×10¹⁶ m⁻³. 재정합 후 코일 손실은 {states[1]['circuit']['coil_loss_w']:.1f} W.",
           'Tₑ 일정은 이 모델의 입자 수지 가정에 따른 결과. 고정 선형 sheath, 점화·공간분포·RF→Etch 직접 연결은 계산하지 않음.')
    save(fig,'03_RF_plasma_power_balance')
    for name,rows in [('native_metrics.csv',native_rows),('native_contours.csv',surface_rows),('rf_power_balance.csv',rf_rows),('rf_density_balance_curve.csv',curve_rows)]:
        with (OUT/'data'/name).open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    manifest['checks']=checks
    manifest['figure_sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in OUT.glob('*.png')}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'figures':len(manifest['figures']),'csv_tables':4,'checks':checks},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
