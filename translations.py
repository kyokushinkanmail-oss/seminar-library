"""
シンプル i18n 辞書 — Flask-Babel を使わない軽量実装。
UIラベルのみ英訳。日本語文字列をキーにしても可だが、保守性のため短キー方式。
"""

TRANSLATIONS = {
    # 共通
    "app_title": {"ja": "極真館組手セミナー", "en": "Kyokushinkan Kumite Seminar"},
    "app_subtitle": {"ja": "資料・動画がすべて残る、学びのライブラリ", "en": "All your seminar materials and videos in one library"},
    "back": {"ja": "戻る", "en": "Back"},
    "save": {"ja": "保存", "en": "Save"},
    "cancel": {"ja": "キャンセル", "en": "Cancel"},
    "submit": {"ja": "送信", "en": "Submit"},
    "delete": {"ja": "削除", "en": "Delete"},
    "edit": {"ja": "編集", "en": "Edit"},
    "search": {"ja": "検索", "en": "Search"},
    "loading": {"ja": "読み込み中...", "en": "Loading..."},
    "lang_switch": {"ja": "EN", "en": "日本語"},
    "free": {"ja": "無料", "en": "Free"},
    "yen": {"ja": "円", "en": "JPY"},

    # ナビ・ヘッダー
    "nav_library": {"ja": "マイライブラリ", "en": "My Library"},
    "nav_my_materials": {"ja": "マイ資料", "en": "My Materials"},
    "nav_shop": {"ja": "ショップ", "en": "Shop"},
    "nav_logout": {"ja": "ログアウト", "en": "Logout"},

    # ランディング
    "landing_tagline": {"ja": "セミナー資料・動画配信システム", "en": "Seminar materials & video platform"},
    "landing_stat_users": {"ja": "登録者", "en": "Members"},
    "landing_stat_seminars": {"ja": "開催セミナー", "en": "Seminars"},
    "landing_stat_materials": {"ja": "資料数", "en": "Materials"},
    "landing_ongoing": {"ja": "開催中", "en": "Active"},
    "landing_already_registered": {"ja": "名が参加登録済み", "en": " people registered"},
    "landing_benefits_title": {"ja": "参加するとこれがもらえる", "en": "What you get"},
    "landing_benefit_material_t": {"ja": "セミナー資料（HTML/PDF）", "en": "Seminar materials (HTML/PDF)"},
    "landing_benefit_material_d": {"ja": "いつでもスマホで閲覧可能", "en": "Accessible anytime on your phone"},
    "landing_benefit_video_t": {"ja": "技術解説動画", "en": "Technical explanation videos"},
    "landing_benefit_video_d": {"ja": "Zoom参加者は無料で視聴", "en": "Free for Zoom participants"},
    "landing_benefit_lib_t": {"ja": "参加した全セミナーの資料が貯まる", "en": "Materials from every seminar you attend"},
    "landing_benefit_lib_d": {"ja": "あなた専用のマイライブラリ", "en": "Your personal library"},
    "landing_cta_register": {"ja": "＋ はじめての方 — 資料を受け取る（無料）", "en": "+ New here — Get materials (Free)"},
    "landing_cta_login": {"ja": "2回目以降の方 — ログイン", "en": "Returning member — Log in"},
    "landing_steps_title": {"ja": "たった3ステップ", "en": "Just 3 steps"},
    "landing_step1_t": {"ja": "支部名と氏名で登録", "en": "Register with branch name and full name"},
    "landing_step1_d": {"ja": "30秒で完了、支部と氏名のみ", "en": "Takes 30 seconds, just branch & name"},
    "landing_step2_t": {"ja": "セミナーに参加", "en": "Attend a seminar"},
    "landing_step2_d": {"ja": "会場QRまたはZoomで自動反映", "en": "Automatic via venue QR or Zoom"},
    "landing_step3_t": {"ja": "マイライブラリに資料が追加", "en": "Materials added to your library"},
    "landing_step3_d": {"ja": "何度でも復習可能、PDFダウンロードOK", "en": "Review anytime, PDF downloadable"},
    "landing_cta_register_now": {"ja": "今すぐ資料を受け取る →", "en": "Get materials now →"},
    "landing_next_seminar": {"ja": "次回予告", "en": "Next seminar"},
    "landing_next_tbd": {"ja": "（詳細は後日お知らせ）", "en": "(Details announced soon)"},
    "landing_next_preregister": {"ja": "先行エントリーする", "en": "Pre-register"},
    "landing_shop_title": {"ja": "過去セミナーの資料を個別購入", "en": "Buy past seminar materials"},
    "landing_shop_desc": {"ja": "参加できなかった回の資料もショップから購入できます", "en": "Purchase materials from seminars you missed"},
    "landing_shop_cta": {"ja": "ショップを見る →", "en": "Visit shop →"},
    "landing_no_seminar": {"ja": "現在公開中のセミナーはありません", "en": "No seminars published at the moment"},
    "landing_wait_next": {"ja": "次回のセミナーをお待ちください", "en": "Please wait for the next seminar"},

    # 登録・ログイン
    "register_title": {"ja": "新規登録", "en": "Sign up"},
    "register_desc": {"ja": "支部名と氏名をご入力ください", "en": "Enter your branch name and full name"},
    "register_branch_label": {"ja": "支部名", "en": "Branch name"},
    "register_branch_placeholder": {"ja": "例: 東京支部 / Tokyo Branch", "en": "e.g. Tokyo Branch / Overseas"},
    "register_name_label": {"ja": "氏名", "en": "Full name"},
    "register_name_placeholder": {"ja": "例: 山田 太郎", "en": "e.g. John Smith"},
    "register_submit": {"ja": "登録する", "en": "Sign up"},
    "register_already": {"ja": "すでに登録済みの方", "en": "Already registered?"},
    "login_title": {"ja": "ログイン", "en": "Log in"},
    "login_desc": {"ja": "登録時の支部名と氏名を入力してください", "en": "Enter the branch name and full name you registered with"},
    "login_submit": {"ja": "ログインする", "en": "Log in"},
    "login_no_account": {"ja": "はじめての方はこちら", "en": "New here? Sign up"},

    # ライブラリ
    "library_title": {"ja": "マイライブラリ", "en": "My Library"},
    "library_materials_card": {"ja": "資料一覧を開く", "en": "Browse materials"},
    "library_shop_card": {"ja": "ショップで探す", "en": "Explore shop"},
    "library_attending_seminars": {"ja": "参加セミナー", "en": "Attended seminars"},
    "library_no_attendance": {"ja": "まだセミナーに参加していません", "en": "You haven't attended any seminars yet"},

    # マイ資料
    "my_materials_title": {"ja": "資料一覧", "en": "My Materials"},
    "my_materials_count": {"ja": "件の資料が閲覧できます", "en": " materials available"},
    "my_materials_search_placeholder": {"ja": "資料タイトルで検索", "en": "Search by title"},
    "my_materials_sort_newest": {"ja": "新しい順", "en": "Newest"},
    "my_materials_sort_oldest": {"ja": "古い順", "en": "Oldest"},
    "my_materials_sort_title": {"ja": "タイトル", "en": "Title"},
    "my_materials_empty": {"ja": "まだ閲覧できる資料がありません。", "en": "No materials available yet."},
    "my_materials_empty_hint": {"ja": "セミナーに参加するか、ショップで購入してください。", "en": "Attend a seminar or purchase from the shop."},
    "my_materials_search_empty": {"ja": "該当する資料が見つかりません。", "en": "No matching materials found."},
    "my_materials_clear_search": {"ja": "検索をクリア", "en": "Clear search"},
    "my_materials_open": {"ja": "開く", "en": "Open"},
    "my_materials_pdf": {"ja": "PDF", "en": "PDF"},
    "my_materials_receipt": {"ja": "領収書", "en": "Receipt"},
    "tag_attended": {"ja": "参加済み", "en": "Attended"},
    "tag_purchased": {"ja": "購入済み", "en": "Purchased"},

    # ショップ
    "shop_title": {"ja": "ショップ", "en": "Shop"},
    "shop_subtitle": {"ja": "過去セミナーの資料を個別購入", "en": "Buy past seminar materials"},
    "shop_buy": {"ja": "購入する", "en": "Buy"},
    "shop_view_detail": {"ja": "詳細を見る", "en": "View details"},
    "shop_empty": {"ja": "現在販売中の資料はありません", "en": "No materials currently for sale"},
    "shop_purchase_instruction": {"ja": "以下のボタンから決済してください", "en": "Purchase using the button below"},

    # 資料閲覧
    "material_download_pdf": {"ja": "PDFをダウンロード", "en": "Download PDF"},
    "material_back_to_library": {"ja": "ライブラリに戻る", "en": "Back to library"},
    "material_preparing": {"ja": "準備中", "en": "Coming soon"},
    "material_premium_notice": {"ja": "この資料は有料コンテンツです", "en": "This is premium content"},

    # 管理画面（最小限）
    "admin_dashboard_title": {"ja": "管理ダッシュボード", "en": "Admin Dashboard"},
}


def t(key, lang="ja"):
    """翻訳ヘルパー。未定義キーはキーそのものを返す。"""
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get("ja") or key
