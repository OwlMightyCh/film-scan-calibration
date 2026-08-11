#!/usr/bin/env python3
"""Replot a digitized PAPER JSON back onto its own datasheet chart. Read-only.

The film side has had this check since 2026-07-28 (engine/c41/datasheet_overlay.py)
and it is what caught the Vision3 basis error. The papers never had it: they were
traced before the routine existed, and nothing has since verified that the
numbers land on the printed ink.

Same principle -- drive off each JSON's own `digitization_audit.*.device_to_data`
strings, so no cooperation is needed from the digitizer that wrote them. Reports
ink-hit per curve, which is the only check that validates frame detection, axis
ORIGIN, axis STEP and curve assignment simultaneously.

Crystal Archive is excluded: its maps are in raster row/col space, not the
vector x_px/y_px the other two use, and it carries no H&D so it drives no cube.

Run:  python3 engine/c41/paper_overlay.py
"""
import json, re, sys
from pathlib import Path
import numpy as np
import fitz

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "c41"))
from datasheet_overlay import ink_hit                      # noqa: E402

_AFF = re.compile(r"=\s*(-?[\d.eE+-]+)\s*\*\s*[xy]_px\s*\+\s*(-?[\d.eE+-]+)")
PAPERS = {
    "EnduraPremier_paper.json": ("Kodak Endura Premier.pdf", "Endura Premier"),
    "FujiProLaserTypeII_paper.json": ("Fujicolor Professional Paper Pro Laser Type II.pdf",
                                      "Fuji Pro Laser TYPE II"),
}
CHARTS = {"characteristic_curves": ("hd", "logE", "statusA_density"),
          "spectral_sensitivity": ("sensitivity", "wavelength_nm", "log_sensitivity"),
          "spectral_dye_density": ("dye", "wavelength_nm", "density")}
COL = {"cyan": "#00aacc", "magenta": "#cc00aa", "yellow": "#ccaa00"}


def aff(b):
    m = _AFF.search(b.get("device_to_data", "")) if isinstance(b, dict) else None
    return (float(m.group(1)), float(m.group(2))) if m else None


def main(dpi=170):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = ROOT / "builds" / "_forensics"; out.mkdir(parents=True, exist_ok=True)
    for fn, (pdfname, label) in PAPERS.items():
        d = json.load(open(ROOT / "data" / "papers" / fn))
        au = d["digitization_audit"]
        doc = fitz.open(ROOT / "paper_datasheet" / pdfname)
        print("== %s" % label)
        bypage = {}
        for chart, blk in au.items():
            if chart not in CHARTS or not isinstance(blk, dict): continue
            bypage.setdefault(blk.get("page_index"), []).append((chart, blk))
        for pg, items in sorted(bypage.items()):
            page = doc[pg]; H = page.rect.height; sc = dpi / 72.0
            pix = page.get_pixmap(dpi=dpi)
            img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
            fig, ax = plt.subplots(figsize=(11, 13)); ax.imshow(img); ax.axis("off")
            for chart, blk in items:
                key, xk, yk = CHARTS[chart]
                xm, ym = aff(blk.get("x_axis", {})), aff(blk.get("y_axis", {}))
                if not (xm and ym): 
                    print("   %-22s no axis map" % chart); continue
                for lay in ("cyan", "magenta", "yellow"):
                    cur = d["layers"][lay].get(key)
                    if not cur: continue
                    xs = np.array(cur[xk], float)
                    ys = np.array([np.nan if v is None else v for v in cur[yk]], float)
                    px = (xs - xm[1]) / xm[0] * sc
                    py = (H - (ys - ym[1]) / ym[0]) * sc
                    ax.plot(px, py, COL[lay], lw=1.8, alpha=.8)
                    ok, tot = ink_hit(img, px, py)
                    flag = "" if tot and 100*ok/tot >= 97 else "   <-- INSPECT"
                    print("   %-22s %-8s ink-hit %5.1f%%  (n=%d)%s"
                          % (chart, lay, 100*ok/max(tot,1), tot, flag))
            p = out / ("%s_p%d_overlay.png" % (fn.split("_")[0], pg))
            plt.tight_layout(); plt.savefig(p, dpi=88, bbox_inches="tight"); plt.close(fig)
            print("   wrote %s" % p.name)


if __name__ == "__main__":
    main()
