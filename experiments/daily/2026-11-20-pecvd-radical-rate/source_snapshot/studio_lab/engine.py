"""3D native level sets with a one-way, explicitly uncalibrated Ar ion-flux proxy."""
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from studio_lab import VERSION
from studio_lab.schema import validate, MAX_SURFACE_NODES, MAX_SURFACE_TRIANGLES
from native_lab.engine import environment
from rf_lab.coupled import global_terms, equilibrium


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def plasma_boundary(request):
    if not request['coupled']:
        flux = request['params']['ion_flux'] * 1e19
        return dict(status='independent', ion_flux_m2_s=flux, ion_scale=1., selected=None)
    terms = global_terms(request['rf'], request['gas'])
    solved = equilibrium(request['rf'], terms)
    if solved['status'] == 'no_accepted_root':
        raise ValueError('현재 수동 RF 값에서 Ar 정상상태 해를 찾지 못했습니다. C 값을 직접 조절하거나 RF 연결을 끄세요. 자동 매칭은 실행하지 않습니다.')
    selected = solved['selected']
    flux = selected['ion_flux_m2_s'] if selected else 0.
    if flux > 40e19:
        raise ValueError('Coupled ion flux exceeds the tested feature input range (40 × 10¹⁹ m⁻²s⁻¹)')
    return dict(status=solved['status'], terms=terms, selected=selected,
                roots=solved['roots'], ion_flux_m2_s=flux, ion_scale=flux/1e19)


def heights_at(nodes, triangles, xy):
    """Highest vertical intersection; nm throughout. Vertical faces are skipped."""
    points = np.asarray(nodes, dtype=float)
    faces = points[np.asarray(triangles, dtype=int)]
    a, b, c = faces[:, 0], faces[:, 1], faces[:, 2]
    den = (b[:,1]-c[:,1])*(a[:,0]-c[:,0])+(c[:,0]-b[:,0])*(a[:,1]-c[:,1])
    valid = np.abs(den)>1e-12
    a,b,c,den = a[valid],b[valid],c[valid],den[valid]
    values=[]
    for x,y in xy:
        u=((b[:,1]-c[:,1])*(x-c[:,0])+(c[:,0]-b[:,0])*(y-c[:,1]))/den
        v=((c[:,1]-a[:,1])*(x-c[:,0])+(a[:,0]-c[:,0])*(y-c[:,1]))/den
        hits=(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)
        z=u*a[:,2]+v*b[:,2]+(1-u-v)*c[:,2]
        values.append(float(z[hits].max()) if hits.any() else None)
    return values


def mesh_layer(level, material):
    import viennals as ls
    mesh=ls.Mesh(); ls.ToSurfaceMesh(level, mesh).apply()
    nodes=np.asarray(mesh.getNodes(),dtype=float)*1000
    triangles=np.asarray(mesh.getTriangles(),dtype=int)
    if not len(nodes) or not len(triangles) or not np.isfinite(nodes).all():
        raise RuntimeError('Native surface is empty or nonfinite')
    if len(nodes)>MAX_SURFACE_NODES or len(triangles)>MAX_SURFACE_TRIANGLES:
        raise RuntimeError('3D preview mesh budget exceeded; use a coarser grid')
    return dict(material=material, positions_nm=nodes.round(6).ravel().tolist(),
                triangles=triangles.ravel().tolist())


def capture(domain, p, at, stage):
    import viennaps as ps
    layers=[mesh_layer(level, ps.MaterialMap.toString(domain.getMaterialMap().getMaterialAtIdx(i)))
            for i,level in enumerate(domain.getLevelSets())]
    surface=layers[-1]
    n=np.asarray(surface['positions_nm']).reshape(-1,3)
    t=np.asarray(surface['triangles']).reshape(-1,3)
    x=np.linspace(-p['pitch_nm']*.48,p['pitch_nm']*.48,81)
    cut=heights_at(n,t,[(v,0) for v in x])
    probes=heights_at(n,t,[(0,0),(.43*p['pitch_nm'],0)])
    area=.5*np.linalg.norm(np.cross(n[t[:,1]]-n[t[:,0]],n[t[:,2]]-n[t[:,0]]),axis=1).sum()
    return dict(at=at, stage=stage, layers=layers,
                metrics=dict(center_z_nm=probes[0], top_z_nm=probes[1], surface_area_nm2=float(area),
                             min_z_nm=float(n[:,2].min()),max_z_nm=float(n[:,2].max()),triangles=len(t),nodes=len(n)),
                section=dict(x_nm=x.tolist(),z_nm=cut))


def simulate(payload, output_dir=None, progress=None, on_boundary=None):
    request=validate(payload); p=request['params']; started=time.perf_counter()
    plasma=plasma_boundary(request)
    if on_boundary: on_boundary(plasma)
    import viennaps as ps
    import viennals as ls
    env=environment()
    if (env['viennaps'],env['viennals']) != ('4.6.2','5.8.5'):
        raise RuntimeError('Use pinned native_lab/requirements.txt versions')
    ps.setDimension(3); ls.setDimension(3); ps.setNumThreads(1); ls.setNumThreads(1)
    ps.Length.setUnit('um'); ps.Time.setUnit('s'); ps.Logger.setLogLevel(ps.LogLevel.WARNING)
    domain=ps.Domain(gridDelta=p['grid_nm']/1000,xExtent=p['pitch_nm']/1000,yExtent=p['length_nm']/1000)
    has_etch=request['model']!='pecvd'
    depth=0 if has_etch else p['depth_nm']/1000
    mask=p['mask_nm']/1000 if has_etch else 0
    if request['geometry']=='hole':
        ps.MakeHole(domain,holeRadius=p['width_nm']/2000,holeDepth=depth,maskHeight=mask).apply()
    else:
        ps.MakeTrench(domain,trenchWidth=p['width_nm']/1000,trenchDepth=depth,maskHeight=mask).apply()
    frames=[capture(domain,p,0,'initial')]
    stages=['etch','pecvd'] if request['model']=='etch_pecvd' else [request['model']]
    step=0; clock=0.; handoff=None
    if progress: progress(0,frames[0])
    for stage in stages:
        if stage=='pecvd':
            if has_etch:
                if frames[-1]['layers'][0]['material']!='Mask':
                    raise RuntimeError('Unexpected native material stack before mask strip')
                domain.removeLevelSet(0,True)
                stripped=capture(domain,p,clock,'ideal_strip')
                frames.append(stripped)
            domain.duplicateTopLevelSet(ps.Material.SiO2)
            before=capture(domain,p,clock,'pecvd_start')
            if has_etch:
                preserved=before['layers'][0]==stripped['layers'][0]
                if not preserved: raise RuntimeError('Native geometry handoff failed')
                handoff=dict(si_preserved=preserved,geometry_sha256=digest(stripped['layers']))
            frames.append(before)
            native=ps.TEOSPECVD(p['sticking'],p['radical_rate_nm_s']/1000,
                               p['ion_rate_nm_s']*plasma['ion_scale']/1000,p['ion_exponent'],1.,1.,1.,0.)
            duration=p['duration_s']; active=(p['radical_rate_nm_s']+p['ion_rate_nm_s']*plasma['ion_scale'])>0
        else:
            coeff=ps.SF6O2Etching.defaultParameters()
            coeff.ionFlux=plasma['ion_flux_m2_s']/1e19
            coeff.etchantFlux=p['fluorine_flux'];coeff.passivationFlux=p['oxygen_flux']
            coeff.Ions.meanEnergy=p['energy_ev']; coeff.Ions.sigmaEnergy=10.;coeff.Ions.exponent=p['ion_exponent']
            native=ps.SF6O2Etching(coeff);duration=p['etch_s']
            active=coeff.ionFlux+p['fluorine_flux']+p['oxygen_flux']>0
        for i in range(p['output_steps']):
            if duration>0 and active:
                process=ps.Process(domain,native,duration/p['output_steps'])
                ray=ps.RayTracingParameters();ray.raysPerPoint=p['rays_per_point'];ray.useRandomSeeds=False
                ray.rngSeed=p['seed']+step;ray.maxReflections=10000;ray.maxBoundaryHits=1000
                process.setParameters(ray)
                adv=ps.AdvectionParameters();adv.timeStepRatio=.4999;adv.spatialScheme=ps.SpatialScheme.ENGQUIST_OSHER_1ST_ORDER
                process.setParameters(adv)
                if stage=='etch':
                    coverage=ps.CoverageParameters();coverage.maxIterations=30;coverage.tolerance=1e-4
                    process.setParameters(coverage)
                process.apply()
            step+=1
            frames.append(capture(domain,p,clock+duration*(i+1)/p['output_steps'],stage))
            if progress: progress(step/(len(stages)*p['output_steps']),frames[-1])
        clock+=duration
    source_paths=[Path(__file__),Path(__file__).with_name('schema.py'),Path(__file__).parents[1]/'rf_lab'/'coupled.py',Path(__file__).parents[1]/'rf_lab'/'model.py',Path(__file__).parents[1]/'sim_app'/'models'/'etch.py']
    identity=dict(request=request,version=VERSION,environment=env,
                  sources={str(path.relative_to(Path(__file__).parents[1])):hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths})
    result=dict(format='studio-3d-run-v1',model=request['model'],request=request,run_hash=digest(identity),identity=identity,
                frames=frames,plasma=plasma,handoff=handoff,elapsed_s=time.perf_counter()-started,
                numerics=dict(dimension=3,coordinates='x,y horizontal; z up; output nm; internal um,s',
                              boundaries='reflective x/y; infinite z',threads=1,seed_rule='seed + process step',
                              spatial_scheme='ENGQUIST_OSHER_1ST_ORDER',time_step_ratio=.4999,
                              max_reflections=10000,max_boundary_hits=1000,
                              coverage_tolerance=1e-4,coverage_max_iterations=30,ion_energy_sigma_ev=10,
                              ion_sticking=1,radical_order=1,ion_order=1,
                              grid_nm=p['grid_nm'],rays_per_point=p['rays_per_point'],
                              max_surface_nodes=MAX_SURFACE_NODES,max_surface_triangles=MAX_SURFACE_TRIANGLES),
                assumptions=[
                    '3D ViennaPS ray transport and level-set evolution, not an extruded 2D movie.',
                    'Ar volume-averaged steady balance with manual fixed-topology RF matching; no automatic matching or recipe optimization.',
                    'One-way Ar ion-flux proxy: Etch ion flux = Gamma_i / 1e19 in 1e15 cm^-2 s^-1; PECVD ion-rate multiplier = Gamma_i / 1e19. This transfer is uncalibrated.',
                    'PECVD radical rate and Etch F/O fluxes remain independent inputs, including when RF is off. No TEOS/SF6 reactor chemistry is solved.',
                    'Ion energy is an independent boundary input; no self-bias, spatial sheath or particle-in-cell solution.',
                    'Etch-to-PECVD retains the native domain after ideal Boolean mask strip. Chemistry memory and residues are not carried.',
                    'Mesh/ray noise is numerical, not predicted physical roughness. Chamber geometry/glow are schematic, not resolved fields.',
                    'Center/top heights are highest vertical ray intersections, not buried-film thickness after pinch-off.',
                ], validation=dict(physical_calibration='not_performed',equipment_match='not_established'),
                sources=[dict(title='ViennaPS 4.6.2 TEOSPECVD implementation',url='https://github.com/ViennaTools/ViennaPS/blob/v4.6.2/include/viennaps/models/psTEOSPECVD.hpp'),
                         dict(title='ViennaPS 4.6.2 SF6/O2 implementation',url='https://github.com/ViennaTools/ViennaPS/blob/v4.6.2/include/viennaps/models/psSF6O2Etching.hpp'),
                         dict(title='ViennaPS TEOS model documentation',url='https://viennatools.github.io/ViennaPS/models/prebuilt/TEOSPECVD.html')])
    json.dumps(result,allow_nan=False)
    if output_dir:
        domain.saveSurfaceMesh(str(Path(output_dir)/'final_surface'))
        domain.saveLevelSets(str(Path(output_dir)/'final_levelset'))
    return result
