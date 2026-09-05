#!/usr/bin/env python3
"""Stock registry shared by the three Portra datasheet digitizers.

The Portra 160 and Portra 400 datasheets are laid out identically -- same page
index, same four vector quadrant charts in the same device-space positions --
so digitizing a second stock is pure parameterization: which PDF, which page,
which output filenames, and which provenance string.

Ektar 100 broke that assumption twice over: its charts sit ~6 pt lower on the
page, and its characteristic chart's logH axis runs -3.0..+2.0 where both
Portras run -4.0..+1.0. Neither shows up as an error, only as wrong numbers, so
the axis ORIGINS are now per-stock registry entries and check_axis_labels()
cross-checks every count-inferred axis against the printed numeric labels.
Run engine/c41/datasheet_forensics.py on a datasheet BEFORE adding it here.

Nothing here touches the digitization algorithms; the axis calibration windows,
curve-selection heuristics and fit bounds stay in the scripts that own them.

The one piece of shared geometry that does live here is frame_boxes(): a chart
frame is drawn either as four long LTLines (Portra 400's characteristic chart)
or as ONE stroked five-point axis-aligned LTCurve rectangle (all four Portra 160
charts, and Portra 400's spectral-sensitivity chart), so both digitizers have to
accept both spellings.

The registry is also the single source of truth for stock display names and data
filenames in the three C-41 ENGINES, which are pure numerics and must not drag in
pdfminer -- so pdfminer is imported lazily, inside the two frame helpers that are
the only things here that need it.
"""
import argparse

# Tolerance for treating two frame corners / two gridline positions as the same
# feature drawn twice. Sized between the largest observed double-draw offset
# (~0.1 pt, Ultra Max 400) and the smallest real gridline spacing on any sheet
# so far (~25 pt, Fujifilm 400's half-decade characteristic ticks).
DEDUPE_TOL_PT = 0.75

# 'shift_bound_nm' is the per-stock peak-shift bound (+/- nm) that
# portra_decompose.py's 9-parameter warp is fitted under. It is per-stock because
# the historical +/-15 was not neutral: every Kodak stock fitted sC at exactly
# +15.0, i.e. all five were CLIPPED by the bound. Releasing them to +/-25 removes
# all bound pinning, and a control that instead released the WIDTH bound buys
# nothing -- so the old bound was an artifact, not a prior.
#
# THERE IS NO KODAK vs FUJIFILM SPLIT. This comment used to claim one, and it was
# wrong. Measured 2026-08-03 across all five Fujifilm stocks:
#   Fujicolor 100      sC +7.13, not clipped   -- bound never binds
#   Pro 400H           sC +14.53, not clipped  -- bound never binds
#   Superia Prem 400   sC +15.00 -> +19.90 when released; RMSE 0.0229 -> 0.0196,
#                      FWHM stays healthy at 82/86/87 nm, collinearity flat.
#                      That is the KODAK pattern: a clipped artifact.
#   Fujifilm 400/200   sC +15.00 -> pins the NEW +/-25 bound too, cyan FWHM
#                      COLLAPSES 69 -> 60 nm against the 74-78 nm fleet band, and
#                      C-Y collinearity rises 0.246 -> 0.284. Degenerate.
#
# DECISION 2026-08-03: the bound is now +/-25 on EVERY stock, with NO exception.
# It was briefly 15 for Fujifilm 400/200. Three reasons the exception was dropped:
#   1. A per-stock bound fits different stocks under DIFFERENT PRIORS, which
#      confounds every inter-stock dye comparison -- the same class of error as
#      basis sensitivity, and this repo's comparisons are its main output.
#   2. +/-25 is the physically justified value: Kodak stocks want up to 23.9 nm,
#      and spektrafilm independently puts C-41 cyan 10-15 nm off Vision3's.
#      +/-15 was never justified; it was the historical default.
#   3. Fujifilm 400/200 PIN +/-25 as well (sC = +25.00 exactly). Under a bound we
#      can justify, that pin is an honest DIAGNOSTIC -- "this stock's published
#      data cannot be described by the model within physically plausible shifts".
#      Under +/-15 the same pin was ambiguous, and using the tighter bound to make
#      the fit look better was papering over the finding.
# Cost, borne only by those two stocks: node-solve residual 0.0847 -> 0.1800
# (26.1% -> 37.6% of nodes over tolerance), Status M cube moves 27 Cineon code
# values in the in-gamut core, cyan FWHM 69 -> 60 nm against the fleet's 74-89 nm.
# Accepted deliberately: their dye chart is SHARED between the two datasheets
# (byte-identical Bezier control points) so it cannot describe two films of
# different speed. Neither cube was trustworthy at either bound; the honest move
# is to leave the diagnostic visible rather than damp it.
# TREAT THE FUJIFILM 400/200 DYE OUTPUT AS UNTRUSTWORTHY and keep it out of
# inter-stock dye comparisons.
#
# (Three of five Fujifilm stocks fit the Vision3 basis as well as Kodak stocks do
# -- Pro 400H 0.0109, Superia 0.0196, Fujicolor 100 0.0250 against the Kodak band
# 0.0106-0.0139. Any claim that "Fujifilm chemistry does not suit this basis" is
# refuted by its own fleet. Separately, the user reports Fujifilm 200/400 are
# Kodak-MANUFACTURED under contract; that is external information, nothing here
# confirms it, and manufacture would not imply shared dye design in any case --
# so it must NOT be used to group these stocks with Kodak ones.)
# The WIDTH bound stays 0.85-1.15 on every stock.
STOCKS = {
    "portra400": {
        "display_name": "Portra 400",
        # The RA-4 paper a user would actually print this brand on. It is a
        # market pairing -- what the two houses sold as a system, and what a
        # lab would have loaded -- rather than any claim about which factory
        # coated the film.
        "print_paper": "endura",
        # prefix shared by this stock's data JSONs and its build artifacts
        "file_prefix": "Portra400",
        "speed_key": "400",
        "pdf_filename": "Portra 400.pdf",
        "page": 3,
        # provenance: publication number + revision date, read off the PDF itself
        "datasheet_code": "E-4050",
        "datasheet_date": "Jan 2025",
        "curves_json": "Portra400_datasheet_curves.json",
        "sensitivity_json": "Portra400_spectral_sensitivity.json",
        "dye_density_json": "Portra400_dye_density.json",
        # bottom-left spectral-sensitivity plot frame, device space. Kept as the
        # historical hand-read constants rather than derived from the page: the
        # derived floats (76.21, 297.44, 276.73, 448.94) differ in the last digit
        # and would perturb this stock's serialized audit block.
        "sens_frame": [76.2, 297.4, 276.7, 448.9],
        "sens_y_origin": 0.0,
        # top-left characteristic-chart data-curve selection window (device
        # space): stroked curves must satisfy x0 > w[0], x1 < w[1], y0 > w[2],
        # y1 < w[3]. Per stock rather than derived, for the same reason.
        "char_curve_window": [81.0, 266.0, 500.0, 690.0],
        # x window for the top-right spectral-dye-density y-tick residual check
        # (short horizontal ticks hanging off the frame's left edge).
        "spec_ygrid_x_window": [356.0, 362.0],
        # characteristic-chart axis ORIGINS: the data value carried by the
        # LOWEST gridline on each axis. Every other tick is origin + n*step, so
        # a wrong origin shifts the whole axis without changing any count.
        # Ektar 100's logH axis runs -3.0..+2.0 where both Portras run
        # -4.0..+1.0, so this cannot be a constant. The density origin is 0.0 on
        # all three stocks and is per-stock anyway -- "every stock so far agrees"
        # is precisely the assumption that has already broken twice.
        "char_x_origin": -4.0,
        "char_n_x": 6, "char_n_y": 5,
        "char_y_origin": 0.0,
        # spectral-dye-density numeric label windows, as label_ticks()'s
        # (lo, hi, olo, ohi). Per stock rather than derived from the frame box:
        # frame_boxes() does not find Portra 400's spectral frame at all (it is
        # drawn neither as four long LTLines nor as one stroked rect), so on the
        # historical stock there is nothing to derive from.
        "spec_x_label_band": [340.0, 560.0, 488.0, 499.0],
        "spec_y_label_band": [500.0, 700.0, 330.0, 362.0],
        "shift_bound_nm": 25.0,
    },
    "portra160": {
        "display_name": "Portra 160",
        "print_paper": "endura",
        "file_prefix": "Portra160",
        "speed_key": "160",
        "pdf_filename": "Portra 160.pdf",
        "page": 3,
        "datasheet_code": "E-4051",
        "datasheet_date": "Jan 2025",
        "curves_json": "Portra160_datasheet_curves.json",
        "sensitivity_json": "Portra160_spectral_sensitivity.json",
        "dye_density_json": "Portra160_dye_density.json",
        # measured off page 4: every Portra 160 frame is a stroked LTCurve rect
        "sens_frame": [73.75, 292.43, 274.23, 444.02],
        "sens_y_origin": -1.0,
        # frame is x 81.45-266.01, y 505.40-689.88; widen just enough for data
        # curves that start and end exactly on the left/right frame edges
        "char_curve_window": [81.0, 266.6, 502.0, 691.0],
        # frame left edge is x 355.13, so the ticks start ~1 pt left of Portra
        # 400's; shift the window to match
        "spec_ygrid_x_window": [354.5, 361.0],
        "char_x_origin": -4.0,
        "char_n_x": 6, "char_n_y": 5,
        "char_y_origin": 0.0,
        "spec_x_label_band": [340.0, 560.0, 488.0, 499.0],
        "spec_y_label_band": [500.0, 700.0, 330.0, 362.0],
        "shift_bound_nm": 25.0,
    },
    "ektar100": {
        "display_name": "Ektar 100",
        "print_paper": "endura",
        "file_prefix": "Ektar100",
        "speed_key": "100",
        "pdf_filename": "Ektar 100.pdf",
        "page": 3,
        # "January 2025 * E-4046" / "KODAK Publication No. E-4046", read off the
        # PDF itself -- NOT the E-4050/E-4051 pair the two Portras share.
        "datasheet_code": "E-4046",
        "datasheet_date": "Jan 2025",
        "curves_json": "Ektar100_datasheet_curves.json",
        "sensitivity_json": "Ektar100_spectral_sensitivity.json",
        "dye_density_json": "Ektar100_dye_density.json",
        # Measured off page 4. Every Ektar frame is a stroked LTCurve rect, and
        # all four sit ~6 pt LOWER on the page than the Portras' -- which is why
        # the characteristic chart's device windows in portra_digitize.py are now
        # derived from the frame box instead of hard-coded.
        #   characteristic (top-left)  x  81.19-265.70  y 499.59-684.08
        #   spectral-dye   (top-right) x 357.45-541.78  y 501.61-685.98
        #   spectral-sens  (bot-left)  x  74.19-274.65  y 283.96-435.44
        #   MTF            (bot-right) x 347.58-550.07  y 280.77-433.82 (ignored)
        "sens_frame": [74.19, 283.96, 274.65, 435.44],
        # log-sensitivity axis runs 0.0..3.0 -- FOUR gridlines, where both
        # Portras have five. Nothing may assume the tick count either.
        "sens_y_origin": 0.0,
        # frame is x 81.19-265.70, y 499.59-684.08; same padding as Portra 160's
        "char_curve_window": [80.7, 266.3, 496.2, 685.2],
        # frame left edge is x 357.45 and its y ticks hang off it at x 357.52
        "spec_ygrid_x_window": [356.5, 363.0],
        # THE trap on this stock: logH runs -3.0..+2.0, not -4.0..+1.0. The tick
        # COUNT is 6 either way, so the existing count guard is blind to it.
        "char_x_origin": -3.0,
        "char_n_x": 6, "char_n_y": 5,
        "char_y_origin": 0.0,
        # charts sit ~6 pt lower, so the Portras' spectral label bands miss
        "spec_x_label_band": [340.0, 560.0, 486.0, 497.0],
        "spec_y_label_band": [498.0, 700.0, 330.0, 362.0],
        "shift_bound_nm": 25.0,
    },
    "gold200": {
        "display_name": "Gold 200",
        "print_paper": "endura",
        "speed_key": "200",
        "pdf_filename": "Gold 200.pdf",
        "page": 3,
        "datasheet_code": "E-7022",
        "datasheet_date": "not stated",
        "file_prefix": "Gold200",
        "curves_json": "Gold200_datasheet_curves.json",
        "sensitivity_json": "Gold200_spectral_sensitivity.json",
        "dye_density_json": "Gold200_dye_density.json",
        # The spectral-sensitivity chart IS present. Its frame is an L-shaped
        # axis pair (3-point path: left edge + bottom edge, no top/right
        # border), which an earlier rect detector missed entirely.
        "sens_frame": [74.87, 322.60, 275.39, 474.11],
        # Unlike the other three stocks, this sheet draws its three sensitivity
        # curves as ~64 short stroked fragments (4-7 path ops each) rather than
        # three continuous polylines, so they must be chained end-to-end and
        # continuity-bridged before tracing. See stitch_sens_fragments() in
        # portra_digitize_sens.py. Set ONLY for this stock: the flag gates the
        # whole alternate collection path, so the other four stocks keep their
        # byte-identical historical output.
        "sens_stitch_fragments": True,
        "sens_y_origin": 0.0,          # axis runs 0.0..4.0, five gridlines
                                       # (Portra 160 runs -1.0..3.0; Ektar 0.0..3.0 with four)
        # characteristic chart: x runs -3.0..+1.0 with FIVE gridlines (both
        # Portras have six spanning -4.0..+1.0; Ektar has six spanning
        # -3.0..+2.0). Third distinct convention in four datasheets.
        "char_x_origin": -3.0,
        "char_y_origin": 0.0,
        "char_n_x": 5, "char_n_y": 5,
        "char_curve_window": [81.0, 267.0, 536.0, 721.0],
        "spec_ygrid_x_window": [356.0, 363.0],
        # spectral chart sits ~48 pt HIGHER on this sheet than on the other
        # three (frame y 552.25-736.60), so its label bands shift with it.
        "spec_x_label_band": [340.0, 560.0, 536.0, 547.0],
        "spec_y_label_band": [546.0, 742.0, 330.0, 362.0],
        # x-axis tick labels lose their minus signs in text extraction on this
        # sheet ('3.02.01.00.01.0'), so the label cross-check cannot validate the
        # x axis here. The dye DECOMPOSITION does not read the characteristic
        # chart at all -- it uses only the spectral chart, whose labels are clean
        # -- so the basis comparison is unaffected by this.
        "char_x_labels_unreliable": True,
        "shift_bound_nm": 25.0,
    },
    "ultramax400": {
        "display_name": "Ultra Max 400",
        "print_paper": "endura",
        "file_prefix": "Ultramax400",
        "speed_key": "400",
        "pdf_filename": "Ultramax 400.pdf",
        "page": 3,
        "datasheet_code": "E-7023",
        "datasheet_date": "Feb 2016",
        "curves_json": "Ultramax400_datasheet_curves.json",
        "sensitivity_json": "Ultramax400_spectral_sensitivity.json",
        "dye_density_json": "Ultramax400_dye_density.json",
        # Kodak Alaris consumer sheet. Layout follows the Portra template but
        # every chart sits lower on the page than Portra 400's, so all four
        # device windows are this stock's own.
        "sens_frame": [76.6, 269.4, 277.6, 421.0],
        "sens_y_origin": 0.0,          # 0.0..4.0, five gridlines
        "char_x_origin": -4.0,
        "char_y_origin": 0.0,
        "char_n_x": 6, "char_n_y": 5,
        "char_curve_window": [81.0, 266.0, 494.0, 680.0],
        "spec_ygrid_x_window": [356.0, 362.0],
        "spec_x_label_band": [340.0, 560.0, 479.0, 491.0],
        "spec_y_label_band": [490.0, 682.0, 331.0, 357.0],
        # TRAP unique to this sheet so far: the spectral-dye-density chart is
        # drawn TWICE, offset ~0.1 pt, so every frame edge and gridline appears
        # doubled (8 verticals for 7 ticks, 9 horizontals for 6). Handled by
        # dedupe_positions() / the frame_boxes() corner dedup, not here.
        "shift_bound_nm": 25.0,
    },
    "proimage100": {
        "display_name": "Pro Image 100",
        "print_paper": "endura",
        "speed_key": "100",
        "pdf_filename": "Pro Image 100.pdf",
        "page": 2,                     # printed page 3. The four earlier Kodak
                                       # sheets put their charts on index 3.
        "datasheet_code": "E-4L",
        "datasheet_date": "July 1997",
        "file_prefix": "ProImage100",
        "curves_json": "ProImage100_datasheet_curves.json",
        "sensitivity_json": "ProImage100_spectral_sensitivity.json",
        "dye_density_json": "ProImage100_dye_density.json",
        # LAYOUT IS MIRRORED relative to the other four Kodak sheets: spectral
        # SENSITIVITY is top-right and spectral DYE DENSITY is bottom-centre,
        # where Gold 200 has dye density top-right and sensitivity lower-left.
        # The historical spec locator (447, 598) lands INSIDE this sheet's
        # sensitivity frame, so both locators are named explicitly here.
        "char_frame_near": (187.0, 624.0),
        "spec_frame_near": (317.0, 369.0),
        "sens_frame": [362.76, 564.81, 563.07, 716.27],
        "sens_y_origin": 0.0,          # 0.0..4.0, five gridlines
        # characteristic chart: x runs -3.0..+1.0 on FIVE labelled ticks, as on
        # Gold 200. Unlike Gold 200, the plot box does not start at a tick -- its
        # left edge sits 16.2 pt left of -3.0 where a decade is 46.1 pt, giving
        # SIX verticals for five ticks. char_vx_window drops that edge.
        "char_x_origin": -3.0,
        "char_y_origin": 0.0,
        "char_n_x": 5, "char_n_y": 5,
        "char_vx_window": [95.0, 300.0],
        "char_curve_window": [86.0, 288.0, 533.0, 718.0],
        # x tick labels are drawn with the minus sign as a separate overbar
        # rule, so extraction yields '3.0 2.0 1.0 0.0 1.0' and the sign is lost.
        # Confirmed by geometry: three 2.91 pt rules at y 526.19 sit above the
        # first three labels and none above the last two.
        "char_x_labels_unreliable": True,
        "spec_ygrid_x_window": [224.0, 231.0],
        "spec_x_label_band": [205.0, 429.0, 263.5, 274.0],
        "spec_y_label_band": [271.0, 468.0, 199.0, 224.6],
        "shift_bound_nm": 25.0,
    },
    "portra800": {
        "display_name": "Portra 800",
        "print_paper": "endura",
        "file_prefix": "Portra800",
        "speed_key": "800",
        "pdf_filename": "Portra 800.pdf",
        "page": 3,
        # FIRST sheet to split its charts across pages: characteristic and
        # spectral sensitivity are on index 3, but spectral DYE DENSITY is alone
        # on index 4 (printed page 5). Without this key the historical
        # spec_frame_near default (447, 598) lands INSIDE the page-3 "EI 3200
        # (Push 2)" characteristic chart and would digitize push curves as dye
        # density without raising anything.
        "spec_page": 4,
        "datasheet_code": "E-4040",
        "datasheet_date": "Jan 2025",   # "Revised 1-25", (c) 2025 Kodak Alaris
        "curves_json": "Portra800_datasheet_curves.json",
        "sensitivity_json": "Portra800_spectral_sensitivity.json",
        "dye_density_json": "Portra800_dye_density.json",
        # Page 3 carries THREE characteristic charts -- EI 800 top-left, EI 1600
        # (Push 1) bottom-left, EI 3200 (Push 2) top-right. Only the standard
        # EI 800 chart is digitized; the frame locator and curve window below
        # select the top-left quadrant and nothing else.
        # sens chart is the LOWER top-right frame (x 350.17-550.94,
        # y 326.63-478.33), wavelength 250..750 over eleven gridlines,
        # log sensitivity 0.0..4.0 over five.
        "sens_frame": [350.17, 326.63, 550.94, 478.33],
        "sens_y_origin": 0.0,
        # EI 800 chart frame: x 81.64-266.17, y 533.11-717.53
        "char_curve_window": [81.0, 266.7, 530.0, 720.0],
        "char_x_origin": -4.0,
        "char_y_origin": 0.0,
        "char_n_x": 6, "char_n_y": 5,
        # ARTWORK TYPO on the EI 800 chart, confirmed by eye on the 300 dpi
        # render: the printed x labels read -4.0, -2.0, -3.0, -1.0, 0.0, 1.0 --
        # Kodak swapped the -2.0 and -3.0 glyphs. The gridlines are uniform and
        # the four correct labels anchor the axis at -4.0..+1.0, so the
        # median-based label cross-check survives the swapped pair (4 of 6
        # labels agree with the median); no skip flag is needed.
        # spectral-dye-density chart, page index 4 top-left: frame x 81.09-
        # 265.44, y 505.88-690.23; x 400..700 nm labelled only at the 100s,
        # y 0.0..2.5 in 0.5 steps (first sheet not to run 0..4+).
        "spec_frame_near": (173.0, 598.0),
        "spec_ygrid_x_window": [80.0, 87.0],
        "spec_x_label_band": [40.0, 300.0, 491.0, 503.0],
        "spec_y_label_band": [500.0, 695.0, 55.0, 81.0],
        "shift_bound_nm": 25.0,
    },
    "fujifilm400": {
        "display_name": "Fujifilm 400",
        "print_paper": "fujiprolaser",
        "file_prefix": "Fujifilm400",
        "speed_key": "400",
        "pdf_filename": "Fujifilm 400.pdf",
        "page": 5,                     # NOT 3 -- this sheet's charts are on p.6
        "datasheet_code": "AF3-0262E",
        "datasheet_date": "2023",
        "curves_json": "Fujifilm400_datasheet_curves.json",
        "sensitivity_json": "Fujifilm400_spectral_sensitivity.json",
        "dye_density_json": "Fujifilm400_dye_density.json",
        # A Fuji-template sheet, not a Kodak one: half-decade gridlines on BOTH
        # characteristic axes, a dye-density plot box wider than its labelled
        # wavelength range, a purely RELATIVE log-sensitivity axis, and data
        # curves drawn as cubic Beziers rather than dense polylines. None of the
        # Kodak digitizers' assumptions survive that, so it has its own script
        # and deliberately carries NO char_*/spec_*/sens_* geometry keys.
        "digitizer": "fuji_digitize.py",
        "shift_bound_nm": 25.0,
    },
    "fujifilm200": {
        "display_name": "Fujifilm 200",
        "print_paper": "fujiprolaser",
        "file_prefix": "Fujifilm200",
        "speed_key": "200",
        "pdf_filename": "Fujifilm 200.pdf",
        "page": 4,                     # NOT 5 -- one page EARLIER than Fuji 400
        "datasheet_code": "AF3-0261E",
        "datasheet_date": "2023",
        "curves_json": "Fujifilm200_datasheet_curves.json",
        "sensitivity_json": "Fujifilm200_spectral_sensitivity.json",
        "dye_density_json": "Fujifilm200_dye_density.json",
        # Same Fuji template as Fujifilm 400 (consecutive publications), so the
        # same script and the same caveats -- but NOT the same geometry: the
        # characteristic frame sits ~4.4 pt lower and the sensitivity scale bar
        # is 65.80 pt/decade, not 65.90. Carries no char_*/spec_*/sens_* keys.
        "digitizer": "fuji_digitize.py",
        "shift_bound_nm": 25.0,
    },
    "fujicolor100": {
        "display_name": "Fujicolor 100",
        "print_paper": "fujiprolaser",
        "file_prefix": "Fujicolor100",
        "speed_key": "100",
        "pdf_filename": "Fujicolor 100 [JP].pdf",
        "page": 4,
        "datasheet_code": "013AR0317A",
        "datasheet_date": "2007",
        "curves_json": "Fujicolor100_datasheet_curves.json",
        "sensitivity_json": "Fujicolor100_spectral_sensitivity.json",
        "dye_density_json": "Fujicolor100_dye_density.json",
        # Japanese-market sheet on the same FAMILY of Fuji template as Fujifilm
        # 400/200, but three things differ and all three are fatal if copied:
        # the page is A4 (595x842) not Letter; the bottom quadrants are MIRRORED
        # (dye density bottom-RIGHT, MTF bottom-LEFT); and the characteristic x
        # axis runs -3.5..+1.0, not -4.0..+0.5. Its printed x labels also lose
        # their minus signs in extraction, exactly as Gold 200's do, so the
        # label cross-check is skipped and flagged. Carries no
        # char_*/spec_*/sens_* keys -- geometry lives in fuji_digitize.SHEETS.
        "digitizer": "fuji_digitize.py",
        "shift_bound_nm": 25.0,
    },
    "superiapremium400": {
        "display_name": "Superia Premium 400",
        "print_paper": "fujiprolaser",
        "file_prefix": "SuperiaPremium400",
        "speed_key": "400",
        "pdf_filename": "Superia Premium 400 [JP].pdf",
        "page": 4,
        "datasheet_code": "013AR0324A",
        "datasheet_date": "2009",
        "curves_json": "SuperiaPremium400_datasheet_curves.json",
        "sensitivity_json": "SuperiaPremium400_spectral_sensitivity.json",
        "dye_density_json": "SuperiaPremium400_dye_density.json",
        # Same Japanese-market template as Fujicolor 100 (A4, mirrored bottom
        # quadrants, 57.19 pt/decade scale bar) but NOT the same geometry, and
        # unlike Fujicolor 100 its characteristic x axis is the usual
        # -4.0..+0.5 AND its printed minus signs survive extraction, so the
        # label cross-check stays enabled.
        "digitizer": "fuji_digitize.py",
        "shift_bound_nm": 25.0,
    },
    "pro400h": {
        "display_name": "Fujifilm Pro 400H",
        "print_paper": "fujiprolaser",
        "file_prefix": "Pro400H",
        "speed_key": "400",
        "pdf_filename": "Fujifilm Pro 400H.pdf",
        "page": 7,
        "datasheet_code": "AF3-176E",
        # The sheet prints no publication date, only "Ref. No. AF3-176E
        # (EIGI-05.1-FG(HB)- 4-1-) Printed in Japan". Not guessed.
        "datasheet_date": "n.d.",
        "curves_json": "Pro400H_datasheet_curves.json",
        "dye_density_json": "Pro400H_dye_density.json",
        # NO 'sensitivity_json' key, and this is not an oversight -- see
        # 'sensitivity_absent' below. Anything reading sensitivity data off the
        # registry must .get() it, not index it.
        #
        # THIS STOCK CARRIES NO SPECTRAL SENSITIVITY DATA, DELIBERATELY. Its
        # sensitivity chart draws FOUR curves: a dashed "Cyan Sensitive Layer"
        # sitting between the green- and red-sensitive layers. Every digitizer
        # in this repo classifies exactly THREE layers by ascending peak
        # wavelength, and how a fourth sensitivity layer should feed a
        # 3-channel exposure model is an open modelling question, not a
        # digitization one. So the chart is not digitized, no
        # Pro400H_spectral_sensitivity.json exists, and pro400h is deliberately
        # NOT registered in c41_scene_engine.py (which requires sensitivity) --
        # a clean KeyError there is the intended behaviour. Do not "fix" this by
        # discarding the fourth curve.
        "sensitivity_absent": True,
        # A further first: datasheet_forensics.py finds NO extractable numeric
        # labels on ANY axis of ANY frame on this sheet -- not merely the
        # missing minus signs of Fujicolor 100 / Gold 200. Both axes of both
        # digitized charts are therefore flagged unreliable and the label
        # cross-check is skipped everywhere; the axis values come from a 300 dpi
        # rendered-page reading, and datasheet_overlay.py's ink-hit test is this
        # stock's ONLY validator. Geometry lives in fuji_digitize.SHEETS.
        "digitizer": "fuji_digitize.py",
        "shift_bound_nm": 25.0,
    },
}

DEFAULT_STOCK = "portra400"


def datasheet_label(stock):
    """'Kodak Portra 400 datasheet E-4050 (Jan 2025)'."""
    return "Kodak %s datasheet %s (%s)" % (
        stock["display_name"], stock["datasheet_code"], stock["datasheet_date"])


# ---------- axis self-check ----------
# A numeric tick label's reported position is the MEAN of its glyphs' x0 (or of
# their y centres), which is systematically a couple of points off the tick it
# annotates: mean-of-x0 sits about half a glyph left of the string's centre, and
# a leading minus sign drags it further left still. On the characteristic
# chart's logH axis that skew is worth ~0.09 decades -- larger than any sane
# absolute tolerance -- so the allowance is the requested data-unit tolerance
# PLUS this device-space skew converted through the axis slope. The errors this
# guard exists to catch are a whole step (1.0 decade, 1.0 D, 50 nm), one to two
# orders of magnitude above the allowance.
LABEL_CENTROID_SKEW_PT = 3.5


def _median(vals):
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def check_axis_labels(stock, chart, axis, slope, intercept, labels, tol=0.05):
    """Cross-check a COUNT-inferred axis calibration against its printed labels.

    Gridline-based calibration assigns tick values by counting gridlines up from
    an assumed origin, so a missed gridline or a wrong origin produces plausible
    WRONG NUMBERS rather than an error -- and evenly spaced gridlines fit any
    origin with zero residual, so the fit's own RMS cannot see it. The printed
    numeric labels are the only independent statement of what the axis actually
    reads. Evaluate the fit at each label's device position and compare.

    The comparison is on the MEDIAN offset rather than each label taken alone,
    for one concrete reason: Portra 160's spectral-sensitivity "2.0" label
    extracts as the string "20.0" (its decimal point clusters elsewhere), and a
    single mis-extracted glyph run must not be able to veto a correct axis. A
    wrong origin or a missed gridline shifts EVERY label together, which moves
    the median; one bad label does not. A majority of labels must also agree
    with that median, so garbage cannot outvote the truth.

    Raises SystemExit naming the stock, the chart, the axis, the offending
    device position, the labelled value, the predicted value and the implied
    offset. Returns the median offset (data units) when the axis checks out.
    """
    pts = [(float(p), float(v), float(p) * slope + intercept) for p, v in labels]
    if len(pts) < 2:
        raise SystemExit(
            "%s: %s chart %s-axis -- only %d numeric axis label(s) found, so the "
            "count-inferred tick values cannot be cross-checked. Refusing to "
            "write. The label search band probably misses on this datasheet; run "
            "engine/c41/datasheet_forensics.py on it to see where the labels are."
            % (stock["display_name"], chart, axis, len(pts)))
    allow = tol + abs(slope) * LABEL_CENTROID_SKEW_PT
    med = _median([pred - v for _, v, pred in pts])
    agree = [t for t in pts if abs((t[2] - t[1]) - med) <= allow]
    if abs(med) <= allow and 2 * len(agree) >= len(pts):
        return med
    pos, val, pred = max(pts, key=lambda t: abs(t[2] - t[1]))
    raise SystemExit(
        "%s: %s chart %s-axis calibration disagrees with the printed labels. "
        "The gridline fit predicts %.4f at device position %.2f, which is "
        "labelled %.4f (offset %+.4f); median offset across all %d labels is "
        "%+.4f, tolerance %.4f. The tick values are inferred from the tick "
        "COUNT, so this is what a wrong axis ORIGIN or a missed gridline looks "
        "like -- the numbers would be plausible and wrong. Refusing to write. "
        "Check this stock's origin in portra_stocks.py against "
        "engine/c41/datasheet_forensics.py."
        % (stock["display_name"], chart, axis, pred, pos, val, pred - val,
           len(pts), med, allow))


def _path_points(curve):
    """The (x, y) vertices of an LTCurve's original_path, in order."""
    return [tuple(p) for seg in curve.original_path for p in seg[1:]
            if isinstance(p, (tuple, list)) and len(p) == 2]


def _rect_boxes_from_curves(els, min_w, min_h, tol):
    """Frames drawn as ONE stroked, non-filled, axis-aligned rectangle path.

    Such a path has five segments but only FOUR coordinate-bearing ones: the
    Portra 160 frames close with a bare ('h',) rather than repeating the start
    point, so _path_points yields 4. Accept either spelling.
    """
    from pdfminer.layout import LTCurve

    out = []
    for c in els:
        if not isinstance(c, LTCurve) or not c.stroke or c.fill:
            continue
        pts = _path_points(c)
        if len(pts) == 3:
            # L-shaped AXIS PAIR: left edge + bottom edge only, no top/right
            # border (Gold 200's spectral-sensitivity chart). The bbox is still
            # the plot rectangle because each arm spans its full axis. Accept
            # only a true perpendicular L, never an arbitrary 3-point path.
            (ax, ay), (bx, by), (cx_, cy) = pts
            v1 = abs(ax - bx) < tol and abs(ay - by) > min_h
            h1 = abs(ay - by) < tol and abs(ax - bx) > min_w
            v2 = abs(bx - cx_) < tol and abs(by - cy) > min_h
            h2 = abs(by - cy) < tol and abs(bx - cx_) > min_w
            if not ((v1 and h2) or (h1 and v2)):
                continue
        elif len(pts) not in (4, 5):
            continue
        x0, y0, x1, y1 = c.bbox
        if (x1 - x0) <= min_w or (y1 - y0) <= min_h:
            continue
        # axis-aligned: every vertex sits on a corner of the bbox
        if any(min(abs(px - x0), abs(px - x1)) > tol
               or min(abs(py - y0), abs(py - y1)) > tol for px, py in pts):
            continue
        out.append((x0, y0, x1, y1))
    return out


def _rect_boxes_from_lines(els, min_w, min_h, tol):
    """Frames drawn as four long axis-aligned LTLines that close on each other.

    The box is built from the raw line coordinates the digitizers already read
    (vertical lines' x0, horizontal lines' y0) so that unioning a frame edge
    into an existing rounded gridline set is exactly idempotent.
    """
    from pdfminer.layout import LTLine

    vert = [l for l in els if isinstance(l, LTLine)
            and abs(l.x1 - l.x0) < tol and abs(l.y1 - l.y0) > min_h]
    horz = [l for l in els if isinstance(l, LTLine)
            and abs(l.y1 - l.y0) < tol and abs(l.x1 - l.x0) > min_w]
    out = []
    for i, a in enumerate(vert):
        for b in vert[i + 1:]:
            xa, xb = sorted((a.x0, b.x0))
            if xb - xa <= min_w:
                continue
            for j, c in enumerate(horz):
                for d in horz[j + 1:]:
                    ya, yb = sorted((c.y0, d.y0))
                    if yb - ya <= min_h:
                        continue
                    # the four lines must close: verticals span [ya, yb] and
                    # horizontals span [xa, xb], each to within tol
                    spans_y = all(abs(min(l.y0, l.y1) - ya) < tol
                                  and abs(max(l.y0, l.y1) - yb) < tol
                                  for l in (a, b))
                    spans_x = all(abs(min(l.x0, l.x1) - xa) < tol
                                  and abs(max(l.x0, l.x1) - xb) < tol
                                  for l in (c, d))
                    if spans_x and spans_y:
                        out.append((xa, ya, xb, yb))
    return out


def frame_boxes(els, min_w=80.0, min_h=80.0, tol=1.0):
    """Axis-aligned chart-frame boxes on a page, as (x0, y0, x1, y1).

    The union of the two ways a frame is drawn -- a single stroked five-point
    LTCurve rectangle, or four long LTLines that close on each other. A frame
    found both ways is reported once.

    Dedup tolerance is DEDUPE_TOL_PT, not the 0.1 pt rounding this used to do.
    Ultra Max 400 draws its spectral-dye-density chart TWICE, offset by ~0.1 pt,
    which straddles a round(v, 1) key: the two copies landed on different keys
    and survived as two frame boxes with every gridline doubled. Two genuinely
    distinct charts never agree on all four corners to within a point.
    """
    boxes = (_rect_boxes_from_curves(els, min_w, min_h, tol)
             + _rect_boxes_from_lines(els, min_w, min_h, tol))
    out = []
    for b in boxes:
        if any(all(abs(b[i] - k[i]) <= DEDUPE_TOL_PT for i in range(4))
               for k in out):
            continue
        out.append(b)
    return out


def dedupe_positions(vals, tol=None):
    """Collapse near-coincident gridline positions to their mean.

    Returns a sorted list. Runs of positions closer than `tol` (default
    DEDUPE_TOL_PT) collapse to one entry at the run's mean.

    This exists because tick VALUES are inferred from tick COUNT: a chart drawn
    twice reports 8 verticals where it has 7 ticks, and the count-based
    assignment then walks off the end of the axis. Real gridlines on these
    sheets sit ~25 pt apart at the closest, so a sub-point tolerance cannot
    merge two real ticks.
    """
    if tol is None:
        tol = DEDUPE_TOL_PT
    out = []
    for v in sorted(vals):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(run) / len(run) for run in out]


def frame_box_near(boxes, x, y, max_dist=150.0):
    """Pick the frame box containing (x, y), else the one whose centre is
    within max_dist of it; None if neither exists.

    (x, y) is a point comfortably inside the quadrant of interest, which is how
    the digitizers name a chart without hard-coding its exact extent. The
    max_dist cutoff keeps a missing frame from silently resolving to a
    neighbouring quadrant's."""
    inside = [b for b in boxes if b[0] <= x <= b[2] and b[1] <= y <= b[3]]
    pool = inside or list(boxes)
    if not pool:
        return None
    best = min(pool, key=lambda b: ((b[0] + b[2]) / 2 - x) ** 2
                                   + ((b[1] + b[3]) / 2 - y) ** 2)
    if best in inside:
        return best
    d2 = ((best[0] + best[2]) / 2 - x) ** 2 + ((best[1] + best[3]) / 2 - y) ** 2
    return best if d2 <= max_dist ** 2 else None


def parse_stock(description, digitizer=None):
    """Parse --stock off the command line and return its registry entry.

    `digitizer` is the basename of the calling script. A stock whose registry
    entry names a DIFFERENT digitizer is refused by name here, so a Fuji-template
    sheet asked of a Kodak-template script fails with a sentence instead of a
    KeyError on whichever geometry key happens to be read first.
    """
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--stock", choices=sorted(STOCKS), default=DEFAULT_STOCK,
                    help="film stock to digitize (default: %s)" % DEFAULT_STOCK)
    name = ap.parse_args().stock
    stock = STOCKS[name]
    want = stock.get("digitizer")
    if digitizer is not None and want is not None and want != digitizer:
        raise SystemExit(
            "%s: %s uses a different datasheet template and is digitized by "
            "engine/c41/%s, not %s. Run:\n  python3 engine/c41/%s"
            % (name, stock["display_name"], want, digitizer, want))
    return stock
