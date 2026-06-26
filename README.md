# PromptPress

**Budgeted context compression for LLM applications.** Cut input tokens 30–70% before they hit the API — without losing the facts, the code, or the exact strings your model needs.

Zero runtime dependencies. Pure Python stdlib. The `anthropic` SDK is optional (for exact token counts and the drop-in client wrapper).

## Why

Input tokens are the dominant cost of most LLM applications — long system prompts, repeated chat history, concatenated documents, verbose tool output. Most of that text is *redundant to a language model*: duplicated paragraphs, markdown decoration, filler words, comments restating the code below them. PromptPress removes exactly that, in order of increasing loss, and **stops the moment your token budget is met** — text is never made lossier than the budget demands.

```
input ──► L0 whitespace ──► L1 markdown ──► L1 html ──► L1 code ──► L2 quoted ──► L2 dedup ──► L2 stopword ──► L3 extract ──► output
          (lossless)        (decoration)    (tags)      (comments)  (email       (Jaccard     (telegraphic    (TextRank
                                                                    cruft)       shingles)    prose)          summarizer)
                       │ budget met? stop here — later stages never run │
```

## Benchmark

Real output of `python benchmarks/run.py` (estimated tokens, three realistic context types):

| sample | tokens | L0 lossless | L1 | L2 | L3 aggressive |
|---|---|---|---|---|---|
| prose | 665 | -0% | -0% | -16% | -65% |
| code-heavy | 582 | -0% | -29% | -29% | -29% |
| chat-log | 313 | -0% | -0% | -87% | -87% |

## Install

```bash
pip install -e .            # library + CLI
pip install -e ".[anthropic]"  # + exact token counting & client middleware
```

## Usage

### Python API

```python
from promptpress import compress

result = compress(big_context, budget=4000)
print(result.summary())
# tokens: 9120 -> 3890 (57.3% saved)
# budget 4000: MET
#   [0] whitespace  -212 tokens
#   [1] markdown    -148 tokens
#   [2] dedup       -3204 tokens
#   [2] stopword    -1666 tokens
send_to_model(result.text)
```

### Drop-in Anthropic client

```python
from promptpress.middleware import CompressedAnthropic

client = CompressedAnthropic(budget_per_message=4000)
client.messages.create(  # same API as anthropic.Anthropic
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": huge_prompt}],
)
```

### CLI

```bash
promptpress compress context.md --budget 4000 --report -o pressed.md
promptpress count context.md
cat history.txt | promptpress compress - --max-level 2
```

Exit code `2` means the budget could not be met even at the maximum allowed level — your signal to truncate or split instead.

## Design

- **Aggressiveness ladder.** Every strategy declares a level: 0 lossless → 3 aggressive. The pipeline runs cheapest-first and short-circuits on budget. A stage that fails to shrink the text is discarded (compression is monotonic by construction).
- **Protected regions.** Code fences, inline code, URLs, and quoted strings are swapped for sentinels before any prose rewriting and restored after — exact-match semantics survive every level.
- **Code-aware, not regex-naive.** Python blocks go through the real `tokenize` module, so `x = "# not a comment"` survives while comments and docstrings die. Other languages get a conservative full-line pass.
- **Email-aware.** The `quoted` stage strips reply chains (`> ...` and `On … wrote:`), `-- ` signatures, mobile footers, and confidentiality disclaimers — the bulk of any context built from email threads or support tickets.
- **Dedup is exact Jaccard over word 3-shingles** — the MinHash idea without the hashing, because prompts have hundreds of paragraphs, not millions.
- **Extractive, never generative.** Level 3 is TextRank (PageRank power iteration over a sentence-similarity graph) implemented from scratch in ~50 lines. It selects your sentences; it cannot hallucinate new ones.
- **Token estimation without a tokenizer.** Word/symbol pass blended with character density, CJK-aware, ~±8% vs real BPE counts — enough for budgeting, zero dependencies. Exact counts available via the Anthropic API when installed.

## Tests

```bash
pip install -e ".[dev]"
pytest -v   # every strategy, budget logic, protection invariants, CLI
```

## License

MIT
