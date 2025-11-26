#!/usr/bin/env python3
"""
Flight Status Dashboard - Test Script
Tests database connectivity and core functionality before running the full dashboard
"""

import sys
import os
import traceback

def test_imports():
    """Test if all required packages are available"""
    print("🔍 Testing Python package imports...")
    
    required_packages = [
        ('streamlit', 'Streamlit'),
        ('pandas', 'Pandas'), 
        ('pyodbc', 'SQL Server ODBC Driver'),
        ('plotly', 'Plotly'),
        ('numpy', 'NumPy')
    ]
    
    missing_packages = []
    
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"✅ {name} - Available")
        except ImportError:
            print(f"❌ {name} - Missing")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n📦 Install missing packages:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ All required packages are available!\n")
    return True

def test_database_connection():
    """Test database connectivity"""
    print("🔗 Testing database connection...")
    
    try:
        import pyodbc
        
        connection_string = (
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=localhost\\MSSQLSERVER01;'
            'DATABASE=stockdata_db;'
            'Trusted_Connection=yes;'
            'MARS_Connection=yes;'
            'Connection Timeout=10;'
        )
        
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        
        # Test basic connection
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        print(f"✅ Database connected successfully!")
        print(f"📊 SQL Server Version: {version.split('Microsoft SQL Server')[1].split('(')[0].strip()}")
        
        # Test if stockdata_db exists and has data
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
        table_count = cursor.fetchone()[0]
        print(f"📋 Found {table_count} tables in database")
        
        # Test key tables
        key_tables = ['nse_500_hist_data', 'nasdaq_100_hist_data']
        for table in key_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM dbo.{table}")
                count = cursor.fetchone()[0]
                print(f"📈 {table}: {count:,} records")
            except:
                print(f"⚠️  {table}: Not found or no access")
        
        cursor.close()
        conn.close()
        print("✅ Database test completed successfully!\n")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed:")
        print(f"Error: {str(e)}")
        print("\n🔧 Troubleshooting:")
        print("1. Ensure SQL Server is running (MSSQLSERVER01 instance)")
        print("2. Verify database 'stockdata_db' exists")
        print("3. Check Windows Authentication permissions")
        print("4. Ensure ODBC Driver 17 for SQL Server is installed")
        return False

def test_sample_query():
    """Test a sample query similar to what the dashboard uses"""
    print("🔍 Testing sample data query...")
    
    try:
        import pandas as pd
        import pyodbc
        
        connection_string = (
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=localhost\\MSSQLSERVER01;'
            'DATABASE=stockdata_db;'
            'Trusted_Connection=yes;'
            'MARS_Connection=yes;'
        )
        
        # Simple test query
        query = """
        SELECT TOP 5 
            ticker,
            company,
            trading_date,
            close_price,
            volume
        FROM dbo.nse_500_hist_data
        ORDER BY trading_date DESC
        """
        
        df = pd.read_sql(query, connection_string)
        
        if not df.empty:
            print(f"✅ Sample query successful! Retrieved {len(df)} rows")
            print("📋 Sample data:")
            print(df.to_string(index=False))
            print()
            return True
        else:
            print("⚠️  Query executed but returned no data")
            return False
            
    except Exception as e:
        print(f"❌ Sample query failed: {str(e)}")
        return False

def main():
    """Main test runner"""
    print("🚀 Flight Status Dashboard - Environment Test")
    print("=" * 50)
    
    success_count = 0
    total_tests = 3
    
    # Test 1: Package imports
    if test_imports():
        success_count += 1
    
    # Test 2: Database connection
    if test_database_connection():
        success_count += 1
    
    # Test 3: Sample query
    if test_sample_query():
        success_count += 1
    
    # Results
    print("=" * 50)
    print(f"🎯 Test Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("✅ All tests passed! You can now run the Flight Status Dashboard")
        print("\n🚀 To start the dashboard, run:")
        print("streamlit run flight_status_dashboard.py --server.port 8502")
    else:
        print("❌ Some tests failed. Please fix the issues above before running the dashboard.")
        
    return success_count == total_tests

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
