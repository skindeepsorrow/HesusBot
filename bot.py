import random

import discord
import os
from discord.ext import commands
from discord import app_commands

import database
import sheet_sync

# 봇이 사용할 기본 권한
intents = discord.Intents.default()

# 봇 생성
bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# "오늘의 메뉴" 응답 시 지급할 exp
MENU_EXP = 50

database.initialize_database()


def require_registered(user_id):
    """피아를 구분하기란 늘 어려운 일입니다. 그렇지 않습니까?"""
    return database.is_registered(str(user_id))


@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user}")
    # 전역 동기화: 모든 서버에 명령어가 반영되지만, 최대 1시간 정도 지연될 수 있습니다.
    synced = await bot.tree.sync()
 
    print(f"슬래시 명령어 {len(synced)}개 전역 동기화 완료")


@bot.tree.command(
    name="똑똑",
    description="헤서스가 깨어 있는지 확인합니다.",
)
async def 똑똑(interaction: discord.Interaction):
    await interaction.response.send_message("Pikaboo! 놀랐습니까?")


# 결과 문장, 확률(%), 지급 exp 목록. 확률의 합은 100이 되어야 합니다.
ATTACK_OUTCOMES = [
    ("헤서스는 회피했습니다!", 30, 0),
    ("헤서스는 지천을 켰습니다. 헤서스가 독잇뱀 눈으로 당신을 꼬라보고 있습니다...", 30, 0),
    ("당신이 헤서스를 때리기 전에 헤서스가 당신을 먼저 때렸습니다. 메타모르포제.", 20, 0),
    ("헤서스는 당신을 지나쳐 지나갔습니다. 아무 일도 일어나지 않았습니다.", 15, 100),
    ("당신은 헤서스를 공략하는 데 성공했습니다!", 5, 100),
]
 
 
@bot.tree.command(
    name="공격",
    description="당신은 헤서스를 공격합니다."
)
async def attack(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
 
    if not require_registered(user_id):
        await interaction.response.send_message(
            "오, 아직 귀하의 성함을 모릅니다. `/등록` 부터 해 주셔야지요."
        )
        return
 
    message, _, exp = random.choices(
        ATTACK_OUTCOMES,
        weights=[outcome[1] for outcome in ATTACK_OUTCOMES],
        k=1
    )[0]
 
    if exp > 0:
        leveled_up, new_level, new_exp = database.add_exp(user_id, exp)
        message += f" (+{exp} EXP)"
        if leveled_up:
            message += f"\n🎉 레벨업! 현재 레벨: **{new_level}**"
 
    await interaction.response.send_message(message)
 

@bot.tree.command(
    name="등록",
    description="제가 귀하를 어떻게 불러드리면 좋겠습니까?",
)
@app_commands.describe(성함="불리고 싶은 이름을 입력하세요.")
async def register(interaction: discord.Interaction, 성함: str):
    user_id = str(interaction.user.id)
    success = database.register_user(user_id, 성함)

    if success:
        await interaction.response.send_message(
            f"'{성함}' 님, 맞습니까? 잘 부탁드리지요."
        )
    else:
        user = database.get_user(user_id)
        existing_name = user[1] if user else 성함
        await interaction.response.send_message(
            f"'{existing_name}' 으로 알고 있습니다. 제 기억이 틀릴 리는 없지요."
        )


@bot.tree.command(
    name="프로필",
    description="현재 귀하의 레벨과 EXP를 확인해 드리겠습니다.",
)
async def my_info(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user = database.get_user(user_id)

    if user is None:
        await interaction.response.send_message(
            "오, 아직 귀하의 성함을 모릅니다. `/등록` 부터 해 주시지요."
        )
        return

    _, username, exp, level = user
    needed = database.exp_needed_for_level(level)

    await interaction.response.send_message(
        f"**{username}** 님, 어서 오십쇼.\n"
        f"레벨: {level}\n"
        f"EXP: {exp} / {needed}"
    )


@bot.tree.command(
    name="오늘의메뉴",
    description="흠, 메뉴 말입니까. 정말 제 선택을 믿으십니까?",
)
async def today_menu(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    if not require_registered(user_id):
        await interaction.response.send_message(
            "오, 아직 귀하의 성함을 모릅니다. `/등록` 부터 해 주시지요."
        )
        return

    menu = database.get_random_menu()

    if menu is None:
        await interaction.response.send_message(
            "아직 등록된 메뉴가 없습니다. `/메뉴동기화` 또는 `/메뉴추가` 명령어로 메뉴를 추가해주십쇼."
        )
        return

    result = database.add_exp(user_id, MENU_EXP)
    leveled_up, new_level, new_exp = result

    embed = discord.Embed(
        title=f"오늘의 메뉴: {menu['name']}",
        description=menu["description"] or None,
        color=discord.Color.orange()
    )

    if menu["image_url"]:
        embed.set_image(url=menu["image_url"])

    footer_text = f"+{MENU_EXP} EXP 획득!"
    if leveled_up:
        footer_text += f" 🎉 레벨업! 현재 레벨: {new_level}"
    embed.set_footer(text=footer_text)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="메뉴추가",
    description="오늘의 메뉴 후보를 하나씩 직접 추가합니다. (관리자 전용)",
)
@app_commands.describe(
    메뉴명="추가할 메뉴 이름을 입력하세요.",
    설명="메뉴에 대한 간단한 설명 (선택)",
    이미지url="메뉴 이미지 링크 (선택)"
)
@app_commands.checks.has_permissions(administrator=True)
async def add_menu(interaction: discord.Interaction, 메뉴명: str, 설명: str = "", 이미지url: str = ""):
    database.add_menu(메뉴명, 설명, 이미지url)
    await interaction.response.send_message(
        f"'{메뉴명}' 라는 품목이 추가된 모양이군요."
    )


@add_menu.error
async def add_menu_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "귀하께서는 아직 이쪽에 발을 들이기엔 그릇이 아니 되십니다.",
            ephemeral=True
        )
    else:
        raise error


@bot.tree.command(
    name="메뉴동기화",
    description="구글 스프레드시트(CSV)에서 오늘의 메뉴 목록을 불러와 갱신합니다. (관리자 전용)",
)
@app_commands.checks.has_permissions(administrator=True)
async def sync_menu(interaction: discord.Interaction):
    csv_url = os.getenv("MENU_SHEET_CSV_URL")

    if not csv_url:
        await interaction.response.send_message(
            "환경변수 MENU_SHEET_CSV_URL이 설정되어 있지 않습니다. .env 파일을 확인해주세요.",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    try:
        menus = sheet_sync.fetch_menus_from_csv(csv_url)
        count = database.sync_menus(menus)
    except Exception as e:
        await interaction.followup.send(f"메뉴 동기화 중 오류가 발생했습니다: {e}")
        return

    await interaction.followup.send(f"구글 스프레드시트에서 메뉴 {count}개를 동기화했습니다. ✅")


@sync_menu.error
async def sync_menu_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "귀하께서는 아직 이쪽에 발을 들이기엔 그릇이 아니 되십니다.",
            ephemeral=True
        )
    else:
        raise error


# 봇 토큰은 코드에 직접 넣지 말고 환경변수로 관리하세요.
# 1) pip install python-dotenv requests
# 2) 같은 폴더에 .env 파일을 만들고 안에 아래 두 줄을 작성하세요.
#    DISCORD_BOT_TOKEN=발급받은토큰
#    MENU_SHEET_CSV_URL=구글시트_웹에게시_CSV_URL
# 3) .env는 .gitignore에 추가해서 절대 외부에 공유되지 않게 하세요.
from dotenv import load_dotenv
load_dotenv()

bot.run(os.getenv("DISCORD_BOT_TOKEN"))