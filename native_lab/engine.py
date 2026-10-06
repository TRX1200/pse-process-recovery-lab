"""Feature-scale native solvers, isolated in one subprocess per run.

This module integrates upstream physical models; it does not rebrand them as a
new original TCAD solver. See docs/NATIVE_SIMULATOR_KR.md for the model boundary.
"""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import math
import platform
import time
from pathlib import Path

import viennaps as ps
import viennals as ls

from native_lab import VERSION
from native_lab.geometry import ordered_paths, measurements
from native_lab.schema import validate, SOURCES
from native_lab.profiles import make_profile, planar_metrics, sidewall_metrics

KB = 1.380649e-23
AMU = 1.66053906660e-27


def environment():
    return {"python": platform.python_version(), "platform": platform.platform(),
            "viennaps": importlib.metadata.version("ViennaPS"),
            "viennals": importlib.metadata.version("ViennaLS"), "threads": 1}


def initialize():
    if environment()["viennaps"] != "4.6.2" or environment()["viennals"] != "5.8.5":
        raise RuntimeError("Install the pinned native_lab/requirements.txt environment")
    ps.setDimension(2)
    ls.setDimension(2)
    ps.setNumThreads(1)
    ls.setNumThreads(1)
    ps.Length.setUnit("um")
    ps.Time.setUnit("s")
    ps.Logger.setLogLevel(ps.LogLevel.WARNING)


def capture(domain, materials, model, params, value, label):
    layers = []
    for index, level in enumerate(domain.getLevelSets()):
        material = ps.MaterialMap.toString(domain.getMaterialMap().getMaterialAtIdx(index))
        mesh = ls.Mesh()
        ls.ToSurfaceMesh(level, mesh).apply()
        paths = ordered_paths(mesh.getNodes(), mesh.getLines())
        layers.append({"material": material, "paths_nm": paths})
    profile = params.get('surface_profile',0)
    if profile == 1:
        metrics = planar_metrics(layers[-1]['paths_nm'],params['pitch_nm'])
    else:
        metrics = measurements(layers,model,params)
        if profile == 2:
            metrics.update(sidewall_metrics(layers[-1]['paths_nm'],params['depth_nm']))
            metrics.pop('mask_loss_nm',None)
    return {"at": value, "label": label, "layers": layers, "metrics": metrics}


def ray_parameters(p, step):
    ray = ps.RayTracingParameters()
    ray.raysPerPoint = p["rays_per_point"]
    ray.rngSeed = p["seed"] + step
    ray.useRandomSeeds = False
    ray.maxReflections = 10000
    ray.maxBoundaryHits = 1000
    return ray


def simulate(payload, output_dir=None, progress=None):
    request = validate(payload)
    initialize()
    model, p = request["model"], request["params"]
    started = time.perf_counter()
    domain = ps.Domain(gridDelta=p["grid_nm"] / 1000, xExtent=p["pitch_nm"] / 1000)
    profile = p['surface_profile']
    if profile:
        make_profile(domain,p)
        if model == 'ald':
            domain.duplicateTopLevelSet(ps.Material.Al2O3)
        materials = ['Si'] if model == 'etch' else ['Si','Al2O3']
    elif model == "etch":
        ps.MakeTrench(domain, trenchWidth=p["width_nm"] / 1000, trenchDepth=0,
                      maskHeight=p["mask_nm"] / 1000).apply()
        materials = ["Si", "Mask"]
    else:
        ps.MakeTrench(domain, trenchWidth=p["width_nm"] / 1000,
                      trenchDepth=p["depth_nm"] / 1000).apply()
        domain.duplicateTopLevelSet(ps.Material.Al2O3)
        materials = ["Si", "Al2O3"]
    frames = [capture(domain, materials, model, p, 0, "initial")]
    initial_mask_offset = frames[0]["metrics"].get("mask_loss_nm", 0)
    if model == "etch" and not profile:
        frames[0]["metrics"]["mask_loss_nm"] = 0.0
    if profile == 1:
        frames[0]['metrics']['mean_advance_nm'] = 0.0
    elif profile == 2 and model == 'etch':
        frames[0]['metrics']['etch_advance_nm'] = 0.0
    if progress:
        progress(0, frames[0])
    warnings = []
    settings = {"length_unit": "um", "coordinate_system": "x horizontal, y up; output nm",
                "boundary_x": "reflective", "boundary_y": "infinite",
                "max_reflections": 10000, "max_boundary_hits": 1000,
                "seed_rule": "seed + output/group index (zero based)",
                "spatial_scheme": "ENGQUIST_OSHER_1ST_ORDER", "time_step_ratio": 0.4999}

    def record(step, total, value, label):
        frames.append(capture(domain, materials, model, p, value, label))
        if model == "etch" and not profile:
            frames[-1]["metrics"]["mask_loss_nm"] = max(0, frames[-1]["metrics"]["mask_loss_nm"] - initial_mask_offset)
        if profile == 1:
            current, initial = frames[-1]['metrics']['mean_height_nm'], frames[0]['metrics']['mean_height_nm']
            frames[-1]['metrics']['mean_advance_nm'] = ((current-initial)*(1 if model=='ald' else -1)
                                                      if current is not None and initial is not None else None)
        elif profile == 2 and model == 'etch':
            frames[-1]['metrics']['etch_advance_nm'] = frames[-1]['metrics']['center_depth_nm']-frames[0]['metrics']['center_depth_nm']
        if progress:
            progress(step / total, frames[-1])

    if model == "etch":
        native = ps.SF6O2Etching.defaultParameters()
        native.ionFlux = p["ion_flux"]
        native.etchantFlux = p["fluorine_flux"]
        native.passivationFlux = p["oxygen_flux"]
        native.Ions.meanEnergy = p["energy_ev"]
        native.Ions.sigmaEnergy = p["energy_sigma_ev"]
        native.Ions.exponent = p["ion_exponent"]
        process_model = ps.SF6O2Etching(native)
        settings["model_parameters"] = native.toProcessMetaData() if hasattr(native, "toProcessMetaData") else {
            "defaults_source": "ViennaPS v4.6.2 SF6O2Etching.defaultParameters",
            "overrides": {k: p[k] for k in ["ion_flux", "fluorine_flux", "oxygen_flux", "energy_ev", "energy_sigma_ev", "ion_exponent"]},
            "mask_effective_density_1e22_cm3": native.Mask.rho,
        }
        coverage = ps.CoverageParameters()
        coverage.maxIterations = 30
        coverage.tolerance = 1e-4
        settings["coverage_max_iterations"] = 30
        settings["coverage_tolerance"] = 1e-4
        steps = p["output_steps"]
        # No incoming particles is handled explicitly: a stationary surface.
        active = p["duration_s"] > 0 and any(p[k] > 0 for k in ("ion_flux", "fluorine_flux", "oxygen_flux"))
        for i in range(steps):
            if active:
                process = ps.Process(domain, process_model, p["duration_s"] / steps)
                process.setParameters(ray_parameters(p, i))
                process.setParameters(coverage)
                process.apply()
            record(i + 1, steps, p["duration_s"] * (i + 1) / steps, "etch")
        axis_unit = "s"
        assumptions = [
            "Si / SF6-O2 native feature model: neutral transport, ion energy/angle, surface coverage, sputtering and ion-enhanced removal.",
            "Incident species fluxes and energy distributions are boundary inputs; no RF circuit, plasma reactor or sccm-to-flux mapping is solved.",
            "Upstream default effective mask density is 500 x 1e22 atoms/cm3: a durable numerical mask, not the density of an identified mask material.",
            "Monte Carlo variation and level-set discretization are numerical errors, not physical surface roughness.",
        ]
    else:
        thermal_flux = p["pressure_pa"] / math.sqrt(2 * math.pi * 72.09 * AMU * KB * (p["temperature_c"] + 273.15))
        sites = p["site_density_nm2"] * 1e18
        loss_flux = p["evaporation_flux"] * 1e19
        max_rate = (thermal_flux * p["sticking"] + loss_flux) / sites
        coverage_dt = min(p["coverage_dt_s"], 0.1 / max_rate) if max_rate else p["coverage_dt_s"]
        bundle = max(1, min(p["bundle_cycles"], int(.4 * p["grid_nm"] / p["gpc_nm"])))
        steps = math.ceil(p["cycles"] / bundle)
        settings.update(incoming_flux_m2_s=thermal_flux, site_density_m2=sites,
                        coverage_dt_s=coverage_dt, effective_bundle_cycles=bundle,
                        max_pulse_steps=math.ceil(p["pulse_s"] / coverage_dt),
                        gas_mean_free_path="infinite; Knudsen limit", precursor_mass_u=72.09)
        completed = 0
        for i in range(steps):
            count = min(bundle, p["cycles"] - completed)
            native = ps.SingleParticleALDParams()
            native.stickingProbability = p["sticking"]
            native.gasMeanFreePath = -1
            native.growthPerCycle = p["gpc_nm"] / 1000 * count
            native.incomingFlux = thermal_flux
            native.evaporationFlux = loss_flux
            # Upstream divides by s0: this API field is SITE DENSITY, not the
            # site AREA named s0 in Aguinsky et al. Equating them is a unit bug.
            native.s0 = sites
            process_model = ps.SingleParticleALD(native)
            alp = ps.AtomicLayerProcessParameters()
            alp.numCycles = 1
            alp.pulseTime = p["pulse_s"]
            alp.coverageTimeStep = coverage_dt
            alp.purgePulseTime = 0
            if p["pulse_s"] > 0 and thermal_flux > 0:
                process = ps.Process(domain, process_model)
                process.setParameters(alp)
                process.setParameters(ray_parameters(p, i))
                process.apply()
            completed += count
            record(i + 1, steps, completed, "growth")
            if profile != 1 and frames[-1]["metrics"]["minimum_gap_nm"] < 2 * p["grid_nm"]:
                warnings.append("통로가 2격자보다 좁아져 중단했습니다. 완전 폐쇄 이후의 성장은 해상도를 높여 검토해야 합니다.")
                break
        axis_unit = "cycle"
        assumptions = [
            "TMA-limited ALD surrogate; opposite half-reaction and purge are assumed complete. No complete TMA/H2O chemistry or impurity prediction.",
            "Coverage-dependent sticking, diffuse reflection and reversible Langmuir kinetics are solved on the evolving 2D geometry.",
            "Aguinsky Table 2 supplies beta=0.0075 and evaporation flux=3e19 as literature starting values. Site density and this geometry are not fitted to that experiment.",
            "Cycle bundling advances at most 0.4 grid spacings at saturated growth per geometry update; chemistry is reinitialized for each representative pulse.",
            "Temperature changes thermal flux only; kinetic coefficients are held fixed. Knudsen-limit transport, no gas-phase collisions.",
        ]
    if profile:
        assumptions += [
            'Corrugation is prescribed initial geometry, then evolved by the same native flux/coverage/level-set model.',
            'No self-organized ripple instability or alternating Bosch etch/passivation generation is modeled. Nonzero profile modes have no mask.',
            'Planar Rq/Ra use 256 uniform x midpoints after mean removal. Wall Rq uses 161 fixed 10%-90% initial-depth samples after linear detrending.',
            'Measured profile change contains discretization and Monte Carlo error. Resolve input amplitude/wavelength and compare grid and seed before interpretation.',
        ]
        settings['initial_profile'] = {'mode':profile,'amplitude_nm':p['corrugation_amplitude_nm'],'count':p['corrugation_count']}
    if output_dir:
        domain.saveSurfaceMesh(str(Path(output_dir) / "final_surface"))
        domain.saveLevelSets(str(Path(output_dir) / "final_levelset"))
    identity = {**request, "implementation": VERSION, "engine": environment(), "numerics": settings}
    result = {"format": "native-feature-run-v1", "model": model,
              "run_hash": hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
              "params": p, "environment": environment(), "implementation": VERSION,
              "numerics": settings, "frames": frames, "axis_unit": axis_unit,
              "elapsed_s": time.perf_counter() - started, "warnings": warnings,
              "assumptions": assumptions, "sources": SOURCES,
              "validation": {"physical_calibration": "not_performed", "equipment_match": "not_established"}}
    json.dumps(result, allow_nan=False)
    return result
