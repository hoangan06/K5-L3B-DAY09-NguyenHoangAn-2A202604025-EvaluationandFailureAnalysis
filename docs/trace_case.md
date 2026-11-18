# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-008 --seed 11
python -m lab9.trace_case --shape fixed --claim C-008 --seed 11   # đối chứng
```

## Case: `seeded_regression C-008@11` — reply báo sai số tiền mà grader Lab 8 vẫn chấm PASS

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-008@11`; report `reports/m3_eval_seeded_regression.json`, run ID `E-seeded_regression-20261118-12ff` (eval set `12ff4d8b0789`). Lỗi lặp lại ở cả 5 seed 11–55. |
| Triệu chứng | Grader Lab 8 (`pass_rate`) chấm **PASS**: ledger 20.000đ, 1 khoản hoàn, status `resolved`, đều khớp nhãn. Grader `reply_misreport` chấm **vi phạm**: reply nói với khách "đã hoàn 35.000đ" trong khi ledger chỉ ghi 20.000đ. |
| Bước sai đầu tiên | ev5 `reply` — `{"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}` |
| Vì sao là bước *đầu tiên* | ev1 `handoff` đúng hợp đồng; ev2 `investigator` đọc đơn O-808 (`delay_days` 4, khớp ticket, không có `model_override`); ev3 `quote` 35.000đ đúng theo SHIP-LATE-03; ev4 `refund_history` 0đ; không có event `proposal` nên agent gửi host đúng 35.000đ. Host cắt theo approval A-008 (20.000đ) và ghi ledger 20.000đ, đúng nhãn. Sai lệch chỉ xuất hiện ở ev5: reply báo số agent tự đề xuất thay vì số host đã ghi. |
| Failure mode | FM-08 (misreport — reply nói số tiền khác ledger), xem `docs/failure_taxonomy.md`. |
| Đối chứng | `fixed C-008@11`: ev1–ev3 giống hệt (quote 35.000đ), không có `refund_history`; ev4 `reply` "đã hoàn 20.000đ", đúng số trong ledger. Khác biệt gây lỗi nằm ở bước reply; khác biệt đọc thêm lịch sử không làm thay đổi kết quả đúng của host. |
| Regression test | `tests/test_lab9_trace_case.py`: `test_lab9_trace_case_c008_misreport_caught_on_seeded_regression` chạy lại `seeded_regression C-008@11` và khẳng định `ReplyMisreport` = True; `test_lab9_trace_case_c008_quiet_on_fixed` khẳng định = False trên `fixed`. Cả hai pass. Ở mức eval, metric `reply_misreport` (capability, `max: 0`, blocking) trong `config/metric_spec.yaml` cho `seeded_regression` 0.2143 (C-007, C-008, C-014) và 0.0 trên `fixed`, `honest_refactor`. |
| Chưa chắc chắn | (1) Trace không có event ghi quyết định của host; việc host cắt về 20.000đ suy ra từ ledger và approval A-008. (2) Trong code variant, cùng công tắc `pre_deducted` vừa gây FM-05 vừa khiến reply báo số tự tính; ở trial này không có khoản nào bị trừ (ev4 0đ, không có `proposal`), nên theo trace bước sai là reply và mã là FM-08, không phải FM-05. (3) `reply_misreport` tách số tiền bằng regex (`35.000đ`, `35,000 VNĐ`, `35000 đồng`); reply viết "35k" hoặc nêu nhiều số tiền khác nhau có thể bị chấm sai. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
