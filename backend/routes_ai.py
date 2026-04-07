import os
import logging

from flask import Blueprint

from api.response import error_response, success_response
from database import get_db
from routes_portfolio_base import require_json_body, require_non_empty_string, require_positive_int

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - handled at runtime if dependency missing
    genai = None

logger = logging.getLogger(__name__)
ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/api/ai/portfolio-analysis', methods=['POST'])
def portfolio_analysis():
    logger.info("AI: Received portfolio-analysis request")
    try:
        data = require_json_body()
        portfolio_id = require_positive_int(data, 'portfolio_id')
        question = require_non_empty_string(data, 'question')

        db = get_db()
        # ... (rest of the code)
        rows = db.execute(
            '''
            SELECT
                h.ticker,
                h.quantity,
                h.total_cost,
                h.sector,
                h.currency,
                pc.price AS current_price
            FROM holdings h
            LEFT JOIN price_cache pc ON pc.ticker = h.ticker
            WHERE h.portfolio_id = ? AND h.quantity > 0
            ORDER BY h.total_cost DESC
            ''',
            (portfolio_id,),
        ).fetchall()

        if not rows:
            return error_response(
                'portfolio_empty',
                'Portfolio has no open positions for analysis.',
                status=404,
            )

        positions = []
        total_portfolio_value = 0.0

        for row in rows:
            quantity = float(row['quantity'] or 0)
            total_cost = float(row['total_cost'] or 0)
            
            # Use 0.0 if current_price is None or cannot be converted to float
            current_price_raw = row['current_price']
            try:
                current_price = float(current_price_raw) if current_price_raw is not None else 0.0
            except (ValueError, TypeError):
                current_price = 0.0

            current_value = quantity * current_price
            unrealized_pnl = current_value - total_cost
            unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0.0

            position = {
                'ticker': row['ticker'],
                'sector': row['sector'] or 'Nieznany',
                'currency': row['currency'] or 'PLN',
                'quantity': quantity,
                'total_cost': total_cost,
                'current_price': current_price,
                'current_value': current_value,
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_pct': unrealized_pnl_pct,
            }
            positions.append(position)
            total_portfolio_value += current_value

        for position in positions:
            weight = (position['current_value'] / total_portfolio_value * 100) if total_portfolio_value > 0 else 0.0
            position['weight_pct'] = weight

        positions_prompt = '\n'.join(
            f"- {position['ticker']}, sektor: {position['sector']}, "
            f"waga: {position['weight_pct']:.2f}%, "
            f"unrealized_pnl: {position['unrealized_pnl_pct']:.2f}%"
            for position in positions
        )

        prompt = f"""
Jesteś doradcą finansowym analizującym portfel inwestycyjny.

Portfel użytkownika (łączna wartość: {total_portfolio_value:.2f} PLN):
{positions_prompt}

Pytanie użytkownika: {question}

Odpowiedz konkretnie po polsku. Wskaż:
- gdzie są największe ryzyka (koncentracja, sektor, strata)
- które pozycje wyglądają dobrze
- co rozważyłbyś dokupić lub sprzedać i dlaczego
- max 300 słów, bez ogólników
""".strip()

        if genai is None:
            return error_response(
                'gemini_unavailable',
                'google-generativeai package is not installed.',
                status=500,
            )

        api_key = os.getenv('GEMINI_API_KEY')
        logger.info(f"AI: GEMINI_API_KEY found: {bool(api_key)}")
        if not api_key:
            logger.error("AI: Missing GEMINI_API_KEY")
            return error_response(
                'gemini_config_error',
                'Missing GEMINI_API_KEY environment variable.',
                status=500,
            )

        logger.info(f"AI: Configuring genai with key: {api_key[:5]}... (using transport='rest')")
        genai.configure(api_key=api_key, transport='rest')
        model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
        
        logger.info("AI: Sending request to Gemini...")
        gemini_response = model.generate_content(prompt)
        logger.info("AI: Received response from Gemini")
        
        answer = (gemini_response.text or '').strip()
        logger.info(f"AI: Answer length: {len(answer)}")

        if not answer:
            return error_response(
                'gemini_empty_response',
                'Gemini returned an empty answer.',
                status=502,
            )

        return success_response({'answer': answer})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response('debug_error', str(e), status=500)
