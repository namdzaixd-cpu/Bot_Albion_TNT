# Bộ Công Cụ Test AI API (Test Key & Latency)

Thư mục này chứa các script độc lập dùng để kiểm tra kết nối, đo độ trễ (latency) và thử nghiệm phản hồi của các mô hình AI (Gemini, Ollama, OpenRouter) trước khi chạy bot Discord chính thức.

---

## 📌 Điều kiện tiên quyết

Các script này đều sử dụng cấu hình chung của dự án. Đảm bảo bạn đã sao chép `.env.example` thành `.env` ở thư mục gốc và điền đầy đủ các thông tin:
* `GEMINI_API_KEY` (Cho Google Gemini)
* `OPENROUTER_API_KEY` (Cho OpenRouter)
* `OLLAMA_API_KEY` (Tùy chọn - khi dùng Ollama qua proxy/cloud)

---

## 📂 Danh sách các file test và lệnh chạy

| Tên File | Công Dụng | Lệnh Chạy (Terminal) |
| :--- | :--- | :--- |
| **`test_api_full.py`** | **[Gộp 13 model]** Test nhanh kết nối/độ trễ thô của cả 3 nhà cung cấp cùng lúc (Không kèm prompt hệ thống). | `python3 test_api_key/test_api_full.py` |
| **`test_api_full_with_instruction.py`** | **[Gộp 13 model]** Test phản hồi của cả 3 nhà cung cấp kèm system instruction từ file do bạn chỉ định. | `python3 test_api_key/test_api_full_with_instruction.py --instruction-path /path/to/chat_ai_instruction.txt` |
| **`test_gemini.py`** | Test riêng lẻ Google Gemini API (gọi trực tiếp Google AI Studio). | `python3 test_api_key/test_gemini.py` |
| **`test_ollama.py`** | Test riêng lẻ Ollama API (chạy cục bộ hoặc qua proxy). | `python3 test_api_key/test_ollama.py` |
| **`test_openrouter.py`** | Test riêng lẻ OpenRouter API (không kèm prompt hệ thống). | `python3 test_api_key/test_openrouter.py` |

Riêng helper này, truyền `--instruction-path` như ví dụ hoặc đặt biến môi trường tiến trình `AI_INSTRUCTION_PATH` trước khi chạy. File phải tồn tại và đọc được; helper dừng trước menu/API nếu thiếu hoặc sai đường dẫn. Không có instruction mặc định.

---

## ⚡ Các tính năng đặc biệt tích hợp sẵn

### 1. Đổi model nhanh không cần khởi động lại (`/model`)
Trong khi đang chat với bot ở Terminal, bạn chỉ cần gõ:
```bash
> /model
```
Hệ thống sẽ dừng chat tạm thời, hiển thị lại menu danh sách model để bạn chọn model mới và tiếp tục cuộc hội thoại ngay lập tức.
*(Lưu ý: Lệnh này được hỗ trợ trên `test_api_full.py`, `test_api_full_with_instruction.py`, `test_gemini.py`, `test_ollama.py`, và `test_openrouter.py`)*

### 🔒 2. Cơ chế tự động chặn phí (Cost Safety) trên OpenRouter
Để bảo vệ số dư tài khoản của bạn, hệ thống áp dụng cơ chế chặn nghiêm ngặt:
* Tất cả các yêu cầu gửi đến **OpenRouter** bắt buộc phải sử dụng các model miễn phí có hậu tố `:free` hoặc `/free` ở cuối.
* Nếu hệ thống phát hiện bạn chọn hoặc nhập một model trả phí qua OpenRouter, yêu cầu sẽ bị chặn ngay lập tức (`[CẢNH BÁO BẢO VỆ CHI PHÍ]`) và thoát chương trình để tránh phát sinh chi phí ngoài ý muốn.
