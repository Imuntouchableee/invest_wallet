from types import SimpleNamespace 
from ui.assets_page import show_assets_page 
class DummyPage: 
    def __init__(self): self.controls = []; self.snack_bar = None 
    def add(self, *controls): self.controls.extend(controls) 
    def update(self): pass 
page = DummyPage() 
user = SimpleNamespace(id=1, name='Tester') 
portfolio_cache = {'data': {'total_usd': 15234.56, 'timestamp': None, 'exchanges': {'bybit': {}, 'gateio': {}}, 'all_assets': [{'currency': 'BTC', 'amount': 0.25, 'price_usd': 64000, 'value_usd': 16000, 'exchange': 'bybit'}, {'currency': 'ETH', 'amount': 1.5, 'price_usd': 3200, 'value_usd': 4800, 'exchange': 'gateio'}, {'currency': 'USDT', 'amount': 1000, 'price_usd': 1, 'value_usd': 1000, 'exchange': 'mexc'}]}} 
show_assets_page(page, {'user': user}, portfolio_cache, lambda: None, lambda **kwargs: None) 
print('controls', len(page.controls)) 
