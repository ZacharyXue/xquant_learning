import pytest
from engine.strategy_base import StrategyBase, Quote
from engine.strategy_registry import register, get, list_all, create, clear


@pytest.fixture(autouse=True)
def clean():
    clear()
    yield
    clear()


class TestRegister:
    def test_register_strategy(self):
        @register
        class MyStrat(StrategyBase):
            name = "my_test"
            display_name = "My Test"
            def on_quote(self, quote):
                return None
        assert get("my_test") is MyStrat
        assert "my_test" in list_all()

    def test_missing_name_raises(self):
        with pytest.raises(ValueError, match="must have a 'name'"):
            @register
            class Bad(StrategyBase):
                def on_quote(self, quote):
                    return None

    def test_create_strategy(self):
        @register
        class S(StrategyBase):
            name = "s1"
            def on_quote(self, q):
                return None
        instance = create("s1", {"display_name": "Override"})
        assert isinstance(instance, S)
        assert instance.name == "s1"

    def test_create_nonexistent(self):
        with pytest.raises(ValueError, match="not found"):
            create("nope", {})

    def test_list_all(self):
        @register
        class S1(StrategyBase):
            name = "a"
            def on_quote(self, q):
                return None
        @register
        class S2(StrategyBase):
            name = "b"
            def on_quote(self, q):
                return None
        assert set(list_all()) == {"a", "b"}
