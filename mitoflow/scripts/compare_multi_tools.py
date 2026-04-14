#!/usr/bin/env python3
"""
多软件比较脚本

比较多种线粒体注释工具的性能：
- NCBI原始注释
- MitoFlow
- AGORA
- GeSeq
- MFannot
- PMGA修正版

输出：
- 各软件性能对比表（Accuracy/Sensitivity/F1）
- 基因检出详情
- 问题基因识别

对标PMGA论文Table S6
"""

import argparse
import json
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple
from Bio import SeqIO
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# 41核心PCG基因列表
CORE_PCG_41 = [
    "nad1", "nad2", "nad3", "nad4", "nad4l", "nad5", "nad6", "nad7", "nad9",
    "cob", "cox1", "cox2", "cox3",
    "atp1", "atp4", "atp6", "atp8", "atp9",
    "ccmb", "ccmc", "ccmfc", "ccmfn",
    "rpl2", "rpl5", "rpl10", "rpl16",
    "rps1", "rps2", "rps3", "rps4", "rps7", "rps10", "rps12", "rps13", "rps14", "rps19",
    "matr", "mttb", "sdh3", "sdh4",
]


def normalize_gene_name(name: str) -> str:
    """标准化基因名称"""
    if not name:
        return ""
    name = name.lower().strip()
    name = name.split(".")[0]
    # 处理别名
    aliases = {
        "ccmfn": "ccmfn",
        "ccmfc": "ccmfc",
        "ccmfc1": "ccmfc",
        "ccmfc2": "ccmfc",
        "nad4l": "nad4l",
        "matr": "matr",
        "mttb": "mttb",
        "rpl2": "rpl2",
        "rpl5": "rpl5",
        "rpl10": "rpl10",
        "rpl16": "rpl16",
    }
    return aliases.get(name, name)


def parse_genbank_features(gb_file: Path, source_name: str = "") -> Tuple[List[Dict], int]:
    """解析GenBank文件，提取基因特征"""
    try:
        record = SeqIO.read(gb_file, "genbank")
    except Exception as e:
        logger.warning(f"Error reading {gb_file}: {e}")
        return [], 0

    features = []
    genome_length = len(record.seq)

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
            features.append({
                'type': feat.type,
                'gene': gene_name,
                'start': int(feat.location.start),
                'end': int(feat.location.end),
                'strand': feat.location.strand,
                'product': feat.qualifiers.get('product', [''])[0],
                'source': source_name,
            })

    return features, genome_length


def parse_mfannot_tbl(tbl_file: Path, source_name: str = "MFannot") -> Tuple[List[Dict], int]:
    """解析MFannot TBL格式文件

    MFannot TBL格式示例:
    >Feature C_0 Table1
    782	363	gene
                    gene	orf139
    6264	7154	CDS
                    gene	cox2
    """
    features = []
    genome_length = 0
    current_gene = ""

    try:
        with open(tbl_file, 'r') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 跳过头部行
            if line.startswith('>Feature') or line.startswith('>genome'):
                if 'len=' in line:
                    for p in line.split():
                        if p.startswith('len='):
                            genome_length = int(p.split('=')[1])
                i += 1
                continue

            # 解析坐标行 (start end feature_type)
            parts = line.split('\t') if '\t' in line else line.split()
            if len(parts) >= 3:
                try:
                    start = int(parts[0])
                    end = int(parts[1])
                    feat_type = parts[2]

                    if feat_type in ['gene', 'CDS']:
                        # 查找下一行的gene名称
                        gene_name = ""
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            if '\tgene\t' in next_line or 'gene\t' in next_line:
                                gene_parts = next_line.split('\t')
                                for idx, p in enumerate(gene_parts):
                                    if p == 'gene' and idx + 1 < len(gene_parts):
                                        gene_name = normalize_gene_name(gene_parts[idx + 1])
                                        break

                        strand = 1 if start < end else -1

                        features.append({
                            'type': feat_type,
                            'gene': gene_name,
                            'start': min(start, end),
                            'end': max(start, end),
                            'strand': strand,
                            'product': '',
                            'source': source_name,
                        })
                except ValueError:
                    pass

            i += 1

    except Exception as e:
        logger.warning(f"Error reading MFannot TBL {tbl_file}: {e}")

    return features, genome_length


def calculate_metrics(detected_genes: Set, reference_genes: Set, core_genes: Set) -> Dict:
    """计算性能指标"""
    # 基因检出比较
    tp = len(reference_genes & detected_genes)
    fp = len(detected_genes - reference_genes)  # 假阳性
    fn = len(reference_genes - detected_genes)  # 漏检

    # 计算指标
    total = tp + fp + fn
    accuracy = tp / total if total > 0 else 0
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    f1 = 2 * precision * sensitivity / (precision + sensitivity) if (precision + sensitivity) > 0 else 0

    # 核心基因统计
    core_tp = len(core_genes & reference_genes & detected_genes)
    core_fn = len(core_genes & reference_genes - detected_genes)

    return {
        'tp': tp,
        'fp': fp,
        'fn': fn,
        'accuracy': accuracy,
        'sensitivity': sensitivity,
        'precision': precision,
        'f1': f1,
        'core_tp': core_tp,
        'core_fn': core_fn,
        'detected_count': len(detected_genes),
        'reference_count': len(reference_genes),
    }


def compare_positions(features1: List[Dict], features2: List[Dict]) -> List[Dict]:
    """比较基因位置差异"""
    # 构建基因位置字典
    pos1 = defaultdict(list)
    pos2 = defaultdict(list)

    for f in features1:
        if f['gene'] and f['type'] == 'CDS':
            pos1[f['gene']].append(f)

    for f in features2:
        if f['gene'] and f['type'] == 'CDS':
            pos2[f['gene']].append(f)

    position_diffs = []
    common_genes = set(pos1.keys()) & set(pos2.keys())

    for gene in common_genes:
        f1 = pos1[gene][0]
        f2 = pos2[gene][0]

        start_diff = abs(f2['start'] - f1['start'])
        end_diff = abs(f2['end'] - f1['end'])
        max_diff = max(start_diff, end_diff)

        if max_diff < 50:
            level = "precise"
        elif max_diff < 100:
            level = "small"
        elif max_diff < 1000:
            level = "medium"
        else:
            level = "large"

        position_diffs.append({
            'gene': gene,
            'pos1_start': f1['start'],
            'pos1_end': f1['end'],
            'pos2_start': f2['start'],
            'pos2_end': f2['end'],
            'start_diff': start_diff,
            'end_diff': end_diff,
            'max_diff': max_diff,
            'level': level,
        })

    return position_diffs


def compare_single_species(
    species: str,
    outputs: Dict[str, Path],
    reference_source: str = "PMGA"
) -> Dict:
    """比较单个物种的多软件输出"""

    results = {}

    # 解析各软件输出
    for tool, filepath in outputs.items():
        if filepath.suffix == '.tbl':
            features, genome_len = parse_mfannot_tbl(filepath, tool)
        else:
            features, genome_len = parse_genbank_features(filepath, tool)

        genes = {f['gene'] for f in features if f['type'] == 'CDS' and f['gene']}
        core_genes = set(CORE_PCG_41)

        results[tool] = {
            'features': features,
            'genome_length': genome_len,
            'genes': genes,
            'core_genes': set(core_genes) & genes,
            'gene_count': len(genes),
            'core_count': len(set(core_genes) & genes),
        }

    # 使用指定参考源作为金标准
    reference_genes = results.get(reference_source, {}).get('genes', set())
    core_genes = set(CORE_PCG_41) & reference_genes

    # 计算各软件指标
    metrics = {}
    for tool, data in results.items():
        m = calculate_metrics(data['genes'], reference_genes, core_genes)
        metrics[tool] = m

        # 计算与参考的位置差异
        if reference_source in results:
            pos_diffs = compare_positions(
                results[reference_source]['features'],
                data['features']
            )
            m['position_diffs'] = pos_diffs
            m['precise_count'] = len([d for d in pos_diffs if d['level'] == 'precise'])
            m['small_diff_count'] = len([d for d in pos_diffs if d['level'] == 'small'])
            m['large_diff_count'] = len([d for d in pos_diffs if d['level'] == 'large'])

    return {
        'species': species,
        'results': results,
        'metrics': metrics,
        'reference_source': reference_source,
    }


def generate_comparison_report(comparison_data: List[Dict], output_dir: Path):
    """生成比较报告"""

    output_dir.mkdir(parents=True, exist_ok=True)

    # 汇总表
    summary_data = []
    for cd in comparison_data:
        species = cd['species']
        for tool, m in cd['metrics'].items():
            summary_data.append({
                'species': species,
                'tool': tool,
                'accuracy': m['accuracy'],
                'sensitivity': m['sensitivity'],
                'precision': m['precision'],
                'f1': m['f1'],
                'tp': m['tp'],
                'fp': m['fp'],
                'fn': m['fn'],
                'gene_count': m['detected_count'],
                'core_count': m.get('core_tp', 0),
                'precise_match': m.get('precise_count', 0),
                'large_diff': m.get('large_diff_count', 0),
            })

    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(output_dir / "tool_comparison_summary.csv", index=False)

    # 各软件平均性能
    tool_avg = summary_df.groupby('tool').agg({
        'accuracy': 'mean',
        'sensitivity': 'mean',
        'precision': 'mean',
        'f1': 'mean',
        'gene_count': 'mean',
    }).round(4)

    # Markdown报告
    report_lines = []
    report_lines.append("# 多软件比较报告\n\n")
    report_lines.append(f"验证物种数: {len(comparison_data)}\n\n")
    report_lines.append("---\n\n")

    report_lines.append("## 1. 各软件平均性能\n\n")
    report_lines.append("| 软件 | Accuracy | Sensitivity | F1 | 平均基因检出数 |\n")
    report_lines.append("|------|----------|-------------|-----|---------------|\n")

    for tool in ['PMGA', 'NCBI', 'GeSeq', 'AGORA', 'MFannot', 'MitoFlow']:
        if tool in tool_avg.index:
            row = tool_avg.loc[tool]
            report_lines.append(f"| {tool} | {row['accuracy']:.2%} | {row['sensitivity']:.2%} | {row['f1']:.2%} | {int(row['gene_count'])} |\n")

    report_lines.append("\n## 2. 各物种详情\n\n")

    for cd in comparison_data:
        species = cd['species']
        report_lines.append(f"### {species}\n\n")

        report_lines.append("| 软件 | F1 | 检出基因 | 精确匹配 | 大偏差 |\n")
        report_lines.append("|------|-----|---------|---------|--------|\n")

        for tool in ['PMGA', 'NCBI', 'GeSeq', 'AGORA', 'MFannot', 'MitoFlow']:
            if tool in cd['metrics']:
                m = cd['metrics'][tool]
                report_lines.append(f"| {tool} | {m['f1']:.2%} | {m['detected_count']} | {m.get('precise_count', '-')} | {m.get('large_diff_count', '-')} |\n")

        report_lines.append("\n")

    # 写入文件
    with open(output_dir / "multi_tool_comparison.md", 'w') as f:
        f.writelines(report_lines)

    # JSON详情
    details = {cd['species']: cd for cd in comparison_data}
    with open(output_dir / "gene_level_comparison.json", 'w') as f:
        json.dump(details, f, indent=2, default=str)

    logger.info(f"报告已生成: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description='多软件比较脚本')
    parser.add_argument('--species', required=True, help='物种名称')
    parser.add_argument('--ncbi', help='NCBI GenBank文件')
    parser.add_argument('--mitoflow-dir', help='MitoFlow输出目录')
    parser.add_argument('--mitoflow-gb', help='MitoFlow GenBank文件（直接指定）')
    parser.add_argument('--agora', help='AGORA GenBank文件')
    parser.add_argument('--geseq', help='GeSeq GenBank文件')
    parser.add_argument('--mfannot', help='MFannot TBL文件')
    parser.add_argument('--pmga', help='PMGA修正版GenBank文件')
    parser.add_argument('--reference', default='PMGA', help='参考源（PMGA或NCBI）')
    parser.add_argument('--output', required=True, help='输出目录')

    args = parser.parse_args()

    outputs = {}

    # 收集各软件输出
    if args.ncbi:
        outputs['NCBI'] = Path(args.ncbi)
    if args.mitoflow_gb:
        outputs['MitoFlow'] = Path(args.mitoflow_gb)
    elif args.mitoflow_dir:
        # 在目录中查找GenBank文件
        mito_dir = Path(args.mitoflow_dir)
        gb_file = mito_dir / "genbank" / f"{args.species.replace(' ', '_')}.gb"
        if gb_file.exists():
            outputs['MitoFlow'] = gb_file
    if args.agora:
        outputs['AGORA'] = Path(args.agora)
    if args.geseq:
        outputs['GeSeq'] = Path(args.geseq)
    if args.mfannot:
        outputs['MFannot'] = Path(args.mfannot)
    if args.pmga:
        outputs['PMGA'] = Path(args.pmga)

    if not outputs:
        logger.error("未提供任何软件输出文件")
        return

    logger.info(f"比较软件: {list(outputs.keys())}")
    logger.info(f"参考源: {args.reference}")

    # 执行比较
    comparison = compare_single_species(args.species, outputs, args.reference)

    # 生成报告
    output_dir = Path(args.output)
    generate_comparison_report([comparison], output_dir)

    # 输出汇总
    print("\n=== 多软件比较结果 ===")
    print(f"物种: {args.species}")
    print(f"参考源: {args.reference}")

    metrics = comparison['metrics']
    print("\n各软件性能:")
    for tool, m in sorted(metrics.items(), key=lambda x: -x[1]['f1']):
        print(f"  {tool}: F1={m['f1']:.2%}, Accuracy={m['accuracy']:.2%}, 基因={m['detected_count']}")


if __name__ == '__main__':
    main()