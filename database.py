import sqlite3
import random


# 데이터베이스 파일 이름
DB_NAME = "database.db"


def get_connection():
    """데이터베이스에 연결합니다."""
    return sqlite3.connect(DB_NAME)


def _ensure_column(cursor, table, column, coltype):
    """테이블에 해당 컬럼이 없으면 추가합니다 (간단한 마이그레이션용)."""
    cursor.execute(f"PRAGMA table_info({table})")
    existing_columns = [row[1] for row in cursor.fetchall()]

    if column not in existing_columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


def initialize_database():
    """필요한 데이터베이스 테이블을 만들고, 이전 버전과의 호환을 위해 컬럼을 보정합니다."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            exp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS menus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menu_name TEXT NOT NULL
        )
    """)

    # 이전 버전에는 없던 컬럼들을 보정 (이미 menus 테이블이 있던 경우 대비)
    _ensure_column(cursor, "menus", "description", "TEXT")
    _ensure_column(cursor, "menus", "image_url", "TEXT")

    connection.commit()
    connection.close()


# ---------------------------------------------------------
# 사용자 / EXP / 레벨 관련
# ---------------------------------------------------------

def register_user(user_id, username):
    """새로운 사용자를 등록합니다. 이미 등록되어 있으면 False를 반환합니다."""

    connection = get_connection()
    cursor = connection.cursor()

    # 이미 가입했는지 확인
    cursor.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,)
    )

    existing_user = cursor.fetchone()

    if existing_user:
        connection.close()
        return False

    # 새로운 사용자 등록
    cursor.execute(
        "INSERT INTO users (user_id, username, exp, level) VALUES (?, ?, 0, 1)",
        (user_id, username)
    )

    connection.commit()
    connection.close()

    return True


def get_user(user_id):
    """
    사용자 정보를 (user_id, username, exp, level) 튜플로 반환합니다.
    등록되지 않은 사용자라면 None을 반환합니다.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT user_id, username, exp, level FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cursor.fetchone()
    connection.close()

    return row


def is_registered(user_id):
    """사용자가 이미 등록되어 있는지 확인합니다."""
    return get_user(user_id) is not None


def exp_needed_for_level(level):
    """해당 레벨에서 다음 레벨로 올라가기 위해 필요한 exp량을 계산합니다."""
    return level * 100


def add_exp(user_id, amount):
    """
    사용자에게 exp를 지급하고, 필요하다면 레벨업까지 처리합니다.

    반환값:
        - 사용자가 등록되어 있지 않다면 None
        - 등록되어 있다면 (leveled_up, new_level, new_exp) 튜플
          leveled_up: 이번 지급으로 레벨이 올랐는지 여부 (bool)
          new_level: 지급 후 최종 레벨
          new_exp: 지급 후 현재 레벨 내에서의 exp
    """

    user = get_user(user_id)

    if user is None:
        return None

    _, username, exp, level = user
    exp += amount

    leveled_up = False

    # exp가 다음 레벨 필요치를 넘으면 여러 번 레벨업 될 수 있으므로 while로 처리
    while exp >= exp_needed_for_level(level):
        exp -= exp_needed_for_level(level)
        level += 1
        leveled_up = True

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "UPDATE users SET exp = ?, level = ? WHERE user_id = ?",
        (exp, level, user_id)
    )

    connection.commit()
    connection.close()

    return leveled_up, level, exp


# ---------------------------------------------------------
# 오늘의 메뉴 관련
# ---------------------------------------------------------

def add_menu(menu_name, description="", image_url=""):
    """오늘의 메뉴 후보를 DB에 추가합니다."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "INSERT INTO menus (menu_name, description, image_url) VALUES (?, ?, ?)",
        (menu_name, description, image_url)
    )

    connection.commit()
    connection.close()


def sync_menus(menu_list):
    """
    외부(예: 구글 스프레드시트)에서 가져온 메뉴 목록으로 menus 테이블을 통째로 갱신합니다.
    menu_list: [{"name": ..., "description": ..., "image_url": ...}, ...]

    반환값: 새로 저장된 메뉴 개수
    """

    connection = get_connection()
    cursor = connection.cursor()

    # 기존 메뉴를 모두 지우고 시트 내용으로 다시 채웁니다 (시트가 최신 정답이라고 가정).
    cursor.execute("DELETE FROM menus")

    for menu in menu_list:
        cursor.execute(
            "INSERT INTO menus (menu_name, description, image_url) VALUES (?, ?, ?)",
            (menu["name"], menu.get("description", ""), menu.get("image_url", ""))
        )

    connection.commit()
    connection.close()

    return len(menu_list)


def get_all_menus():
    """등록된 모든 메뉴를 딕셔너리 리스트로 반환합니다."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT menu_name, description, image_url FROM menus")
    rows = cursor.fetchall()

    connection.close()

    return [
        {"name": row[0], "description": row[1], "image_url": row[2]}
        for row in rows
    ]


def get_random_menu():
    """등록된 메뉴 중 하나를 무작위로 반환합니다. 메뉴가 없으면 None을 반환합니다."""

    menus = get_all_menus()

    if not menus:
        return None

    return random.choice(menus)