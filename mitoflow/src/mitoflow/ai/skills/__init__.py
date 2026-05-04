"""MitoFlow AI Skills — encapsulated domain workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

_SKILLS_DIR = Path(__file__).parent


class Skill:
    """A reusable domain skill with instructions."""

    def __init__(self, name: str, description: str, instructions: str, tags: List[str]) -> None:
        self.name = name
        self.description = description
        self.instructions = instructions
        self.tags = tags

    def to_prompt(self) -> str:
        """Format as a system prompt section."""
        return f"## Skill: {self.name}\n\n{self.instructions}"


class SkillRegistry:
    """Registry of available skills."""

    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {}
        self._load_builtin_skills()

    def _load_builtin_skills(self) -> None:
        """Load built-in skills."""
        self.register(Skill(
            name="assembly",
            description="Guide organelle genome assembly from raw reads",
            instructions=_ASSEMBLY_SKILL,
            tags=["assembly", "getorganelle", "reads"],
        ))
        self.register(Skill(
            name="annotation",
            description="Run and validate mitochondrial genome annotation",
            instructions=_ANNOTATION_SKILL,
            tags=["annotation", "gene", "trna", "rrna"],
        ))
        self.register(Skill(
            name="quality_check",
            description="Assess annotation quality and identify errors",
            instructions=_QC_SKILL,
            tags=["qc", "validation", "accuracy"],
        ))
        self.register(Skill(
            name="erc_analysis",
            description="Evolutionary Rate Covariation analysis pipeline",
            instructions=_ERC_SKILL,
            tags=["erc", "evolution", "coevolution"],
        ))
        self.register(Skill(
            name="cms_detection",
            description="Detect and classify cytoplasmic male sterility genes",
            instructions=_CMS_SKILL,
            tags=["cms", "male_sterility", "chimeric"],
        ))
        self.register(Skill(
            name="comparative",
            description="Comparative genomics across species",
            instructions=_COMPARATIVE_SKILL,
            tags=["synteny", "pan_genome", "orthofinder"],
        ))

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, str]]:
        return [{"name": s.name, "description": s.description, "tags": s.tags} for s in self._skills.values()]

    def find_by_tag(self, tag: str) -> List[Skill]:
        return [s for s in self._skills.values() if tag in s.tags]


_ASSEMBLY_SKILL = """\
## Assembly Workflow

1. **Quality check raw reads**: FastQC/MultiQC
2. **Assemble with GetOrganelle** (recommended):
   ```
   get_organelle_reads.py -1 R1.fq.gz -2 R2.fq.gz -o output_dir \
     -F mitochondria -t 8
   ```
3. **Alternative tools**: NOVOPlasty (seed-based), MITObim (reference-guided)
4. **Validate assembly**: Check circularity, coverage, completeness
5. **Annotate with MitoFlow**: `mitofleshoot annotate -i assembly.fasta`

## Key Parameters
- Seed gene: use cox1 or rps11 for mitochondria
- k-mer: 21-121 range for GetOrganelle
- Coverage: expect 100-1000x for organelle reads

## Common Issues
- Repeats cause assembly fragmentation → try longer k-mers
- Low coverage → increase sequencing depth
- NUMT contamination → filter with MitoFlow numt module
"""


_ANNOTATION_SKILL = """\
## Annotation Workflow

1. **Run MitoFlow annotation**:
   ```
   mitofleshoot annotate -i genome.fasta -o results/ --threads 8
   ```
2. **Check protein-coding genes**: HMM + BLAST evidence
3. **Verify tRNA genes**: tRNAscan-SE + ARAGORN
4. **Verify rRNA genes**: Barrnap + BLAST
5. **Check for RNA editing**: `mitofleshoot rna-edit`
6. **Validate boundaries**: `mitofleshoot qc`

## Gene Boundary Rules
- Start: ATG (or ACG if RNA-edited to ATG)
- Stop: TAA, TAG, TGA (check for RNA editing removal)
- Splice sites: GT-AG for cis-spliced genes
- Trans-splicing: nad1, nad2, nad3, nad4, nad5, nad6, rps10

## Confidence Scoring
- High: HMM + BLAST both hit, e-value < 1e-10
- Medium: One strong hit (e-value < 1e-5)
- Low: Weak hits or partial matches
"""


_QC_SKILL = """\
## Quality Control Workflow

1. **Run MitoFlow QC**:
   ```
   mitofleshoot qc -i results/ --gold-standard ref.gb
   ```
2. **Check error types**:
   - A errors: False positive genes (should not exist)
   - B errors: Position offset (wrong boundaries)
   - C errors: Splice site errors
3. **Boundary validation**:
   - Compare with gold standard GenBank
   - Check coverage drop-off at boundaries
   - Verify RNA editing-corrected start/stop codons
4. **Produce accuracy report**: Precision, Recall, F1

## Interpretation
- F1 ≥ 90%: Good quality
- F1 80-90%: Needs improvement
- F1 < 80%: Significant issues

## Common Fixes
- A errors: Adjust e-value threshold, check for NUMT
- B errors: Re-run with boundary refinement
- C errors: Update splice site models
"""


_ERC_SKILL = """\
## ERC Analysis Workflow

1. **Prepare proteomes**: Annotate all species with MitoFlow
2. **Run OrthoFinder**: Cluster genes into orthogroups
   ```
   orthofinder -f proteomes_dir/ -t 8
   ```
3. **Align orthogroups**: MAFFT for each orthogroup
4. **Build gene trees**: IQ-TREE for each alignment
5. **Reconcile branch lengths**: DLCpar or Treerecs
6. **Compute ERC**: ERCnet2 or custom script
   ```
   ERCnet2 -t species_tree.nwk -d gene_trees_dir/ -o erc_results/
   ```
7. **Statistical testing**: Permutation test + BH FDR correction
8. **Network analysis**: Build ERC network, detect communities

## Interpretation
- ERC > 0.5, FDR < 0.05: Strong coevolution signal
- ERC 0.3-0.5: Moderate signal
- Check organelle-nuclear pairs specifically

## Key References
- Forsythe et al. (2021) Mol Biol Evol
- ERCnet2 (2022) Bioinformatics
"""


_CMS_SKILL = """\
## CMS Detection Workflow

1. **Run MitoFlow CMS module**:
   ```
   mitofleshoot cms -i genome.fasta -o results/
   ```
2. **Identify chimeric ORFs**: Novel ORFs from recombination
3. **Search CMS database**: Compare with known CMS genes
4. **Check for Rf genes**: Nuclear PPR proteins
5. **Validate with expression data**: RNA-seq if available

## Known CMS Systems
| Type | Crop | Causal ORF |
|------|------|------------|
| WA-CMS | Rice | orf288 |
| BT-CMS | Rice | orf79 |
| HL-CMS | Rice | orfH79 |
| Pol-CMS | Wheat | orf256 |

## Features for ML Classification
- ORF length (novel ORFs are typically 200-900 bp)
- Homology to known genes (chimeric nature)
- Upstream/downstream context
- PPR binding site prediction
"""


_COMPARATIVE_SKILL = """\
## Comparative Genomics Workflow

1. **Annotate all species** with MitoFlow
2. **Cluster genes** with OrthoFinder
3. **Compare gene content**:
   - Core genes (present in all species)
   - Accessory genes (some species)
   - Unique genes (species-specific)
4. **Detect synteny**:
   ```
   mitofleshoot synteny -i genbank_dir/ -o synteny_results/
   ```
5. **Visualize**: Circos plots, synteny maps
6. **Analyze evolution**: Gene loss, duplication, rearrangement

## Key Metrics
- Synteny conservation score
- Gene content overlap (Jaccard index)
- Genome size variation
- Repeat content correlation
"""
