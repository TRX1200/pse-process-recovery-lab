"""Prescribed initial corrugation, subsequently evolved by ViennaPS physics.

No noise is added to solved frames. Scallops are input geometry, not a simulated
Bosch cycle. Mesh coordinates are um; profile inputs and measurements are nm.
"""
from __future__ import annotations
import math

import numpy as np
from native_lab.geometry import intersections


def vertices_nm(p):
    half = p['pitch_nm']/2
    amplitude, count = p['corrugation_amplitude_nm'], p['corrugation_count']
    step = p['grid_nm']/2
    if p['surface_profile'] == 1:
        xs = np.linspace(-half, half, math.ceil(2*half/step)+1)
        return [(float(x), amplitude*math.cos(2*math.pi*count*x/(2*half))) for x in xs]
    width, depth = p['width_nm'], p['depth_nm']
    ys = np.linspace(0, -depth, math.ceil(depth/step)+1)
    offsets = amplitude*(1-np.cos(2*math.pi*count*ys/depth))/2
    left = [(-width/2-float(a), float(y)) for a,y in zip(offsets,ys)]
    right = [(width/2+float(a), float(y)) for a,y in zip(offsets[::-1],ys[::-1])]
    return [(-half,0), *left, *right, (half,0)]


def make_profile(domain, p):
    import viennaps as ps
    import viennals as ls
    mesh = ls.Mesh()
    for x,y in vertices_nm(p):
        mesh.insertNextNode([x/1000, y/1000, 0])
    for i in range(len(mesh.getNodes())-1):
        mesh.insertNextLine([i,i+1])
    level = ls.Domain(domain.getGrid())
    ls.FromSurfaceMesh(level,mesh).apply()
    domain.insertNextLevelSetAsMaterial(level, ps.Material.Si)


def planar_metrics(paths, pitch):
    # Midpoint sampling avoids double-counting the periodic/reflective ends.
    xs = (np.arange(256)+.5)/256*pitch-pitch/2
    heights = [max(hits) if (hits:=intersections(paths,float(x),0)) else None for x in xs]
    if any(h is None for h in heights):
        return dict(mean_height_nm=None, roughness_rq_nm=None, roughness_ra_nm=None,
                    peak_valley_nm=None)
    h = np.asarray(heights)
    centered = h-h.mean()
    return dict(mean_height_nm=float(h.mean()), roughness_rq_nm=float(np.sqrt(np.mean(centered**2))),
                roughness_ra_nm=float(np.mean(abs(centered))), peak_valley_nm=float(np.ptp(h)))


def sidewall_metrics(paths, depth):
    # Fixed initial-depth window, 10%-90%; remove only a best-fit straight line.
    ys = np.linspace(-.9*depth, -.1*depth, 161)
    walls = [[],[]]
    for y in ys:
        hits = intersections(paths,float(y),1)
        left, right = [x for x in hits if x < 0], [x for x in hits if x >= 0]
        if not left or not right:
            return dict(left_wall_rq_nm=None,right_wall_rq_nm=None)
        walls[0].append(max(left)); walls[1].append(min(right))
    metrics = {}
    for label, values in zip(('left','right'),walls):
        fit = np.polyval(np.polyfit(ys,values,1),ys)
        metrics[label+'_wall_rq_nm'] = float(np.sqrt(np.mean((np.asarray(values)-fit)**2)))
    return metrics
