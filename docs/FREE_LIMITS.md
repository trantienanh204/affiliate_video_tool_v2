# Giới hạn miễn phí & máy không GPU

## Máy không có NVIDIA GPU (như HP i5-13500H + Iris Xe)

| Mong muốn | Có free local không? |
|-----------|----------------------|
| Script / caption / hashtag AI | ✅ Ollama |
| Voiceover tiếng Việt | ✅ edge-tts |
| Batch Excel 100 SP | ✅ |
| Video đa cảnh từ **nhiều ảnh** | ✅ (photo-motion, không phải neural) |
| Video AI neural (Wan / LTX / Kling-like) | ❌ Cần CUDA GPU |

## Cách dùng free tối đa trên máy hiện tại

1. Chuẩn bị **3–5 ảnh** cùng 1 sản phẩm:
   - Góc toàn thân / close-up / chi tiết chất liệu / người mặc
2. Upload đủ ảnh trong tab **Tạo video**
3. Để AI chia scene: mỗi ảnh một cảnh + chuyển động khác nhau + voice
4. Dùng Batch cho volume caption/script

Kết quả **không** bằng Kling, nhưng là mức **cao nhất có thể với 0đ + không GPU**.

## Nếu sau này có GPU NVIDIA (8GB+)

Xem `docs/AI_VIDEO_SETUP.md` → bật ComfyUI + Wan/LTX → video AI thật, vẫn free model.

## Không dùng

- API trả phí (Kling, Runway, Pika, fal, ElevenLabs…)
- Cloud GPU trả phí

Đúng với yêu cầu: **ưu tiên free / local / open-source**.
