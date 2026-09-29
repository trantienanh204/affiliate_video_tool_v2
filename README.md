# Affiliate Video AI

Hệ thống tạo video Affiliate TikTok từ ảnh sản phẩm, script tiếng Việt và voiceover.

Một cú click: tên sản phẩm + ảnh → script + voiceover tiếng Việt + storyboard + video 9:16.

---

## Tính năng

| Module | Mô tả |
|--------|--------|
| **AI Script** | Ollama (Qwen2.5 / Llama…) hoặc fallback template thông minh |
| **Storyboard** | 4–6 scene, location / camera / lighting / color riêng |
| **TTS** | edge-tts giọng Việt neural (Hoài My, Hương Hạnh, Nam Minh) |
| **Video CPU** | Multi-scene Ken Burns + text overlay + transition |
| **Video AI cloud miễn phí** | Hugging Face ZeroGPU Space (Wan 2.2) – quota hằng ngày, có hàng đợi |
| **Video local** | ComfyUI Image-to-Video – cần GPU NVIDIA phù hợp |
| **Subtitle** | faster-whisper hoặc split script → burn-in |
| **BGM** | Mix nhạc royalty-free từ `assets/music/` |
| **Batch** | Import Excel/CSV → render hàng loạt |
| **Truyện ngắn** | Viết truyện hư cấu dạng voiceover, tạo audio tiếng Việt và tải kịch bản |
| **History** | SQLite job log |
| **UI** | Gradio dark mode, progress, queue, tabs |

Backend mặc định là Hugging Face ZeroGPU để chạy được trên máy không có GPU rời. Ảnh được gửi lên Space; quota miễn phí có giới hạn và dịch vụ có thể bận. fal.ai là lựa chọn trả phí; ComfyUI local cần GPU NVIDIA phù hợp.

---

## Cài đặt nhanh (local)

### Yêu cầu

- Python 3.10+
- FFmpeg
- (Tuỳ chọn) [Ollama](https://ollama.com) + model `qwen2.5:7b`
- (Tuỳ chọn) ComfyUI + GPU cho I2V

```bash
# Ubuntu
sudo apt install ffmpeg fonts-dejavu-core

# Clone / copy project
cd affiliate-video-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Khai báo API key nếu dùng AI video cloud (PowerShell)
$env:FAL_KEY = "YOUR_FAL_API_KEY"

# Chạy
python run.py
# → http://localhost:7860
```

### Docker

```bash
cp .env.example .env
docker compose up -d --build
# App:     http://localhost:7860
# Ollama:  http://localhost:11434

# Pull LLM (một lần)
docker compose exec ollama ollama pull qwen2.5:7b

# Trước khi khởi chạy Compose, khai báo FAL_KEY trong PowerShell
$env:FAL_KEY = "YOUR_FAL_API_KEY"
docker compose up -d --build app
```

---

## Cách dùng

### Single video

1. Chọn danh mục, nhập tên SP, mô tả, giá (tuỳ chọn).
2. Upload 1–n ảnh (nên có người mặc/cầm sản phẩm).
3. Chọn giọng + độ dài → **Tạo video ngay**.
4. Copy caption → TikTok → gắn giỏ hàng.

### Batch

1. Tab **Batch Excel** → tải template mẫu.
2. Điền cột `name` (bắt buộc), các cột khác tuỳ chọn.
3. `image_path` có thể nhiều ảnh, cách nhau bởi `;`.
4. Upload file → **Chạy batch**.

### Truyện ngắn TikTok / YouTube Shorts

1. Mở tab **Truyện ngắn**, chọn mô-típ như thiên kim thật giả, tráo đổi thân phận hoặc tái sinh.
2. Nhập ý tưởng trung tâm và tên nhân vật; AI lập dàn ý 8 chương từ ý tưởng đó rồi viết lần lượt để giữ mạch truyện.
3. Chọn thời lượng tối thiểu 15–20 phút, tông kể, kiểu kết và giọng đọc.
4. Nhận kịch bản, caption, audio tiếng Việt và file văn bản. Truyện dài dùng model Ollama local; cài bằng lệnh docker compose exec ollama ollama pull qwen2.5:7b.

### AI Video miễn phí / Hugging Face ZeroGPU

1. Không cần API key trả phí. Có thể tạo Hugging Face access token miễn phí, rồi đặt biến `HF_TOKEN` để dùng quota theo tài khoản.
2. Rebuild app bằng `docker compose up -d --build app`.
3. Mỗi yêu cầu sinh clip I2V ngắn từ ảnh rồi ghép voiceover. Có thể phải xếp hàng hoặc chờ quota hằng ngày reset.

### GPU / ComfyUI local

1. Chạy ComfyUI (`:8188`).
2. Export workflow I2V ở **API Format** → `workflows/i2v_ltx.json`.
3. `.env`:
   ```
   AVA_RENDER_MODE=gpu
   AVA_COMFYUI_ENABLED=true
   AVA_COMFYUI_URL=http://127.0.0.1:8188
   ```
4. Đặt `AVA_VIDEO_PROVIDER=comfyui`; không có ComfyUI/workflow sẽ báo lỗi, không giả làm video AI.

---

## Cấu trúc project

```
affiliate-video-ai/
├── app/                # Gradio UI
├── ai/                 # LLM analyzer + storyboard
├── video/              # Ken Burns, compositor, subtitle, music, engine
├── tts/                # edge-tts
├── services/           # ComfyUI, batch, history
├── models/             # Pydantic domain models
├── core/               # config, logging, exceptions
├── utils/
├── assets/music/       # đặt file BGM royalty-free tại đây
├── workflows/          # ComfyUI API workflow JSON
├── outputs/            # video kết quả
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── run.py
```

---

## Cấu hình chính (`.env`)

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `AVA_RENDER_MODE` | `cpu` | `cpu` \| `gpu` |
| `AVA_OLLAMA_MODEL` | `qwen2.5:7b` | Model Ollama |
| `AVA_COMFYUI_ENABLED` | `false` | Bật I2V |
| `AVA_BURN_SUBTITLES` | `true` | Gắn phụ đề |
| `AVA_ENABLE_BGM` | `true` | Mix nhạc nền |
| `AVA_MAX_BATCH_SIZE` | `100` | Giới hạn batch |

Xem đầy đủ trong `.env.example`.

---

## Roadmap đã hoàn thành

- [x] Kiến trúc module + config production
- [x] AI analysis / script / storyboard (Ollama + fallback)
- [x] TTS tiếng Việt
- [x] Multi-scene Ken Burns compositor
- [x] Gradio dark UI + progress + queue
- [x] Batch Excel + History SQLite
- [x] ComfyUI I2V client (pluggable)
- [x] Subtitle + BGM
- [x] Docker / docker-compose / README

---

## Lưu ý Affiliate TikTok Shop

- Cần ≥ 1000 follower để gắn giỏ hàng trong video.
- Bật Content disclosure khi đăng.
- Không spam cùng 1 sản phẩm quá nhiều video liên tiếp.
- Ưu tiên ảnh có người + bối cảnh thật.

---

Chúc bạn scale volume và kiếm hoa hồng tốt.
