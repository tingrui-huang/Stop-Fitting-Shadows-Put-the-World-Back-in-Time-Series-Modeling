# Readable reasoning traces - tsrbench50_qwen36

One Markdown file per instance, rendered from the authoritative raw
results under `results/tsrbench50_qwen36/<cond>_raw/`. The reasoning trace and the
final answer are copied verbatim; regenerate with
`python make_readable_traces.py --tag tsrbench50_qwen36`.

An instance missing from a table produced no final answer at all: the
runner writes no result file in that case, so the instance stays
rerunnable and its partial trace is kept in `failures_<cond>.jsonl`.

## QA_ONLY

Question and the four orderings only - the leakage check. 50 of 50 instances answered, 14 correct.

| instance | gold | predicted | | reasoning chars |
|---|---|---|---|---|
| [1](qa_only/1.md) | A | A | ok | 6791 |
| [2](qa_only/2.md) | D | A | x | 6983 |
| [3](qa_only/3.md) | D | A | x | 8041 |
| [4](qa_only/4.md) | C | A | x | 6669 |
| [5](qa_only/5.md) | C | C | ok | 7021 |
| [6](qa_only/6.md) | B | A | x | 6698 |
| [7](qa_only/7.md) | D | A | x | 9470 |
| [8](qa_only/8.md) | C | A | x | 6674 |
| [9](qa_only/9.md) | D | A | x | 6504 |
| [10](qa_only/10.md) | A | A | ok | 6065 |
| [11](qa_only/11.md) | B | A | x | 8018 |
| [12](qa_only/12.md) | B | A | x | 5691 |
| [13](qa_only/13.md) | A | A | ok | 6363 |
| [14](qa_only/14.md) | D | A | x | 6230 |
| [15](qa_only/15.md) | C | A | x | 6167 |
| [16](qa_only/16.md) | A | A | ok | 5656 |
| [17](qa_only/17.md) | B | A | x | 8503 |
| [18](qa_only/18.md) | C | A | x | 7449 |
| [19](qa_only/19.md) | C | A | x | 6594 |
| [20](qa_only/20.md) | B | A | x | 6503 |
| [21](qa_only/21.md) | A | A | ok | 5941 |
| [22](qa_only/22.md) | C | C | ok | 8160 |
| [23](qa_only/23.md) | A | A | ok | 6003 |
| [24](qa_only/24.md) | D | A | x | 7823 |
| [25](qa_only/25.md) | B | C | x | 9454 |
| [26](qa_only/26.md) | B | A | x | 6316 |
| [27](qa_only/27.md) | D | A | x | 6582 |
| [28](qa_only/28.md) | A | A | ok | 7037 |
| [29](qa_only/29.md) | B | A | x | 7235 |
| [30](qa_only/30.md) | C | A | x | 5635 |
| [31](qa_only/31.md) | D | A | x | 6736 |
| [32](qa_only/32.md) | D | A | x | 6526 |
| [33](qa_only/33.md) | C | A | x | 6222 |
| [34](qa_only/34.md) | D | A | x | 6943 |
| [35](qa_only/35.md) | C | A | x | 5452 |
| [36](qa_only/36.md) | A | A | ok | 5707 |
| [37](qa_only/37.md) | A | A | ok | 6388 |
| [38](qa_only/38.md) | B | A | x | 5940 |
| [39](qa_only/39.md) | D | A | x | 5146 |
| [40](qa_only/40.md) | C | A | x | 5952 |
| [41](qa_only/41.md) | B | A | x | 7600 |
| [42](qa_only/42.md) | A | A | ok | 6329 |
| [43](qa_only/43.md) | B | A | x | 5641 |
| [44](qa_only/44.md) | C | A | x | 6443 |
| [45](qa_only/45.md) | B | A | x | 7472 |
| [46](qa_only/46.md) | D | A | x | 9014 |
| [47](qa_only/47.md) | A | A | ok | 5087 |
| [48](qa_only/48.md) | B | A | x | 7070 |
| [49](qa_only/49.md) | A | A | ok | 6510 |
| [50](qa_only/50.md) | C | A | x | 7513 |

## FULL

Timestamped series + events with their times - the reference. 49 of 50 instances answered, 17 correct.

| instance | gold | predicted | | reasoning chars |
|---|---|---|---|---|
| [1](full/1.md) | A | D | x | 19716 |
| [2](full/2.md) | D | D | ok | 21796 |
| [3](full/3.md) | D | B | x | 28612 |
| [4](full/4.md) | C | C | ok | 35683 |
| [5](full/5.md) | C | C | ok | 15961 |
| [6](full/6.md) | B | A | x | 28333 |
| [7](full/7.md) | D | D | ok | 27644 |
| [8](full/8.md) | C | B | x | 20932 |
| [9](full/9.md) | D | B | x | 23295 |
| [10](full/10.md) | A | D | x | 22169 |
| [11](full/11.md) | B | C | x | 27810 |
| [12](full/12.md) | B | B | ok | 18559 |
| [13](full/13.md) | A | A | ok | 12041 |
| [14](full/14.md) | D | B | x | 23725 |
| [15](full/15.md) | C | C | ok | 17502 |
| [16](full/16.md) | A | A | ok | 32118 |
| [17](full/17.md) | B | C | x | 24310 |
| [18](full/18.md) | C | A | x | 24030 |
| [19](full/19.md) | C | A | x | 26419 |
| [20](full/20.md) | B | A | x | 16575 |
| [21](full/21.md) | A | A | ok | 34216 |
| [22](full/22.md) | C | C | ok | 34431 |
| [23](full/23.md) | A | D | x | 22463 |
| [24](full/24.md) | D | C | x | 18249 |
| [25](full/25.md) | B | A | x | 16402 |
| [26](full/26.md) | B | A | x | 25622 |
| [27](full/27.md) | D | C | x | 16555 |
| [28](full/28.md) | A | D | x | 32595 |
| [29](full/29.md) | B | D | x | 27927 |
| [30](full/30.md) | C | A | x | 7495 |
| [31](full/31.md) | D | A | x | 21937 |
| [32](full/32.md) | D | B | x | 21216 |
| [33](full/33.md) | C | D | x | 15935 |
| [34](full/34.md) | D | D | ok | 24916 |
| [35](full/35.md) | C | C | ok | 24160 |
| [36](full/36.md) | A | A | ok | 11967 |
| [37](full/37.md) | A | B | x | 20698 |
| [38](full/38.md) | B | D | x | 25814 |
| [39](full/39.md) | D | D | ok | 24954 |
| [40](full/40.md) | C | C | ok | 27823 |
| [41](full/41.md) | B | A | x | 24619 |
| [42](full/42.md) | A | A | ok | 20669 |
| [44](full/44.md) | C | A | x | 24735 |
| [45](full/45.md) | B | D | x | 17003 |
| [46](full/46.md) | D | D | ok | 11448 |
| [47](full/47.md) | A | D | x | 11523 |
| [48](full/48.md) | B | D | x | 31651 |
| [49](full/49.md) | A | D | x | 24418 |
| [50](full/50.md) | C | A | x | 31549 |

## NO_TS

Every timestamp deleted, series and events. 49 of 50 instances answered, 17 correct.

| instance | gold | predicted | | reasoning chars |
|---|---|---|---|---|
| [1](no_ts/1.md) | A | A | ok | 16248 |
| [2](no_ts/2.md) | D | D | ok | 11436 |
| [3](no_ts/3.md) | D | C | x | 12005 |
| [4](no_ts/4.md) | C | C | ok | 16786 |
| [5](no_ts/5.md) | C | C | ok | 11472 |
| [7](no_ts/7.md) | D | C | x | 6986 |
| [8](no_ts/8.md) | C | B | x | 16169 |
| [9](no_ts/9.md) | D | B | x | 13227 |
| [10](no_ts/10.md) | A | C | x | 13294 |
| [11](no_ts/11.md) | B | D | x | 11384 |
| [12](no_ts/12.md) | B | B | ok | 17022 |
| [13](no_ts/13.md) | A | A | ok | 9309 |
| [14](no_ts/14.md) | D | A | x | 11295 |
| [15](no_ts/15.md) | C | B | x | 11885 |
| [16](no_ts/16.md) | A | B | x | 14196 |
| [17](no_ts/17.md) | B | C | x | 11909 |
| [18](no_ts/18.md) | C | A | x | 11771 |
| [19](no_ts/19.md) | C | D | x | 10927 |
| [20](no_ts/20.md) | B | C | x | 12663 |
| [21](no_ts/21.md) | A | D | x | 10575 |
| [22](no_ts/22.md) | C | C | ok | 12426 |
| [23](no_ts/23.md) | A | D | x | 10464 |
| [24](no_ts/24.md) | D | B | x | 10579 |
| [25](no_ts/25.md) | B | B | ok | 11310 |
| [26](no_ts/26.md) | B | C | x | 11825 |
| [27](no_ts/27.md) | D | D | ok | 12122 |
| [28](no_ts/28.md) | A | D | x | 14595 |
| [29](no_ts/29.md) | B | D | x | 14894 |
| [30](no_ts/30.md) | C | C | ok | 11122 |
| [31](no_ts/31.md) | D | D | ok | 11618 |
| [32](no_ts/32.md) | D | B | x | 11190 |
| [33](no_ts/33.md) | C | C | ok | 18520 |
| [34](no_ts/34.md) | D | C | x | 7743 |
| [35](no_ts/35.md) | C | D | x | 9315 |
| [36](no_ts/36.md) | A | D | x | 12097 |
| [37](no_ts/37.md) | A | D | x | 9496 |
| [38](no_ts/38.md) | B | B | ok | 12257 |
| [39](no_ts/39.md) | D | A | x | 16055 |
| [40](no_ts/40.md) | C | C | ok | 9739 |
| [41](no_ts/41.md) | B | B | ok | 13190 |
| [42](no_ts/42.md) | A | C | x | 12158 |
| [43](no_ts/43.md) | B | B | ok | 10408 |
| [44](no_ts/44.md) | C | B | x | 7969 |
| [45](no_ts/45.md) | B | C | x | 7711 |
| [46](no_ts/46.md) | D | A | x | 14343 |
| [47](no_ts/47.md) | A | D | x | 10519 |
| [48](no_ts/48.md) | B | B | ok | 18662 |
| [49](no_ts/49.md) | A | C | x | 19652 |
| [50](no_ts/50.md) | C | B | x | 18030 |

## SHUFFLED

Series timestamp-value pairing deranged. 46 of 50 instances answered, 15 correct.

| instance | gold | predicted | | reasoning chars |
|---|---|---|---|---|
| [1](shuffled/1.md) | A | B | x | 32438 |
| [2](shuffled/2.md) | D | D | ok | 25970 |
| [3](shuffled/3.md) | D | C | x | 15373 |
| [4](shuffled/4.md) | C | D | x | 25521 |
| [5](shuffled/5.md) | C | C | ok | 26304 |
| [6](shuffled/6.md) | B | A | x | 23780 |
| [7](shuffled/7.md) | D | D | ok | 13708 |
| [8](shuffled/8.md) | C | D | x | 14126 |
| [9](shuffled/9.md) | D | D | ok | 24416 |
| [10](shuffled/10.md) | A | D | x | 19045 |
| [11](shuffled/11.md) | B | C | x | 10132 |
| [12](shuffled/12.md) | B | B | ok | 19853 |
| [13](shuffled/13.md) | A | C | x | 17416 |
| [15](shuffled/15.md) | C | C | ok | 16773 |
| [16](shuffled/16.md) | A | A | ok | 24517 |
| [17](shuffled/17.md) | B | C | x | 17244 |
| [18](shuffled/18.md) | C | B | x | 37270 |
| [19](shuffled/19.md) | C | A | x | 30047 |
| [20](shuffled/20.md) | B | A | x | 13773 |
| [21](shuffled/21.md) | A | A | ok | 30276 |
| [22](shuffled/22.md) | C | B | x | 28266 |
| [23](shuffled/23.md) | A | D | x | 29502 |
| [24](shuffled/24.md) | D | B | x | 32243 |
| [26](shuffled/26.md) | B | A | x | 30133 |
| [27](shuffled/27.md) | D | A | x | 31012 |
| [28](shuffled/28.md) | A | A | ok | 25321 |
| [29](shuffled/29.md) | B | D | x | 24547 |
| [30](shuffled/30.md) | C | D | x | 23246 |
| [31](shuffled/31.md) | D | D | ok | 22606 |
| [32](shuffled/32.md) | D | B | x | 29267 |
| [33](shuffled/33.md) | C | A | x | 20332 |
| [34](shuffled/34.md) | D | A | x | 23680 |
| [35](shuffled/35.md) | C | C | ok | 29700 |
| [36](shuffled/36.md) | A | A | ok | 19300 |
| [37](shuffled/37.md) | A | B | x | 20565 |
| [38](shuffled/38.md) | B | D | x | 32484 |
| [39](shuffled/39.md) | D | D | ok | 20899 |
| [40](shuffled/40.md) | C | C | ok | 22824 |
| [42](shuffled/42.md) | A | A | ok | 30934 |
| [43](shuffled/43.md) | B | D | x | 28525 |
| [44](shuffled/44.md) | C | A | x | 27275 |
| [45](shuffled/45.md) | B | D | x | 27046 |
| [46](shuffled/46.md) | D | A | x | 23366 |
| [47](shuffled/47.md) | A | D | x | 15911 |
| [49](shuffled/49.md) | A | B | x | 18191 |
| [50](shuffled/50.md) | C | A | x | 33917 |

## RELATIVE

Absolute timestamps replaced by unitless relative indices. 44 of 50 instances answered, 11 correct.

| instance | gold | predicted | | reasoning chars |
|---|---|---|---|---|
| [1](relative/1.md) | A | D | x | 19130 |
| [2](relative/2.md) | D | D | ok | 26831 |
| [3](relative/3.md) | D | C | x | 29003 |
| [4](relative/4.md) | C | D | x | 23566 |
| [5](relative/5.md) | C | D | x | 28201 |
| [8](relative/8.md) | C | C | ok | 27969 |
| [9](relative/9.md) | D | A | x | 14991 |
| [10](relative/10.md) | A | D | x | 15160 |
| [11](relative/11.md) | B | C | x | 22305 |
| [12](relative/12.md) | B | B | ok | 33070 |
| [13](relative/13.md) | A | C | x | 15327 |
| [14](relative/14.md) | D | B | x | 24600 |
| [15](relative/15.md) | C | C | ok | 17300 |
| [16](relative/16.md) | A | B | x | 26195 |
| [17](relative/17.md) | B | C | x | 21381 |
| [18](relative/18.md) | C | A | x | 20435 |
| [20](relative/20.md) | B | A | x | 17948 |
| [21](relative/21.md) | A | C | x | 20606 |
| [22](relative/22.md) | C | D | x | 24414 |
| [23](relative/23.md) | A | D | x | 17601 |
| [24](relative/24.md) | D | C | x | 27693 |
| [25](relative/25.md) | B | D | x | 24902 |
| [26](relative/26.md) | B | B | ok | 23169 |
| [27](relative/27.md) | D | A | x | 23073 |
| [29](relative/29.md) | B | B | ok | 25548 |
| [30](relative/30.md) | C | A | x | 17181 |
| [31](relative/31.md) | D | A | x | 20414 |
| [32](relative/32.md) | D | B | x | 29196 |
| [33](relative/33.md) | C | A | x | 32046 |
| [34](relative/34.md) | D | D | ok | 30645 |
| [35](relative/35.md) | C | A | x | 37611 |
| [36](relative/36.md) | A | A | ok | 8811 |
| [37](relative/37.md) | A | B | x | 18529 |
| [38](relative/38.md) | B | C | x | 34808 |
| [39](relative/39.md) | D | D | ok | 21493 |
| [41](relative/41.md) | B | A | x | 21863 |
| [42](relative/42.md) | A | A | ok | 24079 |
| [44](relative/44.md) | C | A | x | 23444 |
| [45](relative/45.md) | B | D | x | 21444 |
| [46](relative/46.md) | D | A | x | 17414 |
| [47](relative/47.md) | A | C | x | 25605 |
| [48](relative/48.md) | B | D | x | 30497 |
| [49](relative/49.md) | A | D | x | 24844 |
| [50](relative/50.md) | C | C | ok | 30665 |
