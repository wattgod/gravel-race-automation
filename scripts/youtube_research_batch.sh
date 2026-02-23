#!/bin/bash
# Parallel YouTube research runner
# Usage: bash scripts/youtube_research_batch.sh <slug_file> [parallel_jobs]
#
# Runs youtube_research.py for each slug in parallel batches

SLUG_FILE="${1:?Usage: $0 <slug_file> [parallel_jobs]}"
PARALLEL="${2:-4}"
OUTPUT_DIR="youtube-research-results"

mkdir -p "$OUTPUT_DIR"

echo "=== YouTube Research Batch ==="
echo "Slugs: $(wc -l < "$SLUG_FILE" | tr -d ' ')"
echo "Parallel jobs: $PARALLEL"
echo "Output: $OUTPUT_DIR/"
echo ""

# Process each slug, skip if already researched
research_one() {
    local slug="$1"
    if [ -f "$OUTPUT_DIR/${slug}.json" ]; then
        echo "  SKIP $slug (already researched)"
        return 0
    fi
    python3 scripts/youtube_research.py --slug "$slug" --max-results 5 --transcript --output "$OUTPUT_DIR/" 2>&1
}
export -f research_one
export OUTPUT_DIR

# Use xargs for parallel execution
cat "$SLUG_FILE" | xargs -P "$PARALLEL" -I {} bash -c 'research_one "$@"' _ {}

DONE=$(ls "$OUTPUT_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')
echo ""
echo "=== Complete: $DONE research files in $OUTPUT_DIR/ ==="
