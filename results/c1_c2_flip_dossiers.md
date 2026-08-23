# C1 <-> C2 discordant cases - Sonnet-5, final frozen benchmark

Post-hoc error analysis. No benchmark file, distractor, mask, question, option or model output was modified, and no inference was run.

C1 = 44/50 (0.88) with timestamps. C2 = 46/50 (0.92) with temporal information removed. Transition matrix: BOTH_CORRECT 42, C1_CORRECT_C2_WRONG 2 [252, 274], C1_WRONG_C2_CORRECT 4 [18, 96, 176, 265], BOTH_WRONG 2 [47, 201].

---

# Instance 18 - LULU

Transition: C1 wrong -> C2 correct

## Task

```
Which of the following statements about LULU's stock price and the given financial analysis is incorrect?
A. The news highlights that Lululemon has a positive Earnings ESP, which typically predicts a strong likelihood of beating earnings estimates, correlating with the stock's potential recovery.
B. The historical stock price data shows a significant volatility leading up to the earnings announcement, suggesting that investors were uncertain about the company's performance.
C. Despite a positive earnings prediction, the historical data indicates a consistent decline in Lululemon’s stock price before the news, which implies a deteriorating business outlook.
D. Following the news publication, Lululemon's stock price dropped sharply, indicating that market sentiment might have turned negative despite an optimistic earnings outlook.
```

- gold answer: **C**
- ground-truth article: position 10, event `earnings`, published 2021-06-02 16:10:05
- time series: 312 points

## C1

- answer **D** (incorrect), confidence 0.72
- rationale: The time series shows LULU's price actually rising from ~316 to ~319 in the hours leading up to the 16:10 article publication on June 2, 2021, with no post-publication sharp drop evident in the data (the series ends right at the publish time), contradicting the claim that price 'dropped sharply' following the news.

Cited evidence:

- Article 10 -> position 10, **GT** - Why Lululemon (LULU) Could Beat Earnings Estimates Again

## C2

- answer **C** (correct), confidence 0.65
- rationale: The price series shows fluctuations with an overall mild upward drift for much of the series before a later decline, not a 'consistent decline' throughout, so claim C mischaracterizes the data; the ESP article (Article 10) implies optimism rather than deteriorating outlook.

Cited evidence:

- Article 10 -> position 10, **GT** - Why Lululemon (LULU) Could Beat Earnings Estimates Again

## Evidence pool

| pos | role | ticker | published (C1) | offset d | event | tier | title |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | B | LULU | 2020-08-08 13:00:00 | -298.1 | other | same_ticker | What 4 Companies Highly Rated for Wellness Do Differently |
| 2 | A | LULU | 2021-12-14 15:32:18 | +195.0 | earnings | exact / future | Why Lululemon Athletica Might Just Be Getting Started |
| 3 | A | LULU | 2021-09-23 11:45:00 | +112.8 | earnings | exact / future | Here's Why the Market Loved Lululemon's Q2 Results |
| 4 | B | LULU | 2022-09-20 12:30:03 | +474.9 | other | same_ticker | If You Invested $1000 in Lululemon 10 Years Ago, This Is How Much You'd Have Now |
| 5 | A | LULU | 2022-10-20 21:50:21 | +505.2 | earnings | exact / future | Lululemon (LULU) Dips More Than Broader Markets: What You Should Know |
| 6 | A | LULU | 2022-12-20 11:00:00 | +565.8 | earnings | exact / future | Here's My Top Growth Stock to Buy in 2022 |
| 7 | A | LULU | 2022-07-08 16:00:06 | +401.0 | earnings | exact / future | What Makes Lululemon (LULU) a New Buy Stock |
| 8 | A | LULU | 2021-11-27 18:23:00 | +178.1 | earnings | exact / future | Lululemon Earnings: What to Watch on Dec. 9 |
| 9 | A | LULU | 2022-05-19 21:45:10 | +351.2 | earnings | exact / future | Lululemon (LULU) Stock Moves -0.48%: What You Should Know |
| 10 | **GT** | LULU | 2021-06-02 16:10:05 | +0.0 | earnings | - | Why Lululemon (LULU) Could Beat Earnings Estimates Again |
| 11 | B | LULU | 2022-04-05 14:20:00 | +306.9 | other | same_ticker | The 3 Best Stocks to Set You Up for Early Retirement |

Composition: 7A / 3B; Type-A tiers {'exact': 7, 'family': 0, 'manual_rescue': 0}; direction {'historical': 0, 'future': 7}; |offset| min 112.82 / median 351.23 / max 565.78 days.

## What changed between C1 and C2

- time series axis: `2021-05-26 16:15:00 | 327.40` -> `Position 1 | 327.40`
- article publication timestamps: 11 shown in C1, 0 in C2
- in-article temporal expressions masked: 125 spans -> `[DATE]` / `[YEAR]` / `[QUARTER]`

Verified unchanged: question and options (byte-identical), ticker, gold answer, time-series numeric values and length, article identities and order, article count, and all non-temporal article text. Re-masking the C1 articles reproduces the C2 articles byte for byte. Diff audit: 125 textual changes, 0 flagged.

## Interpretation

- observable temporal use in C1: **EXPLICIT_TEMPORAL_USE** - rationale states 'rising from ~316 to ~319 in the hours leading up to the 16:10 article publication on June 2, 2021' and 'the series ends right at the publish time'
- observable temporal use in C2: **NO_VISIBLE_TEMPORAL_USE** - rationale describes the series only by shape - 'mild upward drift for much of the series before a later decline' - and names no date, publication time or period
- evidence relied on: C1 **GT**, C2 **GT**
- temporal admissibility of the cited evidence: C1 cited the ground-truth article only; no alias used; C2 cited the ground-truth article only
- semantic vs temporal reliance: C1 **TEMPORAL_GATING_VISIBLE**, C2 **SEMANTIC_MATCH_DOMINANT**
- most likely explanation of the flip: **C1_TEMPORAL_HEURISTIC_MISLED**
- confidence in this interpretation: **HIGH**

The window ends at 2021-06-02 16:10:00 and the ground-truth article publishes at 16:10:05, so the series contains no post-publication point at all. In C1 the model saw that alignment, concluded that the 'sharp drop following the news' asserted by option D is not observable, and answered D. That reasoning is only available when timestamps are visible, and it steered the model onto a non-gold option. In C2 the same check is impossible, so the model evaluated option C against the shape of the whole series and answered C, the gold. The gain here is not evidence that the model reasons better without time; it is evidence that precise temporal alignment can expose an answer option the benchmark's gold label does not treat as the intended one.

---

# Instance 96 - WMT

Transition: C1 wrong -> C2 correct

## Task

```
Which of the following statements about WMT's stock price and the given financial analysis is incorrect?
A. The Zacks Earnings ESP of +3.44% indicates that Walmart is positioned favorably in the market, suggesting potential results that exceed analyst expectations, even if the stock had a recent decline.
B. The significant earnings estimate revision activity mentioned in the news report indicates that analysts were optimistic about Walmart's performance, which could have led investors to expect a price increase prior to the earnings announcement.
C. Following the news publication on November 12, the stock price of Walmart exhibited a downward trend, dropping from approximately $149 to nearly $147.61 by the end of the observation period.
D. Given the historical price peaks, it can be inferred that a bullish trend will continue, likely returning Walmart's stock price to above $150 soon after the earnings report.
```

- gold answer: **D**
- ground-truth article: position 5, event `earnings`, published 2021-11-12 14:17:00
- time series: 380 points

## C1

- answer **C** (incorrect), confidence 0.75
- rationale: The time series shows the price ending around $148.54 on 2021-11-11 (last data point), not dropping to $147.61 as claimed; the actual trend was a modest decline from ~$149 to ~$148.5, not to $147.61.

Cited evidence:

- Article 5 -> position 5, **GT** - Should You Buy Walmart (WMT) Ahead of Earnings?

## C2

- answer **D** (correct), confidence 0.7
- rationale: The time series shows WMT trending downward from ~150.6 to ~148.5, with no clear pattern supporting a bullish resumption above $150; this claim is speculative and unsupported by the data, unlike C which roughly matches the observed decline pattern.

Cited evidence:

_no article cited_

## Evidence pool

| pos | role | ticker | published (C1) | offset d | event | tier | title |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | B | SDC | 2021-10-25 13:28:00 | -18.0 | product_launch | anchor_company_named | SmileDirectClub Expands Oral Care Line With Launch Of Two New Water Flossers |
| 2 | A | WMT | 2022-02-18 00:12:27 | +97.4 | earnings | exact / future | Walmart reports higher than projected EPS. Will the $135 support hold? |
| 3 | A | WMT | 2023-06-21 21:50:25 | +586.3 | earnings | exact / future | Walmart (WMT) Gains As Market Dips: What You Should Know |
| 4 | A | WMT | 2023-04-26 19:31:34 | +530.2 | earnings | exact / future | Walmart Is Ideal Defensive Stock: Analyst Cites Consumer Shift Towards Necessities and Cheaper Substitutes as Catalysts |
| 5 | **GT** | WMT | 2021-11-12 14:17:00 | +0.0 | earnings | - | Should You Buy Walmart (WMT) Ahead of Earnings? |
| 6 | A | WMT | 2021-05-13 16:05:27 | -182.9 | earnings | exact / historical | Walmart Q1 Earnings Preview: Here's What You Need to Know |
| 7 | A | WMT | 2022-09-26 13:00:13 | +317.9 | earnings | exact / future | Is Trending Stock Walmart Inc. (WMT) a Buy Now? |
| 8 | A | WMT | 2022-07-13 21:45:19 | +243.3 | earnings | exact / future | Walmart (WMT) Gains As Market Dips: What You Should Know |
| 9 | B | DSGX | 2021-12-08 11:45:00 | +25.9 | other | anchor_company_named | Descartes MacroPoint™ and McLeod Software PowerBroker® Solutions Integrated to Help Freight Brokers Unlock Capacity and Cover More Loads |
| 10 | B | DSGX | 2021-10-25 10:45:00 | -18.1 | other | anchor_company_named | Descartes MacroPoint™ and FreightWaves SONAR Integrated to Deliver Advanced Transportation Capacity Management Solution |
| 11 | A | WMT | 2022-08-03 13:00:11 | +263.9 | earnings | exact / future | Here is What to Know Beyond Why Walmart Inc. (WMT) is a Trending Stock |

Composition: 7A / 3B; Type-A tiers {'exact': 7, 'family': 0, 'manual_rescue': 0}; direction {'historical': 1, 'future': 6}; |offset| min 97.41 / median 263.95 / max 586.31 days.

## What changed between C1 and C2

- time series axis: `2021-11-05 14:20:00 | 150.62` -> `Position 1 | 150.62`
- article publication timestamps: 11 shown in C1, 0 in C2
- in-article temporal expressions masked: 60 spans -> `[DATE]` / `[YEAR]` / `[QUARTER]`

Verified unchanged: question and options (byte-identical), ticker, gold answer, time-series numeric values and length, article identities and order, article count, and all non-temporal article text. Re-masking the C1 articles reproduces the C2 articles byte for byte. Diff audit: 60 textual changes, 0 flagged.

## Interpretation

- observable temporal use in C1: **EXPLICIT_TEMPORAL_USE** - rationale states 'the price ending around $148.54 on 2021-11-11 (last data point)' - it dates the final observation and checks option C's 'following the news publication on November 12' against it
- observable temporal use in C2: **NO_VISIBLE_TEMPORAL_USE** - rationale compares options on trend shape only ('trending downward from ~150.6 to ~148.5') and returns an empty evidence_articles list
- evidence relied on: C1 **GT**, C2 **NO_CLEAR_ARTICLE**
- temporal admissibility of the cited evidence: C1 cited the ground-truth article only; C2 no article cited at all
- semantic vs temporal reliance: C1 **TEMPORAL_GATING_VISIBLE**, C2 **SEMANTIC_MATCH_DOMINANT**
- most likely explanation of the flip: **C1_TEMPORAL_HEURISTIC_MISLED**
- confidence in this interpretation: **HIGH**

The window ends 2021-11-11 20:55, 17.4 hours before the ground-truth article publishes. Option C asserts a decline 'following the news publication on November 12' - a claim the series cannot cover. With timestamps visible, C1 detected exactly that mismatch and answered C. With timestamps removed, the date in option C became uncheckable, the model stopped trying to verify it, and picked D as the speculative statement, which is the gold. Note the protocol asymmetry this case exposes: the answer options keep their absolute dates in C2 (this is one of 26/50 instances whose MCQA text carries absolute temporal tokens) while the evidence context has none, so a date-anchored option can no longer be checked against anything.

---

# Instance 176 - PLD

Transition: C1 wrong -> C2 correct

## Task

```
Which of the following statements about PLD's stock price and the given financial analysis is incorrect?
A. The average stock price during the time following the news publication was higher than the average price prior to the news, suggesting an overall positive sentiment shift among investors.
B. Following the news release, the stock price dipped initially but rebounded to around 126.8 by the end of the trading session.
C. The stock showed volatility after the news release, with a significant drop to a low of approximately 124.57, reflecting a negative reaction from the market before stabilizing.
D. The news regarding Prologis emphasized its strong positioning and ability to capitalize on shifts in the market, which could lead to investor confidence and potential upward momentum in the stock.
```

- gold answer: **A**
- ground-truth article: position 5, event `guidance`, published 2021-10-06 12:20:00
- time series: 390 points

## C1

- answer **C** (incorrect), confidence 0.62
- rationale: The time series shows the stock's actual intraday low (on 2021-10-01, the session most consistent with a dip-then-rebound pattern) was about 124.29, not 124.57 as stated in option C, making the specific figure inaccurate. Options B and D align closely with the data and news content, while A's claim about a broad average price increase is plausible given the overall upward drift in the series.

Cited evidence:

- Article 5 -> position 5, **GT** - Watch This Growth Stock If the Market Crashes

## C2

- answer **A** (correct), confidence 0.72
- rationale: The price series shows a sharp decline beginning around position 155-180 (down to ~124.3), which aligns with the earnings-day sell-off described in Article 3 (stock fell 4.4% on valuation concerns despite beating estimates). Computing averages before vs. after this drop shows the post-news average (~126.37) is actually lower than the pre-news average (~126.63), and the news itself describes a negative reaction, not a positive sentiment shift as claimed in A.

Cited evidence:

- Article 3 -> position 3, **TYPE_A_TEMPORAL_ALIAS** (future alias, +650.2 days, family match) - Why Prologis Stock Was Slipping Today

## Evidence pool

| pos | role | ticker | published (C1) | offset d | event | tier | title |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A | PLD | 2023-07-18 14:30:03 | +650.1 | earnings | family / future | Here's What Key Metrics Tell Us About Prologis (PLD) Q2 Earnings |
| 2 | B | PLD | 2021-06-07 12:30:02 | -121.0 | ma_deal | same_ticker | Here's How Much You'd Have If You Invested $1000 in Prologis a Decade Ago |
| 3 | A | PLD | 2023-07-18 17:38:00 | +650.2 | earnings | family / future | Why Prologis Stock Was Slipping Today |
| 4 | A | PLD | 2022-05-24 21:50:04 | +230.4 | earnings | family / future | Prologis (PLD) Stock Moves -0.33%: What You Should Know |
| 5 | **GT** | PLD | 2021-10-06 12:20:00 | +0.0 | guidance | - | Watch This Growth Stock If the Market Crashes |
| 6 | A | PLD | 2022-07-15 13:30:04 | +282.1 | earnings | family / future | Prologis (PLD) Boasts Earnings & Price Momentum: Should You Buy? |
| 7 | A | PLD | 2023-04-03 22:15:24 | +544.4 | earnings | family / future | Prologis (PLD) Stock Sinks As Market Gains: What You Should Know |
| 8 | A | PLD | 2023-08-10 10:36:00 | +672.9 | earnings | family / future | Is Prologis a Buy? |
| 9 | B | PLD | 2021-08-17 12:30:05 | -50.0 | ma_deal | same_ticker | Here's How Much You'd Have If You Invested $1000 in Prologis a Decade Ago |
| 10 | B | PLD | 2022-11-15 13:15:00 | +405.0 | dividend_buyback | same_ticker | 1 Dividend Stock Down 34% to Buy Hand Over Fist Right Now |
| 11 | B | PLD | 2021-07-30 12:30:06 | -68.0 | ma_deal | same_ticker | If You Invested $1000 in Prologis 10 Years Ago, This Is How Much You'd Have Now |

Composition: 6A / 4B; Type-A tiers {'exact': 0, 'family': 6, 'manual_rescue': 0}; direction {'historical': 0, 'future': 6}; |offset| min 230.4 / median 650.09 / max 672.93 days.

## What changed between C1 and C2

- time series axis: `2021-09-29 13:30:00 | 126.08` -> `Position 1 | 126.08`
- article publication timestamps: 11 shown in C1, 0 in C2
- in-article temporal expressions masked: 95 spans -> `[DATE]` / `[YEAR]` / `[QUARTER]`

Verified unchanged: question and options (byte-identical), ticker, gold answer, time-series numeric values and length, article identities and order, article count, and all non-temporal article text. Re-masking the C1 articles reproduces the C2 articles byte for byte. Diff audit: 93 textual changes, 0 flagged.

## Interpretation

- observable temporal use in C1: **EXPLICIT_TEMPORAL_USE** - rationale localises the dip - 'the stock's actual intraday low (on 2021-10-01, the session most consistent with a dip-then-rebound pattern)'
- observable temporal use in C2: **IMPLICIT_TEMPORAL_USE** - rationale reasons over ordinal positions and a before/after split - 'a sharp decline beginning around position 155-180', 'the post-news average (~126.37) is actually lower than the pre-news average (~126.63)' - but fixes the event by semantic match: 'aligns with the earnings-day sell-off described in Article 3'
- evidence relied on: C1 **GT**, C2 **TYPE_A_TEMPORAL_ALIAS**
- temporal admissibility of the cited evidence: C1 cited the ground-truth article only; C2 Article 3 is a future temporal alias at +650.2 days (published 2023-07-18) describing a July 2023 session; the window runs 2021-09-29 to 2021-10-05, so it cannot describe any move in it
- semantic vs temporal reliance: C1 **MIXED**, C2 **SEMANTIC_MATCH_DOMINANT**
- most likely explanation of the flip: **C2_SEMANTIC_SHORTCUT_RECOVERED**
- confidence in this interpretation: **HIGH**

C2 produced the gold answer, but its stated reason attributes the price drop in the window to an article published 650 days later. The answer is scored correct while the evidential chain is temporally invalid. C1, which could see that Article 3 is dated 2023, never cited it, and instead lost the item on a numeric-precision argument about option C (124.29 vs the stated 124.57). This is the clearest case in the set where accuracy improves while grounding degrades.

---

# Instance 252 - GILD

Transition: C1 correct -> C2 wrong

## Task

```
Which of the following statements about GILD's stock price and the given financial analysis is correct?
A. The stock price increased significantly after the FDA approval news on January 26, indicating that investors are highly optimistic about Gilead's future growth potential and financial performance.
B. Gilead Sciences' stock price remained stable after the news publication, hovering around $84, suggesting that the market was confident in the company's long-term prospects.
C. The historical stock price movements indicate that Gilead Sciences is entering a strong bullish trend, and this upward momentum is likely to continue following the recent news.
D. The news about Gilead's FDA approval for Sunlenca may create optimism for potential revenue growth; however, the price action immediately following the announcement reflected investor skepticism as the stock price did not rebound strongly.
```

- gold answer: **D**
- ground-truth article: position 11, event `guidance`, published 2023-01-26 13:55:00
- time series: 390 points

## C1

- answer **D** (correct), confidence 0.6
- rationale: Article 11 (Jan 26) discusses Sunlenca's FDA approval as a growth driver, but the price series around Jan 23-25 shows GILD fluctuating in a narrow ~$82-84 range without a strong sustained rally, indicating muted or skeptical investor reaction rather than a clear bullish breakout.

Cited evidence:

- Article 11 -> position 11, **GT** - Could Gilead Sciences Stock Help You Become a Millionaire?

## C2

- answer **B** (incorrect), confidence 0.55
- rationale: The time series shows GILD price oscillating narrowly between roughly $82-$84 throughout the entire period with no sharp breakout or sustained trend, indicating relative stability rather than a strong bullish move or clear skepticism/optimism reaction tied to a specific FDA news date.

Cited evidence:

- Article 11 -> position 11, **GT** - Could Gilead Sciences Stock Help You Become a Millionaire?

## Evidence pool

| pos | role | ticker | published (C1) | offset d | event | tier | title |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A | GILD | 2021-10-21 19:02:48 | -461.8 | earnings | family / historical | Gilead Sciences (GILD) Expected to Beat Earnings Estimates: What to Know Ahead of Q3 Release |
| 2 | A | GILD | 2021-07-21 21:50:18 | -553.7 | earnings | family / historical | Gilead Sciences (GILD) Stock Sinks As Market Gains: What You Should Know |
| 3 | A | GILD | 2022-07-12 21:50:17 | -197.7 | earnings | family / historical | Gilead Sciences (GILD) Stock Moves -0.51%: What You Should Know |
| 4 | B | IKNA | 2023-08-07 11:00:00 | +192.9 | ma_deal | anchor_company_named | Ikena Oncology Acquires Pionyr Immunotherapeutics in All-Stock Transaction |
| 5 | A | GILD | 2021-07-09 21:50:20 | -565.7 | earnings | family / historical | Gilead Sciences (GILD) Gains But Lags Market: What You Should Know |
| 6 | A | GILD | 2022-09-01 15:31:27 | -146.9 | earnings | family / historical | Gilead (GILD) Up 1.9% Since Last Earnings Report: Can It Continue? |
| 7 | A | GILD | 2021-05-20 13:19:00 | -616.0 | earnings | family / historical | This Top Healthcare Dividend Stock Is a Bargain Right Now |
| 8 | A | GILD | 2022-10-10 22:00:23 | -107.7 | earnings | family / historical | Gilead Sciences (GILD) Gains As Market Dips: What You Should Know |
| 9 | B | GILD | 2023-07-19 22:00:19 | +174.3 | other | same_ticker | Gilead Sciences (GILD) Outpaces Stock Market Gains: What You Should Know |
| 10 | B | GILD | 2022-12-08 15:00:00 | -49.0 | dividend_buyback | same_ticker | Is Gilead Sciences a Buy? |
| 11 | **GT** | GILD | 2023-01-26 13:55:00 | +0.0 | guidance | - | Could Gilead Sciences Stock Help You Become a Millionaire? |

Composition: 7A / 3B; Type-A tiers {'exact': 0, 'family': 7, 'manual_rescue': 0}; direction {'historical': 7, 'future': 0}; |offset| min 107.66 / median 461.79 / max 616.02 days.

## What changed between C1 and C2

- time series axis: `2023-01-19 14:30:00 | 84.17` -> `Position 1 | 84.17`
- article publication timestamps: 11 shown in C1, 0 in C2
- in-article temporal expressions masked: 84 spans -> `[DATE]` / `[YEAR]` / `[QUARTER]`

Verified unchanged: question and options (byte-identical), ticker, gold answer, time-series numeric values and length, article identities and order, article count, and all non-temporal article text. Re-masking the C1 articles reproduces the C2 articles byte for byte. Diff audit: 84 textual changes, 0 flagged.

## Interpretation

- observable temporal use in C1: **EXPLICIT_TEMPORAL_USE** - rationale anchors the article to the series - 'Article 11 (Jan 26) ... but the price series around Jan 23-25 shows GILD fluctuating in a narrow ~$82-84 range'
- observable temporal use in C2: **NO_VISIBLE_TEMPORAL_USE** - rationale states the anchor is missing: no 'skepticism/optimism reaction tied to a specific FDA news date', and describes only 'price oscillating narrowly between roughly $82-$84 throughout the entire period'
- evidence relied on: C1 **GT**, C2 **GT**
- temporal admissibility of the cited evidence: C1 cited the ground-truth article only; C2 cited the ground-truth article only
- semantic vs temporal reliance: C1 **TEMPORAL_GATING_VISIBLE**, C2 **SEMANTIC_MATCH_DOMINANT**
- most likely explanation of the flip: **CONSISTENT_WITH_TIMESTAMP_HELP**
- confidence in this interpretation: **HIGH**

Options B and D describe the same price behaviour and differ only in whether it is read relative to the announcement instant: B calls it stability, D calls it a muted reaction to the news. The ground-truth article itself never names the date - it says 'Before the end of last year' - so the publication timestamp is the only thing that ties the series to the announcement. C1 used it and chose D; C2's rationale explicitly reports that it cannot tie any reaction to a news date and falls back to B. No alias is involved in either condition: the mechanism is loss of the announcement anchor, not distractor confusion. One honest caveat: C1's own temporal reasoning was imperfect (it read Jan 23-25, which precedes publication, as the reaction), so the timestamp led it to the gold option without a fully valid inference.

---

# Instance 265 - BLDR

Transition: C1 wrong -> C2 correct

## Task

```
Which of the following statements about BLDR's stock price and the given financial analysis is correct?
A. Despite the positive news regarding Builders FirstSource's valuation metrics, the stock's price dropped by over $5 after the announcement, indicating a lack of investor confidence in the company's future outlook.
B. Builders FirstSource's P/CF ratio of 4.64 is far above the industry average, implying that the stock is overvalued compared to its sector peers.
C. The decrease in BLDR's stock price observed after the news indicates that value investing strategies are faltering, contrary to the principles that typically support such methodologies.
D. The stock price of BLDR increased from approximately $67.2 before the news to around $70.94 shortly after, reflecting a robust immediate interest from investors.
```

- gold answer: **D**
- ground-truth article: position 8, event `earnings`, published 2022-08-04 13:40:12
- time series: 390 points

## C1

- answer **A** (incorrect), confidence 0.62
- rationale: The time series shows BLDR peaking near $73.83 on 2022-08-01 and then falling to about $68.50-68.60 by 2022-08-04 13:40 (a drop of over $5), coinciding with the timing of Article 8 published 2022-08-04 which touted BLDR's attractive valuation (Forward P/E and P/CF below industry averages). This mismatch between the bullish valuation commentary and the actual price decline supports option A, while B is factually wrong (P/CF was below, not above, industry average) and D's price figures don't align with the data around the relevant news timestamp.

Cited evidence:

- Article 8 -> position 8, **GT** - Is Builders FirstSource (BLDR) a Great Value Stock Right Now?

## C2

- answer **D** (correct), confidence 0.62
- rationale: The time series shows a jump from about 67.2 (positions ~119-130) to roughly 70.7-71.0 (positions 154-155) within a short span, consistent with a strong upward move following positive earnings-related news (e.g., the Q4 earnings beat and raised estimates discussed in Article 7/10). Option B misstates the P/CF comparison (Article 8 shows BLDR's P/CF was below, not above, industry average), and options A and C are not supported by the price series, which shows a rise rather than a drop.

Cited evidence:

- Article 7 -> position 7, **TYPE_A_TEMPORAL_ALIAS** (historical alias, -125.9 days, exact match) - Builders FirstSource (BLDR) Down 12.1% Since Last Earnings Report: Can It Rebound?
- Article 10 -> position 10, **TYPE_A_TEMPORAL_ALIAS** (future alias, +279.1 days, exact match) - Can Builders FirstSource (BLDR) Run Higher on Rising Earnings Estimates?
- Article 8 -> position 8, **GT** - Is Builders FirstSource (BLDR) a Great Value Stock Right Now?

## Evidence pool

| pos | role | ticker | published (C1) | offset d | event | tier | title |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A | BLDR | 2023-04-27 22:15:12 | +266.4 | earnings | exact / future | Builders FirstSource (BLDR) Gains But Lags Market: What You Should Know |
| 2 | A | BLDR | 2022-02-11 22:45:08 | -173.6 | earnings | exact / historical | Builders FirstSource (BLDR) Stock Moves -0.94%: What You Should Know |
| 3 | B | BLDR | 2022-03-07 12:00:00 | -150.1 | ma_deal | same_ticker | Builders FirstSource Hires Amy Bass Messersmith as Chief People Officer |
| 4 | A | BLDR | 2023-05-30 13:40:13 | +299.0 | earnings | exact / future | Is Builders FirstSource (BLDR) Stock Undervalued Right Now? |
| 5 | A | BLDR | 2023-02-08 23:00:21 | +188.4 | earnings | exact / future | Builders FirstSource (BLDR) Stock Moves -0.21%: What You Should Know |
| 6 | B | BLDR | 2022-04-12 11:00:00 | -114.1 | executive | same_ticker | Builders FirstSource to Host First Quarter 2022 Financial Results Conference Call and Webcast |
| 7 | A | BLDR | 2022-03-31 15:30:28 | -125.9 | earnings | exact / historical | Builders FirstSource (BLDR) Down 12.1% Since Last Earnings Report: Can It Rebound? |
| 8 | **GT** | BLDR | 2022-08-04 13:40:12 | +0.0 | earnings | - | Is Builders FirstSource (BLDR) a Great Value Stock Right Now? |
| 9 | B | BLDR | 2023-04-05 11:00:00 | +243.9 | executive | same_ticker | Builders FirstSource to Host First Quarter Financial Results Conference Call and Webcast |
| 10 | A | BLDR | 2023-05-10 16:20:06 | +279.1 | earnings | exact / future | Can Builders FirstSource (BLDR) Run Higher on Rising Earnings Estimates? |
| 11 | A | BLDR | 2022-03-11 22:45:17 | -145.6 | earnings | exact / historical | Builders FirstSource (BLDR) Stock Moves -0.44%: What You Should Know |

Composition: 7A / 3B; Type-A tiers {'exact': 7, 'family': 0, 'manual_rescue': 0}; direction {'historical': 3, 'future': 4}; |offset| min 125.92 / median 188.39 / max 299.0 days.

## What changed between C1 and C2

- time series axis: `2022-07-28 13:45:00 | 65.47` -> `Position 1 | 65.47`
- article publication timestamps: 11 shown in C1, 0 in C2
- in-article temporal expressions masked: 85 spans -> `[DATE]` / `[YEAR]` / `[QUARTER]`

Verified unchanged: question and options (byte-identical), ticker, gold answer, time-series numeric values and length, article identities and order, article count, and all non-temporal article text. Re-masking the C1 articles reproduces the C2 articles byte for byte. Diff audit: 82 textual changes, 0 flagged.

## Interpretation

- observable temporal use in C1: **EXPLICIT_TEMPORAL_USE** - rationale aligns article and series by date - 'peaking near $73.83 on 2022-08-01 and then falling to about $68.50-68.60 by 2022-08-04 13:40 ... coinciding with the timing of Article 8 published 2022-08-04'
- observable temporal use in C2: **IMPLICIT_TEMPORAL_USE** - rationale reasons over ordinal positions ('positions ~119-130' to 'positions 154-155') and attributes the move to 'the Q4 earnings beat and raised estimates discussed in Article 7/10'
- evidence relied on: C1 **GT**, C2 **MULTIPLE**
- temporal admissibility of the cited evidence: C1 cited the ground-truth article only; the seven aliases in the pool were not used; C2 of the three cited articles, Article 7 is a historical alias at -125.9 days (2022-03-31) and Article 10 a future alias at +279.1 days (2023-05-10); only Article 8 (GT) is admissible, and the causal claim rests on the two aliases
- semantic vs temporal reliance: C1 **TEMPORAL_GATING_VISIBLE**, C2 **SEMANTIC_MATCH_DOMINANT**
- most likely explanation of the flip: **C2_SEMANTIC_SHORTCUT_RECOVERED** (secondary: C1_TEMPORAL_HEURISTIC_MISLED)
- confidence in this interpretation: **HIGH**

C2 answered D, the gold, and explained the rise by an earnings beat described in two articles dated four months before and nine months after the window. C1, with the dates visible, cited only the ground-truth article, anchored on the segment immediately preceding publication, read it as a decline of over $5 and answered A. Both segments are real: the series both rises earlier and falls at the end. The timestamp told C1 which segment was 'after the announcement' and that reading did not match the gold; without it, C2 read the larger rise and matched. The primary observable mechanism is C2's recovery through inadmissible evidence; the secondary one is C1 anchoring on the pre-publication tail.

---

# Instance 274 - PHM

Transition: C1 correct -> C2 wrong

## Task

```
Which of the following statements about PHM's stock price and the given financial analysis is incorrect?
A. The stock price of PulteGroup experienced a substantial increase following the news release, recovering from the 8% decline reported since the last earnings report.
B. The projected gross margin for PulteGroup in the upcoming quarter is expected to be between 28.5% and 29%, which is an increase from the previous year's first quarter margin of 25.5%.
C. The average price of homes sold by PulteGroup has shown an upward trend, rising from $490,000 a year ago to an expected range of $500,000-$510,000 for the upcoming quarter, indicating positive pricing power.
D. The report suggests that PulteGroup is likely to face challenges ahead given the flatlining of analyst estimates, which implies diminishing enthusiasm for future growth prospects.
```

- gold answer: **D**
- ground-truth article: position 9, event `earnings`, published 2022-03-03 16:30:56
- time series: 390 points

## C1

- answer **D** (correct), confidence 0.72
- rationale: Article 9 states that despite estimates flatlining over the past month, PulteGroup was assigned a Zacks Rank #2 (Buy) with an expectation of above-average returns, contradicting the claim that flat estimates imply diminishing enthusiasm or upcoming challenges.

Cited evidence:

- Article 9 -> position 9, **GT** - PulteGroup (PHM) Down 8% Since Last Earnings Report: Can It Rebound?

## C2

- answer **C** (incorrect), confidence 0.58
- rationale: Article 9 states the average selling price of homes delivered in the last reported quarter was $490,000 (a current, not prior-year, figure), while the forward guidance for the next quarter of $500,000-$510,000 is explicitly compared to a prior-year ASP of $430,000, not $490,000. Statement C therefore misattributes the $490,000 figure as the 'year ago' baseline, making it factually inconsistent with the article's actual figures.

Cited evidence:

- Article 9 -> position 9, **GT** - PulteGroup (PHM) Down 8% Since Last Earnings Report: Can It Rebound?

## Evidence pool

| pos | role | ticker | published (C1) | offset d | event | tier | title |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A | PHM | 2021-09-16 21:45:20 | -167.8 | earnings | exact / historical | PulteGroup (PHM) Gains As Market Dips: What You Should Know |
| 2 | A | PHM | 2021-10-19 19:02:06 | -134.9 | earnings | exact / historical | PulteGroup (PHM) Reports Next Week: Wall Street Expects Earnings Growth |
| 3 | B | PHM | 2023-05-31 13:30:07 | +453.9 | other | same_ticker | Brokers Suggest Investing in PulteGroup (PHM): Read This Before Placing a Bet |
| 4 | A | PHM | 2022-09-27 21:45:18 | +208.2 | earnings | exact / future | PulteGroup (PHM) Dips More Than Broader Markets: What You Should Know |
| 5 | A | PHM | 2022-08-23 13:00:12 | +172.8 | earnings | exact / future | PulteGroup, Inc. (PHM) is Attracting Investor Attention: Here is What You Should Know |
| 6 | B | PHM | 2023-05-17 12:30:03 | +439.8 | other | same_ticker | Here's How Much a $1000 Investment in PulteGroup Made 10 Years Ago Would Be Worth Today |
| 7 | A | PHM | 2022-08-31 21:45:19 | +181.2 | earnings | exact / future | PulteGroup (PHM) Stock Moves -0.78%: What You Should Know |
| 8 | B | PHM | 2022-09-19 17:09:16 | +200.0 | analyst_rating | same_ticker | Analyst Ratings for PulteGroup |
| 9 | **GT** | PHM | 2022-03-03 16:30:56 | +0.0 | earnings | - | PulteGroup (PHM) Down 8% Since Last Earnings Report: Can It Rebound? |
| 10 | A | PHM | 2022-08-12 13:00:11 | +161.8 | earnings | exact / future | PulteGroup, Inc. (PHM) Is a Trending Stock: Facts to Know Before Betting on It |
| 11 | A | PHM | 2021-06-28 21:45:21 | -247.8 | earnings | exact / historical | PulteGroup (PHM) Outpaces Stock Market Gains: What You Should Know |

Composition: 7A / 3B; Type-A tiers {'exact': 7, 'family': 0, 'manual_rescue': 0}; direction {'historical': 3, 'future': 4}; |offset| min 134.9 / median 172.85 / max 247.78 days.

## What changed between C1 and C2

- time series axis: `2022-02-24 16:35:00 | 45.35` -> `Position 1 | 45.35`
- article publication timestamps: 11 shown in C1, 0 in C2
- in-article temporal expressions masked: 80 spans -> `[DATE]` / `[YEAR]` / `[QUARTER]`

Verified unchanged: question and options (byte-identical), ticker, gold answer, time-series numeric values and length, article identities and order, article count, and all non-temporal article text. Re-masking the C1 articles reproduces the C2 articles byte for byte. Diff audit: 75 textual changes, 0 flagged.

## Interpretation

- observable temporal use in C1: **IMPLICIT_TEMPORAL_USE** - rationale refers to the reporting cycle only in relative terms - 'despite estimates flatlining over the past month' - wording that is present unchanged in both conditions
- observable temporal use in C2: **EXPLICIT_TEMPORAL_USE** - rationale is a period-attribution argument - '$490,000 (a current, not prior-year, figure)' vs 'a prior-year ASP of $430,000'
- evidence relied on: C1 **GT**, C2 **GT**
- temporal admissibility of the cited evidence: C1 cited the ground-truth article only; C2 cited the ground-truth article only
- semantic vs temporal reliance: C1 **SEMANTIC_MATCH_DOMINANT**, C2 **MIXED**
- most likely explanation of the flip: **POSSIBLY_TIMESTAMP_RELATED**
- confidence in this interpretation: **LOW**

C2's error is a period-attribution error, and this ground-truth article is the most heavily masked of any in the discordant set (26 masked spans, including 'first-quarter 2021' -> '[QUARTER] [YEAR]' and the Q1/Q2/Q3/Q4-of-2022 community-count sequence), so the article's period labels are exactly what C2 could no longer see. That makes a timestamp link plausible. It is not demonstrated, however: the two sentences C2's rationale actually quotes - 'The average selling price of homes delivered was $490,000, up 10% year over year' and 'suggesting an increase from $430,000 in the year-ago period' - are byte-identical in C1 and C2, so the information the model used was available in both. Reported as possibly related, with low confidence, rather than as a timestamp effect.

---

# Category counts

**C1_CORRECT_C2_WRONG**

- CONSISTENT_WITH_TIMESTAMP_HELP: 1
- POSSIBLY_TIMESTAMP_RELATED: 1
- NO_OBSERVABLE_TIMESTAMP_EFFECT: 0
- UNCLEAR: 0

**C1_WRONG_C2_CORRECT**

- C1_TEMPORAL_HEURISTIC_MISLED: 2
- C2_SEMANTIC_SHORTCUT_RECOVERED: 2
- LIKELY_RUN_VARIABILITY: 0
- OTHER_OBSERVABLE_MECHANISM: 0
- UNCLEAR: 0

No case required `LIKELY_RUN_VARIABILITY`: each of the four C1-wrong/C2-correct flips has an observable input-use explanation.

# Masking side-effect audit

Discordant scope (task 6): **NO_NON_TEMPORAL_MASKING_SIDE_EFFECT_FOUND** - 519 textual changes across the six cases, 0 flagged.

All 50 instances (superset): 5902 textual changes, 4 flagged, all in instance 215 and all adjudicated as genuine calendar years in French-language articles. The auditor was self-tested against injected clause deletion, entity substitution, negation flips and non-date number edits, and caught all four.
