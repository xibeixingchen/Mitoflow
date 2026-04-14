# MitoFlow金标准验证报告

验证物种数: 27

---

## 1. 整体性能汇总

- 平均Accuracy: 71.86%
- 平均Sensitivity: 92.94%
- 平均F1-measure: 79.51%

## 2. 位置偏差统计

- 精确匹配(<50bp): 511 (66.0%)
- 小偏差(50-100bp): 91 (11.8%)
- 中偏差(100-1000bp): 83 (10.7%)
- 大偏差(>1000bp): 89 (11.5%)

## 3. 错误类型统计

- A类错误（基因检出）: 444
- B类错误（位置偏差）: 263
- C类错误（剪接位点）: 417

## 4. 各物种验证详情

### Arabidopsis thaliana

- Accuracy: 83.33%
- F1: 90.91%
- A/B/C错误: 6/5/15

**位置偏差>50bp的基因:**
- nad5: 偏差123500bp (large)
- ccmfc: 偏差19027bp (large)
- cox2: 偏差1408bp (large)
- nad7: 偏差150bp (medium)
- rps7: 偏差69bp (small)

### Raphanus sativus

- Accuracy: 78.95%
- F1: 88.24%
- A/B/C错误: 8/7/14

**位置偏差>50bp的基因:**
- nad1: 偏差180482bp (large)
- atp9: 偏差61696bp (large)
- cox2: 偏差1413bp (large)
- atp6: 偏差522bp (medium)
- rps14: 偏差168bp (medium)
- nad7: 偏差150bp (medium)
- atp1: 偏差57bp (small)

### Camellia sinensis var. assamica

- Accuracy: 21.05%
- F1: 34.78%
- A/B/C错误: 30/4/3

**位置偏差>50bp的基因:**
- atp9: 偏差743001bp (large)
- nad1: 偏差456377bp (large)
- rps19: 偏差384643bp (large)
- rps14: 偏差168bp (medium)

### Glycine max

- Accuracy: 30.11%
- F1: 46.28%
- A/B/C错误: 65/9/13

**位置偏差>50bp的基因:**
- nad5: 偏差239585bp (large)
- nad2: 偏差185090bp (large)
- nad1: 偏差177188bp (large)
- cox2: 偏差1400bp (large)
- rps10: 偏差960bp (medium)
- nad7: 偏差213bp (medium)
- rps14: 偏差174bp (medium)
- rpl16: 偏差111bp (medium)
- ccmfn: 偏差60bp (small)

### Liriodendron tulipifera

- Accuracy: 95.35%
- F1: 97.62%
- A/B/C错误: 2/18/26

**位置偏差>50bp的基因:**
- nad2: 偏差334611bp (large)
- nad1: 偏差149926bp (large)
- ccmfc: 偏差73917bp (large)
- cox2: 偏差2280bp (large)
- rps10: 偏差1047bp (large)
- rps14: 偏差168bp (medium)
- nad7: 偏差141bp (medium)
- cob: 偏差120bp (medium)
- nad6: 偏差120bp (medium)
- rps11: 偏差114bp (medium)

### Malus x domestica

- Accuracy: 83.33%
- F1: 90.91%
- A/B/C错误: 6/8/13

**位置偏差>50bp的基因:**
- cox2: 偏差1262bp (large)
- sdh4: 偏差702bp (medium)
- nad7: 偏差141bp (medium)
- rps14: 偏差105bp (medium)
- cox3: 偏差102bp (medium)
- ccmfn: 偏差96bp (small)
- rpl5: 偏差81bp (small)
- cox1: 偏差72bp (small)

### Ipomoea aquatica

- Accuracy: 100.00%
- F1: 100.00%
- A/B/C错误: 0/14/20

**位置偏差>50bp的基因:**
- nad2: 偏差219073bp (large)
- nad5: 偏差141754bp (large)
- ccmfc: 偏差9119bp (large)
- cox2: 偏差1400bp (large)
- matr: 偏差1131bp (large)
- rps10: 偏差998bp (medium)
- rpl5: 偏差609bp (medium)
- rps14: 偏差168bp (medium)
- nad7: 偏差150bp (medium)
- rpl16: 偏差111bp (medium)

### Capsicum annuum cultivar Jeju

- Accuracy: 17.39%
- F1: 29.63%
- A/B/C错误: 152/10/14

**位置偏差>50bp的基因:**
- nad5: 偏差324167bp (large)
- ccmfc: 偏差320598bp (large)
- nad2: 偏差256584bp (large)
- nad1: 偏差201363bp (large)
- rpl2: 偏差2038bp (large)
- cox2: 偏差1400bp (large)
- rps10: 偏差960bp (medium)
- atp6: 偏差492bp (medium)
- nad7: 偏差150bp (medium)
- rpl16: 偏差81bp (small)

### Nicotiana tabacum 

- Accuracy: 76.19%
- F1: 86.49%
- A/B/C错误: 10/9/18

**位置偏差>50bp的基因:**
- nad2: 偏差177027bp (large)
- nad5: 偏差174677bp (large)
- rpl2: 偏差1981bp (large)
- cox2: 偏差1409bp (large)
- rps10: 偏差888bp (medium)
- atp6: 偏差384bp (medium)
- nad7: 偏差150bp (medium)
- rps14: 偏差105bp (medium)
- ccmfn: 偏差63bp (small)

### Punica granatum

- Accuracy: 100.00%
- F1: 100.00%
- A/B/C错误: 0/13/24

**位置偏差>50bp的基因:**
- nad2: 偏差265313bp (large)
- nad5: 偏差122216bp (large)
- ccmfc: 偏差121149bp (large)
- cox2: 偏差1890bp (large)
- rps10: 偏差978bp (medium)
- cob: 偏差717bp (medium)
- rps14: 偏差168bp (medium)
- rpl2: 偏差82bp (small)
- nad7: 偏差75bp (small)
- rps7: 偏差69bp (small)

### Lagenaria siceraria

- Accuracy: 92.68%
- F1: 96.20%
- A/B/C错误: 3/14/23

**位置偏差>50bp的基因:**
- atp9: 偏差151783bp (large)
- ccmfc: 偏差57498bp (large)
- cox2: 偏差1870bp (large)
- rps10: 偏差900bp (medium)
- rpl2: 偏差402bp (medium)
- rpl16: 偏差123bp (medium)
- nad9: 偏差90bp (small)
- sdh4: 偏差87bp (small)
- cox3: 偏差84bp (small)
- nad7: 偏差75bp (small)

### Cardiocrinum giganteum

- Accuracy: 10.26%
- F1: 18.60%
- A/B/C错误: 35/3/4

**位置偏差>50bp的基因:**
- cox2: 偏差1394bp (large)
- rps10: 偏差879bp (medium)
- rps13: 偏差66bp (small)

### Solanum muricatum

- Accuracy: 100.00%
- F1: 100.00%
- A/B/C错误: 0/10/17

**位置偏差>50bp的基因:**
- nad1: 偏差343470bp (large)
- ccmfc: 偏差238042bp (large)
- cox2: 偏差1400bp (large)
- rps10: 偏差921bp (medium)
- atp6: 偏差270bp (medium)
- nad7: 偏差150bp (medium)
- rps1: 偏差129bp (medium)
- rpl16: 偏差123bp (medium)
- rps14: 偏差111bp (medium)
- ccmc: 偏差99bp (small)

### Ribes nigrum

- Accuracy: 94.87%
- F1: 97.37%
- A/B/C错误: 2/8/17

**位置偏差>50bp的基因:**
- nad5: 偏差376212bp (large)
- cox2: 偏差1963bp (large)
- rps10: 偏差909bp (medium)
- rps14: 偏差168bp (medium)
- nad7: 偏差150bp (medium)
- cox3: 偏差84bp (small)
- ccmfn: 偏差63bp (small)
- nad6: 偏差54bp (small)

### Aglaia odorata

- Accuracy: 97.22%
- F1: 98.59%
- A/B/C错误: 1/14/20

**位置偏差>50bp的基因:**
- nad1: 偏差328916bp (large)
- nad2: 偏差292338bp (large)
- nad5: 偏差30232bp (large)
- cox2: 偏差2104bp (large)
- rps10: 偏差900bp (medium)
- rpl16: 偏差123bp (medium)
- cox3: 偏差102bp (medium)
- atp9: 偏差81bp (small)
- nad7: 偏差75bp (small)
- atp4: 偏差72bp (small)

### Pontederia crassipes

- Accuracy: 94.74%
- F1: 97.30%
- A/B/C错误: 2/13/21

**位置偏差>50bp的基因:**
- nad1: 偏差337251bp (large)
- nad5: 偏差281063bp (large)
- rpl2: 偏差2226bp (large)
- cox2: 偏差1400bp (large)
- rps10: 偏差882bp (medium)
- rps2: 偏差363bp (medium)
- rps14: 偏差168bp (medium)
- rpl16: 偏差123bp (medium)
- nad7: 偏差75bp (small)
- rps1: 偏差75bp (small)

### Selenicereus monacanthus

- Accuracy: 86.11%
- F1: 92.54%
- A/B/C错误: 5/11/16

**位置偏差>50bp的基因:**
- nad5: 偏差1243190bp (large)
- nad9: 偏差1242169bp (large)
- nad1: 偏差1050835bp (large)
- nad2: 偏差907106bp (large)
- nad7: 偏差709181bp (large)
- ccmb: 偏差540415bp (large)
- ccmfc: 偏差433751bp (large)
- atp9: 偏差150298bp (large)
- cox2: 偏差1400bp (large)
- nad6: 偏差75bp (small)

### Quercus acutissima

- Accuracy: 43.24%
- F1: 60.38%
- A/B/C错误: 21/6/9

**位置偏差>50bp的基因:**
- nad4: 偏差14501bp (large)
- cox2: 偏差3705bp (large)
- rpl2: 偏差1119bp (large)
- atp6: 偏差186bp (medium)
- rpl5: 偏差81bp (small)
- nad7: 偏差75bp (small)

### Paeonia lactiflora

- Accuracy: 87.50%
- F1: 93.33%
- A/B/C错误: 4/15/17

**位置偏差>50bp的基因:**
- nad2: 偏差78072bp (large)
- nad4: 偏差41843bp (large)
- ccmfc: 偏差4116bp (large)
- cox2: 偏差1400bp (large)
- nad7: 偏差141bp (medium)
- rps4: 偏差123bp (medium)
- cox3: 偏差111bp (medium)
- nad9: 偏差90bp (small)
- atp6: 偏差90bp (small)
- rpl5: 偏差81bp (small)

### Astragalus membranaceus

- Accuracy: 50.00%
- F1: 66.67%
- A/B/C错误: 17/9/15

**位置偏差>50bp的基因:**
- nad1: 偏差117726bp (large)
- nad4: 偏差30345bp (large)
- cox2: 偏差1470bp (large)
- mttb: 偏差111bp (medium)
- rps4: 偏差84bp (small)
- rps14: 偏差84bp (small)
- ccmfc: 偏差78bp (small)
- nad7: 偏差75bp (small)
- matr: 偏差63bp (small)

### Syzygium samarangense

- Accuracy: 94.87%
- F1: 97.37%
- A/B/C错误: 2/13/18

**位置偏差>50bp的基因:**
- nad2: 偏差94391bp (large)
- cox2: 偏差1367bp (large)
- rpl2: 偏差943bp (medium)
- rps10: 偏差879bp (medium)
- atp6: 偏差357bp (medium)
- rpl16: 偏差309bp (medium)
- rps14: 偏差168bp (medium)
- sdh4: 偏差141bp (medium)
- rps4: 偏差105bp (medium)
- cox3: 偏差78bp (small)

### Eucommia ulmoides

- Accuracy: 80.00%
- F1: 88.89%
- A/B/C错误: 8/11/21

**位置偏差>50bp的基因:**
- nad1: 偏差29334bp (large)
- cox2: 偏差1523bp (large)
- rps10: 偏差942bp (medium)
- rpl16: 偏差309bp (medium)
- rps14: 偏差168bp (medium)
- nad7: 偏差129bp (medium)
- nad5: 偏差77bp (small)
- rpl5: 偏差75bp (small)
- rps7: 偏差69bp (small)
- sdh4: 偏差57bp (small)

### Angelica dahurica

- Accuracy: 25.71%
- F1: 40.91%
- A/B/C错误: 26/4/6

**位置偏差>50bp的基因:**
- nad5: 偏差114259bp (large)
- nad1: 偏差81025bp (large)
- cox2: 偏差1307bp (large)
- rpl16: 偏差123bp (medium)

### Rehmannia glutinosa

- Accuracy: 79.49%
- F1: 88.57%
- A/B/C错误: 8/8/17

**位置偏差>50bp的基因:**
- nad2: 偏差418302bp (large)
- nad1: 偏差187003bp (large)
- cox2: 偏差3509bp (large)
- rps10: 偏差984bp (medium)
- atp6: 偏差237bp (medium)
- rps14: 偏差168bp (medium)
- nad7: 偏差90bp (small)
- ccmfn: 偏差63bp (small)

### Populus tomentosa

- Accuracy: 89.19%
- F1: 94.29%
- A/B/C错误: 4/9/13

**位置偏差>50bp的基因:**
- nad5: 偏差427752bp (large)
- ccmfc: 偏差9536bp (large)
- cox2: 偏差1471bp (large)
- rpl2: 偏差366bp (medium)
- nad1: 偏差88bp (small)
- rps14: 偏差84bp (small)
- nad7: 偏差75bp (small)
- rps7: 偏差69bp (small)
- mttb: 偏差57bp (small)

### Colocasia esculenta

- Accuracy: 39.47%
- F1: 56.60%
- A/B/C错误: 23/7/7

**位置偏差>50bp的基因:**
- cox2: 偏差1769bp (large)
- rps14: 偏差168bp (medium)
- nad7: 偏差150bp (medium)
- rps1: 偏差96bp (small)
- cox3: 偏差78bp (small)
- ccmfc: 偏差66bp (small)
- sdh4: 偏差57bp (small)

### Gossypium hirsutum

- Accuracy: 89.19%
- F1: 94.29%
- A/B/C错误: 4/11/16

**位置偏差>50bp的基因:**
- cox2: 偏差1570bp (large)
- rps10: 偏差954bp (medium)
- rps14: 偏差144bp (medium)
- rpl5: 偏差129bp (medium)
- rpl16: 偏差123bp (medium)
- cox3: 偏差102bp (medium)
- rpl10: 偏差96bp (small)
- mttb: 偏差84bp (small)
- nad7: 偏差75bp (small)
- rps7: 偏差69bp (small)

