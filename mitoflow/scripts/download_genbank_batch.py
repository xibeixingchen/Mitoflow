#!/usr/bin/env python3
"""
批量下载NCBI GenBank文件

使用Biopython Entrez模块下载金标准物种的线粒体基因组GenBank文件

输入: species_list.csv
输出: data/gold_standard/genbank/*.gb
"""

import argparse
import logging
import time
from pathlib import Path
from Bio import Entrez, SeqIO
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# 设置NCBI邮箱（NCBI要求提供邮箱）
Entrez.email = "noreply@example.com"
Entrez.tool = "MitoFlowValidation"


def download_genbank(accession: str, output_file: Path, max_retries: int = 3) -> bool:
    """下载单个GenBank文件

    Args:
        accession: GenBank编号
        output_file: 输出文件路径
        max_retries: 最大重试次数

    Returns:
        成功返回True，失败返回False
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"下载 {accession} (尝试 {attempt + 1}/{max_retries})")

            # 使用Entrez.efetch获取GenBank记录
            handle = Entrez.efetch(
                db="nucleotide",
                id=accession,
                rettype="gb",
                retmode="text"
            )

            # 读取并保存记录
            record = SeqIO.read(handle, "genbank")
            handle.close()

            # 写入文件
            SeqIO.write(record, output_file, "genbank")

            logger.info(f"✓ 成功下载: {accession} -> {output_file}")
            return True

        except Exception as e:
            logger.warning(f"下载失败 {accession}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)  # 等待5秒后重试
            else:
                logger.error(f"✗ 下载失败 {accession}，已达最大重试次数")
                return False

    return False


def main():
    parser = argparse.ArgumentParser(description='批量下载NCBI GenBank文件')
    parser.add_argument('--species-list', required=True, help='物种列表CSV文件')
    parser.add_argument('--output', required=True, help='输出目录')
    parser.add_argument('--limit', type=int, default=0, help='限制下载数量（0=全部）')
    parser.add_argument('--delay', type=float, default=0.5, help='请求间隔秒数（避免API限制）')

    args = parser.parse_args()

    species_file = Path(args.species_list)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 读取物种列表
    df = pd.read_csv(species_file)

    logger.info(f"物种列表: {len(df)} 个")
    logger.info(f"输出目录: {output_dir}")

    # 收集所有GenBank编号
    all_accessions = []
    for row in df.itertuples():
        genbank = row.genbank
        # 处理多个编号（分号分隔）
        for acc in genbank.split(';'):
            acc = acc.strip()
            if acc:
                all_accessions.append((row.species, acc))

    logger.info(f"总GenBank编号: {len(all_accessions)} 个")

    # 限制数量
    if args.limit > 0:
        all_accessions = all_accessions[:args.limit]
        logger.info(f"限制下载: {args.limit} 个")

    # 执行下载
    success_count = 0
    fail_count = 0
    failed_accessions = []

    for i, (species, accession) in enumerate(all_accessions):
        logger.info(f"\n--- [{i+1}/{len(all_accessions)}] {species} ---")

        # 处理多个编号的情况
        species_name = species.replace(' ', '_').replace('.', '')
        output_file = output_dir / f"{accession}.gb"

        # 检查是否已存在
        if output_file.exists():
            logger.info(f"文件已存在: {output_file}")
            success_count += 1
            continue

        # 下载
        if download_genbank(accession, output_file):
            success_count += 1
        else:
            fail_count += 1
            failed_accessions.append((species, accession))

        # API限制：每秒不超过3个请求
        time.sleep(args.delay)

    # 汇总
    logger.info("\n" + "=" * 50)
    logger.info("下载完成汇总:")
    logger.info(f"  成功: {success_count}")
    logger.info(f"  失败: {fail_count}")

    if failed_accessions:
        logger.info("\n失败的编号:")
        for species, acc in failed_accessions:
            logger.info(f"  {species}: {acc}")

    # 记录下载日志
    log_file = output_dir / "download_log.txt"
    with open(log_file, 'w') as f:
        f.write(f"下载时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总编号数: {len(all_accessions)}\n")
        f.write(f"成功: {success_count}\n")
        f.write(f"失败: {fail_count}\n\n")
        f.write("失败的编号:\n")
        for species, acc in failed_accessions:
            f.write(f"  {species}: {acc}\n")

    logger.info(f"日志文件: {log_file}")


if __name__ == '__main__':
    main()