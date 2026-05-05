export interface ModuleDef {
  id: string
  name: string
  icon: string
  desc: string
  badge: 'job' | 'read'
  params?: string[]
  prompt?: string
  category?: 'mito' | 'cgas'
}

export const MODULES: ModuleDef[] = [
  // -- Mitochondrial tools --
  { id: 'mito_annotate',   name: '线粒体注释',       icon: '🧬', desc: 'PCG/tRNA/rRNA gene annotation, HMM+BLAST',          badge: 'job',  prompt: 'Please perform comprehensive mitochondrial gene annotation including protein-coding genes (PCG), tRNA genes, and rRNA genes. Use HMM profiles and BLAST references. Report gene boundaries, strand, and confidence scores.' },
  { id: 'mito_assemble',   name: '线粒体组装',       icon: '🧬🔬', desc: 'Plant mitochondrial genome assembly (long-read/hybrid)',          badge: 'job',  prompt: 'Please assemble a plant mitochondrial genome. Select the best strategy based on data type: Oatk for PacBio HiFi, Flye for ONT, GetOrganelle for hybrid data. Refer to Ni et al. (2025) PBJ review for parameter recommendations.' },
  { id: 'mito_qc',         name: '线粒体质控',       icon: '✅', desc: 'Five-dimensional quality assessment (completeness/contiguity/correctness/contamination/structure)', badge: 'read', prompt: 'Please perform a five-dimensional quality assessment of the mitochondrial genome: completeness (gene space), contiguity (assembly continuity), correctness (base/structural accuracy), contamination (chloroplast/nuclear), and structure (repeat consistency).' },
  { id: 'mito_visualize',  name: '线粒体可视化',     icon: '📊', desc: 'Circular/linear/OGDraw genome maps',                 badge: 'read', prompt: 'Please generate mitochondrial genome visualization plots including circular maps (pycirclize), linear maps (pygenomeviz), OGDraw-quality diagrams, and GC content profiles.' },
  { id: 'mito_codon',      name: '线粒体密码子',     icon: '📐', desc: 'Codon bias, RSCU analysis',                     badge: 'read', prompt: 'Please analyze mitochondrial codon usage bias. Calculate RSCU values, identify preferred codons, and generate visualization plots.' },
  { id: 'mito_gc',         name: '线粒体GC分析',     icon: '📈', desc: 'GC content, GC skew analysis',                        badge: 'read', prompt: 'Please analyze mitochondrial GC content and GC skew. Use sliding window statistics and generate GC distribution plots.' },
  { id: 'mito_phylogeny',  name: '线粒体系统发育',   icon: '🌳', desc: 'Multi-species gene alignment, phylogenetic matrix',               badge: 'job',  prompt: 'Please build a phylogenetic matrix using mitochondrial protein-coding genes. Extract shared genes, perform MAFFT alignment, trimAl trimming, and generate IQ-TREE input files.' },

  // -- Chloroplast tools --
  { id: 'chloro_assemble',     name: '叶绿体组装',       icon: '🧬🔬', desc: 'Chloroplast genome assembly (FASTQ → FASTA)',          badge: 'job',  category: 'cgas', prompt: 'Please assemble a chloroplast genome from raw FASTQ reads using the CGAS module 1 pipeline.' },
  { id: 'chloro_annotate',     name: '叶绿体注释',       icon: '🧬',    desc: 'Chloroplast gene annotation (FASTA → GenBank)',          badge: 'job',  category: 'cgas', prompt: 'Please annotate chloroplast genes including protein-coding genes, tRNA, and rRNA. Generate standard GenBank format output.' },
  { id: 'chloro_codon',        name: '叶绿体密码子',     icon: '📐',    desc: 'Chloroplast codon usage analysis (RSCU)',               badge: 'read', category: 'cgas', prompt: 'Please analyze chloroplast codon usage bias. Calculate RSCU values and compare with mitochondrial patterns.' },
  { id: 'chloro_phylogeny',    name: '叶绿体系统发育',   icon: '🌳',    desc: 'Chloroplast phylogenetic matrix construction',                    badge: 'job',  category: 'cgas', prompt: 'Please build a phylogenetic matrix using chloroplast protein-coding genes. Suitable for species evolutionary relationship studies.' },
  { id: 'chloro_ir_boundary',  name: '叶绿体IR边界',     icon: '✂️',    desc: 'IR boundary analysis (JLB/JSB/JSA/JLA)',            badge: 'read', category: 'cgas', prompt: 'Please analyze chloroplast IR boundaries. Detect LSC/IRb/SSC/IRa quadripartite structure junctions and calculate region lengths.' },
  { id: 'chloro_compare',      name: '叶绿体基因比较',   icon: '🔗',    desc: 'Cross-species gene name normalization',                        badge: 'read', category: 'cgas', prompt: 'Please perform cross-species chloroplast gene comparison. Normalize gene names and identify gene loss/gain events.' },
  { id: 'chloro_snp',          name: '叶绿体SNP',        icon: '🔀',    desc: 'SNP and substitution analysis',                             badge: 'read', category: 'cgas', prompt: 'Please analyze chloroplast SNPs and substitution patterns. Identify hypervariable and conserved regions.' },
  { id: 'chloro_ssr',          name: '叶绿体SSR',        icon: '🔍',    desc: 'Microsatellite (SSR) analysis',                           badge: 'read', category: 'cgas', prompt: 'Please analyze chloroplast microsatellite (SSR) loci. Count SSR types, frequencies, and distributions.' },
  { id: 'chloro_diversity',    name: '叶绿体多样性',     icon: '📊',    desc: 'Nucleotide diversity (Pi) analysis',                      badge: 'read', category: 'cgas', prompt: 'Please calculate chloroplast nucleotide diversity (Pi). Identify high-diversity regions.' },
  { id: 'chloro_intron',       name: '叶绿体内含子',     icon: '✂️',    desc: 'Gene and tRNA intron boundary analysis',                  badge: 'read', category: 'cgas', prompt: 'Please analyze chloroplast gene and tRNA intron boundaries. Identify intron-exon junction sites.' },
  { id: 'chloro_gene_table',   name: '叶绿体基因表',     icon: '📋',    desc: 'Gene content comparison tables',                            badge: 'read', category: 'cgas', prompt: 'Please generate chloroplast gene content comparison tables. Compare gene presence/absence across multiple species.' },
  { id: 'chloro_amino',        name: '叶绿体氨基酸',     icon: '🧪',    desc: 'Amino acid composition analysis',                            badge: 'read', category: 'cgas', prompt: 'Please analyze chloroplast amino acid composition. Count amino acid frequencies and generate reports.' },
  { id: 'chloro_convert',      name: '叶绿体格式转换',   icon: '📝',    desc: 'GenBank format conversion (NCBI submission)',                badge: 'read', category: 'cgas', prompt: 'Please convert chloroplast genome annotation results to NCBI submission standard GenBank format.' },
  { id: 'chloro_gene_compare', name: '叶绿体基因比较',   icon: '🔬',    desc: 'Multi-species gene comparison analysis',                        badge: 'read', category: 'cgas', prompt: 'Please perform multi-species chloroplast gene comparison. Identify orthologs and species-specific genes.' },
  { id: 'chloro_genome_compare', name: '叶绿体基因组比较', icon: '📑',  desc: 'Genome-level comparative analysis',                        badge: 'read', category: 'cgas', prompt: 'Please compare chloroplast genomes at the genome level. Analyze genome size, gene order, and structural variation.' },
]
