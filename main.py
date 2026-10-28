import json
import os
import re
from io import BytesIO

import requests
from PIL import Image

# ==========================================
# 1. 設定
# ==========================================
WIKI_API = "https://limbuscompany.wiki.gg/api.php"
STATE_FILE = "state.json"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "").strip()

KW_TRANSLATION = {
    "Slash": "斬擊", "Pierce": "突刺", "Blunt": "打擊",
    "Bleed": "流血", "Rupture": "破裂", "Burn": "燃燒",
    "Tremor": "震顫", "Sinking": "沉淪", "Charge": "充能",
    "Poise": "呼吸", "Bind": "束縛", "Paralyze": "麻痺",
    "Envy": "忌妒",
}

SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "LimbusRentalMonitorBot/2.0 (Automated GitHub Actions Monitor; DiscordID:anku0910)"
)


# ==========================================
# 2. 狀態管理
# ==========================================
def load_state():
    if not os.path.exists(STATE_FILE):
        return {"last_rental_team": ""}
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ==========================================
# 3. Wiki API
# ==========================================
def api_query(**params):
    params.update(action="query", format="json")
    res = SESSION.get(WIKI_API, params=params).json()
    return res.get("query", {}).get("pages", {}) or {}


def fetch_wikitext():
    pages = api_query(prop="revisions", titles="List_of_Rental_Teams",
                      rvprop="content", rvslots="main")
    if not pages:
        raise ValueError("無法從 Wiki API 取得頁面資料")
    return next(iter(pages.values()))["revisions"][0]["slots"]["main"]["*"]


def fetch_image_url(file_title):
    pages = api_query(prop="imageinfo", iiprop="url", titles=f"File:{file_title}")
    page_id, page = next(iter(pages.items()), (None, {}))
    info = page.get("imageinfo")
    return info[0]["url"] if info and page_id.isdigit() else None


# ==========================================
# 4. 解析器
# ==========================================
def clean_wikitext(text):
    if not text:
        return ""
    text = re.sub(r"<!--.*?-->|<[^>]+>", " ", text, flags=re.S)
    text = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\{\{StatusEffect[^}]*\}\}", "", text, flags=re.I)
    text = re.sub(r"\{\{StatusEffect[^|]*\|([^}|]+)[^}]*\}\}", r"\1", text, flags=re.I)

    def pick_template(match):
        parts = match.group(1).split("|")
        return parts[1] if len(parts) > 1 else parts[0]

    while "{{" in text and "}}" in text:
        text = re.sub(r"\{\{([^{}]+)\}\}", pick_template, text)

    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b([A-Za-z]+)\s+\1\b", r"\1", text, flags=re.I)
    return text.strip()


def translate_keywords(kw_str):
    if kw_str == "None":
        return "無"
    words = [
        KW_TRANSLATION.get(k, k)
        for k in (part.strip() for part in kw_str.split(","))
        if k and not any(c in k for c in "|{}")
    ]
    return "，".join(words) or "無"


def parse_latest_team(wikitext):
    for block in re.split(r"(?=\{\{RentTab)", wikitext):
        if "{{RentTab" not in block:
            continue

        head = block.split("{{RentBox")[0]
        date_m = re.search(
            r"([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{4}"
            r"\s*-\s*[A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{4})",
            head,
        )
        raw_date = date_m.group(1) if date_m else "Unknown Date"

        kw_m = re.search(r"keywords\s*=\s*(.*?)(?=\|\s*[a-zA-Z0-9_]+\s*=|\Z)",
                         head, flags=re.I | re.S)
        raw_kw = clean_wikitext(re.sub(r"\}\}\s*$", "", kw_m.group(1).strip())) if kw_m else "None"

        identities = []
        for box in re.finditer(r"\{\{RentBox\s*\|(.*?)\}\}", block, flags=re.S):
            fields = {}
            for m in re.finditer(r"([a-zA-Z0-9_]+)\s*=\s*([^|}]*)", box.group(1)):
                value = clean_wikitext(m.group(2))
                if value:
                    fields[m.group(1).lower()] = value
            if "sinner" in fields and "id" in fields:
                identities.append(fields)

        if identities:
            return {
                "keywords_zh": translate_keywords(raw_kw),
                "identities": identities[:12],
                "unique_id": f"{raw_date}-{raw_kw}",
            }
    return None


# ==========================================
# 5. 圖片合成與快取
# ==========================================
def download_image(url, cache):
    if not url:
        return None
    if url not in cache:
        print(f"  下載圖片: {url.split('/')[-1]}")
        res = SESSION.get(url)
        if res.status_code != 200:
            return None
        cache[url] = Image.open(BytesIO(res.content)).convert("RGBA")
    return cache[url].copy()


def create_rentbox(data, cache):
    sinner, id_name = data.get("sinner", ""), data.get("id", "")
    rarity = int(data.get("rarity", 3))

    id_img = download_image(fetch_image_url(f"{id_name} {sinner} Uptied.png"), cache)
    ego_imgs = [
        download_image(fetch_image_url(f"{data[key]} {sinner} Icon.png"), cache)
        if data.get(key) else None
        for key in ("zayin", "teth", "he", "waw", "aleph")
    ]

    box_w, id_h, ego_sz, gap, border = 140, 216, 36, 4, 4
    border_color = (240, 203, 27, 255) if rarity == 3 else (174, 1, 0, 255)

    inner_h = id_h + gap * 2 + ego_sz * 2 + 4
    canvas = Image.new("RGBA", (box_w + border * 2, inner_h + border * 2), border_color)
    canvas.paste(Image.new("RGBA", (box_w, inner_h), (30, 32, 36, 255)), (border, border))

    if id_img:
        id_img = id_img.resize((box_w, id_h))
        canvas.paste(id_img, (border, border), id_img)

    placeholder = Image.new("RGBA", (ego_sz, ego_sz), (0, 0, 0, 100))

    y_r2 = border + id_h + gap
    for i, x in enumerate((0, 52, 104)):
        img = ego_imgs[i].resize((ego_sz, ego_sz)) if ego_imgs[i] else placeholder
        canvas.paste(img, (border + x, y_r2), img)

    y_r3 = y_r2 + ego_sz + gap
    for i, x in enumerate((28, 76), start=3):
        img = ego_imgs[i].resize((ego_sz, ego_sz)) if ego_imgs[i] else placeholder
        canvas.paste(img, (border + x, y_r3), img)

    return canvas


def build_team_image(team_data, output_path="team.png", cache=None):
    cache = {} if cache is None else cache
    print("開始合成 6x2 純網格大圖...")
    rentboxes = [create_rentbox(d, cache) for d in team_data["identities"]]

    box_w, box_h, cols, rows, padding, border = 148, 308, 6, 2, 15, 4
    inner_w = cols * box_w + padding * (cols + 1)
    inner_h = rows * box_h + padding * (rows + 1)

    canvas = Image.new("RGBA", (inner_w + border * 2, inner_h + border * 2), (101, 66, 34, 255))
    canvas.paste(Image.new("RGBA", (inner_w, inner_h), (30, 32, 36, 255)), (border, border))

    for i, box in enumerate(rentboxes):
        canvas.paste(
            box,
            (border + padding + (i % cols) * (box_w + padding),
             border + padding + (i // cols) * (box_h + padding)),
            box,
        )

    canvas.save(output_path)
    print(f"大圖合成完畢: {output_path}")


# ==========================================
# 6. Discord 通知
# ==========================================
def send_discord(image_path="team.png"):
    if not WEBHOOK_URL:
        print("未設定 DISCORD_WEBHOOK，跳過發送。")
        return

    payload = {
        "embeds": [{
            "title": "🗓️ 新一輪的鏡牢租借隊伍出來了！",
            "url": "https://github.com/anku0910/limbus-rental-monitor",
            "color": 0x654222,
            "image": {"url": f"attachment://{image_path}"},
            "footer": {"text": "Limbus Company Auto Monitor"},
        }]
    }

    with open(image_path, "rb") as f:
        res = requests.post(WEBHOOK_URL, files={
            "payload_json": (None, json.dumps(payload), "application/json"),
            image_path: (image_path, f, "image/png"),
        })

    if res.status_code in (200, 204):
        print("成功發送 Discord Webhook (含 Embed)！")
    else:
        print(f"發送失敗：HTTP {res.status_code}\n{res.text}")


# ==========================================
# 7. 主程序
# ==========================================
def main():
    print("啟動 Rental Team Monitor...")

    state = load_state()
    team_data = parse_latest_team(fetch_wikitext())

    if not team_data:
        print("解析失敗：找不到 Rental Team 結構。")
        return

    current_id = team_data["unique_id"]
    print(f"抓取到最新 Team: {team_data['keywords_zh']} (ID: {current_id})")

    if state.get("last_rental_team") == current_id:
        print("狀態相同，尚無新隊伍，結束執行。")
        return

    print("發現新隊伍！開始處理圖片...")
    build_team_image(team_data)
    send_discord()

    state["last_rental_team"] = current_id
    save_state(state)
    print("狀態儲存完畢，流程結束。")


if __name__ == "__main__":
    main()
