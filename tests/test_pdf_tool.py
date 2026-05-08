from app.tools.pdf_tool import extract_reproduction_links, normalize_wrapped_urls


def test_extract_reproduction_links_recovers_wrapped_project_url():
    text = "Code and weights are available at www.verlab.dcc.ufmg. br/descriptors/xfeat_cvpr24."

    assert normalize_wrapped_urls(text).endswith("www.verlab.dcc.ufmg.br/descriptors/xfeat_cvpr24.")
    assert extract_reproduction_links(text) == [
        "www.verlab.dcc.ufmg.br/descriptors/xfeat_cvpr24"
    ]
