# NagaAI provider for Hermes Agent

Adds [NagaAI](https://naga.ac) to Hermes Agent as the `nagaai` provider over the
OpenAI Responses API.

```bash
hermes plugins install nagaai
export NAGAAI_API_KEY="ng-..."
hermes --provider nagaai --model anthropic/claude-sonnet-5.5
```

Keys are on the [API Keys](https://naga.ac/dashboard/api-keys) page.

## What it does

- Registers one model provider: base URL `https://api.naga.ac/v1`, key from
  `NAGAAI_API_KEY`, optional `NAGAAI_BASE_URL` override, Hermes' Responses mode.
- Fills the `/model` picker with the chat models that accept tool calls on the
  Responses endpoint, read from the public catalog `GET /v1/models`. If the
  catalog is unreachable, the picker shows a short built-in list.
- Uses `google/gemini-3.5-flash-lite` for auxiliary calls (compression, titles).

## Disclosure

- Prompts, tool results and `NAGAAI_API_KEY` go to `api.naga.ac` through Hermes'
  own client. NagaAI forwards each request to the upstream provider serving the
  chosen model and bills your prepaid NagaAI balance.
- The plugin itself makes one request: `GET https://api.naga.ac/v1/models`,
  without the key, to build the picker. It registers no tools, hooks, commands
  or threads, reads and writes no files, runs no processes, adds no tracking
  headers and does not update itself. No dependencies.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Docs: <https://docs.naga.ac> · License: MIT
