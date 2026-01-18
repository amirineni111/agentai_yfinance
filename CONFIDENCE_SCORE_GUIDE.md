# Model Confidence Score - Quick Reference

## What Changed?

### Before (Hardcoded):
```python
return predicted_change, 75.0  # Everyone got 75%
```
- **No meaning** - just a placeholder number
- All predictions had identical 75% confidence
- Impossible to judge prediction reliability

### After (Calculated):
```python
# Calculate from validation performance:
- Direction Accuracy: % of correct up/down predictions
- R² Score: How well model explains variance
- MAPE-based: Inverse of prediction error
  
confidence = (0.4 × direction_acc + 0.3 × r2_score + 0.3 × error_based)
```
- **Real metric** based on model performance
- Varies by ticker, model, and timeframe
- Bounded between 20% and 95%

---

## How to Interpret Confidence Scores

### Confidence Levels:
| Range | Level | Meaning | Action |
|-------|-------|---------|--------|
| **80-95%** | 🟢 HIGH | Strong predictive power | Trust prediction, act on signals |
| **60-79%** | 🟡 MODERATE | Decent reliability | Use with caution, confirm with other indicators |
| **20-59%** | 🔴 LOW | High uncertainty | Treat as weak signal only |

### Current Scores (20-39%):
Your current predictions show **low confidence** (20-39%) which means:

✅ **What It Tells You:**
- Models CAN detect price direction trends
- Limited by short historical data (~275 days)
- High market volatility makes precise predictions hard
- Models need more data and tuning

❌ **What It Doesn't Mean:**
- Predictions are worthless (they still show trends)
- Models aren't working (they just need improvement)
- You should ignore them (use as one of many signals)

---

## Real Example from Your Database

```sql
ticker         model_name          change_pct  confidence  
BHARTIARTL.NS  Linear Regression   +0.49%      39%    ← Highest confidence
HCLTECH.NS     Gradient Boosting   -0.15%      37%
PEP            Random Forest       -0.10%      37%
EURUSD         Gradient Boosting   +0.91%      31%
AAPL           Random Forest       -2.91%      21%
NZDUSD         Linear Regression   +0.05%      20%    ← Lowest (hit floor)
```

**Interpretation:**
- BHARTIARTL prediction (39%) is the most reliable
- NZDUSD prediction (20%) has highest uncertainty
- All are "low confidence" but BHARTIARTL is relatively better

---

## Confidence Components Breakdown

### 1. Direction Accuracy (40% weight)
- **What:** % of test predictions that correctly predicted up/down
- **Example:** 7 out of 10 test cases predicted correct direction = 70%
- **Impact:** Most important for trend trading

### 2. R² Score (30% weight)  
- **What:** How much variance model explains (0 to 1)
- **Example:** R² = 0.3 means model explains 30% of price movements
- **Impact:** Measures overall prediction quality

### 3. Error-based (30% weight)
- **What:** 100 minus Mean Absolute Percentage Error (MAPE)
- **Example:** MAPE = 20% → Error-based score = 80%
- **Impact:** Penalizes large prediction errors

**Formula:**
```
Confidence = 0.4 × Direction_Acc + 0.3 × (R² × 100) + 0.3 × (100 - MAPE)
Then bounded to [20%, 95%]
```

---

## Why Low Confidence Now?

### Data Constraints:
- **~275 days** of history (need 1+ year ideally)
- **Recent data** (started Dec 2024, not enough cycles)
- **High volatility** period (Jan 2026 markets)

### Model Limitations:
- Default hyperparameters (not optimized)
- No feature engineering (basic technical indicators only)
- No external factors (news, sentiment, macro events)

### Market Reality:
- Stock prices are inherently hard to predict
- Even professional models rarely exceed 60-70% confidence
- **20-39% is honest** - shows model's true capability

---

## How to Improve Confidence

### Short-term (Immediate):
1. **Collect more data** - Run data fetch for older dates
2. **Filter by confidence** - Only act on >30% predictions
3. **Use ensemble** - Combine predictions from multiple models

### Medium-term (1-2 weeks):
1. **Hyperparameter tuning** - Grid search for best model settings
2. **Feature engineering** - Add more technical indicators
3. **Cross-validation** - Use time-series CV for better validation

### Long-term (1+ months):
1. **Collect 1+ year** of historical data
2. **Add external features** - News sentiment, volume patterns
3. **Try advanced models** - LSTM, Transformers, Prophet
4. **Sector-specific models** - Different models per industry

---

## Using Low-Confidence Predictions

### DO:
✅ Use as **one signal among many**
✅ Combine with your own analysis
✅ Filter for highest confidence within dataset
✅ Watch for **direction** rather than exact price
✅ Use stop-losses and risk management

### DON'T:
❌ Bet large amounts on single prediction
❌ Ignore other market indicators
❌ Expect precise price targets
❌ Trade without risk management
❌ Assume 75% old predictions are reliable

---

## Checking Confidence in Dashboard

### SQL Query:
```sql
-- View confidence distribution
SELECT 
    CASE 
        WHEN model_confidence >= 80 THEN 'HIGH (80%+)'
        WHEN model_confidence >= 60 THEN 'MODERATE (60-79%)'
        ELSE 'LOW (<60%)'
    END as confidence_level,
    COUNT(*) as predictions
FROM ai_prediction_history
WHERE prediction_date = CAST(GETDATE() AS DATE)
GROUP BY CASE 
    WHEN model_confidence >= 80 THEN 'HIGH (80%+)'
    WHEN model_confidence >= 60 THEN 'MODERATE (60-79%)'
    ELSE 'LOW (<60%)'
END;
```

### Best Predictions Today:
```sql
-- Get highest confidence predictions
SELECT TOP 20
    ticker,
    model_name,
    days_ahead,
    predicted_change_pct,
    model_confidence,
    target_date
FROM ai_prediction_history
WHERE prediction_date = CAST(GETDATE() AS DATE)
  AND model_confidence != 75  -- Exclude old hardcoded values
ORDER BY model_confidence DESC;
```

---

## Summary

| Aspect | Old System | New System |
|--------|------------|------------|
| **Value** | Always 75% | 20% - 95% |
| **Meaning** | None (placeholder) | Real validation performance |
| **Reliability** | Can't judge | Shows true model capability |
| **Current Range** | N/A | 20% - 39% (low but honest) |
| **Interpretation** | Ignore | Use cautiously as one signal |

**Bottom Line:** 
Your predictions now have **honest, calculated confidence scores**. Low scores (20-39%) accurately reflect model uncertainty with limited data. Use predictions as directional signals, not exact targets. Confidence will improve with more historical data and model tuning.

---

*Last Updated: 2026-01-17*
*Database: 486 new predictions with calculated confidence*
*Old predictions: 900 with hardcoded 75% (will be replaced over time)*
