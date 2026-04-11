"""MitoFlow CLI — One command, one paper."""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console

app = typer.Typer(
    name="mitoflow",
    help="Plant mitochondrial genome annotation & analysis platform.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


@app.command()
def annotate(
    input: Path = typer.Option(..., "-i", "--input", help="Input FASTA file"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    name: str = typer.Option("MitoFlow", "-n", "--name", help="Project/species name"),
    threads: int = typer.Option(4, "-t", "--threads", help="Number of threads"),
    db: Optional[Path] = typer.Option(None, "--db", help="Custom database directory"),
    skip_trna: bool = typer.Option(False, "--skip-trna", help="Skip tRNA annotation"),
    skip_rrna: bool = typer.Option(False, "--skip-rrna", help="Skip rRNA annotation"),
    skip_qc: bool = typer.Option(False, "--skip-qc", help="Skip QC checks"),
    cp: Optional[Path] = typer.Option(None, "--cp", help="Chloroplast genome FASTA (enables MTPT)"),
    bam: Optional[Path] = typer.Option(None, "--bam", help="BAM file for coverage QC"),
):
    """Run full mitochondrial genome annotation pipeline."""
    from .core.pipeline import AnnotationPipeline

    console.print(f"[bold green]MitoFlow v0.1.0[/] — Plant Mitochondrial Genome Annotator")
    console.print(f"Input:  {input}")
    console.print(f"Output: {output}")

    pipeline = AnnotationPipeline(db_path=db, threads=threads)
    result = pipeline.run(
        fasta_path=input,
        output_dir=output,
        name=name,
        skip_trna=skip_trna,
        skip_rrna=skip_rrna,
        skip_qc=skip_qc,
        skip_mtpt=cp is None,
        cp_fasta=cp,
        bam_path=bam,
    )
    console.print(f"[bold green]Done![/] {result.summary()}")


@app.command()
def extract(
    input: Path = typer.Option(..., "-i", "--input", help="GenBank/GFF3 annotation file"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    types: str = typer.Option("CDS,Protein,tRNA,rRNA,intron", "-t", "--types", help="Sequence types to extract"),
):
    """Extract sequences from annotated genome."""
    console.print("[bold]Extracting sequences...[/]")
    # TODO: implement in Milestone 6


@app.command()
def qc(
    input: Path = typer.Option(..., "-i", "--input", help="Mitochondrial genome FASTA"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    name: str = typer.Option("MitoFlow", "-n", "--name", help="Project name"),
    cp: Optional[Path] = typer.Option(None, "--chloroplast", "--cp", help="Chloroplast genome FASTA"),
    bam: Optional[Path] = typer.Option(None, "--bam", help="BAM file for coverage check"),
    gfa: Optional[Path] = typer.Option(None, "--gfa", help="Assembly graph GFA file"),
    db: Optional[Path] = typer.Option(None, "--db", help="Database directory"),
):
    """Run five-dimensional quality control (Completeness/Contiguity/Correctness/Contamination/Structure)."""
    from .core.input import load_fasta
    from .qc.qc_engine import QCEngine
    from .db.manager import DBManager

    console.print(f"[bold green]MitoFlow QC[/] — Five-dimensional assessment")
    console.print(f"Input: {input}")

    genome = load_fasta(input)
    console.print(f"Genome: {genome.length:,} bp, GC={genome.gc_content:.1f}%")

    db_mgr = DBManager(db) if db else None
    engine = QCEngine(db_manager=db_mgr)
    result = engine.run(
        genome=genome,
        fasta_path=input,
        cp_fasta=cp,
        bam_path=bam,
        gfa_path=gfa,
        output_dir=output,
        name=name,
    )

    console.print(result.summary())
    if result.output_files:
        for ftype, fpath in result.output_files.items():
            console.print(f"  {ftype}: {fpath}")


@app.command()
def mtpt(
    input: Path = typer.Option(..., "-i", "--input", help="Mitochondrial genome FASTA"),
    cp: Path = typer.Option(..., "--cp", help="Chloroplast genome FASTA"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    name: str = typer.Option("MitoFlow", "-n", "--name", help="Project name"),
    threads: int = typer.Option(4, "-t", "--threads", help="Number of threads"),
    min_identity: float = typer.Option(70.0, "--min-identity", help="Minimum identity %%"),
    dotplot: bool = typer.Option(True, "--dotplot/--no-dotplot", help="Generate dot-plot"),
):
    """Detect MTPT (mitochondrial plastid-derived DNA transfer) regions."""
    from .core.input import load_fasta
    from .core.output import OutputManager
    from .mtpt.detector import detect_mtpt, generate_mtpt_dotplot

    console.print(f"[bold green]MitoFlow MTPT Detection[/]")
    out = OutputManager(output, name)
    out.setup()

    genome = load_fasta(input)
    console.print(f"Mito: {genome.length:,} bp")

    result = detect_mtpt(
        mito_fasta=input, cp_fasta=cp,
        genome=genome, threads=threads,
        min_identity=min_identity,
    )
    console.print(result.summary())

    # Save report
    report_path = out.report_dir / f"{name}_mtpt.txt"
    report_path.write_text(result.summary())
    console.print(f"Report: {report_path}")

    # Dot-plot
    if dotplot:
        plot_path = out.report_dir / f"{name}_mtpt_dotplot.png"
        generate_mtpt_dotplot(input, cp, plot_path, title=f"{name} MTPT")


@app.command()
def viz(
    input: Path = typer.Option(..., "-i", "--input", help="GenBank file (.gb/.gbk)"),
    output: Path = typer.Option(..., "-o", "--output", help="Output image path (PNG/SVG/PDF)"),
    name: str = typer.Option("", "-n", "--name", help="Organism name (center text)"),
    format: str = typer.Option("png", "--format", help="Output format: png | svg | pdf"),
    dpi: int = typer.Option(600, "--dpi", help="Output resolution (DPI)"),
    style: str = typer.Option("gbdraw", "--style", help="Plot style: gbdraw | ogdraw"),
    gc_window: int = typer.Option(200, "--gc-window", help="GC content window size (bp)"),
    separate_strands: bool = typer.Option(True, "--separate-strands/--no-separate-strands", help="Separate forward/reverse strands (gbdraw)"),
    palette: str = typer.Option("default", "--palette", help="Color palette name (gbdraw, e.g. default, orchid, sakura)"),
):
    """Generate OGDraw-quality circular genome visualization."""
    console.print(f"[bold green]MitoFlow Viz[/] — OGDraw-style genome map")
    console.print(f"Input:  {input}")
    console.print(f"Output: {output}")
    console.print(f"Style:  {style}")

    output.parent.mkdir(parents=True, exist_ok=True)

    if style == "ogdraw":
        # Use OGDrawR if available
        from .viz.circos_plot_ogdraw import draw_genome_map, check_ogdrawr_available
        
        if not check_ogdrawr_available():
            console.print("[red]Error:[/] OGDrawR R package not available. Install with: R -e 'remotes::install_github(\"xibeichens/OGDrawR\")'")
            raise typer.Exit(1)
        else:
            draw_genome_map(
                genbank_path=str(input),
                output_path=str(output),
                organism=name,
            )
        console.print(f"[bold green]Done![/] Saved to {output}")
    elif style == "gbdraw":
        # Use gbdraw (Python)
        from .viz.gbdraw_plot import draw_with_gbdraw, check_gbdraw_available
        
        if not check_gbdraw_available():
            console.print("[red]Error:[/] gbdraw not installed. Install with: pip install gbdraw")
            raise typer.Exit(1)
        else:
            genome_name = name if name else input.stem
            result = draw_with_gbdraw(
                genbank_path=str(input),
                output_path=str(output),
                organism=genome_name,
                format=format,
                gc_window=gc_window,
                separate_strands=separate_strands,
                palette=palette,
            )
            console.print(f"[bold green]Done![/] Genome: {result['genome_length']:,} bp, Genes: {result['gene_count']}")
    else:
        console.print(f"[red]Error:[/] Unknown style '{style}'. Use: gbdraw or ogdraw")
        raise typer.Exit(1)


@app.command()
def rna_edit(
    input: Path = typer.Option(..., "-i", "--input", help="GenBank file"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    name: str = typer.Option("MitoFlow", "-n", "--name", help="Project name"),
    ref: Optional[Path] = typer.Option(None, "--ref", help="Reference edited proteins FASTA"),
):
    """Predict C-to-U RNA editing sites."""
    from .rna_edit.predictor import (
        EditingSite, EditingResult,
        predict_editing_from_known_sites,
        correct_protein_with_editing, build_editing_result,
    )
    from .core.output import OutputManager
    from Bio import SeqIO

    console.print(f"[bold green]MitoFlow RNA Editing[/]")
    out = OutputManager(output, name)
    out.setup()

    # Parse GenBank and predict editing for each CDS
    record = next(SeqIO.parse(str(input), "genbank"))
    genome_seq = str(record.seq).upper()
    all_sites = []

    for feat in record.features:
        if feat.type != "CDS":
            continue
        gene_name = feat.qualifiers.get("gene", feat.qualifiers.get("locus_tag", ["unknown"]))[0]

        cds_seq = str(feat.extract(record.seq)).upper()
        if len(cds_seq) < 30:
            continue

        strand = feat.location.strand or 1
        cds_start = int(feat.location.start) + 1

        sites = predict_editing_from_known_sites(
            gene_name, cds_seq, cds_start, strand, len(genome_seq),
        )
        all_sites.extend(sites)

    result = build_editing_result(all_sites)
    console.print(result.summary())

    report_path = out.report_dir / f"{name}_rna_editing.txt"
    report_path.write_text(result.summary())
    console.print(f"Report: {report_path}")


@app.command()
def codon(
    input: Path = typer.Option(..., "-i", "--input", help="GenBank file"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    name: str = typer.Option("MitoFlow", "-n", "--name", help="Project name"),
    min_length: int = typer.Option(100, "--min-length", help="Minimum CDS length"),
    plot: bool = typer.Option(True, "--plot/--no-plot", help="Generate plots"),
    dpi: int = typer.Option(300, "--dpi", help="Plot resolution"),
):
    """Analyze codon usage (RSCU, ENC, GC3s, PR2, neutrality)."""
    from .codon.analysis import analyze_codon_usage, write_codon_tables
    from .core.output import OutputManager

    console.print(f"[bold green]MitoFlow Codon Usage[/]")
    out = OutputManager(output, name)
    out.setup()
    result = analyze_codon_usage(input, min_cds_length=min_length)
    console.print(result.summary())

    files = write_codon_tables(result, out.report_dir, name)
    for ftype, fpath in files.items():
        console.print(f"  {ftype}: {fpath}")

    if plot:
        from .codon.visualize import plot_all_codon
        plot_files = plot_all_codon(result, out.report_dir, name, dpi=dpi)
        for ptype, ppath in plot_files.items():
            console.print(f"  {ptype}: {ppath}")


@app.command()
def multiconf(
    input: Path = typer.Option(..., "-i", "--input", help="Genome FASTA"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    name: str = typer.Option("MitoFlow", "-n", "--name", help="Project name"),
    gbk: Optional[Path] = typer.Option(None, "--gbk", help="GenBank file with gene annotations"),
    min_repeat: int = typer.Option(100, "--min-repeat", help="Minimum repeat length"),
    reads: Optional[str] = typer.Option(None, "--reads", help="Long reads FASTQ for recombination validation"),
):
    """Predict multi-configuration structure from repeats."""
    from .core.input import load_fasta
    from .core.output import OutputManager
    from .multiconf.repeat_mediated import predict_subgenomes, verify_recombination_with_longreads

    console.print(f"[bold green]MitoFlow Multi-configuration[/]")
    out = OutputManager(output, name)
    out.setup()

    genome = load_fasta(input)
    console.print(f"Genome: {genome.length:,} bp")

    # Optional: load gene annotations
    gene_anns = None
    if gbk:
        from Bio import SeqIO
        from .models.gene import GeneAnnotation, ExonRecord, Strand
        record = next(SeqIO.parse(str(gbk), "genbank"))
        gene_anns = []
        for feat in record.features:
            if feat.type in ("gene", "CDS"):
                gname = feat.qualifiers.get("gene", feat.qualifiers.get("locus_tag", [""]))[0]
                if not gname:
                    continue
                strand_val = Strand.PLUS if (feat.location.strand or 1) == 1 else Strand.MINUS
                gene_anns.append(GeneAnnotation(
                    gene_name=gname,
                    exons=[ExonRecord(
                        start=int(feat.location.start) + 1,
                        end=int(feat.location.end),
                        strand=strand_val,
                    )],
                    strand=strand_val,
                ))

    result = predict_subgenomes(
        genome=genome,
        fasta_path=input,
        gene_annotations=gene_anns,
        min_repeat_length=min_repeat,
    )

    # Optional: validate with long reads
    if reads:
        console.print("[dim]Validating recombination with long reads...[/]")
        result.repeat_pairs = verify_recombination_with_longreads(
            input, reads, result.repeat_pairs,
        )

    console.print(result.summary())

    report_path = out.report_dir / f"{name}_multiconf.txt"
    report_path.write_text(result.summary())
    console.print(f"Report: {report_path}")


@app.command()
def db(
    action: str = typer.Argument(help="download | build | verify"),
    source: Optional[Path] = typer.Option(None, "--source", help="Source directory for building"),
):
    """Manage reference databases."""
    console.print(f"[bold]Database action:[/] {action}")
    # TODO: implement in Milestone 2


@app.command()
def kaks(
    query: Path = typer.Option(..., "-q", "--query", help="Query GenBank file"),
    references: List[Path] = typer.Option(..., "-r", "--ref", help="Reference GenBank file(s)"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    names: Optional[List[str]] = typer.Option(None, "--names", help="Species names (same order as inputs)"),
    engine: str = typer.Option("auto", "--engine", help="Calculation engine: auto | kaks_calculator | python"),
    method: str = typer.Option("MA", "--method", help="KaKs method: MA | NG | LWL | LPB | GY | YN | ALL (kaks_calculator only)"),
    plot: bool = typer.Option(True, "--plot/--no-plot", help="Generate Ka/Ks plots"),
    dpi: int = typer.Option(300, "--dpi", help="Plot resolution"),
):
    """Calculate Ka/Ks selection pressure between species pairs."""
    from .kaks.calculator import (
        batch_kaks, batch_kaks_with_calculator,
        check_kaks_calculator_available, write_kaks_tables,
    )
    from .core.output import OutputManager

    console.print(f"[bold green]MitoFlow Ka/Ks Analysis[/]")
    out = OutputManager(output, "kaks")
    out.setup()

    sp_names = names if names else None

    # Determine engine
    use_calculator = False
    if engine == "kaks_calculator":
        if not check_kaks_calculator_available():
            console.print("[red]Error:[/] KaKs_Calculator-3.0 not found in PATH")
            console.print("[dim]Install from: https://github.com/Chenglin20170390/KaKs_Calculator-3.0[/]")
            raise typer.Exit(1)
        use_calculator = True
    elif engine == "auto":
        if check_kaks_calculator_available():
            use_calculator = True
            console.print("[dim]Using KaKs_Calculator-3.0 (auto-detected)[/]")
        else:
            console.print("[dim]KaKs_Calculator-3.0 not found, using Python NG86[/]")

    if use_calculator:
        results = batch_kaks_with_calculator(
            query, references,
            reference_names=sp_names,
            output_dir=out.report_dir,
            method=method,
        )
    else:
        results = batch_kaks(query, references, reference_names=sp_names, output_dir=out.report_dir)

    total = sum(len(r.results) for r in results)
    console.print(f"Analyzed {total} gene pairs across {len(references)} reference species")

    for batch in results:
        console.print(batch.summary())

    files = write_kaks_tables(results, out.report_dir)
    for ftype, fpath in files.items():
        console.print(f"  {ftype}: {fpath}")

    if plot:
        from .kaks.visualize import plot_all_kaks
        plot_files = plot_all_kaks(results, out.report_dir, dpi=dpi)
        for ptype, ppath in plot_files.items():
            console.print(f"  plot_{ptype}: {ppath}")


@app.command()
def synteny(
    inputs: List[Path] = typer.Option(..., "-i", "--input", help="GenBank files (>=2)"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    names: Optional[List[str]] = typer.Option(None, "--names", help="Species names"),
    min_block: int = typer.Option(2, "--min-block", help="Minimum genes per synteny block"),
    viz_style: str = typer.Option("gbdraw", "--viz", help="Visualization: gbdraw | pygenomeviz | both | none"),
    palette: str = typer.Option("default", "--palette", help="Color palette (gbdraw)"),
):
    """Detect synteny (gene order collinearity) across genomes."""
    from .synteny.collinear import detect_synteny, write_synteny_tables
    from .core.output import OutputManager

    console.print(f"[bold green]MitoFlow Synteny Analysis[/]")
    out = OutputManager(output, "synteny")
    out.setup()

    if len(inputs) < 2:
        console.print("[red]Error: Need at least 2 GenBank files[/]")
        raise typer.Exit(1)

    result = detect_synteny(inputs, species_names=names, min_block_size=min_block)
    console.print(result.summary())

    files = write_synteny_tables(result, out.report_dir)
    for ftype, fpath in files.items():
        console.print(f"  {ftype}: {fpath}")

    # Visualization
    if viz_style != "none":
        if viz_style in ("gbdraw", "both"):
            try:
                from .synteny.visualize import draw_synteny_gbdraw, check_gbdraw_available
                if check_gbdraw_available():
                    gbdraw_path = out.report_dir / f"{names[0] if names else 'synteny'}_gbdraw.png"
                    draw_synteny_gbdraw(
                        genbank_files=inputs,
                        output_path=gbdraw_path,
                        species_names=names,
                        palette=palette,
                        format="png",
                    )
                    console.print(f"  gbdraw: {gbdraw_path}")
                else:
                    console.print("[yellow]Warning:[/] gbdraw not installed, skipping gbdraw visualization")
            except Exception as e:
                console.print(f"[yellow]Warning:[/] gbdraw synteny failed: {e}")

        if viz_style in ("pygenomeviz", "both"):
            try:
                from .synteny.visualize import draw_synteny, SyntenyVizConfig
                pgv_path = out.report_dir / f"{names[0] if names else 'synteny'}_synteny.png"
                draw_synteny(result, pgv_path)
                console.print(f"  pygenomeviz: {pgv_path}")
            except Exception as e:
                console.print(f"[yellow]Warning:[/] pygenomeviz synteny failed: {e}")


@app.command(name="pi")
def pi_cmd(
    inputs: List[Path] = typer.Option(..., "-i", "--input", help="GenBank files (>=2)"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    names: Optional[List[str]] = typer.Option(None, "--names", help="Species names"),
    min_length: int = typer.Option(30, "--min-length", help="Minimum sequence length"),
    dpi: int = typer.Option(300, "--dpi", help="Plot resolution"),
):
    """Calculate nucleotide diversity (Pi) across species."""
    from .pi.diversity import calculate_pi_from_genbank, write_pi_tables
    from .pi.visualize import plot_pi_bar
    from .core.output import OutputManager

    console.print(f"[bold green]MitoFlow Pi Analysis[/]")
    out = OutputManager(output, "pi")
    out.setup()

    if len(inputs) < 2:
        console.print("[red]Error: Need at least 2 GenBank files[/]")
        raise typer.Exit(1)

    sp_names = names if names else None
    result = calculate_pi_from_genbank(inputs, species_names=sp_names, min_length=min_length)
    console.print(result.summary())

    files = write_pi_tables(result, out.report_dir, "mitoflow")
    for ftype, fpath in files.items():
        console.print(f"  {ftype}: {fpath}")

    if result.regions:
        plot_path = out.report_dir / "mitoflow_pi_bar.png"
        plot_pi_bar(result, plot_path, dpi=dpi)
        console.print(f"  pi_plot: {plot_path}")


@app.command()
def phylo(
    inputs: List[Path] = typer.Option(..., "-i", "--input", help="GenBank files"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    names: Optional[List[str]] = typer.Option(None, "--names", help="Species names"),
    type: str = typer.Option("protein", "--type", help="Sequence type: protein | nucleotide"),
    trim: bool = typer.Option(True, "--trim/--no-trim", help="Trim alignments with trimAl"),
    min_presence: float = typer.Option(1.0, "--min-presence", help="Minimum gene presence fraction"),
):
    """Prepare phylogenetic alignment (extract, align, concatenate)."""
    from .phylo.alignment import align_and_concatenate

    console.print(f"[bold green]MitoFlow Phylo Alignment[/]")
    console.print(f"Species: {len(inputs)}, Type: {type}")

    result = align_and_concatenate(
        genbank_files=inputs,
        output_dir=output,
        species_names=names,
        sequence_type=type,
        trim=trim,
        min_presence=min_presence,
    )
    console.print(result.summary())
    for w in result.warnings:
        console.print(f"  [yellow]Warning:[/] {w}")


@app.command()
def cms(
    input: Path = typer.Option(..., "-i", "--input", help="Genome FASTA file"),
    gbk: Path = typer.Option(..., "--gbk", help="GenBank file with annotations"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    name: str = typer.Option("MitoFlow", "-n", "--name", help="Project name"),
    threads: int = typer.Option(4, "-t", "--threads", help="Number of threads"),
    min_orf: int = typer.Option(300, "--min-orf", help="Minimum ORF length (bp)"),
    gene_db: Optional[Path] = typer.Option(None, "--gene-db", help="Mitochondrial gene protein FASTA for chimera detection"),
):
    """Predict CMS (Cytoplasmic Male Sterility) candidate genes."""
    from .core.input import load_fasta
    from .core.output import OutputManager
    from .cms.predictor import predict_cms, write_cms_report, KNOWN_CMS_GENES
    from Bio import SeqIO
    from .models.gene import GeneAnnotation, ExonRecord, Strand

    console.print(f"[bold green]MitoFlow CMS Prediction[/]")
    out = OutputManager(output, name)
    out.setup()

    genome = load_fasta(input)
    console.print(f"Genome: {genome.length:,} bp")
    console.print(f"Known CMS genes in database: {len(KNOWN_CMS_GENES)}")

    # Load gene annotations from GenBank
    record = next(SeqIO.parse(str(gbk), "genbank"))
    gene_anns = []
    for feat in record.features:
        if feat.type in ("gene", "CDS"):
            gname = feat.qualifiers.get("gene", feat.qualifiers.get("locus_tag", [""]))[0]
            if not gname:
                continue
            strand_val = Strand.PLUS if (feat.location.strand or 1) == 1 else Strand.MINUS
            gene_anns.append(GeneAnnotation(
                gene_name=gname,
                exons=[ExonRecord(
                    start=int(feat.location.start) + 1,
                    end=int(feat.location.end),
                    strand=strand_val,
                )],
                strand=strand_val,
            ))

    result = predict_cms(
        fasta_path=input,
        genome_seq=genome.sequence,
        annotated_genes=gene_anns,
        gene_protein_db=gene_db,
        threads=threads,
        min_orf_length=min_orf,
    )
    console.print(result.summary())

    files = write_cms_report(result, out.report_dir, name)
    for ftype, fpath in files.items():
        console.print(f"  {ftype}: {fpath}")


@app.command()
def report(
    input: Path = typer.Option(..., "-i", "--input", help="GenBank file"),
    output: Path = typer.Option(..., "-o", "--output", help="Output HTML file"),
    name: str = typer.Option("MitoFlow", "-n", "--name", help="Project name"),
    qc_scores: Optional[str] = typer.Option(None, "--qc-scores", help="QC scores JSON file"),
):
    """Generate interactive HTML analysis report."""
    from .report.generator import ReportData, generate_html_report
    from Bio import SeqIO

    console.print(f"[bold green]MitoFlow Report[/]")

    record = next(SeqIO.parse(str(input), "genbank"))
    seq = str(record.seq).upper()
    gc = (seq.count("G") + seq.count("C")) / len(seq) * 100 if seq else 0

    # Collect gene data
    genes = []
    for feat in record.features:
        if feat.type in ("gene", "CDS", "tRNA", "rRNA"):
            gname = feat.qualifiers.get("gene", feat.qualifiers.get("locus_tag", [""]))[0]
            if not gname:
                continue
            product = feat.qualifiers.get("product", [""])[0]
            gtype = feat.type
            if feat.type == "gene":
                # Check if there's a CDS with same name
                gtype = "CDS"
            genes.append({
                "name": gname,
                "type": gtype,
                "start": int(feat.location.start) + 1,
                "end": int(feat.location.end),
                "strand": feat.location.strand or 1,
                "product": product,
            })

    data = ReportData(
        project_name=name,
        genome_length=len(seq),
        gc_content=gc,
        n_pcg=sum(1 for g in genes if g["type"] == "CDS"),
        n_trna=sum(1 for g in genes if g["type"] == "tRNA"),
        n_rrna=sum(1 for g in genes if g["type"] == "rRNA"),
        gene_list=genes,
    )

    # Load QC scores if provided
    if qc_scores:
        import json
        with open(qc_scores) as f:
            scores = json.load(f)
        s = scores.get("scores", {})
        data.qc_overall = s.get("overall", 0)
        data.qc_grade = s.get("grade", "N/A")
        data.qc_completeness = s.get("completeness", 0)
        data.qc_contiguity = s.get("contiguity", 0)
        data.qc_correctness = s.get("correctness", 0)
        data.qc_contamination = s.get("contamination", 0)
        data.qc_structure = s.get("structure", 0)
        data.qc_passed = scores.get("annotation_ready", False)
        data.qc_missing_genes = scores.get("missing_genes", [])

    report_path = generate_html_report(data, output, gbk_path=input)
    console.print(f"[bold green]Done![/] Report: {report_path}")


@app.command(name="repeat")
def repeat_cmd(
    input: Path = typer.Option(..., "-i", "--input", help="Genome FASTA file"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    name: str = typer.Option("MitoFlow", "-n", "--name", help="Project name"),
    min_tandem: int = typer.Option(100, "--min-tandem", help="Min tandem repeat length (bp)"),
    min_long: int = typer.Option(100, "--min-long", help="Min dispersed repeat length (bp)"),
    threads: int = typer.Option(4, "-t", "--threads", help="Number of threads"),
):
    """Run repeat detection (SSR + tandem + long repeats)."""
    from .core.input import load_fasta
    from .core.output import OutputManager
    from .repeat.ssr import detect_ssr, write_ssr_output
    from .repeat.tandem import detect_tandem_repeats, write_tandem_output
    from .repeat.long_repeat import detect_long_repeats, write_repeat_output

    console.print(f"[bold green]MitoFlow Repeat Detection[/]")
    out = OutputManager(output, name)
    out.setup()

    genome = load_fasta(input)
    console.print(f"Genome: {genome.length:,} bp")

    report_lines = [
        "=== Repeat Detection ===",
        f"Genome: {genome.length:,} bp",
    ]

    # SSR detection
    ssr_dir = out.report_dir / "ssr"
    ssr_result = detect_ssr(input, ssr_dir)
    ssr_files = write_ssr_output(ssr_result, ssr_dir, name)
    report_lines.append(ssr_result.summary())
    console.print(f"SSRs: {ssr_result.total_count} found")

    # Tandem repeat detection
    tandem_dir = out.report_dir / "tandem"
    tandem_result = detect_tandem_repeats(input, tandem_dir)
    tandem_files = write_tandem_output(tandem_result, tandem_dir, name)
    report_lines.append(tandem_result.summary())
    console.print(f"Tandem repeats: {tandem_result.total_count} found")

    # Long / dispersed repeat detection
    long_dir = out.report_dir / "long_repeat"
    long_result = detect_long_repeats(input, long_dir, min_length=min_long, threads=threads)
    long_files = write_repeat_output(long_result, long_dir, name)
    report_lines.append(long_result.summary())
    console.print(f"Long repeats: {long_result.total_repeats} found")

    # Write summary
    report_path = out.report_dir / f"{name}_repeats.txt"
    report_path.write_text("\n".join(report_lines))
    console.print(f"Report: {report_path}")


@app.command()
def numt(
    input: Path = typer.Option(..., "-i", "--input", help="Mitochondrial genome FASTA"),
    nuc: Path = typer.Option(..., "--nuc", help="Nuclear genome FASTA"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    name: str = typer.Option("MitoFlow", "-n", "--name", help="Project name"),
    threads: int = typer.Option(4, "-t", "--threads", help="Number of threads"),
    min_identity: float = typer.Option(80.0, "--min-identity", help="Minimum identity %%"),
    min_length: int = typer.Option(100, "--min-length", help="Minimum alignment length (bp)"),
):
    """Detect NUMTs (nuclear mitochondrial DNA segments)."""
    from .core.input import load_fasta
    from .core.output import OutputManager
    from .numt.detector import detect_numts

    console.print(f"[bold green]MitoFlow NUMT Detection[/]")
    out = OutputManager(output, name)
    out.setup()

    mito = load_fasta(input)
    console.print(f"Mito: {mito.length:,} bp")

    result = detect_numts(
        mito_fasta=input,
        nuc_fasta=nuc,
        threads=threads,
        min_identity=min_identity,
        min_length=min_length,
    )
    console.print(result.summary())

    report_path = out.report_dir / f"{name}_numt.txt"
    report_path.write_text(result.summary())
    console.print(f"Report: {report_path}")


@app.command()
def gc(
    input: Path = typer.Option(..., "-i", "--input", help="Genome FASTA file"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    name: str = typer.Option("MitoFlow", "-n", "--name", help="Project name"),
    window: int = typer.Option(500, "--window", help="Sliding window size (bp)"),
    dpi: int = typer.Option(300, "--dpi", help="Output resolution (DPI)"),
):
    """GC content analysis and visualization."""
    from .core.input import load_fasta
    from .core.output import OutputManager

    console.print(f"[bold green]MitoFlow GC Analysis[/]")
    out = OutputManager(output, name)
    out.setup()

    genome = load_fasta(input)
    console.print(f"Genome: {genome.length:,} bp, GC={genome.gc_content:.1f}%")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    seq = genome.sequence.upper()
    w = window

    # Sliding window GC
    positions = []
    gc_vals = []
    for i in range(0, len(seq) - w + 1, w // 2):
        chunk = seq[i:i + w]
        g = chunk.count("G")
        c = chunk.count("C")
        gc_vals.append((g + c) / len(chunk) * 100)
        positions.append(i + w // 2)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)

    # Line plot
    ax1.plot(positions, gc_vals, color="#3498db", linewidth=0.8)
    ax1.axhline(y=genome.gc_content, color="#e74c3c", linestyle="--",
                label=f"Overall GC: {genome.gc_content:.1f}%")
    ax1.set_ylabel("GC %")
    ax1.set_title(f"GC Content ({name}) — Window: {w} bp")
    ax1.legend()

    # Histogram
    ax2.hist(gc_vals, bins=50, color="#2ecc71", edgecolor="white", alpha=0.8)
    ax2.set_xlabel("GC %")
    ax2.set_ylabel("Frequency")
    ax2.axvline(x=genome.gc_content, color="#e74c3c", linestyle="--")

    plt.tight_layout()
    plot_path = out.report_dir / f"{name}_gc.png"
    fig.savefig(plot_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    # Write data
    data_path = out.report_dir / f"{name}_gc.tsv"
    with open(data_path, "w") as f:
        f.write("position\tgc_percent\n")
        for pos, val in zip(positions, gc_vals):
            f.write(f"{pos}\t{val:.2f}\n")

    console.print(f"Plot: {plot_path}")
    console.print(f"Data: {data_path}")


@app.command(name="phylo-tree")
def phylo_tree(
    input: Path = typer.Option(..., "-i", "--input",
                               help="Multiple sequence alignment file (FASTA/PHYLIP)"),
    output: Path = typer.Option(..., "-o", "--output", help="Output directory"),
    model: str = typer.Option("MFP", "--model",
                              help="Substitution model (MFP=auto-select, GTR, HKY, etc.)"),
    bootstrap: int = typer.Option(1000, "--bootstrap", help="Number of bootstrap replicates"),
    threads: int = typer.Option(4, "-t", "--threads", help="Number of threads"),
):
    """Build phylogenetic tree from multiple sequence alignment."""
    import shutil

    console.print(f"[bold green]MitoFlow Phylogenetic Tree[/]")
    console.print(f"Input: {input}")
    console.print(f"Model: {model}, Bootstrap: {bootstrap}")

    output.mkdir(parents=True, exist_ok=True)

    iqtree = shutil.which("iqtree2") or shutil.which("iqtree")
    if not iqtree:
        console.print("[red]Error: iqtree2/iqtree not found in PATH[/]")
        raise typer.Exit(1)

    import subprocess

    cmd = [
        iqtree,
        "-s", str(input),
        "-m", model,
        "-bb", str(bootstrap),
        "-nt", str(threads),
        "--prefix", str(output / "phylo"),
    ]
    console.print(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

    if proc.returncode != 0:
        console.print(f"[red]IQ-TREE failed:[/]\n{proc.stderr[-500:]}")
        raise typer.Exit(1)

    tree_file = output / "phylo.treefile"
    if tree_file.exists():
        console.print(f"[bold green]Done![/] Tree: {tree_file}")
    else:
        console.print("[yellow]Tree file not found at expected path. Check output directory.[/]")
        # List what was created
        for f in output.iterdir():
            console.print(f"  {f.name}")


if __name__ == "__main__":
    app()
