import csv
import io

import requests


def fetch_menus_from_csv(csv_url):
    """
    '웹에 게시'로 공개한 구글 스프레드시트의 CSV URL에서 메뉴 데이터를 가져옵니다.

    시트의 첫 번째 행은 헤더로 간주하며, 다음 컬럼명을 찾습니다:
        - 메뉴명 (필수)
        - 설명   (선택)
        - 이미지URL (선택)

    반환값: [{"name": ..., "description": ..., "image_url": ...}, ...]
    """

    response = requests.get(csv_url, timeout=10)
    response.raise_for_status()

    # 구글 시트 CSV는 BOM이 붙어 나오는 경우가 있어 utf-8-sig로 디코딩합니다.
    csv_text = response.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_text))

    menus = []

    for row in reader:
        name = (row.get("메뉴명") or "").strip()

        # 메뉴명이 없는 빈 줄은 건너뜁니다.
        if not name:
            continue

        menus.append({
            "name": name,
            "description": (row.get("설명") or "").strip(),
            "image_url": (row.get("이미지URL") or "").strip(),
        })

    return menus
