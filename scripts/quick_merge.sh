#!/usr/bin/env bash
# quick_merge.sh — 跳 PR 直推主幹（CLAUDE.md §4 例外條款專用）
#
# 用法：
#   ./scripts/quick_merge.sh "commit message"
#
# 行為：
#   1. 確認當前不在主幹（main / master）+ working tree 乾淨
#   2. 切到主幹、pull --ff-only
#   3. git merge --squash 原本分支
#   4. commit（用傳入訊息）+ push origin <主幹>
#   5. 刪本地 + 遠端的原分支
#
# 適用對象（CLAUDE.md §4）：
#   - STATE.md / CLAUDE.md / 註解 / typo
#   - 版本字串 bump（不含程式邏輯）
#   - 不影響功能行為的純文件改動

set -euo pipefail

if [[ $# -lt 1 || -z "${1:-}" ]]; then
    echo "❌ 用法：$0 \"commit message\"" >&2
    exit 1
fi

MSG="$1"

# 偵測主幹（main 優先，否則 master）
if git show-ref --verify --quiet refs/heads/main; then
    TRUNK="main"
elif git show-ref --verify --quiet refs/heads/master; then
    TRUNK="master"
else
    echo "❌ 找不到 main 或 master 分支" >&2
    exit 1
fi

CURRENT="$(git rev-parse --abbrev-ref HEAD)"

if [[ "$CURRENT" == "$TRUNK" ]]; then
    echo "❌ 當前已在主幹 ($TRUNK)；本腳本應從 feature 分支執行" >&2
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "❌ Working tree 不乾淨，請先 commit 或 stash：" >&2
    git status --short >&2
    exit 1
fi

echo "→ 主幹：$TRUNK"
echo "→ 來源分支：$CURRENT"
echo "→ Commit message：$MSG"

# 切主幹 + 拉最新
git checkout "$TRUNK"
git pull --ff-only origin "$TRUNK"

# squash merge feature 分支
git merge --squash "$CURRENT"

# commit + push
git commit -m "$MSG"
git push origin "$TRUNK"

# 清理 feature 分支
git branch -D "$CURRENT"
if git ls-remote --exit-code --heads origin "$CURRENT" >/dev/null 2>&1; then
    git push origin --delete "$CURRENT" || echo "⚠️ 遠端分支刪除失敗（可手動處理）"
fi

echo "✅ 已 squash-merge $CURRENT → $TRUNK 並清理"
