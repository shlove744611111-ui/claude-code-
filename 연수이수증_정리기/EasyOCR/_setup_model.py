# -*- coding: utf-8 -*-
# 최초 설치 시 한글 OCR 모델을 ./models 폴더로 내려받습니다.
import easyocr
easyocr.Reader(['ko'], gpu=False, model_storage_directory='models', download_enabled=True)
print('모델 준비 완료')
