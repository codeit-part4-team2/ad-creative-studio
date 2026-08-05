import torch
from diffusers import StableDiffusionXLControlNetPipeline, ControlNetModel, AutoencoderKL
from controlnet_aux import CannyDetector
from PIL import Image

# 모델 로딩
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16

# 1. ControlNet (Canny, SDXL용) 로딩
controlnet = ControlNetModel.from_pretrained(
    "diffusers/controlnet-canny-sdxl-1.0",
    torch_dtype=dtype
)

# 2. 개선된 VAE 로딩
vae = AutoencoderKL.from_pretrained(
    "madebyollin/sdxl-vae-fp16-fix",
    torch_dtype=dtype
)

# 3. SDXL + ControlNet 파이프라인 조립
pipe = StableDiffusionXLControlNetPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    controlnet=controlnet,
    vae=vae,
    torch_dtype=dtype
)
pipe = pipe.to(device)

# 4. IP-Adapter 로딩 (스타일 참조 이미지 반영용)
pipe.load_ip_adapter(
    "h94/IP-Adapter",
    subfolder="sdxl_models",
    weight_name="ip-adapter_sdxl.bin"
)
pipe.set_ip_adapter_scale(0.6)

# 5. 테스트용 이미지 준비
canny_detector = CannyDetector()
product_image = Image.open("product_sample.jpeg").convert("RGB")
product_image = product_image.resize((1024,1024))
canny_image = canny_detector(product_image)
canny_image.save("canny_debug.png")

# 6. 실제 생성 실행
result = pipe(
    prompt="a small home appliance product photo, studio lighting, white background",
    image=canny_image,
    ip_adapter_image=product_image,
    num_inference_steps=20,
).images[0]

result.save("test_output.png")
print("생성 완료: test_output.png 저장됨")