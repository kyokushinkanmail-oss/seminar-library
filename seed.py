"""
初期データ投入スクリプト
デモ用のセミナー・資料・動画データを作成
"""
import os
import sys
from datetime import datetime

# Flaskアプリを読み込み
from app import app, db, generate_phone_hash
from models import User, Seminar, Attendance, Material, Video


# ============================================
# ポジショニング論 HTML資料（サンプル）
# ============================================
POSITIONING_HTML = """
<h2>ポジショニング論 — 角度と内側と外側</h2>
<p style="color:#737373; font-size:0.9rem;">2026年4月20日 臼井祐介・千田隼人</p>

<h2>1. ポジショニングとは</h2>
<p>
組手において「どこに立つか」は技術以前の問題です。
相手との距離、角度、そして自分が内側にいるか外側にいるかで、
使える技・使えない技が大きく変わります。
</p>
<p>
ポジショニングは「戦う前に勝負がつく」要素であり、
意識的にコントロールすることで組手の質が根本的に変わります。
</p>

<h2>2. 距離の三段階</h2>
<table>
<tr><th>距離</th><th>特徴</th><th>有効な技</th></tr>
<tr><td><strong>遠距離</strong></td><td>前蹴り・上段回し蹴りが届く距離</td><td>蹴り技全般、飛び込み突き</td></tr>
<tr><td><strong>中距離</strong></td><td>ワンステップで打撃が届く距離</td><td>突き・膝蹴り・中段回し蹴り</td></tr>
<tr><td><strong>近距離</strong></td><td>接触～半歩の距離</td><td>膝蹴り・肘（ルールによる）・崩し</td></tr>
</table>

<h2>3. 角度の原則</h2>
<p>
正面（0°）に立つと相手の全ての攻撃を受ける可能性があります。
<strong>15°〜30°のずれ</strong>を作ることで、相手の攻撃の半分を無効化できます。
</p>
<ul>
<li><strong>外側30°</strong> — 回し蹴り・後ろ回し蹴りのアングル</li>
<li><strong>内側15°</strong> — 突きの連打・膝蹴りのアングル</li>
<li>角度は「足の位置」で決まる — 上半身ではなく足を動かす</li>
</ul>

<h2>4. 内側と外側</h2>
<h3>内側（インサイド）のメリット</h3>
<ul>
<li>相手の前手側に入る → 相手のリードハンドを封じやすい</li>
<li>突きの距離が近い → 連打がしやすい</li>
<li>相手の強い後ろ手を避けやすい</li>
</ul>

<h3>外側（アウトサイド）のメリット</h3>
<ul>
<li>相手の死角に入りやすい → 攻撃が見えにくい</li>
<li>回し蹴り・後ろ回し蹴りの角度が取れる</li>
<li>相手が体を回さないと反撃できない → 時間的優位</li>
</ul>

<h2>5. 実戦ドリル</h2>
<h3>ドリル①：サイドステップから中段突き</h3>
<p>
構えた状態から前足を斜め前に出し、角度をつけてから中段突きを3連打。
ポイントは「足が先、手は後」。足の位置が決まってから突くこと。
</p>

<h3>ドリル②：外側回り込みから回し蹴り</h3>
<p>
相手の外側に回り込むステップを踏み、相手が正面を向き直す前に
中段回し蹴り。回り込みの角度は30°以上を意識する。
</p>

<h3>ドリル③：内側入りからの膝蹴り</h3>
<p>
前手でガードしながら相手の内側に半歩入り、
相手のリード手を押さえながら膝蹴り。
距離が近いため、膝を抱え込む動作を最小限にする。
</p>

<h2>6. まとめ</h2>
<ul>
<li>ポジショニングは「技の前に決める」最重要要素</li>
<li>15°〜30°のずれを意識するだけで組手が変わる</li>
<li>内側＝突きの距離、外側＝蹴りの距離と覚える</li>
<li>練習では「足を先に動かす」ことを意識する</li>
</ul>
"""


def seed():
    """初期データ投入"""
    with app.app_context():
        # 既存データがあればスキップ
        if Seminar.query.count() > 0:
            print("データが既に存在します。スキップします。")
            print(f"  セミナー: {Seminar.query.count()}件")
            print(f"  ユーザー: {User.query.count()}名")
            return

        print("初期データを投入中...")

        # --- セミナー作成 ---
        s1 = Seminar(
            title="臼井祐介・千田隼人",
            subtitle="【組手セミナー】ポジショニング論 — 角度と内側と外側",
            slug="2026-04-20-kumite",
            date=datetime(2026, 4, 20),
            instructors="臼井祐介, 千田隼人",
            is_published=True,
            created_at=datetime.utcnow()
        )
        s2 = Seminar(
            title="組手セミナー",
            subtitle="移動稽古の構造的理解",
            slug="2026-03-16-kihon",
            date=datetime(2026, 3, 16),
            instructors="臼井祐介",
            is_published=True,
            created_at=datetime.utcnow()
        )
        s3 = Seminar(
            title="型セミナー",
            subtitle="最破の分解と応用",
            slug="2026-02-16-kata",
            date=datetime(2026, 2, 16),
            instructors="千田隼人",
            is_published=True,
            created_at=datetime.utcnow()
        )
        # 次回セミナー（未来日付）
        s4 = Seminar(
            title="蹴り技セミナー",
            subtitle="詳細は後日お知らせ",
            slug="2026-05-18-keri",
            date=datetime(2026, 5, 18),
            instructors="臼井祐介",
            is_published=True,
            created_at=datetime.utcnow()
        )
        db.session.add_all([s1, s2, s3, s4])
        db.session.flush()  # IDを確定

        # --- 資料（HTML形式） ---
        m1 = Material(
            seminar_id=s1.id,
            title="ポジショニング論 — 角度と内側と外側",
            content_html=POSITIONING_HTML,
            is_free=False,
            price=500,  # 非出席者は購入可能
            sort_order=1
        )
        m2 = Material(
            seminar_id=s2.id,
            title="移動稽古の構造的理解",
            content_html="<h2>移動稽古の構造的理解</h2><p>（資料内容は準備中です）</p>",
            is_free=False,
            price=500,
            sort_order=1
        )
        m3 = Material(
            seminar_id=s3.id,
            title="最破の分解と応用",
            content_html="<h2>最破の分解と応用</h2><p>（資料内容は準備中です）</p>",
            is_free=False,
            price=500,
            sort_order=1
        )
        db.session.add_all([m1, m2, m3])

        # --- 動画 ---
        v1 = Video(
            seminar_id=s1.id,
            title="距離と角度の実演",
            description="ポジショニングの基本概念を実演で解説します",
            duration="12:30",
            price=500,
            sort_order=1
        )
        v2 = Video(
            seminar_id=s1.id,
            title="内側と外側のドリル",
            description="実戦ドリル3種目を段階的に解説",
            duration="18:45",
            price=500,
            sort_order=2
        )
        v3 = Video(
            seminar_id=s3.id,
            title="最破 全体の流れ",
            description="型の全体像と分解の考え方",
            duration="25:10",
            price=800,
            sort_order=1
        )
        db.session.add_all([v1, v2, v3])

        # --- デモユーザー ---
        demo_user = User(
            name="田中太郎",
            phone_hash=generate_phone_hash("090-1234-5678"),
            phone_last4="5678",
            created_at=datetime.utcnow()
        )
        db.session.add(demo_user)
        db.session.flush()

        # 田中太郎は過去2回参加
        a1 = Attendance(user_id=demo_user.id, seminar_id=s2.id, attended_at=datetime(2026, 3, 16), method="qr")
        a2 = Attendance(user_id=demo_user.id, seminar_id=s3.id, attended_at=datetime(2026, 2, 16), method="zoom")
        db.session.add_all([a1, a2])

        db.session.commit()

        print("✅ 初期データ投入完了！")
        print(f"  セミナー: {Seminar.query.count()}件")
        print(f"  資料: {Material.query.count()}件")
        print(f"  動画: {Video.query.count()}本")
        print(f"  デモユーザー: 田中太郎（090-1234-5678）")
        print(f"    - 過去参加: 組手セミナー(QR), 型セミナー(Zoom)")
        print(f"\n🌐 アプリURL: http://localhost:5000")
        print(f"🔧 管理画面: http://localhost:5000/admin?key=admin")
        print(f"📱 QRスキャン: http://localhost:5000/s/2026-04-20-kumite")


if __name__ == "__main__":
    seed()
