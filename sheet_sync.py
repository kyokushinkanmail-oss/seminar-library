"""Google スプレッドシート（CSV export）から参加者リストを取得し、
Material 単位の閲覧権 (MaterialGrant) を付与するモジュール。

外部 API クライアントは使わず urllib + csv の標準ライブラリのみ。
公開シート（リンクを知っている全員が閲覧可）が前提。
"""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
import urllib.request
from datetime import datetime
from typing import List, Dict, Optional, Tuple


CSV_FETCH_TIMEOUT = 10
SHEET_USER_AGENT = "Mozilla/5.0 (kumite-seminar-library)"


def fetch_csv(url):
    """Google Sheet の CSV export URL を取得して dict のリストで返す。
    リダイレクト追従・BOM 除去・ヘッダ trim まで面倒みる。
    """
    req = urllib.request.Request(url, headers={"User-Agent": SHEET_USER_AGENT})
    with urllib.request.urlopen(req, timeout=CSV_FETCH_TIMEOUT) as resp:
        raw = resp.read()
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        cleaned = {}
        for k, v in row.items():
            if k is None:
                continue
            cleaned[k.strip()] = (v or "").strip()
        rows.append(cleaned)
    return rows


_WS_RE = re.compile(r"\s+")


def normalize_name(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u3000", " ")
    s = _WS_RE.sub("", s)
    return s.lower()


def normalize_email(s):
    if not s:
        return ""
    return s.strip().lower()


def find_field(row, candidates):
    """row のキー候補から最初に値が入っているものを返す。"""
    for c in candidates:
        if c in row and row[c]:
            return row[c]
    return ""


# シートの想定列名（ユーザーが少し列名を変えても拾えるよう候補を持たせる）
NAME_FIELDS = ["氏名", "お名前", "名前", "name", "Name", "Full Name"]
BRANCH_FIELDS = ["支部名・道場名", "支部名", "道場名", "branch", "Branch"]
EMAIL_FIELDS = ["メールアドレス", "メール", "email", "Email", "E-mail"]
CLASS_FIELDS = ["参加講座", "参加クラス", "class", "Class", "Course"]


def match_user(row: dict):
    """シート行と一致する User を返す（無ければ None）。
    優先順位: email_norm 一致 > (name_norm + branch_norm) 一致。
    複数ヒットは安全側に倒して None。"""
    from models import User

    email = normalize_email(find_field(row, EMAIL_FIELDS))
    if email:
        cand = [u for u in User.query.filter(User.email.isnot(None)).all()
                if normalize_email(u.email) == email]
        if len(cand) == 1:
            return cand[0]
        if len(cand) > 1:
            return None

    name_norm = normalize_name(find_field(row, NAME_FIELDS))
    branch_norm = normalize_name(find_field(row, BRANCH_FIELDS))
    if not name_norm:
        return None

    cand = [u for u in User.query.all()
            if normalize_name(u.name) == name_norm
            and normalize_name(u.branch_name) == branch_norm]
    if len(cand) == 1:
        return cand[0]
    return None


def resolve_grants(seminar_id, class_value):
    """SheetClassMaterialMap を引いて、その class_value で付与する Material リストを返す。
    material_id IS NULL は当該セミナーの全 Material に展開。"""
    from models import Material, SheetClassMaterialMap

    rows = SheetClassMaterialMap.query.filter_by(
        seminar_id=seminar_id, class_value=class_value
    ).all()
    if not rows:
        return []

    materials = {}
    has_all = any(r.material_id is None for r in rows)
    if has_all:
        for m in Material.query.filter_by(seminar_id=seminar_id).all():
            materials[m.id] = m
    for r in rows:
        if r.material_id is not None:
            m = Material.query.get(r.material_id)
            if m is not None:
                materials[m.id] = m
    return list(materials.values())


def apply_grants(user, seminar, materials, source="sheet"):
    """MaterialGrant を upsert。
    materials が当該 Seminar の全 Material をカバーしているなら Attendance(method="manual") も upsert。
    返り値: (新規作成された MaterialGrant 件数, Attendance を作ったかどうか)。
    """
    from database import db
    from models import Attendance, Material, MaterialGrant

    granted_count = 0
    for m in materials:
        existing = MaterialGrant.query.filter_by(
            user_id=user.id, material_id=m.id
        ).first()
        if existing:
            continue
        db.session.add(MaterialGrant(
            user_id=user.id,
            material_id=m.id,
            seminar_id=seminar.id,
            source=source,
        ))
        granted_count += 1

    all_in_seminar = {m.id for m in Material.query.filter_by(seminar_id=seminar.id).all()}
    given_ids = {m.id for m in materials}
    attended_added = False
    if all_in_seminar and all_in_seminar.issubset(given_ids):
        existing_att = Attendance.query.filter_by(
            user_id=user.id, seminar_id=seminar.id
        ).first()
        if not existing_att:
            db.session.add(Attendance(
                user_id=user.id,
                seminar_id=seminar.id,
                attended_at=datetime.utcnow(),
                method="manual",
            ))
            attended_added = True

    return granted_count, attended_added


def _upsert_pending(seminar_id, row):
    """シート行を SheetPendingEntry に upsert。新規作成したら True。"""
    from database import db
    from models import SheetPendingEntry

    name = find_field(row, NAME_FIELDS)
    branch = find_field(row, BRANCH_FIELDS)
    email = find_field(row, EMAIL_FIELDS)
    class_value = find_field(row, CLASS_FIELDS)
    name_norm = normalize_name(name)
    branch_norm = normalize_name(branch)
    email_norm = normalize_email(email)

    existing = SheetPendingEntry.query.filter_by(
        seminar_id=seminar_id,
        email_norm=email_norm,
        name_norm=name_norm,
    ).first()
    if existing:
        existing.branch_name = branch
        existing.branch_norm = branch_norm
        existing.email = email or existing.email
        existing.class_value = class_value or existing.class_value
        return False
    db.session.add(SheetPendingEntry(
        seminar_id=seminar_id,
        name=name, branch_name=branch, email=email,
        name_norm=name_norm, branch_norm=branch_norm, email_norm=email_norm,
        class_value=class_value,
    ))
    return True


def sync_seminar(seminar_id):
    """SheetSource → CSV 取得 → 各行マッチ・付与 or pending 登録。集計を返す。"""
    from database import db
    from models import Seminar, SheetSource

    src = SheetSource.query.filter_by(seminar_id=seminar_id).first()
    if not src or not src.csv_url:
        return {"error": "sheet_source_missing"}
    seminar = Seminar.query.get(seminar_id)
    if not seminar:
        return {"error": "seminar_missing"}

    result = {
        "fetched": 0,
        "matched": 0,
        "granted": 0,
        "attended_added": 0,
        "pending": 0,
        "unknown_class": 0,
        "errors": [],
    }
    try:
        rows = fetch_csv(src.csv_url)
    except Exception as e:
        result["errors"].append(f"fetch_failed: {e}")
        src.last_synced_at = datetime.utcnow()
        src.last_result_json = json.dumps(result, ensure_ascii=False)
        db.session.commit()
        return result

    result["fetched"] = len(rows)

    for row in rows:
        try:
            class_value = find_field(row, CLASS_FIELDS)
            user = match_user(row)
            if user is None:
                if _upsert_pending(seminar_id, row):
                    result["pending"] += 1
                continue
            materials = resolve_grants(seminar_id, class_value)
            if not materials:
                result["unknown_class"] += 1
                continue
            g, a = apply_grants(user, seminar, materials, source="sheet")
            result["matched"] += 1
            result["granted"] += g
            if a:
                result["attended_added"] += 1
        except Exception as e:
            result["errors"].append(f"row_failed: {e}")

    src.last_synced_at = datetime.utcnow()
    src.last_result_json = json.dumps(result, ensure_ascii=False)
    db.session.commit()
    return result


def consume_pending_for_user(user):
    """register/login 時に呼ぶ。SheetPendingEntry を email/氏名+支部名 で再マッチ → 付与 → consumed_at 打つ。
    返り値は新規 grant 件数。"""
    from database import db
    from models import Seminar, SheetPendingEntry

    pending = SheetPendingEntry.query.filter_by(consumed_at=None).all()
    if not pending:
        return 0

    user_email_norm = normalize_email(user.email)
    user_name_norm = normalize_name(user.name)
    user_branch_norm = normalize_name(user.branch_name)
    granted_total = 0

    for p in pending:
        match = False
        if p.email_norm and user_email_norm and p.email_norm == user_email_norm:
            match = True
        elif p.name_norm and user_name_norm and p.name_norm == user_name_norm \
                and (p.branch_norm or "") == (user_branch_norm or ""):
            match = True
        if not match:
            continue
        seminar = Seminar.query.get(p.seminar_id)
        if not seminar:
            continue
        materials = resolve_grants(p.seminar_id, p.class_value or "")
        if not materials:
            continue
        g, _ = apply_grants(user, seminar, materials, source="sheet")
        granted_total += g
        p.consumed_at = datetime.utcnow()

    if granted_total or any(p.consumed_at for p in pending):
        db.session.commit()
    return granted_total
