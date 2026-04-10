import re

with open('tests/test_portfolio_history_service.py', 'r') as f:
    content = f.read()

# Fix mock_build_price_context.return_value = (ticker_currency, prices)
# to mock_build_price_context.return_value = ticker_currency
content = re.sub(
    r"mock_build_price_context\.return_value = \(ticker_currency, prices\)",
    r"mock_build_price_context.return_value = ticker_currency\n        def mock_price_at(ticker, target_date, cache=None):\n            target_str = target_date.strftime('%Y-%m-%d')\n            if ticker not in prices or not prices[ticker]: return 0\n            if target_str in prices[ticker]: return prices[ticker][target_str]\n            past_dates = [d for d in prices[ticker].keys() if d <= target_str]\n            if past_dates: return prices[ticker][max(past_dates)]\n            return 0\n        patcher = patch('portfolio_history_service.PortfolioHistoryService._price_at', side_effect=mock_price_at)\n        patcher.start()\n        self.addCleanup(patcher.stop)",
    content
)

content = re.sub(
    r"mock_build_price_context\.return_value = \(\n\s*\{'AAA': 'PLN'\},\n\s*\{'AAA': \{'2026-01-31': 220, '2026-02-28': 240, '2026-04-03': 250\}\},\n\s*\)",
    r"mock_build_price_context.return_value = {'AAA': 'PLN'}\n        prices = {'AAA': {'2026-01-31': 220, '2026-02-28': 240, '2026-04-03': 250}}\n        def mock_price_at(ticker, target_date, cache=None):\n            target_str = target_date.strftime('%Y-%m-%d')\n            if ticker not in prices or not prices[ticker]: return 0\n            if target_str in prices[ticker]: return prices[ticker][target_str]\n            past_dates = [d for d in prices[ticker].keys() if d <= target_str]\n            if past_dates: return prices[ticker][max(past_dates)]\n            return 0\n        patcher = patch('portfolio_history_service.PortfolioHistoryService._price_at', side_effect=mock_price_at)\n        patcher.start()\n        self.addCleanup(patcher.stop)",
    content
)

content = re.sub(
    r"mock_build_price_context\.return_value = \(\{\}, \{\}\)",
    r"mock_build_price_context.return_value = {}\n        patcher = patch('portfolio_history_service.PortfolioHistoryService._price_at', return_value=0)\n        patcher.start()\n        self.addCleanup(patcher.stop)",
    content
)

content = re.sub(
    r"mock_build_price_context\.return_value = \(\{ticker: 'PLN' for ticker in tickers\}, price_history\)",
    r"mock_build_price_context.return_value = {ticker: 'PLN' for ticker in tickers}\n        def mock_price_at(ticker, target_date, cache=None):\n            target_str = target_date.strftime('%Y-%m-%d')\n            if ticker not in price_history or not price_history[ticker]: return 0\n            if target_str in price_history[ticker]: return price_history[ticker][target_str]\n            past_dates = [d for d in price_history[ticker].keys() if d <= target_str]\n            if past_dates: return price_history[ticker][max(past_dates)]\n            return 0\n        patcher = patch('portfolio_history_service.PortfolioHistoryService._price_at', side_effect=mock_price_at)\n        patcher.start()\n        self.addCleanup(patcher.stop)",
    content
)

content = re.sub(
    r"mock_build_price_context\.return_value = \(\{'ABC': 'USD'\}, price_history\)",
    r"mock_build_price_context.return_value = {'ABC': 'USD'}\n        def mock_price_at(ticker, target_date, cache=None):\n            target_str = target_date.strftime('%Y-%m-%d')\n            if ticker not in price_history or not price_history[ticker]: return 0\n            if target_str in price_history[ticker]: return price_history[ticker][target_str]\n            past_dates = [d for d in price_history[ticker].keys() if d <= target_str]\n            if past_dates: return price_history[ticker][max(past_dates)]\n            return 0\n        patcher = patch('portfolio_history_service.PortfolioHistoryService._price_at', side_effect=mock_price_at)\n        patcher.start()\n        self.addCleanup(patcher.stop)",
    content
)

content = re.sub(
    r"mock_build_price_context\.return_value = \(\{'AAA': 'PLN'\}, \{'AAA': \{'2026-03-31': 60, '2026-04-03': 60\}\}\)",
    r"mock_build_price_context.return_value = {'AAA': 'PLN'}\n        price_history = {'AAA': {'2026-03-31': 60, '2026-04-03': 60}}\n        def mock_price_at(ticker, target_date, cache=None):\n            target_str = target_date.strftime('%Y-%m-%d')\n            if ticker not in price_history or not price_history[ticker]: return 0\n            if target_str in price_history[ticker]: return price_history[ticker][target_str]\n            past_dates = [d for d in price_history[ticker].keys() if d <= target_str]\n            if past_dates: return price_history[ticker][max(past_dates)]\n            return 0\n        patcher = patch('portfolio_history_service.PortfolioHistoryService._price_at', side_effect=mock_price_at)\n        patcher.start()\n        self.addCleanup(patcher.stop)",
    content
)

content = re.sub(
    r"mock_build_price_context\.return_value = \(\{'AAA': 'PLN'\}, \{'AAA': \{'2026-03-26': 500, '2026-04-03': 500\}\}\)",
    r"mock_build_price_context.return_value = {'AAA': 'PLN'}\n        price_history = {'AAA': {'2026-03-26': 500, '2026-04-03': 500}}\n        def mock_price_at(ticker, target_date, cache=None):\n            target_str = target_date.strftime('%Y-%m-%d')\n            if ticker not in price_history or not price_history[ticker]: return 0\n            if target_str in price_history[ticker]: return price_history[ticker][target_str]\n            past_dates = [d for d in price_history[ticker].keys() if d <= target_str]\n            if past_dates: return price_history[ticker][max(past_dates)]\n            return 0\n        patcher = patch('portfolio_history_service.PortfolioHistoryService._price_at', side_effect=mock_price_at)\n        patcher.start()\n        self.addCleanup(patcher.stop)",
    content
)

content = re.sub(
    r"def test_benchmark_shows_operation_reduction\(self\):",
    r"@patch('portfolio_history_service.get_db')\n    def test_benchmark_shows_operation_reduction(self, mock_get_db):\n        db = MagicMock()\n        db.execute.return_value.fetchone.return_value = None\n        mock_get_db.return_value = db",
    content
)

content = re.sub(
    r"price_index = PortfolioHistoryService\._build_sorted_price_index\(\{\}\)",
    r"",
    content
)

content = re.sub(
    r"_ = PortfolioHistoryService\._price_at\(price_index, 'NONE', point, cache\)",
    r"_ = PortfolioHistoryService._price_at('NONE', point, cache)",
    content
)

with open('tests/test_portfolio_history_service.py', 'w') as f:
    f.write(content)
