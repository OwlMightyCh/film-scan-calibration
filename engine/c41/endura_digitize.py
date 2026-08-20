#!/usr/bin/env python3
"""Digitize the vector charts of the Kodak Endura Premier paper datasheet.

Three charts are harvested across two pages (612x792 pt):

  * PAGE index 3, upper  "Characteristic Curves":   x = log exposure
        (lux-seconds), y = Status A density. Three curves, top->bottom
        by descending bbox-center-y = R, G, B.
  * PAGE index 3, lower  "Spectral-Sensitivity Curves": x = wavelength (nm),
        y = log sensitivity. Three curves, identified by peak wavelength.
  * PAGE index 4         "Spectral-Dye-Density Curves": x = wavelength (nm),
        y = diffuse spectral density. Three curves, identified by peak.

All chart art is vector: LTLine/LTCurve frame + gridlines, LTCurve data
polylines, LTChar labels. Axes are calibrated device->data by an affine fit
to confirmed anchor points. Data curves are the stroked LTCurves with many
vertices inside each chart's frame window.

This reproduces the exact methodology of engine/c41/portra_digitize.py and
reuses its pure helpers. Output is the authoritative paper data
data/papers/EnduraPremier_paper.json (drop-in for endura_print_engine.py).
"""
import json
import sys
from pathlib import Path
import numpy as np
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTLine, LTCurve, LTChar

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.c41.portra_digitize import (  # noqa: E402
    walk, polyline, label_ticks, affine_fit, to_data, resample_curve, bezier,
    cluster,
)

DATA = ROOT / "data"
PDF = ROOT / "paper_datasheet" / "Kodak Endura Premier.pdf"


# ---------- confirmed axis anchor points (device_px -> data) ----------
# Chart (a) Characteristic Curves, PAGE 3 upper
CHAR_X = [(365.4, -3.0), (425.3, -2.0), (487.0, -1.0), (549.0, 0.0)]
CHAR_Y = [(535.8, 0.0), (596.1, 1.0), (657.0, 2.0)]

# Chart (b) Spectral-Sensitivity Curves, PAGE 3 lower
SENS_X = [(351.1, 250), (371.2, 300), (391.3, 350), (411.4, 400), (431.5, 450),
          (451.6, 500), (471.6, 550), (491.7, 600), (511.8, 650), (531.9, 700),
          (551.6, 750)]
SENS_Y = [(325.3, -2.0), (362.8, -1.0), (400.0, 0.0), (437.0, 1.0), (474.8, 2.0)]

# Chart (c) Spectral-Dye-Density Curves, PAGE 4
DYE_X = [(77.0, 400), (138.4, 500), (199.9, 600), (261.3, 700)]
DYE_Y = [(520.0, 0.0), (557.4, 0.5), (595.2, 1.0), (630.6, 1.5), (667.5, 2.0),
         (704.4, 2.5)]


def stroked_in(stroked, xlo, xhi, ylo, yhi, npts=10, center_y_max=None):
    """Stroked LTCurves with >= npts path segments whose bbox lies inside the
    given device-space window (optionally with bbox-center-y below a cap)."""
    out = []
    for c in stroked:
        x0, y0, x1, y1 = c.bbox
        if len(c.original_path) < npts:
            continue
        if not (x0 >= xlo and x1 <= xhi and y0 >= ylo and y1 <= yhi):
            continue
        if center_y_max is not None and (y0 + y1) / 2 >= center_y_max:
            continue
        out.append(c)
    return out


def peak_wavelength(wl_grid, log_sens):
    """Wavelength of maximum (non-NaN) log-sensitivity."""
    arr = np.array(log_sens, float)
    idx = np.nanargmax(arr)
    return float(wl_grid[idx])


def main():
    pages = list(extract_pages(str(PDF)))

    audit = {}

    # =========================================================
    # CHART (a) Characteristic Curves -- PAGE 3, upper
    # =========================================================
    page3 = pages[3]
    els3 = list(walk(page3))
    stroked3 = [e for e in els3 if isinstance(e, LTCurve) and e.stroke]

    cmx, cbx, cxr = affine_fit(CHAR_X)   # logE  = cmx*x_px + cbx
    cmy, cby, cyr = affine_fit(CHAR_Y)   # statA = cmy*y_px + cby

    char_curves = stroked_in(stroked3, 364, 541, 538, 706)
    # top->bottom by descending bbox-center-y = R, G, B
    char_curves.sort(key=lambda c: -(c.bbox[1] + c.bbox[3]) / 2)
    char_names = ["R", "G", "B"]

    char_data = {}
    ranges = []
    for c in char_curves:
        dc = to_data(polyline(c), cmx, cbx, cmy, cby)
        char_data[c] = dc
        order = np.argsort(dc[:, 0])
        ranges.append((dc[order, 0][0], dc[order, 0][-1]))
    lo = max(r[0] for r in ranges)
    hi = min(r[1] for r in ranges)
    logE = np.round(np.arange(np.ceil(lo / 0.02) * 0.02,
                              np.floor(hi / 0.02) * 0.02 + 1e-9, 0.02), 2)

    char_hd = {}          # name -> (logE list, density list)
    char_endpoints = {}
    for name, c in zip(char_names, char_curves):
        vals, rng = resample_curve(char_data[c], logE, extrapolate=False)
        # common support -> no NaNs; sort ascending by logE (grid already asc)
        order = np.argsort(logE)
        gx = [round(float(v), 4) for v in logE[order]]
        gy = [round(float(vals[i]), 4) for i in order]
        char_hd[name] = (gx, gy)
        char_endpoints[name] = {
            "logE_range": [round(rng[0], 4), round(rng[1], 4)],
            "n_path_points": len(char_data[c]),
            "density_range": [round(float(np.nanmin(vals)), 4),
                              round(float(np.nanmax(vals)), 4)],
        }

    audit["characteristic_curves"] = {
        "page_index": 3,
        "x_axis": {
            "device_to_data": "logE = %.6f*x_px + %.6f" % (cmx, cbx),
            "anchors": CHAR_X, "fit_rms_data": round(cxr, 5)},
        "y_axis": {
            "device_to_data": "statusA = %.6f*y_px + %.6f" % (cmy, cby),
            "anchors": CHAR_Y, "fit_rms_data": round(cyr, 5)},
        "curve_order_note": "top->bottom by descending bbox-center-y = R, G, B",
        "curve_point_counts": {n: char_endpoints[n]["n_path_points"]
                               for n in char_names},
        "endpoints": char_endpoints,
        "densitometry": "Status A", "exposure_s": 0.5, "process": "RA-4",
    }

    # =========================================================
    # CHART (b) Spectral-Sensitivity Curves -- PAGE 3, lower
    # =========================================================
    smx, sbx, sxr = affine_fit(SENS_X)   # nm       = smx*x_px + sbx
    smy, sby, syr = affine_fit(SENS_Y)   # log_sens = smy*y_px + sby

    sens_curves = stroked_in(stroked3, 350, 552, 324, 477, center_y_max=500)
    wl_sens = np.arange(350, 751, 2.0)

    sens_layers = {}      # layer -> {"wavelength_nm":[], "log_sensitivity":[]}
    sens_audit = {}
    sens_detect = []      # (peak_nm, layer, npts, min, max)
    for i, c in enumerate(sens_curves):
        dc = to_data(polyline(c), smx, sbx, smy, sby)
        vals, rng = resample_curve(dc, wl_sens, extrapolate=False)
        peak = peak_wavelength(wl_sens, vals)
        if 400 <= peak < 500:
            layer = "yellow"    # blue-sensitive, yellow-forming
        elif 500 <= peak < 600:
            layer = "magenta"   # green-sensitive, magenta-forming
        elif 600 <= peak < 760:
            layer = "cyan"      # red-sensitive, cyan-forming
        else:
            layer = "unknown_%d" % i
        # drop NaNs, keep supported span sorted ascending
        mask = ~np.isnan(vals)
        wsub = wl_sens[mask]
        vsub = vals[mask]
        order = np.argsort(wsub)
        sens_layers[layer] = {
            "wavelength_nm": [round(float(w), 2) for w in wsub[order]],
            "log_sensitivity": [round(float(v), 4) for v in vsub[order]],
            "_peak_nm": round(peak, 2),
        }
        vmin = float(np.nanmin(vals))
        vmax = float(np.nanmax(vals))
        sens_detect.append((round(peak, 2), layer, len(dc),
                            round(vmin, 4), round(vmax, 4)))
        sens_audit[layer] = {
            "peak_nm": round(peak, 2),
            "wavelength_range_nm": [round(rng[0], 2), round(rng[1], 2)],
            "n_path_points": len(dc),
            "log_sensitivity_range": [round(vmin, 4), round(vmax, 4)],
        }

    # Three layers, asserted rather than assumed: a stray curve sharing a peak
    # band overwrites a real one, and the JSON that results looks complete.
    if len(sens_layers) != 3:
        raise SystemExit(
            "spectral sensitivity: expected exactly 3 layers, found %d (%s) "
            "from %d curves" % (len(sens_layers), ", ".join(sorted(sens_layers)),
                                len(sens_curves)))

    audit["spectral_sensitivity"] = {
        "page_index": 3,
        "x_axis": {
            "device_to_data": "wavelength_nm = %.6f*x_px + %.6f" % (smx, sbx),
            "anchors": SENS_X, "fit_rms_data": round(sxr, 5)},
        "y_axis": {
            "device_to_data": "log_sensitivity = %.6f*y_px + %.6f" % (smy, sby),
            "anchors": SENS_Y, "fit_rms_data": round(syr, 5)},
        "layer_by_peak": sens_audit,
    }

    # =========================================================
    # CHART (c) Spectral-Dye-Density Curves -- PAGE 4
    # =========================================================
    page4 = pages[4]
    els4 = list(walk(page4))
    stroked4 = [e for e in els4 if isinstance(e, LTCurve) and e.stroke]

    dmx, dbx, dxr = affine_fit(DYE_X)    # nm      = dmx*x_px + dbx
    dmy, dby, dyr = affine_fit(DYE_Y)    # density = dmy*y_px + dby

    dye_curves = stroked_in(stroked4, 76, 262, 520, 596)
    wl_dye = np.arange(400, 701, 1.0)

    dye_layers = {}       # layer -> {"wavelength_nm":[], "density":[]}
    dye_audit = {}
    dye_detect = []       # (peak_nm, layer, npts, min, max)
    for i, c in enumerate(dye_curves):
        dc = to_data(polyline(c), dmx, dbx, dmy, dby)
        vals, rng = resample_curve(dc, wl_dye, extrapolate=True)   # flat-hold edges
        peak = peak_wavelength(wl_dye, vals)
        if 400 <= peak < 500:
            layer = "yellow"
        elif 500 <= peak < 600:
            layer = "magenta"
        elif 600 <= peak <= 700:
            layer = "cyan"
        else:
            layer = "unknown_%d" % i
        dye_layers[layer] = {
            "wavelength_nm": [int(w) for w in wl_dye],
            "density": [round(float(v), 4) for v in vals],
            "_peak_nm": round(peak, 2),
        }
        vmin = float(np.min(vals))
        vmax = float(np.max(vals))
        dye_detect.append((round(peak, 2), layer, len(dc),
                           round(vmin, 4), round(vmax, 4)))
        dye_audit[layer] = {
            "peak_nm": round(peak, 2),
            "wavelength_range_nm": [round(rng[0], 2), round(rng[1], 2)],
            "n_path_points": len(dc),
            "density_range": [round(vmin, 4), round(vmax, 4)],
        }

    if len(dye_layers) != 3:
        raise SystemExit(
            "spectral dye density: expected exactly 3 layers, found %d (%s) "
            "from %d curves" % (len(dye_layers), ", ".join(sorted(dye_layers)),
                                len(dye_curves)))

    audit["spectral_dye_density"] = {
        "page_index": 4,
        "x_axis": {
            "device_to_data": "wavelength_nm = %.6f*x_px + %.6f" % (dmx, dbx),
            "anchors": DYE_X, "fit_rms_data": round(dxr, 5)},
        "y_axis": {
            "device_to_data": "density = %.6f*y_px + %.6f" % (dmy, dby),
            "anchors": DYE_Y, "fit_rms_data": round(dyr, 5)},
        "layer_by_peak": dye_audit,
    }

    # =========================================================
    # assemble paper JSON (per-layer sensitivity/dye/hd + provenance)
    # =========================================================
    # channel mapping: cyan<-R char, magenta<-G, yellow<-B
    hd_by_layer = {"cyan": "R", "magenta": "G", "yellow": "B"}

    layers = {}
    for layer in ("cyan", "magenta", "yellow"):
        sens = sens_layers[layer]
        dye = dye_layers[layer]
        hd_name = hd_by_layer[layer]
        gx, gy = char_hd[hd_name]
        layers[layer] = {
            "sensitivity": {
                "wavelength_nm": sens["wavelength_nm"],
                "log_sensitivity": sens["log_sensitivity"],
            },
            "dye": {
                "wavelength_nm": dye["wavelength_nm"],
                "density": dye["density"],
            },
            "hd": {
                "logE": gx,
                "statusA_density": gy,
            },
            "peak_sensitivity_nm": sens["_peak_nm"],
            "peak_dye_nm": dye["_peak_nm"],
        }

    out = {
        "provenance": {
            "source": "Kodak Professional ENDURA Premier Paper datasheet E-4070 "
                      "(March 2013), pages 4-5 vector charts, digitized from "
                      "embedded PDF path geometry",
            "density_measure": "status_a",
            "status": "datasheet-digitized (authoritative)",
            "process": "RA-4",
            "date": "2026-07-24",
        },
        "layers": layers,
        "digitization_audit": audit,
    }

    outp = DATA / "papers" / "EnduraPremier_paper.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(outp, "w"), indent=1)

    # ---------- mandatory stdout diagnostics ----------
    print("=== axis calibration residuals (data units) ===")
    print("char (a): x-fit RMS %.4f logE   y-fit RMS %.4f D" % (cxr, cyr))
    print("sens (b): x-fit RMS %.4f nm     y-fit RMS %.4f logS" % (sxr, syr))
    print("dye  (c): x-fit RMS %.4f nm     y-fit RMS %.4f D" % (dxr, dyr))

    print("=== curve point counts ===")
    for n in char_names:
        print("char %s : %d path pts" % (n, char_endpoints[n]["n_path_points"]))
    for peak, layer, npts, _mn, _mx in sens_detect:
        print("sens %-7s (peak %.1f nm): %d path pts" % (layer, peak, npts))
    for peak, layer, npts, _mn, _mx in dye_detect:
        print("dye  %-7s (peak %.1f nm): %d path pts" % (layer, peak, npts))

    print("=== detected peaks -> layer assignment ===")
    for peak, layer, _n, _mn, _mx in sens_detect:
        print("sens curve peak %.1f nm -> %s (forming layer)" % (peak, layer))
    for peak, layer, _n, _mn, _mx in dye_detect:
        print("dye  curve peak %.1f nm -> %s dye" % (peak, layer))

    print("=== spot values ===")

    def at(grid, arr, target):
        return float(np.interp(target, np.array(grid, float),
                               np.array(arr, float)))
    for layer in ("cyan", "magenta", "yellow"):
        d = dye_layers[layer]
        pk = d["_peak_nm"]
        print("dye %-7s density @peak %.1f nm: %.3f (expect ~1.0)"
              % (layer, pk, at(d["wavelength_nm"], d["density"], pk)))
    for n in char_names:
        gx, gy = char_hd[n]
        print("char %s : Dmin %.3f (@logE %.2f)  Dmax(shoulder) %.3f (@logE %.2f)"
              % (n, gy[0], gx[0], gy[-1], gx[-1]))
    for layer in ("cyan", "magenta", "yellow"):
        s = sens_layers[layer]
        print("sens %-7s peak log-sensitivity: %.3f @%.1f nm"
              % (layer, max(s["log_sensitivity"]), s["_peak_nm"]))

    print("=== per-curve min/max ===")
    for n in char_names:
        r = char_endpoints[n]["density_range"]
        print("char %s : min %.3f max %.3f D" % (n, r[0], r[1]))
    for peak, layer, _n, mn, mx in sens_detect:
        print("sens %-7s : min %.3f max %.3f logS" % (layer, mn, mx))
    for peak, layer, _n, mn, mx in dye_detect:
        print("dye  %-7s : min %.3f max %.3f D" % (layer, mn, mx))

    print("wrote %s" % outp.relative_to(ROOT))


if __name__ == "__main__":
    main()
