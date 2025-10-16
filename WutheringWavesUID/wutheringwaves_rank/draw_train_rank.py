import asyncio
import copy
from pathlib import Path
from typing import List, Optional, Union

from PIL import Image, ImageDraw

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import crop_center_img

from ..utils.api.model import AccountBaseInfo
from ..utils.api.wwapi import CharScoreDetail, TotalRankDetail
from ..utils.cache import TimedCache
from ..utils.char_info_utils import get_all_roleid_detail_info_int
from ..utils.database.models import WavesBind
from ..utils.error_reply import WAVES_CODE_102
from ..utils.expression_ctx import get_waves_char_rank
from ..utils.fonts.waves_fonts import (
    waves_font_12,
    waves_font_16,
    waves_font_18,
    waves_font_20,
    waves_font_28,
    waves_font_30,
    waves_font_34,
    waves_font_58,
)
from ..utils.image import (
    AMBER,
    GREY,
    RED,
    SPECIAL_GOLD,
    WAVES_FREEZING,
    WAVES_LINGERING,
    WAVES_MOLTEN,
    WAVES_MOONLIT,
    WAVES_SIERRA,
    WAVES_VOID,
    add_footer,
    get_ICON,
    get_qq_avatar,
    get_square_avatar,
    get_waves_bg,
)
from ..utils.waves_api import waves_api
from ..wutheringwaves_config import PREFIX, WutheringWavesConfig

TEXT_PATH = Path(__file__).parent / "texture2d"
avatar_mask = Image.open(TEXT_PATH / "avatar_mask.png")
char_mask = Image.open(TEXT_PATH / "char_mask.png")
pic_cache = TimedCache(600, 200)


BOT_COLOR = [
    WAVES_MOLTEN,
    AMBER,
    WAVES_VOID,
    WAVES_SIERRA,
    WAVES_FREEZING,
    WAVES_LINGERING,
    WAVES_MOONLIT,
]


async def get_avatar(
    qid: Optional[str],
) -> Image.Image:
    if qid and qid.isdigit():
        if WutheringWavesConfig.get_config("QQPicCache").data:
            pic = pic_cache.get(qid)
            if not pic:
                pic = await get_qq_avatar(qid, size=100)
                pic_cache.set(qid, pic)
        else:
            pic = await get_qq_avatar(qid, size=100)
            pic_cache.set(qid, pic)
        pic_temp = crop_center_img(pic, 120, 120)

        img = Image.new("RGBA", (180, 180))
        avatar_mask_temp = avatar_mask.copy()
        mask_pic_temp = avatar_mask_temp.resize((120, 120))
        img.paste(pic_temp, (0, -5), mask_pic_temp)
    else:
        default_avatar_char_id = "1505"
        pic = await get_square_avatar(default_avatar_char_id)
        pic_temp = Image.new("RGBA", pic.size)
        pic_temp.paste(pic.resize((160, 160)), (10, 10))
        pic_temp = pic_temp.resize((160, 160))
        avatar_mask_temp = avatar_mask.copy()
        mask_pic_temp = Image.new("RGBA", avatar_mask_temp.size)
        mask_pic_temp.paste(avatar_mask_temp, (-20, -45), avatar_mask_temp)
        mask_pic_temp = mask_pic_temp.resize((160, 160))
        img = Image.new("RGBA", (180, 180))
        img.paste(pic_temp, (0, 0), mask_pic_temp)

    return img


async def draw_rank_card_template(
    title_text: str,
    details: list,
    self_uid: str,
) -> Union[str, bytes]:
    width = 1300
    text_bar_height = 130
    item_spacing = 120
    header_height = 510
    footer_height = 50
    char_list_len = len(details)
    total_height = (
        header_height + text_bar_height + item_spacing * char_list_len + footer_height
    )
    card_img = get_waves_bg(width, total_height, "bg9")
    text_bar_img = Image.new("RGBA", (width, 130), color=(0, 0, 0, 0))
    text_bar_draw = ImageDraw.Draw(text_bar_img)
    bar_bg_color = (36, 36, 41, 230)
    text_bar_draw.rounded_rectangle(
        [20, 20, width - 40, 110], radius=8, fill=bar_bg_color
    )
    accent_color = (203, 161, 95)
    text_bar_draw.rectangle([20, 20, width - 40, 26], fill=accent_color)
    text_bar_draw.text((40, 60), "排行说明", GREY, waves_font_28, "lm")
    text_bar_draw.text(
        (185, 50),
        "1. 综合所有角色的声骸分数。具备声骸套装的角色，全量刷新面板后生效。",
        SPECIAL_GOLD,
        waves_font_20,
        "lm",
    )
    text_bar_draw.text(
        (185, 85), "2. 显示前10个最强角色", SPECIAL_GOLD, waves_font_20, "lm"
    )
    temp_notes = "排行标准：以所有角色声骸分数总和（角色分数>=175）为排序的综合排名"
    text_bar_draw.text((1260, 100), temp_notes, SPECIAL_GOLD, waves_font_16, "rm")
    card_img.alpha_composite(text_bar_img, (0, header_height))
    bar = Image.open(TEXT_PATH / "bar1.png")

    # 并发获取所有用户头像
    user_avatar_tasks = [get_avatar(detail.user_id) for detail in details]
    user_avatars = await asyncio.gather(*user_avatar_tasks)

    # 收集所有需要的角色ID
    all_char_ids = set()
    for detail in details:
        if detail.char_score_details:
            sorted_chars = sorted(
                detail.char_score_details, key=lambda x: x.phantom_score, reverse=True
            )[:10]
            for char in sorted_chars:
                if char.phantom_score >= 175:
                    all_char_ids.add(char.char_id)

    # 并发获取所有角色头像
    char_avatar_tasks = [get_square_avatar(char_id) for char_id in all_char_ids]
    char_avatar_results = await asyncio.gather(*char_avatar_tasks)
    char_avatars = dict(zip(all_char_ids, char_avatar_results))

    bot_color_map = {}
    bot_color = copy.deepcopy(BOT_COLOR)

    char_mask_img = Image.open(TEXT_PATH / "char_mask.png")

    for rank_temp_index, (detail, role_avatar) in enumerate(
        zip(details, user_avatars)
    ):
        y_pos = header_height + 130 + rank_temp_index * item_spacing
        bar_bg = bar.copy()
        bar_bg.paste(role_avatar, (100, 0), role_avatar)
        bar_draw = ImageDraw.Draw(bar_bg)
        rank_id = detail.rank
        rank_color = (54, 54, 54)
        if rank_id == 1:
            rank_color = (255, 0, 0)
        elif rank_id == 2:
            rank_color = (255, 180, 0)
        elif rank_id == 3:
            rank_color = (185, 106, 217)
        info_rank = Image.new("RGBA", (50, 50), color=(255, 255, 255, 0))
        rank_draw = ImageDraw.Draw(info_rank)
        rank_draw.rounded_rectangle(
            [0, 0, 50, 50], radius=8, fill=rank_color + (int(0.9 * 255),)
        )
        rank_draw.text((25, 25), f"{rank_id}", "white", waves_font_34, "mm")
        bar_bg.alpha_composite(info_rank, (40, 35))
        bar_draw.text((210, 75), f"{detail.kuro_name}", "white", waves_font_20, "lm")
        char_count = (
            len(detail.char_score_details) if detail.char_score_details else 0
        )
        bar_draw.text((210, 45), "角色数:", (255, 255, 255), waves_font_18, "lm")
        bar_draw.text((280, 45), f"{char_count}", RED, waves_font_20, "lm")
        uid_color = "white"
        if detail.waves_id == self_uid:
            uid_color = RED
        bar_draw.text(
            (350, 40), f"特征码: {detail.waves_id}", uid_color, waves_font_20, "lm"
        )

        botName = "索拉里斯之上"
        color = (54, 54, 54)
        if botName in bot_color_map:
            color = bot_color_map[botName]
        elif bot_color:
            color = bot_color.pop(0)
            bot_color_map[botName] = color
        info_block = Image.new("RGBA", (200, 30), color=(255, 255, 255, 0))
        info_block_draw = ImageDraw.Draw(info_block)
        info_block_draw.rounded_rectangle(
            [0, 0, 200, 30], radius=6, fill=color + (int(0.6 * 255),)
        )
        info_block_draw.text((100, 15), f"{botName}", "white", waves_font_18, "mm")
        bar_bg.alpha_composite(info_block, (350, 66))

        bar_draw.text(
            (1180, 45),
            f"{detail.total_score:.1f}",
            (255, 255, 255),
            waves_font_34,
            "mm",
        )
        bar_draw.text((1180, 75), "总分", "white", waves_font_16, "mm")
        if detail.char_score_details:
            sorted_chars = sorted(
                detail.char_score_details,
                key=lambda x: x.phantom_score,
                reverse=True,
            )[:10]
            char_size = 40
            char_spacing = 45
            char_start_x = 570
            char_start_y = 35

            temp_i = 0
            for i, char in enumerate(sorted_chars):
                if char.phantom_score < 175:
                    continue

                char_x = char_start_x + temp_i * char_spacing
                temp_i += 1

                char_avatar = char_avatars.get(char.char_id)
                if not char_avatar:
                    continue

                char_avatar = char_avatar.resize((char_size, char_size))
                char_mask_resized = char_mask_img.resize((char_size, char_size))
                char_avatar_masked = Image.new("RGBA", (char_size, char_size))
                char_avatar_masked.paste(char_avatar, (0, 0), char_mask_resized)
                bar_bg.paste(
                    char_avatar_masked, (char_x, char_start_y), char_avatar_masked
                )
                score_text = f"{int(char.phantom_score)}"
                bar_draw.text(
                    (char_x + char_size // 2, char_start_y + char_size + 2),
                    score_text,
                    SPECIAL_GOLD,
                    waves_font_12,
                    "mm",
                )
            if sorted_chars:
                best_score = f"{int(sorted_chars[0].phantom_score)} "
                bar_draw.text(
                    (1080, 45), best_score, "lightgreen", waves_font_30, "mm"
                )
                bar_draw.text((1080, 75), "最高分", "white", waves_font_16, "mm")
        card_img.paste(bar_bg, (0, y_pos), bar_bg)
    title_bg = Image.open(TEXT_PATH / "totalrank.jpg")
    title_bg = title_bg.crop((0, 0, width, 500))
    icon = get_ICON()
    icon = icon.resize((128, 128))
    title_bg.paste(icon, (60, 240), icon)
    title_bg_draw = ImageDraw.Draw(title_bg)
    title_bg_draw.text((220, 290), title_text, "white", waves_font_58, "lm")
    title_char_mask_img = Image.open(TEXT_PATH / "char_mask.png").convert("RGBA")
    title_char_mask_img = title_char_mask_img.resize(
        (width, title_char_mask_img.height * width // title_char_mask_img.width)
    )
    title_char_mask_img = title_char_mask_img.crop(
        (0, title_char_mask_img.height - 500, width, title_char_mask_img.height)
    )
    char_mask_temp = Image.new("RGBA", title_char_mask_img.size, (0, 0, 0, 0))
    char_mask_temp.paste(title_bg, (0, 0), title_char_mask_img)
    card_img.paste(char_mask_temp, (0, 0), char_mask_temp)
    card_img = add_footer(card_img)
    return await convert_img(card_img)


async def _process_user_rank_data(
    user: WavesBind, bot: Bot, group_id: str
) -> Optional[TotalRankDetail]:
    if not user.uid:
        return None

    all_role_detail = await get_all_roleid_detail_info_int(user.uid)
    if not all_role_detail:
        return None

    waves_char_rank = await get_waves_char_rank(user.uid, all_role_detail)
    if not waves_char_rank:
        return None

    total_score = sum(
        c.score for c in waves_char_rank if c.score and c.score >= 175
    )
    if total_score == 0:
        return None

    char_score_details = [
        CharScoreDetail(char_id=c.roleId, phantom_score=c.score)
        for c in waves_char_rank
        if c.score
    ]

    kuro_name = user.user_id
    alias_name = user.user_id
    try:
        _, ck = await waves_api.get_ck_result(user.uid, user.user_id, bot.self_id)
        if ck:
            account_info = await waves_api.get_base_info(user.uid, ck)
            if account_info.success:
                validated_info = AccountBaseInfo.model_validate(account_info.data)
                kuro_name = validated_info.name

        sender_info = await bot.get_group_member_info(
            group_id=group_id, user_id=int(user.user_id)
        )
        alias_name = sender_info.get("card") or sender_info.get("nickname")
    except Exception as e:
        logger.warning(f"为用户 {user.user_id} 获取昵称失败: {e}")

    return TotalRankDetail(
        user_id=user.user_id,
        waves_id=user.uid,
        kuro_name=kuro_name,
        username=kuro_name,
        total_score=total_score,
        char_score_details=char_score_details,
        rank=0,
        alias_name=alias_name,
    )


async def draw_train_rank(bot: Bot, ev: Event) -> Union[str, bytes]:
    if not ev.group_id:
        return "请在群聊中使用此功能"

    users = await WavesBind.get_group_all_uid(ev.group_id)
    if not users:
        return f"群内暂无绑定信息, 请使用`{PREFIX}绑定`后使用此功能"

    tasks = [_process_user_rank_data(user, bot, ev.group_id) for user in users]
    results = await asyncio.gather(*tasks)

    rank_data: List[TotalRankDetail] = [res for res in results if res]

    if not rank_data:
        return f"群内无人刷新面板或缓存数据不全, 请使用`{PREFIX}刷新面板`后再试"

    rank_data.sort(key=lambda x: x.total_score, reverse=True)

    rank_data = rank_data[:20]

    for i, user_data in enumerate(rank_data):
        user_data.rank = i + 1

    self_uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not self_uid:
        self_uid = ""

    return await draw_rank_card_template(
        f"当前群{ev.group_id}的练度排行", rank_data, self_uid
    )
