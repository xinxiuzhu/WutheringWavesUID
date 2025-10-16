import sys
from pathlib import Path

# 将插件根目录添加到系统路径，以便导入 damage.py
plugin_root = Path(__file__).parent
sys.path.append(str(plugin_root))

from utils.damage.damage import DamageAttribute

def calculate_damage_distribution():
    """
    计算嘉贝莉娜的伤害分布
    """
    # 1. 设定标准面板 (根据您提供的最新数据)
    # 假设角色和武器的基础攻击力之和为 800 (这是一个估算值，但因为它对两类伤害的影响是相同的，所以不影响最终的比例)
    base_atk = 800
    # 面板总攻击力
    total_atk = 1404
    # 计算出攻击力%和固定攻击力
    atk_percent = (total_atk - base_atk) / base_atk - 1
    atk_flat = 0 # 假设固定攻击力主要来自声骸，这里暂时简化

    panel = {
        "char_atk": base_atk,
        "weapon_atk": 0,
        "atk_percent": atk_percent,
        "atk_flat": atk_flat,
        "crit_rate": 0.607,
        "crit_dmg": 1 + 0.762, # 伤害公式需要的是1+爆伤
        "dmg_bonus": 0.40, # 热熔伤害加成
        "character_level": 90,
        "enemy_level": 90,
    }

    # 2. 精确汇总伤害倍率 (根据您提供的所有技能截图)
    # 假设一个完整的输出循环
    
    # 重击伤害倍率汇总
    heavy_hit_multipliers = {
        # 普攻 (被归类为重击的部分)
        "普攻二段": 0.2631 + 0.2631 + 0.7891,
        "普攻三段": 0.2860 + 0.2860 + 0.4289 + 0.4289,
        # 共鸣技能E (全部为重击)
        "共鸣技能-追近": 0.1074 + 0.2504,
        "共鸣技能-恶翼扬升": 0.5157 + 0.5157,
        # 共鸣回路 (大部分为重击)
        "炽天猎杀一段": 0.5899,
        "炽天猎杀二段": 0.2784 + 0.8351,
        "炽天猎杀三段": 0.2432 + 1.7021,
        "炼羽裁决一段": 0.5922 + 0.9922,
        "炼羽裁决二段": 0.3636 + 1.2377,
        "空中-枪弹暴雨下落": 1.4315,
        "闪避反击-罪业当涤": 1.0795 + 2.5117,
    }

    # 声骸技能伤害倍率汇总
    echo_skill_multipliers = {
        # 普攻 (被归类为声骸伤害的部分)
        "普攻四段": 1.7786,
        # 共鸣解放R
        "共鸣解放-炼净": 1.1090 + (0.9074 * 11),
        # 共鸣回路 (高倍率收尾部分)
        "炽天猎杀四段": 2.2416,
        "炽天猎杀五段": 6.728 + 1.5699,
        "炼羽裁决三段": 1.7528 + 3.09,
    }

    # 3. 计算各类伤害总值
    total_heavy_damage = 0
    total_echo_damage = 0

    print("--- 重击伤害计算详情 ---")
    for name, multi in heavy_hit_multipliers.items():
        # 创建独立的计算器实例
        attr = DamageAttribute(**panel)
        attr.set_skill_multi(multi)
        # 额外加上17.2%的重击伤害加成
        attr.add_dmg_bonus(0.172)
        damage = attr.calculate_expected_damage()
        total_heavy_damage += damage
        print(f"{name}: 倍率={multi:.2f}, 期望伤害={damage:,.0f}")

    print("\n--- 声骸技能伤害计算详情 ---")
    for name, multi in echo_skill_multipliers.items():
        # 创建独立的计算器实例
        attr = DamageAttribute(**panel)
        attr.set_skill_multi(multi)
        # 声骸伤害不吃重击加成
        damage = attr.calculate_expected_damage()
        total_echo_damage += damage
        print(f"{name}: 倍率={multi:.2f}, 期望伤害={damage:,.0f}")

    # 4. 得出最终占比
    total_damage = total_heavy_damage + total_echo_damage
    heavy_ratio = total_heavy_damage / total_damage
    echo_ratio = total_echo_damage / total_damage

    print("\n======================================")
    print(f"伤害计算标准面板: {panel}")
    print("======================================")
    print(f"重击伤害总值: {total_heavy_damage:,.0f}")
    print(f"声骸技能伤害总值: {total_echo_damage:,.0f}")
    print("--------------------------------------")
    print(f"最终伤害占比:")
    print(f"  重击伤害: {heavy_ratio:.2%}")
    print(f"  声骸技能伤害: {echo_ratio:.2%}")
    print("======================================")
    print("\n结论: 建议将 skill_weight 设置为 [0, {:.2f}, 0, 0]".format(heavy_ratio))


if __name__ == "__main__":
    calculate_damage_distribution()