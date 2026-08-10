# Private music catalog

실제 음악 파일과 운영용 manifest.json은 Git에 올리지 않습니다.

1. 내부 웹 노출과 YouTube 양쪽에서 상업적으로 사용할 수 있는 권리를 확인합니다.
2. manifest.example.json을 비공개 음악 디렉터리의 manifest.json으로 복사합니다.
3. 감성·모던·실용·프리미엄 트랙을 각각 하나씩 배치합니다.
4. 출처 URL, 라이선스, 표시 의무, BPM과 실제 SHA-256을 기록합니다.
5. commercial_use는 근거를 확인한 트랙에만 true로 변경합니다.

필수 검증을 통과하지 못하면 서비스는 음악을 사용하지 않고 경고가 포함된 무음
미리보기를 생성합니다.
