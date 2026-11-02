from unittest import mock

from tvm.config import TVMConfig
from tvm import notify
from tests.test_report import sample_report

CFG = TVMConfig()


def test_text_is_compact_and_informative():
    txt = notify.to_text(sample_report(), None, CFG, mode="preview")
    assert txt.startswith("TVM Oct 30 [preview]: RISK-ON SPY 0.88x (vol 23%)")
    assert "Orders (not sent): buy BIL $11.7k, buy SPY $88.3k" in txt
    assert len(txt) < 300


def test_text_live_with_perf_and_cash_regime():
    rep = sample_report(orders=False, dry_run=False)
    rep["signal"]["risk_on"] = False
    perf = {"since": "2026-11-03", "equity": 101_234.0, "strategy_return": 0.0123, "benchmark_return": -0.004}
    txt = notify.to_text(rep, perf, CFG, mode="live")
    assert txt == ("TVM Oct 30: RISK-OFF -> cash (below 200d SMA). No trades. "
                   "Paper $101,234 +1.2% vs VOO -0.4% since Nov 03.")


def test_channels_skip_when_unconfigured():
    assert notify.send_all("x", env={}) == {k: "skipped" for k in notify.CHANNELS}


def test_twilio_and_ntfy_and_telegram_requests():
    env = {"TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "t", "TWILIO_FROM": "+1555", "TWILIO_TO": "+1444",
           "NTFY_TOPIC": "my-topic", "TELEGRAM_BOT_TOKEN": "bot", "TELEGRAM_CHAT_ID": "42"}
    with mock.patch.object(notify.requests, "post") as post:
        post.return_value.raise_for_status = lambda: None
        res = notify.send_all("hello", env=env)
    assert res["twilio"] == res["ntfy"] == res["telegram"] == "sent" and res["email-sms"] == "skipped"
    urls = [c.args[0] for c in post.call_args_list]
    assert "https://api.twilio.com/2010-04-01/Accounts/AC1/Messages.json" in urls
    assert "https://ntfy.sh/my-topic" in urls
    assert "https://api.telegram.org/botbot/sendMessage" in urls
    twilio_call = next(c for c in post.call_args_list if "twilio" in c.args[0])
    assert twilio_call.kwargs["data"] == {"From": "+1555", "To": "+1444", "Body": "hello"}
    assert twilio_call.kwargs["auth"] == ("AC1", "t")


def test_email_sms_uses_smtp():
    env = {"SMTP_HOST": "smtp.example.com", "SMTP_USER": "me@example.com", "SMTP_PASSWORD": "pw",
           "SMS_EMAIL_TO": "5551234567@tmomail.net"}
    smtp = mock.MagicMock()
    factory = mock.MagicMock(return_value=smtp)
    smtp.__enter__.return_value = smtp
    assert notify.send_email_sms("hi", env=env, smtp_factory=factory)
    factory.assert_called_once_with("smtp.example.com", 587, timeout=notify.TIMEOUT)
    smtp.login.assert_called_once_with("me@example.com", "pw")
    sent = smtp.send_message.call_args.args[0]
    assert sent["To"] == "5551234567@tmomail.net" and sent.get_content().strip() == "hi"


def test_channel_errors_do_not_raise():
    env = {"NTFY_TOPIC": "x"}
    with mock.patch.object(notify.requests, "post", side_effect=RuntimeError("down")):
        res = notify.send_all("hello", env=env, log=lambda *_: None)
    assert res["ntfy"].startswith("error: down")


def _gh_env(**extra):
    return {"GITHUB_TOKEN": "ghs_x", "GITHUB_REPOSITORY": "me/repo", "GITHUB_REPOSITORY_OWNER": "me",
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_RUN_ID": "99", **extra}


def test_github_issue_creates_issue_then_comments():
    with mock.patch.object(notify.requests, "get") as get, mock.patch.object(notify.requests, "post") as post:
        get.return_value.raise_for_status = lambda: None
        get.return_value.json.return_value = [{"title": "something else", "number": 1}]
        post.return_value.raise_for_status = lambda: None
        post.return_value.json.return_value = {"number": 7}
        assert notify.send_github_issue("status line", env=_gh_env(), markdown="## md")
    create, comment = post.call_args_list
    assert create.args[0] == "https://api.github.com/repos/me/repo/issues"
    assert create.kwargs["json"]["title"] == notify.GITHUB_ISSUE_TITLE
    assert comment.args[0] == "https://api.github.com/repos/me/repo/issues/7/comments"
    body = comment.kwargs["json"]["body"]
    assert body.startswith("@me status line") and "## md" in body and "actions/runs/99" in body
    assert create.kwargs["headers"]["Authorization"] == "Bearer ghs_x"


def test_github_issue_reuses_existing_and_skips_prs():
    with mock.patch.object(notify.requests, "get") as get, mock.patch.object(notify.requests, "post") as post:
        get.return_value.raise_for_status = lambda: None
        get.return_value.json.return_value = [
            {"title": notify.GITHUB_ISSUE_TITLE, "number": 3, "pull_request": {}},
            {"title": notify.GITHUB_ISSUE_TITLE, "number": 5},
        ]
        post.return_value.raise_for_status = lambda: None
        assert notify.send_github_issue("x", env=_gh_env())
    assert post.call_count == 1 and post.call_args.args[0].endswith("/issues/5/comments")


def test_github_issue_skipped_outside_actions_or_when_disabled():
    assert not notify.send_github_issue("x", env={})
    assert not notify.send_github_issue("x", env=_gh_env(TVM_GITHUB_ISSUE_NOTIFY="false"))
    assert notify.send_all("x", env={})["github-issue"] == "skipped"
