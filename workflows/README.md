# ComfyUI Workflows

Đặt file workflow API format vào đây.

## Cách export từ ComfyUI

1. Mở ComfyUI, load workflow I2V (LTX-Video / Wan 2.1 / CogVideoX…).
2. Bật **Enable Dev mode Options** (settings).
3. Click **Save (API Format)** – không phải Save thường.
4. Đổi tên thành `i2v_ltx.json` (hoặc `i2v_wan.json`) và copy vào thư mục này.

## Node cần có

- `LoadImage` – nhận ảnh sản phẩm
- Text encode positive / negative
- Sampler + model I2V
- Node xuất video (`VHS_VideoCombine`, `SaveVideo`, …)

Hệ thống sẽ tự inject:
- image filename
- positive / negative prompt
- width / height / frame length
- seed

Nếu class_type khác chuẩn, chỉnh `_inject_inputs` trong `services/comfyui/i2v.py`.
