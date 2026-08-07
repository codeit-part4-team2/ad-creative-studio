import torch
from diffusers import StableDiffusionXLControlNetPipeline, ControlNetModel, AutoencoderKL
from controlnet_aux import CannyDetector
from PIL import Image

def _fit_square(image: Image.Image, size: int = 1024) -> Image.Image:
    """
    비율을 유지한 채 size x size 캔버스 중앙에 배치한다 (레터박스).
    단순 resize는 세로로 긴 상품을 가로로 눌러버려서 제품 보존율을 떨어뜨린다.
    """
    image = image.convert("RGB")
    image.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), (255,255,255))
    canvas.paste(image, ((size - image.width) // 2, (size - image.height) // 2))
    return canvas


def load_pipeline():
    """
    서버 시작 시 1회만 호출.
    ControlNet, VAE, SDXL 파이프라인, IP-Adapter를 로딩해서 완성된 pipe 객체를 반환한다.
    """
    if not torch.cuda.is_available():
        raise RuntimeError("model_server는 CUDA GPU가 필요합니다. VM의 GPU 할당 상태를 확인하세요.")
    device = "cuda"
    dtype = torch.float16

    # 1. ControlNet (Canny, SDXL용) 로딩
    controlnet = ControlNetModel.from_pretrained(
        "diffusers/controlnet-canny-sdxl-1.0",
        torch_dtype = dtype
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

    return pipe


def generate_image(pipe,product_image,prompt,negative_prompt,ip_adapter_scale=0.6,num_inference_steps=20, seed=None):
    """
    요청마다 호출.
    이미 로딩된 pipe와 상품 이미지(PIL Image), 프롬프트를 받아서 생성된 이미지(PIL Image)를 반환한다.
    """
    # 5. Canny edge 추출 (ControlNet 입력용)
    canny_detector = CannyDetector()
    product_image = _fit_square(product_image, 1024)
    canny_image = canny_detector(
        product_image,
        detect_resolution=1024,
        image_resolution=1024,
    )

    # 6. IP-Adapter scale 적용 (요청마다 다른 값 가능)
    pipe.set_ip_adapter_scale(ip_adapter_scale)

    # 7. seed 고정 (재현 가능한 비교를 위해)
    generator = None
    if seed is not None:
        generator = torch.Generator(device=pipe.device).manual_seed(seed)

    # 8. 실제 생성 실행
    result = pipe(
        prompt = prompt,
        negative_prompt = negative_prompt,
        image = canny_image,
        ip_adapter_image = product_image,
        num_inference_steps = num_inference_steps,
        height=1024,
        width=1024,
        generator=generator,
    ).images[0]

    return result