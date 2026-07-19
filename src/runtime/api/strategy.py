"""控制台策略调参 API——「按效果调参」的对外接口

将策略旋钮（current）、效果信号（effect）、调参建议（suggestions）聚合成
控制台一页视图；并提供手动调参与调参审计轨迹查询。

对应策划方案 V1-4「控制台策略调整·按效果调参」
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.runtime.core.strategy_tuner import tuner

router = APIRouter(prefix="/strategy", tags=["strategy"])


class TuneRequest(BaseModel):
    agent: str
    param: str
    value: float | int
    reason: str = ""


@router.get("")
async def strategy_panel():
    """控制台一页视图：当前旋钮 + 效果信号 + 调参建议"""
    return {
        "current": tuner.current(),
        "effect_signals": tuner.effect_signals(),
        "suggestions": tuner.suggest()["suggestions"],
    }


@router.get("/suggestions")
async def strategy_suggestions():
    """仅返回效果驱动的调参建议"""
    return tuner.suggest()


@router.post("/tune")
async def tune_strategy(req: TuneRequest):
    """控制台手动调参：夹紧后写入运行时授权边界，并记录审计轨迹"""
    try:
        result = tuner.apply(req.agent, req.param, req.value, req.reason, basis="console")
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/history")
async def strategy_history():
    """调参审计轨迹"""
    return {"history": tuner.history(), "total": len(tuner.history())}
