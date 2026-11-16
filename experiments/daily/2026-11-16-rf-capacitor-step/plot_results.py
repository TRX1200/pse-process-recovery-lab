"""Render numerical CSV results; no synthetic artwork or fitted curves."""
from pathlib import Path
import csv
import json
import platform

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / 'figures'
OUT.mkdir(exist_ok=True)
with (HERE / 'data/time_series.csv').open(encoding='utf-8-sig', newline='') as file:
    records = list(csv.DictReader(file))
summary = json.loads((HERE / 'data/summary.json').read_text(encoding='utf-8'))
series = {case: {key: np.array([float(r[key]) for r in records if r['case'] == case])
                 for key in records[0] if key != 'case'} for case in ('A', 'B')}
assert len(series['A']['t_s']) == len(series['B']['t_s']) == 201
assert np.array_equal(series['A']['density_1e15_m3'], series['B']['density_1e15_m3'])

NAVY, ORANGE, TEAL, GRAY = '#243c57', '#c35e27', '#217a7b', '#b3bfc9'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.labelcolor': NAVY, 'text.color': NAVY, 'axes.titleweight': 'bold',
    'axes.edgecolor': '#bcc6ce', 'grid.color': '#e3e8ed', 'grid.alpha': 0.8,
    'savefig.facecolor': 'white'})

fig, axes = plt.subplots(3, 1, figsize=(12.8, 9), sharex=True,
                         gridspec_kw={'height_ratios': [0.8, 1.3, 1.3]})
fig.subplots_adjust(left=.09, right=.97, top=.84, bottom=.11, hspace=.23)
fig.suptitle('01 / One capacitor change, one identical plasma-load history',
             x=.09, y=.965, ha='left', fontsize=18, fontweight='bold')
fig.text(.09, .917, 'A: hold Cp = 500 pF     |     B: step Cp from 500 to 600 pF at t = 10 s', fontsize=12)
fig.text(.09, .882, '13.56 MHz  /  300 W forward  /  Cs = 120 pF  /  seed 42  /  samples every 0.1 s', fontsize=10, color='#586b7d')
for ax, key, label in zip(axes, ['cp_pf', 'reflected_pct', 'bulk_w'],
                          ['Shunt Cp (pF)', 'Reflected power (%)', 'Plasma-bulk power (W)']):
    ax.axvspan(10, 20, color='#eef3f6', zorder=0)
    ax.axvline(10, color='#8b9baa', lw=1, ls=':')
    for case, color, ls in [('B', ORANGE, '-'), ('A', NAVY, '--')]:
        ax.plot(series[case]['t_s'], series[case][key], color=color,
                lw=2 if case == 'B' else 1.65, ls=ls, label=case,
                drawstyle='steps-post' if key == 'cp_pf' else 'default')
    ax.set_ylabel(label)
    ax.grid(axis='y'); ax.set_xlim(0, 20)
axes[0].set_ylim(480, 635)
axes[0].legend(loc='upper left', ncol=2, frameon=False)
axes[0].text(10.35, 620, 'Comparison window: 10-20 s', fontsize=10)
axes[1].set_ylim(0, 100)
axes[2].set_ylim(bottom=0)
axes[-1].set_xlabel('Time (s)')
fig.text(.09, .035, 'Educational, quasi-static equivalent circuit. The plasma state is prescribed; this is not measured tool data.',
         fontsize=9, color='#586b7d')
fig.savefig(OUT / '01_capacitor_step.png', dpi=160)
plt.close(fig)

means = {c: summary[c]['time_mean_10_to_20_s'] for c in ('A', 'B')}
channels = [('reflected_w', 'Reflected', '#b3bfc9'), ('coil_loss_w', 'Coil loss', NAVY),
            ('capacitor_loss_w', 'Capacitor loss', ORANGE), ('bulk_w', 'Plasma bulk', TEAL)]
fig = plt.figure(figsize=(12.8, 8.8))
grid = fig.add_gridspec(2, 1, height_ratios=[1.25, 1], left=.18, right=.95, top=.78, bottom=.13, hspace=.60)
ax = fig.add_subplot(grid[0]); detail = fig.add_subplot(grid[1])
fig.suptitle('02 / Where did the extra accepted power go?',
             x=.07, y=.965, ha='left', fontsize=20, fontweight='bold')
fig.text(.07, .91, 'Time means over 10-20 s. Forward power stays at 300 W in both cases.', fontsize=12)
fig.text(.07, .865, 'Reflection fell by 6.31 percentage points, but most extra accepted power became coil loss.',
         fontsize=11, color='#586b7d')
left = np.zeros(2)
for key, label, color in channels:
    values = np.array([means[c][key] for c in ('A', 'B')])
    ax.barh([1, 0], values, left=left, color=color, height=.48, label=label)
    if key != 'capacitor_loss_w':
        for i, y in enumerate([1, 0]):
            ax.text(left[i] + values[i]/2, y, f'{values[i]:.1f}', ha='center', va='center',
                    fontsize=10, color=NAVY if key == 'reflected_w' else 'white', fontweight='bold')
    left += values
assert np.allclose(left, 300, rtol=0, atol=1e-8)
ax.set_yticks([1, 0], ['A / Cp 500 pF', 'B / Cp 600 pF'])
ax.set_xlim(0, 300); ax.set_xlabel('Power allocation (W)'); ax.set_axisbelow(True); ax.grid(axis='x')
ax.legend(ncol=4, loc='lower center', bbox_to_anchor=(.5, 1.02), frameon=False, fontsize=10)
delta = {key: means['B'][key] - means['A'][key] for key in ['bulk_w', 'coil_loss_w', 'capacitor_loss_w']}
accepted_delta = means['B']['accepted_w'] - means['A']['accepted_w']
assert np.isclose(sum(delta.values()), accepted_delta, rtol=0, atol=1e-8)
detail.set_title(f'Additional accepted power: +{accepted_delta:.2f} W', loc='left', fontsize=13, pad=15)
keys = ['coil_loss_w', 'bulk_w', 'capacitor_loss_w']
values = [delta[key] for key in keys]
detail.barh([2, 1, 0], values, color=[NAVY, TEAL, ORANGE], height=.56)
detail.set_yticks([2, 1, 0], ['Coil loss', 'Plasma bulk', 'Capacitor loss'])
for y, value in zip([2, 1, 0], values):
    detail.text(value+.25, y, f'+{value:.2f} W  ({100*value/accepted_delta:.1f}%)', va='center', fontsize=10)
detail.set_xlim(0, 19); detail.set_xlabel('B minus A (W)'); detail.grid(axis='x'); detail.set_axisbelow(True)
fig.text(.07, .035, 'Single prescribed stochastic realization (seed 42). No optimization, device prediction, or physical validation.',
         fontsize=9, color='#586b7d')
fig.savefig(OUT / '02_power_budget.png', dpi=160)
plt.close(fig)
(OUT / 'render_environment.json').write_text(json.dumps({
    'python': platform.python_version(), 'matplotlib': matplotlib.__version__,
    'numpy': np.__version__, 'input': 'data/time_series.csv and data/summary.json',
    'note': 'Rendering environment only; numerical simulation versions are in data/result.json.'
}, indent=2), encoding='utf-8')
print('Rendered two figures from the stored numerical results.')
