"""Executed with .venv Python; these checks are not equipment validation."""
import math
import unittest
import viennaps as ps
import viennals as ls
from native_lab.engine import initialize, simulate, KB, AMU, ray_parameters


def planar_ald(dt=.001):
    initialize()
    domain = ps.Domain(gridDelta=.005, xExtent=.2)
    ps.MakeTrench(domain, trenchWidth=.1, trenchDepth=0).apply()
    domain.duplicateTopLevelSet(ps.Material.Al2O3)
    incoming = 3 / math.sqrt(2*math.pi*72.09*AMU*KB*573.15)
    sticking, sites, evaporation, pulse, growth = .0075, 5e18, 3e19, .05, .0056
    native = ps.SingleParticleALDParams()
    native.stickingProbability = sticking
    native.incomingFlux = incoming
    native.s0 = sites
    native.evaporationFlux = evaporation
    native.growthPerCycle = growth
    native.gasMeanFreePath = -1
    model = ps.SingleParticleALD(native)
    alp = ps.AtomicLayerProcessParameters()
    alp.pulseTime = pulse
    alp.coverageTimeStep = dt
    alp.numCycles = 1
    process = ps.Process(domain, model)
    process.setParameters(alp)
    process.setParameters(ray_parameters({"rays_per_point": 1000, "seed": 42}, 0))
    process.apply()
    mesh = ls.Mesh()
    ls.ToSurfaceMesh(domain.getLevelSets()[-1], mesh).apply()
    ys = [point[1] for point in mesh.getNodes()]
    rate_in, rate_out = incoming * sticking / sites, evaporation / sites
    theta = rate_in / (rate_in + rate_out) * -math.expm1(-(rate_in + rate_out) * pulse)
    return sum(ys)/len(ys)*1000, growth*theta*1000


class NativeTests(unittest.TestCase):
    def test_no_particles_no_etch(self):
        updates = []
        r = simulate({"model": "etch", "params": {"ion_flux": 0, "fluorine_flux": 0, "oxygen_flux": 0, "output_steps": 4}},
                     progress=lambda fraction, frame: updates.append((fraction, frame)))
        self.assertEqual(r["frames"][0]["layers"], r["frames"][-1]["layers"])
        self.assertEqual(updates[0], (0, r["frames"][0]))
        self.assertEqual(updates[-1], (1, r["frames"][-1]))

    def test_no_ald_exposure_no_growth(self):
        for params in [{"pulse_s": 0}, {"pressure_pa": 0}]:
            r = simulate({"model": "ald", "params": {**params, "cycles": 10}})
            self.assertEqual(r["frames"][0]["layers"], r["frames"][-1]["layers"])

    def test_etch_determinism_and_material_retention(self):
        request = {"model": "etch", "params": {"duration_s": .3, "output_steps": 4, "rays_per_point": 100}}
        a, b = simulate(request), simulate(request)
        self.assertEqual(a["frames"], b["frames"])
        self.assertEqual(a["run_hash"], b["run_hash"])
        self.assertGreater(a["frames"][-1]["metrics"]["center_depth_nm"], 0)
        self.assertEqual([l["material"] for l in a["frames"][-1]["layers"]], ["Mask", "Si"])
        self.assertEqual(a["frames"][0]["metrics"]["mask_loss_nm"], 0)

    def test_ald_plane_matches_independent_langmuir_solution(self):
        numeric, analytic = planar_ald(.0005)
        self.assertLess(abs(numeric-analytic)/analytic, .03)

    def test_ald_coverage_step_refinement(self):
        coarse, exact = planar_ald(.002)
        fine, _ = planar_ald(.0005)
        self.assertLess(abs(fine-exact), abs(coarse-exact))


if __name__ == "__main__":
    unittest.main()
