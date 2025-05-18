import csv
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='preprocess.log',
    filemode='w'
)
logger = logging.getLogger(__name__)

def parse_date_range(date_range: str, current_year: Optional[int] = None) -> tuple:
    """
    Parse a date range string (e.g., "Feb 1-6" or "Dec 28-Jan 3") into start and end dates.
    Infers the year if not present in the string.
    
    Args:
        date_range: String representing a date range
        current_year: The year to use if not specified in the date_range
    
    Returns:
        Tuple of (start_date, end_date) in ISO format (YYYY-MM-DD)
    """
    if current_year is None:
        current_year = datetime.now().year
    
    # Clean the date range string
    date_range = date_range.strip()
    
    # Handle various separators (-, –, —, to)
    date_range = re.sub(r'[\-–—]|to', '-', date_range)
    
    # Check if there's a range or just a single date
    if '-' in date_range:
        # Split the range
        start_str, end_str = date_range.split('-', 1)
        start_str = start_str.strip()
        end_str = end_str.strip()
        
        # Parse the start date
        try:
            # Check if month is in the start string
            if any(month in start_str.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                                                          'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                # If there's a month, try to parse with the current year
                start_date = datetime.strptime(f"{start_str} {current_year}", "%b %d %Y")
            else:
                # If no month, assume it's just a day and use the month from end_str
                month = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', 
                                 end_str.lower()).group(1).capitalize()
                start_date = datetime.strptime(f"{month} {start_str} {current_year}", "%b %d %Y")
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing start date '{start_str}': {e}")
            return None, None
        
        # Parse the end date
        try:
            end_date = datetime.strptime(f"{end_str} {current_year}", "%b %d %Y")
            
            # Handle year wrap (December to January)
            if start_date.month == 12 and end_date.month == 1:
                end_date = end_date.replace(year=current_year + 1)
            
            # Handle case where end date is before start date (needs year increment)
            if end_date < start_date and end_date.month != 1:
                end_date = end_date.replace(year=current_year + 1)
                
        except ValueError as e:
            logger.warning(f"Error parsing end date '{end_str}': {e}")
            return None, None
    else:
        # Single date
        try:
            start_date = end_date = datetime.strptime(f"{date_range} {current_year}", "%b %d %Y")
        except ValueError as e:
            logger.warning(f"Error parsing single date '{date_range}': {e}")
            return None, None
    
    # Format as ISO dates
    start_iso = start_date.strftime("%Y-%m-%d")
    end_iso = end_date.strftime("%Y-%m-%d")
    
    return start_iso, end_iso

def load_weekly_records(path: str) -> List[Dict]:
    """
    Load and parse the media_enjoyed.csv file.
    
    Args:
        path: Path to the CSV file
        
    Returns:
        List of dictionaries with start_date, end_date, and raw_notes
    """
    records = []
    current_year = None
    
    try:
        with open(path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                date_range = row.get('DateRange', '').strip()
                notes = row.get('Notes', '').strip()
                
                if not date_range or not notes:
                    continue
                
                # Parse the date range
                start_date, end_date = parse_date_range(date_range, current_year)
                
                if start_date and end_date:
                    # Update the current year for future rows
                    current_year = int(start_date.split('-')[0])
                    
                    records.append({
                        'start_date': start_date,
                        'end_date': end_date,
                        'raw_notes': notes
                    })
                else:
                    logger.warning(f"Skipping row with unparseable date range: {date_range}")
    
    except Exception as e:
        logger.error(f"Error loading CSV file: {e}")
        raise
    
    logger.info(f"Loaded {len(records)} weekly records from {path}")
    return records

if __name__ == "__main__":
    # Example usage
    records = load_weekly_records("preprocessing/media_enjoyed.csv")
    print(f"Loaded {len(records)} records")
