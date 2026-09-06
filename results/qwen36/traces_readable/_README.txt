Qwen3.6-35B-A3B / Paper50 -- 可读版推理轨迹
每个文件: 元信息 + 题干选项 + 完整思维链 + rationale
文件名前缀 ok_ / WRONG_ ; 每个条件目录下有 _INDEX.txt
证据正文没有内联(C1 的 prompt 有 80KB), 见每个文件头部的 full prompt 路径
来源: results/qwen36/<cond>_qwen36.jsonl + <cond>_raw/<id>.json, 由本次会话生成

condition                              n  ok  wrong ids
c0                                    50  46  [47, 49, 201, 274]
c1                                    50  46  [18, 47, 49, 201]
c2                                    49  46  [96, 176, 201]
c3                                    50  39  [47, 53, 172, 191, 201, 215, 233, 252, 275, 453, 484]
s1_qo_only                            50  48  [123, 453]
s2_gt_text_only                       50  46  [47, 201, 274, 320]
s3_pool_text_only                     50  45  [53, 201, 233, 274, 320]
s4_ts_only                            50  46  [18, 47, 140, 484]
s5_c2_qo_date_mask                    49  43  [96, 176, 201, 233, 252, 274]
s6_c1_metadata_timestamp_shuffle      50  47  [18, 201, 252]
