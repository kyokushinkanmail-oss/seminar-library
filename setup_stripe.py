"""
Stripe商品・Payment Link自動作成スクリプト
セミナー動画・資料・添削サブスクの決済リンクを一括作成
"""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

import stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

if not stripe.api_key:
    print("❌ STRIPE_SECRET_KEY が .env に設定されていません")
    sys.exit(1)


def create_product_and_link(name, price_yen, description="", recurring=False):
    """商品を作成してPayment Linkを返す"""
    # 商品作成
    product = stripe.Product.create(
        name=name,
        description=description or name,
    )
    print(f"  商品作成: {product.id} — {name}")

    # 価格作成
    price_params = {
        "product": product.id,
        "unit_amount": price_yen,
        "currency": "jpy",
    }
    if recurring:
        price_params["recurring"] = {"interval": "month"}

    price = stripe.Price.create(**price_params)
    print(f"  価格作成: {price.id} — ¥{price_yen}")

    # Payment Link作成
    link = stripe.PaymentLink.create(
        line_items=[{"price": price.id, "quantity": 1}],
        after_completion={
            "type": "redirect",
            "redirect": {
                "url": os.environ.get("BASE_URL", "http://localhost:5000") + "/library"
            }
        }
    )
    print(f"  Payment Link: {link.url}")
    return link.url


def main():
    print("=" * 50)
    print("極真館組手セミナー — Stripe商品セットアップ")
    print("=" * 50)
    print()

    # --- 動画商品 ---
    print("【動画商品】")
    video_links = {}

    print("\n1. 距離と角度の実演（¥500）")
    video_links["距離と角度の実演"] = create_product_and_link(
        "セミナー動画：距離と角度の実演",
        500,
        "ポジショニング論 — 角度と内側と外側（12:30）"
    )

    print("\n2. 内側と外側のドリル（¥500）")
    video_links["内側と外側のドリル"] = create_product_and_link(
        "セミナー動画：内側と外側のドリル",
        500,
        "ポジショニング論 — 実戦ドリル3種目（18:45）"
    )

    print("\n3. 最破 全体の流れ（¥800）")
    video_links["最破 全体の流れ"] = create_product_and_link(
        "セミナー動画：最破 全体の流れ",
        800,
        "型セミナー — 最破の分解と応用（25:10）"
    )

    # --- 資料商品 ---
    print("\n【資料商品】")
    material_links = {}

    print("\n4. ポジショニング論 資料（¥500）")
    material_links["ポジショニング論"] = create_product_and_link(
        "セミナー資料：ポジショニング論 — 角度と内側と外側",
        500,
        "HTML形式のセミナー資料"
    )

    print("\n5. 移動稽古の構造的理解 資料（¥500）")
    material_links["移動稽古"] = create_product_and_link(
        "セミナー資料：移動稽古の構造的理解",
        500,
        "HTML形式のセミナー資料"
    )

    print("\n6. 最破の分解と応用 資料（¥500）")
    material_links["最破"] = create_product_and_link(
        "セミナー資料：最破の分解と応用",
        500,
        "HTML形式のセミナー資料"
    )

    # --- 添削サブスク ---
    print("\n【添削サブスクリプション】")
    print("\n7. 組手動画 添削サービス（¥300/月）")
    sub_link = create_product_and_link(
        "組手動画 添削サービス",
        300,
        "月額300円 — 先生があなたの組手動画を直接アドバイス",
        recurring=True
    )

    # --- DBに反映 ---
    print("\n" + "=" * 50)
    print("Payment LinkをDBに反映中...")

    from app import app, db
    from models import Video, Material

    with app.app_context():
        # 動画
        videos = Video.query.all()
        for v in videos:
            if v.title in video_links:
                v.stripe_payment_link = video_links[v.title]
                print(f"  動画 [{v.title}] → リンク設定済み")

        # 資料
        materials = Material.query.all()
        for m in materials:
            for key, link in material_links.items():
                if key in m.title:
                    m.stripe_payment_link = link
                    print(f"  資料 [{m.title}] → リンク設定済み")
                    break

        db.session.commit()

    print("\n✅ Stripe商品セットアップ完了！")
    print(f"\n🥋 添削サブスク: {sub_link}")
    print("  ↑ このURLをsubscribe.htmlの申し込みボタンに設定してください")

    # サブスクリンクを保存
    with open(".stripe_subscribe_link", "w") as f:
        f.write(sub_link)
    print(f"\n  （.stripe_subscribe_link に保存済み）")


if __name__ == "__main__":
    main()
