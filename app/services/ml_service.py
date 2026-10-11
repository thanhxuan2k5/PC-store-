import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from app.services.csv_sync_service import get_sales_dataframe

# ==========================================
# 1. SENTIMENT CLASSIFICATION FOR REVIEWS
# ==========================================
class SentimentModel:
    def __init__(self):
        self.pipeline = None
        self._train_default_model()

    def _train_default_model(self):
        texts = [
            "Sản phẩm rất tốt, giao hàng nhanh chóng, đóng gói cẩn thận",
            "Máy chạy rất mượt mà, chơi game max setting không bị drop fps",
            "Màn hình màu sắc cực đẹp, 144hz mượt mà, đáng tiền",
            "Bàn phím gõ êm, switch bấm nảy, led rgb đẹp",
            "Card màn hình tản nhiệt mát mẻ, hiệu năng tuyệt vời",
            "Laptop mỏng nhẹ, pin trâu dùng được 8 tiếng liên tục",
            "Nhân viên GearVN tư vấn nhiệt tình, hỗ trợ cài win miễn phí",
            "Chất lượng vượt mong đợi, 5 sao cho shop",
            "Sản phẩm dùng tạm ổn trong tầm giá, không có gì nổi bật",
            "Giao hàng đúng hẹn nhưng hộp hơi móp nhẹ bên ngoài",
            "Máy bình thường, dùng văn phòng thì được",
            "Máy bị lỗi màn hình xanh liên tục, rất thất vọng",
            "Giao hàng quá chậm, trễ hẹn 3 ngày",
            "Sản phẩm bị trầy xước khi mở hộp, quạt kêu to",
            "Bàn phím bị liệt nút space, đổi trả rất phức tạp",
            "Nóng kinh khủng, nhiệt độ cpu lên tới 95 độ",
            "Chất lượng quá tệ, dùng được 2 ngày thì hỏng nguồn"
        ]
        labels = [
            "positive", "positive", "positive", "positive", "positive", "positive", "positive", "positive",
            "neutral", "neutral", "neutral",
            "negative", "negative", "negative", "negative", "negative", "negative"
        ]
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ('clf', LogisticRegression(C=1.0, max_iter=200))
        ])
        self.pipeline.fit(texts, labels)

    def predict(self, text: str) -> Tuple[str, float]:
        if not text or len(text.strip()) < 2:
            return "neutral", 0.5
        probs = self.pipeline.predict_proba([text])[0]
        classes = self.pipeline.classes_
        idx = np.argmax(probs)
        return classes[idx], round(float(probs[idx]), 3)

    def summarize_reviews(self, reviews: List[Any]) -> Dict[str, Any]:
        """Tóm tắt tổng quan cảm xúc của toàn bộ đánh giá sản phẩm."""
        if not reviews:
            return {
                "total": 0,
                "positive_percent": 0.0,
                "neutral_percent": 0.0,
                "negative_percent": 0.0,
                "summary": "Chưa có đánh giá nào cho sản phẩm này."
            }

        counts = {"positive": 0, "neutral": 0, "negative": 0}
        for rev in reviews:
            label = getattr(rev, "sentiment_label", "positive") or "positive"
            counts[label] = counts.get(label, 0) + 1

        total = len(reviews)
        pos_pct = round((counts["positive"] / total) * 100, 1)
        neu_pct = round((counts["neutral"] / total) * 100, 1)
        neg_pct = round((counts["negative"] / total) * 100, 1)

        summary = f"Sản phẩm đạt {pos_pct}% phản hồi tích cực từ khách hàng đã mua."
        return {
            "total": total,
            "positive_percent": pos_pct,
            "neutral_percent": neu_pct,
            "negative_percent": neg_pct,
            "summary": summary
        }

sentiment_model = SentimentModel()

def classify_review_sentiment(text: str) -> Tuple[str, float]:
    return sentiment_model.predict(text)

# ==========================================
# 2. TIME-SERIES SALES FORECAST (RIDGE REGRESSION)
# ==========================================
class SalesForecastModel:
    def __init__(self):
        self.model = Ridge(alpha=1.0)
        self.is_fitted = False

    def train_and_forecast(self, hours_ahead: int = 12) -> List[Dict[str, Any]]:
        df = get_sales_dataframe()
        if df.empty or len(df) < 5:
            now = datetime.now()
            return [{"timestamp": (now + timedelta(hours=i)).strftime("%Y-%m-%d %H:00"), "predicted_revenue": 15000000.0} for i in range(1, hours_ahead + 1)]

        df['created_at'] = pd.to_datetime(df['created_at'])
        df = df.set_index('created_at').resample('1h')['total_price'].sum().reset_index()
        df['hour'] = df['created_at'].dt.hour
        df['dayofweek'] = df['created_at'].dt.dayofweek

        X = df[['hour', 'dayofweek']]
        y = df['total_price']
        self.model.fit(X, y)
        self.is_fitted = True

        last_time = df['created_at'].max()
        forecasts = []
        for i in range(1, hours_ahead + 1):
            next_t = last_time + timedelta(hours=i)
            pred = max(0.0, float(self.model.predict([[next_t.hour, next_t.dayofweek]])[0]))
            forecasts.append({"timestamp": next_t.strftime("%Y-%m-%d %H:00"), "predicted_revenue": round(pred, 2)})
        return forecasts

forecast_model = SalesForecastModel()

def forecast_sales(hours: int = 12) -> List[Dict[str, Any]]:
    return forecast_model.train_and_forecast(hours)
