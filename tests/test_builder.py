from agent.builder import to_identifier


def test_to_identifier_normalizes_display_names():
    assert to_identifier("Chen Jie") == "chen_jie"
    assert to_identifier("Alice Chen") == "alice_chen"
    assert to_identifier("__moderator__") == "moderator"
    assert to_identifier("123bad") == "a_123bad"
