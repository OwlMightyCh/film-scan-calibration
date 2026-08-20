#!/usr/bin/env python3
"""Digitize the vector charts on page 4 (index 3) of a Portra datasheet.

Which stock is selected with --stock (default portra400, i.e. the historical
behaviour); the registry lives in portra_stocks.py.

Two of the four quadrant charts are harvested (the other two -- spectral
sensitivity and MTF -- are ignored):

  * top-left  "Characteristic Curves":      x = log exposure (lux-seconds),
              y = Status M density. Three curves, top->bottom = B, G, R.
  * top-right "Spectral-Dye-Density Curves": x = wavelength (nm),
              y = diffuse spectral density. Two curves, upper = Midscale
              Neutral, lower = Minimum Density (D-min).

All chart art is vector: LTLine/LTCurve frame + gridlines/ticks, LTCurve data
polylines, LTChar tick labels. Axes are calibrated device->data by an affine
fit to the numeric tick-label positions; the plot-frame gridlines give an
independent residual check. Data curves are the stroked LTCurves with many
vertices (the axis-aligned frame/gridlines are excluded).
"""
import json, sys
from pathlib import Path
import numpy as np
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTLine, LTCurve, LTChar

try:                                     # run as a script from engine/c41
    from portra_stocks import (check_axis_labels, datasheet_label,
                               dedupe_positions, frame_box_near, frame_boxes,
                               parse_stock)
except ImportError:                      # imported as engine.c41.portra_digitize
    from engine.c41.portra_stocks import (check_axis_labels, datasheet_label,
                                          dedupe_positions, frame_box_near,
                                          frame_boxes, parse_stock)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

sys.path.insert(0, str(ROOT))
from engine.common.pdfchart import (   # noqa: E402
    affine_fit, bezier, cluster, label_ticks, polyline, resample_curve, to_data,
    walk,
)


def main():
    stock = parse_stock(__doc__.splitlines()[0], digitizer="portra_digitize.py")
    pdf = ROOT / "film_datasheet" / stock["pdf_filename"]
    page = list(extract_pages(str(pdf)))[stock["page"]]
    els = list(walk(page))
    chars = [e for e in els if isinstance(e, LTChar)]
    stroked = [e for e in els if isinstance(e, LTCurve) and e.stroke]
    lines = [e for e in els if isinstance(e, LTLine)]

    # Chart frames, however they happen to be drawn (four long LTLines on the
    # Portra 400 characteristic chart, a single stroked five-point LTCurve rect
    # on every Portra 160 chart). Each quadrant is named by a point inside it.
    frames = frame_boxes(els)
    # The point naming each chart is per stock. Pro Image 100 puts its
    # spectral-dye-density chart bottom-centre and its sensitivity chart
    # top-right -- the reverse of the four earlier Kodak sheets -- so the
    # historical (447, 598) falls INSIDE its SENSITIVITY frame and would have
    # digitized dye density off the wrong chart without raising anything. The
    # defaults reproduce those four sheets exactly.
    cfx, cfy = stock.get("char_frame_near", (173.0, 597.0))
    sfx, sfy = stock.get("spec_frame_near", (447.0, 598.0))
    char_frame = frame_box_near(frames, cfx, cfy)
    spec_frame = frame_box_near(frames, sfx, sfy)

    audit = {}

    # ===== characteristic-curve chart (top-left) =====
    # Every device-space window on this chart is DERIVED from char_frame rather
    # than hard-coded. The absolute constants that used to live here (label band
    # y 493..501, gridline band 503 < y0 < 512, and so on) were read off Portra
    # 400 and happened to survive Portra 160, whose charts sit 0.8 pt away; Ektar
    # 100's sit ~6 pt lower and every one of them misses, which showed up as the
    # gridline detector finding 2 verticals instead of 6. The offsets below
    # reproduce the historical Portra 400 and Portra 160 selections exactly.
    if char_frame is None:
        raise SystemExit(
            "%s: no characteristic-chart frame box found on page %d. Every axis "
            "window on this chart is derived from it, so nothing can be "
            "calibrated. Run engine/c41/datasheet_forensics.py on this PDF."
            % (stock["display_name"], stock["page"] + 1))
    fx0, fy0, fx1, fy1 = char_frame

    # The x labels ("-4.0" ...) carry a minus sign that skews their centroid,
    # so calibrate this chart's axes from the gridlines (exact round values)
    # and keep the numeric-label affine fit only as an independent cross-check.
    # x labels sit in a band just below the frame's bottom edge, clear of the
    # "LOG EXPOSURE (lux-seconds)" axis title ~14 pt lower; y labels sit just
    # left of the frame's left edge, clear of the rotated "DENSITY" title.
    cx = label_ticks(chars, "x", fx0 - 45, fx1 + 40, fy0 - 12, fy0 - 4, gap=6)
    cy = label_ticks(chars, "y", fy0 - 6, fy1 + 6, fx0 - 26, fx0 - 0.5, gap=6)
    cx_lblfit = affine_fit(cx)
    cy_lblfit = affine_fit(cy)

    # vertical gridlines (incl. frame edges) at the bottom axis -> logH
    vx = {round(l.x0, 1) for l in lines
          if abs(l.x1 - l.x0) < 0.5 and fy0 - 2 < l.y0 < fy0 + 8
          and fx0 - 1.5 <= l.x0 <= fx1 + 1.5}
    # horizontal gridlines/ticks at the left axis -> density
    hy = {round(l.y0, 1) for l in lines
          if abs(l.y1 - l.y0) < 0.5 and fx0 - 1.5 <= l.x0 <= fx0 + 1.5
          and fy0 - 5 < l.y0 < fy1 + 3}
    # The frame's own edges are gridlines too, and they carry the extreme axis
    # values. Union them in from the detected frame box, whichever way it was
    # drawn. When the frame is four LTLines (Portra 400) they are already in
    # these sets at the same rounding, so the union is idempotent and cannot
    # move that stock's numbers; when it is a stroked rect (Portra 160) this is
    # what supplies the two missing verticals and two missing horizontals.
    if char_frame is not None:
        vx |= {round(char_frame[0], 1), round(char_frame[2], 1)}
        hy |= {round(char_frame[1], 1), round(char_frame[3], 1)}
    # Ultra Max 400 draws this chart twice, ~0.1 pt apart, doubling every
    # gridline; the count-based tick assignment below would then walk off the
    # axis. No-op on sheets drawn once.
    vx = dedupe_positions(vx)
    hy = dedupe_positions(hy)
    # The frame edge IS a decade tick on the four earlier Kodak sheets, so the
    # union above is right for them. Pro Image 100's characteristic plot box
    # extends 16.2 pt to the LEFT of its -3.0 tick, where a decade is 46.1 pt,
    # so its left edge is not a tick at all; admitting it would hand the whole
    # axis one extra decade and shift every logH value. This window keeps only
    # true ticks. Curve data lying outside it is NOT clipped -- it is placed by
    # the affine fit, which is exact and linear either side of the last tick.
    if stock.get("char_vx_window"):
        _lo, _hi = stock["char_vx_window"]
        vx = [v for v in vx if _lo <= v <= _hi]
    # Axis ORIGINS are per stock, not constants. Ektar 100's logH axis runs
    # -3.0..+2.0 where both Portras run -4.0..+1.0 -- same six ticks, different
    # values, so the count guard below cannot see the difference. The density
    # origin is 0.0 on all three stocks and is still per-stock, because the
    # "-4.0 is universal" assumption is what this fix is repairing.
    x0val = stock["char_x_origin"]
    y0val = stock["char_y_origin"]
    xticks = list(zip(vx, np.arange(x0val, x0val + len(vx))))
    yticks = list(zip(hy, np.arange(y0val, y0val + len(hy))))
    # Tick VALUES are inferred from the tick COUNT, so a single missed gridline
    # shifts the whole axis -- by a decade in logH, or by 1.0 D in density --
    # without raising anything. Portra 400 draws its chart frame as four LTLines
    # (x 81.16/265.63, y 504.63/689.15) so all six/five are found; Portra 160
    # draws the same frame as a stroked LTCurve *rectangle*, so its edges are
    # invisible here and both counts come up short. Fail loudly rather than
    # emit a plausible-looking, decade-shifted curve set.
    # Tick COUNT is per stock too: Gold 200's characteristic chart has FIVE
    # verticals spanning -3.0..+1.0 where both Portras have six over -4.0..+1.0
    # and Ektar six over -3.0..+2.0. Three conventions in four datasheets.
    n_x = stock.get("char_n_x", 6)
    n_y = stock.get("char_n_y", 5)
    if len(vx) != n_x or len(hy) != n_y:
        raise SystemExit(
            "%s: char-chart gridline detection found %d vertical (expect %d, "
            "logH %+.1f..%+.1f) and %d horizontal (expect %d, density %.1f..%.1f)"
            ". Axis calibration would be silently wrong, so refusing to write. "
            "The frame edges on this datasheet are likely a stroked LTCurve "
            "rectangle rather than LTLines -- the detector needs to accept "
            "both before this stock can be digitized."
            % (stock["display_name"], len(vx), n_x, x0val, x0val + n_x - 1,
               len(hy), n_y, y0val, y0val + n_y - 1))
    cmx, cbx, cxr = affine_fit(xticks)
    cmy, cby, cyr = affine_fit(yticks)
    # The count guard above is blind to a wrong ORIGIN -- six evenly spaced
    # gridlines fit -4.0..+1.0 and -3.0..+2.0 equally perfectly, and Ektar 100
    # really does use the latter. Only the printed numeric labels can tell them
    # apart, so the fit is evaluated at the label positions and must agree.
    # Gold 200's x labels lose their minus signs in extraction
    # ('3.02.01.00.01.0'), so the cross-check cannot validate that axis there.
    # Flagged per stock rather than silently skipped -- and note the dye
    # DECOMPOSITION never reads this chart, only the spectral one, so the
    # basis work is unaffected either way.
    if stock.get("char_x_labels_unreliable"):
        print("NOTE %s: x-axis label cross-check SKIPPED (minus signs are not "
              "extractable on this datasheet); x calibration rests on the "
              "gridline count + registry origin alone." % stock["display_name"])
        cx_off = None
    else:
        cx_off = check_axis_labels(stock, "characteristic", "x (logH)",
                                   cmx, cbx, cx)
    cy_off = check_axis_labels(stock, "characteristic", "y (Status M density)",
                               cmy, cby, cy)

    # data curves: stroked LTCurves inside the frame with many vertices,
    # not axis-aligned (frame/gridlines have ~0 width or height).
    # The selection window is per stock rather than derived from char_frame: the
    # frames sit ~0.8 pt apart between stocks and the data curves run right up
    # to the left/right edges, so Portra 160 needs a hair more room on x1 while
    # Portra 400 must keep its historical window bit-for-bit.
    cw0, cw1, cw2, cw3 = stock["char_curve_window"]
    char_curves = []
    for c in stroked:
        x0, y0, x1, y1 = c.bbox
        if len(c.original_path) >= 10 and (x1 - x0) > 30 and (y1 - y0) > 5 \
                and x0 > cw0 and x1 < cw1 and y0 > cw2 and y1 < cw3:
            char_curves.append(c)
    # top->bottom by bbox-center y = B, G, R
    char_curves.sort(key=lambda c: -(c.bbox[1] + c.bbox[3]) / 2)
    names = ["B", "G", "R"]

    char_data = {}
    ranges = []
    for c in char_curves:
        dc = to_data(polyline(c), cmx, cbx, cmy, cby)
        char_data[c] = dc
        order = np.argsort(dc[:, 0])
        ranges.append((dc[order, 0][0], dc[order, 0][-1]))
    lo = max(r[0] for r in ranges); hi = min(r[1] for r in ranges)
    logH = np.round(np.arange(np.ceil(lo / 0.02) * 0.02,
                              np.floor(hi / 0.02) * 0.02 + 1e-9, 0.02), 2)
    statusM = {}
    char_endpoints = {}
    for name, c in zip(names, char_curves):
        vals, rng = resample_curve(char_data[c], logH, extrapolate=False)
        statusM[name] = [round(float(v), 4) for v in vals]
        char_endpoints[name] = {"logH_range": [round(rng[0], 4), round(rng[1], 4)],
                                "n_path_points": len(char_data[c]),
                                "density_range": [round(float(np.nanmin(vals)), 4),
                                                  round(float(np.nanmax(vals)), 4)]}

    # ---- assert the B/G/R assignment, which is otherwise a bare heuristic ----
    # The three curves are named purely by vertical order above, exactly the
    # heuristic that is unsafe on RA-4 paper, where the curves cross two or
    # three times and touch to 0.0000 D. It is safe HERE for a physical reason
    # worth asserting rather than assuming: the orange mask offsets the three
    # records, so on a C-41 negative blue sits above green sits above red at
    # every exposure. Measured across the eleven-stock fleet the smallest gap
    # anywhere is 0.175 D (Fujicolor 100) with no sign change on any stock, so
    # a 0.05 D floor is far below the real margin and far above tracing noise.
    # The overlay cannot catch a swap -- permuting labels moves no plotted point
    # -- so this is the only mechanical guard the assignment has.
    _ORDER_FLOOR_D = 0.05
    _ord = np.array([statusM[k] for k in ("B", "G", "R")], float)
    _gap = np.nanmin(np.diff(-_ord, axis=0), axis=1)          # B-G, G-R at worst
    if not np.all(_gap > _ORDER_FLOOR_D):
        raise SystemExit(
            "ABORT: characteristic curves are not ordered B > G > R by at least "
            "%.2f D (worst B-G %.4f, G-R %.4f). Vertical order is how these "
            "curves are named, so this means the assignment is unreliable on "
            "this sheet -- LOOK at the rendered chart before trusting it."
            % (_ORDER_FLOOR_D, _gap[0], _gap[1]))

    # gridline residual check (independent of label fit)
    char_hgrid = [l for l in lines if abs(l.y1 - l.y0) < 0.5
                  and fx0 - 0.5 <= l.x0 <= fx0 + 1.5 and (l.x1 - l.x0) > 100]
    ygrid_res = []
    for l in char_hgrid:
        d = l.y0 * cmy + cby
        ygrid_res.append(round(d - round(d), 4))
    char_vgrid = [l for l in lines if abs(l.x1 - l.x0) < 0.5
                  and fy0 - 2 < l.y0 < fy0 + 2 and fx0 - 0.5 <= l.x0 <= fx1 + 0.5]
    xgrid_res = []
    for l in char_vgrid:
        d = l.x0 * cmx + cbx
        xgrid_res.append(round(d - round(d), 4))

    audit["characteristic_curves"] = {
        "calibration_basis": "gridlines (exact round values); numeric labels used only as cross-check",
        "x_axis": {"device_to_data": "logH = %.6f*x_px + %.6f" % (cmx, cbx),
                   "gridline_ticks": [(round(p, 2), round(v, 2)) for p, v in xticks],
                   "gridline_fit_rms_data": round(cxr, 5),
                   "label_fit": "logH = %.6f*x_px + %.6f (rms %.4f)" % cx_lblfit,
                   "gridline_residuals": xgrid_res},
        "y_axis": {"device_to_data": "densityM = %.6f*y_px + %.6f" % (cmy, cby),
                   "gridline_ticks": [(round(p, 2), round(v, 2)) for p, v in yticks],
                   "gridline_fit_rms_data": round(cyr, 5),
                   "label_fit": "densityM = %.6f*y_px + %.6f (rms %.4f)" % cy_lblfit,
                   "gridline_residuals": ygrid_res},
        "curve_point_counts": {n: char_endpoints[n]["n_path_points"] for n in names},
        "endpoints": char_endpoints,
    }

    # ===== spectral-dye-density chart (top-right) =====
    # This chart's axes are calibrated FROM the labels (no count inference), so
    # there is nothing to cross-check -- but the label bands themselves are per
    # stock rather than derived, because frame_boxes() does not find Portra 400's
    # spectral frame at all and there is nothing to derive from on that stock.
    # Ektar 100's charts sit ~6 pt lower, so it needs its own band.
    sx = label_ticks(chars, "x", *stock["spec_x_label_band"], gap=6)
    sy = label_ticks(chars, "y", *stock["spec_y_label_band"], gap=6)
    smx, sbx, sxr = affine_fit(sx)
    smy, sby, syr = affine_fit(sy)

    # Select the curves lying inside this quadrant's frame (small tolerance --
    # both dye curves start and end on the frame's left/right edges, so an
    # absolute window a pixel inside the frame drops them entirely). Fall back to
    # the historical hand-read window if no frame box was found here.
    if spec_frame is not None:
        pad = 2.0
        sw0, sw1 = spec_frame[0] - pad, spec_frame[2] + pad
        sw2, sw3 = spec_frame[1] - pad, spec_frame[3] + pad
    else:
        sw0, sw1, sw2, sw3 = 356.0, 543.0, 503.0, 690.0
    spec_curves = []
    for c in stroked:
        x0, y0, x1, y1 = c.bbox
        if len(c.original_path) >= 10 and (x1 - x0) > 100 and (y1 - y0) > 10 \
                and x0 > sw0 and x1 < sw1 and y0 > sw2 and y1 < sw3:
            spec_curves.append(c)
    # upper (higher center y) = Midscale Neutral, lower = D-min
    spec_curves.sort(key=lambda c: -(c.bbox[1] + c.bbox[3]) / 2)
    spec_names = ["midscale_neutral", "dmin"]

    wl = np.arange(400, 701, 1.0)
    spec_out = {}
    spec_endpoints = {}
    for name, c in zip(spec_names, spec_curves):
        dc = to_data(polyline(c), smx, sbx, smy, sby)
        vals, rng = resample_curve(dc, wl, extrapolate=True)   # flat-extrapolate edges
        spec_out[name] = [round(float(v), 4) for v in vals]
        spec_endpoints[name] = {"wavelength_range_nm": [round(rng[0], 2), round(rng[1], 2)],
                                "n_path_points": len(dc),
                                "density_range": [round(float(np.min(vals)), 4),
                                                  round(float(np.max(vals)), 4)]}

    # short y ticks hanging off the frame's left edge; the edge sits ~1 pt
    # further left on Portra 160, so the window is per stock
    tw0, tw1 = stock["spec_ygrid_x_window"]
    spec_hgrid = [l for l in lines if abs(l.y1 - l.y0) < 0.5 and tw0 < l.x0 < tw1
                  and (l.x1 - l.x0) < 6]
    syg_res = []
    for l in spec_hgrid:
        d = l.y0 * smy + sby
        syg_res.append(round(d - round(d * 2) / 2, 4))

    audit["spectral_dye_density"] = {
        "x_axis": {"device_to_data": "wavelength_nm = %.6f*x_px + %.6f" % (smx, sbx),
                   "label_ticks": sx, "fit_rms_data": round(sxr, 5)},
        "y_axis": {"device_to_data": "density = %.6f*y_px + %.6f" % (smy, sby),
                   "label_ticks": sy, "fit_rms_data": round(syr, 5),
                   "gridline_residuals_halfstep": syg_res},
        "curve_point_counts": {n: spec_endpoints[n]["n_path_points"] for n in spec_names},
        "endpoints": spec_endpoints,
    }

    # Curve-to-channel assignment is a heuristic on vertical order, and it is the
    # ONE error class the overlay check (datasheet_overlay.py) cannot see: a
    # swapped pair leaves every curve sitting on printed ink and every residual
    # clean, because only the LABELS moved. Verified empirically -- a deliberate
    # B<->R swap still scores 100% ink-hit. So assert the ordering here instead.
    # On a C-41 negative the blue-sensitive (yellow-dye) record carries the most
    # Status M density at every exposure, then green, then red; margins across the
    # six digitized stocks run 0.21-0.40 D, far above any tracing noise.
    for hi, lo in (("B", "G"), ("G", "R")):
        a = np.array(statusM[hi], float)
        b = np.array(statusM[lo], float)
        m = np.isfinite(a) & np.isfinite(b)
        if m.any() and not np.all(a[m] >= b[m] - 1e-9):
            raise SystemExit(
                "%s: characteristic curve order violated -- %s is not >= %s over "
                "the common support (worst %.4f D). The curves were assigned to "
                "channels by vertical order; that heuristic has failed for this "
                "sheet, so the channel labels are wrong."
                % (stock["file_prefix"], hi, lo, float((a[m] - b[m]).min())))

    out = {
        "source": datasheet_label(stock) + ", page 4 vector charts, "
                  "digitized from the embedded PDF path geometry",
        "char_curves": {
            "log_exposure": [round(float(x), 2) for x in logH],
            "log_exposure_units": "log lux-seconds",
            "statusM_density": statusM,
            "curve_order_note": "at any exposure, top->bottom on the plot = B, G, R",
        },
        "spectral": {
            "wavelength_nm": [int(x) for x in wl],
            "midscale_neutral": spec_out["midscale_neutral"],
            "dmin": spec_out["dmin"],
        },
        "digitization_audit": audit,
    }
    outp = DATA / "films" / stock["curves_json"]
    json.dump(out, open(outp, "w"), indent=1)

    # ---------- mandatory stdout diagnostics ----------
    print("=== axis calibration residuals (data units) ===")
    print("char  : x-fit RMS %.4f logH   y-fit RMS %.4f D" % (cxr, cyr))
    print("        x gridline residuals %s" % xgrid_res)
    print("        y gridline residuals %s" % ygrid_res)
    print("        label cross-check median offset: x %s logH  y %+.4f D "
          "(origins %+.1f / %.1f)"
          % ("SKIPPED" if cx_off is None else "%+.4f" % cx_off,
             cy_off, x0val, y0val))
    print("spectral: x-fit RMS %.4f nm    y-fit RMS %.4f D" % (sxr, syr))
    print("        y gridline residuals (half-step) %s" % syg_res)
    print("=== curve point counts ===")
    for n in names:
        print("char %s : %d path pts" % (n, char_endpoints[n]["n_path_points"]))
    for n in spec_names:
        print("spec %s : %d path pts" % (n, spec_endpoints[n]["n_path_points"]))

    def at(grid, arr, target):
        return float(np.interp(target, grid, np.array(arr, float)))
    print("=== spot values ===")
    for w in (450, 550, 650):
        print("Dmin      @%dnm: %.3f" % (w, at(wl, spec_out["dmin"], w)))
    for w in (450, 550, 650):
        print("Midscale  @%dnm: %.3f" % (w, at(wl, spec_out["midscale_neutral"], w)))
    for n in names:
        for h in (-2.0, 0.0):
            print("char %s density @logH=%+.1f: %.3f" % (n, h, at(logH, statusM[n], h)))
    print("=== per-curve min/max ===")
    for n in names:
        r = char_endpoints[n]["density_range"]
        print("char %s : min %.3f max %.3f D" % (n, r[0], r[1]))
    for n in spec_names:
        r = spec_endpoints[n]["density_range"]
        print("spec %s : min %.3f max %.3f D" % (n, r[0], r[1]))
    print("wrote %s" % outp.relative_to(ROOT))


if __name__ == "__main__":
    main()
