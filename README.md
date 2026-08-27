# Limbus Company Rental Team Monitor
<img width="1012" height="762" alt="Snipaste_2026-08-27_20-27-42" src="https://github.com/user-attachments/assets/22c291c4-b05b-4244-9e9e-686325a5d9a3" />

[English](#english) | [繁體中文](#繁體中文)

---

<a name="english"></a>
## English

A serverless Python automation tool that monitors the [Limbus Company wiki.gg](https://limbuscompany.wiki.gg/) for updates to the Rental Team page and pushes a generated visual grid to a Discord Webhook.

**Disclaimer:** All data and image assets are programmatically retrieved from the Limbus Company wiki.gg using the MediaWiki API. All game assets and intellectual property belong to Project Moon.

### Features
* **Serverless Architecture:** Runs entirely on GitHub Actions, requiring no dedicated hosting or local machine presence.
* **Visual Output:** Dynamically generates a clean 6x2 image grid using `Pillow` to preview the 12 Sinners and their equipped E.G.O.
* **API-Driven:** Utilizes the official MediaWiki API to fetch Wikitext instead of HTML scraping, ensuring stability and minimizing server load on wiki.gg.
* **Smart Caching:** Implements in-memory caching for E.G.O icons during image generation to reduce redundant API requests.
* **State Management:** Maintains a local `state.json` pushed back to the repository to prevent duplicate Discord notifications.

### Setup and Deployment

1. **Fork the Repository:** Fork this repository to your own GitHub account.
2. **Create a Discord Webhook:** In your Discord server, navigate to Channel Settings > Integrations > Webhooks and create a new webhook. Copy the Webhook URL.
3. **Set up GitHub Secrets:**
   * Go to your forked repository's **Settings**.
   * Navigate to **Secrets and variables** > **Actions** > **New repository secret**.
   * Name: `DISCORD_WEBHOOK`
   * Secret: Paste your Discord Webhook URL.
4. **Configure Action Permissions:**
   * In repository **Settings**, go to **Actions** > **General**.
   * Scroll down to **Workflow permissions** and select **Read and write permissions**. Save the changes.
5. **Initial Run:**
   * Go to the **Actions** tab.
   * Select the `Limbus Rental Team Monitor` workflow.
   * Click **Run workflow** to trigger the initial execution.

### Configuration
The default cron schedule in `.github/workflows/monitor.yml` is set to run at specific UTC times. You can modify the `cron` expression to fit your preferred checking frequency.

---

<a name="繁體中文"></a>
## 繁體中文

一個基於無伺服器架構的 Python 自動化工具，用於監控 [Limbus Company wiki.gg](https://limbuscompany.wiki.gg/) 的租借隊伍（Rental Team）更新，並自動生成視覺化網格圖片推送到 Discord Webhook。

**免責聲明：** 本專案的所有數據與圖片資產均透過 MediaWiki API 從 Limbus Company wiki.gg 抓取。所有遊戲資產與智慧財產權皆屬於 Project Moon。

### 功能特色
* **無伺服器架構：** 完全依賴 GitHub Actions 運行，無需配置專屬伺服器或保持本機常駐。
* **視覺化輸出：** 使用 `Pillow` 動態生成 6x2 橫向網格圖片，清晰預覽 12 名角色的身分（Identity）與裝備的 E.G.O。
* **API 驅動：** 使用官方 MediaWiki API 讀取 Wikitext，取代傳統 HTML 網頁爬蟲，提升穩定性並大幅降低 wiki.gg 的伺服器負擔。
* **智慧快取：** 在圖片合成過程中實作記憶體快取機制，避免重複下載相同的 E.G.O 圖示。
* **狀態管理：** 透過將 `state.json` 寫回儲存庫來記錄最新狀態，防止發送重複的 Discord 通知。

### 部署指南

1. **Fork 儲存庫：** 將此專案 Fork 到你個人的 GitHub 帳號中。
2. **建立 Discord Webhook：** 在你的 Discord 伺服器中，進入頻道設定 > 整合 > Webhooks，建立一個新的 Webhook 並複製其網址。
3. **設定 GitHub Secrets：**
   * 進入你 Fork 後的儲存庫 **Settings**。
   * 導覽至 **Secrets and variables** > **Actions** > **New repository secret**。
   * Name（名稱）填寫：`DISCORD_WEBHOOK`
   * Secret（密鑰）填寫：貼上你的 Discord Webhook 網址。
4. **設定 Action 讀寫權限：**
   * 在儲存庫 **Settings** 中，進入 **Actions** > **General**。
   * 向下捲動至 **Workflow permissions**，選擇 **Read and write permissions**，並儲存變更。
5. **首次執行：**
   * 點擊儲存庫上方的 **Actions** 標籤。
   * 選擇左側的 `Limbus Rental Team Monitor` 工作流。
   * 點擊 **Run workflow** 觸發首次執行與測試。

### 自訂設定
工作流設定檔 `.github/workflows/monitor.yml` 中的預設 cron 排程已設定為特定的 UTC 時間。你可以透過修改 `cron` 表達式來更改系統檢查更新的頻率與時間。
