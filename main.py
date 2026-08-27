import os
import re
import json
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

WIKI_API_URL = "https://limbuscompany.wiki.gg/api.php"
STATE_FILE = "state.json"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

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

class WikiFetcher:
    def __init__(self):
        self.session = requests.Session()

    def get_latest_wikitext(self) -> str:
        params = {
            "action": "query", "prop": "revisions",
            "titles": "List_of_Rental_Teams", "rvprop": "content",
            "rvslots": "main", "format": "json"
        }
        res = self.session.get(WIKI_API_URL, params=params).json()
        pages = res.get("query", {}).get("pages", {})
        if not pages: return ""
        page_id = list(pages.keys())[0]
        return pages[page_id]["revisions"][0]["slots"]["main"]["*"]

    def get_image_url(self, file_title: str) -> str:
        params = {
            "action": "query", "prop": "imageinfo",
            "iiprop": "url", "titles": f"File:{file_title}", "format": "json"
        }
        res = self.session.get(WIKI_API_URL, params=params).json()
        pages = res.get("query", {}).get("pages", {})
        page_id = list(pages.keys())[0]
        if int(page_id) < 0 or "imageinfo" not in pages[page_id]: return None
        return pages[page_id]["imageinfo"][0]["url"]

class Parser:
    @staticmethod
    def parse_latest_team(wikitext: str) -> dict:
        blocks = re.split(r'(?=\{\{RentTab)', wikitext)
        for block in blocks:
            if "{{RentTab" not in block: continue
            date_m = re.search(r'date=(.*?)\|', block)
            kw_m = re.search(r'keywords=(.*?)\|', block)
            date_str = date_m.group(1).strip() if date_m else "Unknown Date"
            kw_str = kw_m.group(1).strip() if kw_m else "None"
            
            identities = []
            boxes = re.finditer(r'\{\{RentBox\s*\|(.*?)\}\}', block, re.DOTALL)
            for box in boxes:
                box_str = box.group(1)
                fields = {}
                for match in re.finditer(r'([a-zA-Z0-9_]+)\s*=\s*([^|}]*)', box_str):
                    key, val = match.group(1).strip().lower(), match.group(2).strip()
                    if val: fields[key] = val
                if "sinner" in fields and "id" in fields:
                    identities.append(fields)
                    
            if len(identities) > 0:
                return {
                    "date": date_str, "keywords": kw_str,
                    "identities": identities[:12],
                    "unique_id": f"{date_str}-{kw_str}"
                }
        return None

class ImageComposer:
    def __init__(self, fetcher: WikiFetcher):
        self.fetcher = fetcher
        self.image_cache = {}

    def download_image(self, url: str) -> Image.Image:
        if not url: return None
        if url in self.image_cache: return self.image_cache[url].copy()
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

        box_w, id_h, ego_sz, gap, border_w = 115, 177, 30, 2, 4
        border_color = (240, 203, 27, 255) if rarity == 3 else (174, 1, 0, 255)
        inner_h = id_h + gap + ego_sz + gap + ego_sz + 4
        out_w, out_h = box_w + (border_w * 2), inner_h + (border_w * 2)
        
        canvas = Image.new("RGBA", (out_w, out_h), border_color)
        canvas.paste(Image.new("RGBA", (box_w, inner_h), (30, 32, 36, 255)), (border_w, border_w))
        
        if id_img:
            id_img = id_img.resize((box_w, id_h))
            canvas.paste(id_img, (border_w, border_w), id_img)
            
        placeholder = Image.new("RGBA", (ego_sz, ego_sz), (0, 0, 0, 100))
        y_r2, x_r2 = border_w + id_h + gap, [0, 42, 85]
        for i in range(3):
            img = ego_imgs[i].resize((ego_sz, ego_sz)) if ego_imgs[i] else placeholder
            canvas.paste(img, (border_w + x_r2[i], y_r2), img)
            
        y_r3, x_r3 = y_r2 + ego_sz + gap, [21, 64]
        for i in range(3, 5):
            img = ego_imgs[i].resize((ego_sz, ego_sz)) if ego_imgs[i] else placeholder
            canvas.paste(img, (border_w + x_r3[i-3], y_r3), img)
            
        return canvas

    def build_full_team_image(self, team_data: dict, output_path="team.png"):
        print("🎨 開始合成 RentBoxes...")
        rentboxes = [self.create_rentbox(d) for d in team_data["identities"]]
        
        box_w, box_h, cols, rows, padding, header_h, outer_border = 123, 223, 4, 3, 10, 80, 3
        inner_w = cols * box_w + padding * (cols + 1)
        inner_h = rows * box_h + padding * (rows + 1)
        bg_w, bg_h = inner_w + (outer_border * 2), inner_h + header_h + (outer_border * 2)
        
        canvas = Image.new("RGBA", (bg_w, bg_h), (101, 66, 34, 255))
        canvas.paste(Image.new("RGBA", (inner_w, inner_h), (30, 32, 36, 255)), (outer_border, header_h + outer_border))
        
        draw = ImageDraw.Draw(canvas)
        draw.text((padding + outer_border, 15), f"Date: {team_data['date']}", fill=(255, 255, 255))
        draw.text((padding + outer_border, 45), f"Keywords: {team_data['keywords']}", fill=(200, 200, 200))
        
        for i, box in enumerate(rentboxes):
            x = outer_border + padding + (i % cols) * (box_w + padding)
            y = outer_border + header_h + padding + (i // cols) * (box_h + padding)
            canvas.paste(box, (x, y), box)
            
        canvas.save(output_path)
        print(f"✅ 大圖合成完畢: {output_path}")

class DiscordNotifier:
    @staticmethod
    def send(team_data: dict, image_path="team.png"):
        if not WEBHOOK_URL:
            print("⚠️ 未設定 DISCORD_WEBHOOK，跳過發送。")
            return
        payload = {
            "embeds": [{
                "title": "🗓️ New Limbus Rental Team Available",
                "description": f"**Date:** {team_data['date']}\n**Keywords:** {team_data['keywords']}",
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
            
        if res.status_code in [200, 204]: print("✅ 成功發送 Discord Webhook (含 Embed)！")
        else: print(f"❌ 發送失敗：HTTP {res.status_code}\n{res.text}")

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
    print(f"📄 抓取到最新 Team: {current_id}")
    
    if state.get("last_rental_team") == current_id:
        print("😴 狀態相同，尚無新隊伍，結束執行。")
        return
        
    print("✨ 發現新隊伍！開始處理...")
    composer = ImageComposer(fetcher)
    composer.build_full_team_image(team_data)
    
    DiscordNotifier.send(team_data)
    
    state["last_rental_team"] = current_id
    StateManager.save(state)
    print("💾 狀態儲存完畢，流程結束。")

if __name__ == "__main__":
    main()
