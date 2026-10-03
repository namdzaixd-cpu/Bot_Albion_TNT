"""Interactive API helper; requires an explicit instruction file path."""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "bot"))

GEMINI_API_KEY = ""
OPENROUTER_API_KEY = ""
OLLAMA_API_KEY = ""
raw_instruction = ""

def choose_model():
    print("=== DANH SÁCH 13 MODEL HỖ TRỢ (KÈM SYSTEM INSTRUCTION) ===")
    print("[Google Gemini]")
    print("  1. gemini-3.5-flash-lite")
    print("  2. gemini-3.1-flash-lite")
    print("  3. gemma-4-31b-it")
    print("  4. gemini-2.5-flash")
    print("[Ollama]")
    print("  5. minimax-m3")
    print("  6. gpt-oss:120b")
    print("[OpenRouter]")
    print("  7. nvidia/nemotron-3-ultra-550b-a55b:free")
    print("  8. inclusionai/ling-3.0-flash:free")
    print("  9. poolside/laguna-s-2.1:free")
    print("  10. nvidia/nemotron-3-super-120b-a12b:free")
    print("  11. cohere/north-mini-code:free")
    print("  12. poolside/laguna-xs-2.1:free")
    print("  13. openrouter/free")
    
    choice = input("Lựa chọn của bạn (1-13, Mặc định: 1): ").strip()
    
    if choice == "2":
        return "1", "gemini-3.1-flash-lite"
    elif choice == "3":
        return "1", "gemma-4-31b-it"
    elif choice == "4":
        return "1", "gemini-2.5-flash"
    elif choice == "5":
        return "2", "minimax-m3"
    elif choice == "6":
        return "2", "gpt-oss:120b"
    elif choice == "7":
        return "3", "nvidia/nemotron-3-ultra-550b-a55b:free"
    elif choice == "8":
        return "3", "inclusionai/ling-3.0-flash:free"
    elif choice == "9":
        return "3", "poolside/laguna-s-2.1:free"
    elif choice == "10":
        return "3", "nvidia/nemotron-3-super-120b-a12b:free"
    elif choice == "11":
        return "3", "cohere/north-mini-code:free"
    elif choice == "12":
        return "3", "poolside/laguna-xs-2.1:free"
    elif choice == "13":
        return "3", "openrouter/free"
    elif choice == "1" or not choice:
        return "1", "gemini-3.5-flash-lite"
    else:
        # Nếu nhập custom model ngoài danh sách
        print("\nChọn nhà cung cấp cho model custom này:")
        print("1. Google Gemini")
        print("2. Ollama")
        print("3. OpenRouter")
        provider_choice = input("Lựa chọn (1-3, Mặc định: 1): ").strip()
        provider = provider_choice if provider_choice in ("2", "3") else "1"
        return provider, choice

def get_api_setup(provider, model):
    if provider == "1":
        if not GEMINI_API_KEY:
            print("\n❌ [LỖI 1]: Không tìm thấy GEMINI_API_KEY trong file .env.")
            print("👉 Hướng dẫn: Thêm GEMINI_API_KEY vào file .env ở thư mục gốc.\n")
            raise SystemExit(1)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        return url, headers
        
    elif provider == "2":
        ollama_url = "https://ollama.com/api"
        url_clean = ollama_url.rstrip('/')
        url = url_clean if url_clean.endswith("/api/chat") else (f"{url_clean}/chat" if url_clean.endswith("/api") else f"{url_clean}/api/chat")
        headers = {"Content-Type": "application/json"}
        if OLLAMA_API_KEY:
            headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"
        return url, headers
        
    else:
        # Kiểm tra điều kiện chặn phí cho OpenRouter (bắt buộc phải có :free hoặc /free)
        if not (model.endswith(":free") or model.endswith("/free")):
            print("\n❌ [CẢNH BÁO BẢO VỆ CHI PHÍ]:")
            print(f"Yêu cầu gọi model '{model}' qua OpenRouter đã bị chặn vì không có hậu tố ':free' hoặc '/free'.")
            print("Vui lòng chỉ sử dụng các model miễn phí để tránh phát sinh chi phí ngoài ý muốn!\n")
            raise SystemExit(1)

        if not OPENROUTER_API_KEY:
            print("\n❌ [LỖI 1]: Không tìm thấy OPENROUTER_API_KEY trong file .env.")
            print("👉 Hướng dẫn: Thêm OPENROUTER_API_KEY vào file .env ở thư mục gốc.\n")
            raise SystemExit(1)
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        return url, headers

def load_instruction(path_value):
    if not path_value:
        raise ValueError(
            "Provide --instruction-path or set AI_INSTRUCTION_PATH to the instruction file."
        )
    try:
        path = Path(path_value).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ValueError("The configured instruction file does not exist.") from exc
    if not path.is_file():
        raise ValueError("The configured instruction path is not a file.")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("The configured instruction file could not be read.") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--instruction-path",
        default=os.environ.get("AI_INSTRUCTION_PATH"),
        help="Path to the real system instruction file (or set AI_INSTRUCTION_PATH).",
    )
    args = parser.parse_args(argv)

    global GEMINI_API_KEY, OPENROUTER_API_KEY, OLLAMA_API_KEY, raw_instruction
    try:
        raw_instruction = load_instruction(args.instruction_path)
    except ValueError as exc:
        parser.error(str(exc))

    from core.config import GEMINI_API_KEY as gemini_key
    from core.config import OPENROUTER_API_KEY as openrouter_key

    GEMINI_API_KEY = gemini_key or os.getenv("GEMINI_API_KEY", "")
    OPENROUTER_API_KEY = openrouter_key or os.getenv("OPENROUTER_API_KEY", "")
    OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")

    provider_names = {"1": "Gemini", "2": "Ollama", "3": "OpenRouter"}
    provider, model = choose_model()
    url, headers = get_api_setup(provider, model)
    system_instruction = raw_instruction.replace("{CURRENT_MODEL}", model)
    print(f"\n[{provider_names[provider]}] Sẵn sàng gửi yêu cầu.")
    print(f"[{provider_names[provider]}] Đang sử dụng model: {model}")
    print(f"System instruction: {len(system_instruction)} ký tự")
    print("Gõ câu hỏi rồi Enter (Ctrl+C để thoát), gõ `/model` để đổi model hoặc nhà cung cấp.\n")

    while True:
        question = input("> ").strip()
        if not question:
            continue

        if question.lower() == "/model":
            print()
            provider, model = choose_model()
            url, headers = get_api_setup(provider, model)
            system_instruction = raw_instruction.replace("{CURRENT_MODEL}", model)
            print(f"🔄 Đã chuyển sang: {provider_names[provider]} | Model: {model}\n")
            continue

        if provider == "1":
            body = json.dumps({
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "contents": [{"parts": [{"text": question}]}]
            }).encode("utf-8")
        elif provider == "2":
            body = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": question}
                ],
                "stream": False
            }).encode("utf-8")
        else:
            body = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": question}
                ]
            }).encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        start = time.perf_counter()

        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            elapsed = time.perf_counter() - start
            if provider == "1":
                reply = result["candidates"][0]["content"]["parts"][0]["text"]
            elif provider == "2":
                reply = result["message"]["content"]
            else:
                reply = result["choices"][0]["message"]["content"]
            print(f"\n[{elapsed:.2f}s] {reply}\n")
        except urllib.error.HTTPError as exc:
            elapsed = time.perf_counter() - start
            print(f"\n[{elapsed:.2f}s] Lỗi HTTP {exc.code}")
            if exc.code == 429:
                print("Đã chạm giới hạn request hoặc quota API.")
            elif exc.code in (401, 403):
                print("API key không hợp lệ hoặc không có quyền truy cập.")
            elif exc.code == 404 and provider == "2":
                print("Model hoặc đường dẫn Ollama không tồn tại.")
            elif exc.code in (400, 404) and provider == "1":
                print("Model Gemini không tồn tại hoặc không còn khả dụng.")
            else:
                print("Kiểm tra cấu hình, URL hoặc model.")
        except Exception as exc:
            elapsed = time.perf_counter() - start
            print(f"\n[{elapsed:.2f}s] Lỗi kết nối ({type(exc).__name__}).\n")


if __name__ == "__main__":
    main()
