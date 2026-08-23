# All-50 post-publication semantics audit

Diagnostic only, and independent of model correctness: every classification below is made from the question and option wording, the ground-truth publication time, the supplied window and the ground-truth article. The cross-tab with C1/C2 results comes last, after the classification was fixed.

## B1 Geometry

- instances with at least one time-series point after the ground-truth publication: **0 / 50**
- instances with none: **50 / 50**
- gap from last window point to publication: min -66.17 h, median -0.70 h, max -0.00 h (all negative)

every gap is negative: the window always ends before the ground-truth article publishes. This is the official input_window-only protocol and is not an error in itself.

## B2 Option categories (200 options)

- ADC: 6
- NPC: 90
- PPB: 99
- PRC: 5

### Price levels named by an option but absent from the window

| id | option | gold? | level |
| --- | --- | --- | --- |
| 15 | C | yes | 80 |
| 96 | C |  | 147.61 |
| 133 | D |  | 100 |
| 147 | A |  | 283.66 |
| 148 | A |  | 98.27 |
| 234 | B | yes | 180.81 |
| 268 | C | yes | 2023 |
| 303 | D | yes | 88.22 |
| 313 | D | yes | 18 |
| 313 | D | yes | 19 |
| 334 | C | yes | 53.83 |

Not every absent number is a price: analyst targets, P/E ratios, percentages and years also appear. The ones that matter are flagged per instance below.

## B3 Instance classification

- **INPUT_WINDOW_SUFFICIENT**: 20 - [15, 35, 41, 50, 51, 66, 120, 133, 147, 172, 182, 191, 256, 268, 274, 295, 320, 334, 453, 484]
- **PARTIALLY_UNDERDETERMINED**: 23 - [18, 37, 49, 53, 55, 61, 96, 98, 123, 124, 140, 148, 215, 233, 265, 275, 288, 317, 353, 371, 405, 441, 454]
- **POST_PUBLICATION_EVIDENCE_REQUIRED**: 7 - [47, 176, 201, 234, 252, 303, 313]

## B4 Gold-answer audit

Gold requires post-publication behaviour that is not supplied: **[47, 176, 201, 234, 252, 303, 313]**

Gold partially relies on it (label or framing is post-publication, substance is reachable from the article or the window): [37, 49, 53, 55, 61, 96, 98, 123, 124, 140, 148, 215, 233, 265, 275, 288, 317, 353, 371, 405, 441, 454]

Instances where in-window, pre-publication movement is described as happening after the news: [37, 49, 53, 55, 98, 120, 123, 140, 265, 317, 353, 371, 405]

### Per-instance reasoning

**15 NKE** - gold C - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.08 h vs publication. gold C is a valuation statement from the article; B and D carry post-publication presuppositions but both fail on their own content ('P/E ratios do not matter', 'unlikely that any buyers would emerge')

**18 LULU** - gold C - `PARTIALLY_UNDERDETERMINED`, gold reliance `none`

last window point -0.00 h vs publication. gold C is a claim about the pre-news series and is checkable, but D asserts a sharp drop after publication and is a live competitor for 'the incorrect statement'; deciding C over D needs post-publication data

**35 NVDA** - gold C - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -14.83 h vs publication. gold C states the in-window trend and is directly verifiable; A is unverifiable but the question asks which statement is correct

**37 F** - gold A - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.01 h vs publication. gold A says the price fell 'after the news publication'; the fall is in the window and ends at publication, and the GT article reports the same-day 6.6% drop, so the substance is available but the label is not

**41 JWN** - gold B - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.01 h vs publication. gold B is false on article content (estimates were revised up 34.78%)

**47 DIS** - gold B - `POST_PUBLICATION_EVIDENCE_REQUIRED`, gold reliance `required`

last window point -17.17 h vs publication. gold B asserts increased volatility 'since the 2021-07-16 timestamp'; the window ends 2021-07-15 19:55, 17.2 h before publication, so the evidence it names does not exist in the supplied input

**49 GM** - gold A - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.01 h vs publication. gold A (the incorrect statement) claims the price rose after the downgrade; the ~10% fall is in-window and the article reports it, but A, B and C all describe in-window movement as 'following the news'

**50 NUE** - gold C - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -1.92 h vs publication. gold C is an in-window decline with an explicit date, fully checkable

**51 MU** - gold C - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -14.27 h vs publication. no option requires post-publication observation; gold C is article content about the quarter's results

**53 MDLZ** - gold A - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -10.10 h vs publication. gold A reads the decline as post-announcement hesitation; the decline is in-window and 10.1 h before publication, but the dilution reading that distinguishes A from B/C/D comes from the article

**55 SPY** - gold C - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.03 h vs publication. gold C's levels ($375.89, below $374) both occur at the very end of the window (98% and 100%), i.e. at or just before publication, not after it

**61 TSM** - gold B - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.08 h vs publication. gold B (incorrect) claims a sharp post-news drop below $89; sub-$89 prices occur at 1-56% of the window, not at the end, and the article reports the stock rose - so the falsity is reachable, but only via article content

**66 CPB** - gold C - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.00 h vs publication. gold C is the reaffirmed fiscal-2023 outlook, straight from the article

**96 WMT** - gold D - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -17.37 h vs publication. option C names $147.61, a level absent from the supplied window, and dates it 'following the news publication on November 12' while the window ends 2021-11-11 20:55; C is a live competitor for 'incorrect'

**98 HRB** - gold D - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.05 h vs publication. gold D's shape (peak 25.67 then decline to 25.25) is in the window at 8-53% and 76-89%, but its date labels (Sept 29 to Sept 30) fall at or past the window end - the label is recoverable from shape alone

_close call: shape matches in-window but both date labels are outside it; could be argued as REQUIRED on the dates alone_

**120 MU** - gold B - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.04 h vs publication. gold B is false on article content (Zacks Rank 3 means in line, not underperform); option C calls the last in-window interval 'the first recorded interval after the announcement'

_close call: kept SUFFICIENT because the gold is refuted by article content, though option C mislabels the last in-window interval as post-announcement_

**123 SPY** - gold A - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.70 h vs publication. gold A ties the article's caution to 'the observed downward trend post-announcement'; that downward trend is entirely in-window

**124 ARCC** - gold B - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -2.09 h vs publication. gold B (incorrect) claims a significant fall after the Q2 call; the call publishes 2.1 h after the window ends, so no post-call price exists - the falsity rests on the article's reported results

**133 AMD** - gold A - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.01 h vs publication. gold A is explicitly about sentiment *prior to* the news release

**140 F** - gold B - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -13.15 h vs publication. gold B says the price 'opened at 13.11' on Aug 26 after publication; 13.11 occurs at 75-98% of the window, i.e. on Aug 25, 13.2 h before the article published

**147 LULU** - gold D - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.03 h vs publication. gold D is the analyst target of $389.8, taken from the article

**148 DIS** - gold C - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -1.84 h vs publication. option A names $98.27 on June 24 - a level absent from the window and a date after both the window end and publication; gold C's clause 'may justify the post-news price increase' is also post-publication

**172 NFLX** - gold A - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -15.70 h vs publication. gold A is the $7.9 billion revenue figure from the article

**176 PLD** - gold A - `POST_PUBLICATION_EVIDENCE_REQUIRED`, gold reliance `required`

last window point -16.42 h vs publication. gold A (the incorrect statement) compares the average price after publication with the average before it; publication is 16.4 h after the window ends, so the post-publication average does not exist and the comparison cannot be evaluated at all

**182 LECO** - gold A - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -15.58 h vs publication. gold A is a plausibility statement about the award's effect

**191 WMT** - gold B - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.00 h vs publication. gold B is the 24% two-year-stack e-commerce figure from the article

**201 GD** - gold B - `POST_PUBLICATION_EVIDENCE_REQUIRED`, gold reliance `required`

last window point -2.09 h vs publication. gold B asserts a rebound of over 2% 'within the first trading session after the news release'; the article publishes 2022-12-01 23:00 and the window ends 20:55, so the first post-news session is absent

**215 ADP** - gold C - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.02 h vs publication. gold C (incorrect) claims an immediate drop below 208.00; 208 is touched at 50-86% of the window and not at the end, so the falsity is reachable, but A and D both assert post-publication rises

**233 VZ** - gold B - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.07 h vs publication. gold B (incorrect) claims a >1% fall 'in the immediate aftermath'; publication is 4 minutes after the window ends

**234 DIS** - gold B - `POST_PUBLICATION_EVIDENCE_REQUIRED`, gold reliance `required`

last window point -66.17 h vs publication. gold B names 180.81 'shortly after the news was published'; that level is absent from the supplied window, whose last point is 66.2 h before publication - the gold names data the protocol does not supply

**252 GILD** - gold D - `POST_PUBLICATION_EVIDENCE_REQUIRED`, gold reliance `required`

last window point -17.00 h vs publication. all four options describe post-announcement price action and the window ends 17.0 h before publication; B ('remained stable ... around $84') and gold D ('did not rebound strongly') are indistinguishable from the supplied data

**256 KO** - gold C - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.08 h vs publication. gold C (incorrect) is refuted by its pre-news half alone: the series was already declining before publication, not trending upward

**265 BLDR** - gold D - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.00 h vs publication. gold D's move 67.2 -> 70.94 sits at 28-33% and 40-79% of the window, entirely mid-window; publication is at 100%, so the move it calls 'before the news' to 'shortly after' is wholly pre-publication

**268 CMG** - gold C - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.01 h vs publication. no option requires post-publication observation

**274 PHM** - gold D - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.02 h vs publication. gold D (incorrect) is refuted by the article's Zacks Rank #2 and its own estimate discussion

**275 AAPL** - gold B - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -3.34 h vs publication. gold B says the price began to decline after the earnings release; the window ends 3.3 h before the article, but the article itself reports the 3.72% after-hours slip

**288 NFLX** - gold C - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -1.84 h vs publication. gold C (incorrect) claims a significant post-publication increase; the article's +1.19% is what refutes it, not the series

**295 CM** - gold D - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -64.58 h vs publication. gold D (incorrect) is refuted in-window: the decline from the peak is not consistent, it rebounds repeatedly

**303 AMD** - gold D - `POST_PUBLICATION_EVIDENCE_REQUIRED`, gold reliance `required`

last window point -12.08 h vs publication. gold D describes a rise 'from 83.67 at the beginning of the subsequent time series to a peak of 88.22'; 88.22 is absent from the supplied window (max 87.71) and the phrase names a series the input-window protocol does not provide

**313 T** - gold D - `POST_PUBLICATION_EVIDENCE_REQUIRED`, gold reliance `required`

last window point -3.42 h vs publication. gold D rests on 'the subsequent decrease in stock price on April 19'; the window ends 2023-04-18 19:55 and publication is 23:20, so April 19 is entirely absent

**317 WIX** - gold A - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.08 h vs publication. gold A (incorrect) fails on its general claim that ratings cause sell-offs, but B and C - which the gold labels correct - both assert a post-publication rise, and that rise is in-window

_close call: kept PARTIAL rather than SUFFICIENT because two options the gold treats as correct assert post-publication behaviour_

**320 COST** - gold A - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.33 h vs publication. gold A is explicitly about the days *prior to* publication and its levels are in-window at 0-79% and 19-63%

**334 TOL** - gold C - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -0.05 h vs publication. gold C compares the analyst target with the close just before the news - both available

**353 RH** - gold B - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -16.33 h vs publication. gold B's peak 381.99 is at 63% of the window; the 'downward trend following the publication' it describes is the remaining 37% of the window, which is still 16.3 h before publication

**371 MHK** - gold A - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -13.00 h vs publication. gold A (incorrect) fails on its absolutist causal claim, but its own wording and options B and C describe an in-window decline as the move from a 'pre-news level' to a 'post-news level'

_close call: kept PARTIAL rather than SUFFICIENT because the gold's own wording is a before/after-publication comparison_

**405 MHK** - gold C - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.03 h vs publication. gold C says prices rose 'following the news announcement'; the rise is in-window and publication is 2 minutes after the window ends

**441 SPY** - gold B - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -0.07 h vs publication. gold B (incorrect) claims a consistent rise after November 1st; there is no post-publication data, and the in-window Nov 1 trend is down

**453 NKE** - gold C - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -1.84 h vs publication. gold C is the -15.32% vs -15.56% comparison from the article

**454 DDD** - gold C - `PARTIALLY_UNDERDETERMINED`, gold reliance `partial`

last window point -16.92 h vs publication. gold C ends with 'leading to a sell-off on the stock post-news'; the window ends 16.9 h before publication, but the article reports the drop

**484 O** - gold B - `INPUT_WINDOW_SUFFICIENT`, gold reliance `none`

last window point -4.59 h vs publication. gold B is the cash cap rate figure from the earnings call transcript

## B5 Cross-tab with C1/C2 (descriptive, no tests)

| class | n | C1 acc | C2 acc | C1->C2 wrong | C1->C2 fixed | both wrong |
| --- | --- | --- | --- | --- | --- | --- |
| INPUT_WINDOW_SUFFICIENT | 20 | 1.00 | 0.95 | [274] | - | - |
| PARTIALLY_UNDERDETERMINED | 23 | 0.87 | 1.00 | - | [18, 96, 265] | - |
| POST_PUBLICATION_EVIDENCE_REQUIRED | 7 | 0.57 | 0.57 | [252] | [176] | [47, 201] |

C1 errors by class: {'PARTIALLY_UNDERDETERMINED': [18, 96, 265], 'POST_PUBLICATION_EVIDENCE_REQUIRED': [47, 176, 201]}

C2 errors by class: {'INPUT_WINDOW_SUFFICIENT': [274], 'POST_PUBLICATION_EVIDENCE_REQUIRED': [47, 201, 252]}

### Supplementary cross-tabs

| split | n | C1 acc | C2 acc |
| --- | --- | --- | --- |
| by_gold_post_publication_reliance = none | 21 | 0.95 | 0.95 |
| by_gold_post_publication_reliance = partial | 22 | 0.91 | 1.00 |
| by_gold_post_publication_reliance = required | 7 | 0.57 | 0.57 |
| by_in_window_movement_mislabelled = False | 37 | 0.86 | 0.89 |
| by_in_window_movement_mislabelled = True | 13 | 0.92 | 1.00 |

Post-hoc subgroups on 50 items; no significance testing, and no instance was modified or excluded on the basis of this audit.
