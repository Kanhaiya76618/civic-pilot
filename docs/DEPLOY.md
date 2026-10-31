# Deploying Part 3

One container runs the executor, the citizen console and the sandbox portal.
Only the executor's port is public; the agent's browser reaches the sandbox
internally, and the citizen sees it through the live view.

## Hugging Face Spaces (free, gives the "live URL" the submission asks for)

1. Create a Space: SDK **Docker**, hardware **CPU basic**.
2. In the Space's *Settings → Variables and secrets* add:
   - Secret `AIMLAPI_KEY` (or `ANTHROPIC_API_KEY`): for AI explore and repair. Set a spending cap on the key.
   - Secret `CIVIC_API_KEY`: the key Part 1 and Part 2 send as `X-API-Key`.
   - Secret `CIVIC_WEBHOOK_SECRET`: shared with Part 1 and Part 2 for webhook signatures.
   - Secret `CIVIC_VAULT_KEY`: generate it with the command below.
   - Variable `CIVIC_PUBLIC_URL`: `https://<user>-<space>.hf.space`.
3. Push the repo to the Space, with `deploy/hf-space-README.md` as the Space's `README.md`. The Space needs its front matter:

```bash
git clone https://huggingface.co/spaces/<user>/<space> hf-space
```

```bash
rsync -a --exclude .git --exclude .venv --exclude .data --exclude .env --exclude web/node_modules --exclude web/dist ./ hf-space/
```

```bash
cp deploy/hf-space-README.md hf-space/README.md
```

Then commit and push inside `hf-space/`. The first build takes several minutes, because it installs Chromium.

To generate the vault key:

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Render or any Docker host

Create a Web Service from the repo with the Dockerfile. Set the same variables;
`PORT` is provided by Render. Free instances sleep when idle, so open the URL a
minute before judging.

## Build and run locally

```bash
docker build -t civic-pulse .
```

```bash
docker run --rm -p 7860:7860 -e AIMLAPI_KEY -e CIVIC_PUBLIC_URL=http://localhost:7860 civic-pulse
```

Then open http://localhost:7860.

## Notes

- The Dockerfile builds the web app (`web/`) in a Node stage and copies only the built files into the image. You do not need Node on the server.
- Set `PART1_API_URL` and `PART2_API_URL` when your teammates' services are live; until then their pages show "not connected yet".
- Data lives in `/tmp/civic-data` inside the container and is lost on restart. That is fine for a demo; mount a volume to keep it.
- Patches and drafts from the healer and explorer are written into `registry/*/patches` and `registry/*/drafts` inside the container. Copy any you want to keep into git.
- The start-up script was tested outside Docker. The image itself was not built on the development machine (Docker was not running there): build it once before the deadline.
