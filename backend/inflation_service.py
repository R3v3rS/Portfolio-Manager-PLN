import requests
from database import get_db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class InflationService:
    @staticmethod
    def fetch_and_store_inflation():
        """
        Pulls Poland HICP data from Eurostat API and stores it in the database.
        API: Eurostat SDMX-JSON
        Dataset: prc_hicp_midx (HICP Monthly Index)
        Filters: geo=PL, unit=I15 (Index 2015=100), coicop=CP00 (All-items)
        """
        url = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_midx?format=JSON&lang=en&geo=PL&unit=I15&coicop=CP00"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Eurostat SDMX-JSON structure:
            # data['dimension']['time']['category']['index'] maps index (int) to date string (e.g. "2024-01")
            # data['value'] maps index (string) to the actual value (float)
            
            time_dimension = data['dimension']['time']['category']['index']
            values = data['value']
            
            db = get_db()
            count = 0
            
            # Sort by index to ensure order if needed, though we use dates as keys
            for date_str, idx in time_dimension.items():
                # date_str is typically like "2024M01" in Eurostat JSON
                # Normalize to YYYY-MM
                if 'M' in date_str:
                    formatted_date = date_str.replace('M', '-')
                else:
                    formatted_date = date_str
                
                # The values dict uses the index (as string) as key
                val = values.get(str(idx))
                
                if val is not None:
                    db.execute(
                        "INSERT OR REPLACE INTO inflation_data (date, index_value) VALUES (?, ?)",
                        (formatted_date, float(val))
                    )
                    count += 1
            
            db.commit()
            logger.info(f"Inflation data updated from Eurostat: {count} entries.")
            return True
        except Exception as e:
            logger.error(f"Error fetching inflation data: {e}")
            return False

    @staticmethod
    def get_inflation_series(start_date_str, end_date_str):
        """
        Returns ordered monthly data aligned to portfolio history.
        start_date_str: "YYYY-MM"
        end_date_str: "YYYY-MM"
        """
        db = get_db()
        
        # Ensure we have data
        existing = db.execute("SELECT COUNT(*) as count FROM inflation_data").fetchone()
        if not existing or existing['count'] == 0:
            InflationService.fetch_and_store_inflation()
        
        # Fetch from DB
        rows = db.execute(
            "SELECT date, index_value FROM inflation_data WHERE date >= ? AND date <= ? ORDER BY date ASC",
            (start_date_str, end_date_str)
        ).fetchall()
        
        if not rows:
            logger.warning(f"No inflation data found between {start_date_str} and {end_date_str}")
            return []
            
        logger.info("Inflation data loaded from DB")
        return [{"date": row["date"], "index_value": row["index_value"]} for row in rows]
