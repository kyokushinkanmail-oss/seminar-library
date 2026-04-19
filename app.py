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
_database_url = os.environ.get("DATABASE_URL", _default_db)
# Render の Postgres は postgres:// で始まるが SQLAlchemy 2.x では postgresql:// が必要
if _database_url.startswith("postgres://"):
    _database_url = _database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = _database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["STRIPE_SECRET_KEY"] = os.environ.get("STRIPE_SECRET_KEY", "")
app.config["STRIPE_PUBLISHABLE_KEY"] = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
app.config["BASE_URL"] = os.environ.get("BASE_URL", "http://localhost:5000")

# セッションを365日間保持（iPhone PWAでログイン状態を維持）
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = not app.debug

db.init_app(app)

with app.app_context():
    init_db(app)


def _ensure_kinni_material():
    """4/19セミナー4部「肘・膝」資料がDBに無ければ追加する（冪等）"""
    try:
        from models import Material, Seminar
        # 既に存在していたらスキップ
        existing = Material.query.filter(
            (Material.file_path == "materials/kinni.pdf")
            | (Material.title.like("%肘%膝%"))
        ).first()
        # ファイルからHTMLを常にロード（更新反映のため）
        body_path_check = os.path.join(os.path.dirname(__file__), "static", "materials", "kinni_body.html")
        latest_html = None
        if os.path.exists(body_path_check):
            with open(body_path_check, "r", encoding="utf-8") as f:
                latest_html = f.read()

        if existing:
            changed = False
            if not existing.file_path:
                existing.file_path = "materials/kinni.pdf"
                changed = True
            # ファイルのHTMLが更新されていたらDBに反映
            if latest_html and existing.content_html != latest_html:
                existing.content_html = latest_html
                changed = True
            if changed:
                db.session.commit()
            return

        # ポジショニング資料と同じセミナー（4/19）を取得
        base = Material.query.filter(Material.title.like("%ポジショニング%")).first()
        seminar_id = base.seminar_id if base else None
        if not seminar_id:
            # フォールバック：最初のセミナー
            first_seminar = Seminar.query.order_by(Seminar.date.desc()).first()
            if not first_seminar:
                return
            seminar_id = first_seminar.id

        body_path = os.path.join(os.path.dirname(__file__), "static", "materials", "kinni_body.html")
        if not os.path.exists(body_path):
            return
        with open(body_path, "r", encoding="utf-8") as f:
            html = f.read()

        m = Material(
            seminar_id=seminar_id,
            title="肘・膝セミナー — 近距離戦の最強武器",
            content_html=html,
            file_path="materials/kinni.pdf",
            is_free=False,
            price=500,
            sort_order=4,
        )
        db.session.add(m)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[ensure_kinni] skipped: {e}")


with app.app_context():
    _ensure_kinni_material()


def _ensure_april19_split():
    """4/19セミナーを4コマ（一部〜四部）に分割する（冪等）。

    - 既存Seminarは「一部」として維持（slug保持 → 印刷済QR・既存Attendanceそのまま）
    - 二部/三部/四部 のSeminarを新規作成（slug: <base>-2, -3, -4）
    - 肘・膝Materialを四部に付け替える
    - ポジショニングMaterialは一部に残す
    """
    try:
        from models import Material, Seminar
        base_mat = Material.query.filter(Material.title.like("%ポジショニング%")).first()
        if not base_mat:
            return
        base_seminar = Seminar.query.get(base_mat.seminar_id)
        if not base_seminar:
            return

        # 既に分割済みならスキップ
        part2_slug = f"{base_seminar.slug}-2"
        if Seminar.query.filter_by(slug=part2_slug).first():
            return

        # 一部タイトル整理
        if "一部" not in base_seminar.title:
            base_seminar.title = f"{base_seminar.title}（一部・ポジショニング）"

        new_parts = [
            ("二部", 2),
            ("三部", 3),
            ("四部・肘膝", 4),
        ]
        created = {}
        for label, n in new_parts:
            slug_n = f"{base_seminar.slug}-{n}"
            existing = Seminar.query.filter_by(slug=slug_n).first()
            if existing:
                created[n] = existing
                continue
            s = Seminar(
                title=f"4/19 組手セミナー（{label}）",
                subtitle=base_seminar.subtitle,
                slug=slug_n,
                date=base_seminar.date,
                instructors=base_seminar.instructors,
                description=base_seminar.description,
                is_published=True,
            )
            db.session.add(s)
            db.session.flush()
            created[n] = s

        # 肘・膝Materialを四部へ付け替え
        kinni = Material.query.filter(
            (Material.title.like("%肘%膝%")) | (Material.file_path == "materials/kinni.pdf")
        ).first()
        if kinni and 4 in created:
            kinni.seminar_id = created[4].id

        db.session.commit()
        print(f"[ensure_april19_split] 4/19 split completed (base slug: {base_seminar.slug})")
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[ensure_april19_split] skipped: {e}")


with app.app_context():
    _ensure_april19_split()


def _ensure_april19_schedule():
    """4/19の4コマの正式タイトル・副題・時刻・資料配置を設定する（冪等）。

    実際のスケジュール:
      一部 10:00-12:00 ポジショニングとアングル（資料: ポジショニング）
      二部 13:00-15:00 技術への展開: 肘・膝編（資料: 肘・膝）
      三部 16:00-18:00 オンライン組手研究会（資料なし）
      四部 19:00-21:00 組手会（資料なし）
    """
    try:
        from models import Material, Seminar
        from datetime import datetime

        base_mat = Material.query.filter(Material.title.like("%ポジショニング%")).first()
        if not base_mat:
            return
        base = Seminar.query.get(base_mat.seminar_id)
        if not base:
            return

        # 4コマ分のセミナーを取得
        parts = {1: base}
        for n in (2, 3, 4):
            s = Seminar.query.filter_by(slug=f"{base.slug}-{n}").first()
            if not s:
                return  # split未実行なら諦める
            parts[n] = s

        meta = {
            1: {
                "title": "4/19 組手セミナー 一部（10:00-12:00）",
                "subtitle": "ポジショニングとアングル — 有利を作る配置の本質",
                "description": (
                    "ポジショニングが大事だと言われますが、位置だけでは有利は作れません。"
                    "鍵になるのはアングルという概念です。"
                    "今回はポジショニングとアングルの関係から、なぜ有利が生まれるのかを整理し、"
                    "実戦で使える形まで落とし込みます。これが理解出来れば、組手は圧倒的に変わります。"
                ),
                "date": datetime(2026, 4, 19, 10, 0),
            },
            2: {
                "title": "4/19 組手セミナー 二部（13:00-15:00）",
                "subtitle": "技術への展開：肘・膝編（接近戦）— 避けられない近距離戦の武器",
                "description": (
                    "競技の性質上、避けることのできない接近戦。そこで差を生むのが、肘と膝です。"
                    "膝は昔からある技術ですが、肘は近年、有効な技術として試合の場に現れてきています。"
                    "今回は基本形の確認から入り、実際の組手の中でどう使うのかまで落とし込みます。"
                    "接近戦を制することが、試合を制することに直結します。"
                ),
                "date": datetime(2026, 4, 19, 13, 0),
            },
            3: {
                "title": "4/19 組手セミナー 三部（16:00-18:00）",
                "subtitle": "オンライン組手研究会 — 質問回答セッション",
                "description": (
                    "前回に引き続き、組手や技術に関する疑問に、時間の許す限り答えていくセッションです。"
                    "事前にWEBで質問を募集し、当日はオンラインからのリアルタイム質問にも対応します。"
                ),
                "date": datetime(2026, 4, 19, 16, 0),
            },
            4: {
                "title": "4/19 組手セミナー 四部（19:00-21:00）",
                "subtitle": "組手会 — 学んだ技術の実戦検証",
                "description": (
                    "当日の内容はもちろん、組手中に気付いたことや必要なことを"
                    "アドバイスしながら行います。"
                ),
                "date": datetime(2026, 4, 19, 19, 0),
            },
        }

        for n, m in meta.items():
            s = parts[n]
            s.title = m["title"]
            s.subtitle = m["subtitle"]
            s.description = m["description"]
            s.date = m["date"]

        # 肘・膝Materialを二部に付け替える（以前は四部に配置した）
        kinni = Material.query.filter(
            (Material.title.like("%肘%膝%")) | (Material.file_path == "materials/kinni.pdf")
        ).first()
        if kinni and kinni.seminar_id != parts[2].id:
            kinni.seminar_id = parts[2].id

        db.session.commit()
        print(f"[ensure_april19_schedule] schedule metadata synced")
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[ensure_april19_schedule] skipped: {e}")


with app.app_context():
    _ensure_april19_schedule()


def _ensure_3bu_material():
    """4/19セミナー3部「オンライン組手研究会」のMaterial（まとめ+動画）を追加/同期する（冪等）"""
    try:
        from models import Material, Seminar
        # 3部のセミナーを取得
        seminar = Seminar.query.filter_by(slug="2026-04-19-kumite-3").first()
        if not seminar:
            return

        # ファイルからHTMLを常にロード（更新反映のため）
        body_path = os.path.join(os.path.dirname(__file__), "static", "materials", "3bu_body.html")
        latest_html = None
        if os.path.exists(body_path):
            with open(body_path, "r", encoding="utf-8") as f:
                latest_html = f.read()
        if not latest_html:
            return

        existing = Material.query.filter_by(seminar_id=seminar.id).first()
        if existing:
            changed = False
            target_title = "組手指南録 — 質問回答セミナーまとめ + 動画"
            if existing.title != target_title:
                existing.title = target_title
                changed = True
            if existing.content_html != latest_html:
                existing.content_html = latest_html
                changed = True
            # 動画/レポート表示が本体なのでPDFは未設定
            if existing.file_path:
                existing.file_path = None
                changed = True
            if changed:
                db.session.commit()
            return

        m = Material(
            seminar_id=seminar.id,
            title="組手指南録 — 質問回答セミナーまとめ + 動画",
            content_html=latest_html,
            file_path=None,
            is_free=False,
            price=500,
            sort_order=1,
        )
        db.session.add(m)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[ensure_3bu_material] skipped: {e}")


with app.app_context():
    _ensure_3bu_material()



# ============================================
# ヘルパー
# ============================================
def login_required(f):
    """ログイン必須デコレータ"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("landing"))
        # DBにユーザーが存在するか確認（DB再作成後の古いセッション対策）
        user = User.query.get(session["user_id"])
        if user is None:
            session.clear()
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
        branch_name = request.form.get("branch_name", "").strip()
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        if not name or not phone or not branch_name:
            flash("支部名・お名前・電話番号をすべて入力してください", "error")
            return render_template("register.html", is_new=True)

        phone_hash = generate_phone_hash(phone)
        existing = User.query.filter_by(phone_hash=phone_hash).first()
        if existing:
            flash("この電話番号は既に登録されています。ログインしてください。", "info")
            return redirect(url_for("login"))

        user = User(
            name=name,
            branch_name=branch_name,
            phone_hash=phone_hash,
            phone_last4=phone.replace("-", "")[-4:],
            created_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()

        session.permanent = True
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

    session.permanent = True
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

    # 資料ごとのスライド画像設定（file_pathのbasename stemで分岐）
    slide_config_map = {
        "positioning": {"dir": "slides", "count": 20},
        "kinni": {"dir": "slides_kinni", "count": 16},
    }
    slide_info = None
    if material.file_path:
        stem = os.path.splitext(os.path.basename(material.file_path))[0]
        slide_info = slide_config_map.get(stem)

    return render_template(
        "material_view.html",
        material=material,
        seminar=seminar,
        slide_info=slide_info,
    )


@app.route("/material/<int:material_id>/download")
@login_required
def download_material(material_id):
    """資料PDFをダウンロード（アクセス権チェック付き）"""
    user = get_current_user()
    material = Material.query.get_or_404(material_id)

    # アクセス権チェック：出席者 or 購入者 or 無料
    attendance = Attendance.query.filter_by(
        user_id=user.id, seminar_id=material.seminar_id
    ).first()
    purchased = Purchase.query.filter_by(
        user_id=user.id, material_id=material_id, status="completed"
    ).first()

    if not attendance and not purchased and not material.is_free:
        flash("この資料にアクセスするには、セミナーへの参加または購入が必要です。", "error")
        return redirect(url_for("library"))

    if not material.file_path:
        flash("この資料にはダウンロード可能なファイルがありません。", "error")
        return redirect(url_for("view_material", material_id=material_id))

    # file_path は "materials/positioning.pdf" のように static 配下の相対パス
    # セキュリティ：ディレクトリトラバーサルを防ぐ
    safe_name = os.path.basename(material.file_path)
    # ?dl=1 が指定された場合のみ強制ダウンロード（Files.appへ保存）
    # それ以外はインライン表示（iframeプレビュー・新規タブ表示用）
    force_download = request.args.get("dl") == "1"
    return send_from_directory(
        os.path.join(_app_dir, "static", "materials"),
        safe_name,
        as_attachment=force_download,
        download_name=f"{material.title}.pdf",
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


@app.route("/admin/material/<int:material_id>/qr")
def admin_material_qr(material_id):
    """資料QRコード表示（資料閲覧ページへのリンク）"""
    admin_key = request.args.get("key", "")
    if admin_key != os.environ.get("ADMIN_KEY", "admin"):
        abort(403)
    material = Material.query.get_or_404(material_id)
    seminar = Seminar.query.get(material.seminar_id)
    qr_url = f"{app.config['BASE_URL']}/material/{material.id}"
    return render_template(
        "admin/material_qr.html",
        material=material,
        seminar=seminar,
        qr_url=qr_url,
        key=admin_key,
    )


def _make_qr_png(url: str) -> bytes:
    """URLからPNGのQRコードを生成してbytesで返す（サーバサイド、確実にスキャン可能）"""
    import io
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=12,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e2761", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@app.route("/admin/seminar/<int:seminar_id>/qr.png")
def admin_seminar_qr_png(seminar_id):
    """セミナーQR（PNG直生成。クライアントqrcodejs非依存で確実）"""
    admin_key = request.args.get("key", "")
    if admin_key != os.environ.get("ADMIN_KEY", "admin"):
        abort(403)
    seminar = Seminar.query.get_or_404(seminar_id)
    qr_url = f"{app.config['BASE_URL']}/s/{seminar.slug}"
    from flask import Response
    return Response(_make_qr_png(qr_url), mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=300"})


@app.route("/admin/material/<int:material_id>/qr.png")
def admin_material_qr_png(material_id):
    """資料QR（PNG直生成。クライアントqrcodejs非依存で確実）"""
    admin_key = request.args.get("key", "")
    if admin_key != os.environ.get("ADMIN_KEY", "admin"):
        abort(403)
    material = Material.query.get_or_404(material_id)
    qr_url = f"{app.config['BASE_URL']}/material/{material.id}"
    from flask import Response
    return Response(_make_qr_png(qr_url), mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=300"})



@app.route("/admin/seminar/<int:seminar_id>/attendees")
def admin_attendees(seminar_id):
    """登録者（出席者）一覧"""
    admin_key = request.args.get("key", "")
    if admin_key != os.environ.get("ADMIN_KEY", "admin"):
        abort(403)
    seminar = Seminar.query.get_or_404(seminar_id)
    # 出席記録と user を結合して取得
    rows = (
        db.session.query(Attendance, User)
        .join(User, Attendance.user_id == User.id)
        .filter(Attendance.seminar_id == seminar_id)
        .order_by(Attendance.attended_at.desc())
        .all()
    )
    return render_template(
        "admin/attendees.html",
        seminar=seminar,
        rows=rows,
        key=admin_key,
    )


@app.route("/admin/users")
def admin_users():
    """全登録ユーザー一覧"""
    admin_key = request.args.get("key", "")
    if admin_key != os.environ.get("ADMIN_KEY", "admin"):
        abort(403)
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users, key=admin_key)


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


@app.route("/admin/cleanup")
def admin_cleanup():
    """本番環境の整理用ワンショットエンドポイント（2026-04-20セミナー向け）
    - 指定動画を削除
    - 指定セミナーを非公開化
    Usage: /admin/cleanup?key=<ADMIN_KEY>
    """
    admin_key = request.args.get("key", "")
    if admin_key != os.environ.get("ADMIN_KEY", "admin"):
        abort(403)

    result = {"videos_deleted": [], "seminars_unpublished": [], "errors": []}

    # 削除対象の動画タイトル
    video_titles_to_delete = ["距離と角度の実演", "内側と外側のドリル"]
    for title in video_titles_to_delete:
        videos = Video.query.filter_by(title=title).all()
        for v in videos:
            result["videos_deleted"].append({"id": v.id, "title": v.title})
            # 関連Purchaseは残す（購入履歴として）が、video_idをNoneに
            Purchase.query.filter_by(video_id=v.id).update({"video_id": None})
            db.session.delete(v)

    # 非公開化対象のセミナータイトル（部分一致）
    seminar_titles_to_unpublish = ["蹴り技"]
    for keyword in seminar_titles_to_unpublish:
        seminars = Seminar.query.filter(Seminar.title.contains(keyword)).all()
        for s in seminars:
            if s.is_published:
                s.is_published = False
                result["seminars_unpublished"].append({"id": s.id, "title": s.title})

    db.session.commit()
    return jsonify(result)


# ============================================
# 資料一覧・ショップ（閲覧/販売）
# ============================================
def _extract_toc_from_html(html: str, max_items: int = 12):
    """HTML本文からh1/h2/h3を抽出してTOCリストを返す"""
    import re
    if not html:
        return []
    toc = []
    # コメント除去
    cleaned = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    for m in re.finditer(r"<h([1-3])[^>]*>(.*?)</h\1>", cleaned, re.IGNORECASE | re.DOTALL):
        level = int(m.group(1))
        # タグ除去
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        text = re.sub(r"\s+", " ", text)
        if text and len(text) < 100:
            toc.append({"level": level, "text": text})
            if len(toc) >= max_items:
                break
    return toc


def _extract_preview_text(html: str, max_chars: int = 240) -> str:
    """HTML本文から冒頭のテキストだけを抽出（サンプル用）"""
    import re
    if not html:
        return ""
    cleaned = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", cleaned,
                     flags=re.IGNORECASE | re.DOTALL)
    # 最初のh1/h2以降の本文を拾う
    body = cleaned
    m = re.search(r"</h[12]>", cleaned, re.IGNORECASE)
    if m:
        body = cleaned[m.end():]
    # タグ除去
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return text


@app.route("/my/materials")
@login_required
def my_materials():
    """自分がアクセスできる資料をセミナー横断で一覧表示（検索・並び替え対応）"""
    user = get_current_user()
    q = (request.args.get("q") or "").strip()
    sort = request.args.get("sort", "newest")

    # 出席済みセミナーと購入済み資料からアクセス権のある資料を集める
    attendances = Attendance.query.filter_by(user_id=user.id).all()
    attended_seminar_ids = [a.seminar_id for a in attendances]

    purchases = Purchase.query.filter_by(
        user_id=user.id, status="completed"
    ).all()
    purchased_material_ids = [p.material_id for p in purchases if p.material_id]

    # 資料取得（出席 OR 購入 OR 無料公開）
    from sqlalchemy import or_
    conds = []
    if attended_seminar_ids:
        conds.append(Material.seminar_id.in_(attended_seminar_ids))
    if purchased_material_ids:
        conds.append(Material.id.in_(purchased_material_ids))
    conds.append(Material.is_free == True)  # noqa: E712

    query = Material.query.filter(or_(*conds))
    if q:
        query = query.filter(Material.title.ilike(f"%{q}%"))

    materials = query.all()

    # セミナー情報をまとめて取得
    seminar_ids = {m.seminar_id for m in materials}
    seminars = {s.id: s for s in Seminar.query.filter(Seminar.id.in_(seminar_ids)).all()} if seminar_ids else {}

    # rowsに整形
    rows = []
    for m in materials:
        s = seminars.get(m.seminar_id)
        if not s:
            continue
        rows.append({
            "material": m,
            "seminar": s,
            "via_attendance": s.id in attended_seminar_ids,
            "via_purchase": m.id in purchased_material_ids,
            "has_pdf": bool(m.file_path),
        })

    # 並び替え
    if sort == "oldest":
        rows.sort(key=lambda r: r["seminar"].date)
    elif sort == "title":
        rows.sort(key=lambda r: r["material"].title)
    else:  # newest
        rows.sort(key=lambda r: r["seminar"].date, reverse=True)

    return render_template(
        "my_materials.html",
        user=user,
        rows=rows,
        q=q,
        sort=sort,
    )


@app.route("/shop")
def shop():
    """公開資料カタログ（非ログインでも閲覧可）"""
    user = get_current_user() if "user_id" in session else None
    q = (request.args.get("q") or "").strip()

    # is_free=False かつ 公開セミナーに紐づく資料のみ
    query = (
        Material.query
        .join(Seminar, Material.seminar_id == Seminar.id)
        .filter(Seminar.is_published == True)  # noqa: E712
        .filter(Material.is_free == False)     # noqa: E712
    )
    if q:
        query = query.filter(Material.title.ilike(f"%{q}%"))

    materials = query.all()
    seminar_ids = {m.seminar_id for m in materials}
    seminars = {s.id: s for s in Seminar.query.filter(Seminar.id.in_(seminar_ids)).all()} if seminar_ids else {}

    # ユーザーが既にアクセスできるかのマップ
    accessible_ids = set()
    if user:
        attended = {a.seminar_id for a in Attendance.query.filter_by(user_id=user.id).all()}
        purchased = {p.material_id for p in Purchase.query.filter_by(user_id=user.id, status="completed").all() if p.material_id}
        for m in materials:
            if m.seminar_id in attended or m.id in purchased:
                accessible_ids.add(m.id)

    rows = []
    for m in materials:
        s = seminars.get(m.seminar_id)
        if not s:
            continue
        rows.append({
            "material": m,
            "seminar": s,
            "accessible": m.id in accessible_ids,
        })
    rows.sort(key=lambda r: r["seminar"].date, reverse=True)

    return render_template("shop_index.html", user=user, rows=rows, q=q)


@app.route("/shop/material/<int:material_id>")
def shop_material(material_id):
    """個別販売ページ（概要・目次・サンプル付き）"""
    user = get_current_user() if "user_id" in session else None
    material = Material.query.get_or_404(material_id)
    seminar = Seminar.query.get(material.seminar_id)
    if not seminar or not seminar.is_published:
        abort(404)

    # アクセス権判定
    accessible = False
    if user:
        attended = Attendance.query.filter_by(
            user_id=user.id, seminar_id=material.seminar_id
        ).first()
        purchased = Purchase.query.filter_by(
            user_id=user.id, material_id=material_id, status="completed"
        ).first()
        accessible = bool(attended or purchased or material.is_free)

    toc = _extract_toc_from_html(material.content_html or "", max_items=16)
    preview = _extract_preview_text(material.content_html or "", max_chars=260)

    return render_template(
        "shop_material.html",
        user=user,
        material=material,
        seminar=seminar,
        toc=toc,
        preview=preview,
        accessible=accessible,
    )


@app.route("/admin/material/<int:material_id>/edit", methods=["GET", "POST"])
def admin_edit_material(material_id):
    """資料の価格・Stripe Payment Link を編集"""
    admin_key = request.args.get("key", "") or request.form.get("key", "")
    if admin_key != os.environ.get("ADMIN_KEY", "admin"):
        abort(403)
    material = Material.query.get_or_404(material_id)
    seminar = Seminar.query.get(material.seminar_id)

    if request.method == "POST":
        try:
            material.price = int(request.form.get("price", "0") or 0)
        except ValueError:
            material.price = 0
        material.stripe_payment_link = (request.form.get("stripe_payment_link") or "").strip() or None
        material.is_free = request.form.get("is_free") == "on"
        db.session.commit()
        flash("保存しました", "success")
        return redirect(url_for("admin_edit_material", material_id=material.id, key=admin_key))

    return render_template(
        "admin/material_edit.html",
        material=material,
        seminar=seminar,
        key=admin_key,
    )


# ============================================
# 静的ファイル
# ============================================
@app.route("/static/materials/<path:filename>")
def serve_material(filename):
    return send_from_directory("static/materials", filename)


@app.route("/sw.js")
def service_worker():
    """Service Workerをルートパスから配信（スコープを/にするため）"""
    response = send_from_directory("static", "sw.js")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Content-Type"] = "application/javascript"
    return response


@app.route("/manifest.json")
def manifest():
    """マニフェストをルートパスからも配信（PWA標準の Content-Type を明示）"""
    response = send_from_directory("static", "manifest.json")
    response.headers["Content-Type"] = "application/manifest+json; charset=utf-8"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    """iOS Safariがルートパスで自動取得するアイコンを配信"""
    return send_from_directory("static/icons", "apple-touch-icon.png")


# ============================================
# 起動
# ============================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
