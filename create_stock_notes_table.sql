-- ========================================
-- Create Stock Notes Table
-- ========================================
-- Run this script in SQL Server Management Studio
-- as a user with CREATE TABLE permissions
-- ========================================

USE stockdata_db
GO

-- Drop table if you want to recreate it (optional)
-- DROP TABLE IF EXISTS dbo.stock_notes
-- GO

-- Create stock_notes table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='stock_notes' AND xtype='U')
BEGIN
    CREATE TABLE dbo.stock_notes (
        id INT IDENTITY(1,1) PRIMARY KEY,
        ticker VARCHAR(50) NOT NULL,
        market VARCHAR(20) NOT NULL,
        note_date DATETIME DEFAULT GETDATE(),
        note_title VARCHAR(200),
        note_text VARCHAR(MAX),
        note_type VARCHAR(50) DEFAULT 'General',
        created_at DATETIME DEFAULT GETDATE(),
        updated_at DATETIME DEFAULT GETDATE()
    )
    
    PRINT 'Table stock_notes created successfully!'
END
ELSE
BEGIN
    PRINT 'Table stock_notes already exists!'
END
GO

-- Grant permissions to remote_user
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.stock_notes TO remote_user
GO

PRINT 'Permissions granted to remote_user'
GO

-- Verify table creation
SELECT 'Table created successfully!' AS Status,
       COUNT(*) AS RecordCount
FROM dbo.stock_notes
GO

-- Sample query to view structure
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'stock_notes'
ORDER BY ORDINAL_POSITION
GO
