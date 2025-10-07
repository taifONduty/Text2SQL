#!/usr/bin/env python3
"""
Script to download Northwind database files.
"""

import requests
import zipfile
import io
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_northwind_data():
    """Download Northwind database from Maven Analytics."""
    
    data_dir = Path(__file__).parent.parent / 'data' / 'raw'
    data_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("Downloading Northwind database from Maven Analytics...")
    
    # Maven Analytics Northwind dataset
    url = "https://maven-datasets.s3.amazonaws.com/Northwind+Traders/Northwind+Traders.zip"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        logger.info("Download successful. Extracting files...")
        
        # Extract ZIP file
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            # Find the Excel file in the ZIP
            excel_files = [f for f in zip_file.namelist() if f.endswith('.xlsx')]
            
            if not excel_files:
                logger.error("No Excel file found in ZIP archive")
                return False
            
            # Extract the Excel file
            excel_filename = excel_files[0]
            zip_file.extract(excel_filename, data_dir)
            
            # Rename to northwind.xlsx
            extracted_path = data_dir / excel_filename
            target_path = data_dir / 'northwind.xlsx'
            
            if extracted_path.exists():
                extracted_path.rename(target_path)
                logger.info(f"✓ Northwind database saved to: {target_path}")
                return True
        
        return False
    
    except requests.RequestException as e:
        logger.error(f"Download failed: {e}")
        logger.info("\nAlternative download options:")
        logger.info("1. Manual download from: https://maven-datasets.s3.amazonaws.com/Northwind+Traders/Northwind+Traders.zip")
        logger.info("2. GitHub: https://github.com/pthom/northwind_psql")
        logger.info(f"3. Place Excel file at: {data_dir / 'northwind.xlsx'}")
        return False
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Northwind Database Downloader")
    logger.info("="*60 + "\n")
    
    success = download_northwind_data()
    
    if success:
        logger.info("\n" + "="*60)
        logger.info("Download completed successfully!")
        logger.info("Next step: Run python scripts/setup_database.py")
        logger.info("="*60)
    else:
        logger.error("\nDownload failed. Please download manually.")
        exit(1)

