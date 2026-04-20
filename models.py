"""
極真館 セミナーライブラリ — データモデル
"""
from datetime import datetime
from database import db


class User(db.Model):
    """ユーザー（受講者）"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    branch_name = db.Column(db.String(100))  # 支部名
    phone_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    phone_last4 = db.Column(db.String(4))  # 表示用
    email = db.Column(db.String(255), nullable=True)
    is_subscriber = db.Column(db.Boolean, default=False)  # 添削サブスク
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    remember_token = db.Column(db.String(64), unique=True, nullable=True, index=True)  # PWA自動再ログイン用
    language = db.Column(db.String(5), default="ja")  # 表示言語: ja / en
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendances = db.relationship("Attendance", back_populates="user")
    purchases = db.relationship("Purchase", back_populates="user")


class Seminar(db.Model):
    """セミナー"""
    __tablename__ = "seminars"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(500))
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    date = db.Column(db.DateTime, nullable=False)
    instructors = db.Column(db.String(500))  # カンマ区切り
    description = db.Column(db.Text)
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    materials = db.relationship("Material", back_populates="seminar")
    videos = db.relationship("Video", back_populates="seminar")
    attendances = db.relationship("Attendance", back_populates="seminar")

    @property
    def date_display(self):
        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        wd = weekdays[self.date.weekday()]
        return f"{self.date.year}年{self.date.month}月{self.date.day}日（{wd}）"

    @property
    def date_display_en(self):
        months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday"]
        m = months[self.date.month - 1]
        wd = weekdays[self.date.weekday()]
        return f"{m} {self.date.day}, {self.date.year} ({wd})"

    @property
    def instructor_list(self):
        return [i.strip() for i in self.instructors.split(",") if i.strip()]


class Attendance(db.Model):
    """出席記録"""
    __tablename__ = "attendances"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    seminar_id = db.Column(db.Integer, db.ForeignKey("seminars.id"), nullable=False)
    attended_at = db.Column(db.DateTime, default=datetime.utcnow)
    method = db.Column(db.String(20), default="qr")  # qr / zoom / manual

    user = db.relationship("User", back_populates="attendances")
    seminar = db.relationship("Seminar", back_populates="attendances")

    __table_args__ = (
        db.UniqueConstraint("user_id", "seminar_id", name="uq_user_seminar"),
    )


class Material(db.Model):
    """セミナー資料"""
    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)
    seminar_id = db.Column(db.Integer, db.ForeignKey("seminars.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    title_en = db.Column(db.String(200))  # 英語タイトル
    content_html = db.Column(db.Text)  # HTML形式の資料本文
    content_html_en = db.Column(db.Text)  # HTML形式の資料本文（英語）
    file_path = db.Column(db.String(500))  # 元ファイル（PDFなど）のパス
    is_free = db.Column(db.Boolean, default=False)  # 出席者以外にも無料公開
    price = db.Column(db.Integer, default=0)  # 非出席者向け価格（0 = 非売品）
    stripe_payment_link = db.Column(db.String(500))
    square_checkout_url = db.Column(db.String(500))  # Square Online Checkout Link
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    seminar = db.relationship("Seminar", back_populates="materials")


class Video(db.Model):
    """セミナー動画"""
    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    seminar_id = db.Column(db.Integer, db.ForeignKey("seminars.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    duration = db.Column(db.String(20))  # "12:30"
    video_url = db.Column(db.String(500))  # 埋め込みURL（Vimeo等）
    thumbnail_url = db.Column(db.String(500))
    price = db.Column(db.Integer, default=500)  # 非Zoom参加者向け価格
    stripe_payment_link = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    seminar = db.relationship("Seminar", back_populates="videos")


class Purchase(db.Model):
    """購入履歴"""
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=True)
    item_type = db.Column(db.String(20), nullable=False)  # video / material / subscription
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending / completed / refunded
    stripe_session_id = db.Column(db.String(255))
    square_order_id = db.Column(db.String(255))  # Square側のorder/payment ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="purchases")
