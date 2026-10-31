# smzdm 好价监控（服务器部署）

企业微信「什么值得买」全站好价监控。脚本抓 smzdm 首页好价，标题命中 keywords.txt 中的关键词即推送企微（标题+价格+链接）。

## 目录
- smzdm_wecom_pusher.py : 监控脚本（读 /opt/smzdm/config.txt）
- keywords.txt : 关键词清单（每行一个，改完 60 秒生效）
- config.txt : 企微三项模板（占位符，**不含真实密钥**）

## 部署（服务器执行一行）
```
mkdir -p /opt/_sm && curl -sL https://codeload.github.com/haoyun369/zdm-monitor/tar.gz/refs/heads/main | tar xz -C /opt/_sm && bash /opt/_sm/*/deploy.sh
```
首次会生成 /opt/smzdm/config.txt 占位符，填好三项后重跑上面命令即启动。

## 密钥安全
config.txt 内的 CORP_ID/AGENT_ID/AGENT_SECRET 属于敏感信息，请勿上传到公开仓库；本仓库只放占位符模板。

## 常用操作
- 改关键词：编辑 /opt/smzdm/keywords.txt（60 秒生效）
- 看日志：tail -f /opt/smzdm/smzdm.log
- 重启：bash /opt/smzdm/deploy.sh
