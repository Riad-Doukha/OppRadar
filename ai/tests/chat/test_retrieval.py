from oppradar_ai.chat.retrieval import OpportunityIndex


def test_index_returns_top_k(fixture_opportunities, fake_embed):
    index = OpportunityIndex(fixture_opportunities, embed_fn=fake_embed).build()
    hits = index.search("machine learning internship", k=5)
    assert len(hits) == 5
    scores = [score for _, score in hits]
    assert scores == sorted(scores, reverse=True)


def test_index_empty(fixture_opportunities, fake_embed):
    index = OpportunityIndex([], embed_fn=fake_embed).build()
    assert index.search("anything", k=5) == []


def test_index_search_without_build(fixture_opportunities, fake_embed):
    # search() must lazily build the index.
    index = OpportunityIndex(fixture_opportunities, embed_fn=fake_embed)
    assert not index.is_built
    assert len(index.search("python", k=3)) == 3
    assert index.is_built


def test_k_larger_than_corpus(fixture_opportunities, fake_embed):
    index = OpportunityIndex(fixture_opportunities[:3], embed_fn=fake_embed).build()
    assert len(index.search("backend", k=50)) == 3


def test_save_and_load_roundtrip(fixture_opportunities, fake_embed, tmp_path):
    index = OpportunityIndex(fixture_opportunities, embed_fn=fake_embed).build()
    path = tmp_path / "index.npz"
    index.save(path)

    loaded = OpportunityIndex.load(path, embed_fn=fake_embed)
    assert len(loaded.opportunities) == len(fixture_opportunities)
    assert loaded.opportunities[0].title == fixture_opportunities[0].title
    # Loaded index searches without re-embedding.
    assert len(loaded.search("data", k=4)) == 4
