# VM 접속 가이드 (모델 서빙용)

## 인스턴스 정보
- 이름: sprint-ai-serving-vm
- 리전/영역: us-central1-c
- 머신 타입: g2-standard-4 (vCPU 4, 메모리 16GB)
- GPU: NVIDIA L4 x1
- OS: Ubuntu 22.04 LTS, NVIDIA 드라이버 595.71.05, CUDA 13.2 사전 설치

## 접속 방법
1. GCP 콘솔 로그인 (spai계정@codeit-sprint.kr)
2. 해당 링크 접속: [https://console.cloud.google.com/compute/instances?hl=ko&project=sprint-ai-chunk2-02]
3. sprint-ai-serving-vm 옆 "SSH" 버튼 클릭
4. 터미널에서 nvidia-smi 실행 -> NVIDIA L4 확인되면 성공

## 주의 사항
- VM은 프로젝트당 1개 유지 (추가 생성 시 별도 과금)
- API key 등 민감정보는 .env에만 저장, GitHub 업로드 금지

## 가상환경 (venv) 활성화

⚠️ venv는 프로젝트 디렉토리 (`ad-creative-studio/`) 안이 아니라 홈 디렉토리(`~/serving/`)에 위치합니다.

GCP 콘솔에서 SSH로 접속한 후 (위 "접속 방법" 참고), 아래 명령으로 활성화하세요:


```bash
source ~/serving/venv/bin/activate
```

활성화되면 프롬프트 앞에 `(venv)`가 표시됩니다. 이후 프로젝트 디렉토리로 이동해 작업하세요.

```bash
cd ~/ad-creative-studio
```