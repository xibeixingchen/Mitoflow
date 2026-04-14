# MitoFlow金标准验证报告

验证物种数: 27

---

## 1. 整体性能汇总

- 平均Accuracy: 71.96%
- 平均Sensitivity: 93.04%
- 平均F1-measure: 79.56%

## 2. 位置偏差统计

- 精确匹配(<50bp): 549 (70.8%)
- 小偏差(50-100bp): 117 (15.1%)
- 中偏差(100-1000bp): 54 (7.0%)
- 大偏差(>1000bp): 55 (7.1%)

## 3. 错误类型统计

- A类错误（基因检出）: 443
- B类错误（位置偏差）: 226
- C类错误（剪接位点）: 393

## 4. 各物种验证详情

### Arabidopsis thaliana

- Accuracy: 83.33%
- F1: 90.91%
- A/B/C错误: 6/4/15

**位置偏差>50bp的基因:**
- ccmfc: 偏差19027bp (large)
- cox2: 偏差1408bp (large)
- nad7: 偏差75bp (small)
- rps7: 偏差69bp (small)

### Raphanus sativus

- Accuracy: 78.95%
- F1: 88.24%
- A/B/C错误: 8/6/14

**位置偏差>50bp的基因:**
- atp9: 偏差61696bp (large)
- cox2: 偏差1413bp (large)
- atp6: 偏差522bp (medium)
- rps14: 偏差84bp (small)
- nad7: 偏差75bp (small)
- atp1: 偏差57bp (small)

### Camellia sinensis var. assamica

- Accuracy: 21.05%
- F1: 34.78%
- A/B/C错误: 30/4/3

**位置偏差>50bp的基因:**
- atp9: 偏差743001bp (large)
- rps19: 偏差384643bp (large)
- nad1: 偏差177326bp (large)
- rps14: 偏差84bp (small)

### Glycine max

- Accuracy: 30.11%
- F1: 46.28%
- A/B/C错误: 65/7/12

**位置偏差>50bp的基因:**
- nad7: 偏差138bp (medium)
- rpl16: 偏差111bp (medium)
- rps14: 偏差90bp (small)
- cox2: 偏差73bp (small)
- nad5: 偏差60bp (small)
- rps10: 偏差60bp (small)
- ccmfn: 偏差60bp (small)

### Liriodendron tulipifera

- Accuracy: 95.35%
- F1: 97.62%
- A/B/C错误: 2/17/25

**位置偏差>50bp的基因:**
- ccmfc: 偏差73917bp (large)
- nad1: 偏差23137bp (large)
- cox2: 偏差2280bp (large)
- rps10: 偏差982bp (medium)
- nad6: 偏差120bp (medium)
- cob: 偏差120bp (medium)
- rps11: 偏差114bp (medium)
- rpl16: 偏差111bp (medium)
- rps7: 偏差96bp (small)
- rpl5: 偏差93bp (small)

### Malus x domestica

- Accuracy: 83.33%
- F1: 90.91%
- A/B/C错误: 6/7/13

**位置偏差>50bp的基因:**
- sdh4: 偏差702bp (medium)
- cox2: 偏差138bp (medium)
- cox3: 偏差102bp (medium)
- ccmfn: 偏差96bp (small)
- rpl5: 偏差81bp (small)
- cox1: 偏差72bp (small)
- nad7: 偏差66bp (small)

### Ipomoea aquatica

- Accuracy: 100.00%
- F1: 100.00%
- A/B/C错误: 0/12/19

**位置偏差>50bp的基因:**
- ccmfc: 偏差9119bp (large)
- matr: 偏差1131bp (large)
- rps10: 偏差998bp (medium)
- rpl5: 偏差609bp (medium)
- rpl16: 偏差111bp (medium)
- atp6: 偏差102bp (medium)
- rps14: 偏差84bp (small)
- nad9: 偏差75bp (small)
- nad7: 偏差75bp (small)
- cox2: 偏差71bp (small)

### Capsicum annuum cultivar Jeju

- Accuracy: 17.39%
- F1: 29.63%
- A/B/C错误: 152/7/12

**位置偏差>50bp的基因:**
- ccmfc: 偏差320598bp (large)
- rpl2: 偏差2038bp (large)
- rps10: 偏差887bp (medium)
- atp6: 偏差492bp (medium)
- rpl16: 偏差81bp (small)
- nad7: 偏差75bp (small)
- cox2: 偏差56bp (small)

### Nicotiana tabacum 

- Accuracy: 76.19%
- F1: 86.49%
- A/B/C错误: 10/8/18

**位置偏差>50bp的基因:**
- nad5: 偏差174677bp (large)
- rpl2: 偏差1981bp (large)
- rps10: 偏差888bp (medium)
- atp6: 偏差384bp (medium)
- nad2: 偏差90bp (small)
- nad7: 偏差75bp (small)
- cox2: 偏差71bp (small)
- ccmfn: 偏差63bp (small)

### Punica granatum

- Accuracy: 100.00%
- F1: 100.00%
- A/B/C错误: 0/12/23

**位置偏差>50bp的基因:**
- nad5: 偏差262923bp (large)
- ccmfc: 偏差121149bp (large)
- nad2: 偏差95384bp (large)
- cox2: 偏差1890bp (large)
- cob: 偏差717bp (medium)
- rps10: 偏差102bp (medium)
- rps14: 偏差84bp (small)
- rpl2: 偏差82bp (small)
- rps7: 偏差69bp (small)
- rps19: 偏差60bp (small)

### Lagenaria siceraria

- Accuracy: 92.68%
- F1: 96.20%
- A/B/C错误: 3/12/22

**位置偏差>50bp的基因:**
- atp9: 偏差151783bp (large)
- ccmfc: 偏差57498bp (large)
- cox2: 偏差1870bp (large)
- rpl2: 偏差402bp (medium)
- rpl16: 偏差123bp (medium)
- nad9: 偏差90bp (small)
- sdh4: 偏差87bp (small)
- cox3: 偏差84bp (small)
- rps7: 偏差69bp (small)
- ccmfn: 偏差63bp (small)

### Cardiocrinum giganteum

- Accuracy: 10.26%
- F1: 18.60%
- A/B/C错误: 35/3/4

**位置偏差>50bp的基因:**
- cox2: 偏差965bp (medium)
- rps10: 偏差811bp (medium)
- rps13: 偏差66bp (small)

### Solanum muricatum

- Accuracy: 100.00%
- F1: 100.00%
- A/B/C错误: 0/8/16

**位置偏差>50bp的基因:**
- ccmfc: 偏差238042bp (large)
- rps10: 偏差921bp (medium)
- atp6: 偏差270bp (medium)
- rps1: 偏差129bp (medium)
- rpl16: 偏差123bp (medium)
- ccmc: 偏差99bp (small)
- nad7: 偏差75bp (small)
- cox2: 偏差56bp (small)

### Ribes nigrum

- Accuracy: 97.44%
- F1: 98.70%
- A/B/C错误: 1/6/16

**位置偏差>50bp的基因:**
- cox2: 偏差1963bp (large)
- rps14: 偏差84bp (small)
- cox3: 偏差84bp (small)
- nad7: 偏差75bp (small)
- ccmfn: 偏差63bp (small)
- nad6: 偏差54bp (small)

### Aglaia odorata

- Accuracy: 97.22%
- F1: 98.59%
- A/B/C错误: 1/10/17

**位置偏差>50bp的基因:**
- nad5: 偏差30232bp (large)
- cox2: 偏差2104bp (large)
- rpl16: 偏差123bp (medium)
- cox3: 偏差102bp (medium)
- atp9: 偏差81bp (small)
- atp4: 偏差72bp (small)
- mttb: 偏差69bp (small)
- rps12: 偏差69bp (small)
- ccmfn: 偏差63bp (small)
- nad6: 偏差54bp (small)

### Pontederia crassipes

- Accuracy: 94.74%
- F1: 97.30%
- A/B/C错误: 2/10/19

**位置偏差>50bp的基因:**
- rpl2: 偏差2226bp (large)
- rps10: 偏差838bp (medium)
- rps2: 偏差363bp (medium)
- rpl16: 偏差123bp (medium)
- rps14: 偏差84bp (small)
- rps1: 偏差75bp (small)
- rps13: 偏差72bp (small)
- cox2: 偏差64bp (small)
- mttb: 偏差63bp (small)
- rps4: 偏差51bp (small)

### Selenicereus monacanthus

- Accuracy: 86.11%
- F1: 92.54%
- A/B/C错误: 5/10/15

**位置偏差>50bp的基因:**
- nad9: 偏差1242169bp (large)
- nad5: 偏差1066137bp (large)
- nad2: 偏差907106bp (large)
- nad7: 偏差709256bp (large)
- ccmb: 偏差540415bp (large)
- ccmfc: 偏差433751bp (large)
- atp9: 偏差150298bp (large)
- cox2: 偏差1385bp (large)
- nad6: 偏差75bp (small)
- mttb: 偏差69bp (small)

### Quercus acutissima

- Accuracy: 43.24%
- F1: 60.38%
- A/B/C错误: 21/5/8

**位置偏差>50bp的基因:**
- nad4: 偏差14501bp (large)
- cox2: 偏差3705bp (large)
- rpl2: 偏差1119bp (large)
- atp6: 偏差186bp (medium)
- rpl5: 偏差81bp (small)

### Paeonia lactiflora

- Accuracy: 87.50%
- F1: 93.33%
- A/B/C错误: 4/15/17

**位置偏差>50bp的基因:**
- nad2: 偏差78072bp (large)
- nad4: 偏差41843bp (large)
- ccmfc: 偏差4116bp (large)
- rps4: 偏差123bp (medium)
- cox3: 偏差111bp (medium)
- nad9: 偏差90bp (small)
- atp6: 偏差90bp (small)
- rpl5: 偏差81bp (small)
- mttb: 偏差69bp (small)
- rpl16: 偏差66bp (small)

### Astragalus membranaceus

- Accuracy: 50.00%
- F1: 66.67%
- A/B/C错误: 17/7/13

**位置偏差>50bp的基因:**
- nad1: 偏差223212bp (large)
- nad4: 偏差30345bp (large)
- mttb: 偏差111bp (medium)
- rps4: 偏差84bp (small)
- ccmfc: 偏差78bp (small)
- cox2: 偏差71bp (small)
- matr: 偏差63bp (small)

### Syzygium samarangense

- Accuracy: 94.87%
- F1: 97.37%
- A/B/C错误: 2/11/16

**位置偏差>50bp的基因:**
- nad2: 偏差94391bp (large)
- cox2: 偏差1367bp (large)
- rpl2: 偏差943bp (medium)
- atp6: 偏差357bp (medium)
- rpl16: 偏差309bp (medium)
- sdh4: 偏差141bp (medium)
- rps4: 偏差105bp (medium)
- rps14: 偏差84bp (small)
- cox3: 偏差78bp (small)
- ccmfn: 偏差66bp (small)

### Eucommia ulmoides

- Accuracy: 80.00%
- F1: 88.89%
- A/B/C错误: 8/11/21

**位置偏差>50bp的基因:**
- nad1: 偏差245697bp (large)
- rps10: 偏差942bp (medium)
- rpl16: 偏差309bp (medium)
- cox2: 偏差123bp (medium)
- rps14: 偏差84bp (small)
- nad5: 偏差77bp (small)
- rpl5: 偏差75bp (small)
- rps7: 偏差69bp (small)
- sdh4: 偏差57bp (small)
- atp6: 偏差54bp (small)

### Angelica dahurica

- Accuracy: 25.71%
- F1: 40.91%
- A/B/C错误: 26/4/6

**位置偏差>50bp的基因:**
- nad5: 偏差114259bp (large)
- nad1: 偏差81025bp (large)
- cox2: 偏差1023bp (large)
- rpl16: 偏差123bp (medium)

### Rehmannia glutinosa

- Accuracy: 79.49%
- F1: 88.57%
- A/B/C错误: 8/6/16

**位置偏差>50bp的基因:**
- nad1: 偏差270613bp (large)
- cox2: 偏差3509bp (large)
- rps10: 偏差917bp (medium)
- atp6: 偏差237bp (medium)
- rps14: 偏差84bp (small)
- ccmfn: 偏差63bp (small)

### Populus tomentosa

- Accuracy: 89.19%
- F1: 94.29%
- A/B/C错误: 4/7/11

**位置偏差>50bp的基因:**
- ccmfc: 偏差9536bp (large)
- rpl2: 偏差366bp (medium)
- nad1: 偏差88bp (small)
- cox2: 偏差71bp (small)
- rps7: 偏差69bp (small)
- nad5: 偏差60bp (small)
- mttb: 偏差57bp (small)

### Colocasia esculenta

- Accuracy: 39.47%
- F1: 56.60%
- A/B/C错误: 23/7/7

**位置偏差>50bp的基因:**
- cox2: 偏差1769bp (large)
- rps1: 偏差96bp (small)
- rps14: 偏差84bp (small)
- cox3: 偏差78bp (small)
- nad7: 偏差75bp (small)
- ccmfc: 偏差66bp (small)
- sdh4: 偏差57bp (small)

### Gossypium hirsutum

- Accuracy: 89.19%
- F1: 94.29%
- A/B/C错误: 4/10/15

**位置偏差>50bp的基因:**
- cox2: 偏差1570bp (large)
- rps10: 偏差915bp (medium)
- rpl5: 偏差129bp (medium)
- rpl16: 偏差123bp (medium)
- cox3: 偏差102bp (medium)
- rpl10: 偏差96bp (small)
- mttb: 偏差84bp (small)
- rps7: 偏差69bp (small)
- rps14: 偏差60bp (small)
- sdh3: 偏差57bp (small)

