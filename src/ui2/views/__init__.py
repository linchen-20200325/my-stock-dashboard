"""四頁 view：只吃 PageVM 渲染（⛔ 取數／判態／聚合動作）。"""
from src.ui2.views import hold, market, me, target  # noqa: F401
from shared.ui2_contract.pages import P4_HOLD, P4_ME, P4_MARKET, P4_TARGET

VIEWS = {
    P4_MARKET: market.render,
    P4_TARGET: target.render,
    P4_HOLD: hold.render,
    P4_ME: me.render,
}
