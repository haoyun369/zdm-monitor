#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# smzdm_wecom_pusher.py   —— 什么值得买「全站好价」监控推送
# 逻辑：每 POLL_SECONDS 秒抓一次 smzdm 好价 → 找出新出现的好价
#       → 标题命中 keywords.txt 里的关键字 → 推送企业微信
# 企微三项读 smzdm 自己的 /opt/smzdm/config.txt（与 zkb 分开，另用一套应用）
# ============================================================
import json, os, re, sys, time, html as H
import urllib.request, urllib.parse

# ---- 路径（按需修改）----
CONFIG_PATH  = "/opt/smzdm/config.txt"   # 企微三项（smzdm 自己的一套，与 zkb 分开）
KEYWORDS_PATH = "/opt/smzdm/keywords.txt" # 关键字
SEEN_PATH    = "/opt/smzdm/smzdm_seen.json" # 已看过的好价 ID
LOG_PATH     = "/opt/smzdm/smzdm.log"      # 日志

# ---- 参数 ----
POLL_SECONDS = 60     # 每 60 秒抓一次好价（想改：sed 替换）
SMZDM_URL    = "https://www.smzdm.com/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
      "Referer": "https://www.smzdm.com/"}

DRY = "--dry" in sys.argv   # 测试用：只抓取+过滤，不推送、不写记录


def log(msg):
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    if not DRY:
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def load_kv(path):
    c = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                c[k.strip()] = v.strip()
    except Exception as e:
        log("config 读取失败: %s" % e)
    return c


def load_keywords(path):
    kws = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    kws.append(line)
    except Exception as e:
        log("keywords 读取失败: %s" % e)
    return kws


def load_seen(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_seen(path, ids):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ids, f)
    except Exception as e:
        log("seen 保存失败: %s" % e)


def get_token(corpid, secret):
    try:
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=%s&corpsecret=%s" % (
            urllib.parse.quote(corpid), urllib.parse.quote(secret))
        r = json.loads(urllib.request.urlopen(url, timeout=15).read().decode())
        if r.get("errcode") == 0:
            return r["access_token"]
        log("gettoken 失败: %s" % r)
    except Exception as e:
        log("gettoken 异常: %s" % e)
    return None


def send_wecom(token, agentid, content):
    try:
        url = "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=" + token
        body = {"touser": "@all", "msgtype": "text",
                "agentid": int(agentid), "text": {"content": content}}
        req = urllib.request.Request(
            url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        if r.get("errcode") != 0:
            log("发送失败: %s" % r)
    except Exception as e:
        log("发送异常: %s" % e)


_TITLE_PAT = re.compile(
    r'<a[^>]*href="https://www\.smzdm\.com/p/(\d+)/[^"]*"[^>]*>(.*?)</a>', re.S)
# 带价格的卡片：标题(h5.feed-block-title) 与价格(div.z-highlight) 在同一卡片内、指向同一 /p/id/
_PAIRED_PAT = re.compile(
    r'<h5[^>]*class="[^"]*feed-block-title[^"]*"[^>]*>\s*<a[^>]*href="(https://www\.smzdm\.com/p/(\d+)/[^"]*)"[^>]*>(.*?)</a>\s*</h5>'
    r'(?:\s*<!--[^>]*-->)?\s*<div[^>]*class="z-highlight[^"]*"[^>]*>\s*<a[^>]*>(.*?)</a>', re.S)
_BAD_MARK = ("跳转", "埋点", "BannerClick", "onclick", "dataLayer", "function", "var ")


def _clean(x):
    return H.unescape(re.sub(r"<[^>]+>", "", x)).strip()


def fetch_deals():
    req = urllib.request.Request(SMZDM_URL, headers=UA)
    h = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    deals = {}
    # 1) 带价格的好价卡片（标题+价格同卡、同 id，可靠）
    for link, aid, title, price in _PAIRED_PAT.findall(h):
        t, p = _clean(title), _clean(price)
        if t and aid not in deals:
            deals[aid] = {"id": aid, "title": t,
                          "link": "https://www.smzdm.com/p/%s/" % aid, "price": p}
    # 2) 其它卡片兜底（标题+链接，无价格；不给错误价）
    for m in _TITLE_PAT.finditer(h):
        aid = m.group(1)
        text = _clean(m.group(2))
        if not text or any(x in text for x in _BAD_MARK):
            continue
        if aid not in deals:
            deals[aid] = {"id": aid, "title": text,
                          "link": "https://www.smzdm.com/p/%s/" % aid, "price": None}
    return list(deals.values())


def main():
    log("started: poll every %ss, config=%s, keywords=%s, dry=%s" % (
        POLL_SECONDS, CONFIG_PATH, KEYWORDS_PATH, DRY))
    cfg = load_kv(CONFIG_PATH)
    kws = load_keywords(KEYWORDS_PATH)
    seen = set(load_seen(SEEN_PATH))
    log("seeded %d existing deals, %d keywords" % (len(seen), len(kws)))
    token, token_at = None, 0

    while True:
        try:
            cfg = load_kv(CONFIG_PATH)          # 每轮重读，改配置 60 秒内生效
            kws = load_keywords(KEYWORDS_PATH)  # 每轮重读关键字
            corpid = cfg.get("CORP_ID") or cfg.get("CORPID") or ""
            agentid = cfg.get("AGENT_ID") or cfg.get("AGENTID") or ""
            secret = cfg.get("AGENT_SECRET") or ""

            deals = fetch_deals()
            current = set()
            matched = []
            for d in deals:
                aid = d["id"]
                current.add(aid)
                if aid in seen:
                    continue
                hit = [k for k in kws if k and k in d["title"]]
                if hit:
                    matched.append((d, hit))

            for d, hit in matched:
                content = "%s\n%s\n%s" % (d["title"], d["price"] or "", d["link"])
                if not d["price"]:
                    content = "%s\n%s" % (d["title"], d["link"])
                if DRY:
                    log("[DRY] 命中 %s → %s | %s | %s" % (hit, d["title"], d["price"] or "无价", d["link"]))
                else:
                    if not token or time.time() - token_at > 7000:
                        token = get_token(corpid, secret)
                        token_at = time.time()
                    if token:
                        send_wecom(token, agentid, content)
                        log("已推送: %s | %s" % (d["title"][:40], hit))
                    else:
                        log("推送跳过(无token): %s" % d["title"][:40])

            if not DRY and current:
                seen |= current
                save_seen(SEEN_PATH, sorted(seen))
            if DRY:
                break          # 测试模式：跑一轮就退出
            time.sleep(POLL_SECONDS)
        except Exception as e:
            log("循环异常: %s" % e)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
