"""
Bootstrap case loader — 从 Codex 确认的 25 个种子用例创建 EvalCase 记录。

用法：
    cd eval-service
    PYTHONPATH=. python scripts/load_bootstrap_cases.py

运行前确保：
    1. .env 已配置 DATABASE_URL
    2. alembic upgrade head 已执行
    3. #20-25 号用例的 T+10 方向已人工核验（见脚本底部注释）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import uuid
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models import EvalCase

# ── Bootstrap 用例（来自 2026-04-01-bootstrap-case-selection-prompt.md）────────

BOOTSTRAP_CASES = [
    {
        "no": 1,
        "scene": "外资回流·单边上涨",
        "ticker": "601398.SH",
        "market": "A",
        "key_date": "2025-01-15",
        "t10_direction": "up",
        "input_narrative": "分析工商银行近期走势。特朗普就职前夕，外资预期降息周期延续，人民币汇率企稳，北向资金近期连续净流入大金融板块，请研判传统机构与海外资金的配置逻辑以及后续博弈方向。",
        "note": "外资回流信号典型，结果清晰",
    },
    {
        "no": 2,
        "scene": "反直觉·事件驱动",
        "ticker": "002230.SZ",
        "market": "A",
        "key_date": "2025-01-27",
        "t10_direction": "down",
        "input_narrative": "DeepSeek R1 正式发布，国内 AI 能力得到广泛认可，市场看多国内 AI 应用股。请分析科大讯飞当前处境，结合各参与者视角评估多空博弈方向。",
        "note": "反直觉：AI 浪潮利好预期 vs 开源冲击商业模式",
    },
    {
        "no": 3,
        "scene": "财报驱动·单边上涨",
        "ticker": "9988.HK",
        "market": "HK",
        "key_date": "2025-02-13",
        "t10_direction": "up",
        "input_narrative": "阿里巴巴 FY25Q3 财报即将发布，市场预期云计算增速回升。请对各参与者推演阿里财报后博弈走向，重点关注传统机构与海外资金的分歧。",
        "note": "事件+基本面双重驱动，结果明确",
    },
    {
        "no": 4,
        "scene": "单边下跌",
        "ticker": "6098.HK",
        "market": "HK",
        "key_date": "2025-02-10",
        "t10_direction": "down",
        "input_narrative": "碧桂园服务近期随地产链持续承压，母公司重组进展缓慢。请分析各参与者对物管板块的当前定价逻辑与风险判断。",
        "note": "行业性系统下跌，适合测试负面传导链判断",
    },
    {
        "no": 5,
        "scene": "单边上涨",
        "ticker": "1810.HK",
        "market": "HK",
        "key_date": "2025-02-25",
        "t10_direction": "up",
        "input_narrative": "小米 SU7 销量持续创新高，汽车业务盈利拐点预期强化，港股春节后整体回暖。请推演各参与者对小米当前的博弈判断。",
        "note": "多因子共振，信号明确",
    },
    {
        "no": 6,
        "scene": "政策驱动·事件驱动",
        "ticker": "002594.SZ",
        "market": "A",
        "key_date": "2025-03-05",
        "t10_direction": "up",
        "input_narrative": "两会政府工作报告今日发布，扩大新能源汽车消费政策明确落地。请分析比亚迪作为行业龙头的受益路径，推演各参与者在政策催化下的博弈方向。",
        "note": "政策落地日测试",
    },
    {
        "no": 7,
        "scene": "政策驱动·事件驱动",
        "ticker": "600760.SH",
        "market": "A",
        "key_date": "2025-03-07",
        "t10_direction": "up",
        "input_narrative": "两会国防预算增幅超过市场预期，军工板块受到催化。请分析中航成飞当前博弈格局，重点关注游资与机构的分歧。",
        "note": "超预期政策+游资介入",
    },
    {
        "no": 8,
        "scene": "财报驱动·单边上涨",
        "ticker": "0700.HK",
        "market": "HK",
        "key_date": "2025-03-19",
        "t10_direction": "up",
        "input_narrative": "腾讯 FY2024 年报发布，利润超预期，同时宣布混元大模型 AI 战略升级。港股科技整体估值修复趋势中，请推演各参与者对腾讯的博弈判断。",
        "note": "利润超预期+AI战略催化",
    },
    {
        "no": 9,
        "scene": "反直觉·事件驱动",
        "ticker": "6666.HK",
        "market": "HK",
        "key_date": "2025-04-15",
        "t10_direction": "down",
        "input_narrative": "监管近期出台地产支持措施，市场预期物管板块作为地产后周期受益。请分析恒大物业当前处境，推演各参与者在政策出台后的博弈反应。",
        "note": "反直觉：利好出尽+自身债务拖累",
    },
    {
        "no": 10,
        "scene": "单边下跌·事件驱动",
        "ticker": "0981.HK",
        "market": "HK",
        "key_date": "2025-04-10",
        "t10_direction": "down",
        "input_narrative": "美国宣布新一轮半导体出口管制扩围，中芯国际先进制程产能利用率预期受直接冲击。请推演各参与者对中芯国际的风险判断与博弈方向。",
        "note": "外部政策驱动，信号明确",
    },
    {
        "no": 11,
        "scene": "财报驱动·单边上涨",
        "ticker": "300750.SZ",
        "market": "A",
        "key_date": "2025-04-28",
        "t10_direction": "up",
        "input_narrative": "宁德时代 Q1 财报超预期，海外订单放量叠加碳酸锂成本下降，毛利率明显改善。请推演各参与者对宁德时代基本面拐点的判断分歧。",
        "note": "基本面拐点确认，结果清晰",
    },
    {
        "no": 12,
        "scene": "高波动震荡",
        "ticker": "1211.HK",
        "market": "HK",
        "key_date": "2025-05-12",
        "t10_direction": "flat",
        "input_narrative": "中美贸易谈判处于关键窗口，汽车出口关税走向高度不确定。比亚迪 H 股近期日内振幅极大。请推演各参与者在当前不确定性下的多空博弈。",
        "note": "测试 agent 对不确定性的刻画能力",
    },
    {
        "no": 13,
        "scene": "反直觉·财报驱动",
        "ticker": "PDD",
        "market": "US",
        "key_date": "2025-05-26",
        "t10_direction": "down",
        "input_narrative": "拼多多 Q1 营收大幅超出市场预期，但管理层在业绩会上给出保守前瞻指引，市场担忧增速见顶。请推演各参与者对拼多多当前估值的博弈判断。",
        "note": "财报好但指引悲观，典型反直觉",
    },
    {
        "no": 14,
        "scene": "单边上涨",
        "ticker": "601318.SH",
        "market": "A",
        "key_date": "2025-05-21",
        "t10_direction": "up",
        "input_narrative": "中国平安年报后新业务价值增速改善，股息率提升至具备吸引力水平。市场震荡背景下，保险板块作为防御性资产吸引增量配置资金。请推演各参与者的博弈判断。",
        "note": "防御性资产估值修复",
    },
    {
        "no": 15,
        "scene": "政策驱动·单边上涨",
        "ticker": "6862.HK",
        "market": "HK",
        "key_date": "2025-06-10",
        "t10_direction": "up",
        "input_narrative": "国内消费刺激政策扩围，餐饮补贴方案落地，港股消费板块近期南向资金持续流入。请分析海底捞当前博弈格局，推演各参与者的判断。",
        "note": "政策+资金双驱动",
    },
    {
        "no": 16,
        "scene": "单边上涨·外资驱动",
        "ticker": "3690.HK",
        "market": "HK",
        "key_date": "2025-06-15",
        "t10_direction": "up",
        "input_narrative": "美团外卖业务利润率持续改善，南向资金近期大幅净流入，叠加 AI 本地生活应用预期升温。请推演各参与者对美团当前的博弈判断。",
        "note": "多重驱动，趋势清晰",
    },
    {
        "no": 17,
        "scene": "单边下跌·事件驱动",
        "ticker": "9618.HK",
        "market": "HK",
        "key_date": "2025-07-10",
        "t10_direction": "down",
        "input_narrative": "618 大促数据发布，京东 GMV 表现低于市场预期，消费疲软信号叠加竞争加剧。请推演各参与者对京东当前基本面的博弈判断。",
        "note": "大促数据低于预期，事后结果明确",
    },
    {
        "no": 18,
        "scene": "财报驱动·震荡偏涨",
        "ticker": "600941.SH",
        "market": "A",
        "key_date": "2025-07-25",
        "t10_direction": "up",
        "input_narrative": "中国移动中期业绩发布，5G 用户 ARPU 值改善，AI 算力基础设施投入计划确认。请分析各参与者对中国移动防御性成长逻辑的判断分歧。",
        "note": "防御性成长，机构配置稳定",
    },
    {
        "no": 19,
        "scene": "高波动震荡",
        "ticker": "603501.SH",
        "market": "A",
        "key_date": "2025-08-05",
        "t10_direction": "flat",
        "input_narrative": "全球 AI 泡沫担忧升温，半导体板块估值高企但基本面分化。韦尔股份作为 CIS 传感器龙头处于估值压力与需求回升的拉锯中。请推演各参与者的多空博弈。",
        "note": "板块高波动，适合测试多空博弈刻画",
    },
    # ── ⚠️ #20-25 需人工核验 T+10 真实方向后再入库 ───────────────────────────
    {
        "no": 20,
        "scene": "反直觉·单边下跌",
        "ticker": "600519.SH",
        "market": "A",
        "key_date": "2025-09-01",
        "t10_direction": "down",  # ⚠️ 需核验
        "input_narrative": "双节旺季临近，茅台经销商备货逻辑清晰，市场普遍看多。但渠道反馈批价有所走软，请推演各参与者对茅台旺季逻辑的博弈判断，重点关注批价与股价的关系。",
        "note": "⚠️ 需核验 — 旺季不旺反直觉案例",
    },
    {
        "no": 21,
        "scene": "外资/南向资金驱动",
        "ticker": "0005.HK",
        "market": "HK",
        "key_date": "2025-10-15",
        "t10_direction": "up",  # ⚠️ 需核验
        "input_narrative": "美联储降息周期确认，港股高息金融股对南向资金吸引力提升，汇丰控股近期出现南向大额净流入。请推演各参与者对汇丰当前配置逻辑的博弈判断。",
        "note": "⚠️ 需核验 — 资金面主导行情",
    },
    {
        "no": 22,
        "scene": "高波动震荡",
        "ticker": "000001.SZ",
        "market": "A",
        "key_date": "2025-10-08",
        "t10_direction": "flat",  # ⚠️ 需核验
        "input_narrative": "国庆长假期间海外市场大幅波动，今日 A 股节后首个交易日开盘，多空博弈激烈。请推演各参与者在假期外部冲击下的应对博弈，判断节后走势方向。",
        "note": "⚠️ 需核验 — 假期效应标准测试节点",
    },
    {
        "no": 23,
        "scene": "政策驱动·单边上涨",
        "ticker": "600089.SH",
        "market": "A",
        "key_date": "2025-11-05",
        "t10_direction": "up",  # ⚠️ 需核验
        "input_narrative": "新型电力系统与储能补贴政策新规今日落地，电力设备板块迎来政策催化。请推演各参与者对特变电工作为龙头的受益路径判断与博弈方向。",
        "note": "⚠️ 需核验 — 政策传导链",
    },
    {
        "no": 24,
        "scene": "主题/赛道驱动",
        "ticker": "300124.SZ",
        "market": "A",
        "key_date": "2025-11-25",
        "t10_direction": "up",  # ⚠️ 需核验
        "input_narrative": "特斯拉 Optimus 量产消息持续发酵，人形机器人产业化进入加速期，国内核心零部件龙头估值重塑预期升温。请推演各参与者对汇川技术的博弈判断，重点关注主题驱动与基本面的分歧。",
        "note": "⚠️ 需核验 — 主题先于基本面",
    },
    {
        "no": 25,
        "scene": "主题/赛道驱动·高波动",
        "ticker": "688256.SH",
        "market": "A",
        "key_date": "2026-01-15",
        "t10_direction": "up",  # ⚠️ 需核验
        "input_narrative": "春节前 AI 算力需求预期持续高涨，DeepSeek 新版本发布窗口临近，寒武纪处于高估值高波动状态。请推演各参与者在极端情绪下对寒武纪的博弈判断，评估泡沫风险与趋势延续的可能性。",
        "note": "⚠️ 需核验 — 极端情绪下的稳健性测试",
    },
]


def load(dry_run: bool = False, skip_unverified: bool = False) -> None:
    """
    Args:
        dry_run: 只打印不写库
        skip_unverified: 跳过 #20-25（⚠️ 需核验的用例）
    """
    db = SessionLocal()
    created = 0
    skipped = 0

    try:
        for case_def in BOOTSTRAP_CASES:
            no = case_def["no"]

            if skip_unverified and no >= 20:
                print(f"  [SKIP] #{no:02d} {case_def['ticker']} — 需人工核验")
                skipped += 1
                continue

            run_id = f"bootstrap-{case_def['ticker']}-{case_def['key_date']}"
            existing = db.query(EvalCase).filter(EvalCase.run_id == run_id).first()
            if existing:
                print(
                    f"  [EXISTS] #{no:02d} {case_def['ticker']} {case_def['key_date']}"
                )
                skipped += 1
                continue

            key_date = datetime.strptime(case_def["key_date"], "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )

            if not dry_run:
                record = EvalCase(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    ticker=case_def["ticker"],
                    market=case_def["market"],
                    run_timestamp=key_date,
                    input_narrative=case_def["input_narrative"],
                    agent_snapshots=[],  # 空快照，等重跑 sandbox 后填入
                    resolution_snapshot=None,
                    status="pending",
                    source="bootstrap",
                )
                db.add(record)

            print(
                f"  [{'DRY' if dry_run else 'OK'}] #{no:02d} {case_def['ticker']} {case_def['key_date']} — {case_def['scene']}"
            )
            created += 1

        if not dry_run:
            db.commit()

    finally:
        db.close()

    print(f"\n完成：创建 {created} 条，跳过 {skipped} 条。")
    if not skip_unverified:
        print("⚠️  #20-25 未经核验即入库，请在评测前人工确认 T+10 真实方向。")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    parser.add_argument(
        "--skip-unverified", action="store_true", help="跳过 #20-25 需核验用例"
    )
    args = parser.parse_args()

    print(f"Bootstrap 用例加载 {'(dry run)' if args.dry_run else ''}\n")
    load(dry_run=args.dry_run, skip_unverified=args.skip_unverified)
