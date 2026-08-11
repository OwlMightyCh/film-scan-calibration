#!/usr/bin/env python3
"""RETIRED 2026-08-03 -- the scene-referred output route is no longer shipped.

A colour negative is designed to be PRINTED, and the print branch is now the
only C-41 delivery route: every stock lands through RA-4 paper emulation
(builds/c41/print_endura/ for Kodak, print_fuji/ for Fujifilm), matching how
these films were meant to be seen. The 10 <Stock>_StatusM_to_DWG.cube artifacts
this file produced were deleted; git history keeps them. The print engines'
own cube headers already described themselves as "REPLACES StatusM_to_DWG".

MOVED here rather than deleted, following the dctl/retired/ precedent, so it
cannot be picked up by accident but is not lost. What is still valuable in it,
and is NOT duplicated anywhere else in the repo:
  * the 3x3 matrix fit against 3,258 measured reflectances (Munsell glossy/matt,
    Agfa IT8.7/2, NIST skin) with per-set weighting, and the checker-vs-broad
    comparison that showed the ColorChecker-only matrix was already near optimal
  * the ColorChecker full-chain dE2000 harness, which is how the saturated-red
    dE 6.3 was shown to be a forward-model limit rather than a matrix artifact
  * the neutral-axis exposure-ramp diagnostic (chroma error, luminance tracking)
The interimage/DIR stage is NOT lost with it -- that lives in
engine/common/interimage.py and is still used by the surviving engines.

<Stock>_StatusM.cube is NOT retired. It is the front of the chain: the print
engines and dctl/output/'Print Adjustment.dctl' all consume it.

To run it anyway (writes into builds/c41/, which nothing else reads now):
    python3 engine/retired/c41_scene_engine.py --stock <name>

Original header follows.
=============================================================================
C-41 scene-referred engine: Status M density -> scene-linear DaVinci Wide Gamut.

Route A. Builds a 65^3 .cube that chains directly AFTER
builds/Portra400_StatusM.cube (replacing that build's postshaper +
Density-to-Linear).  Input domain is exactly that cube's output: normalized
Status M density [0,1]^3 = OD/3.30 per channel, D-MIN EXCLUDED.  Output is
scene-linear DaVinci Wide Gamut (D65), negatives allowed, no clamp.

Pipeline per lattice node (normalized Status M density, D-min excluded):
  1. de-normalize to OD, ADD the datasheet D-min Status M triplet;
  2. invert integral Status M densitometry (Gauss-Newton, mirrors
     c41_statusm_engine) -> image-dye amounts (dc,dm,dy) >= 0;
  3. per layer reconstruct its primary channel's Status M density
     (dmin_ch + S[ch][layer]*amount_layer) and invert that channel's
     characteristic curve (monotone, terminal-slope linear extension) -> logH;
  4. relative layer exposure L = 10^(logH - logH_mid), logH_mid from the
     digitized midscale neutral;
  5. 3x3 matrix M (fit to the 24 ColorChecker patches, spectral, under D55,
     Bradford-adapted to D65) maps L -> XYZ(D65);
  6. XYZ(D65) -> DWG linear via the standard DaVinci Wide Gamut matrix.

Stock parameters live in the STOCKS dict ("portra400", "portra160"), selected
with --stock.  All the self-reported metrics required for cheap main-model
verification are printed.
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
from engine.common import interimage as iim   # noqa: E402
from engine.common.spectral import interp_lin, resample   # noqa: E402
sys.path.insert(0, str(ROOT / "engine" / "c41"))   # portra_stocks lives there
from portra_stocks import STOCKS as PORTRA_STOCKS   # noqa: E402

# ----- integration grids -----
DGRID = np.arange(400, 701, 1.0)                 # dye / Status M density grid
CGRID = np.arange(380, 731, 1.0)                 # colorimetric grid
DMAX = 3.30                                       # normalization (matches narrowband cube)
GRAY = 0.18                                        # scene mid-gray reflectance

# Which fitted matrix drives the cube: "broad" (ColorChecker + Munsell/IT8.7-2/
# NIST-skin broad set) or "checker" (legacy ColorChecker-24 only).  One-word
# switch; everything downstream uses the selected matrix.
MATRIX_MODE = "broad"

# 3x3 DIR / interimage inhibition matrix (dye-amount space).  Default identity =>
# interimage stage is skipped and outputs stay bit-identical to the pre-feature
# engine.  Set off-identity to model inter-layer inhibition.
DIR_MATRIX = np.eye(3)

# Broad-set per-set training weights (see _fit_matrix); each spectrum in a set is
# weighted set_weight / n_spectra so no set dominates.  ColorChecker keeps its
# existing absolute per-patch weights, rescaled so the checker's total == 24.
BROAD_SET_WEIGHTS = {
    "munsell_glossy_all": 24.0,
    "munsell_matt":       12.0,
    "agfa_it872":         12.0,
    "nist_skin":          24.0,
}
CHECKER_TOTAL_WEIGHT = 24.0
REFLECTANCE_DIR = DATA / "standards" / "reflectance"


# ================= stock table =================
# Display names and data filenames come from the shared registry
# (engine/c41/portra_stocks.py) so provenance is stated in exactly one place.
STOCKS = {
    "portra400": {
        "dye_density":   DATA / "films" / "Portra400_dye_density.json",
        "char_curves":   DATA / "films" / "Portra400_datasheet_curves.json",
        "sensitivity":   DATA / "films" / "Portra400_spectral_sensitivity.json",
        "statusM":       DATA / "standards" / "StatusM_ISO5-3.json",
        "cmfs":          DATA / "standards" / "CIE1931_2deg_CMFs.json",
        # layer -> primary Status M channel (cyan images in red, etc.)
        "layer_channel": {"cyan": "R", "magenta": "G", "yellow": "B"},
        # dye/exposure triplet ordering used throughout
        "layers":        ["cyan", "magenta", "yellow"],
        "scene_illuminant": "D55",     # datasheet daylight
        "out_cube":      BUILDS / "c41" / "Portra400_StatusM_to_DWG.cube",
        # header provenance: display name + the upstream cube this one chains after
        "display_name":  PORTRA_STOCKS["portra400"]["display_name"],
        "statusm_cube": "Portra400_StatusM.cube",
    },
    "portra160": {
        "dye_density":   DATA / "films" / "Portra160_dye_density.json",
        "char_curves":   DATA / "films" / "Portra160_datasheet_curves.json",
        "sensitivity":   DATA / "films" / "Portra160_spectral_sensitivity.json",
        "statusM":       DATA / "standards" / "StatusM_ISO5-3.json",
        "cmfs":          DATA / "standards" / "CIE1931_2deg_CMFs.json",
        "layer_channel": {"cyan": "R", "magenta": "G", "yellow": "B"},
        "layers":        ["cyan", "magenta", "yellow"],
        "scene_illuminant": "D55",     # datasheet daylight
        "out_cube":      BUILDS / "c41" / "Portra160_StatusM_to_DWG.cube",
        "display_name":  PORTRA_STOCKS["portra160"]["display_name"],
        "statusm_cube": "Portra160_StatusM.cube",
    },
    "gold200": {
        "dye_density":   DATA / "films" / "Gold200_dye_density.json",
        "char_curves":   DATA / "films" / "Gold200_datasheet_curves.json",
        "sensitivity":   DATA / "films" / "Gold200_spectral_sensitivity.json",
        "statusM":       DATA / "standards" / "StatusM_ISO5-3.json",
        "cmfs":          DATA / "standards" / "CIE1931_2deg_CMFs.json",
        "layer_channel": {"cyan": "R", "magenta": "G", "yellow": "B"},
        "layers":        ["cyan", "magenta", "yellow"],
        "scene_illuminant": "D55",     # datasheet daylight
        "out_cube":      BUILDS / "c41" / "Gold200_StatusM_to_DWG.cube",
        "display_name":  PORTRA_STOCKS["gold200"]["display_name"],
        "statusm_cube": "Gold200_StatusM.cube",
        # Sensitivity digitized 2026-07-29 by stitching ~65 path fragments
        # (portra_digitize_sens.py --stock gold200); this stock was blocked here
        # until then. One genuine gap, cyan 470-485 nm, is null not bridged.
    },
    "ultramax400": {
        "dye_density":   DATA / "films" / "Ultramax400_dye_density.json",
        "char_curves":   DATA / "films" / "Ultramax400_datasheet_curves.json",
        "sensitivity":   DATA / "films" / "Ultramax400_spectral_sensitivity.json",
        "statusM":       DATA / "standards" / "StatusM_ISO5-3.json",
        "cmfs":          DATA / "standards" / "CIE1931_2deg_CMFs.json",
        "layer_channel": {"cyan": "R", "magenta": "G", "yellow": "B"},
        "layers":        ["cyan", "magenta", "yellow"],
        "scene_illuminant": "D55",     # datasheet daylight
        "out_cube":      BUILDS / "c41" / "Ultramax400_StatusM_to_DWG.cube",
        "display_name":  PORTRA_STOCKS["ultramax400"]["display_name"],
        "statusm_cube": "Ultramax400_StatusM.cube",
    },
    "fujifilm200": {
        "dye_density":   DATA / "films" / "Fujifilm200_dye_density.json",
        "char_curves":   DATA / "films" / "Fujifilm200_datasheet_curves.json",
        "sensitivity":   DATA / "films" / "Fujifilm200_spectral_sensitivity.json",
        "statusM":       DATA / "standards" / "StatusM_ISO5-3.json",
        "cmfs":          DATA / "standards" / "CIE1931_2deg_CMFs.json",
        "layer_channel": {"cyan": "R", "magenta": "G", "yellow": "B"},
        "layers":        ["cyan", "magenta", "yellow"],
        "scene_illuminant": "D55",     # datasheet daylight
        "out_cube":      BUILDS / "c41" / "Fujifilm200_StatusM_to_DWG.cube",
        "display_name":  PORTRA_STOCKS["fujifilm200"]["display_name"],
        "statusm_cube": "Fujifilm200_StatusM.cube",
        # CAVEATS -- this stock carries every Fujifilm 400 limitation plus one
        # of its own:
        #  * SHARED DYE ARTWORK. Fujifilm publishes ONE spectral-dye-density
        #    chart across the 200 and 400 datasheets -- byte-identical Bezier
        #    control points. So Fujifilm200_dye_density.json is numerically
        #    identical to Fujifilm400's, and Fujifilm200_StatusM.cube is a
        #    duplicate of Fujifilm400's by construction. This scene cube is
        #    the FIRST point at which the two stocks actually diverge, via
        #    their own characteristic curves and spectral sensitivities.
        #  * Log-sensitivity axis is RELATIVE with no absolute origin (the
        #    sheet prints only a 1.0-decade scale bar), as on the 400 sheet.
        #    Layer speed RATIOS survive; absolute speed does not.
        #  * Aggregate fits the Vision3 surrogate basis 2-3x worse than any
        #    Kodak stock (0.0338 D), and its shift bound stays at +/-15 nm
        #    because releasing it reaches a degenerate solution -- see
        #    portra_stocks.py.
    },
    "fujifilm400": {
        "dye_density":   DATA / "films" / "Fujifilm400_dye_density.json",
        "char_curves":   DATA / "films" / "Fujifilm400_datasheet_curves.json",
        "sensitivity":   DATA / "films" / "Fujifilm400_spectral_sensitivity.json",
        "statusM":       DATA / "standards" / "StatusM_ISO5-3.json",
        "cmfs":          DATA / "standards" / "CIE1931_2deg_CMFs.json",
        "layer_channel": {"cyan": "R", "magenta": "G", "yellow": "B"},
        "layers":        ["cyan", "magenta", "yellow"],
        "scene_illuminant": "D55",     # datasheet daylight
        "out_cube":      BUILDS / "c41" / "Fujifilm400_StatusM_to_DWG.cube",
        "display_name":  PORTRA_STOCKS["fujifilm400"]["display_name"],
        "statusm_cube": "Fujifilm400_StatusM.cube",
        # CAVEAT: Fujifilm 400's log-sensitivity axis is RELATIVE with an
        # arbitrary origin (the sheet prints only a 1.0-decade scale bar). The
        # per-layer speed RATIOS are preserved -- all three curves were read off
        # one chart -- so the matrix fit is valid, but absolute speed is not.
        # Its aggregate also fits the Vision3 surrogate basis 2-3x worse than any
        # Kodak stock (0.0338 D), so this cube is the fleet's least confident.
    },
    "ektar100": {
        "dye_density":   DATA / "films" / "Ektar100_dye_density.json",
        "char_curves":   DATA / "films" / "Ektar100_datasheet_curves.json",
        "sensitivity":   DATA / "films" / "Ektar100_spectral_sensitivity.json",
        "statusM":       DATA / "standards" / "StatusM_ISO5-3.json",
        "cmfs":          DATA / "standards" / "CIE1931_2deg_CMFs.json",
        "layer_channel": {"cyan": "R", "magenta": "G", "yellow": "B"},
        "layers":        ["cyan", "magenta", "yellow"],
        "scene_illuminant": "D55",     # datasheet daylight
        "out_cube":      BUILDS / "c41" / "Ektar100_StatusM_to_DWG.cube",
        "display_name":  PORTRA_STOCKS["ektar100"]["display_name"],
        "statusm_cube": "Ektar100_StatusM.cube",
    },
    "fujicolor100": {
        "dye_density":   DATA / "films" / "Fujicolor100_dye_density.json",
        "char_curves":   DATA / "films" / "Fujicolor100_datasheet_curves.json",
        "sensitivity":   DATA / "films" / "Fujicolor100_spectral_sensitivity.json",
        "statusM":       DATA / "standards" / "StatusM_ISO5-3.json",
        "cmfs":          DATA / "standards" / "CIE1931_2deg_CMFs.json",
        "layer_channel": {"cyan": "R", "magenta": "G", "yellow": "B"},
        "layers":        ["cyan", "magenta", "yellow"],
        "scene_illuminant": "D55",     # datasheet daylight
        "out_cube":      BUILDS / "c41" / "Fujicolor100_StatusM_to_DWG.cube",
        "display_name":  PORTRA_STOCKS["fujicolor100"]["display_name"],
        "statusm_cube": "Fujicolor100_StatusM.cube",
        # CAVEAT: Japanese-market sheet (013AR0317A). Process CN-16, densitometry
        # Status M equivalent, exposure daylight -- per the sheet, so directly
        # comparable to the other Fuji entries here.
        # Its log-sensitivity axis is RELATIVE with an arbitrary origin (the
        # sheet prints only a 1.0-decade scale bar, 57.19 pt/decade). The
        # per-layer speed RATIOS are preserved -- all three curves were read off
        # one chart -- so the matrix fit is valid, but absolute speed is not.
        # Its shift bound stays at +/-15 nm because it is a Fujifilm stock; the
        # released 25 nm bound is Kodak-only -- see portra_stocks.py.
    },
    "superiapremium400": {
        "dye_density":   DATA / "films" / "SuperiaPremium400_dye_density.json",
        "char_curves":   DATA / "films" / "SuperiaPremium400_datasheet_curves.json",
        "sensitivity":   DATA / "films" / "SuperiaPremium400_spectral_sensitivity.json",
        "statusM":       DATA / "standards" / "StatusM_ISO5-3.json",
        "cmfs":          DATA / "standards" / "CIE1931_2deg_CMFs.json",
        "layer_channel": {"cyan": "R", "magenta": "G", "yellow": "B"},
        "layers":        ["cyan", "magenta", "yellow"],
        "scene_illuminant": "D55",     # datasheet daylight
        "out_cube":      BUILDS / "c41" / "SuperiaPremium400_StatusM_to_DWG.cube",
        "display_name":  PORTRA_STOCKS["superiapremium400"]["display_name"],
        "statusm_cube": "SuperiaPremium400_StatusM.cube",
        # CAVEAT: as Fujicolor 100 above -- Japanese-market sheet (013AR0324A),
        # process CN-16, Status M equivalent densitometry, and a RELATIVE
        # log-sensitivity axis (1.0-decade scale bar only, 57.19 pt/decade) that
        # preserves layer speed ratios but not absolute speed. Shift bound
        # +/-15 nm, Fujifilm.
    },
}


# ================= small helpers =================
def load_reflectance_set(path):
    """Load one broad-set reflectance JSON and resample every spectrum onto the
    colorimetry grid CGRID with linear interpolation.  Spectra whose native
    support is narrower than CGRID (e.g. the Agfa IT8.7/2 target, 400-700 @ 10 nm)
    are extended flat by holding the end reflectance values -- np.interp's default
    constant edge extrapolation.  Returns a list of (name, R_on_CGRID)."""
    d = json.load(open(path))
    out = []
    for name, spec in d.items():
        n = len(spec["values"])
        wl = np.linspace(float(spec["wl_start"]), float(spec["wl_end"]), n)
        R = np.interp(CGRID, wl, np.asarray(spec["values"], float))  # flat-hold ends
        out.append((name, R))
    return out


class C41SceneEngine:
    def __init__(self, stock="portra400"):
        self.name = stock
        p = STOCKS[stock]
        self.p = p

        # ---------- dyes (peak = 1 per dye) ----------
        dj = json.load(open(p["dye_density"]))["shared_full_curves"]
        wl_d = np.array(dj["wavelength_nm"], float)
        self.DYE = np.stack([resample(wl_d, dj[l], DGRID) for l in p["layers"]])  # (3, N)

        # ---------- Status M responsivities (truncate 700, renormalize) ----------
        smj = json.load(open(p["statusM"]))
        smw = np.array(smj["wavelength_nm"], float)
        PRT = np.stack([resample(smw, smj["responsivity_linear_peak1"][c], DGRID)
                        for c in ("red", "green", "blue")])
        red_full = np.array(smj["responsivity_linear_peak1"]["red"], float)
        self.red_tail_pct = 100.0 * (1.0 - red_full[smw <= 700].sum() / red_full.sum())
        self.PRT_n = PRT / PRT.sum(1, keepdims=True)

        # ---------- Status M of unit-peak dyes: S[ch][layer] ----------
        self.S = self.statusm_fwd(np.eye(3)).T   # column l = statusM of unit dye l

        # ---------- characteristic curves (Status M density incl. D-min vs logH) --
        cd = json.load(open(p["char_curves"]))
        self.logH = np.array(cd["char_curves"]["log_exposure"], float)
        self.char = {c: np.array(cd["char_curves"]["statusM_density"][c], float)
                     for c in ("R", "G", "B")}

        # ---------- datasheet D-min Status M triplet (spectral D-min vs Status M) --
        sp = cd["spectral"]; swl = np.array(sp["wavelength_nm"], float)
        dmn = resample(swl, sp["dmin"], DGRID)
        mid = resample(swl, sp["midscale_neutral"], DGRID)
        self.dmin_statusM = self.dens_spec(dmn)          # add back before char inversion
        self.mid_statusM = self.dens_spec(mid)           # for logH_mid

        # ---------- logH_mid (per channel + average) ----------
        self.logH_mid_per = np.array([self.inv_char(c, self.mid_statusM[i])
                                      for i, c in enumerate("RGB")])
        self.logH_mid = float(self.logH_mid_per.mean())

        # ---------- sensitivities (linear, 0 outside support) ----------
        sj = json.load(open(p["sensitivity"]))
        swl = np.array(sj["wavelength_nm"], float)
        self.SENS = {}
        for l in p["layers"]:
            ls = np.array([np.nan if v is None else v for v in sj["log_sensitivity"][l]], float)
            lin = np.where(np.isfinite(ls), 10.0 ** ls, 0.0)
            self.SENS[l] = resample(swl, lin, CGRID)

        # ---------- colorimetry basis (CMFs, D55, D65) ----------
        cm = json.load(open(p["cmfs"]))
        cw = np.array(cm["wavelength_nm"], float)
        self.CMF = np.stack([resample(cw, cm["x_bar"], CGRID),
                             resample(cw, cm["y_bar"], CGRID),
                             resample(cw, cm["z_bar"], CGRID)])
        shp = colour.SpectralShape(CGRID[0], CGRID[-1], 1)
        self.D55 = colour.SDS_ILLUMINANTS["D55"].copy().align(shp).values
        self.D65 = colour.SDS_ILLUMINANTS["D65"].copy().align(shp).values

        # normalization so a flat 18% gray -> Y = 0.18 under D55
        self.Yw_D55 = float(self.CMF[1] @ self.D55)      # white (R=1) luminance integral
        # reference whites (Y=1) for chromatic adaptation
        Xw55 = (self.CMF @ self.D55) / self.Yw_D55
        Yw_D65 = float(self.CMF[1] @ self.D65)
        Xw65 = (self.CMF @ self.D65) / Yw_D65
        self.M_cat = colour.adaptation.matrix_chromatic_adaptation_VonKries(
            Xw55, Xw65, transform="Bradford")
        self.white_ref = self.M_cat @ Xw55               # D65 white (Y=1), Lab reference

        # ---------- XYZ(D65) -> DWG and DWG -> Rec.2020 ----------
        dwg = colour.RGB_COLOURSPACES["DaVinci Wide Gamut"]
        self.XYZ_to_DWG = np.array(dwg.matrix_XYZ_to_RGB)
        self.dwg_src = "colour-science %s 'DaVinci Wide Gamut' colourspace" % colour.__version__
        r2020 = colour.RGB_COLOURSPACES["ITU-R BT.2020"]
        self.DWG_to_2020 = np.array(r2020.matrix_XYZ_to_RGB) @ np.array(dwg.matrix_RGB_to_XYZ)

        # ---------- interimage / DIR pre-compensation setup ----------
        self._setup_interimage()

        # ---------- fit the 3x3 scene matrix M (checker + broad, then select) ----
        self._fit_matrix()

    # ---------- integral densitometry ----------
    def dens_spec(self, spectrum):
        """Status M density of a spectral density curve."""
        return -np.log10(np.clip(self.PRT_n @ 10.0 ** (-spectrum), 1e-12, None))

    def statusm_fwd(self, dye):
        dye = np.atleast_2d(dye)
        T = 10.0 ** (-(dye @ self.DYE))
        return -np.log10(np.clip(T @ self.PRT_n.T, 1e-12, None))

    def statusm_jac(self, dye):
        dye = np.atleast_2d(dye)
        T = 10.0 ** (-(dye @ self.DYE))
        integ = T @ self.PRT_n.T
        num = np.einsum('nl,il,jl->nij', T, self.PRT_n, self.DYE)
        return -np.log10(np.clip(integ, 1e-12, None)), num / integ[:, :, None]

    def invert_statusm(self, D, iters=14):
        """Gauss-Newton: dye amounts (>=0) whose Status M densities match D."""
        D = np.atleast_2d(D)
        Sinv = np.linalg.inv(self.S)
        dye = D @ Sinv.T
        for _ in range(iters):
            Dv, J = self.statusm_jac(dye)
            r = Dv - D
            step = np.linalg.solve(J, r[:, :, None])[:, :, 0]
            dye = np.clip(dye - step, 0.0, 8.0)
        return dye

    # ---------- characteristic curves ----------
    def inv_char(self, ch, dens):
        """Density (incl. D-min) -> logH for channel ch (monotone increasing)."""
        return float(interp_lin(dens, self.char[ch], self.logH))

    def _inv_char_vec(self, ch, dens):
        return interp_lin(dens, self.char[ch], self.logH)

    def fwd_char(self, ch, logH):
        """logH -> Status M channel density (incl. D-min)."""
        return interp_lin(logH, self.logH, self.char[ch])

    # ---------- interimage / DIR pre-compensation ----------
    def _setup_interimage(self):
        """Build the neutral-axis pre-coupler dye curves.  Along the datasheet
        logH grid the neutral developed dye amounts (datasheet couplers already
        baked in) are decomposed per layer; the pre-coupler curves are then
        inv(DIR_MATRIX) @ (developed amounts) so that re-applying DIR_MATRIX on
        the neutral axis reproduces the datasheet amounts exactly.  Identity
        DIR_MATRIX -> stage disabled and every chain below takes the legacy path."""
        self.DIR = np.asarray(DIR_MATRIX, float)
        self.interimage_on = not iim.is_identity(self.DIR)
        # datasheet (developed) neutral dye amounts vs the char-curve logH grid
        amt = np.empty((self.logH.size, 3))
        for l, layer in enumerate(self.p["layers"]):
            ch = self.p["layer_channel"][layer]
            ci = "RGB".index(ch)
            amt[:, l] = (self.char[ch] - self.dmin_statusM[ci]) / self.S[ci, l]
        self.neutral_amt = amt                            # developed (datasheet)
        self.neutral_amt_pre = iim.precompensate(amt, self.DIR) if self.interimage_on else amt

    # ---------- core inverse chain: Status M (excl D-min, normalized) -> L ----------
    def statusm_norm_to_L(self, Dnorm):
        """Input [0,1]^3 normalized Status M density (D-min excluded) -> relative
        layer-exposure triplet L (order = STOCKS layers)."""
        Dnorm = np.atleast_2d(Dnorm)
        D = Dnorm * DMAX                                  # OD, D-min excluded
        dye = self.invert_statusm(D)                      # (n,3) developed amounts
        logH = np.empty_like(dye)
        if self.interimage_on:
            # strip interimage -> pre-coupler amounts, invert the pre-coupler curve
            pre = iim.precompensate(dye, self.DIR)
            for l in range(3):
                logH[:, l] = interp_lin(pre[:, l], self.neutral_amt_pre[:, l], self.logH)
        else:
            for l, layer in enumerate(self.p["layers"]):
                ch = self.p["layer_channel"][layer]
                ci = "RGB".index(ch)
                chan_dens = self.dmin_statusM[ci] + self.S[ci, l] * dye[:, l]
                logH[:, l] = self._inv_char_vec(ch, chan_dens)
        return 10.0 ** (logH - self.logH_mid)

    # ---------- forward film model (exposure -> normalized Status M, D-min excl) --
    def L_to_statusm_norm(self, L):
        """Relative layer exposure L -> normalized Status M density (D-min
        excluded), i.e. the input domain of this engine's cube."""
        L = np.atleast_2d(L)
        logH = np.log10(np.clip(L, 1e-12, None)) + self.logH_mid
        dye = np.empty_like(L)
        if self.interimage_on:
            # per-layer pre-coupler amount from the pre-coupler curve, then DIR mix
            pre = np.empty_like(L)
            for l in range(3):
                pre[:, l] = interp_lin(logH[:, l], self.logH, self.neutral_amt_pre[:, l])
            dye = iim.apply_dir(pre, self.DIR)
        else:
            for l, layer in enumerate(self.p["layers"]):
                ch = self.p["layer_channel"][layer]
                ci = "RGB".index(ch)
                chan_dens = self.fwd_char(ch, logH[:, l])
                dye[:, l] = (chan_dens - self.dmin_statusM[ci]) / self.S[ci, l]
        return self.statusm_fwd(dye) / DMAX

    # ---------- colorimetry ----------
    def L_of_reflectance(self, R):
        """Relative layer exposures produced by reflectance R under D55."""
        ref = GRAY * np.ones_like(CGRID)
        out = []
        for layer in self.p["layers"]:
            s = self.SENS[layer] * self.D55
            out.append((s @ R) / (s @ ref))
        return np.array(out)

    def XYZ_of_reflectance(self, R):
        """Colorimetric XYZ(D65) of reflectance R (gray-18 -> Y=0.18), Bradford
        adapted D55 -> D65."""
        X55 = (self.CMF @ (R * self.D55)) / self.Yw_D55
        return self.M_cat @ X55

    def _LX_of_set(self, spectra):
        """(L, XYZ) arrays for a list of (name, R_on_CGRID) reflectance spectra."""
        Ls = np.array([self.L_of_reflectance(R) for _, R in spectra])
        Xs = np.array([self.XYZ_of_reflectance(R) for _, R in spectra])
        return Ls, Xs

    def _solve_matrix(self, L_arr, X_arr, w_arr):
        """Weighted least-squares 3x3 (X = M @ L) with the exact grey row-
        normalization constraint so a flat 18%% grey (L=(1,1,1)) maps to the
        colorimetric grey target exactly."""
        w = np.sqrt(w_arr)[:, None]
        A = L_arr * w; B = X_arr * w
        M, *_ = np.linalg.lstsq(A, B, rcond=None)         # L @ M = X
        M = M.T                                            # X = M @ L
        g_target = self.XYZ_of_reflectance(GRAY * np.ones_like(CGRID))
        g_now = M @ np.ones(3)
        return M * (g_target / g_now)[:, None], g_now

    def _fit_matrix(self):
        # ---- ColorChecker 24 (legacy training set + weights) ----
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

        # ---- legacy checker-only matrix ----
        self.M_checker, gnow_checker = self._solve_matrix(
            self.cc_L, self.cc_X, self.cc_w)

        # ---- broad set: load each reflectance dataset, resample, tag by set ----
        self.broad_sets = {}                              # name -> (L_arr, X_arr)
        blocks_L, blocks_X, blocks_w = [], [], []
        for set_name, set_weight in BROAD_SET_WEIGHTS.items():
            spectra = load_reflectance_set(REFLECTANCE_DIR / (set_name + ".json"))
            La, Xa = self._LX_of_set(spectra)
            self.broad_sets[set_name] = (La, Xa)
            per = set_weight / len(spectra)               # so no set dominates
            blocks_L.append(La); blocks_X.append(Xa)
            blocks_w.append(np.full(len(spectra), per))
        # ColorChecker keeps its relative per-patch weights, rescaled so its
        # total weight == CHECKER_TOTAL_WEIGHT.
        cc_w_scaled = self.cc_w * (CHECKER_TOTAL_WEIGHT / self.cc_w.sum())
        blocks_L.insert(0, self.cc_L); blocks_X.insert(0, self.cc_X)
        blocks_w.insert(0, cc_w_scaled)
        L_all = np.concatenate(blocks_L); X_all = np.concatenate(blocks_X)
        w_all = np.concatenate(blocks_w)
        self.M_broad, gnow_broad = self._solve_matrix(L_all, X_all, w_all)

        # ---- select which matrix drives everything downstream ----
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


# ================= build + metrics =================
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stock", choices=sorted(STOCKS), default="portra400",
                    help="film stock to build (default: portra400)")
    args = ap.parse_args(argv)
    eng = C41SceneEngine(args.stock)
    p = eng.p
    print("=== C-41 scene engine :: %s ===" % eng.name)
    print("D-min: EXCLUDED from cube input (added back internally before char inversion).")
    print("Status M red truncation renormalized; excluded 700-770 tail = %.2f%% of red area."
          % eng.red_tail_pct)
    print("XYZ->DWG matrix source: %s" % eng.dwg_src)
    print("ColorChecker training set: colour '%s' (24 patches), scene illuminant %s."
          % (eng.cc_name, p["scene_illuminant"]))
    print("matrix mode: %s (cube uses M_%s)" % (eng.matrix_mode, eng.matrix_mode))
    print(iim.status_line("c41:", eng.DIR))

    # ---- broad-set matrix fit comparison (checker-only vs broad matrix) ----
    print("=== matrix comparison :: dE2000 mean/max per set, both matrices ===")
    print("  %-20s %6s | %-14s | %-14s" % ("set", "n", "checker M", "broad M"))
    eval_sets = [("ColorChecker24", eng.cc_L, eng.cc_X)]
    eval_sets += [(nm, La, Xa) for nm, (La, Xa) in eng.broad_sets.items()]
    for nm, La, Xa in eval_sets:
        dEc = eng.dE((eng.M_checker @ La.T).T, Xa)
        dEb = eng.dE((eng.M_broad @ La.T).T, Xa)
        print("  %-20s %6d | mean %5.2f max %5.2f | mean %5.2f max %5.2f"
              % (nm, len(La), dEc.mean(), dEc.max(), dEb.mean(), dEb.max()))

    # ---- logH_mid diagnostic ----
    print("logH_mid per channel R,G,B = %s   avg %.4f   spread %.4f"
          % (np.round(eng.logH_mid_per, 4).tolist(), eng.logH_mid,
             float(eng.logH_mid_per.max() - eng.logH_mid_per.min())))
    print("gray-18 XYZ before row-renorm %s -> after %s (target %s)"
          % (np.round(eng.M_gray_before, 4).tolist(),
             np.round(eng.M_gray_after, 4).tolist(),
             np.round(eng.XYZ_of_reflectance(GRAY * np.ones_like(CGRID)), 4).tolist()))

    # ---- matrix-only residuals (M@L vs colorimetric XYZ) ----
    Xfit = (eng.M @ eng.cc_L.T).T
    dE_mat = eng.dE(Xfit, eng.cc_X)
    print("=== ColorChecker matrix-only residual (M@L vs colorimetric XYZ) ===")
    print("dE2000  mean %.3f  max %.3f  (patch %s)"
          % (dE_mat.mean(), dE_mat.max(), eng.cc_names[int(np.argmax(dE_mat))]))

    # ---- FULL chain: reflectance -> L -> film fwd -> inverse chain -> M -> DWG ----
    Dnorm = eng.L_to_statusm_norm(eng.cc_L)               # forward film model
    L_rec = eng.statusm_norm_to_L(Dnorm)                 # engine inverse chain
    Xfull = (eng.M @ L_rec.T).T
    dwg_full = (eng.XYZ_to_DWG @ Xfull.T).T
    dwg_ref = (eng.XYZ_to_DWG @ eng.cc_X.T).T
    dE_full = eng.dE(Xfull, eng.cc_X)
    print("=== ColorChecker FULL chain (reflectance->layers->film->inverse->M->DWG) ===")
    print("dE2000  mean %.3f  max %.3f  (patch %s)"
          % (dE_full.mean(), dE_full.max(), eng.cc_names[int(np.argmax(dE_full))]))
    print("per-patch dE2000 (full): %s"
          % np.round(dE_full, 2).tolist())
    print("DWG round-trip check on gray patches (should track colorimetry): "
          "mean |dDWG| %.4f" % np.mean(np.abs(dwg_full[-6:] - dwg_ref[-6:])))

    # ---- neutral-axis exposure ramp ----
    print("=== neutral-axis: flat-gray exposure ramp (logH_mid +/- 2.0, 0.5 steps) ===")
    print(" dlogH   DWG(R,G,B)            chroma_err   lumaY      Y/Y0    expected 10^d")
    dwg_mid = None
    for d in np.arange(-2.0, 2.001, 0.5):
        L = np.full((1, 3), 10.0 ** d)
        Dn = eng.L_to_statusm_norm(L)
        Lr = eng.statusm_norm_to_L(Dn)
        X = (eng.M @ Lr.T).T
        dwg = (eng.XYZ_to_DWG @ X.T).T[0]
        Y = float(X[0, 1])
        if abs(d) < 1e-9:
            dwg_mid = dwg.copy(); Y0 = Y
        chroma_err = float(np.max(np.abs(dwg - dwg.mean())) / max(abs(dwg.mean()), 1e-9))
        Yratio = Y / Y0 if dwg_mid is not None else float("nan")
        print("  %+.1f   %-22s  %.4f      %.5f  %.4f   %.4f"
              % (d, np.round(dwg, 4).tolist(), chroma_err, Y, Yratio, 10.0 ** d))

    # ================= build 65^3 cube =================
    SZ = 65
    ax = np.linspace(0.0, 1.0, SZ)
    node = np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T
    L_lat = eng.statusm_norm_to_L(node)
    XYZ_lat = (eng.M @ L_lat.T).T
    dwg_lat = (eng.XYZ_to_DWG @ XYZ_lat.T).T             # scene-linear DWG (no clamp)
    lut = dwg_lat.reshape(SZ, SZ, SZ, 3)

    # gamut diagnostics
    neg_dwg = 100.0 * np.mean(np.any(dwg_lat < 0.0, axis=1))
    r2020 = (eng.DWG_to_2020 @ dwg_lat.T).T
    neg_2020 = 100.0 * np.mean(np.any(r2020 < 0.0, axis=1))
    print("=== gamut coverage of 65^3 output lattice ===")
    print("outside DWG unit gamut (any negative)      : %.2f%%" % neg_dwg)
    print("outside Rec.2020 (any negative after DWG->2020): %.2f%%" % neg_2020)

    # ---- emit cube ----
    BUILDS.mkdir(exist_ok=True)
    CUBE = p["out_cube"]
    with open(CUBE, "w") as f:
        f.write("# %s Status M density (D-min excluded) -> scene-linear DaVinci Wide Gamut\n"
                % p["display_name"])
        f.write("# INPUT  = normalized Status M density [0,1]^3 = OD/%.2f, D-MIN EXCLUDED\n" % DMAX)
        f.write("#          (chain AFTER %s, replacing its\n" % p["statusm_cube"])
        f.write("#           postshaper + Density-to-Linear)\n")
        f.write("# OUTPUT = scene-linear DaVinci Wide Gamut (D65); negatives allowed (float)\n")
        f.write("LUT_3D_SIZE %d\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n" % SZ)
        flat = lut.transpose(2, 1, 0, 3).reshape(-1, 3)   # cube: R fastest, no clamp
        for v in flat:
            f.write("%.6f %.6f %.6f\n" % (v[0], v[1], v[2]))

    # ---- serialization round-trip RMSE ----
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
    print("wrote %s" % CUBE.relative_to(ROOT))


if __name__ == "__main__":
    main()
