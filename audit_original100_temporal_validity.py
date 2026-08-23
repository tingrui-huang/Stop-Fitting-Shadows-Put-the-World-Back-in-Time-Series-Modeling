"""Outcome-blind temporal-validity audit of the original 100 MTBench-derived MCQA.

Reads ONLY the two raw source files:

    c0_data.json        (the audit brief names it "c0_data(2).json"; the
                         repository copy is c0_data.json - same 50 rows, and it
                         is read-only on disk)
    hard50_data.json

Nothing under results/, out_paper50_reviewed/, final50_*, no distractor pool
and no model output of any kind is opened by this script.  The question it
answers is upstream of every condition and every model run:

    how many of the original 100 items are decidable from the time series and
    ground-truth article the raw data actually supplies?

Mechanical facts (row counts, geometry, price-level matching, article-number
matching) are computed here.  Option semantics and gold support are hand-read
judgements, recorded in the annotation tables below with a one-line reason and
a confidence; every non-obvious call is carried into the borderline review
rather than silently resolved.

Writes into audits/ only.  Modifies nothing.

Usage:  python audit_original100_temporal_validity.py
"""

import datetime as dt
import json
import os
import re

UTC = dt.timezone.utc
SOURCES = {"c0_data.json": "c0", "hard50_data.json": "hard50"}
OUT = "audits"
PRICE_TOL_ABS = 0.02
PRICE_TOL_REL = 0.0015

# option temporal-requirement categories
PRE = "PRE_PUBLICATION_OR_STATIC"
POST = "POST_PUBLICATION_PRICE_REQUIRED"
BA = "BEFORE_AFTER_COMPARISON_REQUIRED"
FC = "FUTURE_FORECAST_OR_EXPECTATION"
AD = "ABSOLUTE_DATE_REFERENCE"
ML = "TEMPORALLY_MISLABELED_OBSERVED_MOVE"
AM = "AMBIGUOUS_TEMPORAL_REQUIREMENT"

# gold support classes
G_FULL = "GOLD_FULLY_VERIFIABLE"
G_SEM = "GOLD_SEMANTICALLY_VERIFIABLE"
G_REQ = "GOLD_REQUIRES_UNAVAILABLE_POST_PUBLICATION_TS"
G_ML = "GOLD_TEMPORALLY_MISLABELED"
G_AMB = "GOLD_AMBIGUOUS"

# instance classes, in precedence order
I_REQ = "GOLD_REQUIRES_UNAVAILABLE_FUTURE"
I_LAB = "TEMPORAL_LABEL_INCONSISTENCY"
I_OTH = "OTHER_AMBIGUITY"
I_DIS = "GOLD_VALID_BUT_DISTRACTORS_UNDERDETERMINED"
I_WELL = "STRICTLY_WELL_POSED"
PRECEDENCE = [I_REQ, I_LAB, I_OTH, I_DIS, I_WELL]

# --------------------------------------------------------------------------
# adjudication rules, stated once and applied uniformly
# --------------------------------------------------------------------------
RULES = {
    "mislabeled_observed_move":
        "an option is TEMPORALLY_MISLABELED_OBSERVED_MOVE when it frames a move "
        "as after/following/since the publication AND the move it describes is "
        "demonstrably the supplied pre-publication move - established either by "
        "matching its named price levels inside the window, or by the "
        "ground-truth article reporting the same move as having happened at or "
        "before publication. A merely false post-publication claim is not a "
        "mislabel.",
    "gold_requires_vs_mislabeled":
        "GOLD_TEMPORALLY_MISLABELED needs the same demonstration. Where a gold "
        "asserts post-publication price behaviour but names no level and the "
        "article does not report it, the honest verdict is "
        "GOLD_REQUIRES_UNAVAILABLE_POST_PUBLICATION_TS with a borderline note - "
        "the relocation cannot be shown, only suspected.",
    "incorrect_statement_items":
        "for 'which statement is incorrect' items the gold is the false option. "
        "If its falsity follows from article content or from internal logic it "
        "is GOLD_SEMANTICALLY_VERIFIABLE even when its wording is about "
        "post-publication prices; if refuting it would need the absent prices, "
        "it is GOLD_REQUIRES_UNAVAILABLE_POST_PUBLICATION_TS.",
    "distractor_underdetermined":
        "a competing option makes the item GOLD_VALID_BUT_DISTRACTORS_"
        "UNDERDETERMINED only when evaluating that option needs absent "
        "post-publication prices. An option that fails on its own logic, on an "
        "absurd causal claim, or on article facts does not count, even if it "
        "carries post-publication wording.",
    "price_tolerance":
        "a named level counts as present in the window when some sample matches "
        "it within max(%.2f absolute, %.4f relative)." % (PRICE_TOL_ABS,
                                                          PRICE_TOL_REL),
}

# --------------------------------------------------------------------------
# annotations: instance_id -> (options ABCD, gold class, instance class,
#                             confidence, note, alt_instance_class or None)
# --------------------------------------------------------------------------
ANN = {
    # ---- c0_data.json ----------------------------------------------------
    4: ((PRE, AD, ML, FC), G_SEM, I_LAB, "HIGH",
        "option C moves the in-window 31.6925-32.6013 band (window tail runs "
        "31.37-32.27) to 'following the news publication'", None),
    6: ((PRE, PRE, FC, POST), G_SEM, I_DIS, "MEDIUM",
        "gold C is a non-sequitur about divesting gaming; option D asserts a 4% "
        "post-publication premarket decline that the window cannot show", I_WELL),
    15: ((PRE, POST, PRE, FC), G_SEM, I_WELL, "MEDIUM",
         "gold C is the article's P/E story; option B presupposes a post-news "
         "rise but fails on its own claim that P/E ratios do not matter", I_DIS),
    18: ((PRE, PRE, PRE, POST), G_SEM, I_DIS, "HIGH",
         "option D ('Following the news publication ... dropped sharply') is a "
         "live competitor for the incorrect statement and cannot be falsified",
         None),
    19: ((PRE, POST, POST, FC), G_SEM, I_DIS, "HIGH",
         "option C names 116.32 'by the end of the following trading session'; "
         "that level is absent from the window", None),
    35: ((POST, PRE, PRE, FC), G_FULL, I_DIS, "MEDIUM",
         "gold C states the in-window uptrend and is directly checkable; "
         "option A's post-publication drop is not", I_WELL),
    37: ((ML, PRE, PRE, POST), G_ML, I_LAB, "HIGH",
         "gold A dates Ford's fall 'after the news publication'; the fall "
         "(13.46 -> 11.32) is the supplied window and ends at publication, and "
         "the article reports it as the same day's move", None),
    47: ((POST, POST, PRE, POST), G_REQ, I_REQ, "HIGH",
         "gold B rests on 'the fluctuations since the 2021-07-16 timestamp'; "
         "the window ends 2021-07-15 19:55", None),
    49: ((POST, ML, ML, PRE), G_SEM, I_LAB, "HIGH",
         "options B and C place the in-window 54.31 -> 49.28 decline 'following "
         "the news'; gold A is refuted by the article's report of the fall",
         None),
    50: ((POST, PRE, AD, PRE), G_FULL, I_WELL, "MEDIUM",
         "gold C is an in-window decline with an explicit date; option A "
         "presupposes a post-news increase but fails on its own reasoning",
         I_DIS),
    51: ((PRE, FC, PRE, PRE), G_SEM, I_WELL, "HIGH",
         "gold C is the quarter's reported results; no option needs absent "
         "prices", None),
    54: ((POST, PRE, PRE, PRE), G_REQ, I_REQ, "MEDIUM",
         "gold A claims a rebound 'to over $260 after the news announcement'; "
         "the window closes at 252.96, which makes it implausible but cannot "
         "refute it", I_WELL),
    56: ((POST, POST, POST, POST), G_REQ, I_REQ, "HIGH",
         "all four options describe the period following the news; publication "
         "is 0.01 h after the last window point, so none of them is checkable",
         None),
    61: ((POST, POST, PRE, POST), G_SEM, I_WELL, "MEDIUM",
         "the article reports that the stock rose after the Q4 results, which "
         "refutes gold B; options A and D lean on the same article statement",
         I_DIS),
    91: ((PRE, FC, PRE, ML), G_SEM, I_LAB, "MEDIUM",
         "option C dates the ~10% rise to 'the week before the news' and option "
         "D relabels the same rise as 'seen in the stock price after the news'",
         None),
    96: ((PRE, PRE, POST, FC), G_SEM, I_DIS, "HIGH",
         "option C names 147.61 'by the end of the observation period'; that "
         "level is absent from the window", None),
    120: ((PRE, PRE, ML, PRE), G_SEM, I_LAB, "HIGH",
          "option C calls 74.6 -> 74.69 'the first recorded interval after the "
          "announcement'; both sit at 96-100% of the window, which closes at "
          "74.70, two minutes before publication", None),
    122: ((POST, PRE, POST, FC), G_SEM, I_DIS, "MEDIUM",
          "gold D is an unfounded forecast (and names 175, absent); options A "
          "and C describe a post-earnings jump the window cannot show", None),
    123: ((ML, PRE, POST, FC), G_ML, I_LAB, "MEDIUM",
          "gold A ties itself to 'the observed downward trend in stock prices "
          "post-announcement'; the observed downward trend (372 -> 361) is the "
          "supplied pre-publication window", None),
    130: ((PRE, ML, POST, FC), G_SEM, I_LAB, "MEDIUM",
          "option B moves the in-window 295.98 -> 301.20 rise into 'the "
          "subsequent trading session'; publication is at the window's end",
          None),
    133: ((PRE, POST, POST, FC), G_SEM, I_DIS, "MEDIUM",
          "gold A is explicitly about sentiment prior to the release; option B "
          "puts a close of 91.1021 'just after the news' while the window "
          "closes at 88.05", None),
    140: ((POST, ML, PRE, FC), G_ML, I_LAB, "HIGH",
          "gold B says the price 'opened at 13.11' on Aug 26 after publication; "
          "13.11 occurs in-window on Aug 25, 13.2 h before the article", None),
    147: ((POST, FC, POST, PRE), G_SEM, I_DIS, "MEDIUM",
          "gold D is the article's $389.8 target; option A names 283.66 "
          "(absent) and option C composes a window-tail level with a mid-window "
          "one", None),
    172: ((PRE, PRE, PRE, POST), G_SEM, I_DIS, "MEDIUM",
          "gold A is the article's revenue figure; option D asserts a "
          "post-publication rise that cannot be checked", I_WELL),
    191: ((PRE, PRE, POST, FC), G_SEM, I_DIS, "MEDIUM",
          "gold B is the article's e-commerce figure; option C describes "
          "'downward movement in stock price following the earnings report'",
          I_WELL),
    216: ((PRE, POST, POST, FC), G_REQ, I_REQ, "MEDIUM",
          "gold B claims a significant rise after the contract news; "
          "publication is 10.8 h past the window end, so the in-window rise "
          "cannot be what it describes, and no level is named", I_LAB),
    218: ((POST, POST, PRE, POST), G_REQ, I_REQ, "MEDIUM",
          "gold D describes 'the period following the news release'; "
          "publication is 0.08 h after the last window point and no level is "
          "named", I_LAB),
    229: ((PRE, PRE, POST, POST), G_REQ, I_REQ, "MEDIUM",
          "gold D claims a notable increase after publication; publication "
          "coincides with the window end and no level is named", I_LAB),
    234: ((POST, POST, FC, POST), G_REQ, I_REQ, "HIGH",
          "gold B names 180.81 'shortly after the news was published'; that "
          "level is absent and the window ends 66.2 h before publication", None),
    256: ((PRE, PRE, PRE, PRE), G_SEM, I_WELL, "HIGH",
          "gold C is refuted by its own pre-news half - the series was already "
          "declining before publication", None),
    265: ((POST, PRE, POST, ML), G_ML, I_LAB, "HIGH",
          "gold D's 67.2 -> 70.94 move sits at 28-33% and 40-79% of the window; "
          "publication is at 100%, so what it calls 'before the news' to "
          "'shortly after' is wholly pre-publication", None),
    268: ((PRE, FC, PRE, PRE), G_SEM, I_WELL, "HIGH",
          "gold C is the article's S&P 500 and 54% figures", None),
    274: ((POST, PRE, PRE, PRE), G_SEM, I_WELL, "MEDIUM",
          "gold D is refuted by the article's own estimate discussion; option A "
          "asserts a post-release increase", I_DIS),
    275: ((PRE, POST, FC, FC), G_SEM, I_WELL, "MEDIUM",
          "gold B's decline is the after-hours slip the article reports, not "
          "anything in the window", None),
    288: ((PRE, AD, POST, PRE), G_SEM, I_WELL, "MEDIUM",
          "the article's +1.19% publication-day close is what refutes gold C",
          None),
    303: ((PRE, POST, POST, POST), G_REQ, I_REQ, "HIGH",
          "gold D names 88.22 (absent; window max 87.71) and locates the move "
          "'at the beginning of the subsequent time series'", None),
    311: ((PRE, FC, PRE, PRE), G_FULL, I_WELL, "MEDIUM",
          "gold D describes the observed interval; 'consistent rise' is a loose "
          "reading of 33.45 -> 34.29 with intermediate dips", None),
    313: ((POST, FC, PRE, POST), G_REQ, I_REQ, "HIGH",
          "gold D rests on 'the subsequent decrease in stock price on April "
          "19'; the window ends 2023-04-18 19:55", None),
    320: ((PRE, ML, FC, FC), G_FULL, I_LAB, "MEDIUM",
          "gold A is correctly scoped to 'the days prior'; option B treats the "
          "in-window 506 -> 488 decline as following the after-close release",
          None),
    333: ((PRE, POST, POST, ML), G_REQ, I_REQ, "MEDIUM",
          "gold B claims shares 'consistently rose after the news'; the window "
          "closes at 142.02 on a decline and publication is 10.2 h later",
          I_LAB),
    334: ((FC, FC, PRE, FC), G_FULL, I_WELL, "HIGH",
          "gold C compares the article's $53.83 target with the pre-news close "
          "47.93, giving 12.3% against the stated 12.9%", None),
    369: ((POST, PRE, PRE, POST), G_SEM, I_DIS, "MEDIUM",
          "gold B is internally wrong about the P/E comparison; option A names "
          "51.20, absent, and the window ends 74.1 h before publication", None),
    371: ((BA, ML, BA, PRE), G_SEM, I_LAB, "MEDIUM",
          "option B places the in-window 178.84 -> 168.74 decline after the "
          "publication; gold A fails on its absolutist causal claim", None),
    375: ((POST, FC, POST, PRE), G_REQ, I_REQ, "MEDIUM",
          "the window ends 56.1 h before publication, so gold C's 'price "
          "movement ... after the report' has no supplied referent", I_DIS),
    376: ((POST, POST, PRE, PRE), G_SEM, I_DIS, "MEDIUM",
          "gold D is refuted by the week's rise; option B names 354.74, absent "
          "from the window", None),
    405: ((PRE, POST, POST, PRE), G_REQ, I_REQ, "MEDIUM",
          "gold C claims an upward trend following the announcement; "
          "publication is 2 minutes after the window ends and the in-window "
          "trend is up, but no level is named, so the relocation cannot be "
          "demonstrated", I_LAB),
    408: ((PRE, PRE, PRE, POST), G_SEM, I_WELL, "MEDIUM",
          "gold B is a general statement about contrarian investing; option D "
          "asserts continuous growth following publication", I_DIS),
    441: ((AD, POST, POST, ML), G_REQ, I_REQ, "MEDIUM",
          "gold B claims the price 'consistently rose after November 1st'; "
          "there is no post-publication data, though the in-window Nov 1 trend "
          "is down", I_LAB),
    453: ((PRE, PRE, PRE, PRE), G_SEM, I_WELL, "HIGH",
          "gold C is the article's -15.32% vs -15.56% comparison; no option "
          "needs absent prices", None),
    467: ((POST, POST, POST, PRE), G_SEM, I_DIS, "MEDIUM",
          "gold C fails on its claim about cloud market leadership; options A "
          "and B assert post-publication increases 17.1 h beyond the window",
          None),

    # ---- hard50_data.json ------------------------------------------------
    10: ((FC, FC, PRE, FC), G_SEM, I_OTH, "MEDIUM",
         "all four options are forecasts; gold A wins only by being the hedged "
         "one ('if external market conditions improve ... might'), so no option "
         "is verifiable from the supplied input", I_WELL),
    36: ((PRE, POST, ML, POST), G_SEM, I_LAB, "MEDIUM",
         "gold B is false because the earnings had not been announced yet; "
         "option C moves the in-window 223.62 -> 225.16 pair to 'shortly after "
         "the news was published'", I_REQ),
    41: ((PRE, PRE, POST, AD), G_SEM, I_WELL, "MEDIUM",
         "gold B is contradicted by the article's 34.78% upward revision; "
         "option C's post-news 'stability' is a soft attribution, not a "
         "checkable price claim", I_DIS),
    53: ((POST, PRE, POST, POST), G_REQ, I_REQ, "MEDIUM",
         "gold A reads the decline as post-announcement hesitation; publication "
         "is 10.1 h past the window end and no level is named", I_LAB),
    55: ((PRE, PRE, ML, POST), G_ML, I_LAB, "MEDIUM",
         "gold C's levels 375.89 and below-374 both occur at the very end of "
         "the window (98% and 100%), i.e. at or just before publication", None),
    66: ((PRE, POST, PRE, ML), G_SEM, I_LAB, "MEDIUM",
         "gold C is the article's reaffirmed outlook; option D moves the "
         "in-window 46.6 -> 45.55 decline to 'after the earnings report'", None),
    78: ((POST, ML, ML, POST), G_SEM, I_LAB, "MEDIUM",
         "gold D is an absurd market-manipulation claim; options B and C place "
         "in-window levels (219.97, 225.83, 220) after the publication", None),
    92: ((POST, PRE, PRE, ML), G_SEM, I_LAB, "MEDIUM",
         "gold B invents a dilution the AGM notice does not contain; option D "
         "reads the in-window 34.84-35.17 band as a pre-news to post-news "
         "transition", None),
    98: ((POST, BA, POST, ML), G_ML, I_LAB, "MEDIUM",
         "gold D's shape (peak 25.67, decline to 25.25) is in the window at "
         "8-53% and 76-89%, but its date labels (Sept 29 to Sept 30) sit at and "
         "beyond the window end", None),
    99: ((PRE, PRE, FC, FC), G_SEM, I_WELL, "HIGH",
         "gold A is the article's 3.45% earnings surprise; no option needs "
         "absent prices", None),
    117: ((FC, FC, FC, PRE), G_SEM, I_WELL, "HIGH",
          "gold D is the article's margin improvement; the other three are "
          "overreaching forecasts", None),
    124: ((PRE, POST, POST, PRE), G_SEM, I_DIS, "MEDIUM",
          "the call publishes 2.1 h after the window ends, so neither gold B's "
          "fall nor option C's 'upward momentum after the earnings "
          "announcement' can be checked; the article's results refute B", None),
    131: ((AD, PRE, POST, PRE), G_SEM, I_DIS, "MEDIUM",
          "gold B misstates the Zacks Rank; option C names 39.84 on October 4, "
          "a level absent from the window", None),
    136: ((POST, PRE, POST, PRE), G_SEM, I_WELL, "MEDIUM",
          "gold A is false about a months-long uptrend; option C's 3% rise is "
          "the article's own figure", None),
    142: ((POST, PRE, ML, POST), G_REQ, I_REQ, "MEDIUM",
          "gold D asserts a decrease after the news; publication is at the "
          "window end and nothing supplied can show or refute it", I_LAB),
    145: ((PRE, POST, PRE, PRE), G_SEM, I_WELL, "MEDIUM",
          "gold D is contradicted by the article's estimate revisions; option "
          "B's post-announcement rise is a soft attribution", I_DIS),
    148: ((POST, PRE, POST, FC), G_SEM, I_DIS, "MEDIUM",
          "gold C is the article's EPS estimate; option A names 98.27 on June "
          "24, absent from the window and after publication", None),
    174: ((POST, PRE, ML, POST), G_SEM, I_LAB, "MEDIUM",
          "gold B fails on its general claim; option C reads the in-window "
          "234.35 -> 224.94 decline as 'the decline observed post-news'", None),
    176: ((BA, POST, POST, PRE), G_REQ, I_REQ, "HIGH",
          "gold A compares the average price after publication with the average "
          "before it; publication is 16.4 h past the window end, so the "
          "post-publication average does not exist", None),
    182: ((PRE, POST, PRE, PRE), G_SEM, I_WELL, "MEDIUM",
          "gold A is a plausibility statement about the award", None),
    201: ((PRE, POST, POST, PRE), G_REQ, I_REQ, "HIGH",
          "gold B needs 'the first trading session after the news release'; the "
          "article publishes 23:00 and the window ends 20:55", None),
    215: ((POST, PRE, ML, POST), G_ML, I_LAB, "MEDIUM",
          "gold C says the price 'immediately dropped below 208.00' after the "
          "news; sub-208 prices occur at 50-86% of the window and the tail runs "
          "208.49-210.39", None),
    220: ((PRE, POST, FC, PRE), G_SEM, I_WELL, "MEDIUM",
          "gold C is refuted by the article's Zacks Rank #1; option B's "
          "post-publication uptrend is a soft attribution", I_DIS),
    223: ((PRE, POST, POST, POST), G_FULL, I_DIS, "MEDIUM",
          "gold A is checkable in-window (no consistent uptrend: 56.97 -> 56.70 "
          "with a 58.81 peak); options C and D name 55.4 and 55.28, both absent",
          None),
    233: ((PRE, PRE, PRE, ML), G_SEM, I_LAB, "MEDIUM",
          "gold B's >1% fall is 4 minutes past the window end and the article "
          "reports a beat; option D reads the in-window 58.20 level as the "
          "post-news stabilisation", None),
    238: ((PRE, POST, PRE, PRE), G_SEM, I_DIS, "MEDIUM",
          "gold A fails on its PEG conclusion; option B names 109.09 on July "
          "29, absent from the window", None),
    243: ((POST, POST, AD, POST), G_FULL, I_DIS, "MEDIUM",
          "gold C is correctly scoped to the week before September 22 and its "
          "levels are in-window; options A, B and D all describe the period "
          "after a publication 16.1 h past the window end", None),
    249: ((POST, PRE, FC, POST), G_REQ, I_REQ, "HIGH",
          "gold A describes 'the subsequent trading hours' after a publication "
          "89.1 h past the window end and names a peak of 128.18, absent from "
          "the window (max 127.31)", None),
    251: ((POST, POST, PRE, POST), G_REQ, I_REQ, "HIGH",
          "gold B turns on the stock opening lower 'the next day', which the "
          "window does not contain", None),
    252: ((POST, POST, POST, POST), G_REQ, I_REQ, "HIGH",
          "all four options describe post-announcement price action and "
          "publication is 17.0 h past the window end; B ('remained stable ... "
          "around $84') and gold D ('did not rebound strongly') are "
          "indistinguishable from the supplied data", None),
    262: ((POST, PRE, AD, POST), G_FULL, I_DIS, "MEDIUM",
          "gold C is the in-window decline leading up to May 5; options A and D "
          "describe post-publication behaviour", None),
    263: ((PRE, POST, POST, PRE), G_REQ, I_REQ, "MEDIUM",
          "gold C closes 'at its lowest point of $273.91 on June 29'; that "
          "level exists in-window but June 29 lies beyond the window, which "
          "ends June 28 19:55", I_LAB),
    278: ((ML, POST, PRE, AD), G_ML, I_LAB, "MEDIUM",
          "gold A puts a high of 30.95 'after the news release'; 30.95 occurs "
          "at 2% of the window, and publication is 63.7 h past its end", None),
    279: ((PRE, POST, POST, PRE), G_SEM, I_DIS, "MEDIUM",
          "gold A fails on its reading of a Zacks Rank #3; option B names "
          "190.56 on June 30, absent from the window", None),
    295: ((PRE, AD, ML, PRE), G_FULL, I_LAB, "MEDIUM",
          "gold D is refuted in-window (the decline from the 42.49 peak is not "
          "consistent); option C reads the in-window 41.80 level as the "
          "post-publication stabilisation, 64.6 h before the article", None),
    302: ((AD, POST, POST, POST), G_REQ, I_REQ, "MEDIUM",
          "gold C asserts a decrease 'in the days following the news'; "
          "publication coincides with the window end", I_DIS),
    308: ((POST, PRE, ML, POST), G_REQ, I_REQ, "MEDIUM",
          "gold D claims an immediate post-publication drop 0.04 h past the "
          "window end; option C reads the in-window 106.35 -> 107.82 rise as "
          "'the subsequent trading window'", I_LAB),
    317: ((POST, ML, ML, PRE), G_SEM, I_LAB, "MEDIUM",
          "gold A fails on its general claim about analyst ratings; options B "
          "and C describe the in-window rise (56.70 -> 71.97, ending at "
          "publication) as following the news", None),
    353: ((POST, ML, POST, POST), G_ML, I_LAB, "MEDIUM",
          "gold B's peak 381.99 sits at 63% of the window; the 'downward trend "
          "following the publication' it describes is the remaining 37% of the "
          "window, still 16.3 h before the article", None),
    357: ((ML, POST, POST, POST), G_REQ, I_REQ, "MEDIUM",
          "gold B asserts a decline after a publication 16.6 h past the window "
          "end; option A reads the in-window 50.60 support as the post-news "
          "pattern", I_LAB),
    360: ((PRE, PRE, FC, PRE), G_SEM, I_WELL, "MEDIUM",
          "gold C is an unfounded recovery forecast; the other three rest on "
          "article content", None),
    382: ((FC, POST, POST, PRE), G_REQ, I_REQ, "HIGH",
          "gold B rests on 'the subsequent stock price data from April 25' and "
          "names 157.42, absent from the window, which ends April 24 19:55",
          None),
    394: ((POST, PRE, FC, AD), G_SEM, I_WELL, "MEDIUM",
          "gold C is an unfounded 'shoot up exponentially' forecast; option A's "
          "post-announcement decline is a soft attribution", I_DIS),
    418: ((POST, PRE, PRE, POST), G_REQ, I_REQ, "HIGH",
          "gold D names a peak of 46.85 following the news; the window's "
          "maximum is 45.46, so the level is absent", None),
    437: ((AD, ML, ML, POST), G_REQ, I_REQ, "MEDIUM",
          "gold D claims volatility decreased after a publication that "
          "coincides with the window end; options B and C place in-window "
          "levels after the news", I_LAB),
    448: ((FC, POST, FC, FC), G_SEM, I_WELL, "MEDIUM",
          "gold A restates the analyst's own implication; the rest are "
          "overreaching forecasts", None),
    454: ((POST, POST, POST, FC), G_SEM, I_WELL, "MEDIUM",
          "gold C's revenue decline and the post-news sell-off are both "
          "reported by the article", None),
    466: ((ML, PRE, PRE, PRE), G_SEM, I_LAB, "MEDIUM",
          "gold B is an unfounded rebound guarantee; option A places the "
          "in-window 158.36 -> 154.53 decline 'following the publication'",
          None),
    481: ((POST, POST, PRE, POST), G_REQ, I_REQ, "MEDIUM",
          "gold D claims a significant upward trend from the close before a "
          "publication 17.4 h past the window end; no level is named", I_LAB),
    484: ((POST, PRE, ML, PRE), G_SEM, I_WELL, "MEDIUM",
          "gold B is the transcript's cash cap rate; option C reads the "
          "in-window 61.50 level as an immediate post-news drop", I_LAB),
}

POST_WORDS = re.compile(
    r"\b(after|following|subsequent|since|thereafter|reaction|by the end|"
    r"shortly after|post-news|post-publication|immediately)\b", re.I)


# --------------------------------------------------------------------------
def parse_utc(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=UTC).timestamp()


def iso(t):
    return dt.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d %H:%M:%S")


def options_of(rec):
    out = {}
    for part in rec["mcqa_question"].splitlines():
        m = re.match(r"^([A-D])\.\s*(.*)$", part.strip(), re.S)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def price_claims(text, vals, article):
    """Mechanically locate every number in an option (task 4)."""
    lo, hi = min(vals), max(vals)
    out = []
    for x in re.findall(r"\$?(\d{1,5}(?:,\d{3})*(?:\.\d+)?)", text):
        n = float(x.replace(",", ""))
        in_article = bool(re.search(r"(?<![\d.])%s(?![\d])" % re.escape(x),
                                    article))
        plausible = lo * 0.9 <= n <= hi * 1.1
        rec = {"token": x, "value": n, "in_plausible_price_range": plausible,
               "appears_in_gt_article": in_article}
        if plausible:
            tol = max(PRICE_TOL_ABS, abs(n) * PRICE_TOL_REL)
            hits = [k for k, v in enumerate(vals) if abs(v - n) <= tol]
            rec["present_in_supplied_ts"] = bool(hits)
            rec["tolerance"] = round(tol, 4)
            rec["closest_actual_price"] = min(vals, key=lambda v: abs(v - n))
            if hits:
                rec["first_pct_of_window"] = round(
                    100.0 * hits[0] / (len(vals) - 1), 1)
                rec["last_pct_of_window"] = round(
                    100.0 * hits[-1] / (len(vals) - 1), 1)
                rec["referenced_move_is_before_publication"] = True
            else:
                rec["referenced_move_is_before_publication"] = False
        out.append(rec)
    return out


def date_claims(text, first_ts, last_ts):
    """Explicit dates in an option, and whether the window covers them."""
    out = []
    pat = (r"\b(January|February|March|April|May|June|July|August|September|"
           r"October|November|December)\s+(\d{1,2})(?:,\s*(\d{4}))?")
    for m in re.finditer(pat, text):
        out.append({"phrase": m.group(0), "month": m.group(1),
                    "day": int(m.group(2)),
                    "year": int(m.group(3)) if m.group(3) else None})
    for d in out:
        y = d["year"] or dt.datetime.fromtimestamp(last_ts, UTC).year
        try:
            t = dt.datetime.strptime("%s %d %d" % (d["month"], d["day"], y),
                                     "%B %d %Y").replace(tzinfo=UTC).timestamp()
        except ValueError:
            d["covered_by_supplied_ts"] = None
            continue
        d["covered_by_supplied_ts"] = first_ts - 86400 <= t <= last_ts
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, integrity = [], {}
    all_ids = []
    for path, tag in SOURCES.items():
        data = json.load(open(path, encoding="utf-8"))
        keys = set()
        for r in data:
            keys |= set(r.keys())
        ids = [r["instance_id"] for r in data]
        all_ids += ids
        suspicious = sorted(k for k in keys if any(
            s in k.lower() for s in ("output", "future", "forecast", "target_window",
                                     "y_values", "y_timestamps", "second")))
        integrity[path] = {
            "source_tag": tag, "n_rows": len(data),
            "n_unique_instance_ids": len(set(ids)),
            "duplicate_instance_ids": sorted(
                {i for i in ids if ids.count(i) > 1}),
            "schema_keys": sorted(keys),
            "output_window_like_fields": suspicious,
            "has_output_window_field": bool(suspicious),
            "n_ts_lengths_seen": sorted({len(r["ts_timestamps"]) for r in data}),
            "ts_values_length_mismatch": [r["instance_id"] for r in data
                                          if len(r["ts_timestamps"])
                                          != len(r["ts_values"])],
            "instances_with_duplicate_timestamp_rows": [
                r["instance_id"] for r in data
                if any(b <= a for a, b in zip(r["ts_timestamps"],
                                              r["ts_timestamps"][1:]))],
        }
        for rec in data:
            ts, vals = rec["ts_timestamps"], rec["ts_values"]
            g = parse_utc(rec["gt_published_utc"])
            iid = rec["instance_id"]
            opt_cats, gold_cls, inst_cls, conf, note, alt = ANN[iid]
            opts = options_of(rec)
            art = rec["gt_article_text"]
            per_opt = {}
            for k, letter in enumerate("ABCD"):
                text = opts.get(letter, "")
                per_opt[letter] = {
                    "text": text,
                    "is_gold": letter == rec["mcqa_answer"],
                    "primary_category": opt_cats[k],
                    "has_post_publication_wording": bool(POST_WORDS.search(text)),
                    "price_claims": price_claims(text, vals, art),
                    "date_claims": date_claims(text, ts[0], ts[-1]),
                }
            rows.append({
                "instance_id": iid, "source_file": path, "source_tag": tag,
                "ticker": rec["ticker"], "gold_answer": rec["mcqa_answer"],
                "subset": rec.get("subset"),
                "geometry": {
                    "first_ts": iso(ts[0]), "last_ts": iso(ts[-1]),
                    "gt_publication_timestamp": rec["gt_published_utc"],
                    "publication_minus_last_ts_hours": round((g - ts[-1]) / 3600.0, 4),
                    "has_ts_before_publication": any(t < g for t in ts),
                    "has_ts_at_or_after_publication": any(t >= g for t in ts),
                    "has_ts_strictly_after_publication": any(t > g for t in ts),
                    "n_points": len(vals),
                    "first_value": vals[0], "last_value": vals[-1],
                    "min_value": min(vals), "max_value": max(vals),
                },
                "question": rec["mcqa_question"].splitlines()[0],
                "options": per_opt,
                "gold_support_class": gold_cls,
                "instance_class": inst_cls,
                "alternative_instance_class": alt,
                "confidence": conf,
                "justification": note,
                "strict_temporal_eligible": inst_cls == I_WELL,
            })
    integrity["combined"] = {
        "total_rows": len(all_ids),
        "n_unique_instance_ids": len(set(all_ids)),
        "duplicate_instance_ids_across_files": sorted(
            {i for i in all_ids if all_ids.count(i) > 1}),
        "id_overlap_between_files": sorted(
            set(integrity["c0_data.json"] and
                [r["instance_id"] for r in json.load(
                    open("c0_data.json", encoding="utf-8"))])
            & set(r["instance_id"] for r in json.load(
                open("hard50_data.json", encoding="utf-8")))),
        "schema_difference": "hard50_data.json carries an extra 'subset' field "
                             "(constant value 'hard_50'); every other field is "
                             "identical in both files",
        "note_on_filename": "the brief names c0_data(2).json; the repository "
                            "holds c0_data.json, read-only, 50 rows, with "
                            "exactly the fields the brief lists",
    }
    rows.sort(key=lambda r: (r["source_tag"], r["instance_id"]))
    with open(os.path.join(OUT, "original100_temporal_validity.jsonl"), "w",
              encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = summarise(rows, integrity)
    write_outputs(rows, summary)
    report(summary)
    return rows, integrity


# --------------------------------------------------------------------------
def summarise(rows, integrity):
    gaps = sorted(r["geometry"]["publication_minus_last_ts_hours"] for r in rows)
    n = len(rows)

    def by(tag=None):
        sub = [r for r in rows if tag is None or r["source_tag"] == tag]
        c = {k: [] for k in PRECEDENCE}
        for r in sub:
            c[r["instance_class"]].append(r["instance_id"])
        return {"n": len(sub),
                "counts": {k: len(v) for k, v in c.items()},
                "instance_ids": {k: sorted(v) for k, v in c.items()}}

    opt_counts, post_req_opts, mislabel_opts = {}, [], []
    absent_levels, uncovered_dates = [], []
    for r in rows:
        for L, o in r["options"].items():
            opt_counts[o["primary_category"]] = \
                opt_counts.get(o["primary_category"], 0) + 1
            if o["primary_category"] in (POST, BA):
                post_req_opts.append("%d%s" % (r["instance_id"], L))
            if o["primary_category"] == ML:
                mislabel_opts.append("%d%s" % (r["instance_id"], L))
            for p in o["price_claims"]:
                if p.get("in_plausible_price_range") and \
                        not p.get("present_in_supplied_ts"):
                    absent_levels.append({
                        "instance_id": r["instance_id"], "option": L,
                        "is_gold": o["is_gold"], "claimed_price": p["value"],
                        "closest_actual_price": p["closest_actual_price"],
                        "tolerance": p["tolerance"]})
            for d in o["date_claims"]:
                if d.get("covered_by_supplied_ts") is False:
                    uncovered_dates.append({
                        "instance_id": r["instance_id"], "option": L,
                        "is_gold": o["is_gold"], "phrase": d["phrase"]})

    gold_counts = {}
    for r in rows:
        gold_counts[r["gold_support_class"]] = \
            gold_counts.get(r["gold_support_class"], 0) + 1
    problem_gold = sorted(r["instance_id"] for r in rows
                          if r["gold_support_class"] in (G_REQ, G_ML, G_AMB))
    borderline = sorted(r["instance_id"] for r in rows
                        if r["alternative_instance_class"])
    eligible = sorted(r["instance_id"] for r in rows
                      if r["strict_temporal_eligible"])
    eligible_up = sorted(set(eligible) | {r["instance_id"] for r in rows
                                          if r["alternative_instance_class"]
                                          == I_WELL})
    eligible_down = sorted(set(eligible) - {r["instance_id"] for r in rows
                                            if r["strict_temporal_eligible"]
                                            and r["alternative_instance_class"]})
    return {
        "outcome_blindness": {
            "sources_read": sorted(SOURCES),
            "statement": "no file under results/, out_paper50_reviewed/, no "
                         "final50_* file, no distractor pool and no model "
                         "prediction, rationale, confidence or correctness was "
                         "opened by this audit",
            "disclosure": "this session had earlier analysed 50 of these ids in "
                          "a different, outcome-aware task. The classifications "
                          "here were re-derived from the two raw files under the "
                          "rules recorded in RULES, using a different category "
                          "scheme and precedence order, and no model outcome was "
                          "consulted; the reader should still treat that prior "
                          "exposure as a limitation rather than assume perfect "
                          "blindness.",
        },
        "task1_pool_integrity": integrity,
        "task2_geometry": {
            "n_with_any_ts_after_gt_publication": sum(
                r["geometry"]["has_ts_strictly_after_publication"] for r in rows),
            "n_with_no_ts_after_gt_publication": sum(
                not r["geometry"]["has_ts_strictly_after_publication"]
                for r in rows),
            "n_with_ts_at_or_after_publication": sum(
                r["geometry"]["has_ts_at_or_after_publication"] for r in rows),
            "publication_minus_last_ts_hours": {
                "min": gaps[0], "median": gaps[n // 2], "max": gaps[-1],
                "note": "positive means publication happens after the last "
                        "supplied point"},
            "gap_distribution_hours": {
                "<=0.1": sum(1 for g in gaps if g <= 0.1),
                "0.1-2": sum(1 for g in gaps if 0.1 < g <= 2),
                "2-12": sum(1 for g in gaps if 2 < g <= 12),
                "12-24": sum(1 for g in gaps if 12 < g <= 24),
                ">24": sum(1 for g in gaps if g > 24)},
        },
        "task3_option_category_counts": dict(sorted(opt_counts.items())),
        "task3_options_requiring_post_publication": post_req_opts,
        "task3_options_with_mislabeled_observed_move": mislabel_opts,
        "task4_price_levels_absent_from_supplied_ts": absent_levels,
        "task4_dates_not_covered_by_supplied_ts": uncovered_dates,
        "task4_tolerance": RULES["price_tolerance"],
        "task5_gold_support_counts": dict(sorted(gold_counts.items())),
        "task5_problematic_gold_ids": problem_gold,
        "task5_gold_requires_unavailable_ids": sorted(
            r["instance_id"] for r in rows if r["gold_support_class"] == G_REQ),
        "task5_gold_temporally_mislabeled_ids": sorted(
            r["instance_id"] for r in rows if r["gold_support_class"] == G_ML),
        "task6_instance_classes": {"combined": by(), "c0": by("c0"),
                                   "hard50": by("hard50")},
        "task7_strict_eligibility": {
            "criterion": "instance_class == STRICTLY_WELL_POSED, decided only "
                         "from question and option semantics, the ground-truth "
                         "publication time, the supplied window and the "
                         "ground-truth article",
            "n_eligible": len(eligible),
            "eligible_ids": eligible,
            "eligible_by_source": {
                "c0": sorted(r["instance_id"] for r in rows
                             if r["strict_temporal_eligible"]
                             and r["source_tag"] == "c0"),
                "hard50": sorted(r["instance_id"] for r in rows
                                 if r["strict_temporal_eligible"]
                                 and r["source_tag"] == "hard50")},
            "ineligible_ids_by_reason": {
                k: by()["instance_ids"][k] for k in PRECEDENCE if k != I_WELL},
            "sensitivity_if_every_borderline_resolved_the_other_way": {
                "upper_bound": len(eligible_up), "upper_bound_ids": eligible_up,
                "lower_bound": len(eligible_down),
                "note": "even the upper bound stays well below 50"},
        },
        "task8_borderline_ids": borderline,
        "task9_option_level_totals": {
            "n_options": 4 * n,
            "n_options_requiring_post_publication_ts": len(post_req_opts),
            "n_options_with_mislabeled_observed_move": len(mislabel_opts),
            "n_problematic_gold_answers": len(problem_gold),
            "n_borderline_instances": len(borderline),
        },
        "confidence_counts": {
            c: sum(1 for r in rows if r["confidence"] == c)
            for c in ("HIGH", "MEDIUM", "LOW")},
        "adjudication_rules": RULES,
    }


def write_outputs(rows, s):
    with open(os.path.join(OUT, "original100_temporal_validity_summary.json"),
              "w", encoding="utf-8", newline="\n") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    e = s["task7_strict_eligibility"]
    with open(os.path.join(OUT, "original100_strict_eligible_ids.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump({"criterion": e["criterion"], "n_eligible": e["n_eligible"],
                   "instance_ids": e["eligible_ids"]}, f, indent=2,
                  ensure_ascii=False)

    g = s["task2_geometry"]
    t6 = s["task6_instance_classes"]
    md = ["# Outcome-blind temporal-validity audit of the original 100 MCQA", "",
          "Sources: `c0_data.json` (50) and `hard50_data.json` (50). No results "
          "file, condition build, distractor pool or model output was read. No "
          "source file was modified and no inference was run.", "",
          "## 1. Pool integrity", ""]
    for k in ("c0_data.json", "hard50_data.json"):
        i = s["task1_pool_integrity"][k]
        md += ["- **%s**: %d rows, %d unique ids, duplicates %s, "
               "output-window-like fields **%s**"
               % (k, i["n_rows"], i["n_unique_instance_ids"],
                  i["duplicate_instance_ids"] or "none",
                  i["output_window_like_fields"] or "NONE"),
               "  - time-series lengths seen: %s; rows with duplicated "
               "(timestamp, value) samples: %s"
               % (i["n_ts_lengths_seen"],
                  i["instances_with_duplicate_timestamp_rows"] or "none")]
    c = s["task1_pool_integrity"]["combined"]
    md += ["- combined: **%d rows, %d unique ids**, id overlap between files %s"
           % (c["total_rows"], c["n_unique_instance_ids"],
              c["id_overlap_between_files"] or "none"),
           "- schema difference: %s" % c["schema_difference"],
           "- %s" % c["note_on_filename"], "",
           "## 2. Temporal geometry", "",
           "- instances with any time-series point strictly after the "
           "ground-truth publication: **%d / 100**"
           % g["n_with_any_ts_after_gt_publication"],
           "- instances with none: **%d / 100**"
           % g["n_with_no_ts_after_gt_publication"],
           "- publication minus last supplied point: min %.2f h, median %.2f h, "
           "max %.2f h (all positive - publication always follows the window)"
           % (g["publication_minus_last_ts_hours"]["min"],
              g["publication_minus_last_ts_hours"]["median"],
              g["publication_minus_last_ts_hours"]["max"]),
           "", "| gap (hours) | n |", "| --- | --- |"]
    for k, v in g["gap_distribution_hours"].items():
        md.append("| %s | %d |" % (k, v))
    md += ["", "Having no post-publication series is the official input-window "
           "protocol and is not an error in itself. What follows asks whether "
           "the question semantics need what the protocol does not supply.", "",
           "## 3. Option temporal requirements (400 options)", ""]
    for k, v in s["task3_option_category_counts"].items():
        md.append("- %s: %d" % (k, v))
    md += ["", "Options requiring post-publication prices or a before/after "
           "comparison: **%d / 400**."
           % s["task9_option_level_totals"]["n_options_requiring_post_publication_ts"],
           "", "Options that relabel a supplied pre-publication move as "
           "happening after the news: **%d / 400** - %s"
           % (s["task9_option_level_totals"]["n_options_with_mislabeled_observed_move"],
              ", ".join(s["task3_options_with_mislabeled_observed_move"])), "",
           "## 4. Mechanical price and date checks", "",
           s["task4_tolerance"], "",
           "### Price levels named by an option but absent from the supplied series",
           "", "| id | option | gold? | claimed | closest actual |",
           "| --- | --- | --- | --- | --- |"]
    for x in s["task4_price_levels_absent_from_supplied_ts"]:
        md.append("| %d | %s | %s | %g | %g |"
                  % (x["instance_id"], x["option"], "yes" if x["is_gold"] else "",
                     x["claimed_price"], x["closest_actual_price"]))
    md += ["", "Not every number in this table is a share price - analyst "
           "targets, P/E ratios and percentages land in the same numeric band "
           "and are noted per instance in the JSONL.", "",
           "### Explicit dates outside the supplied window", "",
           "| id | option | gold? | phrase |", "| --- | --- | --- | --- |"]
    for x in s["task4_dates_not_covered_by_supplied_ts"]:
        md.append("| %d | %s | %s | %s |" % (x["instance_id"], x["option"],
                                             "yes" if x["is_gold"] else "",
                                             x["phrase"]))
    md += ["", "## 5. Gold-answer support", ""]
    for k, v in s["task5_gold_support_counts"].items():
        md.append("- %s: %d" % (k, v))
    md += ["", "Problematic golds (**%d**): %s"
           % (len(s["task5_problematic_gold_ids"]), s["task5_problematic_gold_ids"]),
           "", "- requires unavailable post-publication series: %s"
           % s["task5_gold_requires_unavailable_ids"],
           "- describes a supplied pre-publication move as post-publication: %s"
           % s["task5_gold_temporally_mislabeled_ids"], "",
           "## 6. Instance well-posedness", "",
           "Precedence: %s" % " > ".join(PRECEDENCE), "",
           "| class | combined | c0 | hard50 |", "| --- | --- | --- | --- |"]
    for k in PRECEDENCE:
        md.append("| %s | %d | %d | %d |"
                  % (k, t6["combined"]["counts"][k], t6["c0"]["counts"][k],
                     t6["hard50"]["counts"][k]))
    md += [""]
    for k in PRECEDENCE:
        md.append("- **%s**: %s" % (k, t6["combined"]["instance_ids"][k] or "none"))
    e = s["task7_strict_eligibility"]
    md += ["", "## 7. Strict eligibility", "", "Criterion: %s" % e["criterion"],
           "", "- **strict_temporal_eligible = true for %d / 100**" % e["n_eligible"],
           "- c0_data.json: %d - %s" % (len(e["eligible_by_source"]["c0"]),
                                        e["eligible_by_source"]["c0"]),
           "- hard50_data.json: %d - %s" % (len(e["eligible_by_source"]["hard50"]),
                                            e["eligible_by_source"]["hard50"]),
           "", "Sensitivity: if every borderline call were resolved the other "
           "way, the eligible pool would reach at most **%d**."
           % e["sensitivity_if_every_borderline_resolved_the_other_way"]["upper_bound"],
           "", "## 8. Borderline cases", "",
           "%d instances carry an explicit alternative classification; they are "
           "written out in `original100_borderline_review.md` and are not "
           "silently resolved." % len(s["task8_borderline_ids"]),
           "", "Confidence over the 100: %s" % s["confidence_counts"], "",
           "## 9. Adjudication rules used", ""]
    for k, v in s["adjudication_rules"].items():
        md += ["- **%s** - %s" % (k, v)]
    md += ["", "## 10. Decision support", "",
           "**A. Are there at least 50 strictly well-posed originals?** No. "
           "There are **%d**, and the optimistic upper bound after flipping "
           "every borderline call is **%d**."
           % (e["n_eligible"],
              e["sensitivity_if_every_borderline_resolved_the_other_way"]["upper_bound"]),
           "", "**C. How many are available, and why the shortfall?** %d. The "
           "dominant reason is that %d items have a gold whose truth needs "
           "post-publication prices the protocol does not supply, and a further "
           "%d contain an option - often the gold - that relabels supplied "
           "pre-publication movement as happening after the news."
           % (e["n_eligible"], t6["combined"]["counts"][I_REQ],
              t6["combined"]["counts"][I_LAB]), "",
           "**B. Feasibility of a later outcome-blind filtered subset.** A "
           "50-item temporally-filtered subset cannot be drawn from this pool. "
           "A smaller one (n = %d as classified here) is feasible and would be "
           "outcome-blind by construction, since this flag never touches model "
           "results, distractor coverage or previous membership." % e["n_eligible"],
           "", "**D. Systematic mismatch in the raw pool?** Yes. %d of 400 "
           "options require post-publication prices or a before/after "
           "comparison, %d relabel a supplied move, and %d of 100 golds are "
           "themselves problematic. The mismatch is a property of the inherited "
           "MTBench MCQA, not of any condition built from it."
           % (s["task9_option_level_totals"]["n_options_requiring_post_publication_ts"],
              s["task9_option_level_totals"]["n_options_with_mislabeled_observed_move"],
              len(s["task5_problematic_gold_ids"])), "",
           "**E. Mechanical vs adjudicated.** Mechanical: row counts, id "
           "uniqueness, absence of any output-window field, all geometry, every "
           "price-level and date match, and the absent-level tables. Adjudicated: "
           "the option categories, the gold support class and the instance class "
           "- these rest on reading the wording, and %d of them carry an explicit "
           "alternative." % len(s["task8_borderline_ids"]), ""]
    with open(os.path.join(OUT, "original100_temporal_validity_report.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))

    md = ["# Borderline review - original 100 temporal-validity audit", "",
          "Every instance below has a classification that a careful reader "
          "could reasonably assign differently. None has been silently "
          "resolved: the proposed class is what the audit records, the "
          "alternative is what would change if the call went the other way.", ""]
    by_id = {r["instance_id"]: r for r in rows}
    for iid in s["task8_borderline_ids"]:
        r = by_id[iid]
        md += ["---", "", "## Instance %d - %s (%s)"
               % (iid, r["ticker"], r["source_file"]), "",
               "**Question**: %s" % r["question"], ""]
        for L in "ABCD":
            o = r["options"][L]
            md.append("- **%s**%s `%s` - %s"
                      % (L, " (gold)" if o["is_gold"] else "",
                         o["primary_category"], o["text"]))
        gg = r["geometry"]
        md += ["", "**Gold**: %s. **Gold support**: `%s`."
               % (r["gold_answer"], r["gold_support_class"]),
               "", "**Time-series facts**: %d points, %s to %s, values %.2f "
               "(first) / %.2f (last), range %.2f-%.2f; the article publishes "
               "%.2f h after the last point and no point falls after it."
               % (gg["n_points"], gg["first_ts"], gg["last_ts"],
                  gg["first_value"], gg["last_value"], gg["min_value"],
                  gg["max_value"], gg["publication_minus_last_ts_hours"]),
               "", "**Proposed classification**: `%s`" % r["instance_class"],
               "", "**Alternative classification**: `%s`"
               % r["alternative_instance_class"],
               "", "**Confidence**: %s" % r["confidence"],
               "", "**Reason**: %s" % r["justification"], ""]
    with open(os.path.join(OUT, "original100_borderline_review.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))


def report(s):
    c = s["task1_pool_integrity"]["combined"]
    print("rows %d, unique ids %d, cross-file overlap %s"
          % (c["total_rows"], c["n_unique_instance_ids"],
             c["id_overlap_between_files"] or "none"))
    for k in ("c0_data.json", "hard50_data.json"):
        i = s["task1_pool_integrity"][k]
        print("  %-18s %d rows, output-window fields: %s"
              % (k, i["n_rows"], i["output_window_like_fields"] or "NONE"))
    g = s["task2_geometry"]
    print("\nTS after publication: %d/100 (none: %d); gap min/median/max h "
          "%.2f / %.2f / %.2f"
          % (g["n_with_any_ts_after_gt_publication"],
             g["n_with_no_ts_after_gt_publication"],
             g["publication_minus_last_ts_hours"]["min"],
             g["publication_minus_last_ts_hours"]["median"],
             g["publication_minus_last_ts_hours"]["max"]))
    print("gap distribution: %s" % g["gap_distribution_hours"])
    print("\noption categories: %s" % s["task3_option_category_counts"])
    t = s["task9_option_level_totals"]
    print("options needing post-publication prices: %d/400"
          % t["n_options_requiring_post_publication_ts"])
    print("options relabelling a supplied move:     %d/400"
          % t["n_options_with_mislabeled_observed_move"])
    print("\ngold support: %s" % s["task5_gold_support_counts"])
    print("problematic golds (%d): %s"
          % (len(s["task5_problematic_gold_ids"]), s["task5_problematic_gold_ids"]))
    t6 = s["task6_instance_classes"]
    print("\ninstance classes:")
    for k in PRECEDENCE:
        print("  %-46s combined %2d   c0 %2d   hard50 %2d"
              % (k, t6["combined"]["counts"][k], t6["c0"]["counts"][k],
                 t6["hard50"]["counts"][k]))
    e = s["task7_strict_eligibility"]
    print("\nstrict_temporal_eligible: %d/100  (c0 %d, hard50 %d)"
          % (e["n_eligible"], len(e["eligible_by_source"]["c0"]),
             len(e["eligible_by_source"]["hard50"])))
    print("eligible ids: %s" % e["eligible_ids"])
    print("upper bound if all borderlines flipped: %d"
          % e["sensitivity_if_every_borderline_resolved_the_other_way"]["upper_bound"])
    print("borderline (%d): %s" % (len(s["task8_borderline_ids"]),
                                   s["task8_borderline_ids"]))
    print("confidence: %s" % s["confidence_counts"])


if __name__ == "__main__":
    main()
