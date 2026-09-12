/* Minimal DCTL shim: compiles a Transform DCTL as plain C to catch parse errors,
   undefined identifiers and bad signatures -- the class of fault Resolve reports as
   "main DCTL function has wrong arguments". */
#include <math.h>
#include <stdio.h>
typedef struct { float x, y, z; } float3;
static float3 make_float3(float a, float b, float c){ float3 v={a,b,c}; return v; }
#define __DEVICE__ static
#define __CONSTANT__ static const
static float _powf(float a, float b){ return powf(a,b); }
static float _fmaxf(float a, float b){ return fmaxf(a,b); }
static float _fminf(float a, float b){ return fminf(a,b); }
static float _log10f(float a){ return log10f(a); }
static float _exp10f(float a){ return powf(10.0f,a); }
/* UI params become mutable globals so the harness can drive them */
#define DEFINE_UI_PARAMS(name, label, type, ...) float name = 0;
#define DCTLUI_SLIDER_FLOAT 0
#define DCTLUI_CHECK_BOX 0
#define DCTLUI_VALUE_BOX 0

#include "DCTL_UNDER_TEST"

/* Harness for "Print Adjustment.dctl". The signal is normalized Status M
   density k = OD/3.30; sample points below are the Endura Premier printable
   window k in [0.082, 0.348] and its calibrated mid-gray k = 0.22. */
static void reset(void);

int main(void){
    extern float gamma, gain, pivot, gainR, gainG, gainB, literal;
    const float KMID = 0.22f, KLO = 0.082f, KHI = 0.348f;

    /* 1. defaults must be a bit-exact no-op, in BOTH modes */
    reset();
    float3 a = transform(0,0,0,0, KLO, KMID, KHI);
    printf("no-op   pivoted : %.9f %.9f %.9f  %s\n", a.x,a.y,a.z,
           (a.x==KLO&&a.y==KMID&&a.z==KHI)?"EXACT":"CHANGED");
    literal = 1.0f;
    float3 a2 = transform(0,0,0,0, KLO, KMID, KHI);
    printf("no-op   literal : %.9f %.9f %.9f  %s\n", a2.x,a2.y,a2.z,
           (a2.x==KLO&&a2.y==KMID&&a2.z==KHI)?"EXACT":"CHANGED");

    /* 2. pivoted gamma holds the pivot still and fans the ends */
    reset(); gamma = 1.20f;
    float3 p = transform(0,0,0,0, KLO, KMID, KHI);
    printf("gamma 1.20      : lo %.6f  mid %.6f (want %.6f)  hi %.6f   span %.6f -> %.6f\n",
           p.x, p.y, KMID, p.z, KHI-KLO, p.z-p.x);

    /* 3. pivoted gain is a pure offset: slope untouched, everything shifts */
    reset(); gain = 0.010f;
    float3 q = transform(0,0,0,0, KLO, KMID, KHI);
    printf("gain +0.010     : lo %+.6f  mid %+.6f  hi %+.6f  (want all +0.010000)\n",
           q.x-KLO, q.y-KMID, q.z-KHI);

    /* 4. literal mode: fixed point is k=1, NOT the pivot -- both ends move the
          same direction. This is the documented caveat; assert it holds. */
    reset(); literal = 1.0f; gamma = 0.90f;
    float3 l = transform(0,0,0,0, 0.10f, KMID, 1.0f);
    printf("literal g 0.90  : 0.10 -> %.6f   0.22 -> %.6f   1.00 -> %.6f (fixed)\n",
           l.x, l.y, l.z);
    reset(); literal = 1.0f; gain = 0.10f;
    float3 lg = transform(0,0,0,0, KMID, KMID, KMID);
    printf("literal gain .1 : %.6f (want %.6f = 1.1 * k)\n", lg.x, 1.1f*KMID);

    /* 5. per-channel trim is an additive density offset in both modes */
    reset(); gainR = 0.005f; gainB = -0.005f;
    float3 t = transform(0,0,0,0, KMID, KMID, KMID);
    printf("trim R+ B-      : %.6f %.6f %.6f  (want %.6f %.6f %.6f)\n",
           t.x,t.y,t.z, KMID+0.005f, KMID, KMID-0.005f);
    literal = 1.0f;
    float3 t2 = transform(0,0,0,0, KMID, KMID, KMID);
    printf("trim, literal   : %.6f %.6f %.6f  (same, want %s)\n",
           t2.x,t2.y,t2.z, (t2.x==t.x&&t2.z==t.z)?"MATCH":"DIFFER");

    /* 6. output must stay inside the cube's [0,1] input domain */
    reset(); gain = -0.10f;
    float3 c0 = transform(0,0,0,0, 0.0f, 0.02f, 0.0f);
    reset(); gamma = 2.0f; gain = 0.10f;
    float3 c1v = transform(0,0,0,0, 1.0f, 1.0f, 1.0f);
    printf("clamp           : low %.6f (want 0.000000)   high %.6f (want 1.000000)\n",
           c0.x, c1v.x);
    return 0;
}

static void reset(void){
    extern float gamma, gain, pivot, gainR, gainG, gainB, literal;
    gamma = 1.0f; gain = 0.0f; pivot = 0.22f;
    gainR = 0.0f; gainG = 0.0f; gainB = 0.0f; literal = 0.0f;
}
