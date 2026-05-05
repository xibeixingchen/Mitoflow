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
  // ── 线粒体工具 ──
  { id: 'mito_annotate',   name: '线粒体注释',       icon: '🧬', desc: 'PCG/tRNA/rRNA 基因注释，HMM+BLAST',          badge: 'job',  prompt: '请对线粒体基因组进行全面的基因注释，包括蛋白编码基因(PCG)、tRNA基因和rRNA基因。使用HMM profiles和BLAST参考。报告基因边界、链向和置信度。' },
  { id: 'mito_assemble',   name: '线粒体组装',       icon: '🧬🔬', desc: '植物线粒体基因组组装 (长读/混合)',          badge: 'job',  prompt: '请对植物线粒体基因组进行组装。根据数据类型选择最佳策略：PacBio HiFi用Oatk，ONT用Flye，混合数据用GetOrganelle。参考Ni et al. (2025) PBJ综述。' },
  { id: 'mito_qc',         name: '线粒体质控',       icon: '✅', desc: '五维质量评估 (完整性/连续性/正确性/污染/结构)', badge: 'read', prompt: '请对线粒体基因组进行五维质量评估：完整性(基因空间)、连续性(组装连续度)、正确性(碱基/结构准确性)、污染(叶绿体/核污染)、结构(重复一致性)。' },
  { id: 'mito_visualize',  name: '线粒体可视化',     icon: '📊', desc: '环形/线性/OGDraw基因组图谱',                 badge: 'read', prompt: '请生成线粒体基因组可视化图谱，包括环形图(circular)、线性图(linear)、OGDraw质量图和GC含量图。' },
  { id: 'mito_codon',      name: '线粒体密码子',     icon: '📐', desc: '密码子偏好性、RSCU分析',                     badge: 'read', prompt: '请分析线粒体基因组的密码子使用偏好性。计算RSCU值，识别偏好密码子，并生成可视化图表。' },
  { id: 'mito_gc',         name: '线粒体GC分析',     icon: '📈', desc: 'GC含量、GC skew分析',                        badge: 'read', prompt: '请分析线粒体基因组的GC含量和GC skew。使用滑动窗口统计并生成GC分布图。' },
  { id: 'mito_phylogeny',  name: '线粒体系统发育',   icon: '🌳', desc: '多物种基因比对、系统发育矩阵',               badge: 'job',  prompt: '请使用线粒体蛋白编码基因构建系统发育矩阵。提取共享基因，MAFFT比对，trimAl修剪，生成IQ-TREE输入文件。' },

  // ── 叶绿体工具 ──
  { id: 'chloro_assemble',     name: '叶绿体组装',       icon: '🧬🔬', desc: '叶绿体基因组组装 (FASTQ → FASTA)',          badge: 'job',  category: 'cgas', prompt: '请对叶绿体基因组进行组装。从原始FASTQ读长数据开始，使用CGAS模块1进行组装。' },
  { id: 'chloro_annotate',     name: '叶绿体注释',       icon: '🧬',    desc: '叶绿体基因注释 (FASTA → GenBank)',          badge: 'job',  category: 'cgas', prompt: '请对叶绿体基因组进行基因注释。识别蛋白编码基因、tRNA、rRNA，生成标准GenBank格式。' },
  { id: 'chloro_codon',        name: '叶绿体密码子',     icon: '📐',    desc: '叶绿体密码子使用分析 (RSCU)',               badge: 'read', category: 'cgas', prompt: '请分析叶绿体基因组的密码子使用偏好性。计算RSCU值并与线粒体进行比较。' },
  { id: 'chloro_phylogeny',    name: '叶绿体系统发育',   icon: '🌳',    desc: '叶绿体系统发育矩阵构建',                    badge: 'job',  category: 'cgas', prompt: '请使用叶绿体蛋白编码基因构建系统发育矩阵。适用于物种进化关系研究。' },
  { id: 'chloro_ir_boundary',  name: '叶绿体IR边界',     icon: '✂️',    desc: 'IR区边界分析 (JLB/JSB/JSA/JLA)',            badge: 'read', category: 'cgas', prompt: '请分析叶绿体基因组的IR边界。检测LSC/IRb/SSC/IRa四分区结构的边界位置，计算各区长度。' },
  { id: 'chloro_compare',      name: '叶绿体基因比较',   icon: '🔗',    desc: '跨物种基因名标准化',                        badge: 'read', category: 'cgas', prompt: '请对叶绿体基因进行跨物种比较，标准化基因名称，识别基因丢失和获得事件。' },
  { id: 'chloro_snp',          name: '叶绿体SNP',        icon: '🔀',    desc: 'SNP和替换分析',                             badge: 'read', category: 'cgas', prompt: '请分析叶绿体基因组的SNP和替换模式。识别高变区域和保守区域。' },
  { id: 'chloro_ssr',          name: '叶绿体SSR',        icon: '🔍',    desc: '微卫星(SSR)分析',                           badge: 'read', category: 'cgas', prompt: '请分析叶绿体基因组的微卫星(SSR)位点。统计SSR类型、频率和分布。' },
  { id: 'chloro_diversity',    name: '叶绿体多样性',     icon: '📊',    desc: '核苷酸多样性(Pi)分析',                      badge: 'read', category: 'cgas', prompt: '请计算叶绿体基因组的核苷酸多样性(Pi)。识别高多样性区域。' },
  { id: 'chloro_intron',       name: '叶绿体内含子',     icon: '✂️',    desc: '基因和tRNA内含子边界分析',                  badge: 'read', category: 'cgas', prompt: '请分析叶绿体基因和tRNA的内含子边界。识别内含子-外显子连接点。' },
  { id: 'chloro_gene_table',   name: '叶绿体基因表',     icon: '📋',    desc: '基因含量比较表',                            badge: 'read', category: 'cgas', prompt: '请生成叶绿体基因含量比较表。对比多个物种的基因存在/缺失情况。' },
  { id: 'chloro_amino',        name: '叶绿体氨基酸',     icon: '🧪',    desc: '氨基酸组成分析',                            badge: 'read', category: 'cgas', prompt: '请分析叶绿体基因组的氨基酸组成。统计各氨基酸频率并生成报告。' },
  { id: 'chloro_convert',      name: '叶绿体格式转换',   icon: '📝',    desc: 'GenBank格式转换 (NCBI提交)',                badge: 'read', category: 'cgas', prompt: '请将叶绿体基因组注释结果转换为NCBI提交标准的GenBank格式。' },
  { id: 'chloro_gene_compare', name: '叶绿体基因比较',   icon: '🔬',    desc: '多物种基因比较分析',                        badge: 'read', category: 'cgas', prompt: '请对叶绿体基因进行多物种比较分析。识别同源基因和物种特异性基因。' },
  { id: 'chloro_genome_compare', name: '叶绿体基因组比较', icon: '📑',  desc: '基因组水平比较分析',                        badge: 'read', category: 'cgas', prompt: '请在基因组水平比较叶绿体基因组。分析基因组大小、基因顺序和结构变异。' },
]
