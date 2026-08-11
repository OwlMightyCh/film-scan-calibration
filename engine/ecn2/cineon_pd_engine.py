#!/usr/bin/env python3
import json, re, sys, numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; DATA=ROOT/"data"; BUILDS=ROOT/"builds"
sys.path.insert(0, str(ROOT))
from engine.common import interimage as iim
from engine.common.spectral import density, resample
GRID=np.arange(400,731,1.0)   # provisional; narrowed to the dye set's measured support below

# 3x3 DIR / interimage inhibition matrix (dye-amount space): developed dye =
# DIR_MATRIX @ pre-coupler dye.  Default identity => stage skipped and outputs
# stay bit-identical to the pre-feature engine.
DIR_MATRIX=np.eye(3)
# --dye-json / --out-cube: per-stock basis overrides, mirroring
# c41_statusm_engine. Both must be given together so a per-stock experiment can
# never overwrite the canonical shared cube.
import argparse as _ap_mod
_ap=_ap_mod.ArgumentParser(add_help=False)
_ap.add_argument("--dye-json", default=None)
_ap.add_argument("--out-cube", default=None)
_a,_rest=_ap.parse_known_args(); sys.argv=[sys.argv[0]]+_rest
if bool(_a.dye_json)!=bool(_a.out_cube):
    raise SystemExit("--dye-json and --out-cube must be given together")
_dye=Path(_a.dye_json) if _a.dye_json else DATA/"films"/"Vision3_dye_density.json"
dj=json.load(open(_dye)); fc=dj["shared_full_curves"]

# The integration grid is narrowed to the dye set's MEASURED support, following
# engine/reversal/reversal_transform.py's dye_support_grid(). The traced Vision3
# basis carries null at 400-401 and 799-800 (the tracer cannot centre a line in
# the frame-edge columns). Resampling those to 0 would model the film as
# PERFECTLY CLEAR there -- an unbounded, sign-known error; synthesizing a value
# instead is the C-41 blue-edge defect. Truncating and letting the responsivities
# renormalize on the shorter grid asserts only that the unmeasured 2 nm resembles
# the in-band mean: a bounded bias. Costs 0.89%% of the RP180 blue channel.
_wl_all = np.array(fc["wavelength_nm"], float)
_meas = [ _wl_all[~np.isnan(np.array([np.nan if v is None else v for v in fc[k]], float))]
          for k in ("cyan", "magenta", "yellow") ]
_lo = max(GRID[0], min(m.min() for m in _meas))
_hi = min(GRID[-1], max(m.max() for m in _meas))
GRID = np.arange(np.ceil(_lo), np.floor(_hi) + 1, 1.0)
print("integration grid narrowed to measured dye support: %.0f-%.0f nm" % (GRID[0], GRID[-1]))

wl_d=np.array(fc["wavelength_nm"],float)
def _dye(channel):
    """Resample one dye curve, honouring null entries beyond measured support.

    Mirrors load_dye_channel() in engine/reversal/reversal_transform.py: nulls
    are dropped from the interpolation support rather than cast to 0, so no
    synthesized tail enters the integral. GRID is already narrowed to the
    measured support above, so nothing falls outside it.
    """
    v = np.array([np.nan if x is None else x for x in fc[channel]], float)
    ok = ~np.isnan(v)
    return resample(wl_d[ok], v[ok], GRID)

C=_dye("cyan");M=_dye("magenta");Y=_dye("yellow")
raw=open(DATA/"equipment"/"film_scanner_SPD_combined.csv").read().strip().splitlines()
hdr=raw[0].split(","); data=np.array([[float(x) for x in r.split(",")] for r in raw[1:]])
def col(n): return data[:,hdr.index(n)]
wl_s=data[:,0]
L_R=resample(wl_s,col("R100_G0_B0"),GRID);L_G=resample(wl_s,col("R0_G100_B0"),GRID);L_B=resample(wl_s,col("R0_G0_B100"),GRID)
ct=open(DATA/"equipment"/"a7r2_cfa.md").read()
def arr(k):
    m=re.search(k+r'"?\s*:\s*\[([0-9eE.,\s\\-]*?)\]',ct)
    return np.array([float(x) for x in re.findall(r'-?\d+\.?\d*(?:[eE][-+]?\d+)?',m.group(1))],float)
wl_c=arr("ssf_bands")
S_R=resample(wl_c,arr("red_ssf"),GRID);S_G=resample(wl_c,arr("green_ssf"),GRID);S_B=resample(wl_c,arr("blue_ssf"),GRID)
# RP 180 responsivities: canonical copy lives in data/standards/ (extracted
# from the former inline table here, 2026-07-16 — values unchanged).
import pathlib
_rpj=json.load(open(pathlib.Path(__file__).resolve().parents[2]/"data"/"standards"/"RP180_responsivities.json"))
_rpw=np.array(_rpj["wavelength_nm"],float)
P_R=resample(_rpw,np.array(_rpj["red"],float),GRID)
P_G=resample(_rpw,np.array(_rpj["green"],float),GRID)
P_B=resample(_rpw,np.array(_rpj["blue"],float),GRID)

PHI=np.stack([L_R*S_R,L_G*S_G,L_B*S_B]); PRT=np.stack([P_R,P_G,P_B])
PHI_n=PHI/PHI.sum(1,keepdims=True); PRT_n=PRT/PRT.sum(1,keepdims=True)
DYE=np.stack([C,M,Y])

def scan_fwd(d): return density(PHI_n,d,DYE)
def print_fwd(d): return density(PRT_n,d,DYE)
def scan_jac(dye):
    dye=np.atleast_2d(dye); T=10.0**(-(dye@DYE)); integ=T@PHI_n.T
    num=np.einsum('nl,il,jl->nij',T,PHI_n,DYE); return -np.log10(np.clip(integ,1e-12,None)), num/integ[:,:,None]

# linear seed: scanD = dye @ W  (fit)
n=9; ax=np.linspace(0,2,n)
g=np.array(np.meshgrid(ax,ax,ax,indexing="ij")).reshape(3,-1).T
ds=scan_fwd(g)
W,*_=np.linalg.lstsq(g,ds,rcond=None); Winv=np.linalg.inv(W)

# ---- interimage / DIR pre-compensation (identity => no-op, bit-identical) ----
DIR=np.asarray(DIR_MATRIX,float); INTERIMAGE_ON=not iim.is_identity(DIR)
def _solve_dye(target,iters=12):
    d=target@Winv
    for _ in range(iters):
        Dv,J=scan_jac(d); r=Dv-target
        d=np.clip(d-np.linalg.solve(J,r[:,:,None])[:,:,0],-0.5,6.0)
    return d
if INTERIMAGE_ON:
    # neutral scan-density ramp -> developed (datasheet) dye amounts, then the
    # per-layer pre-coupler curves inv(DIR)@developed so re-applying DIR on the
    # neutral axis reproduces the datasheet amounts exactly.
    _nlv=np.linspace(0,3.30,257); _tn=np.repeat(_nlv[:,None],3,1)
    _dev_n=_solve_dye(_tn)                      # developed amounts vs neutral level
    _pre_n=iim.precompensate(_dev_n,DIR)        # pre-coupler amounts on neutral
def interimage_print_dye(dye):
    """Route developed dye through per-layer pre-coupler curves then DIR-mix.
    Neutral axis is preserved exactly; off-neutral gets inter-layer cross-talk.
    Identity DIR -> returns dye unchanged (bit-identical fast path)."""
    if not INTERIMAGE_ON: return dye
    pre=np.empty_like(dye)
    for l in range(3):
        pre[:,l]=np.interp(dye[:,l],_dev_n[:,l],_pre_n[:,l])
    return iim.apply_dir(pre,DIR)

# ---- per-node inversion over 65^3 lattice in [0,DMAX] ----
DMAX=3.30; SZ = 65
axn=np.linspace(0,DMAX,SZ)
node=np.array(np.meshgrid(axn,axn,axn,indexing="ij")).reshape(3,-1).T  # (SZ^3,3) target scan densities
dye=node@Winv                                   # linear seed
for it in range(12):
    Dv,J=scan_jac(dye); r=Dv-node
    step=np.linalg.solve(J,r[:,:,None])[:,:,0]
    dye=np.clip(dye-step,-0.5,6.0)
res=np.max(np.abs(scan_fwd(dye)-node),1)
print(f"node solve: residual mean {res.mean():.4f} max {res.max():.4f} D  (>{0.02:.2f} on {100*np.mean(res>0.02):.1f}% nodes, mostly out-of-gamut corners)")
print(iim.status_line("ecn2:",DIR))
lut=print_fwd(interimage_print_dye(dye)).reshape(SZ,SZ,SZ,3)

# ---- validate LUT (trilinear) vs truth ----
rng=np.random.default_rng(1); gv=rng.uniform(0,2.2,(5000,3))
sv=scan_fwd(gv); pv=print_fwd(interimage_print_dye(gv))
def trilerp(L,pts):
    x=np.clip(pts/DMAX,0,1)*(SZ-1); i=np.floor(x).astype(int); f=x-i; i=np.minimum(i,SZ-2)
    out=np.zeros((len(pts),3))
    for dx in (0,1):
        for dy in (0,1):
            for dz in (0,1):
                w=(f[:,0] if dx else 1-f[:,0])*(f[:,1] if dy else 1-f[:,1])*(f[:,2] if dz else 1-f[:,2])
                out+=w[:,None]*L[i[:,0]+dx,i[:,1]+dy,i[:,2]+dz]
    return out
pl=trilerp(lut,sv)
print(f"LUT 65^3   : RMSE {np.sqrt(np.mean((pl-pv)**2)):.4f} D  max {np.max(np.abs(pl-pv)):.4f} D")

# ================= EXPORT =================
# .cube (65^3), normalised by DMAX on both axes (clamped 0..1)
BUILDS.mkdir(exist_ok=True)
CUBE=Path(_a.out_cube) if _a.out_cube else BUILDS/"ecn2"/"Vision3 to Cineon PD.cube"
CUBE.parent.mkdir(parents=True, exist_ok=True)
with open(CUBE,"w") as f:
    f.write("# Vision3 250D scanner-density -> RP180 printing-density (per-point)\n")
    f.write("# INPUT  = scanner density / %.2f  (apply -log10(linear) then /%.2f before this LUT)\n"%(DMAX,DMAX))
    f.write("# OUTPUT = printing density / %.2f  (multiply by %.2f to recover OD)\n"%(DMAX,DMAX))
    f.write("LUT_3D_SIZE %d\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n"%SZ)
    flat=np.clip(lut/DMAX,0,1).transpose(2,1,0,3).reshape(-1,3)  # cube: R fastest
    for v in flat: f.write("%.6f %.6f %.6f\n"%(v[0],v[1],v[2]))

# ---- validate the serialized, clipped, six-decimal artifact (not the in-memory LUT) ----
def read_written_cube(path,size,dmax):
    vals=[]
    for line in Path(path).read_text().splitlines():
        parts=line.split()
        if len(parts)==3:
            try: vals.append([float(x) for x in parts])
            except ValueError: pass
    a=np.array(vals)
    if a.shape!=(size**3,3): raise ValueError(f"Unexpected cube payload in {path}: {a.shape}")
    return a.reshape(size,size,size,3).transpose(2,1,0,3)*dmax
wl=read_written_cube(CUBE,SZ,DMAX)
err=trilerp(wl,sv)-pv
print(f"serialized {CUBE.name}: RMSE {np.sqrt(np.mean(err**2)):.4f}, max {np.max(np.abs(err)):.4f} D")
print(f"wrote {CUBE.relative_to(ROOT)}")
