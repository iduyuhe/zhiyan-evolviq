# Contributing to EvolvIQ

Thanks for your interest in contributing! We welcome contributions from the community.

## How to Contribute

1. **Fork** the repository
2. **Create a feature branch**: `git checkout -b feat/your-feature`
3. **Commit** your changes with clear messages
4. **Push** to your fork and open a **Pull Request**

## Development Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m src.runtime.main
```

## Code Style

- Python: Follow [PEP 8](https://peps.python.org/pep-0008/), type hints required
- TypeScript: Follow project conventions, lint with `tsc --noEmit`
- All agents must implement `BaseAgent.analyze(goal) -> dict`
- Seed data over LLM inference — facts are facts

## Pull Request Checklist

- [ ] Tests pass: `pytest tests/ -q`
- [ ] TypeScript compiles: `cd studio && tsc --noEmit`
- [ ] New agents include tools.py + agent.py + __init__.py
- [ ] New agents registered in router.py, federation.py, authorization.py, agents_api.py
- [ ] New agents have frontend rendering in GenericResultView.tsx

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
