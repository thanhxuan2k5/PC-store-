# Rule: Session Log

## Mô tả

Mỗi ngày làm việc, agent **BẮT BUỘC** phải tạo hoặc cập nhật file session log tại:

```
sessions/<YYYY-MM-DD>.md
```

Ví dụ: `sessions/2026-08-12.md`

## Yêu cầu

1. **Tạo file mới** nếu chưa tồn tại file cho ngày hôm nay.
2. **Cập nhật file** nếu đã có - thêm nội dung mới vào cuối file.
3. File phải ghi lại **tất cả các thay đổi** đã thực hiện trong phiên làm việc.

## Format bắt buộc

```markdown
# Session Log - <YYYY-MM-DD>

## Thay đổi chức năng
- Mô tả chức năng mới hoặc thay đổi chức năng đã có

## Sửa lỗi
- Mô tả lỗi đã phát hiện và cách sửa

## Ghi chú
- Các ghi chú bổ sung, TODO, hoặc vấn đề cần theo dõi
```

## Ví dụ

```markdown
# Session Log - 2026-08-12

## Thay đổi chức năng
- Thêm endpoint `/api/inspect` để nhận ảnh và trả kết quả kiểm tra
- Cập nhật pipeline YOLO từ YOLOv8 sang YOLOv11 để cải thiện độ chính xác

## Sửa lỗi
- Fix lỗi OOM khi xử lý ảnh có độ phân giải > 4K, thêm resize trước inference
- Fix lỗi trả sai confidence score do thiếu post-processing

## Ghi chú
- Cần benchmark lại inference time sau khi đổi model
- TODO: Thêm unit test cho module detector
```

## Khi nào cập nhật

- **Sau mỗi lần hoàn thành** một chức năng hoặc fix một lỗi.
- **Trước khi commit** code lên repository.
- **Cuối phiên làm việc** nếu chưa cập nhật.
