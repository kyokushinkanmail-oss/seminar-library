"""
Stripe Payment LinkをDBに反映
"""
import os
from dotenv import load_dotenv
load_dotenv()

from app import app, db
from models import Video, Material

LINKS = {
    "videos": {
        "距離と角度の実演": "https://buy.stripe.com/test_7sY6oH88E7w51X7bBYg7e00",
    },
    "subscribe": "https://buy.stripe.com/test_9B6eVd3So2bL1X79tQg7e01",
}

with app.app_context():
    # 動画
    for v in Video.query.all():
        if v.title in LINKS["videos"]:
            v.stripe_payment_link = LINKS["videos"][v.title]
            print(f"✅ 動画 [{v.title}] → {v.stripe_payment_link}")

    db.session.commit()
    print(f"\n🥋 添削サブスク: {LINKS['subscribe']}")
    print("完了！")
