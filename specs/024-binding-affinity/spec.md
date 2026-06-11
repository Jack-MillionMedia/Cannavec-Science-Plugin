# Spec 024 — Receptor-binding affinity (Cheng-Prusoff IC50 → Ki)

**Status**: Implemented, then archived (PR #41 MVP teardown — see git tag pre-mvp-teardown-2026-06-05)

**Created**: 2026-06-01

**Constitutional gates**: §II, §III, §V, §VI, §X.

## Why this priority

The force-multiplier vision names four personas. Specs 011–023 equipped the
reviewer, the trialist, and the toxicologist with quantitative tools; the
**pharmacologist** still had only registries to read, no calculator to run. The
single highest-yield, safest pharmacology computation is the **Cheng-Prusoff
conversion** (Cheng & Prusoff 1973, Biochem Pharmacol 22:3099).

Here is the problem it solves. A cannabinoid's **IC50** at CB1 is
assay-dependent — it moves with the displacing radioligand's concentration and
the radioligand's own Kd. So a Δ⁹-THC IC50 from one lab and a CBD IC50 from
another are **not on the same axis**, and ranking affinities off raw IC50 values
is a common, silent error in the cannabinoid literature. The Cheng-Prusoff
equation converts each IC50 to **Ki**, the assay-independent inhibition constant,
so the values finally compare:

    Ki = IC50 / (1 + [L]/Kd)      (competitive radioligand binding)
    Ki = IC50 / (1 + [S]/Km)      (competitive enzyme inhibition)

It deepens §VI (phytochemistry/receptor precision): the constitution already
demands receptors carry their UniProt accession; this demands their affinities be
reported on the comparable, assay-independent scale. It stays firmly within §V —
in-vitro binding constants are never a dose, a regimen, or individualized advice.
Deterministic and stdlib-only (§X): exact arithmetic and `math.log10`.

## User stories

### P1 — `binding.cheng_prusoff(ic50, ligand_conc, kd)` and the p-scale

`cheng_prusoff` returns Ki in the input unit; `p_affinity` / `affinity_from_p`
convert to and from the medicinal-chemistry log scale (pKi = −log10 Ki in molar),
on which +1 is a tenfold-tighter binder. Concentrations may be given in M / mM /
µM / nM / pM. Non-positive IC50 or Kd, a negative ligand concentration, and an
unknown unit all refuse.

### P2 — `binding.binding_affinity(...)` → typed result

Returns a `BindingResult` with `to_dict()`: Ki, the correction factor
`1 + [L]/Kd`, pIC50, pKi, the mode, and a rationale that states the IC50 is
assay-specific while the Ki is comparable, and by what multiple the raw IC50
overstated affinity. `mode="enzyme"` relabels [L]/Kd as [S]/Km (same formula).

### P3 — `python3 -m cannavec_science affinity …`

`affinity --ic50 I --ligand L --kd K [--unit nM] [--mode radioligand|enzyme]
[--json]` renders the conversion to Markdown and JSON; a bad input exits
non-zero. The `cannabis-evidence-synthesis` skill routes affinity-comparison
questions to it.

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- `cheng_prusoff(10, 1, 2) == 6.667` (correction 1.5); zero ligand returns the
  IC50 unchanged.
- `p_affinity(10, "nM") == 8.0`, and `affinity_from_p` round-trips across all
  units; nM vs µM differ by exactly 3 on the p-scale.
- Enzyme and radioligand modes give the same Ki and different labels.
- Non-positive IC50/Kd, negative ligand, unknown unit, and unknown mode refuse.
- `affinity …` renders Markdown and `--json` (`ki`, `p_ki`); a bad input exits
  non-zero.
