"""
極真館組手セミナーライブラリ — メインアプリケーション
Flask + SQLite + Jinja2
"""
import os
from dotenv import load_dotenv
load_dotenv()
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort, send_from_directory
)

from database import db, init_db
from models import User, Seminar, Attendance, Purchase, Material, Video

# ============================================
# アプリ初期化
# ============================================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
_app_dir = os.path.dirname(os.path.abspath(__file__))
_data_dir = os.path.join(_app_dir, "data")
os.makedirs(_data_dir, exist_ok=True)
_default_db = f"sqlite:///{os.path.join(_data_dir, 'seminar.db')}"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", _default_db)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["STRIPE_SECRET_KEY"] = os.environ.get("STRIPE_SECRET_KEY", "")
app.config["STRIPE_PUBLISHABLE_KEY"] = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
app.config["BASE_URL"] = os.environ.get("BASE_URL", "http://localhost:5000")

db.init_app(app)

with app.app_context():
    init_db(app)


# ============================================
# ヘルパー
# ============================================
def login_required(f):
    """ログイン必須デコレータ"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("landing"))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """セッションから現在ユーザーを取得"""
    if "user_id" in session:
        return User.query.get(session["user_id"])
    return None


def generate_phone_hash(phone: str) -> str:
    """電話番号のハッシュ（検索用）"""
    normalized = phone.replace("-", "").replace(" ", "").strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


# ============================================
# 公開ページ
# ============================================
@app.route("/")
def landing():
    """トップ — 最新セミナー情報を表示"""
    latest = Seminar.query.filter(
        Seminar.is_published == True
    ).order_by(Seminar.date.desc()).first()
    upcoming = Seminar.query.filter(
        Seminar.date > datetime.utcnow(),
        Seminar.is_published == True
    ).order_by(Seminar.date.asc()).first()
    return render_template("landing.html", seminar=latest, upcoming=upcoming)


@app.route("/s/<seminar_slug>")
def seminar_landing(seminar_slug):
    """QRコードからのセミナー別ランディング"""
    seminar = Seminar.query.filter_by(slug=seminar_slug).first_or_404()
    session["pending_seminar"] = seminar.id

    # ログイン済みなら直接出席登録してライブラリへ
    if "user_id" in session:
        user = User.query.get(session["user_id"])
        if user:
            _process_pending_seminar(user)
            flash(f"「{seminar.title}」の資料をライブラリに追加しました！", "success")
            return redirect(url_for("library"))

    return render_template("landing.html", seminar=seminar, upcoming=None)


@app.route("/register", methods=["GET", "POST"])
def register():
    """新規登録"""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        if not name or not phone:
            flash("お名前と電話番号を入力してください", "error")
            return render_template("register.html", is_new=True)

        phone_hash = generate_phone_hash(phone)
        existing = User.query.filter_by(phone_hash=phone_hash).first()
        if existing:
            flash("この電話番号は既に登録されています。ログインしてください。", "info")
            return redirect(url_for("login"))

        user = User(
            name=name,
            phone_hash=phone_hash,
            phone_last4=phone.replace("-", "")[-4:],
            created_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        _process_pending_seminar(user)
        flash("登録が完了しました！セミナー資料をライブラリに追加しました。", "success")
        return redirect(url_for("library"))

    return render_template("register.html", is_new=True)


@app.route("/login", methods=["GET", "POST"])
def login():
    """ログイン（電話番号）"""
    if request.method == "GET":
        return render_template("register.html", is_new=False)

    phone = request.form.get("phone", "").strip()
    if not phone:
        flash("電話番号を入力してください", "error")
        return render_template("register.html", is_new=False)

    phone_hash = generate_phone_hash(phone)
    user = User.query.filter_by(phone_hash=phone_hash).first()
    if not user:
        flash("この電話番号は登録されていません。新規登録してください。", "error")
        return redirect(url_for("register"))

    session["user_id"] = user.id
    _process_pending_seminar(user)
    flash(f"おかえりなさい、{user.name}さん！", "success")
    return redirect(url_for("library"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


def _process_pending_seminar(user):
    """ログイン/登録後に保留中のセミナー出席を処理"""
    seminar_id = session.pop("pending_seminar", None)
    if seminar_id:
        existing = Attendance.query.filter_by(
            user_id=user.id, seminar_id=seminar_id
        ).first()
        if not existing:
            att = Attendance(
                user_id=user.id,
                seminar_id=seminar_id,
                attended_at=datetime.utcnow(),
                method="qr"
            )
            db.session.add(att)
            db.session.commit()


# ============================================
# ライブラリ（ログイン後）
# ============================================
@app.route("/library")
@login_required
def library():
    """マイライブラリ — 参加セミナー一覧"""
    user = get_current_user()
    attendances = Attendance.query.filter_by(user_id=user.id)\
        .order_by(Attendance.attended_at.desc()).all()
    seminar_ids = [a.seminar_id for a in attendances]
    seminars = Seminar.query.filter(Seminar.id.in_(seminar_ids)).all() if seminar_ids else []
    # 出席順に並べる
    seminar_map = {s.id: s for s in seminars}
    ordered = [seminar_map[sid] for sid in seminar_ids if sid in seminar_map]

    # 購入済みの動画・資料
    purchases = Purchase.query.filter_by(
        user_id=user.id, status="completed"
    ).all()
    purchased_video_ids = {p.video_id for p in purchases if p.video_id}
    purchased_material_ids = {p.material_id for p in purchases if p.material_id}

    # 次回セミナー
    upcoming = Seminar.query.filter(
        Seminar.date > datetime.utcnow(),
        Seminar.is_published == True
    ).order_by(Seminar.date.asc()).first()

    return render_template(
        "library.html",
        user=user,
        seminars=ordered,
        attendance_count=len(attendances),
        upcoming=upcoming,
        purchased_video_ids=purchased_video_ids,
        purchased_material_ids=purchased_material_ids,
    )


@app.route("/seminar/<int:seminar_id>")
@login_required
def seminar_detail(seminar_id):
    """セミナー詳細 — 資料(HTML)閲覧 + 動画 + 購入"""
    user = get_current_user()
    seminar = Seminar.query.get_or_404(seminar_id)

    # 出席チェック
    attendance = Attendance.query.filter_by(
        user_id=user.id, seminar_id=seminar_id
    ).first()

    # 資料一覧
    materials = Material.query.filter_by(seminar_id=seminar_id).all()

    # 動画一覧
    videos = Video.query.filter_by(seminar_id=seminar_id).all()

    # Zoom参加者チェック（出席方法がzoomの場合は動画無料）
    zoom_attended = attendance and attendance.method == "zoom"

    # 購入済みチェック
    purchases = Purchase.query.filter_by(
        user_id=user.id, status="completed"
    ).all()
    purchased_video_ids = {p.video_id for p in purchases if p.video_id}
    purchased_material_ids = {p.material_id for p in purchases if p.material_id}

    return render_template(
        "seminar_detail.html",
        user=user,
        seminar=seminar,
        attendance=attendance,
        materials=materials,
        videos=videos,
        zoom_attended=zoom_attended,
        purchased_video_ids=purchased_video_ids,
        purchased_material_ids=purchased_material_ids,
        stripe_key=app.config["STRIPE_PUBLISHABLE_KEY"],
    )


@app.route("/material/<int:material_id>")
@login_required
def view_material(material_id):
    """資料をHTML形式で閲覧"""
    user = get_current_user()
    material = Material.query.get_or_404(material_id)
    seminar = Seminar.query.get(material.seminar_id)

    # アクセス権チェック：出席者 or 購入者
    attendance = Attendance.query.filter_by(
        user_id=user.id, seminar_id=material.seminar_id
    ).first()
    purchased = Purchase.query.filter_by(
        user_id=user.id, material_id=material_id, status="completed"
    ).first()

    if not attendance and not purchased and not material.is_free:
        flash("この資料にアクセスするには、セミナーへの参加または購入が必要です。", "error")
        return redirect(url_for("library"))

    return render_template(
        "material_view.html",
        material=material,
        seminar=seminar,
    )


@app.route("/video/<int:video_id>")
@login_required
def view_video(video_id):
    """動画ページ"""
    user = get_current_user()
    video = Video.query.get_or_404(video_id)
    seminar = Seminar.query.get(video.seminar_id)

    # Zoom参加者は無料
    attendance = Attendance.query.filter_by(
        user_id=user.id, seminar_id=video.seminar_id
    ).first()
    zoom_attended = attendance and attendance.method == "zoom"

    # 購入済みチェック
    purchased = Purchase.query.filter_by(
        user_id=user.id, video_id=video_id, status="completed"
    ).first()

    if not zoom_attended and not purchased:
        flash("この動画を視聴するには購入が必要です。", "error")
        return redirect(url_for("seminar_detail", seminar_id=video.seminar_id))

    return render_template(
        "video_view.html",
        video=video,
        seminar=seminar,
    )


# ============================================
# 購入（Stripe Payment Links）
# ============================================
@app.route("/purchase/video/<int:video_id>", methods=["POST"])
@login_required
def purchase_video(video_id):
    """動画購入 — Stripe Payment Linkへリダイレクト"""
    user = get_current_user()
    video = Video.query.get_or_404(video_id)

    # 既に購入済みか確認
    existing = Purchase.query.filter_by(
        user_id=user.id, video_id=video_id, status="completed"
    ).first()
    if existing:
        return redirect(url_for("view_video", video_id=video_id))

    # 購入レコード作成（pending状態）
    purchase = Purchase(
        user_id=user.id,
        video_id=video_id,
        item_type="video",
        amount=video.price,
        status="pending",
        created_at=datetime.utcnow()
    )
    db.session.add(purchase)
    db.session.commit()

    # Stripe Payment Linkがある場合はリダイレクト
    if video.stripe_payment_link:
        return redirect(
            f"{video.stripe_payment_link}?client_reference_id=purchase_{purchase.id}"
        )

    # なければデモモードで即完了
    purchase.status = "completed"
    purchase.completed_at = datetime.utcnow()
    db.session.commit()
    flash("購入が完了しました！動画を視聴できます。", "success")
    return redirect(url_for("view_video", video_id=video_id))


@app.route("/purchase/material/<int:material_id>", methods=["POST"])
@login_required
def purchase_material(material_id):
    """資料購入"""
    user = get_current_user()
    material = Material.query.get_or_404(material_id)

    existing = Purchase.query.filter_by(
        user_id=user.id, material_id=material_id, status="completed"
    ).first()
    if existing:
        return redirect(url_for("view_material", material_id=material_id))

    purchase = Purchase(
        user_id=user.id,
        material_id=material_id,
        item_type="material",
        amount=material.price or 0,
        status="pending",
        created_at=datetime.utcnow()
    )
    db.session.add(purchase)
    db.session.commit()

    if material.stripe_payment_link:
        return redirect(
            f"{material.stripe_payment_link}?client_reference_id=purchase_{purchase.id}"
        )

    # デモモード
    purchase.status = "completed"
    purchase.completed_at = datetime.utcnow()
    db.session.commit()
    flash("購入が完了しました！資料を閲覧できます。", "success")
    return redirect(url_for("view_material", material_id=material_id))


@app.route("/subscribe")
@login_required
def subscribe():
    """添削サブスク案内ページ"""
    user = get_current_user()
    return render_template("subscribe.html", user=user)


# ============================================
# Stripe Webhook
# ============================================
@app.route("/webhook/stripe", methods=["POST"])
def stripe_webhook():
    """Stripe決済完了通知を処理"""
    import stripe
    stripe.api_key = app.config["STRIPE_SECRET_KEY"]
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        else:
            event = stripe.Event.construct_from(
                request.get_json(), stripe.api_key
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    if event["type"] == "checkout.session.completed":
        session_data = event["data"]["object"]
        ref = session_data.get("client_reference_id", "")
        if ref.startswith("purchase_"):
            purchase_id = int(ref.replace("purchase_", ""))
            purchase = Purchase.query.get(purchase_id)
            if purchase:
                purchase.status = "completed"
                purchase.completed_at = datetime.utcnow()
                purchase.stripe_session_id = session_data.get("id")
                db.session.commit()

    return jsonify({"status": "ok"}), 200


# ============================================
# 管理 API（セミナー作成・QR生成用）
# ============================================
@app.route("/admin")
def admin_dashboard():
    """管理ダッシュボード"""
    admin_key = request.args.get("key", "")
    if admin_key != os.environ.get("ADMIN_KEY", "admin"):
        abort(403)
    seminars = Seminar.query.order_by(Seminar.date.desc()).all()
    return render_template("admin/dashboard.html", seminars=seminars)


@app.route("/admin/seminar/new", methods=["GET", "POST"])
def admin_new_seminar():
    """新規セミナー作成"""
    admin_key = request.args.get("key", "") or request.form.get("key", "")
    if admin_key != os.environ.get("ADMIN_KEY", "admin"):
        abort(403)

    if request.method == "POST":
        title = request.form["title"]
        subtitle = request.form.get("subtitle", "")
        date_str = request.form["date"]
        instructors = request.form.get("instructors", "")
        slug = request.form.get("slug", "").strip()

        if not slug:
            slug = f"{date_str}-{title[:10]}".replace(" ", "-").lower()

        seminar = Seminar(
            title=title,
            subtitle=subtitle,
            date=datetime.strptime(date_str, "%Y-%m-%d"),
            instructors=instructors,
            slug=slug,
            is_published=True,
            created_at=datetime.utcnow()
        )
        db.session.add(seminar)
        db.session.commit()
        flash(f"セミナー「{title}」を作成しました", "success")
        return redirect(url_for("admin_dashboard", key=admin_key))

    return render_template("admin/new_seminar.html", key=admin_key)


@app.route("/admin/seminar/<int:seminar_id>/qr")
def admin_qr(seminar_id):
    """QRコード表示"""
    admin_key = request.args.get("key", "")
    if admin_key != os.environ.get("ADMIN_KEY", "admin"):
        abort(403)
    seminar = Seminar.query.get_or_404(seminar_id)
    qr_url = f"{app.config['BASE_URL']}/s/{seminar.slug}"
    return render_template("admin/qr.html", seminar=seminar, qr_url=qr_url, key=admin_key)


@app.route("/admin/seminar/<int:seminar_id>/zoom", methods=["POST"])
def admin_mark_zoom(seminar_id):
    """Zoom参加者を一括登録"""
    admin_key = request.form.get("key", "")
    if admin_key != os.environ.get("ADMIN_KEY", "admin"):
        abort(403)

    phones = request.form.get("phones", "").strip().split("\n")
    count = 0
    for phone in phones:
        phone = phone.strip()
        if not phone:
            continue
        phone_hash = generate_phone_hash(phone)
        user = User.query.filter_by(phone_hash=phone_hash).first()
        if user:
            existing = Attendance.query.filter_by(
                user_id=user.id, seminar_id=seminar_id
            ).first()
            if existing:
                existing.method = "zoom"
            else:
                att = Attendance(
                    user_id=user.id,
                    seminar_id=seminar_id,
                    attended_at=datetime.utcnow(),
                    method="zoom"
                )
                db.session.add(att)
            count += 1

    db.session.commit()
    flash(f"Zoom参加者 {count}名を登録しました", "success")
    return redirect(url_for("admin_dashboard", key=admin_key))


# ============================================
# 静的ファイル
# ============================================
@app.route("/static/materials/<path:filename>")
def serve_material(filename):
    return send_from_directory("static/materials", filename)


# ============================================
# 起動
# ============================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
