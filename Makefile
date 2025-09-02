PYTHON := $(shell command -v uv >/dev/null 2>&1 && echo "uv run python" || echo "python")
TEST := $(PYTHON) -m unittest

.PHONY: test
test:
	$(TEST) discover -s tests -p "test_*.py"
