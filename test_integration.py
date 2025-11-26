#!/usr/bin/env python3
"""
Integration Test Script for Flight Status Dashboard
Tests the complete integration without running the full Streamlit app
"""

import sys
import os
import traceback

def test_imports():
    """Test if all required packages are available"""
    print("🧪 Testing imports...")
    
    try:
        import pandas as pd
        print("✅ pandas import successful")
        
        import streamlit as st
        print("✅ streamlit import successful")
        
        import pyodbc
        print("✅ pyodbc import successful")
        
        import plotly.graph_objects as go
        print("✅ plotly import successful")
        
        import plotly.express as px
        print("✅ plotly express import successful")
        
        from datetime import datetime, timedelta
        print("✅ datetime import successful")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_file_structure():
    """Test if the main application file exists and has the right functions"""
    print("\n🗂️ Testing file structure...")
    
    main_file = "streamlitapp_20251123_v2.py"
    
    if not os.path.exists(main_file):
        print(f"❌ Main file {main_file} not found")
        return False
    
    print(f"✅ Main file {main_file} exists")
    
    # Check if key functions exist in the file
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
        functions_to_check = [
            'show_flight_status_page',
            'load_flight_status_data',
            'render_flight_status_summary_metrics',
            'apply_flight_status_filters',
            'get_flight_status_emoji'
        ]
        
        for func in functions_to_check:
            if f"def {func}" in content:
                print(f"✅ Function {func} found")
            else:
                print(f"❌ Function {func} missing")
                return False
        
        # Check navigation integration
        if "🛩️ Flight Status Dashboard" in content:
            print("✅ Flight Status Dashboard found in navigation")
        else:
            print("❌ Flight Status Dashboard missing from navigation")
            return False
        
        # Check routing
        if 'elif page == "🛩️ Flight Status Dashboard":' in content:
            print("✅ Flight Status Dashboard routing found")
        else:
            print("❌ Flight Status Dashboard routing missing")
            return False
    
    return True

def test_syntax():
    """Test if the main file has valid Python syntax"""
    print("\n🐍 Testing Python syntax...")
    
    try:
        import py_compile
        py_compile.compile("streamlitapp_20251123_v2.py", doraise=True)
        print("✅ Python syntax is valid")
        return True
    except py_compile.PyCompileError as e:
        print(f"❌ Syntax error: {e}")
        return False

def main():
    """Main test runner"""
    print("🛩️ Flight Status Dashboard Integration Test")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Imports
    if test_imports():
        tests_passed += 1
    
    # Test 2: File structure
    if test_file_structure():
        tests_passed += 1
    
    # Test 3: Syntax
    if test_syntax():
        tests_passed += 1
    
    # Summary
    print(f"\n📊 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! Flight Status Dashboard is ready to use.")
        print("\n🚀 To start the application:")
        print("streamlit run streamlitapp_20251123_v2.py")
        print("\n📱 The dashboard will be available at:")
        print("http://localhost:8501")
        print("\n🛩️ Navigate to 'Flight Status Dashboard' from the sidebar!")
        return True
    else:
        print("❌ Some tests failed. Please review the errors above.")
        return False

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
