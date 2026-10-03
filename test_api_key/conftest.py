"""Keep manually run live-provider tools out of automatic pytest collection."""

collect_ignore = [
    "test_api_full.py",
    "test_gemini.py",
    "test_api_full_with_instruction.py",
    "test_ollama.py",
    "test_openrouter.py",
]
