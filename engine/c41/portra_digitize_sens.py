#!/usr/bin/env python3
"""Digitize the bottom-left chart on page 4 (index 3) of a Portra datasheet.

Which stock is selected with --stock (default portra400, i.e. the historical
behaviour); the registry lives in portra_stocks.py.

The "Spectral-Sensitivity Curves" quadrant (bottom-left) is harvested here; the
sibling script engine/portra_digitize.py handles the top-left characteristic and
top-right spectral-dye-density quadrants and is NOT modified.

  * bottom-left "Spectral-Sensitivity Curves": x = wavelength (nm, 250..750,
    gridlines every 50 nm), y = log10 sensitivity, whose origin AND tick count
    are per stock (Portra 400 0.0..4.0, Portra 160 -1.0..3.0, Ektar 100
    0.0..3.0 with only four gridlines). Three data curves,
    one per dye-forming layer. They overlap in x, so they are classified by peak
    wavelength / x-extent rather than by vertical order:
        yellow-forming  (shortest peak, support ~350-510 nm)
        magenta-forming (middle peak,   support ~490-610 nm)
        cyan-forming    (longest peak,  support ~520-700 nm, peak ~640-660 nm)

  Sensitivity per the datasheet = log10(1/H) for the exposure H giving a density
  0.2 above D-min; daylight; 1/50 s.

Same pdfminer vector method as portra_digitize.py: the chart art is a vector
LTRect frame + LTLine gridlines + stroked LTCurve data polylines + LTChar tick
labels. Axes are calibrated device->data from the exact-valued gridlines (frame
edges + interior gridlines); the numeric tick labels give an independent
cross-check residual.
"""
import json, sys
from pathlib import Path
import numpy as np
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTLine, LTCurve, LTChar, LTRect

try:                                     # run as a script from engine/c41
    from portra_stocks import (check_axis_labels, datasheet_label,
                               dedupe_positions, frame_box_near, frame_boxes,
                               parse_stock)
except ImportError:                      # imported as engine.c41.portra_digitize_sens
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

# The plot-frame device-space window is per stock and lives in the registry
# ("sens_frame"), read off page-4 geometry. It is deliberately NOT derived from
# the page at run time: this frame is a stroked LTCurve rectangle on both stocks,
# and the derived floats differ from the historical hand-read constants in their
# last digit, which would perturb Portra 400's serialized audit block.


# ---------------------------------------------------------------------------
# Fragment stitching (Gold 200 only, gated on the registry's
# "sens_stitch_fragments"). Portra 400/160, Ektar 100 and Ultramax 400 each
# draw a sensitivity curve as ONE long stroked polyline, which the
# ">= 10 path ops and > 30 pt wide" test in main() picks up directly. Gold 200
# draws the same three curves as ~64 short fragments of 4-7 path ops, every one
# of which fails that test -- which is why the stock was previously declared
# undigitizable.
#
# The fragments are not scattered: consecutive ones share an endpoint EXACTLY
# (fragment k's last point is fragment k+1's first point), so the bulk of the
# work is an exact-coincidence chain walk. What is left after that walk is a
# small number of real drawing breaks, and those are the only place judgement is
# needed -- see _bridge_tracks.
GAP_MAX_NM = 20.0      # widest drawing break considered for bridging
SLOPE_TOL = 0.005      # log-sensitivity per nm; agreement required to bridge
PRED_TOL = 0.05        # log-sensitivity; |linear prediction - actual| to bridge
ORPHAN_MAX_NM = 60.0   # widest x gap over which an orphan track may be adopted
# Expected peak bands per layer, used only as an assertion on the result.
PEAK_BANDS = {"yellow": (360.0, 500.0), "magenta": (470.0, 600.0),
              "cyan": (560.0, 700.0)}


def _endpoint_slope(dc, at_end):
    """Local d(log-sensitivity)/d(wavelength) at one end of a data-space track.

    Measured over the points within 5 nm of the endpoint (at least two, at most
    eight) rather than over a fixed vertex count, because the fragments are
    subdivided far more densely on steep sections than on flat ones.
    """
    pts = dc[::-1] if at_end else dc
    x0 = pts[0, 0]
    k = 1
    while k < len(pts) - 1 and k < 8 and abs(pts[k, 0] - x0) < 5.0:
        k += 1
    dx = pts[k, 0] - x0
    if abs(dx) < 1e-9:
        return 0.0
    return float((pts[k, 1] - pts[0, 1]) / dx)


def _chain_exact(frags, eps=0.05):
    """Greedily concatenate device-space polylines that share an endpoint.

    Either orientation of a candidate is accepted; the caller re-orients the
    finished chain. eps is in PDF points -- the shared endpoints are bit-equal
    in practice, so this is a rounding guard, not a tolerance to tune.
    """
    pool = [[tuple(map(float, p)) for p in f] for f in frags]
    chains = []
    while pool:
        chain = pool.pop(0)
        grew = True
        while grew:
            grew = False
            for i, seg in enumerate(pool):
                for cand in (seg, seg[::-1]):
                    if np.hypot(chain[-1][0] - cand[0][0],
                                chain[-1][1] - cand[0][1]) <= eps:
                        chain = chain + cand[1:]
                    elif np.hypot(chain[0][0] - cand[-1][0],
                                  chain[0][1] - cand[-1][1]) <= eps:
                        chain = cand[:-1] + chain
                    else:
                        continue
                    pool.pop(i)
                    grew = True
                    break
                if grew:
                    break
        chains.append(np.array(chain, float))
    return chains


def _bridge_tracks(tracks, log):
    """Merge tracks separated by a drawing break, NEVER across a real gap.

    A break is an artefact of the drawing (the line is lifted where something
    else overlaps it) when the two facing ends agree in BOTH slope and value:
    extrapolating the left track linearly across the gap must land on the right
    track's first point. That is a strong test -- on Gold 200 the artefact
    break misses by 0.008 log-sens with the two slopes agreeing to 0.0003/nm,
    while the one genuine gap (a curve that dives below the 0.0 axis floor and
    resurfaces later) misses on slope by 60x that.

    Refusing to bridge is the safe direction: an unbridged gap becomes JSON
    null, which is honest about an unmeasured region. Bridging it would
    fabricate a straight line across data the datasheet never printed -- the
    defect registered against Ektar 100.
    """
    tracks = sorted(tracks, key=lambda t: t[0, 0])
    while True:
        best = None
        for i in range(len(tracks)):
            for j in range(len(tracks)):
                if i == j:
                    continue
                a, b = tracks[i], tracks[j]
                gap = b[0, 0] - a[-1, 0]
                if not (0.0 < gap <= GAP_MAX_NM):
                    continue
                sa = _endpoint_slope(a, True)
                sb = _endpoint_slope(b, False)
                dslope = abs(sa - sb)
                resid = abs((a[-1, 1] + sa * gap) - b[0, 1])
                if dslope > SLOPE_TOL or resid > PRED_TOL:
                    continue
                if best is None or resid < best[0]:
                    best = (resid, i, j, gap, dslope)
        if best is None:
            return tracks
        resid, i, j, gap, dslope = best
        log("bridged a %.1f nm drawing break at %.1f nm "
            "(slope agreement %.5f/nm, prediction residual %.4f logSens)"
            % (gap, tracks[i][-1, 0], dslope, resid))
        merged = np.vstack([tracks[i], tracks[j]])
        tracks = [t for k, t in enumerate(tracks) if k not in (i, j)]
        tracks.append(merged)
        tracks.sort(key=lambda t: t[0, 0])


def stitch_sens_fragments(stroked, frame, smx, sbx, smy, sby, inframe, log):
    """Return {layer: [data-space segment, ...]} for a fragment-drawn chart.

    Segments within a layer are x-disjoint and ordered; more than one means a
    genuine gap that the caller must serialize as null, not interpolate.
    """
    FX0, FY0, FX1, FY1 = frame
    frags = []
    for c in stroked:
        x0, y0, x1, y1 = c.bbox
        # >= 4 path ops drops the L-shaped axis pair (a 3-op path); the width
        # test is a second guard against ever chaining the frame into a curve.
        if len(c.original_path) >= 4 and inframe(x0, y0, x1, y1) \
                and (x1 - x0) < 0.9 * (FX1 - FX0):
            frags.append(polyline(c))
    if not frags:
        raise SystemExit("fragment stitching found no candidate path fragments "
                         "inside the sensitivity frame")

    chains = _chain_exact(frags)
    tracks = []
    for ch in chains:
        dc = to_data(ch, smx, sbx, smy, sby)
        if dc[0, 0] > dc[-1, 0]:
            dc = dc[::-1]
        tracks.append(dc)
    log("%d path fragments chained into %d continuous tracks"
        % (len(frags), len(tracks)))

    tracks = _bridge_tracks(tracks, log)
    if len(tracks) < 3:
        raise SystemExit("fragment stitching produced only %d tracks; the chart "
                         "has three sensitivity curves" % len(tracks))

    # The three layer curves are the three tracks reaching highest above the
    # axis floor; anything else is a detached low-level tail of one of them.
    order = sorted(range(len(tracks)), key=lambda k: -float(tracks[k][:, 1].max()))
    seeds = sorted(order[:3], key=lambda k: float(
        tracks[k][np.argmax(tracks[k][:, 1]), 0]))
    layers = {name: [tracks[k]] for name, k in zip(("yellow", "magenta", "cyan"),
                                                   seeds)}
    seed_name = {k: n for n, k in zip(("yellow", "magenta", "cyan"), seeds)}

    for k in order[3:]:
        t = tracks[k]
        # An orphan belongs to the one layer it does NOT overlap in x and whose
        # facing end it is nearest to. Overlap disqualifies: two curves that
        # coexist over the same wavelengths cannot be one curve.
        cand = []
        for s in seeds:
            a, b = tracks[s], t
            if not (b[-1, 0] < a[0, 0] or b[0, 0] > a[-1, 0]):
                continue
            gap = (a[0, 0] - b[-1, 0]) if b[-1, 0] < a[0, 0] else (b[0, 0] - a[-1, 0])
            if gap <= ORPHAN_MAX_NM:
                cand.append((gap, s))
        if not cand:
            raise SystemExit(
                "fragment stitching left an unassignable track spanning "
                "%.1f-%.1f nm (peak %.2f logSens). Refusing to guess which "
                "layer it belongs to." % (t[0, 0], t[-1, 0], t[:, 1].max()))
        gap, s = min(cand)
        layers[seed_name[s]].append(t)
        log("adopted a detached %.1f-%.1f nm tail into %s across a %.1f nm gap "
            "left as null (below the %.1f axis floor)"
            % (t[0, 0], t[-1, 0], seed_name[s], gap, smy * FY0 + sby))

    for name in layers:
        layers[name].sort(key=lambda t: t[0, 0])
    return layers


def main():
    stock = parse_stock(__doc__.splitlines()[0], digitizer="portra_digitize_sens.py")
    pdf = ROOT / "film_datasheet" / stock["pdf_filename"]
    page = list(extract_pages(str(pdf)))[stock["page"]]
    els = list(walk(page))
    chars = [e for e in els if isinstance(e, LTChar)]
    stroked = [e for e in els if isinstance(e, LTCurve) and e.stroke]
    lines = [e for e in els if isinstance(e, LTLine)]
    rects = [e for e in els if isinstance(e, LTRect)]

    FX0, FY0, FX1, FY1 = stock["sens_frame"]
    # the frame as actually drawn, used only to recover its edges as gridlines
    # when it is a stroked LTCurve rectangle (pdfminer then yields no LTRect for
    # it, so the rects loops below find nothing)
    sens_frame = frame_box_near(frame_boxes(els),
                                (FX0 + FX1) / 2, (FY0 + FY1) / 2)

    def inframe(x0, y0, x1, y1, pad=3.0):
        return (x0 > FX0 - pad and x1 < FX1 + pad
                and y0 > FY0 - pad and y1 < FY1 + pad)

    # ----- axis calibration from exact-valued gridlines -----
    # vertical gridlines (interior LTLines) + frame left/right edges -> wavelength
    # A gridline may be drawn as SEVERAL segments, broken where a data curve
    # crosses it -- Gold 200 does this, and a single-segment full-height test
    # finds only 4 of its 11 verticals, which silently rescales the wavelength
    # axis. So group vertical segments by x and judge each group by the extent
    # its segments COVER between them.
    _vsegs = {}
    for l in lines:
        if abs(l.x1 - l.x0) < 0.5 and FX0 - 1 <= l.x0 <= FX1 + 1:
            lo, hi = min(l.y0, l.y1), max(l.y0, l.y1)
            if hi > FY0 - 2 and lo < FY1 + 2:            # inside the plot band
                k = round(l.x0, 1)
                a, b = _vsegs.get(k, (lo, hi))
                _vsegs[k] = (min(a, lo), max(b, hi))
    _need = 0.60 * (FY1 - FY0)
    vx = {k for k, (lo, hi) in _vsegs.items()
          if lo < FY0 + 5 and (hi - lo) >= _need}
    for r in rects:
        if inframe(*r.bbox, pad=2.0):
            vx.add(round(r.bbox[0], 1)); vx.add(round(r.bbox[2], 1))
    if sens_frame is not None:           # frame drawn as a stroked LTCurve rect
        vx.add(round(sens_frame[0], 1)); vx.add(round(sens_frame[2], 1))
    vx = dedupe_positions(vx)
    xvals = np.arange(250.0, 250.0 + 50.0 * len(vx), 50.0)[:len(vx)]
    xticks = list(zip(vx, xvals))
    smx, sbx, sxr = affine_fit(xticks)

    # horizontal gridlines (interior LTLines) + frame bottom/top edges -> log sens
    hy = {round(l.y0, 1) for l in lines
          if abs(l.y1 - l.y0) < 0.5 and FY0 - 1 <= l.y0 <= FY1 + 1
          and min(l.x0, l.x1) < FX0 + 5
          # Gridlines need only START at the left edge, not span the full width:
          # Gold 200 draws its 1.0 log-sens gridline short (x 74.87-179.14 of a
          # 74.87-275.39 plot), and a full-width test silently drops it, which
          # shifts the whole axis by one decade. 25% of the plot width is well
          # clear of tick marks while accepting a genuinely short gridline.
          and max(l.x0, l.x1) > FX0 + 0.25 * (FX1 - FX0)}
    for r in rects:
        if inframe(*r.bbox, pad=2.0):
            hy.add(round(r.bbox[1], 1)); hy.add(round(r.bbox[3], 1))
    if sens_frame is not None:
        hy.add(round(sens_frame[1], 1)); hy.add(round(sens_frame[3], 1))
    hy = dedupe_positions(hy)
    # The bottom gridline is NOT 0.0 on every datasheet: Portra 400's log-sens
    # axis runs 0.0..4.0, Portra 160's runs -1.0..3.0. Inferring it as 0.0 makes
    # every Portra 160 sensitivity 1.0 too high -- which reads as the slower
    # stock being MORE sensitive than the faster one. Per-stock, from the axis
    # labels, not assumed.
    y0val = stock["sens_y_origin"]
    yvals = np.arange(y0val, y0val + 1.0 * len(hy), 1.0)[:len(hy)]
    yticks = list(zip(hy, yvals))
    smy, sby, syr = affine_fit(yticks)

    # independent cross-check: numeric tick labels (x below frame, y left of frame)
    xlbl = label_ticks(chars, "x", FX0 - 10, FX1 + 10, FY0 - 16, FY0 - 2, gap=6)
    ylbl = label_ticks(chars, "y", FY0 - 4, FY1 + 4, FX0 - 20, FX0 - 2, gap=4)
    xlbl_fit = affine_fit(xlbl) if len(xlbl) >= 2 else (0.0, 0.0, 0.0)
    ylbl_fit = affine_fit(ylbl) if len(ylbl) >= 2 else (0.0, 0.0, 0.0)

    # Anchor check on sens_y_origin. The whole y axis hangs off that one number
    # and a wrong one shifts every sensitivity by a constant, which is invisible
    # in the residuals (evenly-spaced gridlines fit any origin perfectly). The
    # rotated "LOG SENSITIVITY" axis title pollutes the middle of ylbl, so fit
    # rms is not usable here -- but the extreme labels sit within ~1.5 pt of the
    # frame edges on both datasheets, so compare against those directly.
    for edge, expect in ((hy[0], yvals[0]), (hy[-1], yvals[-1])):
        near = [v for pos, v in ylbl if abs(pos - edge) <= 4.0]
        if near and abs(near[0] - expect) > 0.01:
            raise SystemExit(
                "%s: log-sensitivity axis anchor mismatch -- gridline at device "
                "y=%.2f is labelled %.2f but sens_y_origin=%s implies %.2f. "
                "Every sensitivity would be offset by %.2f. Fix "
                "sens_y_origin in portra_stocks.py."
                % (stock["display_name"], edge, near[0], y0val, expect,
                   expect - near[0]))

    # General cross-check on BOTH axes, over every label rather than just the
    # two extremes. Both axes here get their tick values from a COUNT -- x from
    # 250 nm upward in 50 nm steps, y from sens_y_origin upward in steps of 1.0
    # -- and evenly spaced gridlines fit any origin with zero residual, so the
    # fit RMS cannot see an origin error. Only the printed labels can. The check
    # is median-based, which is what lets it survive Portra 160's "2.0"
    # log-sensitivity label extracting as the string "20.0".
    xlbl_off = check_axis_labels(stock, "spectral-sensitivity", "x (wavelength)",
                                 smx, sbx, xlbl)
    ylbl_off = check_axis_labels(stock, "spectral-sensitivity",
                                 "y (log sensitivity)", smy, sby, ylbl)

    # gridline residual checks (device->data landing on integers)
    xgrid_res = [round(v - round(v), 4) for v in (np.array(vx) * smx + sbx)]
    ygrid_res = [round(v - round(v), 4) for v in (np.array(hy) * smy + sby)]

    # ----- data curves: stroked LTCurves inside the frame with many vertices -----
    layer_names = ["yellow", "magenta", "cyan"]
    stitch_log = []
    stitched = bool(stock.get("sens_stitch_fragments"))

    if stitched:
        # Gold 200 draws each curve as dozens of short fragments; chain and
        # continuity-bridge them first. Each layer becomes a LIST of x-disjoint
        # data-space segments (>1 only where a real gap survives bridging).
        segs_by_layer = stitch_sens_fragments(
            stroked, (FX0, FY0, FX1, FY1), smx, sbx, smy, sby, inframe,
            stitch_log.append)
        curve_segs = [segs_by_layer[n] for n in layer_names]
    else:
        sens_curves = []
        for c in stroked:
            x0, y0, x1, y1 = c.bbox
            if len(c.original_path) >= 10 and (x1 - x0) > 30 and (y1 - y0) > 10 \
                    and inframe(x0, y0, x1, y1):
                sens_curves.append(c)
        curve_segs = [[to_data(polyline(c), smx, sbx, smy, sby)]
                      for c in sens_curves]

    # data-space curve + peak wavelength (x at max log-sensitivity)
    curve_data = []
    for segs in curve_segs:
        dc = np.vstack(segs)
        order = np.argsort(dc[:, 0])
        xs, ys = dc[order, 0], dc[order, 1]
        peak_x = float(xs[np.argmax(ys)])
        peak_y = float(np.max(ys))
        curve_data.append({"segs": segs, "dc": dc,
                           "lo": float(xs[0]), "hi": float(xs[-1]),
                           "peak_wl": peak_x, "peak_logsens": peak_y})

    # classify by peak wavelength ascending: yellow < magenta < cyan
    curve_data.sort(key=lambda d: d["peak_wl"])
    layers = dict(zip(layer_names, curve_data))

    # union 1-nm support grid across all three curves
    lo = int(np.floor(min(d["lo"] for d in curve_data)))
    hi = int(np.ceil(max(d["hi"] for d in curve_data)))
    wl = np.arange(lo, hi + 1, 1.0)

    log_sens = {}
    supports = {}
    for name in layer_names:
        d = layers[name]
        if stitched and name in PEAK_BANDS:
            b0, b1 = PEAK_BANDS[name]
            if not b0 <= d["peak_wl"] <= b1:
                raise SystemExit(
                    "%s: stitched %s-layer peak is %.1f nm, outside the "
                    "plausible %.0f-%.0f nm band -- the fragments were chained "
                    "into the wrong curves."
                    % (stock["display_name"], name, d["peak_wl"], b0, b1))
        # Resample each segment on its OWN support and merge. A layer with more
        # than one segment has a genuine unmeasured gap between them, and the
        # samples in that gap stay NaN -> JSON null. Interpolating across it is
        # exactly the fabrication this guards against.
        vals = np.full(len(wl), np.nan)
        spans = []
        for seg in d["segs"]:
            sv, srng = resample_curve(seg, wl, extrapolate=False)
            vals = np.where(np.isfinite(sv), sv, vals)
            spans.append([round(srng[0], 2), round(srng[1], 2)])
        rng = (min(s[0] for s in spans), max(s[1] for s in spans))
        # NaN outside each curve's own support -> JSON null
        log_sens[name] = [None if not np.isfinite(v) else round(float(v), 4)
                          for v in vals]
        supports[name] = {"support_nm": [round(rng[0], 2), round(rng[1], 2)],
                          "peak_wavelength_nm": round(d["peak_wl"], 2),
                          "peak_log_sensitivity": round(d["peak_logsens"], 4),
                          "n_path_points": len(d["dc"])}
        if stitched:
            supports[name]["measured_segments_nm"] = spans
            supports[name]["gaps_left_null_nm"] = [
                [spans[k][1], spans[k + 1][0]] for k in range(len(spans) - 1)]

    audit = {
        "calibration_basis": "gridlines (exact round values: frame edges + interior "
                             "gridlines); numeric labels used only as cross-check",
        "frame_device_bbox": [FX0, FY0, FX1, FY1],
        "x_axis": {"device_to_data": "wavelength_nm = %.6f*x_px + %.6f" % (smx, sbx),
                   "gridline_ticks": [(round(p, 2), round(v, 2)) for p, v in xticks],
                   "gridline_fit_rms_data": round(sxr, 5),
                   "label_fit": "wavelength_nm = %.6f*x_px + %.6f (rms %.4f)" % xlbl_fit,
                   "gridline_residuals": xgrid_res},
        "y_axis": {"device_to_data": "log_sensitivity = %.6f*y_px + %.6f" % (smy, sby),
                   "gridline_ticks": [(round(p, 2), round(v, 2)) for p, v in yticks],
                   "gridline_fit_rms_data": round(syr, 5),
                   "label_fit": "log_sensitivity = %.6f*y_px + %.6f (rms %.4f)" % ylbl_fit,
                   "gridline_residuals": ygrid_res},
        "curve_classification": "by peak wavelength ascending (yellow<magenta<cyan); "
                                "curves overlap in x so vertical order is not used",
        "layers": supports,
    }
    if stitched:
        audit["fragment_stitching"] = {
            "reason": "this datasheet draws each sensitivity curve as many short "
                      "stroked path fragments rather than one polyline",
            "method": "chain fragments sharing an endpoint exactly, then bridge a "
                      "remaining break only where the two facing ends agree in "
                      "slope (<= %.4f logSens/nm) and the linear prediction across "
                      "the gap (<= %.3f logSens over <= %.0f nm); any break failing "
                      "that is left as a null gap, never flat-held or interpolated"
                      % (SLOPE_TOL, PRED_TOL, GAP_MAX_NM),
            "trace": list(stitch_log),
        }

    out = {
        "source": datasheet_label(stock) + ", page 4 bottom-left "
                  "'Spectral-Sensitivity Curves', digitized from the embedded PDF "
                  "path geometry",
        "measurement_note": "sensitivity = log10(1/H) for the exposure H giving "
                            "density 0.2 above D-min; daylight; 1/50 s",
        "wavelength_nm": [int(x) for x in wl],
        "wavelength_note": "1 nm grid over the union support of the three layers; "
                          "each layer is null (JSON null) outside its own support",
        "log_sensitivity": {
            "yellow": log_sens["yellow"],
            "magenta": log_sens["magenta"],
            "cyan": log_sens["cyan"],
        },
        "digitization_audit": audit,
    }
    outp = DATA / "films" / stock["sensitivity_json"]
    json.dump(out, open(outp, "w"), indent=1)

    # ---------- mandatory stdout diagnostics ----------
    print("=== axis calibration residuals (data units) ===")
    print("x-fit RMS %.4f nm    y-fit RMS %.5f logSens" % (sxr, syr))
    print("x gridline device->data residuals %s" % xgrid_res)
    print("y gridline device->data residuals %s" % ygrid_res)
    print("x label cross-check fit: %s" % ("wavelength_nm = %.6f*x + %.6f (rms %.4f)" % xlbl_fit))
    print("y label cross-check fit: %s" % ("log_sensitivity = %.6f*y + %.6f (rms %.4f)" % ylbl_fit))
    print("label cross-check median offset: x %+.3f nm   y %+.4f logSens "
          "(y origin %+.1f, %d gridlines)" % (xlbl_off, ylbl_off, y0val, len(hy)))
    if stitched:
        print("=== fragment stitching ===")
        for line in stitch_log:
            print("  %s" % line)
    print("=== per-layer support / peak ===")
    for name in layer_names:
        s = supports[name]
        print("%-8s support %6.1f-%6.1f nm   peak %6.1f nm   peak logSens %.3f   (%d path pts)"
              % (name, s["support_nm"][0], s["support_nm"][1],
                 s["peak_wavelength_nm"], s["peak_log_sensitivity"], s["n_path_points"]))
        if stitched and s["gaps_left_null_nm"]:
            print("%-8s   measured segments %s; gap(s) left NULL %s"
                  % ("", s["measured_segments_nm"], s["gaps_left_null_nm"]))
    print("union support %d-%d nm (%d samples)" % (lo, hi, len(wl)))
    print("wrote %s" % outp.relative_to(ROOT))


if __name__ == "__main__":
    main()
