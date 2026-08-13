"""Command-line entry point.

    python -m s2p_tool components/example_cap.json -o outputs
    python run.py components/*.json
"""
from __future__ import annotations

import argparse
import glob
import sys

from . import __version__
from .pipeline import process

MINI_GUIDE = f"""\
s2p v{__version__} - Kapasitor/Inductor -> SPICE (.cir) + Touchstone (.s2p) modeli

HIZLI BASLANGIC
  Datasheet PDF'ten JSON sablonu cikar (sonra gozden gecir):
    s2p --pdf "yol\\datasheet.pdf" --kind capacitor -o outputs
  Parametre dosyasindan model:
    s2p components\\example_cap.json -o outputs
  Olculmus vendor .s2p ice aktar (en yuksek dogruluk):
    s2p --import "yol\\parca_series.s2p" --kind capacitor -o outputs
  Iki olcumu kiyasla (or. DC-bias derating):
    s2p --compare "...DC0V.s2p" "...DC6V3.s2p" --kind capacitor
  Uretilen .cir'i simulatorde dogrula (ngspice varsa):
    s2p --validate-spice "yol\\parca_series.s2p" --kind capacitor

CIKTI (her parca icin -o klasorune): .s2p  .cir  _report.md  _Zf.csv
KAPSAM: yalniz kapasitor ve inductor.   Tum secenekler: s2p --help
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="s2p",
        description="Capacitor/Inductor datasheet -> SPICE + Touchstone .s2p model")
    p.add_argument("inputs", nargs="*", help="component JSON file(s) or glob(s)")
    p.add_argument("-o", "--out", default="outputs", help="output directory")
    p.add_argument("--z0", type=float, default=50.0, help="reference impedance [Ohm]")
    p.add_argument("--fstart", type=float, default=1e4, help="sweep start [Hz]")
    p.add_argument("--fstop", type=float, default=1e10, help="sweep stop [Hz]")
    p.add_argument("--topology", choices=["series", "shunt"], default="series",
                   help="2-port placement: series-through (default) or shunt-to-ground")
    p.add_argument("--dc-bias", dest="dc_bias", type=float, default=None,
                   help="DC bias [V] -> capacitance derating (Class II ceramics)")
    p.add_argument("--temp", dest="temp_c", type=float, default=None,
                   help="operating temperature [degC] -> capacitance derating")
    p.add_argument("--ac-vrms", dest="ac_vrms", type=float, default=None,
                   help="AC drive level [Vrms] -> capacitance derating (Class II)")
    p.add_argument("--dc-bias-csv", dest="dc_bias_csv", default=None,
                   help="digitized DC-bias curve CSV (V, dC%%) for exact derating")
    p.add_argument("--tcc-csv", dest="tcc_csv", default=None,
                   help="digitized temperature curve CSV (degC, dC%%) for exact derating")
    p.add_argument("--import", dest="imp", metavar="S2P",
                   help="import a measured vendor Touchstone (.s2p) instead of JSON")
    p.add_argument("--compare", nargs="+", metavar="S2P",
                   help="compare extracted params across 2+ measured .s2p (e.g. DC bias)")
    p.add_argument("--validate-spice", dest="valsp", metavar="S2P",
                   help="round-trip: synth .cir then re-simulate it vs measured")
    p.add_argument("--pdf", metavar="PDF",
                   help="extract a datasheet PDF into a pre-filled component JSON")
    p.add_argument("--kind", choices=["capacitor", "inductor"],
                   help="component kind for --import / --compare / --validate-spice / --pdf")
    args = p.parse_args(argv)

    # No inputs and no action -> show the mini guide (e.g. double-clicking the exe).
    if not args.inputs and not (args.imp or args.compare or args.valsp or args.pdf):
        print(MINI_GUIDE)
        return 0

    if args.pdf:
        if not args.kind:
            print("--pdf requires --kind capacitor|inductor", file=sys.stderr)
            return 2
        from .pdfreader import pdf_to_template
        try:
            out = pdf_to_template(args.pdf, args.kind, args.out)
            import json
            data = json.load(open(out, encoding="utf-8"))
            print(f"[OK] datasheet -> {out}")
            for k in ("part_number", "capacitance_f", "inductance_h",
                      "voltage_rating_v", "dielectric", "case"):
                if k in data:
                    print(f"     {k}: {data[k]}")
            print(f"     REVIEW the JSON, then:  s2p {out} -o outputs")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {args.pdf}: {exc}", file=sys.stderr)
            return 1

    if args.valsp:
        from .pipeline import validate_spice_roundtrip
        try:
            print(validate_spice_roundtrip(args.valsp, args.kind or "capacitor"))
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] validate: {exc}", file=sys.stderr)
            return 1

    if args.compare:
        if not args.kind:
            print("--compare requires --kind capacitor|inductor", file=sys.stderr)
            return 2
        from .compare import compare_measured
        try:
            print(compare_measured(args.compare, args.kind))
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] compare: {exc}", file=sys.stderr)
            return 1

    if args.imp:
        if not args.kind:
            print("--import requires --kind capacitor|inductor", file=sys.stderr)
            return 2
        from .pipeline import process_import
        try:
            s2p, cir, rep = process_import(args.imp, args.kind, args.out, args.z0,
                                           args.topology)
            print(f"[OK] (measured) {args.imp}")
            for x in (s2p, cir, rep):
                print(f"     {x}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {args.imp}: {exc}", file=sys.stderr)
            return 1

    paths: list[str] = []
    for item in args.inputs:
        hits = glob.glob(item)
        paths.extend(hits or [item])

    from . import derate
    dc_curve = derate.load_curve_csv(args.dc_bias_csv) if args.dc_bias_csv else None
    tcc_curve = derate.load_curve_csv(args.tcc_csv) if args.tcc_csv else None
    rc = 0
    for path in paths:
        try:
            s2p, cir, rep = process(path, args.out, args.z0, args.fstart, args.fstop,
                                    args.topology, args.dc_bias, args.temp_c,
                                    args.ac_vrms, dc_curve, tcc_curve)
            print(f"[OK] {path}")
            print(f"     {s2p}")
            print(f"     {cir}")
            print(f"     {rep}")
        except Exception as exc:  # noqa: BLE001 - surface clearly to the user
            print(f"[FAIL] {path}: {exc}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
