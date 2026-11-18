# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5` (judge replay: phán quyết đã lưu sẵn trong CSV, n = 100 reply mỗi tiêu chí, nhãn người ở cột `human`). FAIL là lớp dương tính: việc của judge là tìm reply hỏng.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (TP 24, FP 4, FN 6, TN 66) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt κ và recall (TP 9, FP 0, FN 21, TN 70) | loại |

Tỉ lệ fail quan sát và sau hiệu chỉnh Rogan-Gladen: `tone_ok` 0.28 → 0.30; `helpful` 0.09 → 0.30. Với `helpful`, judge chỉ thấy 9% reply hỏng trong khi ước lượng sau hiệu chỉnh là 30%: judge đếm thiếu hơn ba lần.

## ≥5 case audit thủ công

Audit toàn bộ 10 bất đồng của `tone_ok` (4 FP, 6 FN), vì đây là judge được dùng nên rubric của nó cần sửa. Cột "Người nói" là nhãn trong CSV. Các hành động sửa rubric dưới đây là **đề xuất cần kiểm chứng**: mỗi quy tắc rút từ một vài case, nên phải thử trên dữ liệu mới trước khi áp dụng, tránh rubric khớp quá mức với tập audit.

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú và hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em" + "nha" quá suồng sã với khách; judge coi là thân thiện. Đề xuất: quy định xưng hô "LogiX" – "anh/chị"; xưng "em" với khách là FAIL. Tiểu từ "nha/nhé" không tự nó là FAIL, chỉ tính khi đi cùng xưng hô suồng sã như ca này. |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha." | PASS | FAIL | Người | Gọi khách là "bạn". Đề xuất: cùng quy tắc xưng hô với #1, thêm ví dụ FAIL có "bạn ơi" vào rubric. |
| 3 | H-029 "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh, chặn khách liên hệ; judge chỉ thấy "Dạ, vui lòng". Đề xuất: yêu cầu khách ngừng liên hệ là FAIL dù có từ lịch sự. |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Ngắn nhưng đủ ý; judge phạt vì thiếu lời xin lỗi. Đề xuất: không bắt buộc xin lỗi khi yêu cầu đã được giải quyết. |
| 5 | H-051 "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người | CS LogiX cho phép từ "refund"; judge phạt vì tiếng Anh. Đề xuất: thêm danh sách thuật ngữ tiếng Anh mà chuẩn CS LogiX cho phép (bằng chứng hiện có: "refund"). |
| 6 | H-063 "Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | Người, nhưng sai tiêu chí | Lỗi là hứa "sẽ hoàn thêm" ngoài kết quả hệ thống, không phải giọng điệu. Không sửa rubric tone; chuyển sang grader code: reply không được nêu cam kết tiền ngoài ledger (gần FM-08). |
| 7 | H-070 "Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Emoji cười không hợp ngữ cảnh khiếu nại. Đề xuất: emoji cười trong reply xử lý khiếu nại là FAIL; các emoji khác và ngữ cảnh khác chưa có bằng chứng. |
| 8 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | Judge | Note trong CSV: nhãn người sai do đọc nhầm ticket. Hành động: sửa nhãn ở phiên bản tập nhãn sau, không sửa rubric. Không sửa CSV công khai trong lab vì test tham chiếu dùng đúng số liệu hiện tại. |
| 9 | H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ cho đơn O-233 ạ." | FAIL | PASS | Người | Lặp "Dạ" do lỗi gõ, không làm sai giọng điệu. Đề xuất: lỗi gõ nhỏ không đổi nghĩa hay thái độ thì không FAIL tone. |
| 10 | H-094 "Da, LogiX da hoan 40.000đ cho don O-341, xin loi vi su bat tien." | PASS | FAIL | Người | Mất dấu tiếng Việt (dịch máy). Đề xuất: reply tiếng Việt không dấu là FAIL. |

Tổng hợp: người đúng ở 9/10 ca, judge đúng ở 1/10 (H-081). Các FN của judge (#1, #2, #3, #7, #10) đều là lỗi giọng điệu; các ca này gợi ý cần làm rõ rubric về xưng hô, yêu cầu khách ngừng liên hệ, emoji và tiếng Việt có dấu. Các FP (#4, #5, #9) là những ca judge chấm chặt hơn người gán nhãn; riêng #5 có note trong CSV xác nhận chuẩn CS LogiX cho phép từ "refund". Nếu sửa nhãn H-081 thành FAIL, ma trận thành TP 25, FP 3, FN 6, TN 66 (P ≈ 0.893, R ≈ 0.806), nên kết luận "dùng" không đổi.

## Kết luận

- **Loại `helpful`.** Precision 1.0 nhưng recall chỉ 0.3 và κ 0.375 (dưới sàn 0.7 và 0.6): judge không báo nhầm nhưng để lọt 21/30 reply hỏng. Theo cột `human_failure` của CSV, 21 ca bị bỏ lọt gồm 18 ca sai tiền (vd. HL-015 "đã hoàn 55.000đ", ledger ghi 40.000đ) và 3 ca sai xưng hô ("Ok bạn, đơn O-515 xử lý rồi nhé."); 9 ca judge bắt được là giọng cụt (4), không hỏi lại mã đơn (3) và trả lời lạc đề (2). Kết quả replay cho thấy judge này không phát hiện các ca reply lệch ledger. Nếu judge chỉ nhận câu trả lời mà không có ledger, nó không thể kiểm chứng số tiền; tiêu chí này cần grader code. Dùng judge này làm gate sẽ cho merge một agent nói sai số tiền với khách.
- **Nhãn `helpful` trộn hai tiêu chí.** Ba ca "sai xưng hô" là lỗi giọng điệu, thuộc phạm vi `tone_ok`. Bỏ ba ca này ra, recall của `helpful` vẫn chỉ 9/27 ≈ 0.333, nên kết luận loại không đổi; khi gán nhãn lại nên tách xưng hô sang tiêu chí tone.
- **Không kết luận được judge `helpful` có thiên lệch theo độ dài.** 13/18 ca sai tiền bị lọt là reply xin lỗi dài, nhưng trong dữ liệu không có reply dài nào đúng tiền, nên độ dài và việc sai tiền trùng nhau; muốn tách hai yếu tố cần thêm reply dài có số tiền đúng.
- **Dùng `tone_ok` hiện tại.** Judge này đạt floors trên tập replay. Các thay đổi rubric ở bảng audit là đề xuất; cần chạy calibration lại trên tập nhãn mới trước khi áp dụng phiên bản judge mới. Tiêu chí này chỉ chấm giọng điệu, không chấm nội dung tiền hay cam kết (ca #6 chuyển sang grader code).
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai (100 reply mỗi tiêu chí); sau khi sửa rubric cần chấm lại trên một tập nhãn người mới, chưa ai dùng để chỉnh rubric, mới có held-out thật. Với n = 100 và 30 ca FAIL theo người, recall 0.8 của `tone_ok` còn sai số lấy mẫu đáng kể (mỗi ca FN thay đổi recall khoảng 0.033).
