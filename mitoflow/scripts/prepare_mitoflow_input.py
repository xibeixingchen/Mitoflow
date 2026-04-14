#!/usr/bin/env python3
"""
准备MitoFlow输入文件

从GenBank文件提取FASTA序列，用于MitoFlow注释

输入: data/gold_standard/genbank/*.gb
输出: data/gold_standard/fasta/*.fasta
"""

import argparse
import logging
from pathlib import Path
from Bio import SeqIO
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def extract_fasta_from_genbank(genbank_file: Path, output_file: Path) -> bool:
    """从GenBank文件提取FASTA序列

    Args:
        genbank_file: GenBank输入文件
        output_file: FASTA输出文件

    Returns:
        成功返回True
    """
    try:
        record = SeqIO.read(genbank_file, "genbank")

        # 使用物种名作为序列ID
        organism = record.annotations.get('organism', genbank_file.stem)
        species_name = organism.replace(' ', '_').replace('.', '')

        # 创建FASTA记录
        fasta_record = SeqIO.SeqRecord(
            record.seq,
            id=species_name,
            description=f"{organism} mitochondrial genome ({len(record.seq)} bp)"
        )

        SeqIO.write(fasta_record, output_file, "fasta")
        logger.info(f"✓ {genbank_file.name} -> {output_file.name}")
        return True

    except Exception as e:
        logger.error(f"✗ {genbank_file}: {e}")
        return False


def merge_multi_chromosome(genbank_files: list, output_file: Path, species_name: str) -> bool:
    """合并多染色体GenBank文件为单个FASTA

    Args:
        genbank_files: 多个GenBank文件列表
        output_file: 合并后的FASTA输出
        species_name: 物种名

    Returns:
        成功返回True
    """
    try:
        sequences = []
        for gb_file in genbank_files:
            record = SeqIO.read(gb_file, "genbank")
            sequences.append(record.seq)

        # 合并序列
        merged_seq = "".join(str(s) for s in sequences)

        # 创建FASTA记录
        fasta_record = SeqIO.SeqRecord(
            merged_seq,
            id=species_name,
            description=f"{species_name} mitochondrial genome merged ({len(merged_seq)} bp)"
        )

        SeqIO.write(fasta_record, output_file, "fasta")
        logger.info(f"✓ 合并 {len(genbank_files)} 个文件 -> {output_file.name}")
        return True

    except Exception as e:
        logger.error(f"✗ 合并失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='准备MitoFlow输入FASTA文件')
    parser.add_argument('--genbank-dir', required=True, help='GenBank文件目录')
    parser.add_argument('--species-list', required=True, help='物种列表CSV文件')
    parser.add_argument('--output', required=True, help='FASTA输出目录')

    args = parser.parse_args()

    genbank_dir = Path(args.genbank_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 读取物种列表
    species_df = pd.read_csv(args.species_list)

    logger.info(f"物种列表: {len(species_df)} 个")
    logger.info(f"GenBank目录: {genbank_dir}")
    logger.info(f"输出目录: {output_dir}")

    success_count = 0
    fail_count = 0

    # 处理每个物种
    for row in species_df.itertuples():
        species = row.species
        genbank = row.genbank

        # 标准化物种名
        species_name = species.replace(' ', '_').replace('.', '')

        # 获取所有GenBank编号
        accessions = [acc.strip() for acc in genbank.split(';')]

        # 查找对应的GenBank文件
        gb_files = []
        for acc in accessions:
            gb_file = genbank_dir / f"{acc}.gb"
            if gb_file.exists():
                gb_files.append(gb_file)

        if not gb_files:
            logger.warning(f"未找到GenBank文件: {species}")
            fail_count += 1
            continue

        # 输出文件
        output_file = output_dir / f"{species_name}.fasta"

        # 根据文件数量选择处理方式
        if len(gb_files) == 1:
            # 单文件：直接提取
            if extract_fasta_from_genbank(gb_files[0], output_file):
                success_count += 1
            else:
                fail_count += 1
        else:
            # 多文件：合并
            if merge_multi_chromosome(gb_files, output_file, species_name):
                success_count += 1
            else:
                fail_count += 1

    # 汇总
    logger.info("=" * 50)
    logger.info(f"完成: 成功 {success_count}, 失败 {fail_count}")
    logger.info(f"输出目录: {output_dir}")


if __name__ == '__main__':
    main()