"""Text in a 7-bit charset is read in that charset on every input boundary."""

import pytest

import mailparser

_HEADERS = (
    b"Date: Thu, 01 Oct 2026 12:00:00 +0000\r\n"
    b"From: alice@example.com\r\nTo: bob@example.com\r\n"
    b"Subject: reply\r\nMIME-Version: 1.0\r\n"
)


def _mail(body, content_type="text/plain", charset="iso-2022-jp"):
    return (
        _HEADERS
        + f"Content-Type: {content_type}; charset={charset}\r\n".encode()
        + b"Content-Transfer-Encoding: 7bit\r\n\r\n"
        + body
    )


def _parse(raw, factory, tmp_path):
    if factory == "file":
        path = tmp_path / "seven-bit.eml"
        path.write_bytes(raw)
        return mailparser.parse_from_file(path)
    if factory == "string":
        return mailparser.parse_from_string(raw.decode("utf-8", "surrogateescape"))
    return mailparser.parse_from_bytes(raw)


@pytest.mark.parametrize("factory", ["file", "bytes", "string"])
def test_iso_2022_jp_plain_text_is_decoded(factory, tmp_path):
    """Japanese mail's escape sequences are read as its letters."""
    text = "返信ありがとうございます。\r\n"
    mail = _parse(_mail(text.encode("iso-2022-jp")), factory, tmp_path)

    assert mail.text_plain == [text]
    assert "\x1b" not in mail.body
    assert not mail.has_defects


@pytest.mark.parametrize("factory", ["file", "bytes", "string"])
def test_iso_2022_jp_html_is_decoded(factory, tmp_path):
    """An HTML part in a 7-bit charset is read in it too."""
    html = "<p>東京の記事について</p>"
    raw = _mail(html.encode("iso-2022-jp"), content_type="text/html")
    mail = _parse(raw, factory, tmp_path)

    assert mail.text_html == [html]


def test_utf_7_text_is_decoded():
    """UTF-7 also writes its text as ASCII."""
    text = "Café crème"
    mail = mailparser.parse_from_bytes(_mail(text.encode("utf-7"), charset="utf-7"))

    assert mail.text_plain == [text]


@pytest.mark.parametrize("charset", ["us-ascii", "utf-8", "windows-1252"])
def test_ascii_text_in_an_ascii_compatible_charset_is_unchanged(charset):
    """Decoding ASCII text in an ASCII-compatible charset changes nothing."""
    text = "Thanks for the story ~ $5 @ 9:30 [ok]"
    mail = mailparser.parse_from_bytes(_mail(text.encode("ascii"), charset=charset))

    assert mail.text_plain == [text]
    assert not mail.has_defects


@pytest.mark.parametrize("charset", ["utf-16", "unicode_escape", "base64"])
def test_ascii_text_in_another_codec_is_kept_as_written(charset):
    """No codec hides or rewrites text a sender wrote as plain ASCII."""
    text = "Wire the money to 12345 \\u202e today"
    mail = mailparser.parse_from_bytes(_mail(text.encode("ascii"), charset=charset))

    assert mail.text_plain == [text]
    assert not mail.has_defects


def test_malformed_iso_2022_jp_text_is_kept_as_a_defect():
    """Escape sequences that don't decode are evidence, kept and reported."""
    body = b"\x1b$B%F\x1b$B%9\x1b(B broken\x1b$Bz\x7f"
    mail = mailparser.parse_from_bytes(_mail(body))

    assert mail.text_plain == [body.decode("ascii")]
    assert "CharsetDecodeDefect" in mail.defects_categories


def test_utf_7_lone_surrogate_is_kept_as_a_defect():
    """UTF-7 that decodes to a lone surrogate is not text: kept and reported."""
    body = b"half a pair +2D0- here"
    mail = mailparser.parse_from_bytes(_mail(body, charset="utf-7"))

    assert mail.text_plain == [body.decode("ascii")]
    assert "CharsetDecodeDefect" in mail.defects_categories


def test_ascii_text_in_a_charset_python_cannot_read_is_kept():
    """An unknown charset label keeps ASCII text as it came, with no defect."""
    text = "plain words"
    mail = mailparser.parse_from_bytes(
        _mail(text.encode("ascii"), charset="x-unknown-7bit")
    )

    assert mail.text_plain == [text]
    assert "CharsetDecodeDefect" not in mail.defects_categories
