#!/usr/bin/env python3
"""C-41 -> RA-4 print-paper (Kodak Portra Endura) emulation engine.

Paper data is now the AUTHORITATIVE Kodak ENDURA Premier datasheet (E-4070,
March 2013), vector-digitized to data/papers/EnduraPremier_paper.json by
engine/c41/endura_digitize.py (Status A characteristic curves, spectral
sensitivity, spectral dye density).  It supersedes the provisional online-sourced
paper data used during the initial feasibility pass (now retired).

This is the C-41 PRINT-EMULATION route. It was a sibling of the scene-referred
StatusM_to_DWG branch until that branch was RETIRED 2026-08-03; it is now the
sole C-41 delivery route. Its input domain is the same one that branch took, i.e. the
output of <Stock>_StatusM.cube -- normalized ISO Status M
density [0,1]^3 = OD/3.30 per channel, D-MIN EXCLUDED.  Instead of recovering a
scene, it prints the negative onto Portra Endura paper under a tungsten
enlarger and renders the paper reflection colorimetrically to a display space.

Per-node pipeline (input Dnorm in [0,1]^3, normalized Status M density, D-min
excluded):
  1. D_od = Dnorm * DMAX                              (base-relative image-dye Status M density)
  2. dye_neg = invert_statusm(D_od)                   (negative image-dye amounts >= 0)
  3. N(l) = dmin_spec(l) + sum_layer dye_neg * DYE_neg(l) ;  T_neg = 10^-N     (on CGRID)
  4. E_l = sum_l SENS_P_l(l) * L_enl(l) * T_neg(l) ;  logE_l = gray_axis_lock(log10(E_l))
  5. a_l = neutral-scale amount table_l(logE_l)     (per-LAYER dye amount, terminal-slope ext)
       The paper's three characteristic curves are Status A INTEGRAL densities of
       one neutral series, so the red curve carries magenta's and yellow's red
       absorption at their neutral-series amounts. They are converted once, on that
       series, into per-layer amount-versus-logE tables by the Status A inversion;
       each layer is then looked up on its own exposure. Reading each channel's
       curve at its layer's exposure and inverting the mismatched triplet would
       mis-attribute the cross absorption (SA off-diagonals 0.02-0.11) and cost up
       to 15 dE2000 at saturated colours while agreeing exactly on the neutral.
  6. R(l) = 10^-(base(l) + sum a * DYE_P(l))  (paper reflectance); D_P = statusA(a) + Dbase
       base(l) = medium spectral base density (config.medium_base_spd or the print
       medium JSON's "base" block; ZEROS for Endura, whose JSON has none)
  7. XYZ(D65) = (CMF @ (R*D65)) / (CMF_Y @ D65)       (paper white R=1 -> Y=1)
  8. XYZ(D65) -> linear Display-P3 (D65)
  9a. Display-P3 cube : clip[0,1], sRGB encode
  9b. PQ cube         : linear * 203 nits (BT.2408 ref white), ST2084 inverse-EOTF

Gray balance is a full per-channel GRAY-AXIS LOCK (see solve_gray_axis_lock),
replacing the former two-point affine.  All three channels are pulled onto a
COMMON master neutral tone curve at EVERY density, so neutrality holds across the
whole ramp (not just at two anchors) and mid-gray crossover / red cast is
removed.  The master IS the negative's own averaged tonality (mean of the three
balanced per-channel density curves), so no contrast is invented and highlights
are not blown.  The calibration is stored per channel as a monotone 1-D map
logE_raw_l -> logE_req_l and applied globally in the pipeline.

The NEGATIVE stock is selectable with --stock (portra400 default, portra160 also
available); the PAPER is not stock-specific and never changes with it.

Run:  python3 engine/c41/endura_print_engine.py    (from repo root; self-reports metrics)
"""
import argparse
import json
import sys
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import colour

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
BUILDS = ROOT / "builds"

# ----- integration grids / normalization -----
DGRID = np.arange(400, 701, 1.0)          # dye / Status M-A density grid
CGRID = np.arange(380, 731, 1.0)          # colorimetric grid
DMAX = 3.30                                # input normalization (matches <Stock>_StatusM.cube)

# ----- tunable module constants -----
ENLARGER_K = 3200.0                        # enlarger blackbody colour temperature (K)
DW_NITS = 203.0                            # diffuse/paper white nit anchor (BT.2408 HDR ref white)

# ----- gray-axis lock (per-channel full neutral-tone-curve calibration) -----
# Polarity: input is normalized Status M NEGATIVE density; LOW k = thin neg =
# shadow scene = DARK print (HIGH print density); HIGH k = dense neg = highlight
# = LIGHT print (LOW print density).  Instead of anchoring neutrality at two
# densities (the former two-point affine), ALL three channels are pulled onto a
# common master neutral tone curve at EVERY density; the master IS the negative's
# own averaged tonality, so no contrast is invented and highlights are not blown.
K_LO, K_HI = 0.02, 0.65                    # usable neutral input-density span to calibrate over
N_CAL = 256                                # neutral ramp samples
K_MID, D_MID = 0.22, 0.74                  # mid-gray anchor: input k -> paper reflection density (0.74 ~ 0.18 reflectance)

# ----- data files (negative reuses the same files as c41_scene_engine) -----
sys.path.insert(0, str(ROOT))
from engine.common.spectral import interp_lin, pq_encode, resample   # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))   # sibling module import
from portra_stocks import STOCKS as NEG_STOCKS, DEFAULT_STOCK as NEG_STOCK  # noqa: E402


def stocks_for_paper(paper):
    """The negative stocks this repo pairs with a given RA-4 paper."""
    return sorted(k for k, v in NEG_STOCKS.items() if v["print_paper"] == paper)


ENDURA_STOCKS = stocks_for_paper("endura")


def neg_paths(stock):
    """(dye_density, characteristic_curves) data paths for a negative stock."""
    s = NEG_STOCKS[stock]
    return (DATA / "films" / s["dye_density_json"],
            DATA / "films" / s["curves_json"])


# Module-level defaults stay the portra400 paths: callers reassign them
# (compare.py, fuji_print_engine imports them), and EnduraPrintEngine reads them
# for the default stock so that reassignment keeps working.
NEG_DYE, NEG_CURVES = neg_paths(NEG_STOCK)
STATUSM = DATA / "standards" / "StatusM_ISO5-3.json"
STATUSA = DATA / "standards" / "StatusA_ISO5-3.json"
CMFS = DATA / "standards" / "CIE1931_2deg_CMFs.json"
PAPER = DATA / "papers" / "EnduraPremier_paper.json"

LAYERS = ["cyan", "magenta", "yellow"]     # dye/exposure triplet ordering throughout


# ----- sentinel: negative D-min should be read from neg_curves_path -----
_DMIN_FROM_CURVES = object()


@dataclass
class PrintConfig:
    """Configuration for PrintEmulationEngine.

    Defaults reproduce the Kodak Portra Endura RA-4 reflective preset exactly
    (the historical hard-coded behaviour), so an engine built with the default
    config emits byte-identical output.  Override fields to drive a different
    medium -- e.g. a transmissive print film (medium_mode="transmissive").
    """
    medium_mode: str = "reflective"                 # "reflective" | "transmissive"

    # ----- data files -----
    neg_dye_path: Path = NEG_DYE
    neg_curves_path: Optional[Path] = NEG_CURVES
    # neg_dmin: sentinel -> read D-min from neg_curves_path (Endura default);
    #           None -> model negative base as FLAT ZERO spectral offset;
    #           ndarray (on cgrid) -> use directly.
    neg_dmin: object = _DMIN_FROM_CURVES
    statusm_path: Path = STATUSM
    statusa_path: Path = STATUSA
    cmfs_path: Path = CMFS
    print_medium_path: Path = PAPER                 # paper (reflective) or print film (transmissive)
    # medium_base_spd: the print medium's own SPECTRAL base density (D-min of the
    # paper/film support + any non-image density), sampled on cgrid.  It is added
    # to the image-dye density when the medium spectrum is formed:
    #   R/T = 10^-(base(l) + sum_i a_i * Dye_i(l)).
    # Precedence: this field > a top-level "base" block in print_medium_path's
    # JSON ({"wavelength_nm": [...], "density": [...]}) > ZEROS.  Zeros reproduce
    # the historical (base-omitted) behaviour exactly, so the Endura path -- whose
    # paper JSON has no "base" block -- stays bit-identical.
    medium_base_spd: Optional[np.ndarray] = None

    # ----- negative spectral support (see validate B1/B2/B5) -----
    # The negative's dye and D-min data cover a finite band (400-700 nm for Portra) while
    # cgrid is wider (380-730).  resample()'s left=0/right=0 zero-fill means ZERO DENSITY
    # there, i.e. a PERFECTLY TRANSPARENT negative, which turns the uncovered bands into a
    # density-dependent light leak: with the shipped data they carried 41/75/97% of the
    # paper CYAN layer's exposure at Dnorm 0.05/0.22/0.55 and 12/33/85% of YELLOW's,
    # cutting those layers' effective contrast to -0.75 and -1.67 dlogE/dk against
    # magenta's -3.41 (magenta alone has its sensitivity band inside the data).
    #   "truncate"  (default) -> integrate the paper exposure ONLY where the negative has
    #                data; the uncovered bands count as fully blocked.  Fabricates no
    #                density, and matches the truncation already applied to the Status M
    #                red responsivity upstream.  Contrast becomes [-3.46, -3.41, -3.20].
    #   "flat_hold" -> hold the negative's edge density outward.  [-3.59, -3.41, -3.13].
    #   "zero_fill" -> historical pre-2026-07-25 behaviour; kept for A/B comparison only.
    neg_support_mode: str = "truncate"

    # ----- integration grids -----
    dgrid: np.ndarray = field(default_factory=lambda: DGRID.copy())
    cgrid: np.ndarray = field(default_factory=lambda: CGRID.copy())

    # ----- normalization / illuminants -----
    dmax_input: float = DMAX
    enlarger_K: float = ENLARGER_K
    dw_nits: float = DW_NITS

    # ----- gray-axis lock anchors -----
    k_lo: float = K_LO
    k_hi: float = K_HI
    n_cal: int = N_CAL
    k_mid: float = K_MID
    d_mid: float = D_MID
    # mid-gray anchoring for the balancing offset `o`:
    #   "luminance" (default) -> solve for the neutral Status A density whose RENDERED
    #                luminance is y_mid, and anchor K_MID there.  d_mid is then unused.
    #   "density"   -> historical: anchor K_MID directly at Status A density d_mid.
    # Anchoring on Status A density conflates two different quantities: d_mid=0.74 was
    # commented "~0.18 reflectance" but actually renders Y=0.232 (L* 55.3), ~0.37 stop light.
    mid_anchor: str = "luminance"
    y_mid: float = 0.18
    # neutral master basis for the gray-axis lock:
    #   "visual" (default) -> lock the neutral ramp to a true D65-neutral
    #             chromaticity by solving per-point for the dye amounts that render
    #             achromatic at the density-lock's own luminance, falling back to
    #             the equal-density master wherever an exact neutral is unreachable.
    #   "density" -> lock all layers to a COMMON Status A density.  This is only
    #             visually neutral if the dye set is achromatic at equal density,
    #             which the Endura set is NOT: measured a* -0.9/b* +2.4 at D=0.30,
    #             through neutral near D~1.1, to a* +4.5/b* -3.7 at D=2.30 -- a
    #             CROSSED neutral axis (yellow highlights, blue-magenta shadows,
    #             Cab* up to 3.4 across the printable range).  Kept for A/B only.
    neutral_basis: str = "visual"
    # Chromatic adaptation from the medium's VIEWING white to the D65 display
    # white, applied to XYZ before the XYZ->Display-P3 matrix.  Required whenever
    # view_illuminant_spd is not D65 (e.g. a xenon projector), otherwise the
    # illuminant's cast is baked into every output colour.  False (default)
    # reproduces the historical reflective path exactly.
    adapt_view_white_to_d65: bool = False
    cat_method: str = "CAT02"

    # ----- darkroom controls (both default to no-ops: byte-identical output) -----
    # flare: VEILING FLARE at the paper, as a fraction of the open-gate exposure
    #   (E_l -> E_l + flare * sum_l(SENS_P_l * L_enl)).  Models enlarger lens flare, a
    #   deliberate pre-flash, and print-surface/room glare -- everything that puts light on
    #   the paper independent of the negative.  It lifts the toe, so it LOWERS contrast:
    #   measured system gamma (scene->print) 1.83 at 0, 1.71 at 0.005, 1.61 at 0.010,
    #   1.43 at 0.020, with the neutral axis staying at Cab* <= 0.001 throughout.
    #   Applied INSIDE paper_logE_raw, i.e. BEFORE the gray-axis lock, because flare is a
    #   property of the optical path that is present while the print is being balanced --
    #   so the lock accounts for it rather than fighting it.
    #   NB this is the honest version of what the 400/700 nm zero-fill bug was doing by
    #   accident: that leak was channel-SELECTIVE flare (97% of cyan's exposure, 0% of
    #   magenta's), which is why it bought plausible contrast at the cost of a crossed
    #   neutral axis.  A uniform term buys the contrast without the colour damage.
    flare: float = 0.0
    # printer_lights: per-layer paper-exposure trim in logE, [cyan, magenta, yellow] --
    #   dichroic/subtractive filtration in the enlarger head.  Roughly 0.025 logE per
    #   printer-light point on a conventional head.  This is COLOUR BALANCE, not contrast:
    #   a per-channel offset cannot change dD/dlogE at a given point on the H&D, it only
    #   changes which point you sit on.
    #   Applied AFTER the gray-axis lock (in dnorm_to_reflectance), which is the whole
    #   point: the lock defines the neutral reference, and printer lights are a deliberate
    #   departure from it.  Putting them before the lock would let the lock re-neutralize
    #   them straight back out, making the control a no-op on neutrals.
    printer_lights: tuple = (0.0, 0.0, 0.0)

    # ----- viewing/projection illuminant -----
    # None (reflective/Endura default) -> use the engine's D65 in the medium->XYZ
    # step, identical to the historical reflective path.  Provide an SPD sampled
    # on cgrid to replace it (e.g. a projector white for transmissive print film).
    view_illuminant_spd: Optional[np.ndarray] = None

# ================= small helpers =================
def peak_wl(wl, v):
    return float(np.asarray(wl)[int(np.argmax(v))])


class PrintEmulationEngine:
    """Configuration-driven C-41/ECN-2 negative -> print medium -> display engine.

    Supports both a REFLECTIVE medium (RA-4 paper; reflectance R = 10^-D) and a
    TRANSMISSIVE medium (print film; transmittance T = 10^-D).  The spectral
    math is identical for the two; they differ only in which illuminant SPD
    lights the medium in the colorimetry step (config.view_illuminant_spd) and,
    conceptually, in interpretation.  All Endura numerics are the defaults, so
    the default config reproduces the historical reflective output byte-for-byte.
    """
    def __init__(self, config=None):
        self.cfg = config if config is not None else PrintConfig()
        cfg = self.cfg
        self.DGRID = np.asarray(cfg.dgrid, float)
        self.CGRID = np.asarray(cfg.cgrid, float)
        DGRID, CGRID = self.DGRID, self.CGRID

        # ---------- NEGATIVE: image dyes (peak = 1 per dye) on DGRID and CGRID ----------
        dj = json.load(open(cfg.neg_dye_path))["shared_full_curves"]
        wl_d = np.array(dj["wavelength_nm"], float)
        self.DYE_neg = np.stack([resample(wl_d, dj[l], DGRID) for l in LAYERS])    # (3, Nd)
        self.DYE_neg_C = np.stack([resample(wl_d, dj[l], CGRID) for l in LAYERS])  # (3, Nc)

        # ---------- NEGATIVE: Status M responsivities (truncate 700, renormalize) --------
        smj = json.load(open(cfg.statusm_path))
        smw = np.array(smj["wavelength_nm"], float)
        PRT = np.stack([resample(smw, smj["responsivity_linear_peak1"][c], DGRID)
                        for c in ("red", "green", "blue")])
        self.PRT_n = PRT / PRT.sum(1, keepdims=True)
        self.S = self.statusm_fwd(np.eye(3)).T            # column l = Status M of unit neg dye l

        # ---------- NEGATIVE: spectral D-min (orange mask) ------------------------------
        # neg_dmin sentinel -> read from neg_curves_path; None -> FLAT ZERO base;
        # ndarray -> use directly (resampled onto CGRID).
        if cfg.neg_dmin is _DMIN_FROM_CURVES and cfg.neg_curves_path is not None:
            cd = json.load(open(cfg.neg_curves_path))
            sp = cd["spectral"]
            swl = np.array(sp["wavelength_nm"], float)
            self.dmin_spec_C = resample(swl, sp["dmin"], CGRID)         # neg base spectral density
        elif cfg.neg_dmin is None or cfg.neg_dmin is _DMIN_FROM_CURVES:
            # v1: Vision3 orange-mask not modelled; neutral axis handled by
            # gray-axis lock (documented approximation).
            self.dmin_spec_C = np.zeros(CGRID.size)
        else:
            self.dmin_spec_C = np.asarray(cfg.neg_dmin, float)

        # ---------- NEGATIVE: spectral support + edge treatment -------------------------
        # Where does the negative's data actually exist?  Outside that band its density is
        # unknown, and zero-filling it (density 0 == perfectly transparent) leaks light
        # into the paper exposure -- see PrintConfig.neg_support_mode.
        lo, hi = float(wl_d.min()), float(wl_d.max())
        have_curves = (cfg.neg_dmin is _DMIN_FROM_CURVES and cfg.neg_curves_path is not None)
        if have_curves:
            lo, hi = max(lo, float(swl.min())), min(hi, float(swl.max()))
        self.neg_support = (lo, hi)
        if cfg.neg_support_mode == "flat_hold":
            # np.interp (no left/right) holds the terminal value outward.
            self.DYE_neg_C = np.stack([np.interp(CGRID, wl_d, dj[l]) for l in LAYERS])
            if have_curves:
                self.dmin_spec_C = np.interp(CGRID, swl, sp["dmin"])
        # Exposure-integration mask: "truncate" drops the uncovered bands entirely.
        if cfg.neg_support_mode == "truncate":
            self.exp_support = (CGRID >= lo) & (CGRID <= hi)
        else:
            self.exp_support = np.ones(CGRID.size, bool)

        # ---------- PRINT MEDIUM: sensitivity / dye / H&D per layer ---------------------
        pj = json.load(open(cfg.print_medium_path))
        self.paper_prov = pj["provenance"]
        self.SENS_P = np.zeros((3, CGRID.size))           # linear paper sensitivity on CGRID
        self.DYE_P = np.zeros((3, DGRID.size))            # paper dyes (peak 1) on DGRID
        self.DYE_P_C = np.zeros((3, CGRID.size))          # paper dyes on CGRID (reflectance)
        self.hd_logE = []
        self.hd_dens = []
        self.Dbase = np.zeros(3)
        self.peak_sens = np.zeros(3)
        self.peak_dye = np.zeros(3)
        for i, l in enumerate(LAYERS):
            L = pj["layers"][l]
            sw = np.array(L["sensitivity"]["wavelength_nm"], float)
            sv = np.array(L["sensitivity"]["log_sensitivity"], float)
            self.SENS_P[i] = resample(sw, 10.0 ** sv, CGRID)
            self.peak_sens[i] = peak_wl(sw, sv)
            dw = np.array(L["dye"]["wavelength_nm"], float)
            dv = np.array(L["dye"]["density"], float)
            self.DYE_P[i] = resample(dw, dv, DGRID)
            self.DYE_P_C[i] = resample(dw, dv, CGRID)
            self.peak_dye[i] = peak_wl(dw, dv)
            le = np.array(L["hd"]["logE"], float)
            de = np.array(L["hd"]["statusA_density"], float)
            order = np.argsort(le)
            self.hd_logE.append(le[order])
            self.hd_dens.append(de[order])
            self.Dbase[i] = float(de.min())

        # ---------- PRINT MEDIUM: monotone-safe H&D inverse ------------------------------
        # The digitized curves are NOT strictly monotonic: they roll over slightly at the
        # dense end (Endura cyan peaks 2.785 @logE -0.38 then falls to 2.765 at the data
        # edge) and drift ~0.002 D across the far toe -- 22-26 non-increasing steps out of
        # 143 per layer.  The FORWARD direction indexes logE and is fine, but inverting with
        # np.interp using DENSITY as the abscissa is silently wrong wherever density is
        # non-monotonic, so build a strictly-increasing view used for inversion only.
        self.hd_dens_inv = []
        self.hd_logE_inv = []
        for i in range(3):
            le, de = self.hd_logE[i], self.hd_dens[i]
            n = int(np.argmax(de)) + 1                 # drop the shoulder rollover
            d = np.maximum.accumulate(de[:n])          # remove toe / trace dips
            keep = np.concatenate(([True], np.diff(d) > 1e-9))
            self.hd_dens_inv.append(d[keep])
            self.hd_logE_inv.append(le[:n][keep])

        # ---------- PRINT MEDIUM: spectral base density (support D-min) ------------------
        # Physically the medium's spectral density is base(l) + sum_i a_i*Dye_i(l).
        # self.Dbase (above) is the per-layer SCALAR Status A floor used to strip the
        # base out of the H&D density before the DYE-ONLY Status A inversion; this is
        # the SPECTRAL counterpart that is added back when the spectrum is formed.
        # Absent -> exactly zeros (historical behaviour, bit-identical for Endura).
        if cfg.medium_base_spd is not None:
            self.base_spec_C = np.asarray(cfg.medium_base_spd, float)
        elif "base" in pj:
            bwl = np.array(pj["base"]["wavelength_nm"], float)
            bdv = np.array(pj["base"]["density"], float)
            self.base_spec_C = resample(bwl, bdv, CGRID)
        else:
            self.base_spec_C = np.zeros(CGRID.size)

        # ---------- PAPER: Status A responsivities (normalized on DGRID) ----------------
        saj = json.load(open(cfg.statusa_path))
        saw = np.array(saj["wavelength_nm"], float)
        RA = np.stack([resample(saw, saj["responsivity_linear_peak1"][c], DGRID)
                       for c in ("red", "green", "blue")])
        self.RA_n = RA / RA.sum(1, keepdims=True)
        self.SA = self.statusA_fwd(np.eye(3)).T           # column l = Status A of unit paper dye l

        # ---------- PRINT MEDIUM: per-LAYER dye amount along the neutral scale ----------
        # The three H&D curves are consistent with one another only on the neutral
        # series they were measured on, so that is where they are converted to
        # amounts: at every logE the Status A triplet is inverted to the three dye
        # amounts that reproduce it. Off-neutral rendering looks each layer up on
        # its own table (see step 5 in the module docstring).
        self.nt_logE = np.arange(max(l[0] for l in self.hd_logE),
                                 min(l[-1] for l in self.hd_logE) + 1e-9, 0.005)
        Dn = np.stack([interp_lin(self.nt_logE, self.hd_logE[i], self.hd_dens[i])
                       for i in range(3)], axis=1)
        self.nt_amt = self.invert_statusA(np.clip(Dn - self.Dbase, 0.0, None))     # (N,3)
        self.nt_solve_max_resid = float(np.max(np.abs(self.statusA_fwd(self.nt_amt)
                                                      + self.Dbase - Dn)))
        # Strictly increasing per-layer views for the amount -> logE inverse: the
        # shoulder rollover and toe dips are removed exactly as for hd_dens_inv.
        self.nt_tab = []
        for i in range(3):
            am = self.nt_amt[:, i]
            n = int(np.argmax(am)) + 1
            d = np.maximum.accumulate(am[:n])
            keep = np.concatenate(([True], np.diff(d) > 1e-9))
            self.nt_tab.append((self.nt_logE[:n][keep], d[keep]))

        # ---------- colorimetry (CMFs, D65) --------------------------------------------
        cm = json.load(open(cfg.cmfs_path))
        cw = np.array(cm["wavelength_nm"], float)
        self.CMF = np.stack([resample(cw, cm["x_bar"], CGRID),
                             resample(cw, cm["y_bar"], CGRID),
                             resample(cw, cm["z_bar"], CGRID)])
        shp = colour.SpectralShape(CGRID[0], CGRID[-1], 1)
        self.D65 = colour.SDS_ILLUMINANTS["D65"].copy().align(shp).values
        # Medium-viewing illuminant for the medium->XYZ step: default None keeps
        # the historical reflective path (self.D65, identical numerics); a config
        # SPD (on cgrid) replaces it for transmissive/projected viewing.
        if cfg.view_illuminant_spd is None:
            self.view_illum = self.D65
        else:
            self.view_illum = np.asarray(cfg.view_illuminant_spd, float)
        self.Yw = float(self.CMF[1] @ self.view_illum)    # unit-medium white luminance -> Y=1

        # ---------- enlarger illuminant (tungsten blackbody, unit sum) ------------------
        bb = colour.sd_blackbody(cfg.enlarger_K).copy().align(shp).values
        self.L_enl = bb / bb.sum()

        # ---------- paper exposure weights (sensitivity x enlarger, on the neg's support) --
        # Single source of the exposure kernel, masked to where the negative is known.  No
        # renormalization: the absolute scale is absorbed by the gray-axis lock's offsets.
        self.EXP_W = self.SENS_P * self.L_enl * self.exp_support
        full = (self.SENS_P * self.L_enl).sum(1)
        self.exp_weight_kept = self.EXP_W.sum(1) / np.where(full > 0, full, 1.0)

        # ---------- XYZ(D65) -> linear Display P3 --------------------------------------
        p3 = colour.RGB_COLOURSPACES["Display P3"]
        self.XYZ_to_P3 = np.array(p3.matrix_XYZ_to_RGB)

        # ---------- chromatic adaptation matrix: viewing white -> D65 display white ----
        # Built BEFORE the gray-axis lock so the lock's neutral targets are solved
        # in the same (adapted) space the pipeline outputs.
        self._CAT = None
        if cfg.adapt_view_white_to_d65:
            XYZ_view = (np.ones(CGRID.size) * self.view_illum) @ self.CMF.T / self.Yw
            XYZ_d65 = (np.ones(CGRID.size) * self.D65) @ self.CMF.T / float(self.CMF[1] @ self.D65)
            if not np.allclose(XYZ_view, XYZ_d65, atol=1e-6):
                self._CAT = colour.adaptation.matrix_chromatic_adaptation_VonKries(
                    XYZ_view, XYZ_d65, transform=cfg.cat_method)

        # ---------- gray-axis lock auto-calibration (per-channel full neutral curve) -----
        self.solve_gray_axis_lock()

    # ---------- Status M integral densitometry (negative) ----------
    def statusm_fwd(self, dye):
        dye = np.atleast_2d(dye)
        T = 10.0 ** (-(dye @ self.DYE_neg))
        return -np.log10(np.clip(T @ self.PRT_n.T, 1e-12, None))

    def statusm_jac(self, dye):
        dye = np.atleast_2d(dye)
        T = 10.0 ** (-(dye @ self.DYE_neg))
        integ = T @ self.PRT_n.T
        num = np.einsum('nl,il,jl->nij', T, self.PRT_n, self.DYE_neg)
        return -np.log10(np.clip(integ, 1e-12, None)), num / integ[:, :, None]

    def invert_statusm(self, D, iters=14):
        """Gauss-Newton: negative image-dye amounts (>=0) matching Status M densities D."""
        D = np.atleast_2d(D)
        Sinv = np.linalg.inv(self.S)
        dye = D @ Sinv.T
        for _ in range(iters):
            Dv, J = self.statusm_jac(dye)
            r = Dv - D
            step = np.linalg.solve(J, r[:, :, None])[:, :, 0]
            dye = np.clip(dye - step, 0.0, 8.0)
        return dye

    # ---------- Status A integral densitometry (paper) ----------
    def statusA_fwd(self, dye):
        dye = np.atleast_2d(dye)
        T = 10.0 ** (-(dye @ self.DYE_P))
        return -np.log10(np.clip(T @ self.RA_n.T, 1e-12, None))

    def statusA_jac(self, dye):
        dye = np.atleast_2d(dye)
        T = 10.0 ** (-(dye @ self.DYE_P))
        integ = T @ self.RA_n.T
        num = np.einsum('nl,il,jl->nij', T, self.RA_n, self.DYE_P)
        return -np.log10(np.clip(integ, 1e-12, None)), num / integ[:, :, None]

    def invert_statusA(self, D, iters=40):
        """Gauss-Newton: paper dye amounts (>=0) matching Status A densities D."""
        D = np.atleast_2d(D)
        Sinv = np.linalg.inv(self.SA)
        dye = D @ Sinv.T
        for _ in range(iters):
            Dv, J = self.statusA_jac(dye)
            r = Dv - D
            step = np.linalg.solve(J, r[:, :, None])[:, :, 0]
            dye = np.clip(dye - step, 0.0, 8.0)
        return dye

    # ---------- per-layer amount <-> logE on the neutral-scale tables ----------
    def layer_amount(self, logE):
        """(n,3) per-layer log10 E -> (n,3) paper dye amounts (>= 0), each layer on
        its own neutral-scale table with terminal-slope extension beyond it."""
        logE = np.atleast_2d(logE)
        a = np.stack([interp_lin(logE[:, i], self.nt_logE, self.nt_amt[:, i])
                      for i in range(3)], axis=1)
        return np.clip(a, 0.0, None)

    def layer_logE(self, amt):
        """Inverse of layer_amount on the strictly increasing table views. The
        amount is clamped to the table's span first: an amount beyond the
        neutral scale's max black asks for more dye than the layer forms, and
        the shoulder's inverse slope would run that off to meaningless
        exposures, so the lock treats it as the paper does, by clipping."""
        amt = np.atleast_2d(amt)
        return np.stack([interp_lin(np.clip(amt[:, i], self.nt_tab[i][1][0], self.nt_tab[i][1][-1]),
                                    self.nt_tab[i][1], self.nt_tab[i][0])
                         for i in range(3)], axis=1)

    def lock_nonaffinity(self, k_lo, k_hi, n=200):
        """How far the gray-axis lock departs from a per-channel OFFSET over the
        neutral input span [k_lo, k_hi]: per layer (mean, min, max) of
        LEreq - LEraw in log10 E. An enlarger's filtration is an offset, so the
        range (max - min) is the tone remapping the lock applies that no
        filter pack could, i.e. the print model's shape error absorbed on the
        neutral axis."""
        kk = np.linspace(k_lo, k_hi, n)
        LEraw = self.paper_logE_raw(np.repeat(kk[:, None], 3, axis=1))
        out = []
        for i in range(3):
            corr = interp_lin(LEraw[:, i], self.LEraw_s[i], self.LEreq_s[i]) - LEraw[:, i]
            out.append((float(corr.mean()), float(corr.min()), float(corr.max())))
        return out

    # ---------- raw (pre-calibration) paper exposure ----------
    def paper_logE_raw(self, Dnorm):
        """Normalized Status M density (D-min excluded) -> raw log10(E) per paper
        layer, BEFORE gray-balance.  This is the single source of the exposure
        computation used by BOTH the per-node pipeline and solve_gray_axis_lock."""
        Dnorm = np.atleast_2d(Dnorm)
        D_od = Dnorm * self.cfg.dmax_input
        dye_neg = self.invert_statusm(D_od)                              # (n,3)
        N = self.dmin_spec_C + dye_neg @ self.DYE_neg_C                  # (n, Nc)
        T_neg = 10.0 ** (-N)
        E = T_neg @ self.EXP_W.T                                        # (n,3)
        if self.cfg.flare:
            # veiling flare: light reaching the paper independent of the negative, as a
            # fraction of the open-gate (T=1) exposure.  Pre-lock by design -- see
            # PrintConfig.flare.  The open-gate exposure is the UNMASKED
            # sum_l(SENS_P_l * L_enl), not EXP_W: EXP_W carries exp_support, and
            # weighting flare by it makes a nominally uniform veil
            # channel-selective (a cyan deficit of 21%) -- reintroducing exactly
            # the cast this term is meant to model neutrally.
            open_gate = (self.SENS_P * self.L_enl).sum(1)
            E = E + self.cfg.flare * open_gate[None, :]
        return np.log10(np.clip(E, 1e-30, None))                        # (n,3)

    # ---------- gray-axis lock (per-channel full neutral tone curve) ----------
    def solve_gray_axis_lock(self):
        """Force ALL three paper layers onto a COMMON master neutral tone curve at
        every density (a true gray-axis lock), replacing the former two-point
        affine that only locked neutrality at two anchors.

        The master is the negative's own AVERAGED tonality (mean of the three
        balanced per-channel density curves), so no contrast is invented and
        highlights are not blown.  Result stored per channel as a monotone 1-D
        calibration (LEraw_l -> LEreq_l) applied globally in the pipeline.
        """
        cfg = self.cfg
        KK = np.linspace(cfg.k_lo, cfg.k_hi, cfg.n_cal)                 # (N,)
        neutral = np.repeat(KK[:, None], 3, axis=1)                     # (N,3) k*(1,1,1)
        LEraw = self.paper_logE_raw(neutral)                           # (N,3) raw log10 E per layer

        # (3) balancing offset: neutral at K_MID -> the mid-gray anchor on every layer,
        # i.e. the per-layer exposures whose amounts give the anchor's equal Status A
        # density triplet
        LEmid = self.paper_logE_raw(np.full((1, 3), cfg.k_mid))[0]     # (3,)
        self.d_anchor = self.mid_anchor_density()
        a_anchor = self.invert_statusA(np.full((1, 3), self.d_anchor) - self.Dbase)
        o = self.layer_logE(a_anchor)[0] - LEmid                       # (3,)
        self.o = o

        # (4) balanced per-layer amounts and the Status A density they produce
        Db = self.statusA_fwd(self.layer_amount(LEraw + o)) + self.Dbase   # (N,3)

        # (5) master neutral tone curve = mean over channels (data-preserving), clamped to
        # the density band ALL THREE layers can actually realise.  The three layers have
        # different D-min and D-max (Endura: D-min 0.093/0.093/0.067, D-max 2.785/2.549/
        # 2.466), so the unclamped mean runs past the weakest layer at both ends -- at k=0.02
        # it asks for 2.566, above yellow's 2.466, and inverting that extrapolates off the
        # shoulder to logE +9.6.  A neutral can only be as dark as the shallowest layer's
        # D-max and as light as the densest layer's D-min; outside that the print correctly
        # clips to max black / paper white with all three layers still equal (so still
        # neutral), instead of breaking into colour.
        self.d_lo = max(float(d[0]) for d in self.hd_dens_inv)
        self.d_hi = min(float(d[-1]) for d in self.hd_dens_inv)
        Dtarget = np.clip(Db.mean(1), self.d_lo, self.d_hi)            # (N,)

        # (6) per-layer logE required to hit the neutral master at each KK: the amounts
        # of the equal-density triplet, each looked up on its layer's table
        Dtri = np.repeat(Dtarget[:, None], 3, axis=1)
        LEreq = self.layer_logE(self.invert_statusA(np.clip(Dtri - self.Dbase, 0.0, None)))
        self.visual_frac = 0.0
        if cfg.neutral_basis == "visual":
            # True chromaticity-neutral ramp where it is reachable; equal-density elsewhere.
            LEv, ok = self._visual_neutral_LEreq(Dtarget)
            LEreq = np.where(ok[:, None], LEv, LEreq)
            self.visual_frac = float(ok.mean())

        # (7) store monotone sample pairs (LEraw_l, LEreq_l); ensure strictly increasing
        self.LEraw_s = []
        self.LEreq_s = []
        for i in range(3):
            xr = LEraw[:, i]
            yr = LEreq[:, i]
            order = np.argsort(xr)
            xr = xr[order]
            yr = yr[order]
            keep = np.concatenate(([True], np.diff(xr) > 1e-12))       # dedupe non-increasing x
            xr, yr = xr[keep], yr[keep]
            # Enforce a MONOTONE map.  The visual-neutral basis and the master clamp can each
            # step LEreq backwards (worst observed -0.411 at the fallback boundary), and a
            # non-monotone calibration folds the LUT.  xr is ascending here, so yr must be
            # non-decreasing; accumulating the running maximum flattens any backward jump into
            # a plateau, which is the correct reading of it -- that region is clipping.
            self.LEraw_s.append(xr)
            self.LEreq_s.append(np.maximum.accumulate(yr))

    # ---------- mid-gray anchor ----------
    def mid_anchor_density(self):
        """Equal-layer Status A density that the K_MID neutral is anchored to.

        cfg.mid_anchor == "luminance": bisect for the density whose RENDERED luminance is
        cfg.y_mid, so mid-gray is placed by what it looks like rather than by a density
        number.  Y is monotone decreasing in density, so bisection is unconditional.
        "density" reproduces the historical behaviour (anchor straight at cfg.d_mid).
        """
        cfg = self.cfg
        if cfg.mid_anchor != "luminance":
            return float(cfg.d_mid)

        def Y_of(d):
            a = self.invert_statusA(np.full((1, 3), d) - self.Dbase)
            R = 10.0 ** (-(self.base_spec_C + a @ self.DYE_P_C))
            return float(self.medium_to_XYZ(R)[0, 1])

        lo = float(self.Dbase.max()) + 1e-3
        hi = float(min(d.max() for d in self.hd_dens_inv))
        for _ in range(48):
            mid = 0.5 * (lo + hi)
            if Y_of(mid) > cfg.y_mid:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    # ---------- visual-neutral gray-axis lock (print-film dyes) ----------
    def _solve_neutral_amounts(self, XYZ_target, iters=40):
        """Gauss-Newton: print dye amounts (>=0) whose medium->XYZ matches XYZ_target.
        Used to force the neutral ramp onto a true (D65-neutral) chromaticity."""
        ln10 = np.log(10.0)
        a = np.full((XYZ_target.shape[0], 3), 0.5)
        for _ in range(iters):
            # medium spectrum INCLUDES the spectral base (additive in density)
            R = 10.0 ** (-(self.base_spec_C + a @ self.DYE_P_C))       # (n, Nc)
            XYZ = (R * self.view_illum) @ self.CMF.T / self.Yw         # (n,3)
            r = XYZ - XYZ_target
            J = np.empty((a.shape[0], 3, 3))
            for j in range(3):
                dR = -ln10 * R * self.DYE_P_C[j][None, :]              # (n, Nc)
                J[:, :, j] = (dR * self.view_illum) @ self.CMF.T / self.Yw
            step = np.linalg.solve(J, r[:, :, None])[:, :, 0]
            a = np.clip(a - step, 0.0, 8.0)
        return a

    def _visual_neutral_LEreq(self, Dtarget):
        """Per-layer logE required so the neutral ramp renders D65-neutral at the
        density-lock's own luminance (preserves tonality, removes the dye cast)."""
        Nc = self.cfg.cgrid.size
        XYZw = self.medium_to_XYZ(np.ones((1, Nc)))[0]                 # Y=1, view-white chroma
        Dtri = np.repeat(np.asarray(Dtarget)[:, None], 3, axis=1)     # density-lock: equal per layer
        a_dl = self.invert_statusA(np.clip(Dtri - self.Dbase, 0.0, None))
        # medium spectrum INCLUDES the spectral base (additive in density)
        Y_t = self.medium_to_XYZ(
            10.0 ** (-(self.base_spec_C + a_dl @ self.DYE_P_C)))[:, 1]  # (N,) target luminance
        XYZ_target = Y_t[:, None] * XYZw[None, :]                      # neutral chroma at that Y
        a_star = self._solve_neutral_amounts(XYZ_target)              # (N,3) neutral dye amounts
        # An exactly-neutral rendering is not reachable everywhere: at the clamped max-black
        # end the three layers' unequal D-max makes it impossible, and the solve then clips a
        # dye amount and diverges (Endura: Cab* 92 at k=0.05 if used unguarded).  Report a
        # validity mask so the caller can fall back to the equal-density master there.
        ok = np.all((a_star > 1e-9) & (a_star < 8.0 - 1e-9), axis=1)
        for i in range(3):
            ok &= ((a_star[:, i] >= self.nt_tab[i][1][0]) &
                   (a_star[:, i] <= self.nt_tab[i][1][-1]))
        return self.layer_logE(a_star), ok

    # ---------- core: normalized Status M density -> reflectance / XYZ ----------
    def dnorm_to_reflectance(self, Dnorm):
        """Input [0,1]^3 normalized Status M density (D-min excluded) -> paper
        reflectance R on CGRID (n, Nc)."""
        Dnorm = np.atleast_2d(Dnorm)
        LEraw = self.paper_logE_raw(Dnorm)                            # (n,3) raw log10 E
        logE = np.stack([interp_lin(LEraw[:, i], self.LEraw_s[i], self.LEreq_s[i])
                         for i in range(3)], axis=1)                   # gray-axis-locked
        # printer lights: enlarger filtration, applied AFTER the lock so it is a deliberate
        # departure from the locked neutral rather than something the lock cancels out.
        pl = np.asarray(self.cfg.printer_lights, float)
        if pl.any():
            logE = logE + pl[None, :]
        a = self.layer_amount(logE)                                     # (n,3) paper dye amounts
        D_P = self.statusA_fwd(a) + self.Dbase                          # (n,3) Status A
        # medium spectrum INCLUDES the spectral base (additive in density)
        R = 10.0 ** (-(self.base_spec_C + a @ self.DYE_P_C))            # (n, Nc)
        return R, D_P, a

    def medium_to_XYZ(self, M):
        """Medium spectral quantity (reflectance R or transmittance T, both
        10^-D on CGRID) lit by the viewing illuminant -> XYZ, normalized so a
        unit medium (R=1 / T=1) under that illuminant gives Y=1."""
        return (M * self.view_illum) @ self.CMF.T / self.Yw             # (n,3), white -> Y=1

    # Back-compat alias (reflective callers).
    reflectance_to_XYZ = medium_to_XYZ

    def dnorm_to_linP3(self, Dnorm):
        R, D_P, a = self.dnorm_to_reflectance(Dnorm)
        XYZ = self.medium_to_XYZ(R)
        XYZ = self.adapt_to_display(XYZ)
        lin = XYZ @ self.XYZ_to_P3.T
        return lin, XYZ, D_P, a

    # ---------- chromatic adaptation: viewing white -> display (D65) white ----------
    def adapt_to_display(self, XYZ):
        """Adapt XYZ from the medium's VIEWING white to the display white (D65).

        The output space (Display P3) is D65-referred, so XYZ computed under a
        non-D65 viewing illuminant must be adapted or every colour inherits the
        illuminant's cast.  A projected print is viewed with the eye adapted to
        the projector white, so this models the observer, not a white-balance
        fudge.  No-op (identity matrix) when the viewing illuminant already IS
        D65 -- which is the reflective/Endura default, keeping it bit-identical."""
        if self._CAT is None:
            return XYZ
        return XYZ @ self._CAT.T


class EnduraPrintEngine(PrintEmulationEngine):
    """Kodak Portra Endura RA-4 reflective preset (historical default).

    Constructed with a PrintConfig whose fields all equal the module-level
    Endura constants, so output is byte-identical to the pre-refactor engine.
    Reads the module-global PAPER/NEG_* paths at construction time so callers
    that reassign them (e.g. compare.py does E.PAPER = pp) keep working.

    `stock` selects the NEGATIVE only; the paper is unchanged by it.  None or the
    default stock uses the module globals verbatim, preserving the reassignment
    behaviour above and keeping the default build byte-identical.
    """
    def __init__(self, stock=None):
        neg_dye, neg_curves = ((NEG_DYE, NEG_CURVES) if stock in (None, NEG_STOCK)
                               else neg_paths(stock))
        super().__init__(PrintConfig(
            medium_mode="reflective",
            neg_dye_path=neg_dye,
            neg_curves_path=neg_curves,
            statusm_path=STATUSM,
            statusa_path=STATUSA,
            cmfs_path=CMFS,
            print_medium_path=PAPER,
        ))


# ================= serialization round-trip helper =================
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


def trilinear(lut, pts):
    """Trilinear sample of a (S,S,S,3) LUT (axis order = input channel order) at
    pts in [0,1]^3 -- the interpolation a real LUT box performs."""
    S = lut.shape[0]
    x = np.clip(np.asarray(pts, float), 0.0, 1.0) * (S - 1)
    i0 = np.minimum(np.floor(x).astype(int), S - 2)
    f = x - i0
    out = np.zeros((x.shape[0], 3))
    for d0 in (0, 1):
        for d1 in (0, 1):
            for d2 in (0, 1):
                w = ((f[:, 0] if d0 else 1 - f[:, 0]) *
                     (f[:, 1] if d1 else 1 - f[:, 1]) *
                     (f[:, 2] if d2 else 1 - f[:, 2]))
                out += w[:, None] * lut[i0[:, 0] + d0, i0[:, 1] + d1, i0[:, 2] + d2]
    return out


def report_paper_tables(eng, node, a, size):
    """Self-report of the per-layer amount tables over an emitted lattice: the
    neutral-scale solve residual (the one place a Status A inversion happens),
    how much of the lattice runs off the tables' digitised span (terminal-slope
    extension, register 16), and how much clips at zero amount."""
    print("paper tables: neutral-scale Status A solve over logE %.2f..%.2f (%d points), "
          "max |dD| %.1e; amount span per layer [C,M,Y] = %s"
          % (eng.nt_logE[0], eng.nt_logE[-1], eng.nt_logE.size, eng.nt_solve_max_resid,
             [(round(float(t[1][0]), 3), round(float(t[1][-1]), 3)) for t in eng.nt_tab]))
    LEraw = eng.paper_logE_raw(node)
    logE = np.stack([interp_lin(LEraw[:, i], eng.LEraw_s[i], eng.LEreq_s[i]) for i in range(3)], axis=1)
    off = (logE < eng.nt_logE[0]) | (logE > eng.nt_logE[-1])
    zc = (a <= 1e-12)
    print("  over the %d^3 lattice: layer logE outside the tables' span (extension engaged) "
          "[C,M,Y] = %s%%; amount clipped at zero [C,M,Y] = %s%%"
          % (size, np.round(100.0 * off.mean(0), 2).tolist(), np.round(100.0 * zc.mean(0), 2).tolist()))


def report_lock_nonaffinity(eng, k_lo, k_hi):
    """Print the lock's departure from a per-channel offset over [k_lo, k_hi]."""
    rows = eng.lock_nonaffinity(k_lo, k_hi)
    print("gray-axis lock over the printable window k in [%.3f, %.3f]: LEreq - LEraw per layer "
          "(mean / range) = %s logE; an enlarger's filtration is the mean, the range is tone "
          "remapping the lock applies on top"
          % (k_lo, k_hi, "  ".join("%s %+.3f / %.3f" % (l, m, hi - lo)
                                   for l, (m, lo, hi) in zip(LAYERS, rows))))


PROBE_N = 5000          # random points for the interpolation probe
PROBE_SEED = 1          # seeded, so the reported figure is reproducible


def report_cube_fidelity(path, lut_mem, size, exact_fn, unit_scale=255.0):
    """Report a serialized print cube's fidelity as TWO distinct figures.

      * node quantization -- disk against the in-memory lattice, NODE FOR NODE.
        Because both are the same nodes, this can only ever be the six-decimal
        write-rounding floor (~3e-07). It catches a broken writer and nothing
        else; it is NOT an accuracy figure.
      * INTERPOLATION -- the cube READ BACK FROM DISK, trilinearly sampled at
        random points of its [0,1]^3 input domain (normalized Status M
        density), against the engine's own forward at those same points. This
        is the error a real LUT box delivers, and it is the number to quote.

    Also reported in 8-bit code values out of 255, the unit a reader can judge.
    """
    disk = read_cube(path, size)

    # Permanent indexing guard. read_cube ends in .transpose(2, 1, 0, 3), so an
    # axis-swapped interpolator would still produce a plausible-looking number.
    # Sampling at EXACT node coordinates must return those very nodes, to within
    # the write floor; if it does not, the indexing above is wrong.
    ax = np.linspace(0.0, 1.0, size)
    nodes = np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T
    node_err = float(np.max(np.abs(trilinear(disk, nodes) - disk.reshape(-1, 3))))
    assert node_err < 1e-6, (
        "cube axis order mismatch: interpolating %s at its own node coordinates "
        "missed the nodes by %.3e (expected <= the six-decimal write floor)"
        % (path.name, node_err))

    q = disk - lut_mem
    print("serialized %s: node quantization RMSE %.3e  max %.3e  "
          "(six-decimal write floor; not an accuracy figure)"
          % (path.name, float(np.sqrt(np.mean(q ** 2))), float(np.max(np.abs(q)))))

    pts = np.random.default_rng(PROBE_SEED).uniform(0.0, 1.0, (PROBE_N, 3))
    err = trilinear(disk, pts) - np.asarray(exact_fn(pts), float)
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mx = float(np.max(np.abs(err)))
    print("serialized %s: INTERPOLATION RMSE %.3e  max %.3e code value 0-1 "
          "(= %.2f / %.2f code values out of 255; n=%d off-lattice points, seed %d)"
          % (path.name, rmse, mx, rmse * unit_scale, mx * unit_scale,
             PROBE_N, PROBE_SEED))
    return rmse, mx


def write_cube(path, lut, size, header_lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for h in header_lines:
            f.write("# %s\n" % h)
        f.write("LUT_3D_SIZE %d\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n" % size)
        flat = lut.transpose(2, 1, 0, 3).reshape(-1, 3)     # R fastest
        for v in flat:
            f.write("%.6f %.6f %.6f\n" % (v[0], v[1], v[2]))


# ================= build + metrics =================
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # The pairing rule is enforced here, not merely documented: printing a
    # Fujifilm negative on Endura is a combination nobody ever ran, so it is
    # rejected by argparse rather than silently built.
    ap.add_argument("--stock", choices=ENDURA_STOCKS, default=NEG_STOCK,
                    help="NEGATIVE film stock to print (default: %s); the paper "
                         "is not stock-specific, but only the stocks paired "
                         "with Endura are accepted" % NEG_STOCK)
    args = ap.parse_args(argv)
    neg = NEG_STOCKS[args.stock]
    neg_name = neg["display_name"]                  # e.g. "Portra 400"
    neg_prefix = neg["file_prefix"]                 # e.g. "Portra400"

    eng = EnduraPrintEngine(args.stock)
    print("=== C-41 -> RA-4 Portra Endura print-emulation engine ===")
    print("negative stock: %s" % neg_name)
    print("paper data: %s | %s" % (eng.paper_prov["source"], eng.paper_prov["status"]))
    print("input domain: normalized ISO Status M density [0,1]^3 = OD/%.2f, D-MIN EXCLUDED"
          % DMAX)
    for i, l in enumerate(LAYERS):
        print("  %-8s channel: sens peak %.1f nm, dye peak %.1f nm"
              % (l, eng.peak_sens[i], eng.peak_dye[i]))
    print("enlarger K = %.0f" % ENLARGER_K)
    print("negative spectral support: %.0f-%.0f nm, mode=%s ; paper exposure weight kept "
          "[C,M,Y] = %s" % (eng.neg_support[0], eng.neg_support[1],
                            eng.cfg.neg_support_mode,
                            np.round(eng.exp_weight_kept, 3).tolist()))
    print("gray-axis lock (all channels -> common master neutral tone curve at every density):")
    print("  basis=%s (chromaticity-neutral on %.1f%% of the calibration ramp, equal-density "
          "elsewhere)" % (eng.cfg.neutral_basis, 100.0 * eng.visual_frac))
    print("  o [C,M,Y] (balancing offsets) = %s" % np.round(eng.o, 4).tolist())
    print("  mid-gray anchor: %s, K_MID=%.2f -> Status A density %.4f (target Y=%.2f)"
          % (eng.cfg.mid_anchor, K_MID, eng.d_anchor, eng.cfg.y_mid))
    print("  master neutral clamped to the band all 3 layers realise: D in [%.3f, %.3f]"
          % (eng.d_lo, eng.d_hi))
    print("  calibrated span k in [%.2f, %.2f], N=%d" % (K_LO, K_HI, N_CAL))
    D_mid_ach = eng.dnorm_to_reflectance(np.full((1, 3), K_MID))[1][0]
    print("  achieved print density @K_MID [C,M,Y] = %s (anchor %.4f)"
          % (np.round(D_mid_ach, 4).tolist(), eng.d_anchor))

    # ---- neutral-axis ramp ----
    print("=== neutral-axis ramp: Dnorm = k*(1,1,1) ===")
    print("   k      DisplayP3(R,G,B)          chroma_err     Y")
    ks = np.arange(0.05, 0.601, 0.05)
    for k in ks:
        lin, XYZ, D_P, a = eng.dnorm_to_linP3(np.full((1, 3), k))
        rgb = np.clip(lin[0], 0.0, 1.0)
        m = max(abs(rgb.mean()), 1e-9)
        chroma = float(np.max(np.abs(rgb - rgb.mean())) / m)
        print("  %.2f   %-24s  %.4f       %.5f"
              % (k, np.round(rgb, 4).tolist(), chroma, float(XYZ[0, 1])))
    # which k lands mid-gray (linear P3 R~=G~=B~=0.18, i.e. 18% gray)
    kfine = np.linspace(0.02, 0.60, 400)
    linf, XYZf, D_Pf, af = eng.dnorm_to_linP3(np.repeat(kfine[:, None], 3, axis=1))
    lin_mean = np.clip(linf, 0.0, 1.0).mean(1)
    j = int(np.argmin(np.abs(lin_mean - 0.18)))
    k_mid = float(kfine[j])
    print("neutral input k reproducing mid-gray (linear P3 mean ~= 0.18): k=%.3f"
          % k_mid)
    print("  -> linear P3 [R,G,B] = %s ; paper print density [C,M,Y] = %s (mean %.3f)"
          % (np.round(np.clip(linf[j], 0.0, 1.0), 4).tolist(),
             np.round(D_Pf[j], 4).tolist(), float(D_Pf[j].mean())))

    # ================= build 65^3 cubes =================
    SZ = 65
    ax = np.linspace(0.0, 1.0, SZ)
    node = np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T
    lin, XYZ, D_P, a = eng.dnorm_to_linP3(node)

    # ---- paper-side table use over the FULL emitted lattice ----
    report_paper_tables(eng, node, a, SZ)
    # same check on the input side
    D_od = node * DMAX
    dye_in = eng.invert_statusm(D_od)
    mres = np.abs(eng.statusm_fwd(dye_in) - D_od)
    mclip = ((dye_in <= 1e-12) | (dye_in >= 8.0 - 1e-9)).any(1)
    print("Status M inversion residual |D| over the lattice: median %.3e  95th %.3e  max %.3e"
          "  (%.1f%% of nodes need an unrealizable negative-dye amount)"
          % (float(np.median(mres)), float(np.percentile(mres, 95)), float(mres.max()),
             100.0 * mclip.mean()))

    # ---- printable window: where the neutral ramp is between paper white and max black ----
    kf = np.linspace(0.0, 1.0, 501)
    Dn = eng.dnorm_to_reflectance(np.repeat(kf[:, None], 3, axis=1))[1].mean(1)
    inside = (Dn > eng.d_lo + 0.02) & (Dn < eng.d_hi - 0.02)
    if inside.any():
        print("printable neutral window: Dnorm k in [%.3f, %.3f] (outside it the print clips to "
              "paper white / max black, as a real RA-4 print does)"
              % (float(kf[inside][0]), float(kf[inside][-1])))
        report_lock_nonaffinity(eng, float(kf[inside][0]), float(kf[inside][-1]))

    # gamut diagnostics (before clip)
    outside = 100.0 * np.mean(np.any((lin < 0.0) | (lin > 1.0), axis=1))
    print("=== gamut: %.2f%% of the 65^3 lattice outside Display-P3 [0,1] (pre-clip) ===" % outside)

    # ---- 9a: Display P3 cube ----
    p3rgb = colour.cctf_encoding(np.clip(lin, 0.0, 1.0), function="sRGB")
    lut_p3 = p3rgb.reshape(SZ, SZ, SZ, 3)
    CUBE_P3 = BUILDS / "c41" / "print_endura" / ("%s_to_PortraEndura_DisplayP3.cube" % neg_prefix)
    write_cube(CUBE_P3, lut_p3, SZ, [
        "%s (Status M density, D-min excluded) -> Portra Endura print -> Display P3" % neg_name,
        "Paper = Kodak ENDURA Premier datasheet E-4070 (Status A); negative = %s surrogate-dye (register #8)" % neg_name,
        "INPUT  = normalized Status M density [0,1]^3 = OD/%.2f, D-MIN EXCLUDED" % DMAX,
        "         (chain AFTER %s_StatusM.cube; sole C-41 delivery route)" % neg_prefix,
        "OUTPUT = Display P3 (D65), sRGB-encoded, clipped [0,1]",
        "GRAY BALANCE = full per-channel gray-axis lock: all channels pulled onto the",
        "         mean neutral tone curve at every density, replacing the two-point affine",
    ])
    def f_p3(P):
        return colour.cctf_encoding(np.clip(eng.dnorm_to_linP3(P)[0], 0.0, 1.0),
                                    function="sRGB")

    report_cube_fidelity(CUBE_P3, lut_p3, SZ, f_p3)
    print("wrote %s" % CUBE_P3.relative_to(ROOT))

    # ---- 9b: P3-D65 PQ cube ----
    L_cd = np.clip(lin, 0.0, None) * DW_NITS
    pqrgb = pq_encode(L_cd)
    lut_pq = pqrgb.reshape(SZ, SZ, SZ, 3)
    CUBE_PQ = BUILDS / "c41" / "print_endura" / ("%s_to_PortraEndura_P3D65_PQ203.cube" % neg_prefix)
    write_cube(CUBE_PQ, lut_pq, SZ, [
        "%s (Status M density, D-min excluded) -> Portra Endura print -> P3-D65 PQ" % neg_name,
        "Paper = Kodak ENDURA Premier datasheet E-4070 (Status A); negative = %s surrogate-dye (register #8)" % neg_name,
        "INPUT  = normalized Status M density [0,1]^3 = OD/%.2f, D-MIN EXCLUDED" % DMAX,
        "         (chain AFTER %s_StatusM.cube; sole C-41 delivery route)" % neg_prefix,
        "OUTPUT = P3-D65 primaries, ST2084/PQ transfer; paper white = %.0f nits (BT.2408)" % DW_NITS,
        "GRAY BALANCE = full per-channel gray-axis lock: all channels pulled onto the",
        "         mean neutral tone curve at every density, replacing the two-point affine",
    ])
    def f_pq(P):
        return pq_encode(np.clip(eng.dnorm_to_linP3(P)[0], 0.0, None) * DW_NITS)

    report_cube_fidelity(CUBE_PQ, lut_pq, SZ, f_pq)
    print("wrote %s" % CUBE_PQ.relative_to(ROOT))


if __name__ == "__main__":
    main()
