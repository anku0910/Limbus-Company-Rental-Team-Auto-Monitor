import os
import re
import json
import requests
import datetime
from io import BytesIO
from PIL import Image

# ==========================================
# 1. 核心常數與設定
# ==========================================
WIKI_API_URL = "https://limbuscompany.wiki.gg/api.php"
STATE_FILE = "state.json"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "").strip()

# 關鍵字中英對照表
KW_TRANSLATION = {
    "Slash": "斬擊",
    "Pierce": "突刺",
    "Blunt": "打擊",
    "Bleed": "流血",
    "Rupture": "破裂",
    "Burn": "燃燒",
    "Tremor": "震顫",
    "Sinking": "沉淪",
    "Charge": "充能",
    "Poise": "呼吸",
    "Bind": "束縛",
    "Paralyze": "麻痺"
}

# ==========================================
# 2. 狀態管理器
# ==========================================
class StateManager:
    @staticmethod
    def load():
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"last_rental_team": ""}

    @staticmethod
    def save(state_data):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)

# ==========================================
# 3. Wiki API 溝通模組
# ==========================================
class WikiFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "LimbusRentalMonitorBot/2.0 (Automated GitHub Actions Monitor; DiscordID:anku0910)"
        })

    def get_latest_wikitext(self) -> str:
        params = {
            "action": "query", "prop": "revisions",
            "titles": "List_of_Rental_Teams", "rvprop": "content",
            "rvslots": "main", "format": "json"
        }
        res = self.session.get(WIKI_API_URL, params=params).json()
        pages = res.get("query", {}).get("pages", {})
        if not pages:
            raise ValueError("無法從 Wiki API 取得頁面資料")
        page_id = list(pages.keys())[0]
        return pages[page_id]["revisions"][0]["slots"]["main"]["*"]

    def get_image_url(self, file_title: str) -> str:
        params = {
            "action": "query", "prop": "imageinfo",
            "iiprop": "url", "titles": f"File:{file_title}", "format": "json"
        }
        res = self.session.get(WIKI_API_URL, params=params).json()
        
        if "error" in res:
            return None
            
        pages = res.get("query", {}).get("pages", {})
        if not pages:
            return None
            
        page_id = list(pages.keys())[0]
        if int(page_id) < 0 or "imageinfo" not in pages[page_id]:
            return None
            
        return pages[page_id]["imageinfo"][0]["url"]

# ==========================================
# 4. 解析器 (Parser)
# ==========================================
class Parser:
    @staticmethod
    def clean_wikitext(text: str) -> str:
        if not text: return ""
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
        text = re.sub(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', r'\1', text)
        
        def template_replacer(match):
            parts = match.group(1).split('|')
            return parts[1] if len(parts) > 1 else parts[0]
            
        while "{{" in text and "}}" in text:
            text = re.sub(r'\{\{([^{}]+)\}\}', template_replacer, text)
            
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\b([A-Za-z]+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
        
        return text.strip()

    @staticmethod
    def translate_keywords(kw_str: str) -> str:
        """將英文關鍵字轉換為中文"""
        if kw_str == "None":
            return "無"
        
        # 切割後查字典，找不到就保持原樣，最後用中文字元「，」連接
        kws = [k.strip() for k in kw_str.split(',')]
        translated = [KW_TRANSLATION.get(k, k) for k in kws if k]
        return "，".join(translated)

    @staticmethod
    def convert_to_discord_timestamp(date_str: str) -> str:
        """將英文日期區間轉換為 Discord Timestamp 格式"""
        months = {
            "January": 1, "February": 2, "March": 3, "April": 4,
            "May": 5, "June": 6, "July": 7, "August": 8,
            "September": 9, "October": 10, "November": 11, "December": 12
        }
        
        def parse_single(s):
            m = re.search(r'([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})', s)
            if m:
                month_str, day_str, year_str = m.groups()
                month = months.get(month_str)
                if month:
                    # 使用 UTC 中午 12 點作為基準，避免時區偏差導致日期少一天
                    dt = datetime.datetime(int(year_str), month, int(day_str), 12, 0, 0, tzinfo=datetime.timezone.utc)
                    return f"<t:{int(dt.timestamp())}:D>" # :D 會在 Discord 顯示為「YYYY年M月D日」
            return s
            
        parts = date_str.split('-')
        if len(parts) == 2:
            return f"{parse_single(parts[0])} - {parse_single(parts[1])}"
        return date_str

    @staticmethod
    def parse_latest_team(wikitext: str) -> dict:
        blocks = re.split(r'(?=\{\{RentTab)', wikitext)
        for block in blocks:
            if "{{RentTab" not in block:
                continue
            
            renttab_head = block.split('{{RentBox')[0]
            
            date_m = re.search(r'([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{4}\s*-\s*[A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{4})', renttab_head)
            raw_date_str = date_m.group(1) if date_m else "Unknown Date"
            
            kw_m = re.search(r'keywords\s*=\s*(.*?)(?=\|\s*[a-zA-Z0-9_]+\s*=|\Z)', renttab_head, re.IGNORECASE | re.DOTALL)
            if kw_m:
                raw_kw = kw_m.group(1)
                raw_kw = re.sub(r'\}\}\s*$', '', raw_kw.strip()) 
                raw_kw_str = Parser.clean_wikitext(raw_kw).strip()
            else:
                raw_kw_str = "None"
            
            # 套用翻譯與 Timestamp 轉換
            discord_date = Parser.convert_to_discord_timestamp(raw_date_str)
            zh_keywords = Parser.translate_keywords(raw_kw_str)
            
            identities = []
            boxes = re.finditer(r'\{\{RentBox\s*\|(.*?)\}\}', block, re.DOTALL)
            for box in boxes:
                box_str = box.group(1)
                fields = {}
                for match in re.finditer(r'([a-zA-Z0-9_]+)\s*=\s*([^|}]*)', box_str):
                    key = match.group(1).strip().lower()
                    val = Parser.clean_wikitext(match.group(2))
                    if val: fields[key] = val
                
                if "sinner" in fields and "id" in fields:
                    identities.append(fields)
                    
            if len(identities) > 0:
                return {
                    "date_timestamp": discord_date,
                    "keywords_zh": zh_keywords,
                    "identities": identities[:12],
                    "unique_id": f"{raw_date_str}-{raw_kw_str}" # 維持原始字串作為防重複 ID
                }
        return None

# ==========================================
# 5. 圖片合成與快取模組
# ==========================================
class ImageComposer:
    def __init__(self, fetcher: WikiFetcher):
        self.fetcher = fetcher
        self.image_cache = {}

    def download_image(self, url: str) -> Image.Image:
        if not url: return None
        if url in self.image_cache:
            return self.image_cache[url].copy()
            
        print(f"  ⬇️ 下載圖片: {url.split('/')[-1]}")
        res = self.fetcher.session.get(url)
        if res.status_code == 200:
            img = Image.open(BytesIO(res.content)).convert("RGBA")
            self.image_cache[url] = img
            return img.copy()
        return None

    def create_rentbox(self, data: dict) -> Image.Image:
        sinner, id_name = data.get("sinner", ""), data.get("id", "")
        rarity = int(data.get("rarity", 3))
        
        id_title = f"{id_name} {sinner} Uptied.png"
        id_img = self.download_image(self.fetcher.get_image_url(id_title))
        
        ego_keys = ["zayin", "teth", "he", "waw", "aleph"]
        ego_imgs = []
        for key in ego_keys:
            ego_name = data.get(key)
            if ego_name:
                ego_title = f"{ego_name} {sinner} Icon.png"
                ego_imgs.append(self.download_image(self.fetcher.get_image_url(ego_title)))
            else:
                ego_imgs.append(None)

        box_w, id_h, ego_sz, gap, border_w = 140, 216, 36, 4, 4
        border_color = (240, 203, 27, 255) if rarity == 3 else (174, 1, 0, 255)
        
        inner_h = id_h + gap + ego_sz + gap + ego_sz + 4 
        out_w, out_h = box_w + (border_w * 2), inner_h + (border_w * 2) 
        
        canvas = Image.new("RGBA", (out_w, out_h), border_color)
        inner_bg = Image.new("RGBA", (box_w, inner_h), (30, 32, 36, 255))
        canvas.paste(inner_bg, (border_w, border_w))
        
        if id_img:
            id_img = id_img.resize((box_w, id_h))
            canvas.paste(id_img, (border_w, border_w), id_img)
            
        placeholder = Image.new("RGBA", (ego_sz, ego_sz), (0, 0, 0, 100))
        
        y_r2 = border_w + id_h + gap
        x_r2 = [0, 52, 104]
        for i in range(3):
            img = ego_imgs[i].resize((ego_sz, ego_sz)) if ego_imgs[i] else placeholder
            canvas.paste(img, (border_w + x_r2[i], y_r2), img)
            
        y_r3 = y_r2 + ego_sz + gap
        x_r3 = [28, 76]
        for i in range(3, 5):
            img = ego_imgs[i].resize((ego_sz, ego_sz)) if ego_imgs[i] else placeholder
            canvas.paste(img, (border_w + x_r3[i-3], y_r3), img)
            
        return canvas

    def build_full_team_image(self, team_data: dict, output_path="team.png"):
        print("🎨 開始合成 6x2 純網格大圖...")
        rentboxes = [self.create_rentbox(d) for d in team_data["identities"]]
        
        box_w, box_h = 148, 308
        # 【修改為 6x2 排版】
        cols, rows, padding = 6, 2, 15
        outer_border = 4
        
        inner_w = cols * box_w + padding * (cols + 1)
        inner_h = rows * box_h + padding * (rows + 1)
        bg_w = inner_w + (outer_border * 2)
        bg_h = inner_h + (outer_border * 2)
        
        canvas = Image.new("RGBA", (bg_w, bg_h), (101, 66, 34, 255))
        canvas.paste(Image.new("RGBA", (inner_w, inner_h), (30, 32, 36, 255)), 
                     (outer_border, outer_border))
        
        for i, box in enumerate(rentboxes):
            x = outer_border + padding + (i % cols) * (box_w + padding)
            y = outer_border + padding + (i // cols) * (box_h + padding)
            canvas.paste(box, (x, y), box)
            
        canvas.save(output_path)
        print(f"✅ 大圖合成完畢: {output_path}")

# ==========================================
# 6. Discord 通知模組
# ==========================================
class DiscordNotifier:
    @staticmethod
    def send(team_data: dict, image_path="team.png"):
        if not WEBHOOK_URL:
            print("⚠️ 未設定 DISCORD_WEBHOOK，跳過發送。")
            return

        payload = {
            "embeds": [{
                "title": "🗓️ 新一輪的鏡牢租借隊伍出來了！",
                "url": "https://github.com/anku0910/limbus-rental-monitor", # 點擊標題就會開啟 GitHub
                "description": f"**日期：** {team_data['date_timestamp']}\n**體系：** {team_data['keywords_zh']}",
                "color": 0x654222,
                "image": {"url": f"attachment://{image_path}"},
                "footer": {"text": "Limbus Company Auto Monitor"}
            }]
        }

        with open(image_path, "rb") as f:
            files = {
                "payload_json": (None, json.dumps(payload), "application/json"),
                image_path: (image_path, f, "image/png")
            }
            res = requests.post(WEBHOOK_URL, files=files)
            
        if res.status_code in [200, 204]:
            print("✅ 成功發送 Discord Webhook (含 Embed)！")
        else:
            print(f"❌ 發送失敗：HTTP {res.status_code}\n{res.text}")

# ==========================================
# 7. 主程序 (Orchestrator)
# ==========================================
def main():
    print("🔍 啟動 Rental Team Monitor...")
    
    state = StateManager.load()
    fetcher = WikiFetcher()
    
    wikitext = fetcher.get_latest_wikitext()
    team_data = Parser.parse_latest_team(wikitext)
    
    if not team_data:
        print("❌ 解析失敗：找不到 Rental Team 結構。")
        return
        
    current_id = team_data["unique_id"]
    print(f"📄 抓取到最新 Team: {team_data['keywords_zh']} (ID: {current_id})")
    
    if state.get("last_rental_team") == current_id:
        print("😴 狀態相同，尚無新隊伍，結束執行。")
        return
        
    print("✨ 發現新隊伍！開始處理圖片...")
    
    composer = ImageComposer(fetcher)
    composer.build_full_team_image(team_data)
    
    DiscordNotifier.send(team_data)
    
    state["last_rental_team"] = current_id
    StateManager.save(state)
    print("💾 狀態儲存完畢，流程結束。")

if __name__ == "__main__":
    main()
