#!/usr/bin/env python3
"""
MitoFlow金标准验证脚本

基于PMGA修正数据验证MitoFlow注释准确性
对标PMGA论文（Plant Communications, 2025）评估标准

输入:
  - NCBI原始GenBank文件
  - PMGA修正数据 (corrections.csv)
  - MitoFlow输出

输出:
  - validation_report.md (详细报告)
  - validation_summary.csv (汇总数据)
  - validation_details.json (详细数据)
"""

import argparse
import json
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from Bio import SeqIO
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# 核心线粒体基因列表 (对标PMGA)
CORE_PCG_41 = [
    "nad1", "nad2", "nad3", "nad4", "nad4l", "nad5", "nad6", "nad7", "nad9",
    "cob", "cox1", "cox2", "cox3",
    "atp1", "atp4", "atp6", "atp8", "atp9",
    "ccmb", "ccmc", "ccmfc", "ccmfn",
    "rpl2", "rpl5", "rpl10", "rpl16",
    "rps1", "rps2", "rps3", "rps4", "rps7", "rps10", "rps12", "rps13", "rps14", "rps19",
    "matr", "mttb", "rnaseh", "sdh3", "sdh4",
]

# RNA编辑相关基因
STGE_GENES = ["cox1", "nad1", "nad4l", "rps10"]
SPGE_GENES = ["atp6", "atp9", "ccmfc", "mttb"]


def normalize_gene_name(name: str) -> str:
    """标准化基因名称"""
    if not name:
        return ""
    name = name.lower().strip()
    name = name.split(".")[0]  # 移除版本号
    # 移除连字符后缀 (atp1-1 -> atp1, atp6-2 -> atp6)
    name = name.split("-")[0]
    # 处理别名
    aliases = {
        "ccmfn": "ccmfn",
        "ccmfc": "ccmfc",
        "ccmfc1": "ccmfc",
        "ccmfc2": "ccmfc",
        "ccmfn1": "ccmfn",
        "ccmfn2": "ccmfn",
        "nad4l": "nad4l",
        "matr": "matr",
        "mat-r": "matr",
        "mat": "matr",
        "mttb": "mttb",
        "rp15": "rpl5",
        "rnaseh": "rnaseh",
    }
    return aliases.get(name, name)


def parse_genbank_features(gb_files, source_name: str = "") -> Tuple[List[Dict], int]:
    """解析GenBank文件，提取所有基因特征。

    支持多文件合并（用于分染色体/ contig 的物种）。
    """
    if isinstance(gb_files, Path):
        gb_files = [gb_files]

    all_features = []
    genome_length = 0

    for gb_file in gb_files:
        try:
            record = SeqIO.read(gb_file, "genbank")
        except Exception as e:
            logger.warning(f"Error reading {gb_file}: {e}")
            continue

        genome_length = max(genome_length, len(record.seq))

        for feat in record.features:
            if feat.type in ['source', 'repeat_region', 'misc_feature', 'ncRNA', "5'UTR", "3'UTR", 'D-loop']:
                continue

            gene_name = ""
            if 'gene' in feat.qualifiers:
                gene_name = feat.qualifiers['gene'][0]
            elif 'name' in feat.qualifiers:
                gene_name = feat.qualifiers['name'][0]

            gene_name = normalize_gene_name(gene_name)

            if feat.type in ['gene', 'CDS', 'tRNA', 'rRNA', 'exon']:
                # Handle CompoundLocation (join) for trans-spliced genes:
                # split into one feature per part so exon-level comparison works.
                if hasattr(feat.location, 'parts') and len(feat.location.parts) > 1:
                    for part in feat.location.parts:
                        all_features.append({
                            'type': feat.type,
                            'gene': gene_name,
                            'start': int(part.start),
                            'end': int(part.end),
                            'strand': part.strand,
                            'product': feat.qualifiers.get('product', [''])[0],
                        })
                else:
                    all_features.append({
                        'type': feat.type,
                        'gene': gene_name,
                        'start': int(feat.location.start),
                        'end': int(feat.location.end),
                        'strand': feat.location.strand,
                        'product': feat.qualifiers.get('product', [''])[0],
                    })

    return all_features, genome_length


def parse_gff_features(gff_file: Path, fasta_file: Optional[Path] = None) -> Tuple[List[Dict], int]:
    """解析GFF3文件，提取CDS特征。

    需要FASTA文件来获取基因组长度。正确处理Parent关系，
    从gene行提取名称并映射到CDS/exon行。
    """
    all_features = []
    genome_length = 0

    # 获取基因组长度
    if fasta_file and fasta_file.exists():
        try:
            record = SeqIO.read(fasta_file, "fasta")
            genome_length = len(record.seq)
        except Exception:
            pass

    # 第一遍：建立 ID -> gene_name 映射
    id_to_name: dict[str, str] = {}
    lines = [l for l in gff_file.read_text().splitlines() if not l.startswith("#") and l.strip()]
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        feat_type = parts[2]
        attrs = parts[8]
        attr_dict = {}
        for attr in attrs.split(";"):
            if "=" in attr:
                k, v = attr.split("=", 1)
                attr_dict[k] = v

        name = attr_dict.get("Name", attr_dict.get("name", attr_dict.get("gene", "")))
        feat_id = attr_dict.get("ID", "")
        if name and feat_id:
            id_to_name[feat_id] = normalize_gene_name(name)
        # gene行直接记录
        if feat_type == "gene" and name:
            gene_id = attr_dict.get("ID", "")
            if gene_id:
                id_to_name[gene_id] = normalize_gene_name(name)

    # 第二遍：解析特征，CDS通过Parent链查找gene名
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 9:
            continue

        seqid, source, feat_type, start, end, score, strand, phase, attrs = parts

        if feat_type not in ["gene", "CDS", "tRNA", "rRNA", "exon"]:
            continue

        attr_dict = {}
        for attr in attrs.split(";"):
            if "=" in attr:
                k, v = attr.split("=", 1)
                attr_dict[k] = v

        # 确定基因名称
        gene_name = ""
        if feat_type == "gene":
            gene_name = id_to_name.get(attr_dict.get("ID", ""), "")
        else:
            # 通过Parent链查找
            parent = attr_dict.get("Parent", "")
            # Parent可能包含多个ID（逗号分隔）
            for p in parent.split(","):
                p = p.strip()
                if p in id_to_name:
                    gene_name = id_to_name[p]
                    break
                # 尝试查找Parent的Parent（mRNA -> gene）
                for line2 in lines:
                    parts2 = line2.split("\t")
                    if len(parts2) < 9:
                        continue
                    attr_dict2 = {}
                    for attr2 in parts2[8].split(";"):
                        if "=" in attr2:
                            k2, v2 = attr2.split("=", 1)
                            attr_dict2[k2] = v2
                    if attr_dict2.get("ID", "") == p and attr_dict2.get("Parent"):
                        gp = attr_dict2.get("Parent", "").split(",")[0].strip()
                        if gp in id_to_name:
                            gene_name = id_to_name[gp]
                            break
                if gene_name:
                    break

        # 转换为0-based坐标
        start_0 = int(start) - 1
        end_0 = int(end)

        # 链方向
        strand_val = 1 if strand == "+" else (-1 if strand == "-" else None)

        all_features.append({
            'type': feat_type,
            'gene': gene_name,
            'start': start_0,
            'end': end_0,
            'strand': strand_val,
            'product': '',
        })

    return all_features, genome_length


def load_corrections(corrections_file: Path) -> Dict[str, Dict]:
    """加载PMGA修正数据"""
    df = pd.read_csv(corrections_file)

    # 按物种和基因组织修正数据
    corrections = defaultdict(lambda: defaultdict(list))

    for row in df.itertuples():
        species = row.species
        gene = row.gene
        correction_type = row.correction_type

        if correction_type != 'correct':
            corrections[species][gene].append({
                'before': row.position_before,
                'after': row.position_after,
                'type': correction_type,
                'note': row.correction_note,
            })

    return dict(corrections)


def circular_offset(a: int, b: int, genome_length: int) -> int:
    """计算环形基因组上两点的最短距离"""
    diff = abs(a - b)
    return min(diff, genome_length - diff)


def compare_gene_positions(
    ncbi_features: List[Dict],
    mitoflow_features: List[Dict],
    pmga_corrections: Dict[str, List],
    species: str,
    genome_length: int = 0,
) -> Dict:
    """比较基因位置差异（使用环形距离）"""

    # 构建基因位置字典
    ncbi_pos = defaultdict(list)
    mito_pos = defaultdict(list)

    for f in ncbi_features:
        if f['gene'] and f['type'] == 'CDS':
            ncbi_pos[f['gene']].append(f)

    for f in mitoflow_features:
        if f['gene'] and f['type'] == 'CDS':
            mito_pos[f['gene']].append(f)

    # 计算偏差
    position_diffs = []

    common_genes = set(ncbi_pos.keys()) & set(mito_pos.keys())

    for gene in common_genes:
        ncbi_list = ncbi_pos[gene]
        mito_list = mito_pos[gene]

        if len(ncbi_list) == 1 and len(mito_list) == 1:
            # 单CDS基因，直接比较
            ncbi_f = ncbi_list[0]
            mito_f = mito_list[0]
            start_diff = circular_offset(mito_f['start'], ncbi_f['start'], genome_length) if genome_length else abs(mito_f['start'] - ncbi_f['start'])
            end_diff = circular_offset(mito_f['end'], ncbi_f['end'], genome_length) if genome_length else abs(mito_f['end'] - ncbi_f['end'])
            max_diff = max(start_diff, end_diff)
        else:
            # 多CDS基因：逐exon按start排序后配对比较
            ncbi_sorted = sorted(ncbi_list, key=lambda f: f['start'])
            mito_sorted = sorted(mito_list, key=lambda f: f['start'])

            pair_max_diffs = []
            start_diffs = []
            end_diffs = []
            for n_f, m_f in zip(ncbi_sorted, mito_sorted):
                sdiff = circular_offset(m_f['start'], n_f['start'], genome_length) if genome_length else abs(m_f['start'] - n_f['start'])
                ediff = circular_offset(m_f['end'], n_f['end'], genome_length) if genome_length else abs(m_f['end'] - n_f['end'])
                pair_max_diffs.append(max(sdiff, ediff))
                start_diffs.append(sdiff)
                end_diffs.append(ediff)

            if pair_max_diffs:
                max_diff = max(pair_max_diffs)
                # 起始/终止偏差用第一个和最后一个exon的边界
                start_diff = start_diffs[0]
                end_diff = end_diffs[-1]
            else:
                max_diff = 0
                start_diff = 0
                end_diff = 0

        # 分类偏差级别
        if max_diff < 50:
            diff_level = "precise"
        elif max_diff < 100:
            diff_level = "small"
        elif max_diff < 1000:
            diff_level = "medium"
        else:
            diff_level = "large"

        # 检查是否有PMGA修正
        pmga_correction = pmga_corrections.get(gene, [])
        has_correction = len(pmga_correction) > 0

        # 报告位置：单CDS用自身，多CDS用第一个exon
        if len(ncbi_list) == 1 and len(mito_list) == 1:
            ncbi_start = ncbi_list[0]['start']
            ncbi_end = ncbi_list[0]['end']
            mito_start = mito_list[0]['start']
            mito_end = mito_list[0]['end']
        else:
            ncbi_start = ncbi_sorted[0]['start'] if ncbi_list else 0
            ncbi_end = ncbi_sorted[-1]['end'] if ncbi_list else 0
            mito_start = mito_sorted[0]['start'] if mito_list else 0
            mito_end = mito_sorted[-1]['end'] if mito_list else 0

        position_diffs.append({
            'gene': gene,
            'ncbi_start': ncbi_start,
            'ncbi_end': ncbi_end,
            'mito_start': mito_start,
            'mito_end': mito_end,
            'start_diff': start_diff,
            'end_diff': end_diff,
            'max_diff': max_diff,
            'diff_level': diff_level,
            'has_pmga_correction': has_correction,
            'pmga_correction_type': pmga_correction[0]['type'] if pmga_correction else None,
        })

    return position_diffs


def calculate_metrics(
    ncbi_genes: set,
    mitoflow_genes: set,
    core_genes: set = set(CORE_PCG_41)
) -> Dict:
    """计算基因检出指标"""

    # 全基因集合比较
    tp = len(ncbi_genes & mitoflow_genes)  # 共有基因
    fp = len(mitoflow_genes - ncbi_genes)  # MitoFlow独有（可能是误检）
    fn = len(ncbi_genes - mitoflow_genes)  # NCBI独有（漏检）

    # 基因总数（假设所有NCBI基因都是真实存在的）
    total_real = len(ncbi_genes)

    # 计算指标
    if tp + fp + fn == 0:
        accuracy = sensitivity = precision = f1 = 0
    else:
        accuracy = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        f1 = 2 * precision * sensitivity / (precision + sensitivity) if (precision + sensitivity) > 0 else 0

    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

    # 核心基因统计
    core_tp = len(set(core_genes) & ncbi_genes & mitoflow_genes)
    core_fn = len(set(core_genes) & ncbi_genes - mitoflow_genes)
    core_detected_ncbi = len(set(core_genes) & ncbi_genes)
    core_detected_mito = len(set(core_genes) & mitoflow_genes)

    return {
        'tp': tp,
        'fp': fp,
        'fn': fn,
        'accuracy': accuracy,
        'sensitivity': sensitivity,
        'precision': precision,
        'fnr': fnr,
        'f1': f1,
        'core_detected_ncbi': core_detected_ncbi,
        'core_detected_mito': core_detected_mito,
        'core_tp': core_tp,
        'core_fn': core_fn,
    }


def count_error_types(
    ncbi_genes: set,
    mitoflow_genes: set,
    position_diffs: List[Dict]
) -> Dict:
    """统计三类错误数量"""

    # A类: 基因检出错误
    a_errors = len(ncbi_genes - mitoflow_genes) + len(mitoflow_genes - ncbi_genes)

    # B类: 起始/终止位置错误 (>50bp偏差)
    b_errors = len([d for d in position_diffs if d['start_diff'] > 50 or d['end_diff'] > 50])

    # C类: 剪接位点错误（多外显子基因位置偏差 >10bp）
    # 这里简化处理，用位置偏差>10bp且不是SSE修正的基因
    c_errors = len([d for d in position_diffs
                    if d['max_diff'] > 10
                    and not d['has_pmga_correction']])

    return {
        'a_errors': a_errors,
        'b_errors': b_errors,
        'c_errors': c_errors,
        'total_errors': a_errors + b_errors + c_errors,
    }


def validate_single_species(
    species: str,
    ncbi_files,
    mitoflow_dir: Path,
    corrections: Dict,
    prefer_gff: bool = False,
) -> Dict:
    """验证单个物种"""

    if isinstance(ncbi_files, Path):
        ncbi_files = [ncbi_files]

    # 解析NCBI原始注释（支持多文件合并）
    ncbi_features, ncbi_length = parse_genbank_features(ncbi_files, "NCBI")

    # 标准化物种名用于文件查找
    species_name = species.replace(' ', '_').replace('.', '')

    # 解析MitoFlow输出
    gff_file = mitoflow_dir / "gff" / f"{species_name}.gff"
    mitoflow_file = mitoflow_dir / "genbank" / f"{species_name}.gb"
    if not mitoflow_file.exists():
        mitoflow_file = mitoflow_dir / "genbank" / f"{species_name}.gbk"

    if prefer_gff and gff_file.exists():
        fasta_file = mitoflow_dir / "fasta" / f"{species_name}.fasta"
        if not fasta_file.exists():
            fasta_file = Path("data/gold_standard/fasta") / f"{species_name}.fasta"
        mitoflow_features, mito_length = parse_gff_features(gff_file, fasta_file)
    elif mitoflow_file.exists():
        mitoflow_features, mito_length = parse_genbank_features(mitoflow_file, "MitoFlow")
    elif gff_file.exists():
        fasta_file = mitoflow_dir / "fasta" / f"{species_name}.fasta"
        if not fasta_file.exists():
            fasta_file = Path("data/gold_standard/fasta") / f"{species_name}.fasta"
        mitoflow_features, mito_length = parse_gff_features(gff_file, fasta_file)
    else:
        logger.warning(f"MitoFlow file not found for {species_name}")
        return None

    # 提取基因集合
    ncbi_genes = {f['gene'] for f in ncbi_features if f['type'] == 'CDS' and f['gene']}
    mito_genes = {f['gene'] for f in mitoflow_features if f['type'] == 'CDS' and f['gene']}

    # 获取该物种的修正数据
    species_corrections = corrections.get(species, {})

    # 比较位置（使用环形距离）
    genome_length = ncbi_length if ncbi_length > 0 else mito_length
    position_diffs = compare_gene_positions(ncbi_features, mitoflow_features, species_corrections, species, genome_length)

    # 计算指标
    metrics = calculate_metrics(ncbi_genes, mito_genes)

    # 统计错误类型
    error_counts = count_error_types(ncbi_genes, mito_genes, position_diffs)

    return {
        'species': species,
        'genome_length_ncbi': ncbi_length,
        'genome_length_mitoflow': mito_length,
        'ncbi_genes': list(ncbi_genes),
        'mitoflow_genes': list(mito_genes),
        'metrics': metrics,
        'error_counts': error_counts,
        'position_diffs': position_diffs,
        'corrections': species_corrections,
    }


def generate_report(
    results: List[Dict],
    output_dir: Path
):
    """生成验证报告"""

    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成汇总CSV
    summary_data = []
    for r in results:
        summary_data.append({
            'species': r['species'],
            'genome_length': r['genome_length_ncbi'],
            'ncbi_genes_count': len(r['ncbi_genes']),
            'mitoflow_genes_count': len(r['mitoflow_genes']),
            'accuracy': r['metrics']['accuracy'],
            'sensitivity': r['metrics']['sensitivity'],
            'precision': r['metrics']['precision'],
            'f1': r['metrics']['f1'],
            'fnr': r['metrics']['fnr'],
            'core_detected': r['metrics']['core_detected_mito'],
            'a_errors': r['error_counts']['a_errors'],
            'b_errors': r['error_counts']['b_errors'],
            'c_errors': r['error_counts']['c_errors'],
            'total_errors': r['error_counts']['total_errors'],
        })

    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(output_dir / "validation_summary.csv", index=False)

    # 生成JSON详情
    details = {r['species']: r for r in results}
    with open(output_dir / "validation_details.json", 'w') as f:
        json.dump(details, f, indent=2)

    # 生成Markdown报告
    report_lines = []
    report_lines.append("# MitoFlow金标准验证报告\n\n")
    report_lines.append(f"验证物种数: {len(results)}\n\n")
    report_lines.append("**注: 本报告使用环形距离比较基因位置**\n\n")
    report_lines.append("---\n\n")

    # 汇总统计
    report_lines.append("## 1. 整体性能汇总\n\n")

    avg_accuracy = sum(r['metrics']['accuracy'] for r in results) / len(results)
    avg_sensitivity = sum(r['metrics']['sensitivity'] for r in results) / len(results)
    avg_f1 = sum(r['metrics']['f1'] for r in results) / len(results)

    report_lines.append(f"- 平均Accuracy: {avg_accuracy:.2%}\n")
    report_lines.append(f"- 平均Sensitivity: {avg_sensitivity:.2%}\n")
    report_lines.append(f"- 平均F1-measure: {avg_f1:.2%}\n\n")

    # 偏差统计
    all_diffs = []
    for r in results:
        all_diffs.extend(r['position_diffs'])

    precise_count = len([d for d in all_diffs if d['diff_level'] == 'precise'])
    small_count = len([d for d in all_diffs if d['diff_level'] == 'small'])
    medium_count = len([d for d in all_diffs if d['diff_level'] == 'medium'])
    large_count = len([d for d in all_diffs if d['diff_level'] == 'large'])

    report_lines.append("## 2. 位置偏差统计\n\n")
    report_lines.append(f"- 精确匹配(<50bp): {precise_count} ({precise_count/len(all_diffs):.1%})\n")
    report_lines.append(f"- 小偏差(50-100bp): {small_count} ({small_count/len(all_diffs):.1%})\n")
    report_lines.append(f"- 中偏差(100-1000bp): {medium_count} ({medium_count/len(all_diffs):.1%})\n")
    report_lines.append(f"- 大偏差(>1000bp): {large_count} ({large_count/len(all_diffs):.1%})\n\n")

    # 错误统计
    report_lines.append("## 3. 错误类型统计\n\n")
    total_a = sum(r['error_counts']['a_errors'] for r in results)
    total_b = sum(r['error_counts']['b_errors'] for r in results)
    total_c = sum(r['error_counts']['c_errors'] for r in results)

    report_lines.append(f"- A类错误（基因检出）: {total_a}\n")
    report_lines.append(f"- B类错误（位置偏差）: {total_b}\n")
    report_lines.append(f"- C类错误（剪接位点）: {total_c}\n\n")

    # 各物种详情
    report_lines.append("## 4. 各物种验证详情\n\n")
    for r in results:
        report_lines.append(f"### {r['species']}\n\n")
        report_lines.append(f"- Accuracy: {r['metrics']['accuracy']:.2%}\n")
        report_lines.append(f"- F1: {r['metrics']['f1']:.2%}\n")
        report_lines.append(f"- A/B/C错误: {r['error_counts']['a_errors']}/{r['error_counts']['b_errors']}/{r['error_counts']['c_errors']}\n\n")

        # 列出位置偏差>50bp的基因
        large_diffs = [d for d in r['position_diffs'] if d['max_diff'] > 50]
        if large_diffs:
            report_lines.append("**位置偏差>50bp的基因:**\n")
            for d in sorted(large_diffs, key=lambda x: -x['max_diff'])[:10]:
                report_lines.append(f"- {d['gene']}: 偏差{d['max_diff']}bp ({d['diff_level']})\n")
            report_lines.append("\n")

    # 写入文件
    with open(output_dir / "validation_report.md", 'w') as f:
        f.writelines(report_lines)

    logger.info(f"报告已生成: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description='MitoFlow金标准验证')
    parser.add_argument('--ncbi-dir', required=True, help='NCBI GenBank文件目录')
    parser.add_argument('--mitoflow-dir', required=True, help='MitoFlow输出目录')
    parser.add_argument('--corrections', required=True, help='PMGA修正数据CSV文件')
    parser.add_argument('--output', required=True, help='输出目录')
    parser.add_argument('--species-list', required=True, help='物种列表CSV文件')
    parser.add_argument('--prefer-gff', action='store_true', help='优先使用GFF文件而非GenBank')

    args = parser.parse_args()

    ncbi_dir = Path(args.ncbi_dir)
    mitoflow_base = Path(args.mitoflow_dir)
    corrections_file = Path(args.corrections)
    output_dir = Path(args.output)
    species_file = Path(args.species_list)
    prefer_gff = args.prefer_gff

    # 加载修正数据
    logger.info("加载PMGA修正数据...")
    corrections = load_corrections(corrections_file)
    logger.info(f"加载 {len(corrections)} 个物种的修正数据")

    # 加载物种列表
    species_df = pd.read_csv(species_file)
    species_list = species_df['species'].tolist()

    logger.info(f"待验证物种: {len(species_list)}")

    # 执行验证
    results = []
    for species in species_list:
        # 标准化物种名（处理空格和特殊字符）
        species_name = species.replace(' ', '_').replace('.', '')

        # 查找NCBI文件
        genbank_acc = species_df[species_df['species'] == species]['genbank'].iloc[0]
        # GenBank可能有多个编号（分号分隔）
        gb_files = []
        for acc in genbank_acc.split(';'):
            acc = acc.strip()
            gb_file = ncbi_dir / f"{acc}.gb"
            if gb_file.exists():
                gb_files.append(gb_file)

        if not gb_files:
            logger.warning(f"NCBI文件未找到: {species} ({genbank_acc})")
            continue

        # MitoFlow输出目录
        mitoflow_dir = mitoflow_base / species_name

        if not mitoflow_dir.exists():
            logger.warning(f"MitoFlow目录未找到: {species_name}")
            continue

        logger.info(f"验证: {species}")
        result = validate_single_species(species, gb_files, mitoflow_dir, corrections, prefer_gff=prefer_gff)

        if result:
            results.append(result)

    # 生成报告
    logger.info("生成验证报告...")
    generate_report(results, output_dir)

    # 输出汇总
    print("\n=== 验证完成 ===")
    print(f"验证物种数: {len(results)}")

    if results:
        avg_f1 = sum(r['metrics']['f1'] for r in results) / len(results)
        print(f"平均F1-measure: {avg_f1:.2%}")

        all_diffs = []
        for r in results:
            all_diffs.extend(r['position_diffs'])
        small_diff_rate = len([d for d in all_diffs if d['max_diff'] < 100]) / len(all_diffs)
        print(f"小偏差率(<100bp): {small_diff_rate:.1%}")


if __name__ == '__main__':
    main()