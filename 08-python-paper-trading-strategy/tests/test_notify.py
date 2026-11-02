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
