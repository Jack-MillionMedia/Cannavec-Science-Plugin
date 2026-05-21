"""Endocannabinoidome reference (spec 002 US6).

The endocannabinoidome (eCBome) is the extended endocannabinoid system
— the parent CB1/CB2 cannabinoid system plus the broader family of
lipid mediators (anandamide / 2-AG plus their N-acylethanolamine and
fatty-acid amide cousins), the receptors they engage (CB1/CB2/GPR55/
GPR119/GPR18/PPARα/PPARγ/TRPV1/TRPA1/TRPM8), the metabolic enzymes
that gate them (FAAH/MAGL/DAGLα/DAGLβ/NAPE-PLD/ABHD6/ABHD12/COX-2),
and the transporters that move them (FABP5/FABP7).

Every entry carries a primary identifier (UniProt accession for proteins,
HMDB ID for lipid mediators) per Constitution §I.

The module is reference-only — no live discovery (deferred to v0.3),
no live HMDB lookup. Each entry is hand-curated against the primary
literature.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


__all__ = [
    "EcbomeEntry",
    "EcbomeRole",
    "all_ecbome_entries",
    "find_ecbome_entries",
    "ecbome_for_compound",
    "render_markdown",
]


class EcbomeRole(str, Enum):
    """The functional class of an eCBome entry."""

    MEDIATOR = "mediator"
    RECEPTOR = "receptor"
    ENZYME = "enzyme"
    TRANSPORTER = "transporter"


@dataclass(frozen=True)
class EcbomeCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class EcbomeEntry:
    """One eCBome entity — receptor, enzyme, transporter, or mediator."""

    name: str
    role: EcbomeRole
    aliases: tuple[str, ...] = ()
    uniprot_id: str | None = None         # for proteins
    hmdb_id: str | None = None            # for lipid mediators
    gene_symbol: str | None = None        # for proteins
    summary: str = ""
    binds_to: tuple[str, ...] = ()        # receptor → ligands OR ligand → receptors
    citations: tuple[EcbomeCitation, ...] = ()
    last_verified: str = "2026-05-21"
    watch_pmids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Constitution §I — every entry has a primary identifier.
        if not (self.uniprot_id or self.hmdb_id):
            raise ValueError(
                f"eCBome entry {self.name!r} must have a UniProt or HMDB ID"
            )
        if not self.watch_pmids and self.citations:
            object.__setattr__(
                self, "watch_pmids",
                tuple(c.pmid for c in self.citations if c.pmid),
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["role"] = self.role.value
        d["aliases"] = list(self.aliases)
        d["binds_to"] = list(self.binds_to)
        d["citations"] = [
            {"label": c.label, "pmid": c.pmid, "doi": c.doi, "year": c.year}
            for c in self.citations
        ]
        d["watch_pmids"] = list(self.watch_pmids)
        return d


# Re-used citations
_DEVANE_1992 = EcbomeCitation(
    label="Devane WA et al., Science 1992, isolation of anandamide",
    pmid="1470919", year=1992,
)
_MECHOULAM_1995 = EcbomeCitation(
    label="Mechoulam R et al., Biochem Pharmacol 1995, 2-AG identification",
    pmid="7544547", year=1995,
)
_DI_MARZO_2018 = EcbomeCitation(
    label="Di Marzo V et al., Nat Rev Drug Discov 2018, eCBome overview",
    pmid="30382238", year=2018,
)
_BISOGNO_2005 = EcbomeCitation(
    label="Bisogno T et al., J Biol Chem 2005, DAGLα cloning",
    pmid="15545257", year=2005,
)
_DINH_2002 = EcbomeCitation(
    label="Dinh TP et al., PNAS 2002, MAGL identification",
    pmid="12235421", year=2002,
)
_CRAVATT_1996 = EcbomeCitation(
    label="Cravatt BF et al., Nature 1996, FAAH cloning",
    pmid="8900284", year=1996,
)
_LO_VERME_2005 = EcbomeCitation(
    label="Lo Verme J et al., Mol Pharmacol 2005, PEA via PPARα",
    pmid="15860571", year=2005,
)
_OVERTON_2006 = EcbomeCitation(
    label="Overton HA et al., Cell Metab 2006, GPR119 as OEA receptor",
    pmid="16517406", year=2006,
)
_RYBERG_2007 = EcbomeCitation(
    label="Ryberg E et al., Br J Pharmacol 2007, GPR55 cannabinoid receptor",
    pmid="17876302", year=2007,
)
_HUANG_2002 = EcbomeCitation(
    label="Huang SM et al., PNAS 2002, NADA endocannabinoid",
    pmid="12077423", year=2002,
)
_KACZOCHA_2009 = EcbomeCitation(
    label="Kaczocha M et al., PNAS 2009, FABP5/FABP7 as anandamide transporters",
    pmid="19505913", year=2009,
)
_PERTWEE_2010 = EcbomeCitation(
    label="Pertwee RG et al., Pharmacol Rev 2010, IUPHAR cannabinoid receptors",
    pmid="21079038", year=2010,
)


# ── Mediators (lipid endocannabinoids + cannabinoid-like NAEs) ──────


_MEDIATORS: tuple[EcbomeEntry, ...] = (
    EcbomeEntry(
        name="anandamide",
        aliases=("AEA", "N-arachidonoylethanolamine"),
        role=EcbomeRole.MEDIATOR,
        hmdb_id="HMDB0004080",
        summary=(
            "First-identified endogenous CB1 agonist. Partial agonist at CB1; "
            "weak agonist at CB2; full agonist at TRPV1; PPARγ ligand. "
            "Synthesised on-demand by NAPE-PLD; hydrolysed by FAAH."
        ),
        binds_to=("CB1", "CB2", "TRPV1", "PPARγ", "GPR55"),
        citations=(_DEVANE_1992, _DI_MARZO_2018),
    ),
    EcbomeEntry(
        name="2-arachidonoylglycerol",
        aliases=("2-AG",),
        role=EcbomeRole.MEDIATOR,
        hmdb_id="HMDB0004666",
        summary=(
            "Most abundant endogenous cannabinoid by mass. Full agonist at "
            "both CB1 and CB2. Synthesised by DAGLα/β; hydrolysed primarily "
            "by MAGL (≈85%) with ABHD6/ABHD12 contributing the remainder."
        ),
        binds_to=("CB1", "CB2"),
        citations=(_MECHOULAM_1995, _DI_MARZO_2018),
    ),
    EcbomeEntry(
        name="palmitoylethanolamide",
        aliases=("PEA",),
        role=EcbomeRole.MEDIATOR,
        hmdb_id="HMDB0002100",
        summary=(
            "N-acylethanolamine cannabinoid-like mediator. PPARα agonist "
            "(anti-inflammatory). Does NOT bind CB1/CB2 with appreciable "
            "affinity. Surfaces in chronic pain / neuroinflammation literature."
        ),
        binds_to=("PPARα", "GPR55"),
        citations=(_LO_VERME_2005,),
    ),
    EcbomeEntry(
        name="oleoylethanolamide",
        aliases=("OEA",),
        role=EcbomeRole.MEDIATOR,
        hmdb_id="HMDB0002088",
        summary=(
            "N-acylethanolamine satiety mediator. GPR119 / PPARα agonist; "
            "anorexigenic. The PPARα signal controls hepatic lipid metabolism."
        ),
        binds_to=("GPR119", "PPARα"),
        citations=(_OVERTON_2006,),
    ),
    EcbomeEntry(
        name="virodhamine",
        aliases=("O-arachidonoylethanolamine",),
        role=EcbomeRole.MEDIATOR,
        hmdb_id="HMDB0011131",
        summary=(
            "Endogenous CB2 partial agonist / CB1 partial antagonist. "
            "Identified as endocannabinoid in human / animal tissue but "
            "physiological role is less established than AEA / 2-AG."
        ),
        binds_to=("CB1", "CB2"),
        citations=(_DI_MARZO_2018,),
    ),
    EcbomeEntry(
        name="N-arachidonoyldopamine",
        aliases=("NADA",),
        role=EcbomeRole.MEDIATOR,
        hmdb_id="HMDB0012252",
        summary=(
            "Endogenous TRPV1 + CB1 dual-agonist. Concentrated in striatum + "
            "hippocampus; signal-noise interpretation requires care."
        ),
        binds_to=("TRPV1", "CB1"),
        citations=(_HUANG_2002,),
    ),
    EcbomeEntry(
        name="N-arachidonoylglycine",
        aliases=("NAGly", "NAGLY"),
        role=EcbomeRole.MEDIATOR,
        hmdb_id="HMDB0012252",
        summary=(
            "Endogenous lipid mediator structurally related to AEA. Does NOT "
            "bind CB1/CB2 appreciably; agonist at GPR18 and the orphan GPR55. "
            "Implicated in immune-cell migration and inflammatory pain."
        ),
        binds_to=("GPR18", "GPR55"),
        citations=(_DI_MARZO_2018,),
    ),
    EcbomeEntry(
        name="2-arachidonoylglyceryl-ether",
        aliases=("noladin ether", "2-AGE"),
        role=EcbomeRole.MEDIATOR,
        hmdb_id="HMDB0011130",
        summary=(
            "Endogenous CB1 agonist (controversial — not all groups detect "
            "it in tissue). When present, hydrolysis-resistant relative to "
            "2-AG via the glyceryl-ether bond."
        ),
        binds_to=("CB1",),
        citations=(_DI_MARZO_2018,),
    ),
)


# ── Receptors ───────────────────────────────────────────────────────


_RECEPTORS: tuple[EcbomeEntry, ...] = (
    EcbomeEntry(
        name="CB1",
        aliases=("CNR1", "cannabinoid receptor 1"),
        role=EcbomeRole.RECEPTOR,
        uniprot_id="P21554",
        gene_symbol="CNR1",
        summary=(
            "Primary Gi/o-coupled cannabinoid receptor in CNS; highest "
            "density in basal ganglia / cerebellum / hippocampus. Mediates "
            "psychoactive effects of Δ⁹-THC; partial agonism by Δ⁹-THC."
        ),
        binds_to=("anandamide", "2-AG", "Δ⁹-THC", "Δ⁸-THC"),
        citations=(_PERTWEE_2010,),
    ),
    EcbomeEntry(
        name="CB2",
        aliases=("CNR2", "cannabinoid receptor 2"),
        role=EcbomeRole.RECEPTOR,
        uniprot_id="P34972",
        gene_symbol="CNR2",
        summary=(
            "Primarily peripheral / immune-cell cannabinoid receptor; "
            "increasingly recognised in microglia + spinal cord. Mediates "
            "anti-inflammatory cannabinoid effects without the CB1 "
            "psychoactivity profile."
        ),
        binds_to=("2-AG", "anandamide", "CBD"),
        citations=(_PERTWEE_2010,),
    ),
    EcbomeEntry(
        name="GPR55",
        aliases=("orphan GPCR 55",),
        role=EcbomeRole.RECEPTOR,
        uniprot_id="Q9Y2T6",
        gene_symbol="GPR55",
        summary=(
            "Lysophosphatidylinositol-preferring GPCR with cannabinoid-class "
            "ligands. Activated by anandamide, NAGly, and Δ⁹-THC at "
            "physiological concentrations. CBD acts as an antagonist."
        ),
        binds_to=("anandamide", "Δ⁹-THC", "CBD"),
        citations=(_RYBERG_2007,),
    ),
    EcbomeEntry(
        name="GPR119",
        aliases=(),
        role=EcbomeRole.RECEPTOR,
        uniprot_id="Q8TDV5",
        gene_symbol="GPR119",
        summary=(
            "Enteroendocrine-cell GPCR; OEA agonist. Drives GLP-1 + PYY "
            "secretion; satiety / glucose-homeostasis axis."
        ),
        binds_to=("OEA",),
        citations=(_OVERTON_2006,),
    ),
    EcbomeEntry(
        name="GPR18",
        aliases=(),
        role=EcbomeRole.RECEPTOR,
        uniprot_id="Q14330",
        gene_symbol="GPR18",
        summary=(
            "Orphan GPCR with NAGly + Δ⁹-THC affinity reported in some "
            "assays. De-orphanisation remains contested; identifier "
            "discipline is important when citing GPR18 in mechanism claims."
        ),
        binds_to=("NAGly",),
        citations=(_DI_MARZO_2018,),
    ),
    EcbomeEntry(
        name="PPARα",
        aliases=("peroxisome proliferator-activated receptor alpha",),
        role=EcbomeRole.RECEPTOR,
        uniprot_id="Q07869",
        gene_symbol="PPARA",
        summary=(
            "Nuclear receptor; lipid-mediator target. Anandamide / PEA / OEA "
            "all engage PPARα. Anti-inflammatory + lipid-metabolism arm of "
            "the eCBome."
        ),
        binds_to=("PEA", "OEA", "anandamide"),
        citations=(_LO_VERME_2005,),
    ),
    EcbomeEntry(
        name="PPARγ",
        aliases=("peroxisome proliferator-activated receptor gamma",),
        role=EcbomeRole.RECEPTOR,
        uniprot_id="P37231",
        gene_symbol="PPARG",
        summary=(
            "Nuclear receptor; adipocyte-differentiation + insulin-sensitisation "
            "target. Anandamide + Δ⁹-THC bind at micromolar affinity. Cannabidiol "
            "engages at low-micromolar with anti-inflammatory downstream effects."
        ),
        binds_to=("anandamide", "Δ⁹-THC", "CBD"),
        citations=(_DI_MARZO_2018,),
    ),
    EcbomeEntry(
        name="TRPV1",
        aliases=("vanilloid receptor 1", "capsaicin receptor"),
        role=EcbomeRole.RECEPTOR,
        uniprot_id="Q8NER1",
        gene_symbol="TRPV1",
        summary=(
            "Heat-activated TRP channel; anandamide is a full agonist at "
            "low micromolar concentrations. NADA is a dual TRPV1/CB1 ligand."
        ),
        binds_to=("anandamide", "NADA", "CBD"),
        citations=(_PERTWEE_2010,),
    ),
    EcbomeEntry(
        name="TRPA1",
        aliases=("transient receptor potential A1",),
        role=EcbomeRole.RECEPTOR,
        uniprot_id="O75762",
        gene_symbol="TRPA1",
        summary=(
            "Cold + irritant-activated TRP channel. Engaged by several "
            "phytocannabinoids (CBD, CBC) at low-micromolar concentrations."
        ),
        binds_to=("CBD", "CBC"),
        citations=(_PERTWEE_2010,),
    ),
    EcbomeEntry(
        name="TRPM8",
        aliases=("transient receptor potential M8", "menthol receptor"),
        role=EcbomeRole.RECEPTOR,
        uniprot_id="Q7Z2W7",
        gene_symbol="TRPM8",
        summary=(
            "Cold-menthol receptor; cannabinoids (CBD, CBG) act as low-micromolar "
            "antagonists. Tied to neuropathic-pain literature."
        ),
        binds_to=("CBD", "CBG"),
        citations=(_PERTWEE_2010,),
    ),
)


# ── Enzymes ─────────────────────────────────────────────────────────


_ENZYMES: tuple[EcbomeEntry, ...] = (
    EcbomeEntry(
        name="FAAH",
        aliases=("fatty-acid amide hydrolase",),
        role=EcbomeRole.ENZYME,
        uniprot_id="O00519",
        gene_symbol="FAAH",
        summary=(
            "Anandamide hydrolase; serine hydrolase superfamily. Pharmacologic "
            "inhibition raises endogenous AEA / PEA / OEA tone — drug class "
            "explored for pain + anxiety (e.g. PF-04457845)."
        ),
        binds_to=("anandamide", "PEA", "OEA"),
        citations=(_CRAVATT_1996, _DI_MARZO_2018),
    ),
    EcbomeEntry(
        name="MAGL",
        aliases=("monoacylglycerol lipase", "MGLL"),
        role=EcbomeRole.ENZYME,
        uniprot_id="Q99685",
        gene_symbol="MGLL",
        summary=(
            "Primary 2-AG hydrolase (~85% of brain 2-AG hydrolysis). MAGL "
            "inhibition raises 2-AG tone, downstream of CB1 signalling — "
            "drug class explored for pain + neuroinflammation (e.g. ABX-1431)."
        ),
        binds_to=("2-AG",),
        citations=(_DINH_2002, _DI_MARZO_2018),
    ),
    EcbomeEntry(
        name="DAGLα",
        aliases=("diacylglycerol lipase alpha", "DAGLA"),
        role=EcbomeRole.ENZYME,
        uniprot_id="Q9Y4D2",
        gene_symbol="DAGLA",
        summary=(
            "CNS-dominant 2-AG synthase. DAGLα knockout produces a profound "
            "loss of brain 2-AG. Drives on-demand 2-AG synthesis in postsynaptic "
            "neurons during retrograde signalling."
        ),
        binds_to=("2-AG",),
        citations=(_BISOGNO_2005,),
    ),
    EcbomeEntry(
        name="DAGLβ",
        aliases=("diacylglycerol lipase beta", "DAGLB"),
        role=EcbomeRole.ENZYME,
        uniprot_id="Q8NCG7",
        gene_symbol="DAGLB",
        summary=(
            "Peripheral-tissue / immune-cell 2-AG synthase. Loss-of-function "
            "tightens macrophage / microglial 2-AG signalling axis."
        ),
        binds_to=("2-AG",),
        citations=(_BISOGNO_2005,),
    ),
    EcbomeEntry(
        name="NAPE-PLD",
        aliases=("N-acyl-phosphatidylethanolamine phospholipase D", "NAPEPLD"),
        role=EcbomeRole.ENZYME,
        uniprot_id="Q6IQ20",
        gene_symbol="NAPEPLD",
        summary=(
            "Anandamide + PEA + OEA synthase. Knockout retains residual "
            "NAE production via alternate pathways, indicating redundancy."
        ),
        binds_to=("anandamide", "PEA", "OEA"),
        citations=(_DI_MARZO_2018,),
    ),
    EcbomeEntry(
        name="ABHD6",
        aliases=("α/β-hydrolase domain 6",),
        role=EcbomeRole.ENZYME,
        uniprot_id="Q9BV23",
        gene_symbol="ABHD6",
        summary=(
            "Minor 2-AG hydrolase (~4% of brain 2-AG hydrolysis). Postsynaptic "
            "localisation suggests local regulation distinct from MAGL."
        ),
        binds_to=("2-AG",),
        citations=(_DI_MARZO_2018,),
    ),
    EcbomeEntry(
        name="ABHD12",
        aliases=("α/β-hydrolase domain 12",),
        role=EcbomeRole.ENZYME,
        uniprot_id="Q8N2K0",
        gene_symbol="ABHD12",
        summary=(
            "Minor 2-AG hydrolase. ABHD12 loss-of-function mutations cause "
            "PHARC syndrome, demonstrating the enzyme's CNS importance."
        ),
        binds_to=("2-AG",),
        citations=(_DI_MARZO_2018,),
    ),
    EcbomeEntry(
        name="COX-2",
        aliases=("cyclooxygenase 2", "PTGS2"),
        role=EcbomeRole.ENZYME,
        uniprot_id="P35354",
        gene_symbol="PTGS2",
        summary=(
            "Secondary anandamide / 2-AG metabolism — produces prostaglandin "
            "glyceryl-esters / ethanolamides. Bridges the eCBome to "
            "prostanoid signalling."
        ),
        binds_to=("anandamide", "2-AG"),
        citations=(_DI_MARZO_2018,),
    ),
)


# ── Transporters ────────────────────────────────────────────────────


_TRANSPORTERS: tuple[EcbomeEntry, ...] = (
    EcbomeEntry(
        name="FABP5",
        aliases=("fatty acid binding protein 5", "epidermal FABP"),
        role=EcbomeRole.TRANSPORTER,
        uniprot_id="Q01469",
        gene_symbol="FABP5",
        summary=(
            "Intracellular fatty-acid-binding protein. Identified as an "
            "anandamide transporter delivering AEA to FAAH for hydrolysis. "
            "Tissue-distribution-relevant in epidermis / immune cells."
        ),
        binds_to=("anandamide",),
        citations=(_KACZOCHA_2009,),
    ),
    EcbomeEntry(
        name="FABP7",
        aliases=("fatty acid binding protein 7", "brain-type FABP"),
        role=EcbomeRole.TRANSPORTER,
        uniprot_id="O15540",
        gene_symbol="FABP7",
        summary=(
            "Brain-type fatty-acid-binding protein; second anandamide "
            "transporter. CNS distribution suggests neuron-specific eCBome "
            "tone regulation distinct from FABP5."
        ),
        binds_to=("anandamide",),
        citations=(_KACZOCHA_2009,),
    ),
)


_REGISTRY: tuple[EcbomeEntry, ...] = _MEDIATORS + _RECEPTORS + _ENZYMES + _TRANSPORTERS


# ── Public API ──────────────────────────────────────────────────────


def all_ecbome_entries() -> tuple[EcbomeEntry, ...]:
    return _REGISTRY


def find_ecbome_entries(name_or_alias: str) -> tuple[EcbomeEntry, ...]:
    """Lookup by name or alias (case-insensitive)."""
    if not name_or_alias:
        return ()
    q = name_or_alias.lower().strip()
    out: list[EcbomeEntry] = []
    for e in _REGISTRY:
        if q == e.name.lower():
            out.append(e)
            continue
        if q in {a.lower() for a in e.aliases}:
            out.append(e)
            continue
        if e.gene_symbol and q == e.gene_symbol.lower():
            out.append(e)
            continue
    return tuple(out)


def ecbome_for_compound(compound: str) -> tuple[EcbomeEntry, ...]:
    """Return every eCBome entry that binds the given compound name."""
    if not compound:
        return ()
    needle = compound.lower()
    out: list[EcbomeEntry] = []
    for e in _REGISTRY:
        if any(needle in b.lower() for b in e.binds_to):
            out.append(e)
    return tuple(out)


def detect_ecbome_mention(text: str) -> tuple[EcbomeEntry, ...]:
    """Detect eCBome entries named in ``text`` (used by ``answer.py``)."""
    if not text:
        return ()
    lower = text.lower()
    out: list[EcbomeEntry] = []
    seen: set[str] = set()
    for e in _REGISTRY:
        names = [e.name.lower(), *(a.lower() for a in e.aliases)]
        if e.gene_symbol:
            names.append(e.gene_symbol.lower())
        for needle in names:
            if needle in lower and e.name not in seen:
                out.append(e)
                seen.add(e.name)
                break
    return tuple(out)


# ── Renderer ────────────────────────────────────────────────────────


def render_markdown(entries: tuple[EcbomeEntry, ...]) -> str:
    """Render an eCBome reference block."""
    if not entries:
        return ""
    lines: list[str] = []
    lines.append("## Endocannabinoidome (eCBome) reference")
    lines.append("")
    # Group by role for the standard "mediators / receptors / enzymes /
    # transporters" four-bucket presentation.
    by_role: dict[EcbomeRole, list[EcbomeEntry]] = {r: [] for r in EcbomeRole}
    for e in entries:
        by_role[e.role].append(e)
    for role in (
        EcbomeRole.MEDIATOR, EcbomeRole.RECEPTOR,
        EcbomeRole.ENZYME, EcbomeRole.TRANSPORTER,
    ):
        bucket = by_role[role]
        if not bucket:
            continue
        lines.append(f"### {role.value.capitalize()}s")
        lines.append("")
        for e in bucket:
            ident = e.uniprot_id or e.hmdb_id
            ident_label = f"UniProt {e.uniprot_id}" if e.uniprot_id else f"HMDB {e.hmdb_id}"
            lines.append(f"- **{e.name}** [{ident_label}] — {e.summary}")
            if e.binds_to:
                lines.append(f"  - Binds / engages: {', '.join(e.binds_to)}")
        lines.append("")
    return "\n".join(lines).rstrip()
