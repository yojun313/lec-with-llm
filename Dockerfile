# 1. 베이스 이미지 설정 (Python 3.10 slim 사용)
FROM python:3.10-slim

# 2. 필수 시스템 패키지 설치
# libreoffice: PPT -> PDF 변환
# poppler-utils: PDF -> 이미지 추출
# wkhtmltopdf: Markdown -> PDF 생성
# ffmpeg: 오디오 처리 (Faster-Whisper용)
RUN apt-get update && apt-get install -y \
    libreoffice \
    poppler-utils \
    wkhtmltopdf \
    ffmpeg \
    fonts-nanum \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리 설정
WORKDIR /app

# 4. 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 및 환경 설정 파일 복사
# (스크린샷 구조상 server 폴더 내부에 소스가 있다면 경로를 맞춰주어야 합니다)
COPY . .

# 6. 업로드 및 결과물 저장 폴더 생성 (권한 설정)
RUN mkdir -p static/uploads static/results static/docs

# 7. 포트 설정
EXPOSE 8000

# 8. 서버 실행 (main.py가 루트에 있는 경우)
CMD ["python", "main.py"]