"""电压质量评估服务"""
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class VoltageQuality:
    """电压质量评估结果"""
    score: int  # 0-100
    grade: str  # A/B/C/D/F
    label: str  # 优秀/良好/一般/较差/危险
    deviation_percent: float  # 偏差百分比
    in_safe_range: bool  # 是否在安全区间
    issues: list  # 问题列表
    recommendation: str  # 建议


def assess_voltage_quality(
    input_voltage: Optional[float],
    input_voltage_nominal: Optional[float],
    input_voltage_min: Optional[float],
    input_voltage_max: Optional[float],
    input_transfer_low: Optional[float],
    input_transfer_high: Optional[float],
    status_flags: list,
) -> Optional[VoltageQuality]:
    """
    评估电压质量

    评分维度：
    1. 偏差度 (40分)：当前电压与额定电压的偏差
    2. 稳定性 (30分)：波动范围
    3. 安全性 (30分)：是否接近切换阈值
    """
    # Zero input voltage is expected during an outage. It must not break UPS telemetry.
    if (input_voltage is None or input_voltage <= 0
            or input_voltage_nominal is None or input_voltage_nominal <= 0):
        return None

    issues = []
    score = 100

    # 1. 偏差度评分
    deviation = abs(input_voltage - input_voltage_nominal) / input_voltage_nominal * 100
    deviation_percent = round(deviation, 1)

    if deviation > 15:
        score -= 40
        issues.append(f"电压偏差过大：{deviation_percent}%")
    elif deviation > 10:
        score -= 25
        issues.append(f"电压偏差较大：{deviation_percent}%")
    elif deviation > 5:
        score -= 10
        issues.append(f"电压轻微偏差：{deviation_percent}%")

    # 2. 稳定性评分
    if input_voltage_min and input_voltage_max:
        range_percent = (input_voltage_max - input_voltage_min) / input_voltage_nominal * 100
        if range_percent > 20:
            score -= 30
            issues.append(f"电压波动剧烈：{input_voltage_min}-{input_voltage_max}V")
        elif range_percent > 10:
            score -= 20
            issues.append(f"电压波动较大：{input_voltage_min}-{input_voltage_max}V")
        elif range_percent > 5:
            score -= 10

    # 3. 安全性评分
    in_safe_range = True
    if input_transfer_low and input_transfer_high:
        low_margin = (input_voltage - input_transfer_low) / input_transfer_low * 100
        high_margin = (input_transfer_high - input_voltage) / input_voltage * 100
        min_margin = min(low_margin, high_margin)

        if min_margin < 5:
            score -= 30
            in_safe_range = False
            issues.append("电压接近切换阈值！")
        elif min_margin < 10:
            score -= 15
            issues.append("电压接近切换阈值")
        elif min_margin < 20:
            score -= 5

    # 4. AVR 状态扣分
    flags = [f.upper() for f in status_flags]
    if "BOOST" in flags:
        score -= 10
        issues.append("AVR 升压激活")
    elif "TRIM" in flags:
        score -= 10
        issues.append("AVR 降压激活")

    # 确保分数在 0-100 范围
    score = max(0, min(100, score))

    # 等级评定
    if score >= 90:
        grade, label = "A", "优秀"
    elif score >= 75:
        grade, label = "B", "良好"
    elif score >= 60:
        grade, label = "C", "一般"
    elif score >= 40:
        grade, label = "D", "较差"
    else:
        grade, label = "F", "危险"

    # 生成建议
    if not issues:
        recommendation = "电压质量良好，无需处理"
    elif score >= 60:
        recommendation = "建议关注电压波动情况"
    else:
        recommendation = "建议检查电源线路或使用稳压器"

    return VoltageQuality(
        score=score,
        grade=grade,
        label=label,
        deviation_percent=deviation_percent,
        in_safe_range=in_safe_range,
        issues=issues,
        recommendation=recommendation,
    )
