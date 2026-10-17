# ClaimBack — VS Code 一键启动（Mac）

## 1. 运行

1. 解压 ZIP，把文件夹 `ClaimBack_VSCode_Complete` 用 VS Code 的 **File → Open Folder** 打开。
2. 菜单 **Terminal → New Terminal**，输入：

   ```bash
   ./run.sh
   ```

3. 在浏览器打开 **http://127.0.0.1:8000**。
4. 先体验 Demo Mode，不用 API Key：点开 `CB-0001`，点击 **Run investigation**，查看证据、AI 报告（此模式为模板，不是 LLM 输出）、执行步骤，最后 **Download .md**。
5. 进入左侧 **Reliability lab**，分别点击 **Run v1 failures** 和 **Verify v2 fix**；可以展示同一组案例修复前后的区别。

## 2. 配置真正的 AI 和 PRISM

打开项目根目录 `.env` 文件。`run.sh` 启动时会从 `.env.example` 自动复制。如果还没有它，手工复制也可以。

```ini
NICRRON_API_KEY=你的Nicrron密钥
NICRRON_MODEL=nicrron/auto
PRISMTRACE_HOST=https://prism.blockconvey.com
PRISMTRACE_API_KEY=你的PRISM密钥
PRISMTRACE_PROJECT_ID=你的PRISM项目UUID
```

修改以后**重启服务**（终端按 Control+C，再运行 `./run.sh`）。在界面选择 Live Mode，这时 `write_response` 会调用 Nicrron AI，后台尝试把真实执行记录和实际步骤发到 PRISM。只有在 PRISM 官网看见执行记录和 Alerts / Root Cause，才能当成比赛证明。

## 3. 比赛三个 Proof

- **Sessions：** 在 PRISM 找到 v2 的真实运行，检查至少 6 个工具/工作流步骤。本项目有 8 步。
- **Alert：** 在 PRISM 的 Alerts 手动设置错误警报；运行 v1 产生已知的测试故障，确认警报触发。
- **Root Cause：** 在 Reliability lab 中运行 v1（CB-0005 / 0010 / 0015），再运行 v2，并在 PRISM 验证是否形成失败原因聚类。官方建议积累 50+ 次运行。

## 4. 如果启动失败

- `permission denied` → 使用 `bash run.sh`。
- `python3: command not found` → 安装 Python 3.10+，重新打开 VS Code。
- `address already in use` → 关闭之前运行的服务或调整端口。
- `ModuleNotFoundError` → 确认终端已激活 `.venv`，执行 `python -m pip install -r requirements.txt`。
- `Live mode needs Nicrron` → 检查 `.env`，然后重启服务。
- `PRISM trace 没看到` → 到 **Agent activity** 点击 Run 查看上传状态，检查密钥和 Project UUID；本地状态 `sent` 只表示 API 接受请求，还需 PRISM 页面最终确认。

**注意：** Demo Mode 不调用 Nicrron；项目没有真实银行卡、自动支付、真实 Chargeback 提交；导入仅支持示例 JSON，不支持 PDF/OCR。不要上传真实隐私信息。
