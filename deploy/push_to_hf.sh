#!/bin/sh
# Uploads this project to a Hugging Face Docker Space (large files such as pothole_best.pt are handled for you).
#   uvx --from huggingface_hub hf auth login            # once; paste a token with "write" access
#   sh deploy/push_to_hf.sh Anurag137/swayam-sevak
# Secrets (.env, keys) are never uploaded: add them in the Space's Settings -> Variables and secrets.
set -e
SPACE="${1:?usage: sh deploy/push_to_hf.sh <owner>/<space-name>}"
cd "$(dirname "$0")/.."
HF="uvx --from huggingface_hub hf"

$HF upload "$SPACE" . . --repo-type space \
  --exclude ".git/*" \
  --exclude ".venv/*" \
  --exclude ".data/*" \
  --exclude "web/node_modules/*" \
  --exclude "web/dist/*" \
  --exclude "**/__pycache__/*" \
  --exclude ".pytest_cache/*" \
  --exclude ".env" \
  --exclude ".env.*" \
  --exclude "README.md" \
  --exclude "*.pyc" \
  --exclude "registry/*/drafts/*" \
  --exclude "registry/*/patches/*" \
  --exclude "reports/*" \
  --exclude "voice-check/*" \
  --commit-message "Deploy Swayam-sevak"
# The Space needs its own README header (sdk: docker, app_port: 7860).
$HF upload "$SPACE" deploy/hf-space-README.md README.md --repo-type space --commit-message "Space README"
echo "Done. Build log: https://huggingface.co/spaces/$SPACE?logs=build"
