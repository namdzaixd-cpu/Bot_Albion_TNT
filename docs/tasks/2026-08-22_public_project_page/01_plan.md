# Guild Operations Dossier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay trang Flask công khai bằng Guild Operations Dossier đầy đủ, trung thực và dễ tra cứu cho cả thành viên Discord lẫn developer.

**Architecture:** Giữ nguyên `bot/core/webserver.py` và cơ chế thay `{{ session_id }}`; toàn bộ nội dung, style và progressive enhancement nằm trong một HTML tự chứa. Thêm một test Python dùng thư viện chuẩn để khóa section, liên kết, 34 command và loại bỏ các claim lỗi thời.

**Tech Stack:** HTML5, CSS thuần, JavaScript thuần, Python `html.parser`/pytest, Flask hiện có.

**Spec:** `docs/features/public_project_page.md`

## Global Constraints

- Phạm vi production source chỉ sửa `bot/core/templates/index.html`; không sửa cog, database, dashboard, README hoặc `/aboutme`.
- Giữ nguyên chuỗi `{{ session_id }}` cho `bot/core/webserver.py` thay ở runtime.
- Hiển thị chính xác 34 lệnh đang được nạp tại commit `c4a3058`; không quảng bá 3 lệnh blacklist vì cog chưa được nạp.
- Không hiển thị “BOT ONLINE”; dùng “Web service đang phản hồi” để không suy diễn trạng thái Discord gateway.
- Không dùng `YOUR_CLIENT_ID`; CTA công khai chỉ trỏ tới GitHub, Discord, Albion Online và repository AI Bot.
- Không mô tả GitHub JSON sync, `.tmp/.bak`, JSON DB hoặc Auto Backup như kiến trúc production.
- Không thêm dependency frontend hoặc Python.
- Không lộ endpoint nội bộ, token, secret, biến môi trường hoặc finding bảo mật trên trang công khai.
- Giao diện dùng palette steel/brass/cyan, responsive từ 320px, có skip link, focus-visible và `prefers-reduced-motion`.
- Không chạy `bot/main.py` hoặc bất kỳ lệnh nào khởi động Discord bot local.
- `docs/` đang bị `.gitignore` bỏ qua; chỉ dùng `git add -f` với đúng feature spec và ba artifact trong task này, không sửa `.gitignore` và không force-add file docs khác.
- Commit message bằng tiếng Việt và không có dòng đồng tác giả AI.

---

## File Structure

- Create: `docs/features/public_project_page.md` — đặc tả nội dung, sự thật nguồn, visual direction và tiêu chí hoàn thành.
- Create: `docs/tasks/2026-08-22_public_project_page/01_plan.md` — implementation plan đã được user duyệt.
- Create: `bot/tests/test_public_index.py` — test hợp đồng nội dung cho trang công khai.
- Modify: `bot/core/templates/index.html` — semantic content, visual system và command filtering.
- Create during execution: `docs/tasks/2026-08-22_public_project_page/02_task.md` — checklist thực thi được cập nhật theo kết quả thật.
- Create during completion: `docs/tasks/2026-08-22_public_project_page/03_walkthrough.md` — thay đổi, ảnh kiểm tra, lệnh verify và commit/push cuối cùng.

## Task 1: Khóa hợp đồng nội dung công khai

**Files:**
- Create: `bot/tests/test_public_index.py`
- Modify: `bot/core/templates/index.html`

**Interfaces:**
- Consumes: file HTML được `bot/core/webserver.py:15-27` đọc và thay chuỗi `{{ session_id }}`.
- Produces: section ID ổn định, 34 phần tử có `data-command`, liên kết có `data-link`, và copy trạng thái trung thực để test lẫn JavaScript dùng chung.

- [ ] **Step 1: Viết test hợp đồng nội dung đang fail**

Tạo `bot/tests/test_public_index.py` với nội dung:

```python
from html.parser import HTMLParser
from pathlib import Path

from core.webserver import app


ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = ROOT / "bot" / "core" / "templates" / "index.html"

EXPECTED_SECTIONS = {
    "overview",
    "problems",
    "modules",
    "architecture",
    "workflows",
    "commands",
    "data",
    "stack",
}

EXPECTED_COMMANDS = {
    "/aboutme",
    "/recuibot toggle",
    "/recuibot set_apply_channel",
    "/recuibot setup_channels",
    "/recuibot setup_roles",
    "/recuibot list",
    "/spupdate",
    "/spcheck",
    "/sphistory",
    "/sptop",
    "/splog",
    "/spexport",
    "/addsp",
    "/removesp",
    "/removesprole",
    "/resetsp",
    "/massing",
    "/masstemplatelist",
    "/masstemplatedelete",
    "/guildconfig",
    "/guildcheck",
    "/newmembers",
    "/alojoin",
    "/aloleave",
    "/alonametoggle",
    "/alo",
    "/aloconfig",
    "/alomute",
    "/alounmute",
    "/coresetup",
    "/coreadd",
    "/coreremove",
    "/coreautoreact",
    "/corelist",
}

EXPECTED_LINKS = {
    "github": "https://github.com/namdzaixd-cpu/Bot_Albion_TNC",
    "discord": "https://discord.gg/PhMqCskBJ",
    "chatbot": "https://github.com/kudominer/TNC-Chatbot",
    "albion": "https://albiononline.com",
}


class IndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.commands = []
        self.links = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if values.get("data-command"):
            self.commands.append(values["data-command"])
        if tag == "a" and values.get("data-link"):
            self.links[values["data-link"]] = values.get("href")


def render_index():
    response = app.test_client().get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    parser = IndexParser()
    parser.feed(html)
    return html, parser


def test_public_index_matches_project_contract():
    template = INDEX_PATH.read_text(encoding="utf-8")
    html, parser = render_index()

    assert '<html lang="vi">' in html
    assert "{{ session_id }}" in template
    assert "{{ session_id }}" not in html
    assert "Web service đang phản hồi" in html
    assert EXPECTED_SECTIONS <= parser.ids
    assert set(parser.commands) == EXPECTED_COMMANDS
    assert len(parser.commands) == len(EXPECTED_COMMANDS) == 34
    assert parser.links == EXPECTED_LINKS


def test_public_index_has_no_stale_or_placeholder_claims():
    html, _ = render_index()
    forbidden = {
        "YOUR_CLIENT_ID",
        "BOT ONLINE",
        "GitHub Sync",
        "JSON DB",
        "Auto Backup",
        "/blacklist add",
        "/registertnc",
    }
    assert all(term not in html for term in forbidden)
```

- [ ] **Step 2: Chạy test để xác nhận test bắt đúng trang cũ**

Run:

```bash
python3 -m pytest bot/tests/test_public_index.py -q
```

Expected: FAIL vì trang hiện tại thiếu các section mới, không có 34 `data-command`, còn `YOUR_CLIENT_ID`, “BOT ONLINE”, “GitHub Sync”, “JSON DB” và “Auto Backup”.

- [ ] **Step 3: Thay semantic content của `index.html`**

Giữ `<!DOCTYPE html>`, `<html lang="vi">`, metadata responsive và `{{ session_id }}`. Thay body hiện tại bằng cấu trúc chính xác:

```html
<a class="skip-link" href="#main-content">Bỏ qua điều hướng</a>
<header class="site-header">
  <nav aria-label="Điều hướng chính">...</nav>
</header>
<main id="main-content">
  <section id="overview">...</section>
  <section id="problems">...</section>
  <section id="modules">...</section>
  <section id="architecture">...</section>
  <section id="workflows">...</section>
  <section id="commands">...</section>
  <section id="data">...</section>
  <section id="stack">...</section>
</main>
<footer>...</footer>
```

Nội dung phải tuân theo `docs/features/public_project_page.md`, gồm:

- Hero ghi “TNC Guild Operations” và “Web service đang phản hồi · Session #{{ session_id }}”.
- 7 nhóm lệnh: About, Onboarding, Siphoned, Massing, GuildCheck, ALO TTS và Core-Bank.
- 2 dịch vụ nền: LastSeen và Discord Sync.
- AI Bot là service riêng với link repository TNC-Chatbot.
- Architecture map có các node Discord, Bot chính, Supabase, Dashboard, AI Bot và External APIs.
- Data section nói rõ Supabase là nguồn dữ liệu production; `bot/Storage/` là legacy.
- Verification section chỉ nêu 23 Python tests passed, Python compile passed và Next.js production build 21 route.

Tạo đúng 34 row/card command. Mỗi row có `data-command="/tên lệnh"`, `data-system="tên-module"`, `<code>` chứa tên lệnh và một mô tả tiếng Việt cụ thể theo command decorator trong cog tương ứng.

Tạo đúng bốn link được test:

```html
<a data-link="github" href="https://github.com/namdzaixd-cpu/Bot_Albion_TNC">GitHub</a>
<a data-link="discord" href="https://discord.gg/PhMqCskBJ">Discord TNC</a>
<a data-link="chatbot" href="https://github.com/kudominer/TNC-Chatbot">TNC-Chatbot</a>
<a data-link="albion" href="https://albiononline.com">Albion Online</a>
```

Không lặp `data-link` trên các CTA khác; CTA phụ dùng anchor section hoặc link không có thuộc tính này để map test không bị ghi đè.

- [ ] **Step 4: Chạy test hợp đồng sau khi cập nhật content**

Run:

```bash
python3 -m pytest bot/tests/test_public_index.py -q
```

Expected: `2 passed`.

## Task 2: Xây visual system và progressive enhancement

**Files:**
- Modify: `bot/core/templates/index.html`
- Modify: `bot/tests/test_public_index.py`

**Interfaces:**
- Consumes: section IDs, `data-command` và `data-system` từ Task 1.
- Produces: CSS token system, responsive layout, reduced-motion behavior và bộ lọc command không làm mất nội dung semantic.

- [ ] **Step 1: Thêm test cho accessibility hooks và command filter**

Thêm test sau vào `bot/tests/test_public_index.py`:

```python
def test_public_index_includes_accessible_progressive_enhancement():
    html, parser = render_index()

    assert 'class="skip-link"' in html
    assert 'id="command-search"' in html
    assert 'aria-live="polite"' in html
    assert "prefers-reduced-motion: reduce" in html
    assert "data-system" in html
    assert "IntersectionObserver" in html
    assert "command-search" in html
    assert len(parser.commands) == 34
```

- [ ] **Step 2: Chạy test mới để xác nhận các hook chưa đầy đủ**

Run:

```bash
python3 -m pytest bot/tests/test_public_index.py::test_public_index_includes_accessible_progressive_enhancement -q
```

Expected: FAIL trên ít nhất một hook accessibility/filter chưa được triển khai.

- [ ] **Step 3: Áp token và layout Guild Operations Dossier**

Khai báo token CSS ở `:root`:

```css
:root {
  --steel-950: #101621;
  --steel-850: #172334;
  --parchment: #e8e0cf;
  --brass: #d2a84a;
  --map-cyan: #70b7c8;
  --battle-red: #b85745;
  --muted: #9da9b5;
  --line: rgba(112, 183, 200, 0.22);
  --display: "Barlow Condensed", "Arial Narrow", sans-serif;
  --body: "IBM Plex Sans", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, monospace;
}
```

Thực hiện các layout cụ thể:

- Header sticky có backdrop và navigation wrap trên màn hình hẹp.
- Hero hai cột desktop, một cột mobile; architecture mini-map là điểm nhấn duy nhất.
- Module grid 3 cột desktop, 2 cột tablet, 1 cột mobile.
- Architecture map dùng CSS Grid và SVG inline cho đường kết nối có label; không dùng canvas.
- Command toolbar sticky trong section, input tìm kiếm và chip module có trạng thái `aria-pressed`.
- Command table chuyển thành card tại `max-width: 720px` bằng `display: grid` và label pseudo-element.
- `:focus-visible` dùng outline `2px solid var(--map-cyan)` với offset 3px.
- `@media (prefers-reduced-motion: reduce)` tắt animation, transition và scroll behavior.

- [ ] **Step 4: Thêm JavaScript lọc command và reveal an toàn**

JavaScript phải lấy đúng các hook đã khóa:

```javascript
const search = document.getElementById("command-search");
const rows = [...document.querySelectorAll("[data-command]")];
const result = document.getElementById("command-result");
const filters = [...document.querySelectorAll("[data-command-filter]")];
let activeSystem = "all";

function applyCommandFilter() {
  const query = (search?.value || "").trim().toLocaleLowerCase("vi");
  let visible = 0;
  rows.forEach((row) => {
    const matchesText = !query || row.textContent.toLocaleLowerCase("vi").includes(query);
    const matchesSystem = activeSystem === "all" || row.dataset.system === activeSystem;
    row.hidden = !(matchesText && matchesSystem);
    if (!row.hidden) visible += 1;
  });
  if (result) result.textContent = `${visible} / ${rows.length} lệnh`;
}

search?.addEventListener("input", applyCommandFilter);
filters.forEach((button) => button.addEventListener("click", () => {
  activeSystem = button.dataset.commandFilter;
  filters.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  applyCommandFilter();
}));
applyCommandFilter();
```

Reveal-on-scroll phải thêm class enhancement sau khi DOM đã sẵn sàng để nội dung không bị ẩn khi JavaScript lỗi:

```javascript
if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) entry.target.classList.add("is-visible");
    });
  }, { threshold: 0.12 });
  document.querySelectorAll("[data-reveal]").forEach((node) => observer.observe(node));
}
```

- [ ] **Step 5: Chạy test public index và toàn bộ Python suite**

Run:

```bash
python3 -m pytest bot/tests/test_public_index.py -q
python3 -m pytest bot/tests -q
```

Expected: test public index `3 passed`; toàn bộ suite cũ và mới `26 passed`.

## Task 3: Kiểm tra trình duyệt, tài liệu hóa và giao nhận

**Files:**
- Modify if browser review finds defects: `bot/core/templates/index.html`
- Create: `docs/tasks/2026-08-22_public_project_page/02_task.md`
- Create: `docs/tasks/2026-08-22_public_project_page/03_walkthrough.md`

**Interfaces:**
- Consumes: HTML hoàn chỉnh và test contract của Task 1–2.
- Produces: bằng chứng desktop/mobile, checklist hoàn thành, commit và trạng thái remote có thể kiểm tra.

- [ ] **Step 1: Tạo task artifact từ trạng thái thực thi thật**

`02_task.md` phải liệt kê các deliverable và đánh dấu theo kết quả đã chạy:

```markdown
# Guild Operations Dossier — Task Checklist

- [ ] Nội dung phản ánh đúng commit production đã review
- [ ] Đủ 34 command đang được nạp
- [ ] Architecture map mô tả Bot–Supabase–Dashboard–AI Bot
- [ ] Không còn placeholder và claim storage/status lỗi thời
- [ ] Desktop 1440px đã kiểm tra
- [ ] Mobile 390px đã kiểm tra
- [ ] Keyboard focus và command filter đã kiểm tra
- [ ] Python tests, py_compile và HTML contract đều đạt
- [ ] Commit, fetch, push và kiểm tra process local hoàn tất
```

Chỉ đánh dấu `[x]` sau khi có output hoặc ảnh chứng minh tương ứng.

- [ ] **Step 2: Kiểm tra HTML qua Flask test client mà không chạy bot**

Run:

```bash
PYTHONPATH=bot python3 -c 'from core.webserver import app; response = app.test_client().get("/"); body = response.get_data(as_text=True); assert response.status_code == 200; assert "{{ session_id }}" not in body; assert "TNC Guild Operations" in body; print("Flask index OK", len(body))'
```

Expected: in `Flask index OK <positive length>`; không mở Discord gateway và không gọi `bot.run()`.

- [ ] **Step 3: Render bằng browser ở desktop và mobile**

Khởi chạy static server không liên quan Discord bot:

```bash
python3 -m http.server 8765 --directory bot/core/templates
```

Dùng browser automation mở `http://127.0.0.1:8765/index.html` và kiểm tra:

- Desktop viewport 1440×1000: hero, architecture map, module grid và command table không chồng lấn.
- Mobile viewport 390×844: navigation wrap, module/command thành một cột, không có horizontal overflow.
- Nhập `core` vào `#command-search`: chỉ còn 5 command Core-Bank.
- Chọn filter `alo`: chỉ còn 7 command ALO TTS.
- Tab từ skip link tới navigation, CTA, search và filter đều thấy focus ring.
- Chế độ reduced motion không chạy node pulse/reveal transition.

Lưu screenshot kiểm tra ngoài `bot/Storage/`; đường dẫn screenshot được ghi vào walkthrough.

- [ ] **Step 4: Chạy verification cuối**

Run:

```bash
python3 -m pytest bot/tests -q
python3 -m py_compile $(git ls-files 'bot/*.py' 'bot/**/*.py')
git diff --check
git status --short
```

Expected:

- `26 passed`.
- `py_compile` exit code 0.
- `git diff --check` không có output.
- Source/test chỉ có các file trong File Structure xuất hiện ở tracked diff. Feature spec và ba artifact dưới `docs/` vẫn bị ignore cho tới bước `git add -f`; `.agents/skills/`, `.codex/` và `AGENTS.md` vẫn untracked và không được stage.

- [ ] **Step 5: Viết walkthrough từ bằng chứng thật**

`03_walkthrough.md` phải ghi:

- Commit nguồn đã audit và ngày review.
- Tóm tắt section/module/architecture/command matrix đã tạo.
- Kết quả exact của pytest, py_compile, Flask test client và browser viewport checks.
- Các finding audit ngoài phạm vi không bị sửa.
- Danh sách file trong commit và hash commit sau khi tạo.

- [ ] **Step 6: Stage và commit đúng phạm vi**

Run:

```bash
git add bot/core/templates/index.html bot/tests/test_public_index.py
git add -f docs/features/public_project_page.md docs/tasks/2026-08-22_public_project_page/01_plan.md docs/tasks/2026-08-22_public_project_page/02_task.md docs/tasks/2026-08-22_public_project_page/03_walkthrough.md
git diff --cached --check
git diff --cached --name-only
git commit -m "cập_nhật(web): xây trang hồ sơ vận hành Bot TNC"
```

Expected: commit thành công, không có `.agents/skills/`, `.codex/` hoặc `AGENTS.md` trong `git diff --cached --name-only`.

- [ ] **Step 7: Fetch trước push và xử lý remote theo guardrail**

Run:

```bash
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

Nếu remote không có commit mới, chạy `git push origin main`. Nếu remote có commit mới, chạy `git pull --rebase origin main`; nếu có conflict thì dừng, báo file và commit xung đột cho user, không tự resolve. Nếu rebase sạch, chạy lại verification cuối rồi `git push origin main`.

- [ ] **Step 8: Kiểm tra bot local sau push**

Run:

```bash
pgrep -af "bot/main.py"
```

Nếu có PID thật của Discord bot local, xác nhận đúng command line rồi chạy `kill <PID-chính-xác>`. Không dùng `pkill` hoặc pattern rộng. Nếu không có process, ghi “không có bot local đang chạy” vào walkthrough.

- [ ] **Step 9: Kiểm tra production sau deploy**

Run:

```bash
curl -fsSL https://bot-albion-tnc.onrender.com/ -o /tmp/tnc-production-index.html
rg -n "TNC Guild Operations|Web service đang phản hồi|TNC-Chatbot" /tmp/tnc-production-index.html
```

Expected: đủ ba marker sau khi Render deploy commit mới. Nếu Render chưa deploy xong, báo trạng thái deployment thay vì tuyên bố trang production đã cập nhật.
