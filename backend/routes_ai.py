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
        include_subportfolios = bool(data.get('include_subportfolios', True))

        db = get_db()

        portfolio_row = db.execute(
            '''
            SELECT p.name, p.account_type, p.current_cash
            FROM portfolios p WHERE p.id = ?
            ''',
            (portfolio_id,),
        ).fetchone()

        if not portfolio_row:
            return error_response(
                'portfolio_not_found',
                'Portfolio not found.',
                status=404,
            )

        subportfolios = []
        if include_subportfolios:
            subportfolios = db.execute(
                '''
                SELECT p.id, p.name, p.current_cash
                FROM portfolios p
                WHERE p.parent_portfolio_id = ? AND (p.is_archived = 0 OR p.is_archived IS NULL)
                ''',
                (portfolio_id,),
            ).fetchall()

        rows = db.execute(
            '''
            SELECT
                h.ticker,
                h.quantity,
                h.total_cost,
                h.sector,
                h.currency,
                h.sub_portfolio_id,
                pc.price AS current_price
            FROM holdings h
            LEFT JOIN price_cache pc ON pc.ticker = h.ticker
            WHERE h.portfolio_id = ? AND h.quantity > 0
            ORDER BY h.sub_portfolio_id, h.total_cost DESC
            ''',
            (portfolio_id,),
        ).fetchall()

        if not rows:
            return error_response(
                'portfolio_empty',
                'Portfolio has no open positions for analysis.',
                status=404,
            )

        sub_map = {
            int(sub['id']): {
                'id': int(sub['id']),
                'name': sub['name'] or f"Sub-portfel {sub['id']}",
                'cash': float(sub['current_cash'] or 0.0),
                'positions': [],
                'value': 0.0,
            }
            for sub in subportfolios
        }

        positions_without_sub = []
        all_positions = []
        total_positions_value = 0.0
        sectors = set()

        for row in rows:
            quantity = float(row['quantity'] or 0)
            total_cost = float(row['total_cost'] or 0)

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
                'sub_portfolio_id': row['sub_portfolio_id'],
            }

            sectors.add(position['sector'])
            all_positions.append(position)
            total_positions_value += current_value

            sub_portfolio_id = row['sub_portfolio_id']
            if include_subportfolios and sub_portfolio_id is not None:
                sub_id = int(sub_portfolio_id)
                sub_entry = sub_map.setdefault(
                    sub_id,
                    {
                        'id': sub_id,
                        'name': f'Sub-portfel {sub_id}',
                        'cash': 0.0,
                        'positions': [],
                        'value': 0.0,
                    },
                )
                sub_entry['positions'].append(position)
                sub_entry['value'] += current_value
            else:
                positions_without_sub.append(position)

        if not all_positions:
            return error_response(
                'portfolio_empty',
                'Portfolio has no open positions for analysis.',
                status=404,
            )

        total_cash = float(portfolio_row['current_cash'] or 0.0) + sum(sub['cash'] for sub in sub_map.values())
        total_value = total_positions_value + total_cash
        cash_pct = (total_cash / total_value * 100) if total_value > 0 else 0.0

        for position in all_positions:
            position['weight_pct'] = (position['current_value'] / total_positions_value * 100) if total_positions_value > 0 else 0.0

        best_position = max(all_positions, key=lambda x: x['unrealized_pnl_pct'])
        worst_position = min(all_positions, key=lambda x: x['unrealized_pnl_pct'])

        sub_lines = []
        if include_subportfolios and sub_map:
            for sub in sorted(sub_map.values(), key=lambda x: x['value'], reverse=True):
                sub_pct = (sub['value'] / total_value * 100) if total_value > 0 else 0.0
                sub_lines.append(
                    f"[{sub['name']}] — wartość: {sub['value']:.2f} PLN ({sub_pct:.1f}% portfela), "
                    f"gotówka: {sub['cash']:.2f} PLN"
                )
                sub_lines.append('  Pozycje:')
                if sub['positions']:
                    sub_total_value = sub['value']
                    for position in sub['positions']:
                        weight = (position['current_value'] / sub_total_value * 100) if sub_total_value > 0 else 0.0
                        sub_lines.append(
                            f"  - {position['ticker']}, sektor: {position['sector']}, waga: {weight:.1f}%, "
                            f"PnL: {position['unrealized_pnl_pct']:+.1f}%, waluta: {position['currency']}"
                        )
                else:
                    sub_lines.append('  - Brak pozycji')
        else:
            sub_lines.append('Brak sub-portfeli do analizy.')

        no_sub_lines = []
        if positions_without_sub:
            for position in positions_without_sub:
                no_sub_lines.append(
                    f"  - {position['ticker']}, sektor: {position['sector']}, waga: {position['weight_pct']:.1f}%, "
                    f"PnL: {position['unrealized_pnl_pct']:+.1f}%, waluta: {position['currency']}"
                )
        else:
            no_sub_lines.append('  - Brak')

        sub_lines_text = '\n'.join(sub_lines)
        no_sub_lines_text = '\n'.join(no_sub_lines)

        prompt = f"""
Jesteś doradcą finansowym analizującym portfel inwestycyjny.

PORTFEL: {portfolio_row['name']} | Typ konta: {portfolio_row['account_type'] or 'Nieznany'}
Łączna wartość: {total_value:.2f} PLN
Gotówka w portfelu: {total_cash:.2f} PLN ({cash_pct:.1f}% portfela)
Liczba pozycji: {len(all_positions)} | Liczba sektorów: {len(sectors)}
Najlepsza pozycja: {best_position['ticker']} ({best_position['unrealized_pnl_pct']:+.1f}%)
Najgorsza pozycja: {worst_position['ticker']} ({worst_position['unrealized_pnl_pct']:+.1f}%)

STRUKTURA SUB-PORTFELI:
{sub_lines_text}

POZYCJE BEZ SUB-PORTFELA (jeśli są):
{no_sub_lines_text}

Założenie analityczne: konto nie pobiera prowizji dla transakcji akcjami w PLN — nie doliczaj prowizji do kosztów ani rekomendacji.

Pytanie użytkownika: {question}

Odpowiedz konkretnie po polsku. Uwzględnij:
- czy strategia każdego sub-portfela jest spójna ze swoją nazwą
- gdzie są ryzyka koncentracji (po pozycji, sektorze, walucie)
- które pozycje nie pasują do swojego sub-portfela
- co warto rozważyć kupić/sprzedać z uzasadnieniem
- jak wygląda poziom gotówki — za dużo czy za mało?
- jeśli konto IKE/IKZE — uwzględnij aspekt podatkowy
Max 400 słów, konkretnie, bez ogólników.
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

        return success_response(
            {
                'answer': answer,
                'analysis_meta': {
                    'positions_count': len(all_positions),
                    'subportfolios_count': len(sub_map) if include_subportfolios else 0,
                },
            }
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response('debug_error', str(e), status=500)
