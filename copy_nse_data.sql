-- Copy NSE_500 data from restored backup to current database
-- Run this in SQL Server Management Studio

USE stockdata_db;
GO

-- Step 1: Check current count in stockdata_db (should be 0 or very low)
SELECT COUNT(*) as Current_NSE_500_Count FROM dbo.nse_500;
GO

-- Step 2: Insert data from restored backup
INSERT INTO stockdata_db.dbo.nse_500
SELECT * FROM stockdata_db_restore.dbo.nse_500;
GO

-- Step 3: Verify the data was copied
SELECT COUNT(*) as New_NSE_500_Count FROM dbo.nse_500;
GO

-- Step 4: Show some sample records
SELECT TOP 10 ticker, company_name, monitor_startdate, monitor_enddate 
FROM dbo.nse_500 
ORDER BY ticker;
GO

-- Optional: If you also need to restore NASDAQ_top100 data, uncomment below:
/*
INSERT INTO stockdata_db.dbo.NASDAQ_top100
SELECT * FROM stockdata_db_restore.dbo.NASDAQ_top100;
GO

SELECT COUNT(*) as NASDAQ_Count FROM dbo.NASDAQ_top100;
GO
*/
