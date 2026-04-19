import sqlite3
import os

def clear_database():
    # Pobieramy ścieżkę do bazy danych znajdującej się w tym samym folderze co skrypt
    db_path = os.path.join(os.path.dirname(__file__), 'portfolio.db')
    
    if not os.path.exists(db_path):
        # Próba znalezienia bazy w folderze wyżej, jeśli skrypt jest w backend/
        db_path = os.path.join(os.path.dirname(__file__), '..', 'portfolio.db')
        if not os.path.exists(db_path):
             # Ostateczna próba w bieżącym katalogu
             db_path = 'portfolio.db'

    print(f"Próba połączenia z bazą danych: {os.path.abspath(db_path)}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Tabela symbol_mappings zostaje - reszta do wyczyszczenia
        tables_to_clear = [
            'watchlist', 'ppk_transactions', 'transactions', 'holdings',
            'stock_prices', 'price_cache', 'quotes_cache', 'stock_history_refresh_state', 'radar_cache', 'asset_metadata',
            'dividends', 'bonds', 'loan_rates', 'loan_overpayments',
            'ppk_portfolios', 'portfolios', 'budget_transactions',
            'envelope_loans', 'envelopes', 'envelope_categories',
            'budget_accounts', 'loans', 'inflation_data'
        ]

        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Sprawdzamy które tabele faktycznie istnieją
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        for table in tables_to_clear:
            if table in existing_tables:
                cursor.execute(f"DELETE FROM {table}")
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
                print(f"Wyczyszczono: {table}")
            else:
                print(f"Pominięto (brak tabeli): {table}")
        
        conn.commit()
        print("\n[OK] Historia została wyczyszczona. Zachowano symbol_mappings.")
    except Exception as e:
        print(f"\n[BŁĄD]: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    clear_database()
