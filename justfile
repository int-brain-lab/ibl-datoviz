# Pass arguments through the shell without interpolating user input into shell code.
set positional-arguments

# List contributor commands.
default:
    @just --list

# Install locked dependencies and prepare fixtures plus real-data review assets.
setup datoviz:
    uv sync --group dev --locked
    uv run --frozen tools/review.py setup --datoviz "$1"

# Install locked dependencies and prepare fixtures, skipping review data downloads.
setup-tests datoviz:
    uv sync --group dev --locked
    uv run --frozen tools/review.py setup --datoviz "$1" --tests-only

# Check the remembered Datoviz source and loaded native library.
doctor:
    uv run --frozen tools/review.py doctor

# Run the test suite, or forward a test path and pytest options.
test *args:
    uv run --frozen tools/review.py test -- "$@"

# Open all six examples or one named example; extra options include --frames N.
review example='all' *args:
    uv run --frozen tools/review.py run "$@"

# Check Python style and correctness with Ruff.
lint:
    uv run --frozen ruff check .

# Build documentation strictly using its pinned extra dependencies.
docs:
    uv run --frozen --with-requirements docs/requirements.txt mkdocs build --strict
