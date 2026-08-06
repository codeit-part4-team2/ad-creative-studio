import torch
from diffusers import StableDiffusionXLControlNetPipeline, ControlNetModel, AutoencoderKL
from controlnet_aux import CannyDetector
from PIL import Image

def load_pipeline():
    """
    서버 시작 시 1회만 호출.
    ControlNet, VAE, SDXL 파이프라인, IP-Adapter를 로딩해서 완성된 pipe 객체를 반환한다.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
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


def generate_image(pipe,product_image,prompt,negative_prompt,ip_adapter_scale=0.6,num_inference_steps=20):
    """
    요청마다 호출.
    이미 로딩된 pipe와 상품 이미지(PIL Image), 프롬프트를 받아서 생성된 이미지(PIL Image)를 반환한다.
    """
    # 5. Canny edge 추출 (ControlNet 입력용)
    canny_detector = CannyDetector()
    product_image = product_image.resize((1024,1024))
    canny_image = canny_detector(product_image)

    # 6. IP-Adapter scale 적용 (요청마다 다른 값 가능)
    pipe.set_ip_adapter_scale(ip_adapter_scale)

    # 7. 실제 생성 실행
    result = pipe(
        prompt = prompt,
        negative_prompt = negative_prompt,
        image = canny_image,
        ip_adapter_image = product_image,
        num_inference_steps = num_inference_steps,
    ).images[0]

    return result