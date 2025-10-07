# CSV Setup Guide

The full installation instructions – including how to load the Northwind CSVs – now live in **`INSTALLATION_GUIDE.md`**.  
To avoid keeping the same steps in multiple places, this file only highlights the key reminder:

1. Place the Northwind CSV exports in `data/raw/northwind/` (one file per table).
2. Configure your `.env`.
3. Run the canonical setup command:
   ```bash
   python scripts/setup_database.py
   ```

For detailed troubleshooting, Docker vs local Postgres notes, verification steps, and CLI usage, head over to `INSTALLATION_GUIDE.md`. It is the single source of truth for setup going forward. ✅
