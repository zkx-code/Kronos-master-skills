"""Market adapters for scheduled mainland equity intraday prediction."""
from __future__ import annotations
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class MarketAdapter:
    key: str
    name: str
    exchange: str
    calendar: str
    timezone: str
    symbol_pattern: re.Pattern[str]
    automatic_sources: tuple[str, ...]
    calendar_reference: str
    calendar_note: str
    def normalize_symbol(self, symbol: str) -> str:
        value = symbol.strip().lower()
        if self.key == 'cn':
            if not re.fullmatch(r'(sh|sz)\d{6}', value):
                raise ValueError('沪深 A 股代码必须是 sh600519 或 sz000001 格式')
            return value
        if self.key == 'bse':
            value = value.removeprefix('bj')
            if not self.symbol_pattern.fullmatch(value):
                raise ValueError('北交所代码必须是 43xxxx、83xxxx、87xxxx 或 92xxxx 格式')
            return value
        raise ValueError(f'Unsupported market: {self.key}')

CN_ADAPTER = MarketAdapter(
    'cn', '沪深 A 股', 'SSE/SZSE', 'XSHG', 'Asia/Shanghai',
    re.compile(r'(sh|sz)\d{6}'), ('sina', 'eastmoney'),
    'https://www.sse.com.cn/disclosure/dealinstruc/closed/',
    'XSHG schedule; verify exchange holidays and instrument suspensions before inference',
)
BSE_ADAPTER = MarketAdapter(
    'bse', '北京证券交易所', 'BSE', 'XSHG', 'Asia/Shanghai',
    re.compile(r'(43|83|87|92)\d{4}'), ('eastmoney',),
    'https://www.bse.cn/',
    'XSHG is a shared-session proxy, not a Beijing Exchange calendar; '
    'verify BSE holiday notices and instrument suspensions before inference',
)
ADAPTERS = {'cn': CN_ADAPTER, 'bse': BSE_ADAPTER}

def get_adapter(market: str) -> MarketAdapter:
    try:
        return ADAPTERS[market.lower()]
    except KeyError as exc:
        raise ValueError(f'Unsupported market {market!r}; choose cn or bse') from exc
