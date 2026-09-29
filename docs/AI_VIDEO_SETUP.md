# Hướng dẫn bật AI Video thật (Image-to-Video)

## Máy không có GPU NVIDIA: dùng Hugging Face ZeroGPU miễn phí

**Hai loại key khác nhau:** `HF_TOKEN` là key Hugging Face dùng cho ZeroGPU/Spaces. `FAL_KEY` là key riêng của fal.ai và dịch vụ này có thể tính phí. Thêm `HF_TOKEN` không bật được backend fal.ai.

Máy dùng Intel Iris Xe không phù hợp để chạy Wan/LTX I2V qua ComfyUI local. Backend mặc định là Hugging Face Space `zerogpu-aoti/wan2-2-fp8da-aoti-faster`, chạy Wan 2.2 trên ZeroGPU. Dịch vụ cho dùng miễn phí với quota hằng ngày; tài liệu hiện ghi tài khoản miễn phí có 5 phút GPU/ngày, người chưa đăng nhập 2 phút/ngày. Quota, thời gian chờ và khả năng Space hoạt động có thể thay đổi. Ảnh sản phẩm được gửi lên Space để xử lý. Có thể đặt `HF_TOKEN` miễn phí để dùng quota tài khoản.

Space: https://huggingface.co/spaces/zerogpu-aoti/wan2-2-fp8da-aoti-faster

PowerShell, tại thư mục project:

```powershell
$env:HF_TOKEN = "YOUR_HUGGINGFACE_READ_TOKEN"
$env:AVA_VIDEO_PROVIDER = "hf_zerogpu"
$env:AVA_VIDEO_PROVIDER_FALLBACKS = "fal,comfyui"
docker compose up -d --build app
```

Khi HF lỗi/hết quota, ứng dụng tự thử fal.ai nếu có `FAL_KEY`, rồi thử ComfyUI nếu kết nối được. fal.ai là dịch vụ có thể tính phí; nếu chỉ để trống `FAL_KEY`, ứng dụng sẽ bỏ qua provider này và báo rõ khi các nguồn miễn phí/local khác đều không sẵn sàng. ZeroGPU quota dùng chung theo tài khoản, nên token không làm quota vô hạn và một Space dự phòng khác cũng không bảo đảm vượt quota.

Mặc định video dùng hai bước: Qwen Image tạo keyframe hoạt hình 3D có nhân vật hư cấu, sau đó Wan I2V tạo chuyển động. Voiceover truyền tải nội dung nên app không chèn text trang trí. Cả hai lượt dùng quota ZeroGPU; nếu lượt keyframe hết quota, app không cố xuất video chụp thật trái với phong cách đã chọn. Vì AI tái tạo hình ảnh, chi tiết vải/đường may có thể khác ảnh nguồn.

Project chỉ gọi Space khi bạn gửi yêu cầu tạo video. Mỗi lần tạo sẽ gửi ảnh sản phẩm lên Hugging Face. Nếu không muốn dùng cloud, cần máy có GPU NVIDIA đủ VRAM để chạy ComfyUI, hoặc dùng `AVA_VIDEO_PROVIDER=fal` (trả phí).

## ComfyUI local

Ken Burns (zoom ảnh) **không phải** sản phẩm chính.  
Sản phẩm chính = **ComfyUI + model I2V** tạo chuyển động thật từ ảnh sản phẩm.

---

## 1. Phần cứng tối thiểu

| GPU VRAM | Model khuyến nghị | Ghi chú |
|----------|-------------------|---------|
| **8–12 GB** | Wan 2.1 1.3B / GGUF Q4 | Chậm, clip ngắn 2–4s |
| **16 GB** | LTX-2.3 distilled GGUF / Wan GGUF | Cân bằng tốt |
| **24 GB** | Wan 2.1/2.2 I2V 14B FP8, LTX full | Chất lượng production |

**Không có GPU NVIDIA** → không thể chạy I2V local chất lượng.  
CPU-only chỉ còn script + voice + placeholder (không phải AI video).

---

## 2. Cài ComfyUI

```bash
# Cách nhanh (portable / git)
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -r requirements.txt
# Có GPU NVIDIA:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

python main.py --listen 0.0.0.0 --port 8188
```

Mở http://127.0.0.1:8188 xác nhận chạy được.

---

## 3. Chọn model I2V (free / local)

### Khuyến nghị 2026

1. **Wan 2.1 / 2.2 I2V** (Alibaba, Apache 2.0) – chất lượng motion tốt  
2. **LTX-2.3** (Lightricks) – nhanh hơn, có bản distilled / GGUF cho 16GB  

Trong ComfyUI:
- Menu **Template Library → Video → LTX-2.3 Image to Video**  
  hoặc workflow Wan I2V từ docs ComfyUI / Civitai.

Tải checkpoint theo hướng dẫn template (đặt vào `models/checkpoints` hoặc `diffusion_models`).

---

## 4. Export workflow API cho tool

1. Trong ComfyUI, load workflow **Image-to-Video** đã chạy thử thành công.  
2. Bật **Dev mode** (Settings).  
3. **Save (API Format)** – không phải Save thường.  
4. Đổi tên file thành:

```
affiliate-video-ai/workflows/i2v_ltx.json
```

(hoặc `i2v_wan.json` nếu dùng Wan)

5. Tool sẽ inject tự động:
   - ảnh sản phẩm (LoadImage)
   - prompt / negative từ storyboard
   - size 9:16, số frame, seed

Nếu class_type node khác chuẩn, chỉnh `services/comfyui/i2v.py` → `_inject_inputs`.

---

## 5. Bật trong Affiliate Video AI

`.env`:

```env
AVA_RENDER_MODE=gpu
AVA_COMFYUI_ENABLED=true
AVA_COMFYUI_URL=http://127.0.0.1:8188
AVA_REQUIRE_AI_VIDEO=true
AVA_I2V_MAX_SCENES=2
AVA_I2V_SCENE_DURATION=3
```

Nếu app chạy Docker, ComfyUI trên host:

```env
AVA_COMFYUI_URL=http://host.docker.internal:8188
```

Restart app:

```bash
docker compose up -d --build app
# hoặc
python run.py
```

---

## 6. Pipeline khi GPU bật

```
Ảnh sản phẩm
  → AI viết script + storyboard (4–6 scene, prompt I2V từng cảnh)
  → ComfyUI I2V tối đa 2 cảnh ngắn (giữ identity sản phẩm)
  → MoviePy ghép scene + TTS + subtitle + BGM
  → Video 9:16
```

Mỗi scene = **clip AI thật** (chuyển động camera / sản phẩm / bối cảnh), không phải zoom ảnh.

---

## 7. Không có GPU thì sao?

Hiện **không có** model I2V open-source chạy CPU ra video affiliate chất lượng.  
Các hướng thay thế:

| Hướng | Ghi chú |
|-------|---------|
| Thuê GPU cloud (RunPod, Vast, etc.) | Chỉ trả GPU, tự host ComfyUI |
| Máy có RTX 3060 12GB+ | Đủ chạy bản GGUF nhỏ |
| Giữ CPU mode | Chỉ preview script/voice – **không phải AI video** |

Tool cố tình **không** gắn API trả phí (Kling, Runway, fal…) theo yêu cầu ban đầu.

---

## Checklist nhanh

- [ ] GPU NVIDIA ≥ 8GB (tốt nhất ≥ 16GB)  
- [ ] ComfyUI chạy tại `:8188`  
- [ ] Model I2V đã tải + workflow test OK trong ComfyUI  
- [ ] `workflows/i2v_ltx.json` (API format) có trong project  
- [ ] `.env`: `AVA_RENDER_MODE=gpu`, `AVA_COMFYUI_ENABLED=true`  
- [ ] Upload **ảnh sản phẩm** khi tạo video (bắt buộc cho I2V)  

## Tối ưu thời gian

Tool mặc định chỉ sinh tối đa 2 clip I2V, mỗi clip 3 giây, thay vì gọi model tuần tự 4–6 lần. Voiceover chạy đồng thời với ComfyUI. Video hoàn chỉnh lặp các clip AI ngắn cho đủ thời lượng voice, giúp giảm thời gian chờ; muốn nhiều chuyển động đa dạng hơn, tăng `AVA_I2V_MAX_SCENES` lên 3–4 và chấp nhận render lâu hơn. Tốc độ vẫn phụ thuộc GPU, model, độ phân giải và số bước của workflow.

Nếu `AVA_REQUIRE_AI_VIDEO=true`, ComfyUI lỗi/mất kết nối hoặc thiếu workflow thì app dừng và báo lỗi, không xuất preview zoom ảnh. Chỉ đặt `false` nếu muốn cho phép CPU preview.
