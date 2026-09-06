# Readable reasoning traces - tsrbench160_glm53flash_zai

One Markdown file per instance, rendered from the authoritative raw
results under `results/tsrbench160_glm53flash_zai/`. The reasoning trace and the final
answer are copied verbatim and are never elided; regenerate with
`python make_readable_traces.py --tag tsrbench160_glm53flash_zai`.

Runs marked **no answer** ran the completion ceiling out without
emitting one. They write no result file, so they are rendered from
`failures_<cond>.jsonl`; their reasoning is whole up to the cut.
They are scored wrong in the accuracy tables.

## QA_ONLY

Question and the four orderings only - the leakage check. 160 of 160 instances rendered, 39 correct, 0 never answered.

| instance | gold | predicted | | reasoning chars |
|---|---|---|---|---|
| [1](qa_only/1.md) | A | B | x | 1,670 |
| [2](qa_only/2.md) | A | A | ok | 1,509 |
| [3](qa_only/3.md) | D | A | x | 3,789 |
| [4](qa_only/4.md) | B | A | x | 1,563 |
| [5](qa_only/5.md) | A | C | x | 1,468 |
| [6](qa_only/6.md) | A | C | x | 2,540 |
| [7](qa_only/7.md) | D | A | x | 2,382 |
| [8](qa_only/8.md) | A | C | x | 1,079 |
| [9](qa_only/9.md) | B | B | ok | 1,656 |
| [10](qa_only/10.md) | C | A | x | 1,205 |
| [11](qa_only/11.md) | A | A | ok | 1,341 |
| [12](qa_only/12.md) | D | A | x | 1,624 |
| [13](qa_only/13.md) | C | C | ok | 1,385 |
| [14](qa_only/14.md) | D | A | x | 2,031 |
| [15](qa_only/15.md) | C | C | ok | 1,916 |
| [16](qa_only/16.md) | C | A | x | 2,101 |
| [17](qa_only/17.md) | B | A | x | 1,417 |
| [18](qa_only/18.md) | B | A | x | 1,137 |
| [19](qa_only/19.md) | D | A | x | 1,272 |
| [20](qa_only/20.md) | D | A | x | 1,659 |
| [21](qa_only/21.md) | D | A | x | 1,183 |
| [22](qa_only/22.md) | A | C | x | 1,878 |
| [23](qa_only/23.md) | D | A | x | 1,436 |
| [24](qa_only/24.md) | B | C | x | 1,521 |
| [25](qa_only/25.md) | C | B | x | 1,599 |
| [26](qa_only/26.md) | D | B | x | 1,714 |
| [27](qa_only/27.md) | D | B | x | 2,473 |
| [28](qa_only/28.md) | A | C | x | 1,961 |
| [29](qa_only/29.md) | B | B | ok | 2,075 |
| [30](qa_only/30.md) | B | C | x | 1,648 |
| [31](qa_only/31.md) | D | C | x | 1,919 |
| [32](qa_only/32.md) | B | B | ok | 2,370 |
| [33](qa_only/33.md) | B | C | x | 1,875 |
| [34](qa_only/34.md) | D | A | x | 1,568 |
| [35](qa_only/35.md) | A | A | ok | 1,273 |
| [36](qa_only/36.md) | D | C | x | 2,244 |
| [37](qa_only/37.md) | A | A | ok | 1,101 |
| [38](qa_only/38.md) | A | D | x | 1,424 |
| [39](qa_only/39.md) | B | A | x | 1,445 |
| [40](qa_only/40.md) | D | D | ok | 1,468 |
| [41](qa_only/41.md) | B | A | x | 1,816 |
| [42](qa_only/42.md) | A | A | ok | 990 |
| [43](qa_only/43.md) | D | C | x | 1,748 |
| [44](qa_only/44.md) | B | A | x | 2,138 |
| [45](qa_only/45.md) | D | B | x | 1,579 |
| [46](qa_only/46.md) | C | B | x | 1,816 |
| [47](qa_only/47.md) | A | B | x | 1,693 |
| [48](qa_only/48.md) | B | B | ok | 2,226 |
| [49](qa_only/49.md) | B | C | x | 1,426 |
| [50](qa_only/50.md) | D | A | x | 4,590 |
| [51](qa_only/51.md) | B | B | ok | 1,888 |
| [52](qa_only/52.md) | B | A | x | 1,377 |
| [53](qa_only/53.md) | C | B | x | 946 |
| [54](qa_only/54.md) | C | A | x | 1,438 |
| [55](qa_only/55.md) | B | B | ok | 1,316 |
| [56](qa_only/56.md) | C | A | x | 1,500 |
| [57](qa_only/57.md) | B | B | ok | 1,981 |
| [58](qa_only/58.md) | A | A | ok | 1,398 |
| [59](qa_only/59.md) | B | D | x | 1,366 |
| [60](qa_only/60.md) | A | A | ok | 1,577 |
| [61](qa_only/61.md) | B | A | x | 1,343 |
| [62](qa_only/62.md) | B | C | x | 1,685 |
| [63](qa_only/63.md) | B | C | x | 2,562 |
| [64](qa_only/64.md) | B | B | ok | 1,510 |
| [65](qa_only/65.md) | B | C | x | 1,552 |
| [66](qa_only/66.md) | B | C | x | 1,622 |
| [67](qa_only/67.md) | A | A | ok | 1,442 |
| [68](qa_only/68.md) | C | B | x | 1,745 |
| [69](qa_only/69.md) | C | C | ok | 1,424 |
| [70](qa_only/70.md) | A | D | x | 1,910 |
| [71](qa_only/71.md) | D | D | ok | 1,173 |
| [72](qa_only/72.md) | D | B | x | 1,413 |
| [73](qa_only/73.md) | A | A | ok | 1,271 |
| [74](qa_only/74.md) | B | A | x | 1,538 |
| [75](qa_only/75.md) | A | B | x | 1,856 |
| [76](qa_only/76.md) | B | C | x | 1,602 |
| [77](qa_only/77.md) | C | C | ok | 1,498 |
| [78](qa_only/78.md) | D | C | x | 1,530 |
| [79](qa_only/79.md) | D | C | x | 1,517 |
| [80](qa_only/80.md) | B | B | ok | 2,105 |
| [81](qa_only/81.md) | A | A | ok | 1,470 |
| [82](qa_only/82.md) | B | A | x | 1,607 |
| [83](qa_only/83.md) | B | C | x | 1,410 |
| [84](qa_only/84.md) | D | A | x | 1,495 |
| [85](qa_only/85.md) | C | B | x | 1,493 |
| [86](qa_only/86.md) | A | B | x | 1,996 |
| [87](qa_only/87.md) | B | A | x | 1,362 |
| [88](qa_only/88.md) | D | C | x | 1,220 |
| [89](qa_only/89.md) | C | A | x | 3,342 |
| [90](qa_only/90.md) | D | B | x | 1,278 |
| [91](qa_only/91.md) | A | A | ok | 1,611 |
| [92](qa_only/92.md) | B | C | x | 1,296 |
| [93](qa_only/93.md) | C | A | x | 1,919 |
| [94](qa_only/94.md) | C | B | x | 1,708 |
| [95](qa_only/95.md) | B | A | x | 1,180 |
| [96](qa_only/96.md) | B | A | x | 1,772 |
| [97](qa_only/97.md) | B | A | x | 1,234 |
| [98](qa_only/98.md) | D | A | x | 1,640 |
| [99](qa_only/99.md) | A | B | x | 1,601 |
| [100](qa_only/100.md) | C | A | x | 1,441 |
| [101](qa_only/101.md) | D | D | ok | 2,071 |
| [102](qa_only/102.md) | A | A | ok | 1,606 |
| [103](qa_only/103.md) | D | B | x | 1,686 |
| [104](qa_only/104.md) | C | A | x | 1,088 |
| [105](qa_only/105.md) | C | A | x | 2,059 |
| [106](qa_only/106.md) | B | C | x | 1,503 |
| [107](qa_only/107.md) | D | C | x | 1,762 |
| [108](qa_only/108.md) | C | C | ok | 1,477 |
| [109](qa_only/109.md) | C | B | x | 1,250 |
| [110](qa_only/110.md) | A | A | ok | 1,811 |
| [111](qa_only/111.md) | D | B | x | 1,324 |
| [112](qa_only/112.md) | D | C | x | 1,570 |
| [113](qa_only/113.md) | C | A | x | 960 |
| [114](qa_only/114.md) | D | C | x | 2,313 |
| [115](qa_only/115.md) | A | A | ok | 1,623 |
| [116](qa_only/116.md) | D | A | x | 1,481 |
| [117](qa_only/117.md) | B | D | x | 1,520 |
| [118](qa_only/118.md) | D | A | x | 1,220 |
| [119](qa_only/119.md) | B | C | x | 1,492 |
| [120](qa_only/120.md) | C | C | ok | 1,851 |
| [121](qa_only/121.md) | B | A | x | 2,091 |
| [122](qa_only/122.md) | A | C | x | 2,314 |
| [123](qa_only/123.md) | D | A | x | 1,717 |
| [124](qa_only/124.md) | D | C | x | 2,397 |
| [125](qa_only/125.md) | D | A | x | 1,459 |
| [126](qa_only/126.md) | B | B | ok | 1,846 |
| [127](qa_only/127.md) | D | C | x | 1,681 |
| [128](qa_only/128.md) | C | A | x | 1,404 |
| [129](qa_only/129.md) | C | B | x | 2,528 |
| [130](qa_only/130.md) | B | B | ok | 1,751 |
| [131](qa_only/131.md) | C | B | x | 1,182 |
| [132](qa_only/132.md) | B | A | x | 1,506 |
| [133](qa_only/133.md) | D | A | x | 1,271 |
| [134](qa_only/134.md) | D | A | x | 1,446 |
| [135](qa_only/135.md) | A | C | x | 1,534 |
| [136](qa_only/136.md) | A | B | x | 2,706 |
| [137](qa_only/137.md) | B | C | x | 1,632 |
| [138](qa_only/138.md) | A | B | x | 2,313 |
| [139](qa_only/139.md) | C | A | x | 1,731 |
| [140](qa_only/140.md) | C | A | x | 1,440 |
| [141](qa_only/141.md) | D | A | x | 1,156 |
| [142](qa_only/142.md) | A | A | ok | 1,309 |
| [143](qa_only/143.md) | B | B | ok | 1,569 |
| [144](qa_only/144.md) | D | A | x | 1,099 |
| [145](qa_only/145.md) | D | B | x | 1,421 |
| [146](qa_only/146.md) | B | D | x | 1,642 |
| [147](qa_only/147.md) | D | C | x | 3,988 |
| [148](qa_only/148.md) | D | C | x | 5,879 |
| [149](qa_only/149.md) | D | C | x | 2,213 |
| [150](qa_only/150.md) | A | A | ok | 1,760 |
| [151](qa_only/151.md) | B | A | x | 1,670 |
| [152](qa_only/152.md) | A | B | x | 1,745 |
| [153](qa_only/153.md) | A | A | ok | 1,817 |
| [154](qa_only/154.md) | C | B | x | 1,445 |
| [155](qa_only/155.md) | B | D | x | 2,180 |
| [156](qa_only/156.md) | D | A | x | 1,627 |
| [157](qa_only/157.md) | B | C | x | 1,199 |
| [158](qa_only/158.md) | D | D | ok | 1,800 |
| [159](qa_only/159.md) | C | A | x | 2,750 |
| [160](qa_only/160.md) | D | C | x | 1,796 |

## FULL

Timestamped series + events with their times - the reference. 152 of 160 instances rendered, 83 correct, 54 never answered.

| instance | gold | predicted | | reasoning chars |
|---|---|---|---|---|
| [1](full/1.md) | A | *no answer* | x | 69,492 |
| [2](full/2.md) | A | *no answer* | x | 80,576 |
| [3](full/3.md) | D | D | ok | 43,821 |
| [4](full/4.md) | B | B | ok | 51,804 |
| [5](full/5.md) | A | *no answer* | x | 69,172 |
| [6](full/6.md) | A | A | ok | 37,325 |
| [7](full/7.md) | D | *no answer* | x | 59,674 |
| [8](full/8.md) | A | A | ok | 64,148 |
| [9](full/9.md) | B | *no answer* | x | 60,396 |
| [10](full/10.md) | C | C | ok | 26,575 |
| [11](full/11.md) | A | *no answer* | x | 57,953 |
| [12](full/12.md) | D | *no answer* | x | 51,645 |
| [13](full/13.md) | C | C | ok | 50,767 |
| [14](full/14.md) | D | A | x | 45,430 |
| [15](full/15.md) | C | *no answer* | x | 91,096 |
| [16](full/16.md) | C | A | x | 8,893 |
| [17](full/17.md) | B | *no answer* | x | 75,373 |
| [18](full/18.md) | B | B | ok | 12,574 |
| [19](full/19.md) | D | B | x | 44,474 |
| [20](full/20.md) | D | D | ok | 23,834 |
| [21](full/21.md) | D | D | ok | 34,219 |
| [22](full/22.md) | A | A | ok | 12,803 |
| [23](full/23.md) | D | D | ok | 8,096 |
| [24](full/24.md) | B | *no answer* | x | 0 |
| [25](full/25.md) | C | C | ok | 24,641 |
| [26](full/26.md) | D | A | x | 8,950 |
| [27](full/27.md) | D | B | x | 21,880 |
| [28](full/28.md) | A | A | ok | 16,417 |
| [29](full/29.md) | B | B | ok | 30,519 |
| [30](full/30.md) | B | B | ok | 46,857 |
| [31](full/31.md) | D | D | ok | 38,021 |
| [32](full/32.md) | B | *no answer* | x | 79,610 |
| [33](full/33.md) | B | B | ok | 31,176 |
| [34](full/34.md) | D | D | ok | 34,938 |
| [35](full/35.md) | A | *no answer* | x | 61,114 |
| [36](full/36.md) | D | D | ok | 33,389 |
| [37](full/37.md) | A | A | ok | 30,105 |
| [38](full/38.md) | A | A | ok | 27,926 |
| [39](full/39.md) | B | B | ok | 7,448 |
| [40](full/40.md) | D | A | x | 18,422 |
| [41](full/41.md) | B | B | ok | 17,043 |
| [42](full/42.md) | A | *no answer* | x | 63,212 |
| [43](full/43.md) | D | D | ok | 35,879 |
| [44](full/44.md) | B | B | ok | 7,745 |
| [45](full/45.md) | D | *no answer* | x | 73,632 |
| [47](full/47.md) | A | A | ok | 54,210 |
| [48](full/48.md) | B | *no answer* | x | 62,555 |
| [49](full/49.md) | B | *no answer* | x | 77,045 |
| [50](full/50.md) | D | D | ok | 58,818 |
| [51](full/51.md) | B | B | ok | 12,548 |
| [52](full/52.md) | B | B | ok | 42,541 |
| [53](full/53.md) | C | C | ok | 34,442 |
| [54](full/54.md) | C | C | ok | 40,757 |
| [55](full/55.md) | B | B | ok | 18,243 |
| [56](full/56.md) | C | *no answer* | x | 56,339 |
| [57](full/57.md) | B | *no answer* | x | 61,067 |
| [58](full/58.md) | A | *no answer* | x | 75,409 |
| [60](full/60.md) | A | A | ok | 31,318 |
| [61](full/61.md) | B | B | ok | 49,444 |
| [65](full/65.md) | B | *no answer* | x | 82,764 |
| [66](full/66.md) | B | B | ok | 27,382 |
| [68](full/68.md) | C | C | ok | 46,732 |
| [69](full/69.md) | C | C | ok | 27,186 |
| [70](full/70.md) | A | A | ok | 15,008 |
| [71](full/71.md) | D | D | ok | 31,993 |
| [73](full/73.md) | A | B | x | 42,434 |
| [74](full/74.md) | B | *no answer* | x | 56,050 |
| [75](full/75.md) | A | A | ok | 5,582 |
| [76](full/76.md) | B | B | ok | 19,113 |
| [77](full/77.md) | C | C | ok | 58,015 |
| [78](full/78.md) | D | *no answer* | x | 63,754 |
| [79](full/79.md) | D | D | ok | 17,006 |
| [80](full/80.md) | B | *no answer* | x | 63,810 |
| [81](full/81.md) | A | A | ok | 42,637 |
| [82](full/82.md) | B | *no answer* | x | 65,985 |
| [83](full/83.md) | B | C | x | 42,820 |
| [84](full/84.md) | D | D | ok | 39,471 |
| [85](full/85.md) | C | *no answer* | x | 64,112 |
| [86](full/86.md) | A | A | ok | 51,004 |
| [88](full/88.md) | D | *no answer* | x | 60,648 |
| [89](full/89.md) | C | C | ok | 9,432 |
| [90](full/90.md) | D | *no answer* | x | 61,915 |
| [91](full/91.md) | A | *no answer* | x | 58,437 |
| [92](full/92.md) | B | *no answer* | x | 70,791 |
| [93](full/93.md) | C | C | ok | 27,327 |
| [94](full/94.md) | C | A | x | 10,328 |
| [95](full/95.md) | B | B | ok | 66,954 |
| [96](full/96.md) | B | B | ok | 10,480 |
| [97](full/97.md) | B | *no answer* | x | 61,564 |
| [98](full/98.md) | D | *no answer* | x | 58,489 |
| [99](full/99.md) | A | C | x | 26,690 |
| [100](full/100.md) | C | *no answer* | x | 64,589 |
| [101](full/101.md) | D | D | ok | 19,628 |
| [102](full/102.md) | A | *no answer* | x | 66,462 |
| [103](full/103.md) | D | *no answer* | x | 57,316 |
| [104](full/104.md) | C | C | ok | 19,439 |
| [105](full/105.md) | C | *no answer* | x | 73,321 |
| [106](full/106.md) | B | B | ok | 17,026 |
| [107](full/107.md) | D | D | ok | 16,061 |
| [108](full/108.md) | C | *no answer* | x | 60,740 |
| [109](full/109.md) | C | C | ok | 17,488 |
| [110](full/110.md) | A | D | x | 7,928 |
| [111](full/111.md) | D | *no answer* | x | 78,108 |
| [112](full/112.md) | D | D | ok | 16,705 |
| [113](full/113.md) | C | *no answer* | x | 71,254 |
| [114](full/114.md) | D | D | ok | 55,410 |
| [115](full/115.md) | A | *no answer* | x | 52,822 |
| [116](full/116.md) | D | D | ok | 24,047 |
| [117](full/117.md) | B | C | x | 5,854 |
| [118](full/118.md) | D | D | ok | 8,521 |
| [119](full/119.md) | B | D | x | 35,242 |
| [120](full/120.md) | C | *no answer* | x | 65,090 |
| [121](full/121.md) | B | B | ok | 14,074 |
| [122](full/122.md) | A | A | ok | 4,862 |
| [123](full/123.md) | D | D | ok | 15,687 |
| [124](full/124.md) | D | D | ok | 35,958 |
| [125](full/125.md) | D | *no answer* | x | 82,553 |
| [126](full/126.md) | B | B | ok | 23,380 |
| [127](full/127.md) | D | *no answer* | x | 83,431 |
| [128](full/128.md) | C | C | ok | 18,673 |
| [129](full/129.md) | C | *no answer* | x | 80,737 |
| [130](full/130.md) | B | *no answer* | x | 77,211 |
| [131](full/131.md) | C | C | ok | 23,714 |
| [132](full/132.md) | B | *no answer* | x | 107,363 |
| [133](full/133.md) | D | *no answer* | x | 75,887 |
| [134](full/134.md) | D | A | x | 27,672 |
| [135](full/135.md) | A | A | ok | 67,942 |
| [136](full/136.md) | A | A | ok | 32,900 |
| [137](full/137.md) | B | *no answer* | x | 76,993 |
| [138](full/138.md) | A | A | ok | 0 |
| [139](full/139.md) | C | C | ok | 13,932 |
| [140](full/140.md) | C | C | ok | 20,337 |
| [141](full/141.md) | D | D | ok | 6,321 |
| [142](full/142.md) | A | *no answer* | x | 63,940 |
| [143](full/143.md) | B | B | ok | 8,603 |
| [144](full/144.md) | D | D | ok | 57,447 |
| [145](full/145.md) | D | D | ok | 16,867 |
| [146](full/146.md) | B | D | x | 50,649 |
| [147](full/147.md) | D | D | ok | 47,967 |
| [148](full/148.md) | D | D | ok | 36,263 |
| [149](full/149.md) | D | D | ok | 68,501 |
| [150](full/150.md) | A | *no answer* | x | 78,327 |
| [151](full/151.md) | B | B | ok | 24,987 |
| [152](full/152.md) | A | *no answer* | x | 62,012 |
| [153](full/153.md) | A | *no answer* | x | 58,702 |
| [154](full/154.md) | C | *no answer* | x | 64,502 |
| [155](full/155.md) | B | *no answer* | x | 58,189 |
| [156](full/156.md) | D | D | ok | 8,311 |
| [157](full/157.md) | B | B | ok | 25,357 |
| [158](full/158.md) | D | D | ok | 14,798 |
| [159](full/159.md) | C | *no answer* | x | 66,836 |
| [160](full/160.md) | D | D | ok | 40,636 |

## NO_TS

Every timestamp deleted, series and events. 154 of 160 instances rendered, 20 correct, 121 never answered.

| instance | gold | predicted | | reasoning chars |
|---|---|---|---|---|
| [1](no_ts/1.md) | A | *no answer* | x | 73,278 |
| [2](no_ts/2.md) | A | *no answer* | x | 77,927 |
| [3](no_ts/3.md) | D | *no answer* | x | 56,998 |
| [4](no_ts/4.md) | B | *no answer* | x | 59,663 |
| [5](no_ts/5.md) | A | *no answer* | x | 80,651 |
| [6](no_ts/6.md) | A | *no answer* | x | 79,199 |
| [7](no_ts/7.md) | D | *no answer* | x | 60,400 |
| [8](no_ts/8.md) | A | *no answer* | x | 86,625 |
| [9](no_ts/9.md) | B | *no answer* | x | 56,051 |
| [10](no_ts/10.md) | C | *no answer* | x | 63,934 |
| [11](no_ts/11.md) | A | *no answer* | x | 78,320 |
| [12](no_ts/12.md) | D | *no answer* | x | 74,786 |
| [13](no_ts/13.md) | C | *no answer* | x | 59,313 |
| [14](no_ts/14.md) | D | *no answer* | x | 72,372 |
| [15](no_ts/15.md) | C | *no answer* | x | 60,227 |
| [16](no_ts/16.md) | C | *no answer* | x | 62,605 |
| [17](no_ts/17.md) | B | *no answer* | x | 73,315 |
| [18](no_ts/18.md) | B | *no answer* | x | 54,359 |
| [19](no_ts/19.md) | D | A | x | 54,892 |
| [20](no_ts/20.md) | D | *no answer* | x | 69,317 |
| [21](no_ts/21.md) | D | A | x | 27,775 |
| [22](no_ts/22.md) | A | D | x | 31,998 |
| [23](no_ts/23.md) | D | D | ok | 37,682 |
| [24](no_ts/24.md) | B | B | ok | 18,359 |
| [25](no_ts/25.md) | C | C | ok | 64,257 |
| [26](no_ts/26.md) | D | *no answer* | x | 66,245 |
| [27](no_ts/27.md) | D | *no answer* | x | 77,436 |
| [28](no_ts/28.md) | A | *no answer* | x | 79,487 |
| [29](no_ts/29.md) | B | C | x | 66,979 |
| [30](no_ts/30.md) | B | B | ok | 48,377 |
| [31](no_ts/31.md) | D | *no answer* | x | 83,795 |
| [32](no_ts/32.md) | B | *no answer* | x | 80,363 |
| [33](no_ts/33.md) | B | *no answer* | x | 85,507 |
| [34](no_ts/34.md) | D | *no answer* | x | 75,460 |
| [35](no_ts/35.md) | A | B | x | 68,913 |
| [36](no_ts/36.md) | D | A | x | 39,257 |
| [37](no_ts/37.md) | A | *no answer* | x | 87,810 |
| [38](no_ts/38.md) | A | *no answer* | x | 83,580 |
| [39](no_ts/39.md) | B | B | ok | 60,537 |
| [40](no_ts/40.md) | D | D | ok | 62,574 |
| [41](no_ts/41.md) | B | *no answer* | x | 77,896 |
| [42](no_ts/42.md) | A | *no answer* | x | 78,930 |
| [43](no_ts/43.md) | D | *no answer* | x | 58,567 |
| [44](no_ts/44.md) | B | *no answer* | x | 77,784 |
| [45](no_ts/45.md) | D | *no answer* | x | 74,914 |
| [46](no_ts/46.md) | C | A | x | 27,914 |
| [47](no_ts/47.md) | A | *no answer* | x | 64,887 |
| [48](no_ts/48.md) | B | *no answer* | x | 61,599 |
| [52](no_ts/52.md) | B | C | x | 50,916 |
| [55](no_ts/55.md) | B | *no answer* | x | 66,190 |
| [56](no_ts/56.md) | C | *no answer* | x | 59,915 |
| [57](no_ts/57.md) | B | *no answer* | x | 81,645 |
| [59](no_ts/59.md) | B | B | ok | 69,168 |
| [60](no_ts/60.md) | A | *no answer* | x | 67,991 |
| [61](no_ts/61.md) | B | *no answer* | x | 54,424 |
| [62](no_ts/62.md) | B | *no answer* | x | 58,067 |
| [63](no_ts/63.md) | B | A | x | 56,986 |
| [64](no_ts/64.md) | B | *no answer* | x | 61,423 |
| [65](no_ts/65.md) | B | C | x | 55,012 |
| [66](no_ts/66.md) | B | *no answer* | x | 60,190 |
| [67](no_ts/67.md) | A | *no answer* | x | 56,527 |
| [68](no_ts/68.md) | C | *no answer* | x | 66,884 |
| [69](no_ts/69.md) | C | *no answer* | x | 81,324 |
| [70](no_ts/70.md) | A | *no answer* | x | 52,819 |
| [71](no_ts/71.md) | D | *no answer* | x | 58,574 |
| [72](no_ts/72.md) | D | D | ok | 41,180 |
| [73](no_ts/73.md) | A | *no answer* | x | 73,672 |
| [74](no_ts/74.md) | B | *no answer* | x | 56,030 |
| [75](no_ts/75.md) | A | A | ok | 67,712 |
| [76](no_ts/76.md) | B | A | x | 44,409 |
| [77](no_ts/77.md) | C | *no answer* | x | 55,624 |
| [78](no_ts/78.md) | D | *no answer* | x | 64,193 |
| [79](no_ts/79.md) | D | *no answer* | x | 57,841 |
| [80](no_ts/80.md) | B | *no answer* | x | 77,501 |
| [81](no_ts/81.md) | A | *no answer* | x | 64,149 |
| [82](no_ts/82.md) | B | *no answer* | x | 74,531 |
| [83](no_ts/83.md) | B | *no answer* | x | 58,204 |
| [84](no_ts/84.md) | D | *no answer* | x | 70,139 |
| [85](no_ts/85.md) | C | *no answer* | x | 62,978 |
| [86](no_ts/86.md) | A | *no answer* | x | 65,908 |
| [87](no_ts/87.md) | B | *no answer* | x | 84,085 |
| [88](no_ts/88.md) | D | *no answer* | x | 63,397 |
| [89](no_ts/89.md) | C | *no answer* | x | 81,440 |
| [90](no_ts/90.md) | D | A | x | 65,725 |
| [91](no_ts/91.md) | A | *no answer* | x | 59,290 |
| [92](no_ts/92.md) | B | B | ok | 70,329 |
| [93](no_ts/93.md) | C | C | ok | 38,047 |
| [94](no_ts/94.md) | C | *no answer* | x | 60,275 |
| [95](no_ts/95.md) | B | B | ok | 58,735 |
| [96](no_ts/96.md) | B | *no answer* | x | 86,888 |
| [97](no_ts/97.md) | B | *no answer* | x | 48,600 |
| [98](no_ts/98.md) | D | *no answer* | x | 76,199 |
| [99](no_ts/99.md) | A | *no answer* | x | 69,370 |
| [100](no_ts/100.md) | C | *no answer* | x | 60,818 |
| [101](no_ts/101.md) | D | *no answer* | x | 79,637 |
| [102](no_ts/102.md) | A | *no answer* | x | 71,218 |
| [103](no_ts/103.md) | D | *no answer* | x | 77,458 |
| [104](no_ts/104.md) | C | *no answer* | x | 65,408 |
| [105](no_ts/105.md) | C | *no answer* | x | 72,809 |
| [106](no_ts/106.md) | B | B | ok | 46,175 |
| [107](no_ts/107.md) | D | D | ok | 41,181 |
| [108](no_ts/108.md) | C | *no answer* | x | 61,816 |
| [109](no_ts/109.md) | C | *no answer* | x | 56,934 |
| [110](no_ts/110.md) | A | *no answer* | x | 65,134 |
| [111](no_ts/111.md) | D | *no answer* | x | 69,140 |
| [112](no_ts/112.md) | D | *no answer* | x | 88,883 |
| [113](no_ts/113.md) | C | *no answer* | x | 69,319 |
| [114](no_ts/114.md) | D | *no answer* | x | 68,223 |
| [115](no_ts/115.md) | A | *no answer* | x | 74,708 |
| [116](no_ts/116.md) | D | *no answer* | x | 58,467 |
| [117](no_ts/117.md) | B | *no answer* | x | 68,103 |
| [118](no_ts/118.md) | D | *no answer* | x | 61,904 |
| [119](no_ts/119.md) | B | *no answer* | x | 88,337 |
| [120](no_ts/120.md) | C | *no answer* | x | 71,710 |
| [121](no_ts/121.md) | B | B | ok | 42,880 |
| [122](no_ts/122.md) | A | A | ok | 30,635 |
| [123](no_ts/123.md) | D | *no answer* | x | 70,390 |
| [124](no_ts/124.md) | D | *no answer* | x | 84,384 |
| [125](no_ts/125.md) | D | *no answer* | x | 56,034 |
| [126](no_ts/126.md) | B | *no answer* | x | 89,385 |
| [127](no_ts/127.md) | D | *no answer* | x | 93,934 |
| [128](no_ts/128.md) | C | *no answer* | x | 74,904 |
| [129](no_ts/129.md) | C | *no answer* | x | 75,932 |
| [130](no_ts/130.md) | B | *no answer* | x | 81,965 |
| [131](no_ts/131.md) | C | *no answer* | x | 81,488 |
| [132](no_ts/132.md) | B | A | x | 51,809 |
| [133](no_ts/133.md) | D | *no answer* | x | 92,207 |
| [134](no_ts/134.md) | D | *no answer* | x | 88,731 |
| [135](no_ts/135.md) | A | *no answer* | x | 96,536 |
| [136](no_ts/136.md) | A | *no answer* | x | 65,621 |
| [137](no_ts/137.md) | B | *no answer* | x | 74,587 |
| [138](no_ts/138.md) | A | *no answer* | x | 87,826 |
| [139](no_ts/139.md) | C | C | ok | 39,490 |
| [140](no_ts/140.md) | C | C | ok | 29,684 |
| [141](no_ts/141.md) | D | D | ok | 33,586 |
| [142](no_ts/142.md) | A | A | ok | 24,893 |
| [143](no_ts/143.md) | B | *no answer* | x | 61,560 |
| [144](no_ts/144.md) | D | *no answer* | x | 60,860 |
| [145](no_ts/145.md) | D | *no answer* | x | 71,862 |
| [146](no_ts/146.md) | B | *no answer* | x | 63,530 |
| [147](no_ts/147.md) | D | *no answer* | x | 71,979 |
| [148](no_ts/148.md) | D | *no answer* | x | 67,051 |
| [149](no_ts/149.md) | D | *no answer* | x | 59,866 |
| [150](no_ts/150.md) | A | *no answer* | x | 85,284 |
| [151](no_ts/151.md) | B | *no answer* | x | 98,587 |
| [152](no_ts/152.md) | A | *no answer* | x | 62,950 |
| [153](no_ts/153.md) | A | *no answer* | x | 79,775 |
| [154](no_ts/154.md) | C | *no answer* | x | 60,054 |
| [155](no_ts/155.md) | B | *no answer* | x | 95,627 |
| [156](no_ts/156.md) | D | *no answer* | x | 58,930 |
| [157](no_ts/157.md) | B | *no answer* | x | 80,221 |
| [158](no_ts/158.md) | D | *no answer* | x | 66,453 |
| [159](no_ts/159.md) | C | *no answer* | x | 78,823 |
| [160](no_ts/160.md) | D | *no answer* | x | 71,163 |

## SHUFFLED

Series timestamp-value pairing deranged. 154 of 160 instances rendered, 68 correct, 55 never answered.

| instance | gold | predicted | | reasoning chars |
|---|---|---|---|---|
| [1](shuffled/1.md) | A | B | x | 32,805 |
| [2](shuffled/2.md) | A | B | x | 12,220 |
| [3](shuffled/3.md) | D | A | x | 40,613 |
| [4](shuffled/4.md) | B | A | x | 21,369 |
| [5](shuffled/5.md) | A | B | x | 41,967 |
| [6](shuffled/6.md) | A | A | ok | 15,112 |
| [7](shuffled/7.md) | D | *no answer* | x | 61,966 |
| [8](shuffled/8.md) | A | D | x | 43,689 |
| [9](shuffled/9.md) | B | C | x | 30,556 |
| [10](shuffled/10.md) | C | C | ok | 15,989 |
| [11](shuffled/11.md) | A | B | x | 44,221 |
| [12](shuffled/12.md) | D | D | ok | 18,986 |
| [13](shuffled/13.md) | C | C | ok | 14,684 |
| [14](shuffled/14.md) | D | C | x | 60,697 |
| [15](shuffled/15.md) | C | *no answer* | x | 79,008 |
| [16](shuffled/16.md) | C | B | x | 60,130 |
| [17](shuffled/17.md) | B | *no answer* | x | 69,781 |
| [18](shuffled/18.md) | B | B | ok | 11,202 |
| [19](shuffled/19.md) | D | *no answer* | x | 69,404 |
| [20](shuffled/20.md) | D | *no answer* | x | 66,866 |
| [21](shuffled/21.md) | D | D | ok | 25,105 |
| [22](shuffled/22.md) | A | A | ok | 19,994 |
| [23](shuffled/23.md) | D | D | ok | 13,485 |
| [24](shuffled/24.md) | B | B | ok | 13,774 |
| [25](shuffled/25.md) | C | *no answer* | x | 78,480 |
| [26](shuffled/26.md) | D | B | x | 33,168 |
| [27](shuffled/27.md) | D | *no answer* | x | 57,978 |
| [28](shuffled/28.md) | A | B | x | 10,514 |
| [29](shuffled/29.md) | B | B | ok | 18,745 |
| [30](shuffled/30.md) | B | B | ok | 63,555 |
| [31](shuffled/31.md) | D | *no answer* | x | 68,529 |
| [32](shuffled/32.md) | B | *no answer* | x | 76,895 |
| [33](shuffled/33.md) | B | B | ok | 19,669 |
| [34](shuffled/34.md) | D | D | ok | 9,179 |
| [35](shuffled/35.md) | A | C | x | 23,115 |
| [36](shuffled/36.md) | D | D | ok | 16,602 |
| [37](shuffled/37.md) | A | A | ok | 37,706 |
| [38](shuffled/38.md) | A | A | ok | 27,905 |
| [39](shuffled/39.md) | B | B | ok | 5,215 |
| [40](shuffled/40.md) | D | C | x | 24,670 |
| [41](shuffled/41.md) | B | *no answer* | x | 59,212 |
| [42](shuffled/42.md) | A | A | ok | 7,688 |
| [43](shuffled/43.md) | D | D | ok | 34,142 |
| [44](shuffled/44.md) | B | *no answer* | x | 77,966 |
| [45](shuffled/45.md) | D | D | ok | 6,763 |
| [46](shuffled/46.md) | C | B | x | 29,906 |
| [47](shuffled/47.md) | A | *no answer* | x | 67,937 |
| [48](shuffled/48.md) | B | *no answer* | x | 62,071 |
| [49](shuffled/49.md) | B | *no answer* | x | 74,698 |
| [50](shuffled/50.md) | D | *no answer* | x | 70,675 |
| [51](shuffled/51.md) | B | B | ok | 28,054 |
| [52](shuffled/52.md) | B | C | x | 8,656 |
| [53](shuffled/53.md) | C | C | ok | 11,779 |
| [54](shuffled/54.md) | C | D | x | 61,887 |
| [55](shuffled/55.md) | B | B | ok | 15,666 |
| [57](shuffled/57.md) | B | C | x | 33,544 |
| [58](shuffled/58.md) | A | *no answer* | x | 74,862 |
| [59](shuffled/59.md) | B | *no answer* | x | 55,359 |
| [60](shuffled/60.md) | A | *no answer* | x | 81,138 |
| [61](shuffled/61.md) | B | D | x | 22,660 |
| [62](shuffled/62.md) | B | *no answer* | x | 66,487 |
| [63](shuffled/63.md) | B | B | ok | 18,776 |
| [64](shuffled/64.md) | B | B | ok | 27,092 |
| [65](shuffled/65.md) | B | *no answer* | x | 76,459 |
| [66](shuffled/66.md) | B | B | ok | 41,772 |
| [68](shuffled/68.md) | C | *no answer* | x | 71,714 |
| [69](shuffled/69.md) | C | C | ok | 35,789 |
| [70](shuffled/70.md) | A | *no answer* | x | 54,636 |
| [72](shuffled/72.md) | D | *no answer* | x | 64,705 |
| [73](shuffled/73.md) | A | *no answer* | x | 58,002 |
| [74](shuffled/74.md) | B | *no answer* | x | 67,545 |
| [75](shuffled/75.md) | A | A | ok | 27,176 |
| [76](shuffled/76.md) | B | *no answer* | x | 65,869 |
| [77](shuffled/77.md) | C | *no answer* | x | 62,733 |
| [78](shuffled/78.md) | D | *no answer* | x | 58,998 |
| [79](shuffled/79.md) | D | *no answer* | x | 61,962 |
| [80](shuffled/80.md) | B | D | x | 58,232 |
| [81](shuffled/81.md) | A | *no answer* | x | 70,012 |
| [83](shuffled/83.md) | B | B | ok | 74,668 |
| [85](shuffled/85.md) | C | C | ok | 76,739 |
| [86](shuffled/86.md) | A | *no answer* | x | 58,287 |
| [87](shuffled/87.md) | B | C | x | 25,310 |
| [88](shuffled/88.md) | D | *no answer* | x | 61,896 |
| [89](shuffled/89.md) | C | C | ok | 6,004 |
| [90](shuffled/90.md) | D | *no answer* | x | 62,470 |
| [91](shuffled/91.md) | A | A | ok | 39,133 |
| [92](shuffled/92.md) | B | *no answer* | x | 109,130 |
| [94](shuffled/94.md) | C | *no answer* | x | 84,739 |
| [95](shuffled/95.md) | B | B | ok | 41,420 |
| [96](shuffled/96.md) | B | B | ok | 8,713 |
| [97](shuffled/97.md) | B | A | x | 65,719 |
| [98](shuffled/98.md) | D | B | x | 50,372 |
| [99](shuffled/99.md) | A | *no answer* | x | 64,221 |
| [100](shuffled/100.md) | C | D | x | 57,528 |
| [101](shuffled/101.md) | D | A | x | 14,777 |
| [102](shuffled/102.md) | A | *no answer* | x | 63,711 |
| [103](shuffled/103.md) | D | D | ok | 48,856 |
| [104](shuffled/104.md) | C | C | ok | 63,059 |
| [105](shuffled/105.md) | C | *no answer* | x | 79,460 |
| [106](shuffled/106.md) | B | B | ok | 5,980 |
| [107](shuffled/107.md) | D | D | ok | 54,333 |
| [108](shuffled/108.md) | C | *no answer* | x | 65,438 |
| [109](shuffled/109.md) | C | C | ok | 11,355 |
| [110](shuffled/110.md) | A | *no answer* | x | 72,915 |
| [111](shuffled/111.md) | D | *no answer* | x | 78,390 |
| [112](shuffled/112.md) | D | D | ok | 27,083 |
| [113](shuffled/113.md) | C | C | ok | 67,899 |
| [114](shuffled/114.md) | D | *no answer* | x | 80,061 |
| [115](shuffled/115.md) | A | B | x | 36,596 |
| [116](shuffled/116.md) | D | D | ok | 20,859 |
| [117](shuffled/117.md) | B | C | x | 13,658 |
| [118](shuffled/118.md) | D | D | ok | 11,472 |
| [119](shuffled/119.md) | B | *no answer* | x | 55,244 |
| [120](shuffled/120.md) | C | C | ok | 29,073 |
| [121](shuffled/121.md) | B | B | ok | 21,955 |
| [122](shuffled/122.md) | A | A | ok | 3,828 |
| [123](shuffled/123.md) | D | *no answer* | x | 78,462 |
| [124](shuffled/124.md) | D | D | ok | 16,071 |
| [125](shuffled/125.md) | D | D | ok | 70,045 |
| [126](shuffled/126.md) | B | B | ok | 52,859 |
| [127](shuffled/127.md) | D | *no answer* | x | 75,445 |
| [128](shuffled/128.md) | C | *no answer* | x | 87,639 |
| [129](shuffled/129.md) | C | D | x | 77,820 |
| [130](shuffled/130.md) | B | B | ok | 26,644 |
| [131](shuffled/131.md) | C | *no answer* | x | 76,481 |
| [132](shuffled/132.md) | B | B | ok | 35,185 |
| [133](shuffled/133.md) | D | *no answer* | x | 78,092 |
| [134](shuffled/134.md) | D | A | x | 14,421 |
| [135](shuffled/135.md) | A | A | ok | 15,212 |
| [136](shuffled/136.md) | A | A | ok | 24,062 |
| [137](shuffled/137.md) | B | B | ok | 39,828 |
| [138](shuffled/138.md) | A | A | ok | 17,213 |
| [139](shuffled/139.md) | C | C | ok | 6,312 |
| [140](shuffled/140.md) | C | C | ok | 11,671 |
| [141](shuffled/141.md) | D | D | ok | 9,511 |
| [142](shuffled/142.md) | A | A | ok | 23,061 |
| [143](shuffled/143.md) | B | B | ok | 21,415 |
| [144](shuffled/144.md) | D | A | x | 40,013 |
| [145](shuffled/145.md) | D | D | ok | 11,891 |
| [146](shuffled/146.md) | B | B | ok | 18,030 |
| [147](shuffled/147.md) | D | D | ok | 25,512 |
| [148](shuffled/148.md) | D | D | ok | 18,703 |
| [149](shuffled/149.md) | D | *no answer* | x | 65,413 |
| [150](shuffled/150.md) | A | *no answer* | x | 63,157 |
| [151](shuffled/151.md) | B | C | x | 46,940 |
| [152](shuffled/152.md) | A | *no answer* | x | 77,323 |
| [153](shuffled/153.md) | A | *no answer* | x | 73,837 |
| [154](shuffled/154.md) | C | *no answer* | x | 90,465 |
| [155](shuffled/155.md) | B | B | ok | 54,496 |
| [156](shuffled/156.md) | D | D | ok | 63,669 |
| [157](shuffled/157.md) | B | *no answer* | x | 68,840 |
| [158](shuffled/158.md) | D | D | ok | 13,758 |
| [159](shuffled/159.md) | C | C | ok | 26,816 |
| [160](shuffled/160.md) | D | *no answer* | x | 77,863 |

## RELATIVE

Absolute timestamps replaced by unitless relative indices. 153 of 160 instances rendered, 13 correct, 117 never answered.

| instance | gold | predicted | | reasoning chars |
|---|---|---|---|---|
| [1](relative/1.md) | A | *no answer* | x | 86,407 |
| [2](relative/2.md) | A | *no answer* | x | 62,894 |
| [3](relative/3.md) | D | C | x | 17,623 |
| [4](relative/4.md) | B | *no answer* | x | 64,970 |
| [5](relative/5.md) | A | *no answer* | x | 65,270 |
| [6](relative/6.md) | A | B | x | 24,833 |
| [7](relative/7.md) | D | *no answer* | x | 74,781 |
| [8](relative/8.md) | A | *no answer* | x | 81,596 |
| [9](relative/9.md) | B | *no answer* | x | 59,983 |
| [10](relative/10.md) | C | *no answer* | x | 61,637 |
| [11](relative/11.md) | A | D | x | 24,971 |
| [12](relative/12.md) | D | *no answer* | x | 62,186 |
| [13](relative/13.md) | C | *no answer* | x | 73,931 |
| [14](relative/14.md) | D | *no answer* | x | 61,583 |
| [15](relative/15.md) | C | *no answer* | x | 59,028 |
| [16](relative/16.md) | C | *no answer* | x | 58,321 |
| [17](relative/17.md) | B | *no answer* | x | 56,096 |
| [18](relative/18.md) | B | A | x | 15,054 |
| [19](relative/19.md) | D | *no answer* | x | 56,688 |
| [20](relative/20.md) | D | B | x | 9,138 |
| [21](relative/21.md) | D | *no answer* | x | 56,577 |
| [22](relative/22.md) | A | *no answer* | x | 76,779 |
| [23](relative/23.md) | D | *no answer* | x | 76,003 |
| [24](relative/24.md) | B | *no answer* | x | 72,759 |
| [25](relative/25.md) | C | *no answer* | x | 75,365 |
| [26](relative/26.md) | D | *no answer* | x | 75,578 |
| [27](relative/27.md) | D | *no answer* | x | 83,537 |
| [28](relative/28.md) | A | *no answer* | x | 56,585 |
| [29](relative/29.md) | B | B | ok | 73,903 |
| [30](relative/30.md) | B | *no answer* | x | 75,181 |
| [31](relative/31.md) | D | *no answer* | x | 95,483 |
| [32](relative/32.md) | B | *no answer* | x | 84,032 |
| [33](relative/33.md) | B | *no answer* | x | 78,328 |
| [34](relative/34.md) | D | *no answer* | x | 74,807 |
| [35](relative/35.md) | A | C | x | 37,431 |
| [36](relative/36.md) | D | C | x | 15,497 |
| [37](relative/37.md) | A | *no answer* | x | 86,064 |
| [38](relative/38.md) | A | *no answer* | x | 76,382 |
| [39](relative/39.md) | B | B | ok | 57,289 |
| [40](relative/40.md) | D | *no answer* | x | 75,632 |
| [41](relative/41.md) | B | *no answer* | x | 56,786 |
| [42](relative/42.md) | A | *no answer* | x | 57,663 |
| [43](relative/43.md) | D | *no answer* | x | 54,438 |
| [44](relative/44.md) | B | *no answer* | x | 74,381 |
| [45](relative/45.md) | D | *no answer* | x | 65,396 |
| [46](relative/46.md) | C | C | ok | 32,315 |
| [47](relative/47.md) | A | *no answer* | x | 81,520 |
| [48](relative/48.md) | B | *no answer* | x | 61,882 |
| [50](relative/50.md) | D | *no answer* | x | 60,680 |
| [52](relative/52.md) | B | A | x | 34,472 |
| [54](relative/54.md) | C | *no answer* | x | 59,535 |
| [55](relative/55.md) | B | *no answer* | x | 68,124 |
| [57](relative/57.md) | B | *no answer* | x | 61,643 |
| [59](relative/59.md) | B | *no answer* | x | 58,275 |
| [60](relative/60.md) | A | *no answer* | x | 61,719 |
| [61](relative/61.md) | B | *no answer* | x | 61,005 |
| [62](relative/62.md) | B | A | x | 32,169 |
| [63](relative/63.md) | B | *no answer* | x | 78,647 |
| [64](relative/64.md) | B | *no answer* | x | 60,291 |
| [65](relative/65.md) | B | *no answer* | x | 70,485 |
| [67](relative/67.md) | A | *no answer* | x | 54,981 |
| [68](relative/68.md) | C | *no answer* | x | 56,100 |
| [69](relative/69.md) | C | *no answer* | x | 56,982 |
| [70](relative/70.md) | A | *no answer* | x | 61,835 |
| [71](relative/71.md) | D | *no answer* | x | 60,823 |
| [72](relative/72.md) | D | D | ok | 54,355 |
| [73](relative/73.md) | A | *no answer* | x | 87,484 |
| [74](relative/74.md) | B | *no answer* | x | 82,391 |
| [75](relative/75.md) | A | A | ok | 44,960 |
| [76](relative/76.md) | B | *no answer* | x | 76,236 |
| [77](relative/77.md) | C | *no answer* | x | 57,606 |
| [78](relative/78.md) | D | B | x | 53,223 |
| [79](relative/79.md) | D | *no answer* | x | 60,543 |
| [80](relative/80.md) | B | *no answer* | x | 58,348 |
| [81](relative/81.md) | A | B | x | 61,044 |
| [82](relative/82.md) | B | C | x | 25,294 |
| [83](relative/83.md) | B | *no answer* | x | 58,483 |
| [84](relative/84.md) | D | *no answer* | x | 65,390 |
| [85](relative/85.md) | C | *no answer* | x | 61,176 |
| [86](relative/86.md) | A | *no answer* | x | 67,582 |
| [87](relative/87.md) | B | *no answer* | x | 57,009 |
| [88](relative/88.md) | D | *no answer* | x | 56,339 |
| [89](relative/89.md) | C | *no answer* | x | 67,910 |
| [90](relative/90.md) | D | *no answer* | x | 57,967 |
| [91](relative/91.md) | A | *no answer* | x | 61,985 |
| [92](relative/92.md) | B | *no answer* | x | 62,145 |
| [93](relative/93.md) | C | C | ok | 64,891 |
| [94](relative/94.md) | C | *no answer* | x | 78,418 |
| [95](relative/95.md) | B | *no answer* | x | 60,935 |
| [96](relative/96.md) | B | *no answer* | x | 82,299 |
| [97](relative/97.md) | B | *no answer* | x | 57,674 |
| [98](relative/98.md) | D | *no answer* | x | 56,129 |
| [99](relative/99.md) | A | *no answer* | x | 52,205 |
| [100](relative/100.md) | C | B | x | 23,987 |
| [101](relative/101.md) | D | *no answer* | x | 65,330 |
| [102](relative/102.md) | A | *no answer* | x | 72,226 |
| [103](relative/103.md) | D | C | x | 51,363 |
| [104](relative/104.md) | C | *no answer* | x | 59,658 |
| [105](relative/105.md) | C | *no answer* | x | 57,964 |
| [106](relative/106.md) | B | D | x | 8,952 |
| [107](relative/107.md) | D | *no answer* | x | 69,469 |
| [108](relative/108.md) | C | *no answer* | x | 88,115 |
| [109](relative/109.md) | C | *no answer* | x | 59,037 |
| [110](relative/110.md) | A | *no answer* | x | 62,180 |
| [111](relative/111.md) | D | *no answer* | x | 69,672 |
| [112](relative/112.md) | D | C | x | 39,714 |
| [113](relative/113.md) | C | *no answer* | x | 75,608 |
| [114](relative/114.md) | D | *no answer* | x | 60,329 |
| [115](relative/115.md) | A | *no answer* | x | 55,328 |
| [116](relative/116.md) | D | D | ok | 48,693 |
| [117](relative/117.md) | B | *no answer* | x | 60,193 |
| [118](relative/118.md) | D | D | ok | 40,687 |
| [119](relative/119.md) | B | *no answer* | x | 55,048 |
| [120](relative/120.md) | C | *no answer* | x | 59,167 |
| [121](relative/121.md) | B | *no answer* | x | 64,834 |
| [122](relative/122.md) | A | A | ok | 43,797 |
| [123](relative/123.md) | D | *no answer* | x | 78,661 |
| [124](relative/124.md) | D | *no answer* | x | 68,461 |
| [125](relative/125.md) | D | *no answer* | x | 74,612 |
| [126](relative/126.md) | B | C | x | 50,767 |
| [127](relative/127.md) | D | *no answer* | x | 84,439 |
| [128](relative/128.md) | C | *no answer* | x | 62,044 |
| [129](relative/129.md) | C | *no answer* | x | 89,295 |
| [130](relative/130.md) | B | *no answer* | x | 72,497 |
| [131](relative/131.md) | C | B | x | 28,015 |
| [133](relative/133.md) | D | *no answer* | x | 77,729 |
| [134](relative/134.md) | D | *no answer* | x | 91,634 |
| [135](relative/135.md) | A | *no answer* | x | 85,783 |
| [136](relative/136.md) | A | A | ok | 32,632 |
| [137](relative/137.md) | B | *no answer* | x | 61,357 |
| [138](relative/138.md) | A | *no answer* | x | 84,598 |
| [139](relative/139.md) | C | C | ok | 46,580 |
| [140](relative/140.md) | C | C | ok | 45,024 |
| [141](relative/141.md) | D | *no answer* | x | 62,384 |
| [142](relative/142.md) | A | D | x | 12,193 |
| [143](relative/143.md) | B | C | x | 58,260 |
| [144](relative/144.md) | D | *no answer* | x | 58,262 |
| [145](relative/145.md) | D | *no answer* | x | 61,831 |
| [146](relative/146.md) | B | *no answer* | x | 60,704 |
| [147](relative/147.md) | D | *no answer* | x | 57,677 |
| [148](relative/148.md) | D | *no answer* | x | 75,448 |
| [149](relative/149.md) | D | A | x | 25,488 |
| [150](relative/150.md) | A | *no answer* | x | 55,869 |
| [151](relative/151.md) | B | C | x | 9,526 |
| [152](relative/152.md) | A | *no answer* | x | 62,119 |
| [153](relative/153.md) | A | A | ok | 14,230 |
| [154](relative/154.md) | C | *no answer* | x | 78,810 |
| [155](relative/155.md) | B | *no answer* | x | 62,789 |
| [156](relative/156.md) | D | *no answer* | x | 60,125 |
| [157](relative/157.md) | B | D | x | 35,228 |
| [158](relative/158.md) | D | *no answer* | x | 66,587 |
| [159](relative/159.md) | C | *no answer* | x | 56,412 |
| [160](relative/160.md) | D | *no answer* | x | 58,241 |
