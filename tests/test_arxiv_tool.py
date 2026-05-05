from app.tools.arxiv_tool import extract_arxiv_id, parse_arxiv_atom_feed


def test_extract_arxiv_id_from_url():
    assert extract_arxiv_id("https://arxiv.org/abs/2301.12345") == "2301.12345"


def test_extract_arxiv_id_from_pdf_url():
    assert extract_arxiv_id("https://arxiv.org/pdf/2301.12345") == "2301.12345"


def test_extract_arxiv_id_from_bare_id():
    assert extract_arxiv_id("2301.12345") == "2301.12345"


def test_extract_arxiv_id_with_version():
    assert extract_arxiv_id("https://arxiv.org/abs/2301.12345v2") == "2301.12345v2"


def test_extract_arxiv_id_invalid():
    assert extract_arxiv_id("not-an-arxiv-id") is None


def test_parse_arxiv_atom_feed():
    feed = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2301.12345v2</id>
        <updated>2023-01-02T00:00:00Z</updated>
        <published>2023-01-01T00:00:00Z</published>
        <title> A   Useful Paper </title>
        <summary> This paper
        does useful things. </summary>
        <author><name>Ada Lovelace</name></author>
        <arxiv:primary_category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
        <link title="pdf" href="http://arxiv.org/pdf/2301.12345v2"/>
      </entry>
    </feed>
    """

    papers = parse_arxiv_atom_feed(feed)

    assert papers == [{
        "arxiv_id": "2301.12345v2",
        "title": "A Useful Paper",
        "summary": "This paper does useful things.",
        "authors": ["Ada Lovelace"],
        "published": "2023-01-01T00:00:00Z",
        "updated": "2023-01-02T00:00:00Z",
        "abs_url": "http://arxiv.org/abs/2301.12345v2",
        "pdf_url": "http://arxiv.org/pdf/2301.12345v2",
        "primary_category": "cs.LG",
    }]
