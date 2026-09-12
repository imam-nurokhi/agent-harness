#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${HOME}/AI-Workspace"
PROJECT_ROOT="${WORKSPACE_ROOT}/projects/sandbox"
AGENT_ROOT="${WORKSPACE_ROOT}/agents"

echo "== Agent Harness bootstrap for macOS Apple Silicon =="

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew belum ditemukan. Install Homebrew dari https://brew.sh lalu jalankan script ini kembali."
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  brew install node
fi

mkdir -p "${PROJECT_ROOT}" "${AGENT_ROOT}/roles" "${AGENT_ROOT}/prompts" "${AGENT_ROOT}/reports" "${WORKSPACE_ROOT}/worktrees" "${WORKSPACE_ROOT}/archives"

if ! command -v codex >/dev/null 2>&1; then
  npm install -g @openai/codex
fi

if ! command -v claude >/dev/null 2>&1; then
  npm install -g @anthropic-ai/claude-code
fi

if [ ! -f "${PROJECT_ROOT}/README.md" ]; then
  cat > "${PROJECT_ROOT}/README.md" <<'EOF'
# Agent Harness Sandbox

Folder ini digunakan untuk menguji agent sebelum diberi akses ke repository penting.

## Aturan
- Jangan masukkan credential atau data sensitif.
- Semua perubahan harus melalui review.
- Gunakan task kecil dan dapat diverifikasi.
EOF
fi

echo
echo "Workspace siap: ${WORKSPACE_ROOT}"
echo "Sandbox siap:   ${PROJECT_ROOT}"
echo
echo "Langkah berikutnya:"
echo "1. Jalankan: codex"
echo "2. Login menggunakan akun ChatGPT."
echo "3. Jalankan: claude"
echo "4. Login menggunakan akun Claude."
echo "5. Download dan install Munder Difflin dari https://munderdiffl.in"
echo "6. Tambahkan folder ${WORKSPACE_ROOT} pada onboarding Munder Difflin."

