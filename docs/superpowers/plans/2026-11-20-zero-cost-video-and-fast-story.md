# Kế Hoạch Triển Khai: Tái Cấu Trúc Video AI Chi Phí 0đ & Viết Truyện Tối Ưu

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng hệ thống sinh video AI chi phí 0đ (video theo prompt tự do và video giáo dục trẻ em có phát âm 0đ) và module viết truyện siêu tốc 1-shot (không TTS, cốt truyện liền mạch) đồng thời cập nhật toàn bộ giao diện Gradio và Docker container.

**Architecture:** 
- Phân hệ Viết truyện: Chuyển đổi từ vòng lặp 8 chương cũ sang kiến trúc 1-shot LLM & Instant Template Fallback, lược bỏ hoàn toàn TTS audio, hỗ trợ 3 mức độ dài (ngắn/vừa/dài).
- Phân hệ Video Giáo dục Trẻ em & Video Tự do: Kiến trúc dựng 2.5D MoviePy trên CPU chi phí 0đ, tạo thẻ flashcard hoạt hình bằng Pillow hoặc AI tạo ảnh miễn phí (Pollinations AI), đồng bộ âm thanh giọng đọc edge-tts 0đ và nhạc nền BGM.
- Phân hệ UI & Docker: Tái cấu trúc Gradio 4 Tabs (Video Yêu Cầu & Affiliate, Video Trẻ Em & Giáo Dục, Viết Truyện Nhanh, Lịch Sử) và cấu hình Docker mount volumes để chạy trực tiếp.

**Tech Stack:** Python 3.12, Gradio, MoviePy, Pillow, Edge-TTS, Ollama / HTTPX, Docker Compose, Pytest.

**Spec:** `docs/superpowers/specs/2026-11-20-video-ai-and-story-refactor-design.md`

## Global Constraints
- Chi phí chạy video AI là 0đ (không bắt buộc GPU nặng hoặc API cloud trả phí).
- Module truyện chữ KHÔNG tạo file âm thanh TTS, chỉ sinh văn bản và file `.txt`.
- Video trẻ em hỗ trợ giọng đọc phát âm chuẩn miễn phí qua `edge-tts`.
- Mọi thay đổi đều được kiểm thử tự động bằng pytest và tạo commit git tương ứng theo `AGENTS.md`.

---

## Review Focus
1. **Mất kết nối mạng khi tạo ảnh:** Phải tự động chuyển sang chế độ vẽ canvas hoạt hình offline bằng Pillow, không làm crash tiến trình render.
2. **Ollama chưa bật hoặc lỗi model:** Module viết truyện phải tự động fallback sang Instant Creative Template để người dùng luôn nhận được truyện ngay lập tức.
3. **Độ dài âm thanh TTS lệch với video:** Hệ thống phải tự động đo độ dài audio từng thẻ học để gán chính xác thời lượng từng scene, kèm audio ducking nhạc nền.
4. **Ký tự lạ / tiếng nước ngoài trong truyện:** Bộ lọc tự động làm sạch văn bản, giữ tiếng Việt tự nhiên và liền mạch.
5. **Docker hot-reload / cập nhật mã:** Mount thư mục mã nguồn trong `docker-compose.yml` để Docker phản ánh ngay các thay đổi khi restart.

---

### Task 1: Module Viết Truyện Siêu Tốc 1-Shot (Fast Story Generator - Text-Only)

**Files:**
- Modify: `models/story.py`
- Create: `ai/story/fast_generator.py`
- Create: `tests/test_fast_story.py`

**Interfaces:**
- Produces: `generate_fast_story(input_data: FastStoryInput, client: OllamaClient | None = None) -> FastStoryResult`

- [ ] **Step 1: Viết bài test cho Fast Story Generator**
  Viết test trong `tests/test_fast_story.py` kiểm tra sinh truyện theo 3 mức độ dài (ngắn, vừa, dài), kiểm tra fallback khi Ollama offline, kiểm tra tính liền mạch và không có trường TTS.

- [ ] **Step 2: Chạy test để xác nhận test fail**
  Chạy `python -m pytest tests/test_fast_story.py` xác nhận lỗi `ImportError / ModuleNotFound`.

- [ ] **Step 3: Cập nhật `models/story.py` và tạo `ai/story/fast_generator.py`**
  - Cập nhật model hỗ trợ `length` (short: ~350 từ, medium: ~800 từ, long: ~1800 từ).
  - Viết logic 1-shot prompt tối ưu narrative arc (Mở bài -> Xung đột -> Cao trào -> Hóa giải).
  - Tích hợp kho `INSTANT_STORY_TEMPLATES` sinh tức thì 0.1s khi không có LLM.

- [ ] **Step 4: Chạy test để xác nhận pass 100%**
  Chạy `python -m pytest tests/test_fast_story.py` -> PASS.

- [ ] **Step 5: Git commit**
  `git add models/story.py ai/story/fast_generator.py tests/test_fast_story.py`
  `git commit -m "feat(story): implement fast 1-shot coherent story generator without TTS"`

---

### Task 2: Phân Hệ Video AI Trẻ Em & Giáo Dục Chi Phí 0đ (Kids Education Video Engine)

**Files:**
- Create: `video/kids_education/presets.py`
- Create: `video/kids_education/canvas.py`
- Create: `video/kids_education/generator.py`
- Create: `tests/test_kids_education.py`

**Interfaces:**
- Produces: `render_kids_education_video(config: KidsVideoConfig, job_id: str, progress_cb=None) -> KidsVideoResult`

- [ ] **Step 1: Viết test cho Kids Education Video**
  Viết test trong `tests/test_kids_education.py` kiểm tra nạp presets (từ vựng, số đếm, con vật, câu đố, truyện đạo đức), vẽ thẻ canvas hoạt hình offline, và pipeline sinh kịch bản giáo dục.

- [ ] **Step 2: Chạy test để xác nhận fail**
  Chạy `python -m pytest tests/test_kids_education.py` -> FAIL.

- [ ] **Step 3: Triển khai Presets, Canvas Drawer và Video Generator**
  - `presets.py`: Dữ liệu bài học mẫu từ vựng song ngữ, số đếm, câu đố, động vật.
  - `canvas.py`: Hàm vẽ thẻ flashcard rực rỡ, chữ to dễ đọc, khung viền hoạt hình dễ thương bằng Pillow (100% offline).
  - `generator.py`: Tải ảnh AI 0đ (Pollinations) với fallback canvas, tạo voiceover phát âm chuẩn qua `edge-tts`, ghép nhạc BGM vui nhộn và render MP4.

- [ ] **Step 4: Chạy test xác nhận pass 100%**
  Chạy `python -m pytest tests/test_kids_education.py` -> PASS.

- [ ] **Step 5: Git commit**
  `git add video/kids_education/ tests/test_kids_education.py`
  `git commit -m "feat(kids): add zero-cost kids education video engine with presets and TTS"`

---

### Task 3: Video AI Theo Yêu Cầu Linh Hoạt & Chế Độ 0đ (Custom Video Generator)

**Files:**
- Create: `video/custom/generator.py`
- Create: `tests/test_custom_video.py`

**Interfaces:**
- Produces: `render_custom_prompt_video(prompt: str, duration: int, voice_name: str, enable_ai_image: bool = True, progress_cb=None) -> Path`

- [ ] **Step 1: Viết test cho Custom Video Generator**
  Viết test trong `tests/test_custom_video.py` kiểm tra phân tích kịch bản theo prompt tự do, tạo các scene và render video hoàn chỉnh.

- [ ] **Step 2: Chạy test để xác nhận fail**
  Chạy `python -m pytest tests/test_custom_video.py` -> FAIL.

- [ ] **Step 3: Triển khai `video/custom/generator.py`**
  - Phân tách prompt tự do thành 3-5 phân cảnh.
  - Tải/sinh ảnh minh họa và áp dụng hiệu ứng chuyển động Ken Burns 2.5D.
  - Lồng tiếng thuyết minh hoặc nhạc nền.

- [ ] **Step 4: Chạy test xác nhận pass 100%**
  Chạy `python -m pytest tests/test_custom_video.py` -> PASS.

- [ ] **Step 5: Git commit**
  `git add video/custom/ tests/test_custom_video.py`
  `git commit -m "feat(video): add flexible custom prompt video engine"`

---

### Task 4: Cập Nhật Toàn Bộ Giao Diện Gradio & Cấu Hình Docker

**Files:**
- Modify: `docker-compose.yml`
- Modify: `app/ui/layout.py`
- Modify: `app/main.py`
- Create: `tests/test_app_layout.py`

**Interfaces:**
- UI gồm 4 Tabs:
  1. Tab 1: Video Theo Yêu Cầu & Affiliate (Sub-tab Prompt tự do & Sub-tab Sản phẩm/Batch)
  2. Tab 2: Video Trẻ Em & Giáo Dục (Kho presets, xem trước thẻ, 1-click tạo video có giọng đọc 0đ)
  3. Tab 3: Viết Truyện Nhanh (1-shot, chọn độ dài, xem trước & tải file .txt, không TTS)
  4. Tab 4: Lịch Sử Jobs

- [ ] **Step 1: Viết test kiểm tra UI layout và callbacks**
  Viết test trong `tests/test_app_layout.py` kiểm tra khởi tạo app, cấu trúc các tabs và handlers.

- [ ] **Step 2: Cập nhật `docker-compose.yml`**
  Mount các thư mục mã nguồn (`./app`, `./video`, `./ai`, `./models`, `./services`, `./core`, `./tests`, `./utils`) vào container `/app` để cập nhật tức thì.

- [ ] **Step 3: Triển khai cập nhật `app/ui/layout.py` và `app/main.py`**
  - Tích hợp Tab Video Trẻ Em & Giáo Dục.
  - Tích hợp Tab Video Theo Yêu Cầu.
  - Nâng cấp Tab Viết Truyện Nhanh: lược bỏ audio, thêm tùy chọn độ dài, hiển thị ngay kết quả.

- [ ] **Step 4: Chạy toàn bộ test suite dự án**
  Chạy `pytest` trong môi trường docker / local để xác nhận 100% tests pass.

- [ ] **Step 5: Build lại và khởi động lại Docker container**
  Chạy `docker compose restart app` hoặc `docker compose up -d --build app`.

- [ ] **Step 6: Git commit**
  `git add docker-compose.yml app/ui/layout.py app/main.py tests/test_app_layout.py`
  `git commit -m "feat(ui): redesign gradio interface with kids education and fast story tabs"`
