#!/usr/bin/env python3
"""Vision3 scene-referred engine: scanner density -> scene-linear DaVinci Wide Gamut.

The ECN-2 branch's secondary, scene-referred path, and its only per-stock
engine. A scene-referred decode reads the scan back as the scene the camera
recorded, as a digital intermediate does, and is the accuracy reference for
graded work; the ADX16 route is the branch's primary delivery. (C-41 is the
opposite case: those negatives were designed to be printed, and print
emulation is their sole delivery route.)

Chains at exactly the same point as builds/ecn2/'Vision3 to ADX16.cube':
INPUT is normalized scanner density [0,1]^3 = OD/3.30 per channel, D-MIN
EXCLUDED (upstream: -log10(linear), per-channel D-min subtraction, /3.30 --
the same 3.3 shaper pair, register #5). OUTPUT is scene-linear DaVinci Wide
Gamut (D65); negatives allowed, no clamp.

Pipeline per lattice node:
  1. de-normalize to scanner (image) density;
  2. Gauss-Newton unmix through PHI (scanner LED SPD x sensor response x
     10^-Dmin(l); default --sensor none = unity/monochrome) -> image-dye
     amounts. The roll anchor divides the base and orange mask out of the
     frame in INTEGRATED density, so the cube receives the dyes as the LEDs
     see them through the mask, and the mask is the stock's own traced
     Minimum Density curve. The basis is the stock's OWN traced dye set: the
     family-average basis exists to serve the stock-blind ADX16 route, and a
     per-stock cube has no reason to discard the per-stock trace;
  3. per layer, look the amount up on that layer's neutral-scale table
     (amount versus logH on the sheet's shared exposure axis) -> logH. The
     tables come from the FULL three-channel Status M solve along the
     characteristic curves: the sheet's curves are integral densities, so
     each channel carries the other two layers' unwanted absorption (S
     off-diagonals 0.03-0.13 of the diagonal, S = Status M of the unit-peak
     dyes), and only the three amounts that reproduce all three curves at
     once are the sheet's neutral. Nulls are dropped from the curves'
     support and the tables extend with their terminal slope;
  4. relative layer exposure L = 10^(logH - logH_mid). logH_mid comes from
     the traced midscale-neutral spectral curve: Status M integrated over its
     measured support only (responsivities renormalized on that support, so
     nothing is synthesized beyond it), char-inverted per channel, averaged.
     The sheet's camera-stops zero is PRINTED as a cross-check, not used: the
     two differ by 0.07-0.40 logH across the fleet and the midscale patch is
     the very quantity this anchor is for. Residual uncertainty in logH_mid
     is a uniform per-stock exposure trim, never a colour error;
  5. a 3x3 matrix (weighted least squares over ColorChecker 24 + Munsell
     glossy/matt + Agfa IT8.7/2 + NIST skin reflectances, illuminated by the
     stock's balance illuminant -- D55 for 50D/250D, 3200 K blackbody for
     200T/500T -- Bradford-adapted to D65, with an exact grey-row
     normalization) maps L -> XYZ(D65);
  6. XYZ(D65) -> DWG linear via the standard DaVinci Wide Gamut matrix.

Ancestry: the inverse chain, matrix fit and diagnostics port the unpublished
C-41 scene-referred engine's machinery; the scan-side unmix, dye-support grid
narrowing and --sensor handling mirror adx_engine.py.

The ColorChecker "full chain" metric is NOT independent evidence about the
film model: the forward model and the inverse chain are built from the same
machinery, so that figure collapses to the matrix-only residual and the
matrix was fitted on those very patches. It is printed as a plumbing check
(the chain inverts itself), nothing more. No part of this chain has a
measured check; that project-wide caveat applies here in full.
"""
import argparse
import json
import sys
import numpy as np
from pathlib import Path
import colour

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"; BUILDS = ROOT / "builds"
sys.path.insert(0, str(ROOT))
from engine.common import interimage as iim              # noqa: E402
from engine.common.spectral import interp_lin, resample, density  # noqa: E402

# ----- constants shared with the rest of the branch -----
# Corridor for the whole negative family; must match the 3.3 shaper DCTL pair
# (register #5) and adx_engine's DMAX.
DMAX = 3.30
# a lattice node counts as converged, for the clean-cell diagnostic, when its
# scan residual is within this; the C-41 error budget's reachability tolerance
CLEAN_TOL_D = 1.0e-3
SZ = 65
GRAY = 0.18                       # scene mid-gray reflectance
# Colorimetric grid. 380 nm is the conventional visible floor and what the
# reflectance training sets support without extension; it truncates the 21 nm
# of traced 50D yellow-layer toe below 380 nm, asserting the sensitivity-
# times-illuminant product there is negligible rather than synthesizing
# reflectance data to integrate against it.
CGRID = np.arange(380, 731, 1.0)

# 3x3 DIR / interimage inhibition matrix (dye-amount space). Identity =>
# stage skipped, outputs bit-identical to the stage-free chain.
DIR_MATRIX = np.eye(3)

# Which fitted matrix drives the cube: "broad" (ColorChecker + Munsell/IT8.7-2/
# NIST-skin) or "checker" (ColorChecker-24 only). One-word switch.
MATRIX_MODE = "broad"

# Broad-set per-set training weights; each spectrum in a set is weighted
# set_weight / n_spectra so no set dominates. ColorChecker keeps its per-patch
# weights, rescaled so the checker's total == 24.
BROAD_SET_WEIGHTS = {
    "munsell_glossy_all": 24.0,
    "munsell_matt":       12.0,
    "agfa_it872":         12.0,
    "nist_skin":          24.0,
}
CHECKER_TOTAL_WEIGHT = 24.0
REFLECTANCE_DIR = DATA / "standards" / "reflectance"


# ================= stock table =================
# Balance illuminant is the sheet's own sensitometric exposure: 5500 K
# daylight for the D stocks, 3200 K tungsten for the T stocks. The 500T
# characteristic-curve file keeps its historical V3500T name.
STOCKS = {
    "50D": {
        "display_name": "Kodak Vision3 50D (5203)",
        "dye_density":  DATA / "films" / "Vision3_50D_dye_density.json",
        "char_curves":  DATA / "films" / "Vision3_50D_datasheet_curves.json",
        "sensitivity":  DATA / "films" / "Vision3_50D_spectral_sensitivity.json",
        "scene_illuminant": "D55",
    },
    "250D": {
        "display_name": "Kodak Vision3 250D (5207)",
        "dye_density":  DATA / "films" / "Vision3_250D_dye_density.json",
        "char_curves":  DATA / "films" / "Vision3_250D_datasheet_curves.json",
        "sensitivity":  DATA / "films" / "Vision3_250D_spectral_sensitivity.json",
        "scene_illuminant": "D55",
    },
    "200T": {
        "display_name": "Kodak Vision3 200T (5213)",
        "dye_density":  DATA / "films" / "Vision3_200T_dye_density.json",
        "char_curves":  DATA / "films" / "Vision3_200T_datasheet_curves.json",
        "sensitivity":  DATA / "films" / "Vision3_200T_spectral_sensitivity.json",
        "scene_illuminant": "3200K",
    },
    "500T": {
        "display_name": "Kodak Vision3 500T (5219)",
        "dye_density":  DATA / "films" / "Vision3_500T_dye_density.json",
        "char_curves":  DATA / "films" / "V3500T_datasheet_curves.json",
        "sensitivity":  DATA / "films" / "Vision3_500T_spectral_sensitivity.json",
        "scene_illuminant": "3200K",
    },
}
LAYERS = ["cyan", "magenta", "yellow"]            # dye/exposure triplet order


# ================= sensor resolution (mirrors adx_engine) =================
DEFAULT_SENSOR = "none"


def resolve_sensor(value):
    """(path, label); path is None for the unity/monochrome case."""
    if value == "none":
        return None, "none (unity response; monochrome sensor)"
    cams = DATA / "cameras"
    if "/" in value or "\\" in value:
        p = Path(value)
    elif value.endswith(".json"):
        p = cams / value
        if not p.exists():
            p = Path(value)
    else:
        p = cams / ("%s_ssf.json" % value)
    if not p.exists():
        raise SystemExit("sensor file not found: %s\n(look in %s)" % (p, cams))
    return p, p.name


def sensor_stem(value):
    """Directory stem for a named sensor, e.g. 'Sony_ILCE-7RM3'."""
    n = Path(value).name
    if n.endswith(".json"):
        n = n[:-5]
    if n.endswith("_ssf"):
        n = n[:-4]
    return n


def load_reflectance_set(path):
    """Load one broad-set reflectance JSON, resampled onto CGRID with linear
    interpolation. Spectra narrower than CGRID (e.g. Agfa IT8.7/2, 400-700 @
    10 nm) are extended flat by holding the end values -- np.interp's default
    constant edge extrapolation. Returns a list of (name, R_on_CGRID)."""
    d = json.load(open(path))
    out = []
    for name, spec in d.items():
        n = len(spec["values"])
        wl = np.linspace(float(spec["wl_start"]), float(spec["wl_end"]), n)
        R = np.interp(CGRID, wl, np.asarray(spec["values"], float))  # flat-hold ends
        out.append((name, R))
    return out


class V3SceneEngine:
    def __init__(self, stock, sensor_path, sensor_label):
        self.name = stock
        self.p = STOCKS[stock]
        p = self.p
        self.sensor_label = sensor_label

        # ---------- dye basis (per-stock, peak = 1, D-min subtracted) ----------
        dj = json.load(open(p["dye_density"]))
        fc = dj["shared_full_curves"]
        wl_all = np.array(fc["wavelength_nm"], float)
        vals = {k: np.array([np.nan if v is None else v for v in fc[k]], float)
                for k in LAYERS}
        meas = [wl_all[~np.isnan(vals[k])] for k in LAYERS]
        # Densitometry grid narrowed to the UNION of the dyes' measured
        # support, clamped to the array's own range -- the same policy, for
        # the same reasons, as adx_engine (no synthesized tail, no
        # perfectly-clear zero-fill at the frame edge).
        lo = max(400.0, min(m.min() for m in meas), wl_all.min())
        hi = min(730.0, max(m.max() for m in meas), wl_all.max())
        self.DGRID = np.arange(np.ceil(lo), np.floor(hi) + 1, 1.0)
        self.DYE = np.empty((3, self.DGRID.size))
        for i, k in enumerate(LAYERS):
            v = vals[k]; ok = ~np.isnan(v)
            self.DYE[i] = resample(wl_all[ok], v[ok], self.DGRID)
            glo = self.DGRID < meas[i].min(); ghi = self.DGRID > meas[i].max()
            if glo.any() or ghi.any():
                print("  WARNING %s dye zero-filled over %d nm inside the grid "
                      "(measured %.0f-%.0f nm)"
                      % (k, int(glo.sum() + ghi.sum()), meas[i].min(), meas[i].max()))

        # ---------- traced midscale neutral (absolute, mask included) ----------
        m = dj["midscale_neutral"]
        mwl = np.array(m["wavelength_nm"], float)
        mok = np.array([v is not None for v in m["density"]], bool)
        self.mid_wl = mwl[mok]
        self.mid_spec = np.array([v for v in m["density"] if v is not None], float)

        # ---------- traced Minimum Density: base plus orange mask, absolute ----------
        # The roll anchor divides this out of the frame in INTEGRATED density,
        # so the scanner reads the image dyes through it: the scan-side
        # responsivity is the LED behind the mask, and the characteristic
        # curves, which include it, are matched with it in the stack.
        md = dj["minimum_density"]
        mdw = np.array(md["wavelength_nm"], float)
        mdv = np.array([np.nan if v is None else v for v in md["density"]], float)
        mdok = ~np.isnan(mdv)
        if self.DGRID[0] < mdw[mdok].min() or self.DGRID[-1] > mdw[mdok].max():
            raise SystemExit("%s: minimum density support %.0f-%.0f nm does not cover the "
                             "dye grid %.0f-%.0f" % (stock, mdw[mdok].min(), mdw[mdok].max(),
                                                     self.DGRID[0], self.DGRID[-1]))
        self.DMIN = resample(mdw[mdok], mdv[mdok], self.DGRID)

        # ---------- scanner PHI (LED SPD x sensor; unity sensor by default) ----
        raw = open(DATA / "equipment" / "film_scanner_SPD_combined.csv").read().strip().splitlines()
        hdr = raw[0].split(",")
        sdat = np.array([[float(x) for x in r.split(",")] for r in raw[1:]])
        wl_s = sdat[:, 0]

        def scol(n):
            return resample(wl_s, sdat[:, hdr.index(n)], self.DGRID)
        L_R, L_G, L_B = scol("R100_G0_B0"), scol("R0_G100_B0"), scol("R0_G0_B100")
        if sensor_path is None:
            S_R = S_G = S_B = 1.0            # unity response: PHI is the LED SPD alone
        else:
            import re
            ct = open(sensor_path).read()

            def arr(k):
                mm = re.search(k + r'"?\s*:\s*\[([0-9eE.,\s\-]*?)\]', ct)
                return np.array([float(x) for x in
                                 re.findall(r'-?\d+\.?\d*(?:[eE][-+]?\d+)?', mm.group(1))], float)
            wl_c = arr("ssf_bands")
            S_R = resample(wl_c, arr("red_ssf"), self.DGRID)
            S_G = resample(wl_c, arr("green_ssf"), self.DGRID)
            S_B = resample(wl_c, arr("blue_ssf"), self.DGRID)
        PHI_bare = np.stack([L_R * S_R, L_G * S_G, L_B * S_B])
        self.PHI_bare_n = PHI_bare / PHI_bare.sum(1, keepdims=True)
        PHI = PHI_bare * 10.0 ** (-self.DMIN)
        self.PHI_n = PHI / PHI.sum(1, keepdims=True)
        cent = lambda P: (P * self.DGRID).sum(1) / P.sum(1)
        self.mask_centroid_shift_nm = cent(self.PHI_n) - cent(self.PHI_bare_n)

        # ---------- Status M responsivities (truncated to grid, renormalized) --
        smj = json.load(open(DATA / "standards" / "StatusM_ISO5-3.json"))
        self.sm_wl = np.array(smj["wavelength_nm"], float)
        self.sm_raw = {c: np.array(smj["responsivity_linear_peak1"][c], float)
                       for c in ("red", "green", "blue")}
        SM = np.stack([resample(self.sm_wl, self.sm_raw[c], self.DGRID)
                       for c in ("red", "green", "blue")])
        self.SM_n = SM / SM.sum(1, keepdims=True)
        red = self.sm_raw["red"]
        self.red_tail_pct = 100.0 * (1.0 - red[self.sm_wl <= self.DGRID[-1]].sum() / red.sum())

        # ---------- Status M of unit-peak dyes: S[ch][layer] ----------
        self.S = self.statusm_fwd(np.eye(3)).T   # column l = Status M of unit dye l

        # ---------- characteristic curves (absolute density incl. base+mask) ---
        cd = json.load(open(p["char_curves"]))["char_curves"]
        logH = np.array(cd["log_exposure"], float)
        self.char = {}                    # ch -> (logH, density), strictly rising
        for ch in "RGB":
            dv = np.array([np.nan if v is None else v for v in cd["density"][ch]], float)
            ok = np.isfinite(dv)
            x, y = logH[ok], dv[ok]
            # The engine's curve model must be STRICTLY increasing in density
            # so the inverse exists everywhere.  The smoothed trace can hold
            # density ties and hair-width dips at the toe; scan from the end
            # keeping each point strictly below the minimum kept so far, which
            # yields a strictly increasing sequence preserving the LAST
            # occurrence of every density level.  The SAME point set serves
            # both directions, so forward and inverse invert each other
            # exactly, at the cost of bridging a tie run with a sliver of
            # slope (error bounded by one grid step's density rise).
            keep = np.zeros(y.size, bool)
            lo = np.inf
            for i in range(y.size - 1, -1, -1):
                if y[i] < lo - 1e-9:
                    keep[i] = True
                    lo = y[i]
            self.char[ch] = (x[keep], y[keep])
        self.dmin = np.array([cd["dmin"][ch] for ch in "RGB"], float)
        self.stop0 = float(cd["camera_stops_zero_logH"])

        # ---------- logH_mid from the traced midscale neutral ----------
        # Status M over the midscale trace's measured support only: the
        # responsivities are resampled onto that support and renormalized, so
        # the integral asserts nothing beyond the measured band (its bias is
        # bounded by how flat the spectrum is over the unmeasured tail).
        row = []
        for c in ("red", "green", "blue"):
            r = resample(self.sm_wl, self.sm_raw[c], self.mid_wl)
            rn = r / r.sum()
            row.append(-np.log10(max(rn @ 10.0 ** (-self.mid_spec), 1e-12)))
        self.mid_statusM = np.array(row)
        self.logH_mid_per = np.array([self.inv_char(ch, self.mid_statusM[i])
                                      for i, ch in enumerate("RGB")])
        self.logH_mid = float(self.logH_mid_per.mean())

        # ---------- sensitivities (linear, 0 outside measured support) ---------
        sj = json.load(open(p["sensitivity"]))
        swl = np.array(sj["wavelength_nm"], float)
        self.SENS = {}
        for l in LAYERS:
            ls = np.array([np.nan if v is None else v for v in sj["log_sensitivity"][l]], float)
            ok = np.isfinite(ls)
            self.SENS[l] = resample(swl[ok], 10.0 ** ls[ok], CGRID)

        # ---------- colorimetry basis (CMFs, scene illuminant, D65) ----------
        cm = json.load(open(DATA / "standards" / "CIE1931_2deg_CMFs.json"))
        cw = np.array(cm["wavelength_nm"], float)
        self.CMF = np.stack([resample(cw, cm["x_bar"], CGRID),
                             resample(cw, cm["y_bar"], CGRID),
                             resample(cw, cm["z_bar"], CGRID)])
        shp = colour.SpectralShape(CGRID[0], CGRID[-1], 1)
        if p["scene_illuminant"] == "D55":
            self.ILL = colour.SDS_ILLUMINANTS["D55"].copy().align(shp).values
        elif p["scene_illuminant"] == "3200K":
            self.ILL = colour.sd_blackbody(3200, shp).values
        else:
            raise ValueError("unknown scene_illuminant %r" % p["scene_illuminant"])
        self.D65 = colour.SDS_ILLUMINANTS["D65"].copy().align(shp).values

        # normalization so a flat 18% gray -> Y = 0.18 under the scene illuminant
        self.Yw_scene = float(self.CMF[1] @ self.ILL)
        Xw_scene = (self.CMF @ self.ILL) / self.Yw_scene
        Yw_D65 = float(self.CMF[1] @ self.D65)
        Xw65 = (self.CMF @ self.D65) / Yw_D65
        self.M_cat = colour.adaptation.matrix_chromatic_adaptation_VonKries(
            Xw_scene, Xw65, transform="Bradford")
        self.white_ref = self.M_cat @ Xw_scene           # D65 white (Y=1), Lab reference

        # ---------- XYZ(D65) -> DWG and DWG -> Rec.2020 ----------
        dwg = colour.RGB_COLOURSPACES["DaVinci Wide Gamut"]
        self.XYZ_to_DWG = np.array(dwg.matrix_XYZ_to_RGB)
        self.dwg_src = "colour-science %s 'DaVinci Wide Gamut' colourspace" % colour.__version__
        r2020 = colour.RGB_COLOURSPACES["ITU-R BT.2020"]
        self.DWG_to_2020 = np.array(r2020.matrix_XYZ_to_RGB) @ np.array(dwg.matrix_RGB_to_XYZ)

        # ---------- scan-side unmix seed + interimage ----------
        n = 9; ax = np.linspace(0, 2, n)
        g = np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T
        W, *_ = np.linalg.lstsq(g, self.scan_fwd(g), rcond=None)
        self.Winv = np.linalg.inv(W)
        self._setup_interimage()

        # ---------- fit the 3x3 scene matrix ----------
        self._fit_matrix()

    # ---------- integral densitometry ----------
    def scan_fwd(self, dye):
        return density(self.PHI_n, dye, self.DYE)

    def statusm_fwd(self, dye):
        return density(self.SM_n, dye, self.DYE)

    def statusm_abs(self, dye):
        """Absolute Status M of the film: mask plus image dyes, as the
        characteristic sheet's densitometer reads it."""
        dye = np.atleast_2d(dye)
        T = 10.0 ** (-(dye @ self.DYE + self.DMIN))
        return -np.log10(np.clip(T @ self.SM_n.T, 1e-12, None))

    def scan_jac(self, dye):
        dye = np.atleast_2d(dye)
        T = 10.0 ** (-(dye @ self.DYE))
        integ = T @ self.PHI_n.T
        num = np.einsum('nl,il,jl->nij', T, self.PHI_n, self.DYE)
        return -np.log10(np.clip(integ, 1e-12, None)), num / integ[:, :, None]

    def invert_scan(self, D, iters=12):
        """Gauss-Newton: dye amounts whose scanner densities match D."""
        D = np.atleast_2d(D)
        dye = D @ self.Winv
        for _ in range(iters):
            Dv, J = self.scan_jac(dye)
            step = np.linalg.solve(J, (Dv - D)[:, :, None])[:, :, 0]
            dye = np.clip(dye - step, -0.5, 6.0)
        return dye

    # ---------- characteristic curves ----------
    def inv_char(self, ch, dens):
        """Absolute channel density (incl. base+mask) -> logH."""
        xp, fp = self.char[ch]
        return float(interp_lin(dens, fp, xp))

    def fwd_char(self, ch, logH):
        """logH -> absolute channel density (incl. base+mask)."""
        xp, fp = self.char[ch]
        return interp_lin(logH, xp, fp)

    # ---------- neutral-scale amount tables, interimage pre-compensation ----------
    def _setup_interimage(self):
        """Per-layer dye amount along the sheet's neutral scale, and the
        pre-coupler form of it when DIR is not the identity.

        The characteristic curves are Status M INTEGRAL densities of one
        neutral exposure series, so the red curve carries the magenta and
        yellow layers' red absorption at the amounts those layers have on
        that series. Reading one channel's curve as if it measured one
        layer (dmin_ch + S[ch,l]*a_l) attributes that cross absorption to
        the primary layer: on a neutral that satisfies the sheet it puts the
        three layers' exposures 0.09-0.22 logH apart at midscale and up to
        0.44 logH at +1.5 stops (500T), a cast the engine's own neutral ramp
        cannot see because forward and inverse would share the rule. The
        amounts are therefore solved from all three curves at once, by
        Gauss-Newton on the full dye stack, so the model's neutral IS the
        sheet's. Each layer's table is made strictly increasing in amount
        (reverse scan keeping the last point of a tie run) so the
        amount -> logH inverse exists, and the SAME table serves the forward
        model, so a neutral ramp inverts itself exactly."""
        self.DIR = np.asarray(DIR_MATRIX, float)
        self.interimage_on = not iim.is_identity(self.DIR)
        lo = max(c[0][0] for c in self.char.values())
        hi = min(c[0][-1] for c in self.char.values())
        grid = self.char["G"][0]                          # shared exposure axis
        grid = grid[(grid >= lo) & (grid <= hi)]
        # the curves are ABSOLUTE densities of mask plus dyes, and so is the
        # model stack: the traced mask sits under the dyes in every column, and
        # the sheet's own D-min triplet is only compared against it
        Dabs = np.stack([self.fwd_char(ch, grid) for ch in "RGB"], axis=1)
        self.mask_statusM = self.statusm_abs(np.zeros((1, 3)))[0]
        amt = (Dabs - self.mask_statusM) @ np.linalg.inv(self.S).T
        for _ in range(30):
            T = 10.0 ** (-(amt @ self.DYE + self.DMIN))
            integ = T @ self.SM_n.T
            J = np.einsum('nl,il,jl->nij', T, self.SM_n, self.DYE) / integ[:, :, None]
            r = -np.log10(np.clip(integ, 1e-12, None)) - Dabs
            amt = np.clip(amt - np.linalg.solve(J, r[:, :, None])[:, :, 0], -0.5, 6.0)
        self.neutral_solve_max_resid = float(np.max(np.abs(self.statusm_abs(amt) - Dabs)))
        self.neutral_negative_frac = float(np.mean((amt < 0).any(1)))
        self.neutral_logH = grid
        self.neutral_amt = amt
        self.neutral_amt_pre = iim.precompensate(amt, self.DIR) if self.interimage_on else amt
        self.neutral_tab = []                             # per layer: (amount asc, logH asc)
        self.neutral_dropped = []
        for l in range(3):
            a = self.neutral_amt_pre[:, l]
            keep = np.zeros(a.size, bool)
            m = np.inf
            for i in range(a.size - 1, -1, -1):
                if a[i] < m - 1e-9:
                    keep[i] = True
                    m = a[i]
            self.neutral_tab.append((a[keep], grid[keep]))
            self.neutral_dropped.append(int((~keep).sum()))

    # ---------- core inverse chain: scan density (norm, excl D-min) -> L ------
    def scan_norm_to_L(self, Dnorm):
        Dnorm = np.atleast_2d(Dnorm)
        dye = self.invert_scan(Dnorm * DMAX)              # developed image-dye amounts
        pre = iim.precompensate(dye, self.DIR) if self.interimage_on else dye
        # The INVERSE lookup, amount -> logH, is CLAMPED at both ends of each
        # layer's table (Rule 4; knowledge/reading-datasheet-charts.md, terminal
        # behaviour): past the shoulder the inverse slope is enormous, so a
        # terminal-slope extension turns a small overshoot in amount into many
        # stops of invented exposure. The forward model keeps its terminal-slope
        # extension, so forward and inverse agree only within the published
        # span; the clean-cell diagnostic below reports where that holds.
        logH = np.stack([interp_lin(np.clip(pre[:, l], a[0], a[-1]), a, h)
                         for l, (a, h) in enumerate(self.neutral_tab)], axis=1)
        return 10.0 ** (logH - self.logH_mid)

    # ---------- forward film model (exposure -> normalized scan density) ------
    def L_to_scan_norm(self, L):
        L = np.atleast_2d(L)
        logH = np.log10(np.clip(L, 1e-12, None)) + self.logH_mid
        pre = np.stack([interp_lin(logH[:, l], self.neutral_tab[l][1], self.neutral_tab[l][0])
                        for l in range(3)], axis=1)
        dye = iim.apply_dir(pre, self.DIR) if self.interimage_on else pre
        return self.scan_fwd(dye) / DMAX

    # ---------- colorimetry ----------
    def L_of_reflectance(self, R):
        """Relative layer exposures of reflectance R under the scene illuminant."""
        ref = GRAY * np.ones_like(CGRID)
        out = []
        for layer in LAYERS:
            s = self.SENS[layer] * self.ILL
            out.append((s @ R) / (s @ ref))
        return np.array(out)

    def XYZ_of_reflectance(self, R):
        """Colorimetric XYZ(D65) of R (gray-18 -> Y=0.18), Bradford adapted."""
        Xs = (self.CMF @ (R * self.ILL)) / self.Yw_scene
        return self.M_cat @ Xs

    def _LX_of_set(self, spectra):
        Ls = np.array([self.L_of_reflectance(R) for _, R in spectra])
        Xs = np.array([self.XYZ_of_reflectance(R) for _, R in spectra])
        return Ls, Xs

    def _solve_matrix(self, L_arr, X_arr, w_arr):
        """Weighted least-squares 3x3 (X = M @ L) with the exact grey row-
        normalization so a flat 18% grey (L=(1,1,1)) maps to the colorimetric
        grey target exactly."""
        w = np.sqrt(w_arr)[:, None]
        A = L_arr * w; B = X_arr * w
        M, *_ = np.linalg.lstsq(A, B, rcond=None)         # L @ M = X
        M = M.T                                            # X = M @ L
        g_target = self.XYZ_of_reflectance(GRAY * np.ones_like(CGRID))
        g_now = M @ np.ones(3)
        return M * (g_target / g_now)[:, None], g_now

    def _fit_matrix(self):
        # ---- ColorChecker 24 ----
        cc = colour.SDS_COLOURCHECKERS["babel_average"]
        self.cc_name = "babel_average"
        shp = colour.SpectralShape(CGRID[0], CGRID[-1], 1)
        names = list(cc.keys())
        Ls, Xs, wts = [], [], []
        for i, nm in enumerate(names):
            R = cc[nm].copy().align(shp).values
            Ls.append(self.L_of_reflectance(R))
            Xs.append(self.XYZ_of_reflectance(R))
            wts.append(4.0 if i >= len(names) - 6 else 1.0)   # last 6 = neutrals
        self.cc_L = np.array(Ls); self.cc_X = np.array(Xs)
        self.cc_names = names; self.cc_w = np.array(wts)

        self.M_checker, gnow_checker = self._solve_matrix(self.cc_L, self.cc_X, self.cc_w)

        # ---- broad set ----
        self.broad_sets = {}
        blocks_L, blocks_X, blocks_w = [], [], []
        for set_name, set_weight in BROAD_SET_WEIGHTS.items():
            spectra = load_reflectance_set(REFLECTANCE_DIR / (set_name + ".json"))
            La, Xa = self._LX_of_set(spectra)
            self.broad_sets[set_name] = (La, Xa)
            blocks_L.append(La); blocks_X.append(Xa)
            blocks_w.append(np.full(len(spectra), set_weight / len(spectra)))
        cc_w_scaled = self.cc_w * (CHECKER_TOTAL_WEIGHT / self.cc_w.sum())
        blocks_L.insert(0, self.cc_L); blocks_X.insert(0, self.cc_X)
        blocks_w.insert(0, cc_w_scaled)
        L_all = np.concatenate(blocks_L); X_all = np.concatenate(blocks_X)
        w_all = np.concatenate(blocks_w)
        self.M_broad, gnow_broad = self._solve_matrix(L_all, X_all, w_all)

        if MATRIX_MODE not in ("broad", "checker"):
            raise ValueError("MATRIX_MODE must be 'broad' or 'checker'")
        self.matrix_mode = MATRIX_MODE
        self.M = self.M_broad if MATRIX_MODE == "broad" else self.M_checker
        self.M_gray_before = gnow_broad if MATRIX_MODE == "broad" else gnow_checker
        self.M_gray_after = self.M @ np.ones(3)

    # ---------- Lab / dE ----------
    def _lab(self, XYZ):
        return colour.XYZ_to_Lab(np.asarray(XYZ), colour.XYZ_to_xy(self.white_ref))

    def dE(self, XYZ_a, XYZ_b):
        return colour.delta_E(self._lab(XYZ_a), self._lab(XYZ_b), method="CIE 2000")


# ================= corridor requirement (reporting only) =================
def corridor_requirement(eng, dye_ceiling):
    """Peak scan density over the dye box [0, dye_ceiling]^3 -- neutral AND a
    coarse off-neutral sweep, max over channels (mirrors adx_engine)."""
    axis = np.linspace(0.0, dye_ceiling, 5)
    sweep = np.array(np.meshgrid(axis, axis, axis, indexing="ij")).reshape(3, -1).T
    probes = np.vstack([np.full((1, 3), dye_ceiling), sweep])
    return float(np.max(eng.scan_fwd(probes)))


def datasheet_dye_ceiling(eng):
    """Neutral dye amount whose stack, over the traced mask, reaches this
    stock's deepest published density (the characteristic curves' maximum,
    absolute), so the probe box ends where the neutral tables do."""
    peak = max(float(fp.max()) for _, fp in eng.char.values())

    def f(d):
        return float(np.max(eng.statusm_abs(np.full((1, 3), d))))
    lo, hi = 0.0, 32.0
    if f(hi) < peak:
        return hi
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if f(mid) < peak:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ================= build + metrics =================
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stock", choices=sorted(STOCKS), required=True,
                    help="Vision3 stock to build")
    ap.add_argument("--sensor", default=DEFAULT_SENSOR,
                    help="camera SSF: 'none' for a unity (monochrome) response, "
                         "or a bare name from data/cameras/ or a path "
                         "(default: %s)" % DEFAULT_SENSOR)
    args = ap.parse_args(argv)
    sensor_path, sensor_label = resolve_sensor(args.sensor)
    eng = V3SceneEngine(args.stock, sensor_path, sensor_label)
    p = eng.p
    print("=== Vision3 scene engine :: %s ===" % eng.name)
    print("densitometry grid: %.0f-%.0f nm (measured dye support)"
          % (eng.DGRID[0], eng.DGRID[-1]))
    print("sensor: %s" % eng.sensor_label)
    print("D-min: EXCLUDED from cube input; the traced Minimum Density curve filters the "
          "scan-side illuminant (LED centroid shift R/G/B %s nm) and sits under the dyes "
          "in the neutral solve; its Status M %s against the char sheet's D-min triplet %s "
          "(delta %s)"
          % (np.round(eng.mask_centroid_shift_nm, 2).tolist(),
             np.round(eng.mask_statusM, 3).tolist(), np.round(eng.dmin, 3).tolist(),
             np.round(eng.mask_statusM - eng.dmin, 3).tolist()))
    print("neutral amount tables: full 3-channel Status M solve over logH %.2f..%.2f, "
          "max |dD| %.1e; %.1f%% of points need a negative amount (toe); tie points "
          "dropped per layer %s; amounts at logH_mid %s"
          % (eng.neutral_logH[0], eng.neutral_logH[-1], eng.neutral_solve_max_resid,
             100 * eng.neutral_negative_frac, eng.neutral_dropped,
             np.round(eng.neutral_amt[np.argmin(np.abs(eng.neutral_logH - eng.logH_mid))], 3).tolist()))
    print("Status M red truncation: renormalized on the grid; excluded tail = "
          "%.2f%% of red area." % eng.red_tail_pct)
    print("scene illuminant: %s   XYZ->DWG matrix source: %s"
          % (p["scene_illuminant"], eng.dwg_src))
    print("matrix mode: %s (cube uses M_%s)" % (eng.matrix_mode, eng.matrix_mode))
    print(iim.status_line("v3scene:", eng.DIR))

    # ---- logH_mid provenance ----
    print("logH_mid per channel R,G,B = %s   avg %.4f   spread %.4f   "
          "(midscale trace support %.0f-%.0f nm)"
          % (np.round(eng.logH_mid_per, 4).tolist(), eng.logH_mid,
             float(eng.logH_mid_per.max() - eng.logH_mid_per.min()),
             eng.mid_wl.min(), eng.mid_wl.max()))
    print("cross-check: sheet camera-stops zero at logH %.4f (NOT used; "
          "difference to logH_mid = %.3f logH, a uniform exposure trim)"
          % (eng.stop0, eng.stop0 - eng.logH_mid))

    # ---- matrix fit comparison ----
    print("=== matrix comparison :: dE2000 mean/max per set, both matrices ===")
    print("  %-20s %6s | %-14s | %-14s" % ("set", "n", "checker M", "broad M"))
    eval_sets = [("ColorChecker24", eng.cc_L, eng.cc_X)]
    eval_sets += [(nm, La, Xa) for nm, (La, Xa) in eng.broad_sets.items()]
    for nm, La, Xa in eval_sets:
        dEc = eng.dE((eng.M_checker @ La.T).T, Xa)
        dEb = eng.dE((eng.M_broad @ La.T).T, Xa)
        print("  %-20s %6d | mean %5.2f max %5.2f | mean %5.2f max %5.2f"
              % (nm, len(La), dEc.mean(), dEc.max(), dEb.mean(), dEb.max()))
    print("gray-18 XYZ before row-renorm %s -> after %s (target %s)"
          % (np.round(eng.M_gray_before, 4).tolist(),
             np.round(eng.M_gray_after, 4).tolist(),
             np.round(eng.XYZ_of_reflectance(GRAY * np.ones_like(CGRID)), 4).tolist()))

    # ---- ColorChecker matrix-only residual ----
    Xfit = (eng.M @ eng.cc_L.T).T
    dE_mat = eng.dE(Xfit, eng.cc_X)
    print("=== ColorChecker matrix-only residual (M@L vs colorimetric XYZ) ===")
    print("dE2000  mean %.3f  max %.3f  (patch %s)"
          % (dE_mat.mean(), dE_mat.max(), eng.cc_names[int(np.argmax(dE_mat))]))

    # ---- full chain (plumbing check only; see module docstring caveat) ----
    Dnorm = eng.L_to_scan_norm(eng.cc_L)
    L_rec = eng.scan_norm_to_L(Dnorm)
    Xfull = (eng.M @ L_rec.T).T
    dE_full = eng.dE(Xfull, eng.cc_X)
    print("=== ColorChecker FULL chain (reflectance->film fwd->inverse->M) ===")
    print("dE2000  mean %.3f  max %.3f  (plumbing check: fwd/inverse share "
          "machinery, so this must and does track the matrix-only figure)"
          % (dE_full.mean(), dE_full.max()))

    # ---- neutral-axis exposure ramp ----
    print("=== neutral-axis: flat-gray exposure ramp (logH_mid +/- 2.0, 0.5 steps) ===")
    print(" dlogH   DWG(R,G,B)              chroma_err   lumaY      Y/Y0    expected 10^d")
    Y0 = float((eng.M @ eng.scan_norm_to_L(
        eng.L_to_scan_norm(np.ones((1, 3)))).T).T[0, 1])
    for d in np.arange(-2.0, 2.001, 0.5):
        L = np.full((1, 3), 10.0 ** d)
        Dn = eng.L_to_scan_norm(L)
        Lr = eng.scan_norm_to_L(Dn)
        X = (eng.M @ Lr.T).T
        dwg = (eng.XYZ_to_DWG @ X.T).T[0]
        Y = float(X[0, 1])
        chroma_err = float(np.max(np.abs(dwg - dwg.mean())) / max(abs(dwg.mean()), 1e-9))
        print("  %+.1f   %-24s  %.4f      %.5f  %.4f   %.4f"
              % (d, np.round(dwg, 4).tolist(), chroma_err, Y, Y / Y0, 10.0 ** d))

    # ---- corridor requirement (reporting only; DMAX unchanged) ----
    needed = corridor_requirement(eng, datasheet_dye_ceiling(eng))
    print("corridor: this stock's published maximum needs %.2f D scan density, "
          "DMAX is %.2f (%.0f%% headroom)"
          % (needed, DMAX, 100.0 * (DMAX - needed) / needed))

    # ================= build 65^3 cube =================
    ax = np.linspace(0.0, 1.0, SZ)
    node = np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T
    dye = eng.invert_scan(node * DMAX)
    res = np.max(np.abs(eng.scan_fwd(dye) - node * DMAX), 1)
    interior = np.all((dye > -0.5 + 1e-6) & (dye < 6.0 - 1e-6), axis=1)
    ri = res[interior]
    print("node solve: residual mean %.4f max %.4f D over all %d nodes; "
          "on the %.1f%% of nodes solved inside the dye box: "
          "mean %.6f p99 %.6f max %.4f D, >0.02 D on %.2f%% "
          "(the remainder are density combinations no dye stack reaches)"
          % (res.mean(), res.max(), len(res), 100 * interior.mean(),
             ri.mean(), float(np.percentile(ri, 99)), ri.max(),
             100 * np.mean(ri > 0.02)))
    L_lat = eng.scan_norm_to_L(node)
    XYZ_lat = (eng.M @ L_lat.T).T
    dwg_lat = (eng.XYZ_to_DWG @ XYZ_lat.T).T              # scene-linear DWG, no clamp
    lut = dwg_lat.reshape(SZ, SZ, SZ, 3)

    neg_dwg = 100.0 * np.mean(np.any(dwg_lat < 0.0, axis=1))
    r2020 = (eng.DWG_to_2020 @ dwg_lat.T).T
    neg_2020 = 100.0 * np.mean(np.any(r2020 < 0.0, axis=1))
    print("=== gamut coverage of 65^3 output lattice ===")
    print("outside DWG unit gamut (any negative)          : %.2f%%" % neg_dwg)
    print("outside Rec.2020 (any negative after DWG->2020): %.2f%%" % neg_2020)

    # ---- emit cube ----
    if sensor_path is None:
        CUBE = BUILDS / "ecn2" / ("Vision3 %s to Scene DWG.cube" % eng.name)
    else:
        CUBE = (BUILDS / ("sensor-%s" % sensor_stem(args.sensor)) / "ecn2"
                / ("Vision3 %s to Scene DWG.cube" % eng.name))
    CUBE.parent.mkdir(parents=True, exist_ok=True)
    with open(CUBE, "w") as f:
        f.write("# %s scanner density -> scene-linear DaVinci Wide Gamut\n"
                % p["display_name"])
        f.write("# INPUT  = normalized scanner density [0,1]^3 = OD/%.2f, "
                "D-MIN EXCLUDED\n" % DMAX)
        f.write("#          (same input point as 'Vision3 to ADX16.cube': "
                "-log10(linear), D-min subtracted, /%.2f)\n" % DMAX)
        f.write("# OUTPUT = scene-linear DaVinci Wide Gamut (D65); negatives "
                "allowed (float)\n")
        f.write("# scene illuminant %s; sensor: %s\n"
                % (p["scene_illuminant"], eng.sensor_label))
        f.write("LUT_3D_SIZE %d\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n" % SZ)
        flat = lut.transpose(2, 1, 0, 3).reshape(-1, 3)   # cube: R fastest, no clamp
        for v in flat:
            f.write("%.6f %.6f %.6f\n" % (v[0], v[1], v[2]))

    # ---- serialization round-trip ----
    def read_cube(path, size):
        vals = []
        for line in Path(path).read_text().splitlines():
            parts = line.split()
            if len(parts) == 3:
                try:
                    vals.append([float(x) for x in parts])
                except ValueError:
                    pass
        a = np.array(vals)
        if a.shape != (size ** 3, 3):
            raise ValueError("Unexpected cube payload %s" % (a.shape,))
        return a.reshape(size, size, size, 3).transpose(2, 1, 0, 3)
    rt = read_cube(CUBE, SZ)
    rmse = float(np.sqrt(np.mean((rt - lut) ** 2)))
    print("serialized %s: round-trip RMSE %.3e  max %.3e"
          % (CUBE.name, rmse, float(np.max(np.abs(rt - lut)))))

    # ---- trilinear LUT vs exact chain over probe dye boxes ----
    # Mirrors adx_engine's validation: the cube is exact at its nodes by
    # construction, so what needs measuring is the trilinear interpolation
    # error between them, in the output's own units. Relative DWG error is
    # the meaningful figure for a scene-linear output spanning decades.
    def trilerp(Larr, pts):
        x = np.clip(pts / DMAX, 0, 1) * (SZ - 1)
        i = np.minimum(np.floor(x).astype(int), SZ - 2)
        fr = x - i
        out = np.zeros((len(pts), 3))
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    w = ((fr[:, 0] if dx else 1 - fr[:, 0])
                         * (fr[:, 1] if dy else 1 - fr[:, 1])
                         * (fr[:, 2] if dz else 1 - fr[:, 2]))
                    out += w[:, None] * Larr[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
        return out

    # A lattice cell is CLEAN when all eight corner nodes CONVERGED (scan
    # residual within CLEAN_TOL_D, not merely inside the solver's clipping
    # box) AND every layer's amount at every corner lies within BOTH ends of
    # its neutral table, so that no corner value sits on a table's clamp at
    # either the toe or the shoulder (Rule 4: the inverse lookup clamps, never
    # runs off the shoulder). Any other cell mixes clamped or unconverged
    # corners into the interpolation, and its error is not an interpolation
    # figure. Table membership is tested on the pre-interimage
    # amounts, which are what the tables index.
    tab_lo = np.array([float(t[0][0]) for t in eng.neutral_tab])
    tab_top = np.array([float(t[0][-1]) for t in eng.neutral_tab])
    pre_lat = iim.precompensate(dye, eng.DIR) if eng.interimage_on else dye
    node_clean = (interior & (res <= CLEAN_TOL_D)
                  & np.all((pre_lat >= tab_lo[None, :]) & (pre_lat <= tab_top[None, :]), axis=1)
                  ).reshape(SZ, SZ, SZ)

    def cell_clean(pts):
        x = np.clip(pts / DMAX, 0, 1) * (SZ - 1)
        i = np.minimum(np.floor(x).astype(int), SZ - 2)
        ok = np.ones(len(pts), bool)
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    ok &= node_clean[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
        return ok

    def stats(rel):
        return (rel.mean(), float(np.percentile(rel, 99)), rel.max()) if rel.size else (np.nan,) * 3

    Y_mid = float((eng.M @ np.ones((3, 1)))[1, 0])

    def probe(label, ceiling, detail=False):
        ceiling = np.broadcast_to(np.asarray(ceiling, float), (3,))
        gv = np.random.default_rng(1).uniform(0, 1, (5000, 3)) * ceiling
        sv = eng.scan_fwd(gv)
        XYZ_t = (eng.M @ eng.scan_norm_to_L(sv / DMAX).T).T
        truth = (eng.XYZ_to_DWG @ XYZ_t.T).T
        approx = trilerp(rt, sv)
        rel = np.abs(approx - truth) / np.maximum(np.abs(truth), 1e-3)
        print("LUT trilinear vs exact chain [%s, dye 0-%s]: rel err "
              "mean %.4f p99 %.4f max %.4f  (abs max %.4f DWG)"
              % (label, "/".join("%.2f" % c for c in ceiling), rel.mean(),
                 float(np.percentile(rel, 99)), rel.max(),
                 float(np.max(np.abs(approx - truth)))))
        if not detail:
            return
        # separate interpolation from extrapolation and inverse failure, and
        # declare the region: the figures a user of the cube can rely on are
        # the CLEAN-cell ones, banded by how bright the scene value is.
        clean = cell_clean(sv)
        per = rel.max(1)
        print("  by lattice cell: CLEAN (all 8 corners converged to %.0e D and "
              "within both ends of every table) %.1f%% of samples: mean %.4f "
              "p99 %.4f max %.4f; the rest (a corner on a table's end clamp "
              "or unconverged): "
              "mean %.4f p99 %.4f max %.4f"
              % ((CLEAN_TOL_D, 100 * clean.mean(),) + stats(per[clean]) + stats(per[~clean])))
        yrel = XYZ_t[:, 1] / Y_mid
        edges = [(0, 1), (1, 10), (10, 100), (100, np.inf)]
        print("  by exact-chain luminance, multiples of mid-grey, CLEAN cells only "
              "(n, mean, p99, max):")
        for lo, hi in edges:
            m = clean & (yrel >= lo) & (yrel < hi)
            print("    %5s-%-5s n=%4d  %s"
                  % (lo, "inf" if hi == np.inf else hi, int(m.sum()),
                     "mean %.4f p99 %.4f max %.4f" % stats(per[m]) if m.any() else "--"))
        m = clean & (yrel < 100)
        print("  DECLARED OPERATING REGION -- clean cells, below 100x mid-grey: "
              "%.1f%% of samples, mean %.4f p99 %.4f max %.4f"
              % ((100 * m.mean(),) + stats(per[m])))
    probe("working range", 2.2)
    # the published span, per layer: the top of each neutral-scale table is the
    # largest amount the sheet's curves document for that layer; beyond it the
    # inverse is clamped at the table's end, which the working-range probe
    # above exercises deliberately
    probe("published char span", [float(t[0][-1]) for t in eng.neutral_tab], detail=True)
    # Endpoint regression (Rule 4), exercised through the DELIVERED inverse,
    # scan_norm_to_L, not through a restatement of its clipping expression:
    # a dye state whose one layer sits at a table end and the same state with
    # that layer pushed beyond the end must decode to the same exposure, and
    # that exposure must be the table end's. The state enters the way a scan
    # does (forward model to normalised scanner density, then the unmix), so
    # the tolerance is the scan inverse's, not machine precision. Removing
    # the clip from scan_norm_to_L fails this on every layer.
    mid = np.array([float(np.median(t[0])) for t in eng.neutral_tab])
    worst_ratio = 0.0
    for l, (a, h) in enumerate(eng.neutral_tab):
        for edge, amt_end, amt_out, want in (("toe", a[0], a[0] - 0.3, h[0]),
                                             ("shoulder", a[-1], a[-1] + 0.5, h[-1])):
            pre = np.stack([mid, mid]); pre[0, l] = amt_end; pre[1, l] = amt_out
            dye = iim.apply_dir(pre, eng.DIR) if eng.interimage_on else pre
            L = eng.scan_norm_to_L(eng.scan_fwd(dye) / DMAX)
            ratio = float(L[1, l] / L[0, l])
            worst_ratio = max(worst_ratio, abs(np.log10(ratio)))
            assert abs(np.log10(ratio)) < 1e-4, ("inverse not clamped", l, edge, ratio)
            assert abs(np.log10(L[0, l]) + eng.logH_mid - want) < 1e-3, (l, edge, L[0, l], want)
    print("inverse endpoint clamp (through scan_norm_to_L): a layer 0.3 amount below its table "
          "toe or 0.5 above its shoulder decodes to the end's exposure, worst |dlogH| %.1e "
          "(a terminal-slope extension would give %s logH at the shoulders)"
          % (worst_ratio,
             np.round([h[-1] + 0.5 * (h[-1] - h[-2]) / (a[-1] - a[-2]) for a, h in eng.neutral_tab], 1).tolist()))
    print("wrote %s" % CUBE.relative_to(ROOT))


if __name__ == "__main__":
    main()
