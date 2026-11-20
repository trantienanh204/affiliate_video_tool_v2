# Thiết kế Hệ thống: Tái cấu trúc Video AI Chi Phí 0đ & Viết Truyện Tối Ưu

- **Ngày cập nhật:** 2026-11-20
- **Trạng thái:** Chờ người dùng phê duyệt lần cuối (Pending Approval)
- **Tác giả:** Antigravity AI & User
- **Quyết định đã chốt:** **A1** (Có phát âm 0đ qua `edge-tts` cho video giáo dục trẻ em) + **B1** (Giữ luồng Affiliate & Batch Excel trong chế độ sản phẩm).

---

## 1. Bối cảnh & Mục tiêu (Context & Goals)

Tái cấu trúc toàn diện hệ thống Affiliate Video AI thành nền tảng đa năng:
1. **Video AI Chi phí 0đ (Zero-Cost Video Engine):**
   - Vận hành mượt mà trên mọi máy tính (CPU / Docker) mà không cần GPU 12GB+ hoặc API cloud trả phí.
   - Thêm phân hệ chuyên biệt: **Video Trẻ Em & Giáo Dục Đơn Giản** (từ vựng, số đếm, con vật, câu đố hoạt hình, truyện đạo đức) có giọng đọc phát âm chuẩn 0đ (`edge-tts`) và nhạc nền vui nhộn.
   - Hỗ trợ tạo video linh hoạt theo **Prompt yêu cầu tự do** lẫn chế độ **Sản phẩm Affiliate & Batch Excel** truyền thống.
2. **Viết Truyện Tối Ưu (Ultra-Fast & Coherent Story Generation):**
   - Giảm thời gian sinh từ hàng chục phút (vòng lặp 8 chương cũ) xuống còn vài giây (1-shot LLM hoặc instant creative templates).
   - Truyện mạch lạc, logic nhân vật và cốt truyện chặt chẽ, cuốn hút.
   - **Lược bỏ hoàn toàn giọng đọc TTS** cho phân hệ truyện (chỉ tập trung xuất bản kịch bản/truyện chữ chất lượng cao và file `.txt`).

---

## 2. Các quyết định kiến trúc đã chốt (Architectural Decisions)

| Hạng mục | Quyết định đã chốt | Chi tiết kỹ thuật |
|----------|--------------------|-------------------|
| **Dựng Video AI** | **Phương án A (Zero-Cost 2D/2.5D)** | MoviePy + Ken Burns pan/zoom + badge hoạt hình + khung viền cartoon + text động. |
| **Giọng đọc Video Giáo dục** | **A1: Tích hợp Voiceover 0đ** | Dùng `edge-tts` neural giọng đọc chuẩn, tự động căn chỉnh thời lượng cảnh theo độ dài tiếng nói, có nút bật/tắt. |
| **Tính năng Affiliate & Batch** | **B1: Giữ lại & Gom nhóm** | Tab "Video Theo Yêu Cầu" có 2 chế độ: *Prompt Tự Do* & *Sản Phẩm / Batch Excel*. |
| **Nguồn ảnh minh họa** | **Hybrid: Free AI + Offline Canvas** | Gọi API tạo ảnh hoạt hình miễn phí (Pollinations/HF Spaces), tự động fallback vẽ thẻ Flashcard đồ họa bằng Pillow nếu offline. |
| **Module Viết truyện** | **1-Shot Cohesive + No TTS** | Viết toàn bộ câu chuyện trong 1 lượt với quy tắc narrative arc chặt chẽ. Hỗ trợ 3 mức độ dài (Ngắn, Vừa, Dài). Không sinh audio. |
| **GPU / Cloud cũ** | **Giữ dưới dạng cờ cấu hình (Flag)** | Mặc định chạy `RenderMode.CPU` (0đ), giữ nguyên code ComfyUI/fal phòng khi người dùng muốn bật lại sau này. |

---

## 3. Thiết kế chi tiết các phân hệ (Detailed Component Design)

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Gradio Dashboard                              │
│  [Tab 1: Video Theo Yêu Cầu & Affiliate]   [Tab 2: Video Bé & Giáo Dục]│
│  [Tab 3: Viết Truyện Nhanh (Text-Only)]    [Tab 4: Lịch Sử Jobs]       │
└───────────────────┬──────────────────────────────────┬─────────────────┘
                    │                                  │
          ┌─────────▼─────────┐              ┌─────────▼─────────┐
          │  Video AI Engine  │              │  Fast Story Gen   │
          │   (Zero-Cost)     │              │   (Text-Only)     │
          └─────────┬─────────┘              └─────────┬─────────┘
                    │                                  │
     ┌──────────────┴──────────────┐         ┌─────────┴─────────┐
     │ - Image Provider (AI/Canvas)│         │ - 1-Shot Ollama   │
     │ - Ken Burns & Compositor    │         │ - Instant Template│
     │ - Edge-TTS 0đ + BGM Ducking │         │   Fallback        │
     │ - Presets (Kids & Products) │         │ - Coherence Prompt│
     └─────────────────────────────┘         └───────────────────┘
```

### Phân hệ 1: Video Trẻ Em & Giáo Dục (`video/kids_education/`)
- **Kho Presets nội dung:**
  - `vocabulary`: Học từ vựng Anh - Việt theo chủ đề (Động vật, Trái cây, Phương tiện, Gia đình...).
  - `numbers`: Học đếm số vui nhộn kèm minh họa số lượng con vật/đồ vật.
  - `animals`: Khám phá thế giới động vật (hình ảnh hoạt hình, âm thanh, tên gọi, sự thật thú vị).
  - `riddles`: Câu đố mẹo phát triển tư duy (câu hỏi, hình gợi ý và giải đáp hoạt họa).
  - `moral_stories`: Truyện ngụ ngôn đạo đức ngắn (30-60s) dạy bé lòng biết ơn, chia sẻ, trung thực.
- **Pipeline dựng video giáo dục:**
  1. *Kịch bản & Thẻ học:* Sinh các flashcard cảnh (chữ lớn, song ngữ, mô tả hình ảnh).
  2. *Tạo ảnh 0đ:* Tải ảnh hoạt hình màu sắc tươi sáng từ AI tạo ảnh miễn phí (Pollinations AI). Nếu không có mạng hoặc lỗi, tự động chuyển sang chế độ vẽ thẻ canvas đồ họa sắc nét bằng Pillow.
  3. *Giọng đọc mẫu 0đ:* Dùng `edge-tts` (giọng đọc trẻ em hoặc giọng đọc chuẩn) đọc tên từ vựng/câu hỏi/kịch bản. Tự động tính toán thời lượng mỗi cảnh khớp với giọng nói.
  4. *Ghép nhạc & Hiệu ứng:* Hòa âm giọng đọc với nhạc nền thiếu nhi (audio ducking: giảm âm lượng nhạc khi có tiếng đọc), thêm hiệu ứng chuyển cảnh và viền khung hoạt họa.

### Phân hệ 2: Video Theo Yêu Cầu & Sản Phẩm Affiliate (`video/custom/` & `services/product/`)
- **Chế độ 1: Tạo theo Prompt tự do:**
  - Nhập ý tưởng/chủ đề (ví dụ: "Review mẹo công nghệ", "Phong cảnh thiên nhiên thư giãn", "Giới thiệu quán cà phê").
  - Phân tích cảnh tự động -> sinh ảnh/lấy ảnh -> pan/zoom Ken Burns -> lồng voiceover/BGM -> render MP4 9:16.
- **Chế độ 2: Sản phẩm Affiliate & Batch Excel:**
  - Giữ nguyên luồng nhập thông tin sản phẩm và upload file Excel/CSV chạy render hàng loạt.

### Phân hệ 3: Viết Truyện Tối Ưu Tốc Độ & Liền Mạch (`ai/story/fast_generator.py`)
- **Tối ưu tốc độ & cốt truyện:**
  - Chuyển thành quy trình **1-Shot LLM** với Prompt cấu trúc chặt chẽ (Narrative Arc): Khởi đầu -> Xung đột nảy sinh -> Cao trào -> Nút thắt/Bất ngờ -> Hóa giải/Kết bài.
  - Bộ từ vựng, tính cách nhân vật và bối cảnh được neo chặt trong 1 prompt duy nhất, loại bỏ hoàn toàn hiện tượng quên cốt truyện hoặc mâu thuẫn giữa các chương.
  - Tích hợp **Instant Creative Template Generator**: Kho kịch bản và template xây dựng sẵn, cho phép xuất bản truyện hay ngay lập tức trong 0.1 giây nếu Ollama không khả dụng.
- **Tùy chọn độ dài:**
  - *Ngắn (Short):* ~300 - 500 từ (phù hợp đọc lướt, làm video ngắn).
  - *Vừa (Medium):* ~800 - 1200 từ (tiểu phẩm, truyện ngắn kịch tính).
  - *Dài (Long):* ~1500 - 2500 từ (truyện hoàn chỉnh, đầy đủ diễn biến).
- **Loại bỏ TTS audio:**
  - Không khởi tạo tiến trình sinh âm thanh, trả kết quả văn bản ngay kèm bản tải `.txt`.

### Phân hệ 4: Tái cấu trúc Giao diện Gradio (`app/ui/`)
- Giao diện được sắp xếp lại thành 4 Tabs chính:
  1. **Tab 1: 🎬 Video Theo Yêu Cầu & Affiliate** (Sub-tab Prompt tự do & Sub-tab Sản phẩm/Batch).
  2. **Tab 2: 🧸 Video Trẻ Em & Giáo Dục** (Chọn chủ đề preset hoặc nhập chủ đề riêng, chọn giọng đọc, 1-click tạo video).
  3. **Tab 3: 📖 Viết Truyện Nhanh** (Chọn mô-típ, nhập ý tưởng, chọn độ dài, sinh truyện tức thì, tải file text).
  4. **Tab 4: 📜 Lịch Sử & Quản Lý** (Xem lại các sản phẩm đã render).

---

## 4. Kế hoạch Kiểm thử & Quy chuẩn (Verification & Testing)

Theo quy định `AGENTS.md`:
1. Viết bộ kiểm thử toàn diện với `pytest`:
   - `tests/test_fast_story.py`: Kiểm thử luồng sinh truyện nhanh 1-shot, các mức độ dài, kiểm thử tính toàn vẹn cốt truyện và template fallback.
   - `tests/test_kids_education.py`: Kiểm thử bộ preset giáo dục, sinh thẻ flashcard, xử lý ảnh offline và audio voiceover.
   - `tests/test_compositor_zero_cost.py`: Kiểm thử ghép video Ken Burns 2.5D, hòa trộn âm thanh ducking và xuất file MP4.
2. Mọi bài kiểm tra phải pass 100% trước khi hoàn tất.
3. Tạo commit git riêng cho từng tính năng và cập nhật.
