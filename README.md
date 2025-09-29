# TickTick Habit -> Slack Poster

Daily job that fetches TickTick habit analytics and posts progress updates to your Slack accountability channels.

## Prerequisites
- Python 3.9+
- TickTick developer app with OAuth client credentials (needed to mint an access token manually)
- Slack app with a bot token (`chat:write` scope) added to your target channels

## Setup
1. **Install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Prepare environment variables**
   ```bash
   cp .env.example .env
   edit .env
   ```
   Fill in at least:
   - `TICKTICK_ACCESS_TOKEN` – obtain this via the TickTick OAuth authorize/token exchange. Note that access tokens expire quickly; you must refresh this value manually whenever it expires.
   - `SLACK_BOT_TOKEN` – from your Slack app
   - Optionally `SLACK_DEFAULT_CHANNEL` – used when a habit mapping omits `slack_channel`
   - Optional but recommended for the helper script: `TICKTICK_CLIENT_ID`, `TICKTICK_CLIENT_SECRET`, `TICKTICK_REDIRECT_URI`
3. **Mint a TickTick access token**
   Run the OAuth authorization code flow (see "Manual TickTick access token" below). Use `python scripts/ticktick_auth_link.py` to generate the browser link, then `python scripts/ticktick_code_exchange.py CODE` to swap the returned `code` for an access token. Paste the token into `.env` as `TICKTICK_ACCESS_TOKEN`.
4. **Create the habit mapping**
   ```bash
   cp config/habits.example.yaml config/habits.yaml
   edit config/habits.yaml
   ```
   Each habit entry needs at least a `title` and the Slack channel that should receive updates. Include `habit_id` for unambiguous matching (run `python scripts/ticktick_to_slack.py --list-habits` to see the IDs once credentials are in place). You can customise `message_template` per habit using placeholders like `{title}`, `{status}`, `{value}`, `{streak}`.

## Running manually
```bash
source .venv/bin/activate
python scripts/ticktick_to_slack.py --dry-run   # inspect payloads without posting
python scripts/ticktick_to_slack.py             # post to Slack
```
Use `--date YYYY-MM-DD` to fetch a past day. `--list-habits` prints all habits and exits (Slack token not required for that call).

## Scheduling via cron
Cron uses the host timezone. To guarantee an 8 pm IST run irrespective of the machine's timezone, prefix the job with `TZ=Asia/Kolkata`.

```cron
0 20 * * * TZ=Asia/Kolkata /path/to/venv/bin/python /path/to/codex-test/scripts/ticktick_to_slack.py >> /path/to/logs/ticktick_cron.log 2>&1
```

- Replace `/path/to/venv/bin/python` with the Python interpreter from your virtual environment.
- Update `/path/to/codex-test` with this repository's absolute path.
- Redirecting output to a log file is optional but recommended for monitoring.

After editing the crontab (`crontab -e`), verify the entry with `crontab -l`.

## Habit configuration format
```yaml
habits:
  - title: "Meditation"
    habit_id: "abcdef12-3456-7890-abcd-ef1234567890"  # optional but recommended
    slack_channel: "#accountability"
    message_template: "*{title}*: {status} (streak: {streak})"
  - title: "Workout"
    slack_channel: "#fitness"

default_template: "*{title}*: {status}"
```
Add or adjust entries whenever you want to report a different habit or change the destination channel.

## Manual TickTick access token
TickTick issues short-lived access tokens. Whenever the token expires, repeat this flow and update `TICKTICK_ACCESS_TOKEN` in `.env`:

1. Generate the authorization URL using the helper script (falls back to `.env` values):
   ```bash
   python scripts/ticktick_auth_link.py
   ```
   The script prints the URL and tries to open your default browser. Copy the displayed `state` value; you will confirm it later. You can also supply flags such as `--client-id`, `--redirect-uri`, or `--no-browser` if needed.
   Prefer to construct manually? Use the format:
   ```
   https://ticktick.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=ENCODED_REDIRECT&response_type=code&scope=tasks%3Aread%20tasks%3Awrite%20habit%3Aread&state=SOME_RANDOM_STRING
   ```
   Ensure `redirect_uri` matches your TickTick app settings.
2. Copy the `code` query parameter from the redirected URL.
3. Exchange the code for tokens:
   ```bash
   curl https://ticktick.com/oauth/token \
        --data-urlencode "client_id=YOUR_CLIENT_ID" \
        --data-urlencode "client_secret=YOUR_CLIENT_SECRET" \
        --data-urlencode "grant_type=authorization_code" \
        --data-urlencode "redirect_uri=YOUR_REDIRECT_URI" \
        --data-urlencode "code=AUTH_CODE_FROM_STEP_2"
   ```
   Or use the helper script (reads credentials from `.env` or CLI flags):
   ```bash
   python scripts/ticktick_code_exchange.py AUTH_CODE_FROM_STEP_2
   ```
4. Copy the `access_token` from the JSON response and paste it into `.env` as `TICKTICK_ACCESS_TOKEN`.

If your network uses TLS inspection, add `--cacert /path/to/proxy-root.pem` to the `curl` command so the handshake succeeds.

## Troubleshooting
- `ModuleNotFoundError`: ensure you installed packages with `pip install -r requirements.txt` inside your virtualenv.
- `Slack API error`: verify the bot has been invited to the channel and the token has `chat:write` scope.
- `TickTick access token expired`: repeat the manual OAuth exchange above and update `TICKTICK_ACCESS_TOKEN` in `.env`.
