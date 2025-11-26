"""
Flask/FastAPI conversion of the Streamlit trading dashboard
For deployment on traditional web hosting
"""

from flask import Flask, render_template, request, jsonify
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
import json
import yfinance as yf
from datetime import datetime, timedelta

app = Flask(__name__)

# Configure JSON encoder for Plotly
app.json_encoder = PlotlyJSONEncoder

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/stock-data')
def get_stock_data():
    """API endpoint to fetch stock data"""
    symbol = request.args.get('symbol', 'AAPL')
    period = request.args.get('period', '1y')
    
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        
        # Create price chart
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name=symbol
        ))
        
        fig.update_layout(
            title=f'{symbol} Stock Price',
            yaxis_title='Price ($)',
            template='plotly_dark'
        )
        
        return jsonify({
            'chart': json.dumps(fig, cls=PlotlyJSONEncoder),
            'data': data.tail(10).to_dict('records'),
            'current_price': float(data['Close'].iloc[-1]),
            'change': float(data['Close'].iloc[-1] - data['Close'].iloc[-2])
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml-prediction')
def get_ml_prediction():
    """API endpoint for ML predictions"""
    symbol = request.args.get('symbol', 'AAPL')
    
    # Simplified ML prediction logic
    # (You would integrate your actual ML models here)
    
    import numpy as np
    
    # Mock prediction for demonstration
    prediction = {
        'symbol': symbol,
        'predicted_change': np.random.uniform(-0.05, 0.05),
        'confidence': np.random.uniform(0.6, 0.9),
        'recommendation': 'BUY',  # or 'HOLD', 'SELL'
        'target_price': 150.0,
        'risk_level': 'Medium'
    }
    
    return jsonify(prediction)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
