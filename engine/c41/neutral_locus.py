"""The stock's published neutral, in the cube's own metric (C-41).

A colour negative's neutral exposure series does not read as equal image-dye
Status M densities: on Portra 400 it sits about 0.10/0.06 D below and 0.16 D
above equal channels in R/G/B at mid-grey.  Two consumers must agree on what
that neutral is, the Status M cube (which subtracts the offset so the sheet's
neutral series lies on the diagonal, where Print Adjustment's per-channel
pivot and the print engine's gray-axis lock expect it) and the print engine
(which adds it back before inverting Status M into dye amounts).  One solver,
imported by both, so the two cannot drift; the print engine also checks its
offset against the one written into the Status M cube's header.

The series is the sheet's three Status M characteristic-curve records (base
and fog included) solved TOGETHER at every exposure through the spectral base,
    -log10( Pi_M(l) 10^-(Dmin(l) + a.DYE(l)) ) = sheet record,
into image-dye amounts; the bare image-dye Status M of those amounts, over
DMAX, is the locus.  No integrated D-min is subtracted anywhere: that
subtraction is not the cube's metric (c41_statusm_engine prints the
difference).  The offset is the locus's departure from the diagonal at K_MID,
where a printer sets the balance; the series' departure from that constant
offset is its own curvature, reported and never fitted.

K_MID is the mid-grey input the print engines anchor Y = 0.18 to and the
default Pivot of dctl/output/Print Adjustment.dctl; K_LO..K_HI is the lock's
calibration span; MID_BAND is the +/- Dnorm band about K_MID used for
reporting (the printable-band convention).
"""
import json
from types import SimpleNamespace
import numpy as np

K_LO, K_HI = 0.02, 0.65
K_MID = 0.22
MID_BAND = 0.12


def sheet_neutral_locus(curves_path, dmin, dye, prt_n, dmax,
                        k_mid=K_MID, k_lo=K_LO, k_hi=K_HI, mid_band=MID_BAND):
    """dmin (Nd,), dye (3,Nd), prt_n (3,Nd) on one wavelength grid.

    Returns offset (3,) in Dnorm plus diagnostics (locus, window, band,
    spreads, solve residual, minimum amount).  Raises if the file carries no
    Status M characteristic curves or too few exposures fall in the span."""
    cc = json.load(open(curves_path)).get("char_curves")
    if not cc or "statusM_density" not in cc:
        raise ValueError("%s carries no Status M characteristic curves" % curves_path)
    log_h = np.array(cc["log_exposure"], float)
    target = np.stack([np.array(cc["statusM_density"][k], float) for k in ("R", "G", "B")], 1)
    keep = ~np.isnan(target).any(1)
    log_h, target = log_h[keep], target[keep]
    dmin = np.asarray(dmin, float)
    dye = np.asarray(dye, float)
    prt_n = np.asarray(prt_n, float)

    def full_m(a):
        return -np.log10(np.clip(10.0 ** (-(dmin[None, :] + a @ dye)) @ prt_n.T, 1e-12, None))

    a = np.full(target.shape, 0.5)
    for _ in range(60):
        f = full_m(a)
        jac = np.empty((len(a), 3, 3))
        for j in range(3):
            d = np.zeros(3); d[j] = 1e-5
            jac[:, :, j] = (full_m(a + d) - f) / 1e-5
        a = a - np.linalg.solve(jac, (f - target)[:, :, None])[:, :, 0]
    resid = np.abs(full_m(a) - target).max(1)
    closed = resid <= 1e-3
    image_m = -np.log10(np.clip(10.0 ** (-(a @ dye)) @ prt_n.T, 1e-12, None))   # bare image-dye Status M
    locus = image_m / dmax
    mean_k = locus.mean(1)
    window = closed & (mean_k >= k_lo) & (mean_k <= k_hi)
    if window.sum() < 3:
        raise ValueError("fewer than 3 sheet exposures fall in k in [%.2f, %.2f]" % (k_lo, k_hi))
    departure = locus - mean_k[:, None]
    order = np.argsort(mean_k[window])
    mk, dep = mean_k[window][order], departure[window][order]
    offset = np.array([np.interp(k_mid, mk, dep[:, i]) for i in range(3)])
    band = window & (np.abs(mean_k - k_mid) <= mid_band)
    return SimpleNamespace(
        offset=offset, log_h=log_h, amounts=a, locus=locus, window=window, band=band,
        spread_band=np.ptp(departure[band], axis=0), spread_span=np.ptp(departure[window], axis=0),
        resid=float(resid.max()), amount_min=float(a.min()), n=int(len(log_h)))


def header_offset(cube_path):
    """The neutral offset a Status M cube's header records, or None."""
    for line in open(cube_path):
        if not line.startswith("#"):
            break
        if line.startswith("# neutral offset"):
            nums = line.split("=")[1].split("D")[0].split("/")
            return np.array([float(x) for x in nums])
    return None
