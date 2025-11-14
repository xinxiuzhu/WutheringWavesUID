import re
from typing import Any, List

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils.at_help import ruser_id
from ..utils.hint import error_reply
from ..utils.button import WavesButton
from ..utils.database.models import WavesBind
from ..utils.error_reply import WAVES_CODE_103
from .draw_slash_query_card import draw_slash_img
from .endless_rank_cleaner import check_and_clean
from .draw_endless_rank_card import draw_endless_rank_img
from .draw_global_endless_rank_card import draw_global_endless_rank_img

sv_waves_endless_rank = SV("ww无尽排行", priority=3)
sv_waves_slash_query = SV("ww冥海查询", priority=4)
sv_waves_global_endless_rank = SV("ww无尽bot排行", priority=3)
sv_update_waves_endless = SV("ww更新全部无尽",pm=1)
sv_delete_waves_endless = SV("ww清除无尽",pm=1) 


@sv_waves_slash_query.on_command(
    (
        "冥海",
        "mh",
        "海墟",
        "冥歌海墟",
        "查询冥海",
        "查询无尽",
        "查询海墟",
        "无尽",
        "无尽深渊",
        "禁忌",
        "禁忌海域",
        "再生海域",
    ),
    block=True,
)
async def send_waves_slash_query_info(bot: Bot, ev: Event):
    user_id = ruser_id(ev)
    uid = await WavesBind.get_uid_by_game(user_id, ev.bot_id)
    if not uid:
        return await bot.send(error_reply(WAVES_CODE_103))

    im = await draw_slash_img(ev, uid, user_id)
    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        return await bot.send(im, at_sender)
    else:
        buttons: List[Any] = [
            WavesButton("冥歌海墟", "冥海"),
            WavesButton("冥海前6层", "禁忌"),
            WavesButton("冥海11层", "冥海11"),
            WavesButton("冥海12层", "无尽"),
        ]
        return await bot.send_option(im, buttons)


@sv_waves_endless_rank.on_regex("^无尽(?:排行|排名)$", block=True)
async def send_endless_rank_card(bot: Bot, ev: Event):
    await check_and_clean()  # 懒加载检查并清理
    if not ev.group_id:
        return await bot.send("请在群聊中使用")

    im = await draw_endless_rank_img(bot, ev)

    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        await bot.send(im, at_sender)
    if isinstance(im, bytes):
        await bot.send(im)


@sv_waves_global_endless_rank.on_regex(r"^无尽bot排行(\d*)$", block=True)
async def send_global_endless_rank_card(bot: Bot, ev: Event):
    await check_and_clean()  # 懒加载检查并清理
    im = await draw_global_endless_rank_img(bot, ev)
    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        await bot.send(im, at_sender)
    if isinstance(im, bytes):
        await bot.send(im)

@sv_delete_waves_endless.on_regex(r"^清除无尽(\d*)$", block=True)
async def send_global_endless_rank_card(bot: Bot, ev: Event):
    from .models import SlashSimpleRecord
    await SlashSimpleRecord.clean_simple()
    await bot.send("清理完成")

@sv_update_waves_endless.on_command(
    ("更新全部无尽",),
    block=True,
)
async def update_all_endless_data(bot: Bot, ev: Event):
    await bot.send("开始更新所有用户的无尽数据，请稍候...")

    try:
        # 导入必要的模块
        import json
        import asyncio

        from .models import SlashSimpleRecord
        from ..utils.api.requests import WavesApi
        from ..utils.database.models import WavesUser
        from ..utils.ascension.char import get_char_model
        from ..utils.char_info_utils import get_all_roleid_detail_info

        # 获取所有有效用户
        all_users = await WavesUser.get_waves_all_user()

        if not all_users:
            return await bot.send("没有找到有效的用户数据")

        await bot.send(f"找到 {len(all_users)} 个有效用户，开始获取无尽数据...")

        waves_api = WavesApi()
        success_count = 0
        error_count = 0
        no_data_count = 0

        # 限制并发数量，避免API请求过于频繁
        semaphore = asyncio.Semaphore(5)

        async def process_user_data(user):
            nonlocal success_count, error_count, no_data_count

            async with semaphore:
                try:
                    uid = user.uid
                    cookie = user.cookie
                    user_id = user.user_id
                    # 获取用户基本信息
                    account_info = await waves_api.get_base_info(uid, cookie)
                    user_name = ""
                    if isinstance(account_info, tuple) and account_info[0]:
                        account_data = account_info[1]
                        if isinstance(account_data, dict):
                            user_name = account_data.get("name", "")

                    # 获取无尽数据
                    slash_data = await waves_api.get_slash_detail(uid, cookie)

                    if isinstance(slash_data, str):
                        # API返回错误信息
                        error_count += 1
                        return

                    if (not isinstance(slash_data, dict) or slash_data.get("code") != 200):
                        error_count += 1
                        return

                    data = slash_data.get("data")
                    if not data or not data.get("isUnlock", False):
                        no_data_count += 1
                        return

                    difficulty_list = data.get("difficultyList", [])
                    if not difficulty_list:
                        no_data_count += 1
                        return

                    # 获取角色详细信息
                    role_detail_info_map = await get_all_roleid_detail_info(uid)
                    role_detail_info_map = (
                        role_detail_info_map if role_detail_info_map else {}
                    )

                    # 处理每个难度的挑战数据
                    for difficulty in difficulty_list:
                        challenge_list = difficulty.get("challengeList", [])
                        for challenge in challenge_list:
                            challenge_id = challenge.get("challengeId")
                            if challenge_id != 12:
                                continue
                            challenge_name = challenge.get("challengeName")
                            rank = challenge.get("rank", "")
                            score = challenge.get("score", 0)
                            half_list = challenge.get("halfList", [])

                            if challenge_id and challenge_name:
                                # 构建包含详细角色信息的halfList
                                detailed_half_list = []
                                for half in half_list:
                                    detailed_roles = []
                                    role_list = half.get("roleList", [])

                                    for role in role_list:
                                        role_id = role.get("roleId")
                                        if not role_id:
                                            continue
                                        char_model = get_char_model(role_id)
                                        role_detail = None
                                        if (role_detail_info_map and str(role_id) in role_detail_info_map):
                                            role_detail = role_detail_info_map[str(role_id)]
                                        # 构建详细角色信息
                                        detailed_role = {
                                            "roleId": role_id,
                                            "iconUrl": role.get("iconUrl", ""),
                                            "roleName": (char_model.name if char_model else ""),
                                            "starLevel": (char_model.starLevel if char_model else 0),
                                            "level": (role_detail.level if role_detail else 0),
                                            "chain": (role_detail.get_chain_num() if role_detail else 0),
                                        }
                                        detailed_roles.append(detailed_role)
                                    # 构建详细的half信息
                                    detailed_half = {
                                        "buffDescription": half.get("buffDescription", ""),
                                        "buffIcon": half.get("buffIcon", ""),
                                        "buffName": half.get("buffName", ""),
                                        "buffQuality": half.get("buffQuality", 0),
                                        "roleList": detailed_roles,
                                        "score": half.get("score", 0),
                                    }
                                    detailed_half_list.append(detailed_half)

                                # 保存到数据库
                                payload = {
                                    "wavesId": uid,
                                    "name": user_name,
                                    "challengeId": challenge_id,
                                    "challengeName": challenge_name,
                                    "rank": rank,
                                    "score": score,
                                    "halfList": detailed_half_list,
                                }

                                await SlashSimpleRecord.save_simple_record(
                                    payload=payload, user_id=user_id
                                )

                    success_count += 1

                except Exception as e:
                    error_count += 1
                    print(f"处理用户 {user.uid} 数据时出错: {e}")

        # 并发处理所有用户数据
        tasks = [process_user_data(user) for user in all_users]
        await asyncio.gather(*tasks, return_exceptions=True)

        # 发送结果报告
        result_message = f"无尽数据更新完成！\n"
        result_message += f"成功处理: {success_count} 个用户\n"
        result_message += f"无数据: {no_data_count} 个用户\n"
        result_message += f"处理失败: {error_count} 个用户\n"
        result_message += f"总计: {len(all_users)} 个用户"

        await bot.send(result_message)

    except Exception as e:
        error_msg = f"更新无尽数据时发生错误: {str(e)}"
        print(error_msg)
        await bot.send(error_msg)
