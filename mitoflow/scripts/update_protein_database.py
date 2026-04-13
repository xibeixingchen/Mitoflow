#!/usr/bin/env python3
"""
从线粒体基因组GenBank文件提取高质量参考蛋白序列
"""

import argparse
import csv
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq
import warnings

# 过滤Biopython警告
try:
    from Bio import BiopythonParserWarning
    warnings.filterwarnings("ignore", category=BiopythonParserWarning)
except ImportError:
    pass
warnings.filterwarnings("ignore", category=UserWarning)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# 目标基因列表（问题和核心基因）
TARGET_GENES = set([
    # 问题基因（优先）
    "rpl16", "rps1", "atp6", "rpl2", "ccmfc",
    # 其他核心基因
    "nad1", "nad2", "nad3", "nad4", "nad4l", "nad5", "nad6", "nad7", "nad9",
    "cox1", "cox2", "cox3", "cob",
    "atp1", "atp4", "atp8", "atp9",
    "ccmb", "ccmc", "ccmfn",
    "rpl5", "rpl10", "rps2", "rps3", "rps4", "rps7", "rps10",
    "rps12", "rps13", "rps14", "rps19",
    "matr", "mttb", "sdh3", "sdh4"
])

# RNA编辑起始密码子例外（ACG→M）
RNA_EDIT_START_CODONS = {
    "cox1": {"ACG", "M"},
    "nad1": {"ACG", "M"},
    "nad4l": {"ACG", "M"},
    "rps10": {"ACG", "M"},
    "mttb": {"ATA", "M"},
    "rpl16": {"GTG", "M"},  # GTG可作为起始
}

# 质量控制参数
MIN_LENGTH = 50  # 最小氨基酸长度
MAX_LENGTH = 2500  # 最大氨基酸长度
SIMILARITY_THRESHOLD = 0.95  # 去冗余阈值

# 基因特异性最小长度（过滤截断序列）
GENE_MIN_LENGTHS = {
    "rpl16": 150,  # 正常rpl16应该>=150aa
    "rps1": 140,   # 正常rps1应该>=140aa
    "rpl2": 280,   # 正常rpl2应该>=280aa
    "atp6": 200,   # 正常atp6应该>=200aa
    "rps3": 180,   # 正常rps3应该>=180aa
}


def load_refseq_info(csv_file: Path) -> Dict[str, bool]:
    """从CSV加载RefSeq信息"""
    refseq_status = {}
    with open(csv_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            organism = row['organism']
            is_refseq = row['is_refseq'] == 'TRUE'
            refseq_status[organism] = is_refseq
    return refseq_status


def normalize_gene_name(name: str) -> str:
    """标准化基因名称"""
    if not name:
        return ""
    name = name.lower().strip()
    # 处理别名
    aliases = {
        "ccmfn": "ccmfn",
        "ccmfc": "ccmfc",
        "ccmfc1": "ccmfc",
        "ccmfc2": "ccmfc",
        "nad4l": "nad4l",
        "matr": "matr",
        "mttb": "mttb",
    }
    return aliases.get(name, name)


def is_valid_protein(seq: str, gene_name: str) -> bool:
    """检查蛋白序列完整性"""
    # 使用基因特异性最小长度
    min_len = GENE_MIN_LENGTHS.get(gene_name, MIN_LENGTH)
    if len(seq) < min_len or len(seq) > MAX_LENGTH:
        logger.debug(f"{gene_name}: 长度{len(seq)}不在范围{min_len}-{MAX_LENGTH}内")
        return False

    # 检查起始密码子
    allowed_starts = RNA_EDIT_START_CODONS.get(gene_name, {"M"})
    first_aa = seq[0].upper()
    if first_aa not in allowed_starts:
        logger.debug(f"{gene_name}: 赴始不是有效密码子 ({first_aa})")
        return False

    # 检查终止密码子（某些可能没有*标记）
    last_aa = seq[-1].upper()
    if last_aa != '*' and last_aa not in {'*', 'M', 'L', 'S', 'A', 'V'}:
        # 不强制要求终止符，但记录警告
        pass

    return True


def extract_proteins_from_genbank(
    gb_file: Path,
    gene_set: Set[str]
) -> Dict[str, List[SeqRecord]]:
    """从GenBank文件提取蛋白序列"""
    proteins = defaultdict(list)

    try:
        rec = SeqIO.read(gb_file, "genbank")
        organism = rec.annotations.get('organism', gb_file.stem.replace('_mito', ''))

        for feat in rec.features:
            if feat.type != "CDS":
                continue

            if 'gene' not in feat.qualifiers:
                continue

            gene_name = normalize_gene_name(feat.qualifiers['gene'][0])
            if gene_name not in gene_set:
                continue

            # 提取翻译序列
            if 'translation' not in feat.qualifiers:
                continue

            seq = feat.qualifiers['translation'][0]

            # 检查完整性
            if not is_valid_protein(seq, gene_name):
                continue

            # 创建SeqRecord
            # 使用物种名+基因名作为ID
            seq_id = f"{organism.replace(' ', '_')}_{gene_name}"
            record = SeqRecord(
                Seq(seq),
                id=seq_id,
                description=f"{organism} {gene_name} ({len(seq)}aa)"
            )
            proteins[gene_name].append(record)

    except Exception as e:
        logger.warning(f"解析 {gb_file} 失败: {e}")

    return proteins


def remove_redundant_sequences(
    sequences: List[SeqRecord],
    threshold: float = SIMILARITY_THRESHOLD
) -> List[SeqRecord]:
    """去除高度相似的冗余序列"""
    if len(sequences) <= 1:
        return sequences

    # 按长度排序，保留较长序列
    sequences.sort(key=lambda x: len(x.seq), reverse=True)

    kept = []
    for seq in sequences:
        is_redundant = False
        for kept_seq in kept:
            # 简单相似度计算：比对长度/最大长度
            min_len = min(len(seq.seq), len(kept_seq.seq))
            max_len = max(len(seq.seq), len(kept_seq.seq))

            # 精确匹配前min_len个字符
            matches = sum(1 for a, b in zip(seq.seq[:min_len], kept_seq.seq[:min_len]) if a == b)
            similarity = matches / max_len

            if similarity >= threshold:
                is_redundant = True
                break

        if not is_redundant:
            kept.append(seq)

    return kept


def main():
    parser = argparse.ArgumentParser(description='从线粒体基因组提取参考蛋白序列')
    parser.add_argument('--genbank-dir', required=True, help='GenBank文件目录')
    parser.add_argument('--info-csv', required=True, help='基因组信息CSV文件')
    parser.add_argument('--output-dir', required=True, help='输出FASTA目录')
    parser.add_argument('--refseq-only', action='store_true', help='仅使用RefSeq序列')
    parser.add_argument('--max-per-gene', type=int, default=100, help='每个基因最大序列数')
    parser.add_argument('--genes', nargs='+', default=None, help='指定基因列表')

    args = parser.parse_args()

    genbank_dir = Path(args.genbank_dir)
    info_csv = Path(args.info_csv)
    output_dir = Path(args.output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载RefSeq信息
    refseq_info = load_refseq_info(info_csv)
    logger.info(f"加载 {len(refseq_info)} 个物种信息")
    refseq_count = sum(1 for v in refseq_info.values() if v)
    logger.info(f"其中 RefSeq: {refseq_count} 个")

    # 确定目标基因
    target_genes = set(args.genes) if args.genes else TARGET_GENES
    logger.info(f"目标基因: {len(target_genes)} 个")

    # 统计
    all_proteins = defaultdict(list)
    processed_count = 0
    refseq_used_count = 0

    # 遍历GenBank文件
    for gb_file in genbank_dir.glob('*.gb'):
        # 从文件名推断物种
        species_name = gb_file.stem.replace('_mito', '').replace('_', ' ')

        # RefSeq过滤
        if args.refseq_only:
            # 检查物种是否为RefSeq
            is_refseq = refseq_info.get(species_name, False)
            if not is_refseq:
                continue
            refseq_used_count += 1

        # 提取蛋白
        proteins = extract_proteins_from_genbank(gb_file, target_genes)

        for gene, records in proteins.items():
            all_proteins[gene].extend(records)

        processed_count += 1
        if processed_count % 50 == 0:
            logger.info(f"已处理 {processed_count} 个文件...")

    logger.info(f"处理完成: {processed_count} 个文件 (RefSeq: {refseq_used_count})")

    # 去冗余并写入文件
    for gene in target_genes:
        sequences = all_proteins.get(gene, [])
        if not sequences:
            logger.warning(f"基因 {gene} 未找到序列")
            continue

        # 去冗余
        unique_seqs = remove_redundant_sequences(sequences)

        # 限制数量
        unique_seqs = unique_seqs[:args.max_per_gene]

        # 写入FASTA
        output_file = output_dir / f"{gene}.Protein.fasta"
        SeqIO.write(unique_seqs, output_file, 'fasta')

        # 统计长度分布
        lengths = [len(s.seq) for s in unique_seqs]
        min_len, max_len = min(lengths), max(lengths)

        logger.info(f"{gene}: {len(unique_seqs)} 条序列, 长度范围 {min_len}-{max_len}aa")

    # 总结
    logger.info("=" * 50)
    logger.info("数据库更新完成!")
    logger.info(f"输出目录: {output_dir}")

    # 重点报告问题基因
    problem_genes = ["rpl16", "rps1", "atp6", "rpl2", "ccmfc"]
    logger.info("\n问题基因改进情况:")
    for gene in problem_genes:
        seqs = all_proteins.get(gene, [])
        if seqs:
            lengths = [len(s.seq) for s in remove_redundant_sequences(seqs)]
            logger.info(f"  {gene}: {len(lengths)} 条序列, 长度 {min(lengths)}-{max(lengths)}aa")


if __name__ == '__main__':
    main()