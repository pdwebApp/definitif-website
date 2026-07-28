from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


def _to_float(v: Any, default: float = 0.0) -> float:
    if v is None or v == "":
        return default
    try:
        return float(v)
    except Exception:
        return default


def _to_int(v: Any, default: int = 0) -> int:
    if v is None or v == "":
        return default
    try:
        return int(v)
    except Exception:
        return default


def _to_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    return str(v)


@dataclass
class KPI:
    l: str = ""
    user_type: str = ""
    pv: float = 0.0
    inv: float = 0.0
    ugl: float = 0.0
    rgl: float = 0.0
    ret: float = 0.0
    x1: float = 0.0
    x2: float = 0.0
    val_date: str = ""
    nav_requested_date: str = ""
    nav_latest_available: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KPI":
        data = data or {}
        return cls(
            l=_to_str(data.get("l")),
            user_type = _to_str(data.get("user_type")).title(),
            pv=_to_float(data.get("pv")),
            inv=_to_float(data.get("inv")),
            ugl=_to_float(data.get("ugl")),
            rgl=_to_float(data.get("rgl")),
            ret=_to_float(data.get("ret")),
            x1=_to_float(data.get("x1")),
            x2=_to_float(data.get("x2")),
            val_date=_to_str(data.get("val_date")),
            nav_requested_date=_to_str(data.get("nav_requested_date")),
            nav_latest_available=_to_str(data.get("nav_latest_available")),
        )


@dataclass
class Holding:
    p: str = ""
    folio_no: str = ""
    isin: str = ""
    fund_display: str = ""
    g: str = ""
    c: str = ""
    buy_date: str = ""
    buy_nav: float = 0.0
    units_remaining: float = 0.0
    cost_value: float = 0.0
    current_nav: float = 0.0
    nav_as_of: str = ""
    cv: float = 0.0
    ugl: float = 0.0
    unrealised_gl_pct: float = 0.0
    holding_days: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Holding":
        data = data or {}
        return cls(
            p=_to_str(data.get("p")),
            folio_no=_to_str(data.get("folio_no")),
            isin=_to_str(data.get("isin")),
            fund_display=_to_str(data.get("fund_display")),
            g=_to_str(data.get("g")),
            c=_to_str(data.get("c")),
            buy_date=_to_str(data.get("buy_date")),
            buy_nav=_to_float(data.get("buy_nav")),
            units_remaining=_to_float(data.get("units_remaining")),
            cost_value=_to_float(data.get("cost_value")),
            current_nav=_to_float(data.get("current_nav")),
            nav_as_of=_to_str(data.get("nav_as_of")),
            cv=_to_float(data.get("cv")),
            ugl=_to_float(data.get("ugl")),
            unrealised_gl_pct=_to_float(data.get("unrealised_gl_pct")),
            holding_days=_to_int(data.get("holding_days")),
        )

_SOURCE_KEY_MAP = {
    "asset_alloc": "assetAlloc",
    "market_cap": "marketCap",
    "strategy_alloc": "strategyAlloc",
    "category_alloc": "categoryAlloc",
    "pan_summary": "panSummary",
    "perf_isin": "perfIsin",
    "perf_strat": "perfStrat",
    "profitbook": "profitBook",
    "profitbook_fy": "profitBookFY",
    "profitbook_strategy": "profitBookStrategy",
    "profitbook_category": "profitBookCategory",
    "profitbook_transactions": "profitBookTransactions",
}

def _remap_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {_SOURCE_KEY_MAP.get(k, k): _remap_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_remap_keys(v) for v in obj]
    return obj

@dataclass
class ClientReportData:
    kpi: KPI = field(default_factory=KPI)
    holdings: List[Holding] = field(default_factory=list)
    asset_alloc: List[AllocationItem] = field(default_factory=list)
    market_cap: List[AllocationItem] = field(default_factory=list)
    strategy_alloc: List[AllocationItem] = field(default_factory=list)
    category_alloc: List[CategoryAllocationItem] = field(default_factory=list)
    pan_summary: List[PanSummaryItem] = field(default_factory=list)
    perf_isin: List[PerformanceItem] = field(default_factory=list)
    perf_strat: List[PerformanceItem] = field(default_factory=list)
    profitbook: List[ProfitBookItem] = field(default_factory=list)
    profitbook_fy: List[ProfitBookFYItem] = field(default_factory=list)
    profitbook_strategy: List[ProfitBookStrategyItem] = field(default_factory=list)
    profitbook_category: List[ProfitBookCategoryItem] = field(default_factory=list)
    profitbook_transactions: List[ProfitBookItem] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClientReportData":
        data = data or {}
        return cls(
            kpi=KPI.from_dict(data.get("kpi") or {}),
            holdings=[Holding.from_dict(x) for x in (data.get("holdings") or [])],
            asset_alloc=[AllocationItem.from_dict(x) for x in (data.get("assetAlloc") or [])],
            market_cap=[AllocationItem.from_dict(x) for x in (data.get("marketCap") or [])],
            strategy_alloc=[AllocationItem.from_dict(x) for x in (data.get("strategyAlloc") or [])],
            category_alloc=[CategoryAllocationItem.from_dict(x) for x in (data.get("categoryAlloc") or [])],
            pan_summary=[PanSummaryItem.from_dict(x) for x in (data.get("panSummary") or [])],
            perf_isin=[PerformanceItem.from_dict(x) for x in (data.get("perfIsin") or [])],
            perf_strat=[PerformanceItem.from_dict(x) for x in (data.get("perfStrat") or [])],
            profitbook=[ProfitBookItem.from_dict(x) for x in (data.get("profitBook") or [])],
            profitbook_fy=[ProfitBookFYItem.from_dict(x) for x in (data.get("profitBookFY") or [])],
            profitbook_strategy=[ProfitBookStrategyItem.from_dict(x) for x in (data.get("profitBookStrategy") or [])],
            profitbook_category=[ProfitBookCategoryItem.from_dict(x) for x in (data.get("profitBookCategory") or [])],
            profitbook_transactions=[ProfitBookItem.from_dict(x) for x in (data.get("profitBookTransactions") or [])],
        )

    @classmethod
    def _remap_source_keys(cls, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {cls._SOURCE_KEY_MAP.get(k, k): cls._remap_source_keys(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [cls._remap_source_keys(v) for v in obj]
        return obj

    def to_dict(self) -> Dict[str, Any]:
        return self._remap_source_keys(asdict(self))

@dataclass
class AllocationItem:
    l: str = ""
    v: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AllocationItem":
        data = data or {}
        return cls(
            l=_to_str(data.get("l")),
            v=_to_float(data.get("v")),
        )


@dataclass
class CategoryAllocationItem:
    g: str = ""
    c: str = ""
    cv: float = 0.0
    w: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CategoryAllocationItem":
        data = data or {}
        return cls(
            g=_to_str(data.get("g")),
            c=_to_str(data.get("c")),
            cv=_to_float(data.get("cv")),
            w=_to_float(data.get("w")),
        )

@dataclass
class PanSummaryItem:
    p: str = ""
    inv: float = 0.0
    cv: float = 0.0
    ugl: float = 0.0
    rgl: float = 0.0
    ret: float = 0.0
    x1: float = 0.0
    x2: float = 0.0
    n: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PanSummaryItem":
        data = data or {}
        return cls(
            p=_to_str(data.get("p")),
            inv=_to_float(data.get("inv")),
            cv=_to_float(data.get("cv")),
            ugl=_to_float(data.get("ugl")),
            rgl=_to_float(data.get("rgl")),
            ret=_to_float(data.get("ret")),
            x1=_to_float(data.get("x1")),
            x2=_to_float(data.get("x2")),
            n=_to_str(data.get("n")),
        )


@dataclass
class PerformanceItem:
    p: str = ""
    isin: str = ""
    fund_display: str = ""
    g: str = ""
    c: str = ""
    inv: float = 0.0
    cv: float = 0.0
    ugl: float = 0.0
    ret: float = 0.0
    x1: Optional[float] = None
    x2: Optional[float] = None
    w: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerformanceItem":
        data = data or {}
        return cls(
            p=_to_str(data.get("p")),
            isin=_to_str(data.get("isin")),
            fund_display=_to_str(data.get("fund_display")),
            g=_to_str(data.get("g")),
            c=_to_str(data.get("c")),
            inv=_to_float(data.get("inv")),
            cv=_to_float(data.get("cv")),
            ugl=_to_float(data.get("ugl")),
            ret=_to_float(data.get("ret")),
            x1=None if data.get("x1") is None else _to_float(data.get("x1")),
            x2=None if data.get("x2") is None else _to_float(data.get("x2")),
            w=None if data.get("w") is None else _to_float(data.get("w")),
        )

@dataclass
class ProfitBookItem:
    p: str = ""
    n: str = ""
    financial_year: str = ""
    g: str = ""
    fund_display: str = ""
    folio_no: str = ""
    dop: str = ""
    dos: str = ""
    total_units: float = 0.0
    total_cost: float = 0.0
    total_proceeds: float = 0.0
    total_gain_loss: float = 0.0
    gain_loss_pct: float = 0.0
    gain_type: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfitBookItem":
        data = data or {}
        return cls(
            p=_to_str(data.get("p")),
            n=_to_str(data.get("n")),
            financial_year=_to_str(data.get("financial_year")),
            g=_to_str(data.get("g")),
            fund_display=_to_str(data.get("fund_display")),
            folio_no=_to_str(data.get("folio_no")),
            dop=_to_str(data.get("dop")),
            dos=_to_str(data.get("dos")),
            total_units=_to_float(data.get("total_units")),
            total_cost=_to_float(data.get("total_cost")),
            total_proceeds=_to_float(data.get("total_proceeds")),
            total_gain_loss=_to_float(data.get("total_gain_loss")),
            gain_loss_pct=_to_float(data.get("gain_loss_pct")),
            gain_type=_to_str(data.get("gain_type")),
        )

@dataclass
class ProfitBookFYItem:
    fy: str = ""
    type: str = ""
    investment: float = 0.0
    sale: float = 0.0
    gain: float = 0.0
    pct: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfitBookFYItem":
        data = data or {}
        return cls(
            fy=_to_str(data.get("fy")),
            type=_to_str(data.get("type")),
            investment=_to_float(data.get("investment")),
            sale=_to_float(data.get("sale")),
            gain=_to_float(data.get("gain")),
            pct=_to_float(data.get("pct")),
        )

@dataclass
class ProfitBookStrategyItem:
    financial_year: str = ""
    g: str = ""
    total_cost: float = 0.0
    total_proceeds: float = 0.0
    total_gain_loss: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfitBookStrategyItem":
        data = data or {}
        return cls(
            financial_year=_to_str(data.get("financial_year")),
            g=_to_str(data.get("g")),
            total_cost=_to_float(data.get("total_cost")),
            total_proceeds=_to_float(data.get("total_proceeds")),
            total_gain_loss=_to_float(data.get("total_gain_loss")),
        )

@dataclass
class ProfitBookCategoryItem:
    financial_year: str = ""
    g: str = ""
    c: str = ""
    total_cost: float = 0.0
    total_proceeds: float = 0.0
    total_gain_loss: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfitBookCategoryItem":
        data = data or {}
        return cls(
            financial_year=_to_str(data.get("financial_year")),
            g=_to_str(data.get("g")),
            c=_to_str(data.get("c")),
            total_cost=_to_float(data.get("total_cost")),
            total_proceeds=_to_float(data.get("total_proceeds")),
            total_gain_loss=_to_float(data.get("total_gain_loss")),
        )